"""Offline measurement only. Public output contains no operator or provider strings."""
from __future__ import annotations

import argparse
import importlib
import json
import math
import multiprocessing
import os
import subprocess
import sys
import tempfile
import time
import tomllib
import wave
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from statistics import median
from threading import Event, Thread
from typing import Any, Literal, NoReturn, Protocol, TextIO, cast

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "backend"))

from app.contexts.editorial.derivation_contracts import word_tokens  # noqa: E402
from app.contexts.production.session_suggestions.cue_catalog import (  # noqa: E402
    BOUNDARY_CUE_CATALOG,
)
from app.contexts.production.session_suggestions.cue_composition import (  # noqa: E402
    CompositionRequest,
    compose,
)

ENGINES = ("baseline", "option_a", "option_b")
EXTENSIONS = {".mov", ".mp4", ".mkv", ".mxf", ".wav"}
PROFILES = tuple(profile.key for profile in BOUNDARY_CUE_CATALOG.profiles)
TIMEOUT = 7200
PREFLIGHT_TIMEOUT = 60
ENGINE_TIMEOUT = 300


class Refusal(ValueError):
    """Invalid local input; never print its diagnostic."""


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise Refusal()


def parser() -> Parser:
    result = Parser(prog="transcription_engine_spike", description=__doc__)
    result.add_argument("--blocks", required=True)
    result.add_argument("--candidate", choices=("option_a", "stageflow"), default="option_a")
    result.add_argument("--whisper-cpp-binary")
    result.add_argument("--whisper-cpp-model")
    result.add_argument("--render-load", action="store_true")
    result.add_argument("--device", choices=("cuda", "cpu"))
    result.add_argument("--language", choices=("en",), default="en")
    result.add_argument("--profile", choices=PROFILES, default="conference")
    result.add_argument("--max-blocks", type=int, default=6)
    result.add_argument("--engine-timeout-seconds", type=int, default=ENGINE_TIMEOUT)
    result.add_argument("--markdown", action="store_true")
    return result


def local_path(raw: str, *, directory: bool = False, external: bool = False) -> Path:
    # Reject UNC/device paths before any filesystem access; no PATH or URL resolution.
    if not raw or raw.startswith(("\\\\", "//")) or any(c in raw for c in "\0\r\n"):
        raise Refusal()
    path = Path(raw)
    if not path.is_absolute():
        raise Refusal()
    path = path.resolve(strict=True)
    if str(path).startswith(("\\\\", "//")) or (external and path.is_relative_to(REPOSITORY)):
        raise Refusal()
    if not (path.is_dir() if directory else path.is_file()):
        raise Refusal()
    return path


@dataclass(frozen=True)
class Settings:
    blocks: tuple[Path, ...]
    model: Path
    device: str
    compute_type: str
    ffmpeg: Path
    ffprobe: Path
    profile: str = "conference"
    language: str = "en"
    cpp_binary: Path | None = None
    cpp_model: Path | None = None
    render_load: bool = False
    engine_timeout_seconds: int = ENGINE_TIMEOUT
    candidate: str = "option_a"

    def __post_init__(self) -> None:
        object.__setattr__(self, "blocks", tuple(self.blocks))
        if not 60 <= self.engine_timeout_seconds <= 14400:
            raise Refusal()
        if self.candidate not in {"option_a", "stageflow"}:
            raise Refusal()


