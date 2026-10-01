import os
import subprocess
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import pytest

from app.contexts.transcription_evidence import (
    TranscriptEvidenceStatus,
    TranscriptionExecutionError,
    TranscriptionExecutionRequest,
)
from app.contexts.work_execution import TranscriptionOperationInput
from app.core.config.deployment import LocalTranscriptionConfiguration
from app.infrastructure.transcription import CTranslate2WhisperExecutionAdapter
from app.infrastructure.transcription.ctranslate2_whisper.adapter import Engine
from app.infrastructure.transcription.ctranslate2_whisper.types import Segment, Word
from app.shared.ids import EntityId
from app.shared.time import FixedClock
from tests.test_faster_whisper_execution_adapter import NOW, StaticResolver


def request() -> TranscriptionExecutionRequest:
    identity = EntityId("42000000-0000-0000-0000-000000000001")
    return TranscriptionExecutionRequest(operation_id=identity, attempt_id=identity,
        fence_generation=1, work_key="a" * 64, input=TranscriptionOperationInput(
            asset_id=identity, manifest_id=identity, manifest_version="1.0", asset_format="wav",
            execution_profile_id="ct2-whisper-large-v3-turbo-cpu-int8",
            execution_profile_version="1.0", requested_language="en", request_word_timing=True))


class Decoder:
    identity = ("8.1", "a" * 64, "8.1", "b" * 64)

    def decode(self, path: Path, heartbeat: Callable[[], None]) -> object:
        heartbeat()
        return "synthetic PCM"


class Model:
    def __init__(self, *, failure: Exception | None = None, after: bool = False,
                 segments: list[Segment] | None = None) -> None:
        self.failure, self.after = failure, after
        self.segments = segments if segments is not None else [Segment(" Hello world ", 1, 2, [
            Word(" Hello", .95, 1.4, .9), Word(" world ", 1.4, 2.05, .8)])]

    def transcribe(self, audio: Any, *, language: str | None, word_timestamps: bool,
                   renew_lease: Callable[[], None]) -> Iterable[Segment]:
        assert audio == "synthetic PCM" and language == "en" and word_timestamps
        renew_lease()
        if self.failure and not self.after:
            raise self.failure
        yield from self.segments
        if self.failure:
            raise self.failure


def configuration(tmp_path: Path, **changes: Any) -> LocalTranscriptionConfiguration:
    values: dict[str, Any] = dict(provider="stageflow-ctranslate2-whisper",
        model_path=str(tmp_path), model_version="synthetic",
        ffmpeg_path=str(tmp_path / "ffmpeg.exe"), device="cpu", compute_type="int8",
        execution_profile_id="ct2-whisper-large-v3-turbo-cpu-int8")
    values.update(changes)
    return LocalTranscriptionConfiguration(**values)


def adapter(tmp_path: Path, model: Model | None = None,
            **changes: Any) -> CTranslate2WhisperExecutionAdapter:
    (tmp_path / "tokenizer.json").write_text("{}")
    return CTranslate2WhisperExecutionAdapter(configuration(tmp_path),
        resolver=StaticResolver(tmp_path / "synthetic.wav"), clock=FixedClock(NOW),
        model_factory=lambda *args, **kwargs: model or Model(),
        decoder_factory=lambda path: Decoder(), version_lookup=lambda name: "4.8.1", **changes)


def test_adapter_normalizes_contract_deterministically(tmp_path: Path) -> None:
    port = adapter(tmp_path)
    renewals: list[None] = []
    first = port.execute(request(), lambda: renewals.append(None))
    second = port.execute(request(), lambda: None)
    assert first == second and first.status is TranscriptEvidenceStatus.COMPLETE
    assert first.provenance.provider_id == "stageflow-ctranslate2-whisper"
    assert first.provenance.provider_version == "1.0"
    assert first.provenance.execution_tool_id == "ctranslate2"
    assert first.provenance.execution_tool_version == "4.8.1"
    assert first.provenance.execution_revision == "stageflow-ctranslate2-whisper-adapter-1.0"
    assert first.language == "en"
    segment = first.segments[0]
    assert segment.asset_start_microseconds == 950000
    assert segment.asset_end_microseconds == 2050000
    assert [w.text for w in segment.words] == ["Hello", "world"]
    assert [w.confidence for w in segment.words] == [.9, .8]
    assert all(w.confidence_semantics == "provider_probability" for w in segment.words)
    assert len(renewals) == 4
    assert first.limitations == (
        "provider language probability not persisted", "speaker labels unavailable")
    assert (port.decode_tool_version, port.decode_tool_sha256,
            port.probe_tool_version, port.probe_tool_sha256) == Decoder.identity
    assert all(str(tmp_path) not in item for item in first.limitations)


