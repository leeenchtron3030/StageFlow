"""Port of the qualified native command/identity/fallback boundary, without test imports."""
import hashlib
import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from app.contexts.rendering.contracts import (
    FFmpegIdentity,
    RenderError,
    RenderProfile,
    RenderReason,
    require_profile,
)

from .storage import OutputStore, safe_path


def concat_list_content(inputs: Sequence[Path]) -> str:
    lines = ["ffconcat version 1.0"]
    for path in inputs:
        if not path.is_absolute() or any(char in str(path) for char in "\r\n\0"):
            raise RenderError(RenderReason.INPUT_MISSING)
        quoted = path.as_posix().replace("'", "'\\''")
        lines.append(f"file '{quoted}'")
    return "\n".join(lines) + "\n"


def cuda_decode_fallback(stderr: str) -> bool:
    return any(
        "cuda" in line.casefold() and re.search(
            r"\bfailed setup for format cuda\b|"
            r"\bhwaccel (?:setup|initiali[sz]ation) (?:failed|returned error)\b",
            line, re.IGNORECASE,
        ) is not None for line in stderr.splitlines()
    )


@dataclass(frozen=True, slots=True)
class EncodingResult:
    frame_count: int
    duration_microseconds: int


class FFmpegAdapter:
    def __init__(self, ffmpeg_path: Path) -> None:
        try:
            self.binary = safe_path(ffmpeg_path)
            # A batch wrapper would invoke a shell on Windows even with shell=False.
            if self.binary.suffix.casefold() in {".cmd", ".bat"}:
                raise RenderError(RenderReason.IDENTITY_REFUSED)
            self.identity = self._identify()
        except (OSError, RenderError):
            raise RenderError(RenderReason.IDENTITY_REFUSED) from None

    def _identify(self) -> FFmpegIdentity:
        try:
            with safe_path(self.binary).open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
            result = subprocess.run([str(self.binary), "-nostdin", "-version"],
                                    capture_output=True, check=False, timeout=10,
                                    encoding="utf-8", errors="replace", shell=False)
            lines = result.stdout.splitlines()
            match = re.match(r"^ffmpeg version ([A-Za-z0-9][A-Za-z0-9._+~-]*)(?:\s|$)",
                             lines[0] if lines else "")
            configurations = [line for line in lines if line.startswith("configuration:")]
            if (result.returncode or match is None or len(configurations) != 1
                    or any(flag in configurations[0]
                           for flag in ("--enable-gpl", "--enable-nonfree"))):
                raise RenderError(RenderReason.IDENTITY_REFUSED)
            return FFmpegIdentity(match.group(1), digest)
        except (OSError, subprocess.SubprocessError):
            raise RenderError(RenderReason.IDENTITY_REFUSED) from None

    def nvenc_available(self) -> bool:
        try:
            result = subprocess.run(
                [str(self.binary), "-nostdin", "-hide_banner", "-f", "lavfi", "-i",
                 "color=size=1920x1080:rate=30", "-frames:v", "1", "-an", "-c:v", "h264_nvenc",
                 "-f", "null", "-"], capture_output=True, check=False, timeout=15, shell=False,
            )
            return result.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def render(
        self, inputs: Sequence[Path], output: Path, store: OutputStore,
        profile: RenderProfile, heartbeat: Callable[[], None],
    ) -> EncodingResult:
        require_profile(profile)
        store.validate()
        if safe_path(output).parent != store.temp:
            raise RenderError(RenderReason.STORE_UNAVAILABLE)
        if self._identify() != self.identity:
            raise RenderError(RenderReason.IDENTITY_REFUSED)
        for item in inputs:
            safe_path(item)
        with store.temporary(".ffconcat") as concat:
            concat.write_text(concat_list_content(inputs), encoding="utf-8", newline="\n")
            command = [str(self.binary), "-nostdin", "-hide_banner", "-y",
                       "-hwaccel", "cuda", "-hwaccel_output_format", "cuda",
                       "-f", "concat", "-safe", "0", "-protocol_whitelist", "file,pipe",
                       "-i", str(concat), "-map", "0:v:0", "-map_metadata", "-1",
                       "-map_chapters", "-1",
                       "-vf", "scale_cuda=1920:1080:format=nv12", "-fps_mode", "passthrough",
                       "-c:v", profile.encoder, "-preset", profile.preset,
                       "-rc", profile.rate_control, "-b:v", str(profile.bit_rate),
                       "-g", str(profile.gop), "-an", "-f", profile.container,
                       "-progress", "pipe:1", "-nostats", str(output)]
            try:
                with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      encoding="utf-8", errors="replace", shell=False) as process:
                    try:
                        while True:
                            try:
                                stdout, stderr = process.communicate(timeout=5)
                                break
                            except subprocess.TimeoutExpired:
                                heartbeat()
                    except BaseException:
                        process.kill()
                        process.communicate()
                        raise
                    if cuda_decode_fallback(stderr):
                        raise RenderError(RenderReason.CUDA_FALLBACK)
                    if process.returncode:
                        if any(marker in stderr.casefold() for marker in (
                            "openencodesessionex failed", "no capable devices found",
                            "cannot load nvcuda", "cannot load nvencode", "unknown encoder",
                        )):
                            raise RenderError(RenderReason.NVENC_UNAVAILABLE)
                        raise RenderError(RenderReason.EXIT_NONZERO, retryable=True)
                    frames = re.findall(r"(?:^|[\r\n])frame\s*=\s*(\d+)\s*(?:[\r\n]|$)", stdout)
                    durations = re.findall(r"(?:^|[\r\n])out_time_us=(\d+)", stdout)
                    if (not frames or not durations
                            or int(frames[-1]) <= 0 or int(durations[-1]) <= 0):
                        raise RenderError(RenderReason.OUTPUT_INVALID)
                    return EncodingResult(int(frames[-1]), int(durations[-1]))
            except OSError:
                raise RenderError(RenderReason.EXIT_NONZERO, retryable=True) from None
