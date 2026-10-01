"""Explicit-path LGPL FFmpeg decode with bounded reads and lease heartbeats."""
import hashlib
import json
import math
import re
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from threading import Thread
from typing import Any

from app.contexts.transcription_evidence.application import TranscriptionExecutionError

from .features import FloatArray, np


def failure(code: str = "media_decode_failed") -> TranscriptionExecutionError:
    return TranscriptionExecutionError(code, retryable=code == "media_decode_failed",
                                       diagnostic_summary="local audio decode unavailable")


def channel_average(channels: int) -> str:
    if not 1 <= channels <= 8:
        raise ValueError("audio channel count out of bounds")
    weight = format(1 / channels, ".17g")
    return "pan=mono|c0=" + "+".join(f"{weight}*c{i}" for i in range(channels))


def run_bounded(command: list[str], *, limit: int, timeout: float,
                heartbeat: Callable[[], None]) -> bytes:
    output = bytearray()
    errors: list[Exception] = []
    oversized = False
    try:
        with subprocess.Popen(command, shell=False, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
            assert process.stdout is not None
            stream = process.stdout

            def read() -> None:
                nonlocal oversized
                try:
                    while chunk := stream.read(min(8192, limit + 1)):
                        if len(output) + len(chunk) > limit:
                            oversized = True
                            process.kill()
                            return
                        output.extend(chunk)
                except OSError as exc:
                    errors.append(exc)
                    process.kill()

            reader = Thread(target=read, daemon=True)
            reader.start()
            try:
                deadline = time.monotonic() + timeout
                while True:
                    heartbeat()
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise failure()
                    try:
                        process.wait(timeout=min(5, remaining))
                        break
                    except subprocess.TimeoutExpired:
                        continue
            except BaseException:
                process.kill()
                process.wait()
                raise
            finally:
                reader.join()
            if oversized or errors or process.returncode:
                raise failure()
    except OSError:
        raise failure() from None
    return bytes(output)


class FFmpegDecoder:
    def __init__(self, path: Path, *, runner: Callable[..., bytes] = run_bounded) -> None:
        self.ffmpeg = path
        self.ffprobe = path.with_name("ffprobe.exe" if path.suffix.lower() == ".exe" else "ffprobe")
        self.runner = runner
        self.identity = self.identify(lambda: None)

    def identify(self, heartbeat: Callable[[], None]) -> tuple[str, str, str, str]:
        identities: list[str] = []
        for name, path in (("ffmpeg", self.ffmpeg), ("ffprobe", self.ffprobe)):
            if (not path.is_absolute() or ".." in path.parts
                    or path.suffix.casefold() in {".cmd", ".bat"}
                    or str(path).startswith(("\\\\", "//"))
                    or any(c in str(path) for c in "\0\r\n")):
                raise failure("provider_runtime_unavailable")
            try:
                if any(p.is_symlink() or p.is_junction() for p in (path, *path.parents)):
                    raise failure("provider_runtime_unavailable")
                with path.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                raw = self.runner([str(path), "-version"], limit=65536, timeout=15,
                                  heartbeat=heartbeat).decode("utf-8", errors="replace")
            except (OSError, TranscriptionExecutionError):
                raise failure("provider_runtime_unavailable") from None
            lines = raw.splitlines()
            match = re.fullmatch(name + r" version ([A-Za-z0-9][A-Za-z0-9._-]{0,100})(?: .*?)?",
                                 lines[0] if lines else "")
            configurations = [line for line in lines if line.startswith("configuration:")]
            if (match is None or len(configurations) != 1 or any(
                    flag in configurations[0].lower()
                    for flag in ("--enable-gpl", "--enable-nonfree"))):
                raise failure("provider_runtime_unavailable")
            identities.extend((match[1], digest))
        return (identities[0], identities[1], identities[2], identities[3])

    def decode(self, path: Path, heartbeat: Callable[[], None]) -> FloatArray:
        heartbeat()
        if self.identify(heartbeat) != self.identity:
            raise failure("provider_runtime_unavailable")
        if not path.is_absolute() or not path.is_file():
            raise failure()
        try:
            raw = self.runner([str(self.ffprobe), "-v", "error", "-protocol_whitelist", "file",
                               "-select_streams", "a:0", "-show_entries",
                               "stream=channels,duration:format=duration", "-of", "json",
                               str(path)], limit=65536, timeout=30, heartbeat=heartbeat)
            info: Any = json.loads(raw)
            channels = info["streams"][0]["channels"]
            if type(channels) is not int:
                raise ValueError
            pan = channel_average(channels)
            # Prefer container duration, as reference decode includes stream offsets.
            duration = float(info.get("format", {}).get("duration")
                             or info["streams"][0]["duration"])
            if not math.isfinite(duration) or not 0 < duration <= 14400:
                raise ValueError
            limit = math.ceil((duration + 1) * 16000) * 2
            pcm = self.runner(
                [str(self.ffmpeg), "-nostdin", "-hide_banner", "-loglevel", "error",
                 "-protocol_whitelist", "file,pipe", "-i", str(path), "-map", "0:a:0",
                 "-vn", "-af", pan, "-ar", "16000", "-f", "s16le", "pipe:1"],
                limit=limit, timeout=min(600, max(30, duration * 2)), heartbeat=heartbeat)
            if not pcm or len(pcm) % 2 or len(pcm) > limit:
                raise ValueError
            return np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
        except (ValueError, KeyError, IndexError, TypeError, AttributeError, RecursionError,
                OSError, subprocess.TimeoutExpired):
            raise failure() from None
