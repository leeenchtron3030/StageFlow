"""Optional evaluation adapters for local transcription engines.

These adapters are qualification-only and intentionally use lazy imports or explicitly
supplied executables. Their dependencies are not StageFlow runtime dependencies.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import math
import subprocess
import tempfile
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

try:
    from qualification.transcription_benchmark import (
        CorpusItem,
        EngineIdentity,
        EngineSegment,
        EngineTranscript,
        EngineWord,
        EvaluationError,
    )
except ModuleNotFoundError:
    from transcription_benchmark import (
        CorpusItem,
        EngineIdentity,
        EngineSegment,
        EngineTranscript,
        EngineWord,
        EvaluationError,
    )


def _version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError as exc:
        raise EvaluationError(f"optional runtime {distribution} is unavailable") from exc


class FasterWhisperEngine:
    def __init__(
        self,
        *,
        model: str,
        model_version: str,
        device: str,
        compute_type: str,
    ) -> None:
        initialization_started = time.perf_counter()
        try:
            runtime_module = importlib.import_module("faster_whisper")
            whisper_model: Any = runtime_module.WhisperModel
        except (ImportError, AttributeError, OSError) as exc:
            raise EvaluationError("faster-whisper runtime could not be loaded") from exc

        runtime_version = _version("faster-whisper")
        ctranslate_version = _version("ctranslate2")
        model_path = Path(model).resolve(strict=False)
        model_id = model_path.name if model_path.is_dir() else model
        self._identity = EngineIdentity(
            provider_id="faster-whisper",
            provider_version=runtime_version,
            model_id=model_id,
            model_version=model_version,
            execution_tool_id="ctranslate2",
            execution_tool_version=ctranslate_version,
            execution_revision=f"stageflow-eval-{runtime_version}",
            device=device,
            compute_type=compute_type,
            capabilities=(
                "asset-relative-segment-timing",
                "asset-relative-word-timing",
                "language-detection",
                "local-model-cache",
            ),
            limitations=("speaker-labels-unavailable",),
        )
        try:
            self._model: Any = whisper_model(
                model,
                device=device,
                compute_type=compute_type,
            )
        except (RuntimeError, OSError, ValueError) as exc:
            raise EvaluationError("faster-whisper model could not be initialized") from exc
        self._initialization_seconds = time.perf_counter() - initialization_started

    @property
    def identity(self) -> EngineIdentity:
        return self._identity

    @property
    def initialization_seconds(self) -> float:
        return self._initialization_seconds

    def transcribe(
        self,
        item: CorpusItem,
        renew_lease: Callable[[], None],
    ) -> EngineTranscript:
        renew_lease()
        try:
            raw_segments, info = self._model.transcribe(
                str(item.media_path),
                language=item.language,
                beam_size=5,
                word_timestamps=True,
                vad_filter=False,
                condition_on_previous_text=True,
            )
            segments: list[EngineSegment] = []
            for raw_segment in raw_segments:
                renew_lease()
                raw_words = getattr(raw_segment, "words", None) or ()
                words = tuple(
                    EngineWord(
                        text=str(word.word),
                        start_seconds=float(word.start),
                        end_seconds=float(word.end),
                        confidence=float(word.probability),
                        confidence_semantics="provider-probability",
                    )
                    for word in raw_words
                    if str(word.word).strip()
                )
                raw_start = float(raw_segment.start)
                raw_end = float(raw_segment.end)
                segment_start = min(
                    (raw_start, *(word.start_seconds for word in words))
                )
                segment_end = max((raw_end, *(word.end_seconds for word in words)))
                limitations = ["segment-confidence-not-normalized"]
                if segment_start != raw_start or segment_end != raw_end:
                    limitations.append("segment-boundary-expanded-to-word-timing")
                segments.append(
                    EngineSegment(
                        text=str(raw_segment.text),
                        start_seconds=segment_start,
                        end_seconds=segment_end,
                        words=words,
                        limitations=tuple(limitations),
                    )
                )
        except EvaluationError:
            raise
        except (RuntimeError, OSError, ValueError) as exc:
            diagnostic = str(exc).casefold()
            for runtime_library in ("cublas64_12.dll", "cudnn64_9.dll"):
                if runtime_library in diagnostic:
                    raise EvaluationError(
                        f"faster-whisper runtime library unavailable: {runtime_library}"
                    ) from exc
            raise EvaluationError("faster-whisper transcription failed") from exc
        if not segments:
            raise EvaluationError("faster-whisper returned no speech segments")
        language_value = str(getattr(info, "language", item.language or "und"))
        return EngineTranscript(
            language=language_value,
            segments=tuple(segments),
            produced_at=datetime.now(UTC),
            limitations=(
                "speaker-labels-unavailable",
                "provider-language-probability-not-persisted",
            ),
        )


class WhisperCppEngine:
    def __init__(
        self,
        *,
        executable: Path,
        model: Path,
        model_version: str,
        device: str,
        compute_type: str,
    ) -> None:
        initialization_started = time.perf_counter()
        executable_path = executable.resolve(strict=False)
        model_path = model.resolve(strict=False)
        if not executable_path.is_file():
            raise EvaluationError("whisper.cpp executable is unavailable")
        if not model_path.is_file():
            raise EvaluationError("whisper.cpp model is unavailable")
        try:
            completed = subprocess.run(
                [str(executable_path), "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise EvaluationError("whisper.cpp executable could not be inspected") from exc
        version_text = (completed.stdout + completed.stderr).strip()
        version_match = None
        version_tokens = version_text.replace("(", " ").replace(")", " ").split()
        for index, token in enumerate(version_tokens):
            if token.rstrip(":").casefold() == "version" and index + 1 < len(version_tokens):
                candidate = version_tokens[index + 1].strip(",")
                if candidate[:1].isdigit():
                    version_match = candidate
                    break
            if token.startswith("v") and token[1:2].isdigit():
                version_match = token.strip(",")
                break
        runtime_version = version_match or "unreported"
        self._executable = executable_path
        self._model = model_path
        self._identity = EngineIdentity(
            provider_id="whisper.cpp",
            provider_version=runtime_version,
            model_id=model_path.stem,
            model_version=model_version,
            execution_tool_id="whisper-cli",
            execution_tool_version=runtime_version,
            execution_revision=f"stageflow-eval-{runtime_version}",
            device=device,
            compute_type=compute_type,
            capabilities=(
                "asset-relative-segment-timing",
                "language-detection",
                "local-model-file",
                "subprocess-isolation",
            ),
            limitations=(
                "speaker-labels-unavailable",
                "word-timing-experimental-not-normalized",
            ),
        )
        self._initialization_seconds = time.perf_counter() - initialization_started

    @property
    def identity(self) -> EngineIdentity:
        return self._identity

    @property
    def initialization_seconds(self) -> float:
        return self._initialization_seconds

    @staticmethod
    def _offsets(value: object) -> tuple[float, float]:
        if not isinstance(value, Mapping):
            raise EvaluationError("whisper.cpp segment offsets are malformed")
        offsets = cast(Mapping[str, object], value)
        try:
            raw_start = offsets["from"]
            raw_end = offsets["to"]
        except KeyError as exc:
            raise EvaluationError("whisper.cpp segment offsets are malformed") from exc
        if not isinstance(raw_start, int | float) or not isinstance(raw_end, int | float):
            raise EvaluationError("whisper.cpp segment offsets are malformed")
        start = float(raw_start) / 1000
        end = float(raw_end) / 1000
        if not math.isfinite(start) or not math.isfinite(end):
            raise EvaluationError("whisper.cpp segment offsets are non-finite")
        return start, end

    def transcribe(
        self,
        item: CorpusItem,
        renew_lease: Callable[[], None],
    ) -> EngineTranscript:
        renew_lease()
        with tempfile.TemporaryDirectory(prefix="stageflow-whisper-cpp-") as directory:
            output_base = Path(directory) / "result"
            command = [
                str(self._executable),
                "-m",
                str(self._model),
                "-f",
                str(item.media_path),
                "-bs",
                "5",
                "-ojf",
                "-of",
                str(output_base),
                "-np",
            ]
            if item.language is not None:
                command.extend(("-l", item.language))
            if self._identity.device.casefold() == "cpu":
                command.append("--no-gpu")
            elif self._identity.device.casefold() not in {"cuda", "gpu"}:
                raise EvaluationError("whisper.cpp device must be cpu or cuda")
            try:
                completed = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    timeout=max(300, int(item.duration_seconds * 10)),
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise EvaluationError("whisper.cpp transcription could not complete") from exc
            renew_lease()
            output_path = output_base.with_suffix(".json")
            if completed.returncode != 0 or not output_path.is_file():
                raise EvaluationError("whisper.cpp transcription failed")
            try:
                document: object = json.loads(output_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise EvaluationError("whisper.cpp JSON output is malformed") from exc

        if not isinstance(document, Mapping):
            raise EvaluationError("whisper.cpp JSON output root is malformed")
        root = cast(Mapping[str, object], document)
        result = root.get("result")
        language: str | None = item.language
        if isinstance(result, Mapping):
            result_map = cast(Mapping[str, object], result)
            raw_language = result_map.get("language")
            if raw_language is not None:
                language = str(raw_language)
        raw_transcription_value = root.get("transcription")
        if not isinstance(raw_transcription_value, list):
            raise EvaluationError("whisper.cpp JSON transcription is malformed")
        raw_transcription = cast(list[object], raw_transcription_value)

        segments: list[EngineSegment] = []
        for raw_segment in raw_transcription:
            if not isinstance(raw_segment, Mapping):
                raise EvaluationError("whisper.cpp JSON segment is malformed")
            segment = cast(Mapping[str, object], raw_segment)
            text_value = str(segment.get("text", "")).strip()
            if not text_value:
                continue
            start, end = self._offsets(segment.get("offsets"))
            segments.append(
                EngineSegment(
                    text=text_value,
                    start_seconds=start,
                    end_seconds=end,
                    limitations=("word-timing-experimental-not-normalized",),
                )
            )
        if not segments:
            raise EvaluationError("whisper.cpp returned no speech segments")
        return EngineTranscript(
            language=language,
            segments=tuple(segments),
            produced_at=datetime.now(UTC),
            limitations=(
                "speaker-labels-unavailable",
                "word-timing-experimental-not-normalized",
            ),
        )