"""Opt-in host checks on generated audio only; paths are operator-provisioned."""
import importlib
import os
import wave
from pathlib import Path
from typing import Any

import pytest

np = pytest.importorskip("numpy")

from app.contexts.transcription_evidence import (  # noqa: E402
    TranscriptEvidenceStatus,
    TranscriptionExecutionError,
)
from app.infrastructure.transcription import CTranslate2WhisperExecutionAdapter  # noqa: E402
from app.infrastructure.transcription.ctranslate2_whisper.decode import FFmpegDecoder  # noqa: E402
from app.shared.time import FixedClock  # noqa: E402
from tests.test_ctranslate2_whisper_adapter import configuration, request  # noqa: E402
from tests.test_faster_whisper_execution_adapter import NOW, StaticResolver  # noqa: E402

pytestmark = pytest.mark.skipif(not os.environ.get("STAGEFLOW_TEST_FFMPEG_PATH"),
                                reason="operator FFmpeg path not supplied")


def operator_ffmpeg() -> Path:
    raw = os.environ.get("STAGEFLOW_TEST_FFMPEG_PATH")
    if not raw:
        pytest.skip("operator FFmpeg path not supplied")
    return Path(raw)


def synthetic_stereo(path: Path, sample_rate: int = 16000) -> None:
    t = np.arange(sample_rate) / sample_rate
    channels = np.column_stack((.4 * np.sin(2 * np.pi * 440 * t),
                                .1 * np.sin(2 * np.pi * 660 * t)))
    with wave.open(str(path), "wb") as audio:
        audio.setparams((2, 2, sample_rate, sample_rate, "NONE", "not compressed"))
        audio.writeframes(np.round(channels * 32767).astype("<i2").tobytes())


@pytest.mark.parametrize("sample_rate", [16000, 48000])
def test_host_pcm_matches_reference_within_one_s16_step(tmp_path: Path, sample_rate: int) -> None:
    ffmpeg = operator_ffmpeg()
    pytest.importorskip("av")
    pytest.importorskip("faster_whisper")
    reference: Any = importlib.import_module("faster_whisper.audio")
    media = tmp_path / "unequal-stereo.wav"
    synthetic_stereo(media, sample_rate)
    actual = FFmpegDecoder(ffmpeg).decode(media, lambda: None)
    expected = reference.decode_audio(str(media), sampling_rate=16000)
    np.testing.assert_allclose(actual, expected, rtol=0, atol=1 / 32768)


def test_host_cpu_int8_synthetic_end_to_end(tmp_path: Path) -> None:
    ffmpeg = operator_ffmpeg()
    model = os.environ.get("STAGEFLOW_TEST_WHISPER_MODEL_PATH")
    if not model:
        pytest.skip("offline model path not supplied")
    pytest.importorskip("tokenizers")
    # Inspect distribution without executing CTranslate2's converter initializer.
    import importlib.metadata
    try:
        importlib.metadata.distribution("ctranslate2")
    except importlib.metadata.PackageNotFoundError:
        pytest.skip("CTranslate2 runtime not installed")
    media = tmp_path / "synthetic.wav"
    synthetic_stereo(media)
    adapter = CTranslate2WhisperExecutionAdapter(
        configuration(Path(model), ffmpeg_path=str(ffmpeg)), resolver=StaticResolver(media),
        clock=FixedClock(NOW))
    try:
        result = adapter.execute(request(), lambda: None)
    except TranscriptionExecutionError as exc:
        # A tone need not produce speech; this outcome still requires full inference.
        assert exc.reason_code == "provider_no_speech_segments"
    else:
        assert result.status is TranscriptEvidenceStatus.COMPLETE
