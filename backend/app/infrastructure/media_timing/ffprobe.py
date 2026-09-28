"""No shell, no PATH search, bounded output, and no retained diagnostics."""
import hashlib
import json
import re
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Thread
from typing import Any, cast

from app.contexts.production.media_timing_evidence import MediaTimingInspectionResult
from app.contexts.production.media_timing_evidence.inspection import (
    InspectionFields,
    MediaTimingError,
    inspection_result,
)
from app.shared.time import Clock


@dataclass(frozen=True, slots=True)
class FFprobeIdentity:
    version: str
    sha256: str


RENDER_INPUT_FORMATS = "mov,mp4,m4a,3gp,3g2,mj2,matroska,webm,mxf"


@dataclass(frozen=True, slots=True)
class RenderStreamFacts:
    """Only bounded stream facts; no tags, paths, or media payloads escape the probe."""

    video_codecs: tuple[str, ...]
    audio_codecs: tuple[str, ...]

    @property
    def has_audio(self) -> bool:
        return bool(self.audio_codecs)


class FFprobeAdapter:
    def __init__(self, path: Path, clock: Clock, *, timeout: float = 30,
                 output_limit: int = 1_048_576) -> None:
        if not 0 < timeout <= 60 or not 1 <= output_limit <= 1_048_576:
            raise ValueError("media_timing_bounds_invalid")
        self.binary, self.clock = path, clock
        self.timeout, self.output_limit = timeout, output_limit
        self.identity = self._identify()

    def _run(self, arguments: list[str], heartbeat: Callable[[], None] | None = None) -> bytes:
        output = bytearray()
        oversized = False
        try:
            with subprocess.Popen([str(self.binary), *arguments], shell=False,
                                  stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL) as process:
                assert process.stdout is not None
                stream = process.stdout

                def read() -> None:
                    nonlocal oversized
                    while chunk := stream.read(8192):
                        if len(output) + len(chunk) > self.output_limit:
                            oversized = True
                            process.kill()
                            return
                        output.extend(chunk)

                reader = Thread(target=read, daemon=True)
                reader.start()
                try:
                    deadline = time.monotonic() + self.timeout
                    while True:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise MediaTimingError("media_timing_timeout", retryable=True)
                        try:
                            process.wait(timeout=min(5, remaining))
                            break
                        except subprocess.TimeoutExpired:
                            if heartbeat is not None:
                                heartbeat()
                except BaseException:
                    process.kill()
                    process.wait()
                    raise
                finally:
                    reader.join()
                if oversized or process.returncode:
                    raise MediaTimingError("media_timing_output_invalid")
        except OSError:
            raise MediaTimingError("media_timing_tool_unavailable", retryable=True) from None
        return bytes(output)

    def _identify(self, heartbeat: Callable[[], None] | None = None) -> FFprobeIdentity:
        path = self.binary
        if (not path.is_absolute() or ".." in path.parts
                or path.suffix.casefold() in {".cmd", ".bat"}
                or str(path).startswith(("\\\\", "//"))):
            raise MediaTimingError("media_timing_tool_refused")
        try:
            for part in (path, *path.parents):
                if part.is_symlink() or part.is_junction():
                    raise MediaTimingError("media_timing_tool_refused")
            if not path.is_file():
                raise MediaTimingError("media_timing_tool_unavailable", retryable=True)
            with path.open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
        except OSError:
            raise MediaTimingError("media_timing_tool_unavailable", retryable=True) from None
        text = self._run(["-version"], heartbeat).decode("utf-8", errors="replace")
        lines = text.splitlines()
        match = re.fullmatch(r"ffprobe version ([A-Za-z0-9][A-Za-z0-9._-]{0,100})(?: .*?)?",
                             lines[0] if lines else "")
        configs = [line for line in lines if line.startswith("configuration:")]
        if (match is None or len(configs) != 1 or any(
                flag in configs[0].casefold() for flag in ("--enable-gpl", "--enable-nonfree"))):
            raise MediaTimingError("media_timing_tool_refused")
        return FFprobeIdentity(match.group(1), digest)

    def inspect(self, path: Path) -> MediaTimingInspectionResult:
        if self._identify() != self.identity:
            raise MediaTimingError("media_timing_tool_refused")
        if not path.is_absolute() or not path.is_file():
            raise MediaTimingError("input_missing", retryable=True)
        raw = self._run(["-protocol_whitelist", "file", "-v", "error", "-print_format", "json",
                         "-format_whitelist", "mov,mp4,m4a,3gp,3g2,mj2,matroska,webm,mxf,wav",
                         "-show_format", "-show_streams", str(path)])
        try:
            document: object = json.loads(raw)
            if not isinstance(document, dict):
                raise ValueError
            document = cast(dict[str, Any], document)
            container, streams = document.get("format", {}), document.get("streams", [])
            if not isinstance(container, dict) or not isinstance(streams, list):
                raise ValueError
            container = cast(dict[str, Any], container)
            streams = cast(list[Any], streams)
            tags = container.get("tags", {})
            if not isinstance(tags, dict) or any(not isinstance(s, dict) for s in streams):
                raise ValueError
            tags = cast(dict[str, Any], tags)
            video = next((s for s in streams if s.get("codec_type") == "video"), dict[str, Any]())

            def field(value: object) -> str | None:
                if value is None:
                    return None
                if not isinstance(value, str):
                    raise ValueError
                return value

            fields = InspectionFields(field(tags.get("creation_time")),
                field(container.get("duration")), field(video.get("start_time")),
                field(video.get("duration")))
        except (ValueError, UnicodeError, RecursionError):
            raise MediaTimingError("media_timing_output_invalid") from None
        return inspection_result(fields, version=self.identity.version,
                                 digest=self.identity.sha256, inspected_at=self.clock.now())

    def render_streams(self, path: Path, heartbeat: Callable[[], None]) -> RenderStreamFacts:
        """Apply the render demuxer allowlist without changing timing inspection."""
        heartbeat()
        if self._identify(heartbeat) != self.identity:
            raise MediaTimingError("media_timing_tool_refused")
        if not path.is_absolute() or not path.is_file():
            raise MediaTimingError("input_missing", retryable=True)
        raw = self._run(["-protocol_whitelist", "file", "-v", "error", "-print_format", "json",
                         "-format_whitelist", RENDER_INPUT_FORMATS,
                         "-show_streams", str(path)], heartbeat)
        try:
            document = json.loads(raw)
            if not isinstance(document, dict):
                raise ValueError
            document = cast(dict[str, Any], document)
            streams: object = document.get("streams")
            if not isinstance(streams, list) or not streams:
                raise ValueError
            streams = cast(list[object], streams)
            video: list[str] = []
            audio: list[str] = []
            for stream in streams:
                if not isinstance(stream, dict):
                    raise ValueError
                stream = cast(dict[str, Any], stream)
                kind, codec = stream.get("codec_type"), stream.get("codec_name")
                if not isinstance(kind, str) or kind not in {
                    "video", "audio", "subtitle", "data", "attachment", "unknown",
                }:
                    raise ValueError
                if kind in {"video", "audio"}:
                    if (not isinstance(codec, str)
                            or re.fullmatch(r"[a-z0-9_]{1,80}", codec) is None):
                        raise ValueError
                    (video if kind == "video" else audio).append(codec)
            return RenderStreamFacts(tuple(video), tuple(audio))
        except (ValueError, UnicodeError, RecursionError):
            raise MediaTimingError("media_timing_output_invalid") from None
