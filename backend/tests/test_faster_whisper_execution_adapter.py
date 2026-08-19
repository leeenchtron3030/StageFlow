from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from app.contexts.transcription_evidence import TranscriptEvidenceStatus
from app.contexts.transcription_evidence.application import (
    TranscriptionExecutionError,
    TranscriptionExecutionRequest,
)
from app.contexts.work_execution import TranscriptionOperationInput
from app.core.config.deployment import LocalTranscriptionConfiguration
from app.infrastructure.transcription.faster_whisper import (
    FasterWhisperExecutionAdapter,
    FasterWhisperInfo,
    FasterWhisperModel,
    FasterWhisperModelFactory,
    MediaPathResolver,
)
from app.shared.ids import EntityId
from app.shared.time import FixedClock

NOW = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


@dataclass
class RawWord:
    word: str
    start: float
    end: float
    probability: float


@dataclass
class RawSegment:
    text: str
    start: float
    end: float
    words: tuple[RawWord, ...] | None


@dataclass
class RawInfo:
    language: str


class StaticResolver:
    def __init__(self, path: Path) -> None:
        self.path = path

    def resolve(self, input: TranscriptionOperationInput) -> Path:
        del input
        return self.path


class FakeModel:
    def __init__(
        self,
        *,
        fail_after_first: bool = False,
        immediate_failure: Exception | None = None,
        iteration_failure: Exception | None = None,
    ) -> None:
        self.fail_after_first = fail_after_first
        self.immediate_failure = immediate_failure
        self.iteration_failure = iteration_failure

    def transcribe(
        self,
        audio: str,
        *,
        language: str | None,
        beam_size: int,
        word_timestamps: bool,
        vad_filter: bool,
        condition_on_previous_text: bool,
    ) -> tuple[object, FasterWhisperInfo]:
        if self.immediate_failure is not None:
            raise self.immediate_failure
        assert audio.endswith("sample.wav")
        assert language == "en"
        assert beam_size == 5
        assert word_timestamps is True
        assert vad_filter is False
        assert condition_on_previous_text is True

        first = RawSegment(
            text=" Hello world ",
            start=1.0,
            end=2.0,
            words=(
                RawWord(" Hello", 0.95, 1.4, 0.9),
                RawWord(" world", 1.4, 2.05, 0.8),
            ),
        )

        def values() -> object:
            yield first
            if self.iteration_failure is not None:
                raise self.iteration_failure
            if self.fail_after_first:
                raise RuntimeError("simulated provider iteration failure")

        return values(), RawInfo(language="en")


def _configuration(model_path: Path) -> LocalTranscriptionConfiguration:
    return LocalTranscriptionConfiguration(
        model_version="0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf",
        model_path=str(model_path),
    )


def _request() -> TranscriptionExecutionRequest:
    return TranscriptionExecutionRequest(
        operation_id=EntityId("42000000-0000-0000-0000-000000000001"),
        attempt_id=EntityId("42000000-0000-0000-0000-000000000002"),
        fence_generation=1,
        work_key="a" * 64,
        input=TranscriptionOperationInput(
            asset_id=EntityId("42000000-0000-0000-0000-000000000003"),
            manifest_id=EntityId("42000000-0000-0000-0000-000000000004"),
            manifest_version="1.0",
            asset_format="wav",
            execution_profile_id="faster-whisper-large-v3-turbo-cuda-float16",
            execution_profile_version="1.0",
            requested_language="en",
            request_word_timing=True,
        ),
    )


