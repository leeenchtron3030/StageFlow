"""Port of the qualified native command/identity/fallback boundary, without test imports."""
import hashlib
import re
import subprocess
from collections.abc import Callable, Sequence
from contextlib import ExitStack
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from app.contexts.production.media_timing_evidence.inspection import MediaTimingError
from app.contexts.rendering.contracts import (
    FFmpegIdentity,
    RenderError,
    RenderProfile,
    RenderReason,
    require_requestable,
)
from app.infrastructure.media_timing.ffprobe import (
    RENDER_INPUT_FORMATS,
    FFprobeAdapter,
    RenderStreamFacts,
)

from .storage import OutputStore, safe_path


def concat_list_content(inputs: Sequence[Path]) -> str:
    lines = ["ffconcat version 1.0"]
    for path in inputs:
        if not path.is_absolute() or any(char in str(path) for char in "\r\n\0"):
            raise RenderError(RenderReason.INPUT_MISSING)
        quoted = path.as_posix().replace("'", "'\\''")
        lines.append(f"file '{quoted}'")
        # Concat inherits the outer whitelist. Per-file open options replace it so
        # referenced media cannot itself be a concat/playlist, regardless of suffix.
        lines.append(f"option format_whitelist {RENDER_INPUT_FORMATS}")
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


def identify_ffmpeg(binary: Path) -> FFmpegIdentity:
    try:
        with safe_path(binary).open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        result = subprocess.run([str(binary), "-nostdin", "-version"],
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


class FFmpegAdapter:
    def __init__(self, ffmpeg_path: Path, ffprobe: FFprobeAdapter) -> None:
        self.ffprobe = ffprobe
        try:
            self.binary = safe_path(ffmpeg_path)
            # A batch wrapper would invoke a shell on Windows even with shell=False.
            if self.binary.suffix.casefold() in {".cmd", ".bat"}:
                raise RenderError(RenderReason.IDENTITY_REFUSED)
            self.identity = self._identify()
        except (OSError, RenderError):
            raise RenderError(RenderReason.IDENTITY_REFUSED) from None

    def _identify(self) -> FFmpegIdentity:
        return identify_ffmpeg(self.binary)

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
        require_requestable(profile)
        assert profile.output_frame_rate is not None and profile.audio_sample_rate is not None
        store.validate()
        if safe_path(output).parent != store.temp:
            raise RenderError(RenderReason.STORE_UNAVAILABLE)
        if self._identify() != self.identity:
            raise RenderError(RenderReason.IDENTITY_REFUSED)
        if not inputs:
            raise RenderError(RenderReason.INPUT_MISSING)
        facts = [self._probe(safe_path(item), heartbeat) for item in inputs]
        if any(not fact.video_codecs for fact in facts):
            raise RenderError(RenderReason.INPUT_MISSING)
        # ExitStack owns every intermediate, including on cancellation/BaseException.
        with ExitStack() as temporary:
            intermediates: list[Path] = []
            for item, fact in zip(inputs, facts, strict=True):
                # Stage 1a encodes the video exactly once; its frame count fixes the length.
                # The video-only file lives only until its audio-fitted copy exists.
                with store.temporary(".mov") as video:
                    command = [str(self.binary), "-nostdin", "-hide_banner", "-y",
                               "-hwaccel", "cuda", "-hwaccel_output_format", "cuda",
                               "-protocol_whitelist", "file,pipe",
                               "-format_whitelist", RENDER_INPUT_FORMATS,
                               "-i", str(safe_path(item)), "-map", "0:v:0", "-an",
                               "-map_metadata", "-1", "-map_chapters", "-1",
                               "-vf", f"scale_cuda={profile.width}:{profile.height}:format=nv12",
                               "-fps_mode", "cfr",
                               "-r", str(profile.output_frame_rate),
                               "-c:v", profile.encoder, "-preset", profile.preset,
                               "-rc", profile.rate_control, "-b:v", str(profile.bit_rate),
                               "-g", str(profile.gop),
                               "-f", "mov", "-progress", "pipe:1", "-nostats", str(video)]
                    frames = self._encode(command, heartbeat).frame_count
                    # Stage 1b fits audio to exactly that video length. `apad` with `-shortest`
                    # overran by minutes on FFmpeg 8 (Run 003), so the length is explicit samples.
                    samples = round(Fraction(frames) / profile.output_frame_rate
                                    * profile.audio_sample_rate)
                    if samples <= 0:
                        raise RenderError(RenderReason.OUTPUT_INVALID)
                    intermediate = temporary.enter_context(store.temporary(".mov"))
                    intermediates.append(intermediate)
                    command = [str(self.binary), "-nostdin", "-hide_banner", "-y",
                               "-protocol_whitelist", "file,pipe", "-format_whitelist", "mov",
                               "-i", str(video)]
                    command += (["-protocol_whitelist", "file,pipe",
                                 "-format_whitelist", RENDER_INPUT_FORMATS,
                                 "-i", str(safe_path(item))] if fact.has_audio else
                                ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"])
                    command += ["-map", "0:v:0", "-map", "1:a:0",
                                "-map_metadata", "-1", "-map_chapters", "-1", "-c:v", "copy",
                                "-af", "aresample=48000:async=1:first_pts=0,"
                                f"aformat=channel_layouts=stereo,apad=whole_len={samples},"
                                f"atrim=end_sample={samples}",
                                "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2",
                                "-f", "mov", "-progress", "pipe:1", "-nostats", str(intermediate)]
                    self._encode(command, heartbeat)
            concat = temporary.enter_context(store.temporary(".ffconcat"))
            concat.write_text(concat_list_content(intermediates), encoding="utf-8", newline="\n")
            command = [str(self.binary), "-nostdin", "-hide_banner", "-y",
                       "-f", "concat", "-safe", "0", "-protocol_whitelist", "file,pipe",
                       "-format_whitelist", "concat", "-i", str(concat),
                       "-map", "0:v:0", "-map", "0:a:0", "-map_metadata", "-1",
                       "-map_chapters", "-1", "-c:v", "copy", "-c:a", "aac",
                       "-b:a", str(profile.audio_bit_rate), "-ar", "48000", "-ac", "2", "-f", "mp4",
                       "-progress", "pipe:1", "-nostats", str(output)]
            encoded = self._encode(command, heartbeat)
            output_facts = self._probe(safe_path(output), heartbeat, output=True)
            if output_facts.video_codecs != ("h264",) or output_facts.audio_codecs != ("aac",):
                raise RenderError(RenderReason.OUTPUT_INVALID)
            return encoded

    def _probe(
        self, path: Path, heartbeat: Callable[[], None], *, output: bool = False,
    ) -> RenderStreamFacts:
        try:
            return self.ffprobe.render_streams(path, heartbeat)
        except MediaTimingError as exc:
            code = (RenderReason.OUTPUT_INVALID if output else
                    RenderReason.INPUT_MISSING if exc.code == "input_missing" else
                    RenderReason.INTERNAL)
            raise RenderError(code, retryable=exc.retryable) from None

    def _encode(self, command: list[str], heartbeat: Callable[[], None]) -> EncodingResult:
        heartbeat()
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
                heartbeat()
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