@pytest.mark.parametrize("error", [RuntimeError("private"),
                                   ValueError("private"), OSError("private")])
def test_partial_after_iteration_failure(tmp_path: Path, error: Exception) -> None:
    result = adapter(tmp_path, Model(failure=error, after=True)).execute(request(), lambda: None)
    assert result.status is TranscriptEvidenceStatus.PARTIAL
    assert result.partial_reason == "provider_iteration_failed" and len(result.segments) == 1
    assert result.limitations == (
        "provider language probability not persisted", "speaker labels unavailable")


def test_index_error_after_segment_is_retryable_failure(tmp_path: Path) -> None:
    with pytest.raises(TranscriptionExecutionError) as caught:
        adapter(tmp_path, Model(failure=IndexError("private"), after=True)).execute(
            request(), lambda: None)
    assert caught.value.reason_code == "provider_execution_failed"
    assert caught.value.retryable
    assert "private" not in caught.value.diagnostic_summary


@pytest.mark.parametrize("error,code,retry", [
    (RuntimeError("private"), "provider_execution_failed", True),
    (IndexError("private"), "provider_execution_failed", True),
    (RuntimeError("cudnn64_9.dll private"), "cuda_runtime_unavailable", False)])
def test_failure_before_result(tmp_path: Path, error: Exception, code: str, retry: bool) -> None:
    with pytest.raises(TranscriptionExecutionError) as caught:
        adapter(tmp_path, Model(failure=error)).execute(request(), lambda: None)
    assert caught.value.reason_code == code and caught.value.retryable is retry
    assert "private" not in caught.value.diagnostic_summary


def test_empty_result_and_invalid_timing_are_refused(tmp_path: Path) -> None:
    with pytest.raises(TranscriptionExecutionError, match="provider_no_speech_segments"):
        adapter(tmp_path, Model(segments=[])).execute(request(), lambda: None)
    with pytest.raises(TranscriptionExecutionError, match="provider_timing_invalid"):
        adapter(tmp_path, Model(segments=[Segment("x", float("nan"), 1, None)])).execute(
            request(), lambda: None)


def test_invalid_probability_omitted(tmp_path: Path) -> None:
    result = adapter(tmp_path, Model(segments=[Segment("x", 0, 1, [
        Word("x", 0, 1, float("nan"))])])).execute(request(), lambda: None)
    word = result.segments[0].words[0]
    assert word.confidence is None and word.confidence_semantics is None
    assert word.limitations


@pytest.mark.parametrize("device,compute", [("cuda", "int8"), ("cpu", "float16"),
                                          ("auto", "int8"), ("cpu", "float32")])
def test_pair_refused_in_config_and_adapter(tmp_path: Path, device: str, compute: str) -> None:
    with pytest.raises(ValueError):
        configuration(tmp_path, device=device, compute_type=compute)
    invalid = configuration(tmp_path).model_copy(update=dict(device=device, compute_type=compute))
    with pytest.raises(ValueError):
        CTranslate2WhisperExecutionAdapter(invalid, resolver=StaticResolver(tmp_path),
                                          clock=FixedClock(NOW))


def test_model_tokenizer_and_runtime_version_required(tmp_path: Path) -> None:
    config = configuration(tmp_path)
    with pytest.raises(TranscriptionExecutionError, match="provider_model_unavailable"):
        CTranslate2WhisperExecutionAdapter(config, resolver=StaticResolver(tmp_path),
                                          clock=FixedClock(NOW))
    (tmp_path / "tokenizer.json").touch()
    with pytest.raises(TranscriptionExecutionError, match="runtime_version_mismatch"):
        CTranslate2WhisperExecutionAdapter(config, resolver=StaticResolver(tmp_path),
            clock=FixedClock(NOW), version_lookup=lambda name: "0.0")


@pytest.mark.parametrize("path", [None, "ffmpeg", "../ffmpeg", "C:/tools/ffmpeg.cmd"])
def test_explicit_ffmpeg_configuration_required(tmp_path: Path, path: str | None) -> None:
    with pytest.raises(ValueError):
        configuration(tmp_path, ffmpeg_path=path)


def test_defaults_unchanged_and_both_new_profiles_validate(tmp_path: Path) -> None:
    old = LocalTranscriptionConfiguration(model_path=str(tmp_path), model_version="synthetic")
    assert (old.provider, old.device, old.compute_type, old.ffmpeg_path) == (
        "faster-whisper", "cuda", "float16", None)
    assert old.execution_profile_id == "faster-whisper-large-v3-turbo-cuda-float16"
    for device, compute in (("cpu", "int8"), ("cuda", "float16")):
        assert configuration(tmp_path, device=device, compute_type=compute).device == device