def _adapter(
    tmp_path: Path, model: FakeModel
) -> tuple[FasterWhisperExecutionAdapter, list[tuple[str, str, str]]]:
    model_path = tmp_path / "model"
    model_path.mkdir()
    media_path = tmp_path / "sample.wav"
    media_path.write_bytes(b"synthetic audio")
    initialized: list[tuple[str, str, str]] = []

    def factory(
        model_size_or_path: str, *, device: str, compute_type: str
    ) -> FasterWhisperModel:
        initialized.append((model_size_or_path, device, compute_type))
        return cast(FasterWhisperModel, model)

    adapter = FasterWhisperExecutionAdapter(
        _configuration(model_path),
        resolver=cast(MediaPathResolver, StaticResolver(media_path)),
        clock=FixedClock(NOW),
        model_factory=cast(FasterWhisperModelFactory, factory),
        version_lookup=lambda distribution: {
            "faster-whisper": "1.2.1",
            "ctranslate2": "4.8.1",
        }[distribution],
    )
    return adapter, initialized


def test_adapter_normalizes_exact_qualified_cuda_result_deterministically(
    tmp_path: Path,
) -> None:
    adapter, initialized = _adapter(tmp_path, FakeModel())
    renewals = 0

    def renew() -> None:
        nonlocal renewals
        renewals += 1

    first = adapter.execute(_request(), renew)
    second = adapter.execute(_request(), renew)

    assert initialized == [(str(tmp_path / "model"), "cuda", "float16")]
    assert first == second
    assert first.status is TranscriptEvidenceStatus.COMPLETE
    assert first.provenance.provider_id == "faster-whisper"
    assert first.provenance.provider_version == "1.2.1"
    assert first.provenance.model_id == "large-v3-turbo"
    assert first.provenance.model_version == (
        "0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf"
    )
    assert first.provenance.execution_tool_id == "ctranslate2"
    assert first.provenance.execution_tool_version == "4.8.1"
    assert first.language == "en"
    assert len(first.segments) == 1
    segment = first.segments[0]
    assert segment.asset_start_microseconds == 950_000
    assert segment.asset_end_microseconds == 2_050_000
    assert [word.confidence for word in segment.words] == [0.9, 0.8]
    assert all(
        word.confidence_semantics == "provider_probability"
        for word in segment.words
    )
    assert renewals == 4


def test_adapter_preserves_partial_provider_result(tmp_path: Path) -> None:
    adapter, _ = _adapter(tmp_path, FakeModel(fail_after_first=True))

    result = adapter.execute(_request(), lambda: None)

    assert result.status is TranscriptEvidenceStatus.PARTIAL
    assert result.partial_reason == "provider_iteration_failed"
    assert len(result.segments) == 1


@pytest.mark.parametrize(
    "model",
    (
        FakeModel(immediate_failure=IndexError("provider media index failed")),
        FakeModel(iteration_failure=IndexError("provider segment index failed")),
    ),
)
def test_adapter_normalizes_provider_index_error_as_retryable_failure(
    tmp_path: Path,
    model: FakeModel,
) -> None:
    adapter, _ = _adapter(tmp_path, model)

    with pytest.raises(TranscriptionExecutionError) as captured:
        adapter.execute(_request(), lambda: None)

    assert captured.value.reason_code == "provider_execution_failed"
    assert captured.value.retryable is True
    assert captured.value.diagnostic_summary == "faster-whisper execution failed"


def test_adapter_rejects_unqualified_runtime_without_cpu_fallback(
    tmp_path: Path,
) -> None:
    model_path = tmp_path / "model"
    model_path.mkdir()
    resolver = cast(MediaPathResolver, StaticResolver(tmp_path / "sample.wav"))
    factory_called = False

    def factory(
        model_size_or_path: str, *, device: str, compute_type: str
    ) -> FasterWhisperModel:
        del model_size_or_path, device, compute_type
        nonlocal factory_called
        factory_called = True
        return cast(FasterWhisperModel, FakeModel())

    with pytest.raises(TranscriptionExecutionError, match="provider_version_mismatch"):
        FasterWhisperExecutionAdapter(
            _configuration(model_path),
            resolver=resolver,
            clock=FixedClock(NOW),
            model_factory=cast(FasterWhisperModelFactory, factory),
            version_lookup=lambda distribution: {
                "faster-whisper": "1.2.0",
                "ctranslate2": "4.8.1",
            }[distribution],
        )

    assert factory_called is False
