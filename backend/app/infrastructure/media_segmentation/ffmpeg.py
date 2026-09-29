"""Fixed one-pass CPU filters; bounded transient output, never persisted diagnostics."""
import re
import subprocess
import time
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from pathlib import Path
from threading import Thread

from app.contexts.production.media_segmentation_evidence.contracts import (
    CURRENT_SEGMENTATION_PROFILE,
    MAX_INTERVALS,
    MAX_OFFSET_US,
    MediaSegmentationError,
    SegmentationInterval,
    SegmentationResult,
)
from app.contexts.rendering.contracts import RenderError
from app.infrastructure.rendering.ffmpeg import identify_ffmpeg
from app.infrastructure.rendering.storage import safe_path
from app.shared.time import Clock

END_TOLERANCE_US = 1_000_000


def parse_intervals(stderr: str, duration_microseconds: int) -> tuple[SegmentationInterval, ...]:
    """Ignore unrelated diagnostics; reject malformed/contradictory detector events."""
    opened: dict[str, int] = {}
    ended: dict[str, int] = {}
    intervals: list[SegmentationInterval] = []

    def append(kind: str, start: int, end: int) -> None:
        if end <= start or end > duration_microseconds or start < ended.get(kind, 0):
            raise MediaSegmentationError("render_output_invalid")
        if len(intervals) >= MAX_INTERVALS:
            raise MediaSegmentationError("media_segmentation_interval_limit")
        intervals.append(SegmentationInterval(
            "freeze" if kind == "freeze" else "silence", start, end))
        ended[kind] = end

    if not 0 < duration_microseconds <= MAX_OFFSET_US:
        raise MediaSegmentationError("render_output_invalid")
    for line in stderr.splitlines():
        # Only actual filter log records are observations, never filenames in diagnostics.
        if re.match(
                r"\[(?:Parsed_)?(?:freezedetect|silencedetect)(?:_\d+)? @ [^]]+\]", line) is None:
            continue
        for match in re.finditer(r"(freeze|silence)_(start|end):[ \t]*([^\s|]*)", line):
            kind, edge, raw = match.groups()
            try:
                if len(raw) > 64 or re.fullmatch(
                        r"-?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]{1,4})?", raw) is None:
                    raise ValueError
                numeric = Decimal(raw) * 1_000_000
                if not -1_000_000 <= numeric <= MAX_OFFSET_US:
                    raise ValueError
                offset = max(0, int(numeric))
                # silencedetect ends EOF silence at the last audio frame, which can slightly
                # exceed the measured output duration; clamp only such end offsets.
                if edge == "end" and offset <= duration_microseconds + END_TOLERANCE_US:
                    offset = min(offset, duration_microseconds)
                if offset > duration_microseconds:
                    raise ValueError
            except (ValueError, InvalidOperation):
                raise MediaSegmentationError("render_output_invalid") from None
            if edge == "start":
                if kind in opened or offset < ended.get(kind, 0):
                    raise MediaSegmentationError("render_output_invalid")
                opened[kind] = offset
            else:
                if kind not in opened:
                    raise MediaSegmentationError("render_output_invalid")
                append(kind, opened.pop(kind), offset)
    for kind, start in opened.items():
        append(kind, start, duration_microseconds)
    return tuple(sorted(intervals, key=lambda value: (value.start_microseconds, value.kind)))


class FFmpegSegmentationAdapter:
    def __init__(self, path: Path, clock: Clock, *, timeout: float = 3600,
                 output_limit: int = 8_388_608) -> None:
        if not 0 < timeout <= 86_400 or not 1 <= output_limit <= 8_388_608:
            raise ValueError("media_segmentation_bounds_invalid")
        self.clock, self.timeout, self.output_limit = clock, timeout, output_limit
        try:
            self.binary = safe_path(path)
            if self.binary.suffix.casefold() in {".cmd", ".bat"}:
                raise MediaSegmentationError("render_identity_refused")
            self.identity = identify_ffmpeg(self.binary)
        except (OSError, RenderError):
            raise MediaSegmentationError("render_identity_refused") from None

    def inspect(self, path: Path, heartbeat: Callable[[], None]) -> SegmentationResult:
        heartbeat()
        try:
            if identify_ffmpeg(self.binary) != self.identity:
                raise MediaSegmentationError("render_identity_refused")
        except RenderError:
            raise MediaSegmentationError("render_identity_refused") from None
        try:
            path = safe_path(path)
            if not path.is_file():
                raise OSError
        except (OSError, RenderError):
            raise MediaSegmentationError("input_missing", retryable=True) from None
        profile = CURRENT_SEGMENTATION_PROFILE
        command = [str(self.binary), "-nostdin", "-hide_banner", "-nostats",
            "-loglevel", "info", "-progress", "pipe:1", "-protocol_whitelist", "file",
            "-format_whitelist", profile.demuxer_allowlist, "-hwaccel", "none",
            "-i", str(path), "-map", "0:v:0?", "-map", "0:a:0?",
            "-vf", profile.video_filter, "-af", profile.audio_filter, "-f", "null", "-"]
        buffers = [bytearray(), bytearray()]
        oversized = False
        read_failed = False
        try:
            with subprocess.Popen(command, shell=False, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
                assert process.stdout is not None and process.stderr is not None

                def read(stream: object, index: int) -> None:
                    nonlocal oversized, read_failed
                    try:
                        # Both streams are binary pipes; reads are bounded even without newlines.
                        from typing import BinaryIO, cast
                        pipe = cast(BinaryIO, stream)
                        while chunk := pipe.read(8192):
                            if len(buffers[index]) + len(chunk) > self.output_limit:
                                oversized = True
                                process.kill()
                                return
                            buffers[index].extend(chunk)
                    except OSError:
                        read_failed = True
                        process.kill()

                readers = [Thread(target=read, args=(stream, index), daemon=True)
                           for index, stream in enumerate((process.stdout, process.stderr))]
                for reader in readers:
                    reader.start()
                try:
                    deadline = time.monotonic() + self.timeout
                    while True:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise MediaSegmentationError(
                                "media_segmentation_timeout", retryable=True)
                        try:
                            process.wait(timeout=min(5, remaining))
                            break
                        except subprocess.TimeoutExpired:
                            heartbeat()
                except BaseException:
                    process.kill()
                    process.wait()
                    raise
                finally:
                    for reader in readers:
                        reader.join()
                heartbeat()
                if oversized or read_failed:
                    raise MediaSegmentationError("render_output_invalid")
                if process.returncode:
                    raise MediaSegmentationError("render_exit_nonzero", retryable=True)
        except OSError:
            raise MediaSegmentationError("render_exit_nonzero", retryable=True) from None
        progress = buffers[0].decode("utf-8", errors="replace")
        durations = re.findall(r"(?:^|[\r\n])out_time_us=([0-9]{1,15})(?:[\r\n]|$)", progress)
        if not durations or "progress=end" not in progress.splitlines():
            raise MediaSegmentationError("render_output_invalid")
        duration = int(durations[-1])
        intervals = parse_intervals(buffers[1].decode("utf-8", errors="replace"), duration)
        try:
            return SegmentationResult(intervals, duration, self.identity.version,
                                      self.identity.sha256, self.clock.now())
        except ValueError:
            raise MediaSegmentationError("render_output_invalid") from None