@pytest.mark.parametrize("profile", [None, "faster-whisper-large-v3-turbo-cuda-float16",
                                    "faster-whisper", "faster-whisper-custom"])
def test_stageflow_refuses_legacy_profile_identity(profile: str | None) -> None:
    values = configuration(Path.cwd()).model_dump()
    if profile is None:
        values.pop("execution_profile_id")
    else:
        values["execution_profile_id"] = profile
    with pytest.raises(ValueError, match="distinct execution profile id"):
        LocalTranscriptionConfiguration.model_validate(values)


@pytest.mark.parametrize("device,compute", [("cuda", "float16"), ("cpu", "int8")])
def test_stageflow_accepts_distinct_operator_profile(device: str, compute: str) -> None:
    config = configuration(Path.cwd(), device=device, compute_type=compute,
                           execution_profile_id="operator-event-profile")
    assert config.execution_profile_id == "operator-event-profile"


def test_clean_process_exercises_adapter_and_native_loader_without_forbidden_imports(
    tmp_path: Path,
) -> None:
    # The real engine modules need the optional transcription-core runtime.
    pytest.importorskip("numpy")
    pytest.importorskip("tokenizers")
    script = '''
import importlib
import sys
from pathlib import Path
for module in ("engine", "decode", "alignment", "tokenizer", "features"):
    importlib.import_module("app.infrastructure.transcription.ctranslate2_whisper." + module)
importlib.import_module("tokenizers")
from tests.test_ctranslate2_whisper_adapter import adapter, request
result = adapter(Path(sys.argv[1])).execute(request(), lambda: None)
assert result.segments
from app.infrastructure.transcription.ctranslate2_whisper.runtime import inference_runtime
try:
    import importlib.metadata
    importlib.metadata.distribution("ctranslate2")
except importlib.metadata.PackageNotFoundError:
    pass
else:
    assert hasattr(inference_runtime(), "Whisper")
for name in ("av", "faster_whisper", "huggingface_hub", "onnxruntime", "tqdm"):
    assert not any(m == name or m.startswith(name + ".") for m in sys.modules), name
'''
    environment = dict(os.environ)
    environment.pop("STAGEFLOW_API_SHARED_SECRET", None)
    run = subprocess.run([sys.executable, "-c", script, str(tmp_path)], env=environment,
                         capture_output=True, text=True, timeout=60, check=False)
    assert run.returncode == 0, run.stderr


def test_missing_native_runtime_is_not_retryable(tmp_path: Path) -> None:
    (tmp_path / "tokenizer.json").touch()

    def factory(*args: Any, **kwargs: Any) -> Engine:
        raise ImportError("private")

    with pytest.raises(TranscriptionExecutionError) as caught:
        CTranslate2WhisperExecutionAdapter(configuration(tmp_path),
            resolver=StaticResolver(tmp_path),
            clock=FixedClock(NOW), decoder_factory=lambda path: Decoder(),
            model_factory=factory, version_lookup=lambda name: "4.8.1")
    assert caught.value.reason_code == "provider_runtime_unavailable" and not caught.value.retryable


def test_decode_failure_preserves_retry_code(tmp_path: Path) -> None:
    class FailedDecoder(Decoder):
        def decode(self, path: Path, heartbeat: Callable[[], None]) -> Any:
            raise TranscriptionExecutionError("media_decode_failed", retryable=True,
                                               diagnostic_summary="local audio decode unavailable")

    (tmp_path / "tokenizer.json").touch()
    port = CTranslate2WhisperExecutionAdapter(configuration(tmp_path),
        resolver=StaticResolver(tmp_path), clock=FixedClock(NOW),
        model_factory=lambda *a, **kw: Model(), decoder_factory=lambda _: FailedDecoder(),
        version_lookup=lambda _: "4.8.1")
    with pytest.raises(TranscriptionExecutionError) as caught:
        port.execute(request(), lambda: None)
    assert caught.value.reason_code == "media_decode_failed" and caught.value.retryable


def test_window_lease_loss_is_not_partial_evidence(tmp_path: Path) -> None:
    from app.contexts.work_execution.repository import WorkExecutionLeaseLostError

    error = WorkExecutionLeaseLostError("synthetic expired lease")
    port = adapter(tmp_path, Model(failure=error, after=True))
    with pytest.raises(WorkExecutionLeaseLostError) as caught:
        port.execute(request(), lambda: None)
    assert caught.value is error