def load_settings(args: argparse.Namespace, environ: Mapping[str, str]) -> Settings:
    if not 1 <= args.max_blocks <= 1000:
        raise Refusal()
    if bool(args.whisper_cpp_binary) != bool(args.whisper_cpp_model):
        raise Refusal()
    if args.candidate == "stageflow" and args.whisper_cpp_binary:
        raise Refusal()
    folder = local_path(args.blocks, directory=True, external=True)
    entries = sorted(folder.iterdir(), key=lambda p: (p.name.casefold(), p.name))
    if not entries or len(entries) > 1000:
        raise Refusal()
    blocks: list[Path] = []
    for entry in entries:
        if (entry.is_symlink() or entry.is_junction() or entry.name.startswith(".")
                or entry.suffix.casefold() not in EXTENSIONS):
            raise Refusal()
        blocks.append(local_path(str(entry), external=True))
    config_path = local_path(environ.get("STAGEFLOW_KERNEL_CONFIG_PATH", ""))
    with config_path.open("rb") as stream:
        config = tomllib.load(stream)
    transcription = config["local_transcription"]
    device = args.device or transcription.get("device", "cuda")
    compute_type = transcription.get("compute_type", "float16")
    if args.candidate == "stageflow":
        compute_type = "int8" if device == "cpu" else "float16"
    if device not in {"cuda", "cpu"} or not isinstance(compute_type, str) or not compute_type:
        raise Refusal()
    ffmpeg = local_path(transcription["ffmpeg_path"] if args.candidate == "stageflow"
                        else config["local_media_segmentation"]["ffmpeg_path"])
    ffprobe = local_path(config["local_media_timing"]["ffprobe_path"])
    cpp = local_path(args.whisper_cpp_binary) if args.whisper_cpp_binary else None
    if any(p.suffix.casefold() in {".bat", ".cmd"} for p in (ffmpeg, ffprobe, cpp) if p):
        raise Refusal()
    model = local_path(transcription["model_path"], directory=True)
    # faster-whisper otherwise downloads a fallback tokenizer even for a local model.
    local_path(str(model / "tokenizer.json"))
    return Settings(
        tuple(blocks[:args.max_blocks]), model,
        device, compute_type, ffmpeg, ffprobe, args.profile, args.language, cpp,
        local_path(args.whisper_cpp_model) if cpp else None, args.render_load,
        args.engine_timeout_seconds,
        args.candidate,
    )


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float
    segment: int = 0

    def __post_init__(self) -> None:
        if (not math.isfinite(self.start) or not math.isfinite(self.end)
                or not 0 <= self.start <= self.end):
            raise ValueError("invalid_word")


@dataclass(frozen=True)
class Measurement:
    words: tuple[Word, ...]
    decode_seconds: float
    inference_seconds: float
    total_seconds: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "words", tuple(self.words))
        if any(not math.isfinite(n) or n < 0 for n in (
            self.decode_seconds, self.inference_seconds, self.total_seconds,
        )) or self.total_seconds <= 0:
            raise ValueError("invalid_measurement")


def summary(values: Sequence[float]) -> dict[str, float | None]:
    """Median and nearest-rank p95; empty evidence is null, never perfect agreement."""
    ordered = sorted(values)
    return {"median": median(ordered) if ordered else None,
            "p95": ordered[math.ceil(len(ordered) * .95) - 1] if ordered else None}


def word_agreement(baseline: Sequence[Word], candidate: Sequence[Word]) -> dict[str, Any]:
    left = [(word_tokens(w.text), w) for w in baseline if word_tokens(w.text)]
    right = [(word_tokens(w.text), w) for w in candidate if word_tokens(w.text)]
    matcher = SequenceMatcher(None, [t for t, _ in left], [t for t, _ in right], autojunk=False)
    pairs = [(left[i + k][1], right[j + k][1])
             for i, j, size in matcher.get_matching_blocks() for k in range(size)]
    return {"matched_word_count": len(pairs),
            "matched_word_fraction": len(pairs) / len(left) if left else None,
            "start_delta_seconds": summary([abs(a.start - b.start) for a, b in pairs]),
            "end_delta_seconds": summary([abs(a.end - b.end) for a, b in pairs])}


def profile_phrases(key: str) -> tuple[tuple[str, ...], ...]:
    profile = next(p for p in BOUNDARY_CUE_CATALOG.profiles if p.key == key)
    cues = compose(CompositionRequest(BOUNDARY_CUE_CATALOG.version, profile.group_keys, key))
    # Changeover phrases occur in both lists; count each normalized phrase once.
    return tuple(dict.fromkeys(word_tokens(p) for p in (*cues.start, *cues.end)))


def cue_hits(words: Sequence[Word], phrases: Sequence[tuple[str, ...]]) -> list[tuple[int, float]]:
    """Literal normalized matching, non-overlapping per phrase, never across segments.

    Mirrors editorial.derivation.match_phrases; keeps only private ordinals/offsets.
    """
    hits: list[tuple[int, float]] = []
    for segment in dict.fromkeys(w.segment for w in words):
        tokens = [(token, w.start) for w in words if w.segment == segment
                  for token in word_tokens(w.text)]
        for phrase_id, phrase in enumerate(phrases):
            if not phrase:
                continue
            position = 0
            while position + len(phrase) <= len(tokens):
                end = position + len(phrase)
                if tuple(t for t, _ in tokens[position:end]) == phrase:
                    hits.append((phrase_id, tokens[position][1]))
                    position = end
                else:
                    position += 1
    return sorted(hits)


