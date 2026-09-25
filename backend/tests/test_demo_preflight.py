from __future__ import annotations

import json
import wave
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from app.contexts.transcription_evidence import (
    NormalizedTranscriptResult,
    TranscriptionExecutionError,
    TranscriptionExecutionRequest,
)
from app.core.config.deployment import LocalTranscriptionConfiguration, RuntimeProfile
from app.demo import cli
from app.demo.cli import verify_transcription_inference, write_silent_transcription_probe
from app.infrastructure.transcription import FasterWhisperExecutionAdapter


class FailingProbeExecution:
    def __init__(self, error: TranscriptionExecutionError) -> None:
        self.error = error
        self.requests: list[TranscriptionExecutionRequest] = []
        self.renewals = 0

    def execute(
        self,
        request: TranscriptionExecutionRequest,
        renew_lease: Callable[[], None],
    ) -> NormalizedTranscriptResult:
        self.requests.append(request)
        renew_lease()
        self.renewals += 1
        raise self.error


def _configuration(tmp_path: Path) -> LocalTranscriptionConfiguration:
    return LocalTranscriptionConfiguration(
        model_version="0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf",
        model_path=str(tmp_path / "model"),
    )


def test_silent_probe_is_valid_mono_pcm_audio(tmp_path: Path) -> None:
    path = tmp_path / "probe.wav"

    write_silent_transcription_probe(path)

    with wave.open(str(path), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2
        assert audio.getframerate() == 16_000
        assert audio.getnframes() == 16_000


def test_preflight_accepts_no_speech_only_after_real_provider_execution(
    tmp_path: Path,
) -> None:
    execution = FailingProbeExecution(
        TranscriptionExecutionError(
            "provider_no_speech_segments",
            retryable=False,
            diagnostic_summary="faster-whisper returned no speech segments",
        )
    )
    configuration = _configuration(tmp_path)

    verify_transcription_inference(
        cast(FasterWhisperExecutionAdapter, execution),
        configuration,
        "demo-deployment",
    )

    assert execution.renewals == 1
    assert len(execution.requests) == 1
    assert execution.requests[0].input.execution_profile_id == (
        configuration.execution_profile_id
    )
    assert execution.requests[0].input.request_word_timing is True


def test_preflight_rejects_cuda_runtime_failure(tmp_path: Path) -> None:
    expected = TranscriptionExecutionError(
        "cuda_runtime_unavailable",
        retryable=False,
        diagnostic_summary="configured CUDA runtime is unavailable",
    )
    execution = FailingProbeExecution(expected)

    with pytest.raises(TranscriptionExecutionError) as captured:
        verify_transcription_inference(
            cast(FasterWhisperExecutionAdapter, execution),
            _configuration(tmp_path),
            "demo-deployment",
        )

    assert captured.value is expected


@pytest.mark.parametrize("item_count", [None, 0, 3])
def test_preflight_program_source_output_and_errors(
    item_count: int | None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    probe_calls: list[bool] = []

    def probe() -> int:
        probe_calls.append(True)
        assert item_count is not None
        return item_count

    components = SimpleNamespace(
        configuration=SimpleNamespace(
            deployment=SimpleNamespace(
                deployment_id="example-deployment",
                runtime_profile=RuntimeProfile.DEMO_SINGLE_STAGE,
                event=SimpleNamespace(stages=[
                    SimpleNamespace(sources=[SimpleNamespace(path=str(tmp_path))])
                ]),
                local_transcription=_configuration(tmp_path),
            )
        ),
        program_source=None if item_count is None else SimpleNamespace(probe=probe),
    )
    execution = FailingProbeExecution(
        TranscriptionExecutionError(
            "provider_no_speech_segments",
            retryable=False,
            diagnostic_summary="synthetic silent probe",
        )
    )

    def gpu_probe(*args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=0, stdout="synthetic GPU")

    def create_execution(*args: object, **kwargs: object) -> FailingProbeExecution:
        return execution

    monkeypatch.setattr(cli, "_components", lambda: components)
    monkeypatch.setattr(cli.subprocess, "run", gpu_probe)
    monkeypatch.setattr(cli, "FasterWhisperExecutionAdapter", create_execution)
    monkeypatch.setattr(execution, "provider_id", "test-provider", raising=False)
    monkeypatch.setattr(execution, "provider_version", "test-version", raising=False)

    result = cli.main(["preflight"])
    captured = capsys.readouterr()

    assert probe_calls == ([] if item_count is None else [True])
    if item_count is None or item_count == 0:
        expected = (
            "program_source_not_configured" if item_count is None
            else "configured_program_source_empty"
        )
        assert result == 1
        assert captured.out == ""
        assert captured.err == f"stageflow_demo_error={expected}\n"
        assert execution.requests == []
    else:
        assert result == 0
        assert captured.err == ""
        payload = json.loads(captured.out)
        assert payload["program_source_available"] is True
        assert payload["devcon_read_available"] is payload["program_source_available"]
        assert payload["program_source_items"] == item_count
        assert payload["devcon_program_items"] == payload["program_source_items"]
        assert len(execution.requests) == 1
