from __future__ import annotations

import wave
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from app.contexts.transcription_evidence import (
    NormalizedTranscriptResult,
    TranscriptionExecutionError,
    TranscriptionExecutionRequest,
)
from app.core.config.deployment import LocalTranscriptionConfiguration
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