def cue_agreement(
    baseline: list[tuple[int, float]], candidate: list[tuple[int, float]],
) -> dict[str, Any]:
    # Ordered one-to-one matching maximizes matches within the inclusive 2 s window.
    left, right = sorted(baseline), sorted(candidate)
    i = j = 0
    deltas: list[float] = []
    while i < len(left) and j < len(right):
        a, b = left[i], right[j]
        if a[0] == b[0] and abs(a[1] - b[1]) <= 2:
            deltas.append(abs(a[1] - b[1]))
            i += 1
            j += 1
        elif a < b:
            i += 1
        else:
            j += 1
    return {"baseline_cue_hit_count": len(left), "cue_hit_count": len(right),
            "matched_cue_hit_count": len(deltas),
            "cue_hit_fraction": len(deltas) / len(left) if left else None,
            "cue_delta_seconds": summary(deltas)}


def decode_command(ffmpeg: Path, block: Path, wav: Path | None = None) -> list[str]:
    command = [str(ffmpeg), "-nostdin", "-hide_banner", "-loglevel", "error",
               "-protocol_whitelist", "file,pipe", "-i", str(block), "-map", "0:a:0",
               "-vn", "-ac", "1", "-ar", "16000"]
    return command + (["-c:a", "pcm_s16le", "-f", "wav", "-y", str(wav)] if wav else
                      ["-f", "f32le", "-"])


def pcm_array(data: bytes, numpy: Any = None) -> Any:
    if not data or len(data) % 4:
        raise ValueError("invalid_pcm")
    if numpy is None:
        numpy = importlib.import_module("numpy")
    # FFmpeg f32le is explicitly little-endian, independent of host byte order.
    return numpy.frombuffer(data, dtype="<f4").copy()


def cpp_command(settings: Settings, wav: Path, output: Path) -> list[str]:
    assert settings.cpp_binary is not None and settings.cpp_model is not None
    command = [str(settings.cpp_binary), "-m", str(settings.cpp_model), "-f", str(wav),
               "-l", settings.language, "-bs", "5", "-ojf", "-of", str(output),
               # Positive max length enables token timing; a high cap preserves cue spans.
               "-ml", "1000000", "-sow"]
    return command + (["-ng"] if settings.device == "cpu" else [])


def cpp_words(payload: Mapping[str, Any]) -> tuple[Word, ...]:
    """Full JSON token offsets are milliseconds; merge subwords, discard special tokens."""
    words: list[Word] = []
    for segment_id, segment in enumerate(payload["transcription"]):
        tokens = segment["tokens"]  # Missing token timing is a failure, never segment timing.
        for token in tokens:
            text = token["text"]
            if text.startswith("[_") or text.startswith("<|"):
                continue
            offsets = token["offsets"]
            start, end = float(offsets["from"]) / 1000, float(offsets["to"]) / 1000
            if words and not text.startswith(" ") and words[-1].segment == segment_id:
                previous = words.pop()
                words.append(Word(previous.text + text, previous.start, end, segment_id))
            else:
                words.append(Word(text, start, end, segment_id))
    return tuple(w for w in words if word_tokens(w.text))


class Load(Protocol):
    def alive(self) -> bool: ...
    def stop(self) -> None: ...


class Effects(Protocol):
    def warm_cache(self, block: Path) -> None: ...
    def warm_up(self, engine: str) -> None: ...
    def duration(self, block: Path) -> float: ...
    def measure(self, engine: str, block: Path) -> Measurement: ...
    def start_load(self, block: Path) -> Load: ...


