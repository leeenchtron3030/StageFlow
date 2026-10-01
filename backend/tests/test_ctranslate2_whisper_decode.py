import io
import json
import math
import struct
import subprocess
from pathlib import Path
from typing import Any

import pytest

np = pytest.importorskip("numpy")

from app.contexts.transcription_evidence import TranscriptionExecutionError  # noqa: E402
from app.infrastructure.transcription.ctranslate2_whisper import decode  # noqa: E402


@pytest.mark.parametrize("channels", range(1, 9))
def test_downmix_is_explicit_equal_weight_average(channels: int) -> None:
    expression = decode.channel_average(channels)
    terms = expression.removeprefix("pan=mono|c0=").split("+")
    assert len(terms) == channels
    assert [t.split("*")[1] for t in terms] == [f"c{i}" for i in range(channels)]
    assert all(math.isclose(float(t.split("*")[0]), 1 / channels) for t in terms)
    if channels == 2:
        assert expression == "pan=mono|c0=0.5*c0+0.5*c1"


@pytest.mark.parametrize("channels", [0, 9, -1])
def test_unsupported_channel_count_refused(channels: int) -> None:
    with pytest.raises(ValueError):
        decode.channel_average(channels)


def decoder(tmp_path: Path, *, channels: Any = 2, duration: Any = "1.0",
            pcm: bytes = struct.pack("<hhh", -32768, 0, 32767),
            error: Exception | None = None, flags: str = "--enable-shared"
            ) -> tuple[decode.FFmpegDecoder, list[Any]]:
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffmpeg.write_bytes(b"fake executable")
    ffmpeg.with_name("ffprobe.exe").write_bytes(b"fake executable")
    calls: list[Any] = []

    def runner(command: list[str], **bounds: Any) -> bytes:
        calls.append((command, bounds))
        if command[-1] == "-version":
            return f"{Path(command[0]).stem} version 8.1\nconfiguration: {flags}\n".encode()
        if "-show_entries" in command:
            return json.dumps(dict(streams=[dict(channels=channels)],
                                   format=dict(duration=duration))).encode()
        if error is not None:
            raise error
        return pcm

    return decode.FFmpegDecoder(ffmpeg, runner=runner), calls


def test_s16_conversion_command_and_duration_bounds(tmp_path: Path) -> None:
    port, calls = decoder(tmp_path)
    media = tmp_path / "synthetic.wav"
    media.touch()
    actual = port.decode(media, lambda: None)
    np.testing.assert_array_equal(actual, [-1, 0, 32767 / 32768])
    assert actual.dtype == np.float32
    command, bounds = calls[-1]
    assert command[command.index("-map") + 1] == "0:a:0"
    assert command[command.index("-af") + 1] == "pan=mono|c0=0.5*c0+0.5*c1"
    assert "-ac" not in command and command[-5:] == ["-ar", "16000", "-f", "s16le", "pipe:1"]
    assert bounds["limit"] == 64000 and bounds["timeout"] == 30


@pytest.mark.parametrize("kwargs", [dict(channels=9), dict(channels="2"), dict(duration="nan"),
    dict(duration=0), dict(duration=14401), dict(pcm=b"a"), dict(pcm=b""),
    dict(pcm=bytes(64002)), dict(error=subprocess.TimeoutExpired("private", 30))])
def test_decode_failures_are_bounded_retryable_and_sanitized(tmp_path: Path,
                                                          kwargs: dict[str, Any]) -> None:
    port, _ = decoder(tmp_path, **kwargs)
    media = tmp_path / "synthetic.wav"
    media.touch()
    with pytest.raises(TranscriptionExecutionError) as caught:
        port.decode(media, lambda: None)
    assert caught.value.reason_code == "media_decode_failed" and caught.value.retryable
    assert "private" not in caught.value.diagnostic_summary


@pytest.mark.parametrize("flags", ["--enable-gpl", "--enable-nonfree"])
def test_unapproved_ffmpeg_build_is_refused(tmp_path: Path, flags: str) -> None:
    with pytest.raises(TranscriptionExecutionError) as caught:
        decoder(tmp_path, flags=flags)
    assert caught.value.reason_code == "provider_runtime_unavailable"
    assert not caught.value.retryable


def test_replaced_binary_is_refused(tmp_path: Path) -> None:
    port, _ = decoder(tmp_path)
    port.ffmpeg.write_bytes(b"changed binary")
    with pytest.raises(TranscriptionExecutionError) as caught:
        port.decode(tmp_path / "synthetic.wav", lambda: None)
    assert caught.value.reason_code == "provider_runtime_unavailable"


def test_malformed_probe_structure_is_retryable(tmp_path: Path) -> None:
    port, _ = decoder(tmp_path)
    original = port.runner

    def runner(command: list[str], **bounds: Any) -> bytes:
        if "-show_entries" in command:
            return b'{"streams":[{"channels":2}],"format":[]}'
        return original(command, **bounds)

    port.runner = runner
    media = tmp_path / "synthetic.wav"
    media.touch()
    with pytest.raises(TranscriptionExecutionError) as caught:
        port.decode(media, lambda: None)
    assert caught.value.reason_code == "media_decode_failed" and caught.value.retryable


class Process:
    def __init__(self, data: bytes, *, waits: int = 0) -> None:
        self.stdout = io.BytesIO(data)
        self.returncode = 0
        self.killed = False
        self.waits = waits
        self.reaped = False

    def __enter__(self) -> "Process":
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout: float | None = None) -> None:
        if self.waits and not self.killed:
            self.waits -= 1
            raise subprocess.TimeoutExpired("private", timeout or 0)
        self.reaped = True


def install_process(monkeypatch: pytest.MonkeyPatch, process: Process) -> None:
    def popen(command: list[str], **kwargs: Any) -> Process:
        assert kwargs["shell"] is False and kwargs["stderr"] == subprocess.DEVNULL
        assert kwargs["stdin"] == subprocess.DEVNULL
        return process
    monkeypatch.setattr(decode.subprocess, "Popen", popen)


def test_subprocess_output_is_capped_while_reading(monkeypatch: pytest.MonkeyPatch) -> None:
    process = Process(bytes(100))
    install_process(monkeypatch, process)
    with pytest.raises(TranscriptionExecutionError):
        decode.run_bounded(["explicit"], limit=10, timeout=30, heartbeat=lambda: None)
    assert process.killed and process.reaped


def test_subprocess_timeout_kills_and_reaps(monkeypatch: pytest.MonkeyPatch) -> None:
    process = Process(b"", waits=1)
    install_process(monkeypatch, process)
    ticks = iter([0., 1., 31.])
    monkeypatch.setattr(decode.time, "monotonic", lambda: next(ticks))
    renewals: list[None] = []
    with pytest.raises(TranscriptionExecutionError):
        decode.run_bounded(["explicit"], limit=10, timeout=30,
                           heartbeat=lambda: renewals.append(None))
    assert process.killed and process.reaped and len(renewals) == 2


def test_lease_loss_stops_decode_without_remapping(monkeypatch: pytest.MonkeyPatch) -> None:
    process = Process(b"", waits=1)
    install_process(monkeypatch, process)
    error = RuntimeError("lease lost")

    def heartbeat() -> None:
        raise error

    with pytest.raises(RuntimeError) as caught:
        decode.run_bounded(["explicit"], limit=10, timeout=30, heartbeat=heartbeat)
    assert caught.value is error and process.killed and process.reaped