class RenderLoad:
    def __init__(self, ffmpeg: Path, block: Path) -> None:
        self.process = subprocess.Popen(
            [str(ffmpeg), "-nostdin", "-hide_banner", "-loglevel", "error",
             "-stream_loop", "-1", "-protocol_whitelist", "file,pipe", "-i", str(block),
             "-map", "0:v:0", "-an", "-c:v", "h264_nvenc", "-progress", "pipe:1",
             "-f", "null", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        ready = Event()

        def drain() -> None:
            assert self.process.stdout is not None
            for line in self.process.stdout:
                if line.startswith(b"frame="):
                    try:
                        if int(line.split(b"=", 1)[1]) > 0:
                            ready.set()
                    except ValueError:
                        pass

        self.reader = Thread(target=drain, daemon=True)
        self.reader.start()
        if not ready.wait(30) or not self.alive():
            self.stop()
            raise RuntimeError("render_unavailable")

    def alive(self) -> bool:
        return self.process.poll() is None

    def stop(self) -> None:
        if self.alive():
            self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        self.reader.join(timeout=5)
        if self.process.stdout:
            self.process.stdout.close()


class LocalEffects:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model: Any = None
        self.command_timeout = TIMEOUT
        self.adapters: dict[str, Any] = {}
        self.decode_seconds = 0.0

    def warm_cache(self, block: Path) -> None:
        with block.open("rb") as source:
            while source.read(1024 * 1024):
                pass

    def warm_up(self, engine: str) -> None:
        if self.settings.candidate == "stageflow":
            from app.contexts.transcription_evidence import TranscriptionExecutionError

            with tempfile.TemporaryDirectory(prefix="transcription-parity-") as directory:
                path = Path(directory) / "silence.wav"
                with wave.open(str(path), "wb") as audio:
                    audio.setparams((1, 2, 16000, 16000, "NONE", "not compressed"))
                    audio.writeframes(bytes(32000))
                try:
                    self.adapter_measure(engine, path)
                except TranscriptionExecutionError as exc:
                    if exc.reason_code != "provider_no_speech_segments":
                        raise
            return
        if engine == "option_b":
            root = local_path(tempfile.gettempdir(), directory=True, external=True)
            with tempfile.TemporaryDirectory(prefix="transcription-spike-", dir=root) as directory:
                wav, output = Path(directory) / "silence.wav", Path(directory) / "result"
                with wave.open(str(wav), "wb") as audio:
                    audio.setparams((1, 2, 16000, 16000, "NONE", "not compressed"))
                    audio.writeframes(bytes(32000))
                subprocess.run(cpp_command(self.settings, wav, output), check=True,
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=PREFLIGHT_TIMEOUT)
            return
        self.load_model()
        numpy: Any = importlib.import_module("numpy")
        # Consume the lazy iterator: model construction alone does not exercise CUDA.
        segments, _ = self.model.transcribe(
            numpy.zeros(16000, dtype="float32"), language=self.settings.language,
            beam_size=5, word_timestamps=True, vad_filter=False,
            condition_on_previous_text=True,
        )
        for _ in segments:
            pass

    def command(self, command: list[str]) -> bytes:
        return subprocess.run(command, check=True, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                              timeout=self.command_timeout).stdout

    def duration(self, block: Path) -> float:
        result = self.command([str(self.settings.ffprobe), "-v", "error",
                               "-protocol_whitelist", "file,pipe", "-show_entries",
                               "format=duration", "-of", "json", str(block)])
        duration = float(json.loads(result)["format"]["duration"])
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("invalid_duration")
        return duration

    def start_load(self, block: Path) -> Load:
        return RenderLoad(self.settings.ffmpeg, block)

    def measure(self, engine: str, block: Path) -> Measurement:
        if self.settings.candidate == "stageflow":
            return self.adapter_measure(engine, block)
        if engine == "option_b":
            return self.cpp_measure(block)
        self.load_model()
        return self.whisper_measure(engine, block)

    def adapter_measure(self, engine: str, block: Path) -> Measurement:
        """ED-0122 measures the complete adapter boundary, including normalization.

        CPU comparison binds the reference factory to CPU int8 in this private
        harness only; the production faster-whisper constructor stays CUDA-only.
        """
        from app.contexts.transcription_evidence import TranscriptionExecutionRequest
        from app.contexts.work_execution import TranscriptionOperationInput
        from app.core.config.deployment import LocalTranscriptionConfiguration
        from app.infrastructure.transcription import (
            CTranslate2WhisperExecutionAdapter,
            FasterWhisperExecutionAdapter,
        )
        from app.shared.ids import EntityId
        from app.shared.time import SystemClock

        class Resolver:
            def resolve(inner, input: TranscriptionOperationInput) -> Path:
                return self.current_block

        self.current_block = block
        stageflow = engine == "stageflow"
        if engine not in self.adapters:
            configuration = LocalTranscriptionConfiguration(
                provider="stageflow-ctranslate2-whisper" if stageflow else "faster-whisper",
                model_version="offline-parity-model", model_path=str(self.settings.model),
                device=self.settings.device if stageflow else "cuda",
                compute_type=self.settings.compute_type if stageflow else "float16",
                execution_profile_id=f"parity-{engine}-{self.settings.device}",
                ffmpeg_path=str(self.settings.ffmpeg) if stageflow else None,
            )
            if stageflow:
                from app.infrastructure.transcription.ctranslate2_whisper.decode import (
                    FFmpegDecoder,
                )

                class TimedDecoder(FFmpegDecoder):
                    def decode(inner, path: Path, heartbeat: Callable[[], None]) -> Any:
                        started = time.perf_counter()
                        try:
                            return super().decode(path, heartbeat)
                        finally:
                            self.decode_seconds += time.perf_counter() - started

                self.adapters[engine] = CTranslate2WhisperExecutionAdapter(
                    configuration, resolver=Resolver(), clock=SystemClock(),
                    decoder_factory=TimedDecoder)
            else:
                def factory(path: str, **kwargs: Any) -> Any:
                    module = importlib.import_module("faster_whisper")
                    return module.WhisperModel(path, device=self.settings.device,
                                               compute_type=self.settings.compute_type,
                                               local_files_only=True)

                self.adapters[engine] = FasterWhisperExecutionAdapter(
                    configuration, resolver=Resolver(), clock=SystemClock(), model_factory=factory)
        identity = EntityId("42000000-0000-0000-0000-000000000001")
        request = TranscriptionExecutionRequest(
            operation_id=identity, attempt_id=identity, fence_generation=1, work_key="0" * 64,
            input=TranscriptionOperationInput(
                asset_id=identity, manifest_id=identity, manifest_version="1.0", asset_format="wav",
                execution_profile_id=f"parity-{engine}-{self.settings.device}",
                execution_profile_version="1.0", requested_language="en", request_word_timing=True))
        self.decode_seconds = 0.0
        module: Any = None
        original: Any = None
        if not stageflow:
            module = importlib.import_module("faster_whisper.transcribe")
            original = module.decode_audio

            def timed_decode(*args: Any, **kwargs: Any) -> Any:
                started = time.perf_counter()
                try:
                    with decoding():
                        return original(*args, **kwargs)
                finally:
                    self.decode_seconds += time.perf_counter() - started

            module.decode_audio = timed_decode
        started = time.perf_counter()
        try:
            result = self.adapters[engine].execute(request, lambda: None)
            if result.status.value != "complete":
                raise WorkerFailure("engine_failed")
            words = tuple(Word(w.text, w.asset_start_microseconds / 1e6,
                               w.asset_end_microseconds / 1e6, segment.ordinal)
                          for segment in result.segments for w in segment.words)
            total = time.perf_counter() - started
            return Measurement(words, self.decode_seconds,
                               max(0, total - self.decode_seconds), total)
        finally:
            if module is not None:
                module.decode_audio = original

    def load_model(self) -> None:
        if self.model is None:
            # Adapter factory reused lazily. Its CUDA-only wrapper cannot measure CPU/arrays.
            from app.infrastructure.transcription import faster_whisper as adapter

            local_path(str(self.settings.model / "tokenizer.json"))
            factory: Any = cast(Any, adapter)._default_model_factory()
            self.model = factory(str(self.settings.model), device=self.settings.device,
                                 compute_type=self.settings.compute_type, local_files_only=True)

    def whisper_measure(self, engine: str, block: Path) -> Measurement:
        module: Any = importlib.import_module("faster_whisper.transcribe")
        original = module.decode_audio
        decode_seconds = 0.0

        def timed_decode(*args: Any, **kwargs: Any) -> Any:
            nonlocal decode_seconds
            started = time.perf_counter()
            try:
                with decoding():
                    return original(*args, **kwargs)
            finally:
                decode_seconds += time.perf_counter() - started

        started = time.perf_counter()
        try:
            audio: Any = str(block)
            if engine == "baseline":
                module.decode_audio = timed_decode
            else:
                with decoding():
                    audio = pcm_array(self.command(decode_command(self.settings.ffmpeg, block)))
                decode_seconds = time.perf_counter() - started
            # Mirrors adapter execute(), faster_whisper.py:273-280. No exported settings object.
            segments, _ = self.model.transcribe(
                audio, language=self.settings.language, beam_size=5, word_timestamps=True,
                vad_filter=False, condition_on_previous_text=True,
            )
            words = tuple(Word(w.word, float(w.start), float(w.end), i)
                          for i, segment in enumerate(segments) for w in (segment.words or ()))
            total = time.perf_counter() - started
            return Measurement(words, decode_seconds, max(0, total - decode_seconds), total)
        finally:
            module.decode_audio = original

    def cpp_measure(self, block: Path) -> Measurement:
        # WAV/provider JSON are private scratch, never written into the repository.
        root = local_path(tempfile.gettempdir(), directory=True, external=True)
        with tempfile.TemporaryDirectory(prefix="transcription-spike-", dir=root) as directory:
            wav, output = Path(directory) / "audio.wav", Path(directory) / "result"
            started = time.perf_counter()
            with decoding():
                self.command(decode_command(self.settings.ffmpeg, block, wav))
            decoded = time.perf_counter()
            self.command(cpp_command(self.settings, wav, output))
            words = cpp_words(json.loads(output.with_suffix(".json").read_text(encoding="utf-8")))
            ended = time.perf_counter()
            return Measurement(words, decoded - started, ended - decoded, ended - started)


class WorkerConnection(Protocol):
    def send(self, obj: Any, /) -> None: ...
    def recv(self) -> Any: ...
    def poll(self, timeout: float = 0.0) -> bool: ...
    def close(self) -> None: ...


class WorkerFailure(RuntimeError):
    def __init__(self, code: Literal[
        "worker_start_failed", "cuda_runtime_unavailable", "warm_up_failed", "engine_failed",
        "decode_failed", "engine_timeout",
    ]) -> None:
        super().__init__(code)
        self.code = code


def warm_up_failure(exc: Exception, engine: str, device: str) -> str:
    if engine == "option_b":
        return "warm_up_failed"
    if isinstance(exc, EngineTimeout):
        return "warm_up_timeout"
    if isinstance(exc, WorkerFailure):
        return exc.code
    from app.infrastructure.transcription import faster_whisper as adapter

    failure = (exc if isinstance(exc, adapter.TranscriptionExecutionError)
               else cast(Any, adapter)._provider_failure(exc))
    if device == "cuda" and failure.reason_code == "cuda_runtime_unavailable":
        return "cuda_runtime_unavailable"
    return "warm_up_failed"


@contextmanager
def decoding() -> Generator[None]:
    try:
        yield
    except subprocess.TimeoutExpired:
        raise EngineTimeout() from None
    except Exception:
        raise WorkerFailure("decode_failed") from None


def measurement_failure(exc: Exception, engine: str, device: str) -> str:
    from app.contexts.transcription_evidence import TranscriptionExecutionError

    if isinstance(exc, TranscriptionExecutionError) and exc.reason_code == "media_decode_failed":
        return "decode_failed"
    if isinstance(exc, (EngineTimeout, subprocess.TimeoutExpired)):
        return "engine_timeout"
    if isinstance(exc, WorkerFailure):
        return (exc.code if exc.code in (
            "engine_failed", "decode_failed", "cuda_runtime_unavailable", "engine_timeout",
        ) else "engine_failed")
    if warm_up_failure(exc, engine, device) == "cuda_runtime_unavailable":
        return "cuda_runtime_unavailable"
    return "engine_failed"


def engine_worker(connection: WorkerConnection, settings: Settings,
                  factory: Callable[[Settings], LocalEffects] = LocalEffects) -> None:
    """Private result IPC only; Python/native diagnostics always go to the null device."""
    with quiet_output(native=True):
        effects = factory(settings)
        # Let subprocess.run kill/reap a stuck decoder before the outer worker deadline.
        effects.command_timeout = settings.engine_timeout_seconds - 10
        try:
            while True:
                action, engine, block = connection.recv()
                try:
                    result = (effects.warm_up(engine) if action == "warm_up"
                              else effects.measure(engine, block))
                except Exception as exc:
                    # Send before native object destruction, which can itself hang.
                    code = (warm_up_failure(exc, engine, settings.device)
                            if action == "warm_up"
                            else measurement_failure(exc, engine, settings.device))
                    connection.send((False, code))
                else:
                    connection.send((True, result))
        except EOFError:
            pass
        finally:
            connection.close()


class EngineTimeout(RuntimeError):
    pass


class GuardedEffects(LocalEffects):
    """One persistent model worker; parent owns deadlines and forced cleanup."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.worker: Any = None
        self.connection: WorkerConnection | None = None

    def call(self, action: str, engine: str, block: Path | None = None) -> Any:
        try:
            if self.worker is None:
                try:
                    context = multiprocessing.get_context("spawn")
                    self.connection, child = context.Pipe()
                    try:
                        worker = context.Process(target=engine_worker, args=(child, self.settings))
                        try:
                            worker.start()
                        except Exception:
                            worker.close()
                            raise
                        self.worker = worker
                    finally:
                        child.close()
                except Exception:
                    raise WorkerFailure("worker_start_failed") from None
            assert self.connection is not None
            self.connection.send((action, engine, block))
            deadline = (PREFLIGHT_TIMEOUT if action == "warm_up"
                        else self.settings.engine_timeout_seconds)
            if not self.connection.poll(deadline):
                raise EngineTimeout()
            succeeded, result = self.connection.recv()
            if not succeeded:
                # Whitelist private IPC as well; never forward arbitrary worker strings.
                if action == "warm_up":
                    raise WorkerFailure("cuda_runtime_unavailable"
                                        if result == "cuda_runtime_unavailable"
                                        else "warm_up_failed")
                for code in ("engine_failed", "decode_failed", "cuda_runtime_unavailable",
                             "engine_timeout"):
                    if result == code:
                        raise WorkerFailure(code)
                raise WorkerFailure("engine_failed")
            return result
        except Exception:
            self.close()
            raise

    def warm_up(self, engine: str) -> None:
        # External CLI already has a subprocess timeout and owns its scratch cleanup.
        if engine == "option_b":
            super().warm_up(engine)
        else:
            self.call("warm_up", engine)

    def measure(self, engine: str, block: Path) -> Measurement:
        if engine == "option_b":
            return super().measure(engine, block)
        if self.worker is None:
            self.warm_up(engine)
        return cast(Measurement, self.call("measure", engine, block))

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        if self.worker is not None:
            if self.worker.is_alive():
                self.worker.terminate()
            self.worker.join(timeout=5)
            if self.worker.is_alive():
                self.worker.kill()
                self.worker.join(timeout=5)
            self.worker.close()
            self.worker = None


def flatten_numbers(value: Mapping[str, Any], prefix: str = "") -> dict[str, float]:
    numbers: dict[str, float] = {}
    for key, item in value.items():
        name = f"{prefix}{key}"
        if isinstance(item, dict):
            numbers.update(flatten_numbers(cast(dict[str, Any], item), name + "_"))
        elif type(item) in (int, float) and key != "ordinal":
            numbers[name] = item
    return numbers


def aggregate(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for engine in (*ENGINES, "stageflow"):
        for pass_id in (1, 2):
            for load in ("off", "active", "unavailable"):
                selected = [r for r in rows
                            if r["engine"] == engine and r["pass_ordinal"] == pass_id
                            and r["render_load"] == load and r["status"] == "completed"]
                if not selected:
                    continue
                samples: dict[str, list[float]] = {}
                for row in selected:
                    for key, number in flatten_numbers(row["metrics"]).items():
                        samples.setdefault(key, []).append(number)
                result.append({"engine": engine, "pass_ordinal": pass_id, "render_load": load,
                               "block_count": len(selected),
                               "metrics": {k: {"sample_count": len(v), **summary(v)}
                                           for k, v in samples.items()}})
    return result


def run(settings: Settings, effects: Effects) -> tuple[int, dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    phrases = profile_phrases(settings.profile)
    engines = (("baseline", "stageflow") if settings.candidate == "stageflow" else
               ENGINES[:3] if settings.cpp_binary else ENGINES[:2])
    durations: dict[Path, float] = {}
    for ordinal, block in enumerate(settings.blocks, 1):
        try:
            duration = effects.duration(block)
            if not math.isfinite(duration) or duration <= 0:
                raise ValueError()
            durations[block] = duration
        except Exception:
            failures.append({"ordinal": ordinal, "failure_code": "probe_failed"})
    unavailable: dict[str, str] = {}
    if durations:
        for engine in engines:
            if engine in unavailable:
                continue
            try:
                effects.warm_up(engine)
            except Exception as exc:
                code = warm_up_failure(exc, engine, settings.device)
                unavailable[engine] = code
                if (settings.candidate == "option_a" and settings.device == "cuda"
                        and engine != "option_b"):
                    unavailable.update(baseline=code, option_a=code)
    for pass_id in range(1, 3 if settings.render_load else 2):
        for ordinal, block in enumerate(settings.blocks, 1):
            if block not in durations:
                continue
            try:
                effects.warm_cache(block)
            except Exception:
                failures.append({"ordinal": ordinal, "failure_code": "cache_warm_failed"})
                continue
            measurements: dict[str, Measurement] = {}
            block_rows: list[dict[str, Any]] = []
            # Reverse every other block (same sequence in both load passes).
            order = engines if ordinal % 2 else tuple(reversed(engines))
            for position, engine in enumerate(order, 1):
                row: dict[str, Any] = {"ordinal": ordinal, "engine": engine,
                                       "pass_ordinal": pass_id, "render_load": "off",
                                       "first_engine": order[0], "engine_ordinal": position}
                if engine in unavailable:
                    row.update(status="failed", failure_code=unavailable[engine])
                    rows.append(row)
                    continue
                load: Load | None = None
                if pass_id == 2:
                    row["render_load"] = "unavailable"
                    try:
                        load = effects.start_load(block)
                        if load.alive():
                            row["render_load"] = "active"
                    except Exception:
                        pass
                try:
                    measured = effects.measure(engine, block)
                    measurements[engine] = measured
                    metrics: dict[str, Any] = {
                        "media_seconds": durations[block],
                        "decode_seconds": measured.decode_seconds,
                        "inference_seconds": measured.inference_seconds,
                        "total_seconds": measured.total_seconds,
                        "real_time_factor": durations[block] / measured.total_seconds,
                        "word_count": len(measured.words),
                        "cue_hit_count": len(cue_hits(measured.words, phrases)),
                        "word_agreement": None, "cue_agreement": None,
                    }
                    row.update(status="completed", metrics=metrics)
                except Exception as exc:
                    row.update(status="failed", failure_code=measurement_failure(
                        exc, engine, settings.device))
                finally:
                    if load is not None:
                        try:
                            if not load.alive():
                                row["render_load"] = "unavailable"
                            load.stop()
                        except Exception:
                            row["render_load"] = "unavailable"
                rows.append(row)
                block_rows.append(row)
            baseline = measurements.get("baseline")
            if baseline is not None:
                for row in block_rows:
                    if row["status"] == "completed":
                        measured = measurements[row["engine"]]
                        row["metrics"]["word_agreement"] = word_agreement(
                            baseline.words, measured.words)
                        row["metrics"]["cue_agreement"] = cue_agreement(
                            cue_hits(baseline.words, phrases), cue_hits(measured.words, phrases))
    errors = len(failures) + sum(r["status"] == "failed" for r in rows)
    return (3 if errors else 0), {
        "error_count": errors, "device": settings.device, "profile": settings.profile,
        "block_count": len(settings.blocks), "failures": failures,
        "measurements": rows, "aggregates": aggregate(rows),
    }


@contextmanager
def native_handles(sink: TextIO) -> Generator[None]:
    """Windows DLLs can use OS standard handles instead of Python's CRT fd table."""
    if os.name != "nt":
        yield
        return
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetStdHandle.argtypes = [wintypes.DWORD]
    kernel.GetStdHandle.restype = wintypes.HANDLE
    kernel.SetStdHandle.argtypes = [wintypes.DWORD, wintypes.HANDLE]
    kernel.SetStdHandle.restype = wintypes.BOOL
    saved = [(number, kernel.GetStdHandle(number)) for number in (-11, -12)]
    try:
        for number, _ in saved:
            if not kernel.SetStdHandle(number, msvcrt.get_osfhandle(sink.fileno())):
                raise OSError()
        yield
    finally:
        for number, handle in saved:
            kernel.SetStdHandle(number, handle)


@contextmanager
def quiet_output(*, native: bool) -> Generator[None]:
    """Suppress provider Python logging and native stdout/stderr, restoring both on error."""
    with open(os.devnull, "w") as sink:
        saved: list[tuple[int, int]] = []
        try:
            if native:
                sys.stdout.flush()
                sys.stderr.flush()
                for fd in (1, 2):
                    saved.append((fd, os.dup(fd)))
                    os.dup2(sink.fileno(), fd)
            with redirect_stdout(sink), redirect_stderr(sink):
                if native:
                    with native_handles(sink):
                        yield
                else:
                    yield
        finally:
            for fd, original in saved:
                os.dup2(original, fd)
                os.close(original)


def markdown(report: dict[str, Any]) -> str:
    lines = ["| engine | pass | render_load | blocks | total median s | total p95 s |",
             "| --- | --- | --- | --- | --- | --- |"]
    for row in report.get("aggregates", []):
        total = row["metrics"]["total_seconds"]
        lines.append(f"| {row['engine']} | {row['pass_ordinal']} | {row['render_load']} | "
                     f"{row['block_count']} | {total['median']:.6f} | {total['p95']:.6f} |")
    return "\n".join(lines)


def main(
    argv: Sequence[str] | None = None, *, output: TextIO | None = None,
    table_output: TextIO | None = None,
    loader: Callable[[argparse.Namespace, Mapping[str, str]], Settings] = load_settings,
    effects_factory: Callable[[Settings], Effects] = GuardedEffects, native_quiet: bool = False,
) -> int:
    output, table_output = output or sys.stdout, table_output or sys.stderr
    args: argparse.Namespace | None = None
    try:
        args = parser().parse_args(argv)
    except Exception:
        print(json.dumps({"error_count": 1}), file=output)
        return 1
    with quiet_output(native=native_quiet):
        try:
            settings = loader(args, os.environ)
        except Exception:
            code, report = 1, {"error_count": 1}
        else:
            effects = effects_factory(settings)
            try:
                code, report = run(settings, effects)
            finally:
                if isinstance(effects, GuardedEffects):
                    effects.close()
    print(json.dumps(report, allow_nan=False), file=output)
    if args.markdown and code != 1:
        print(markdown(report), file=table_output)
    return code


if __name__ == "__main__":
    raise SystemExit(main(native_quiet=True))
