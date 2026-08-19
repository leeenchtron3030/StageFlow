"""Provider-neutral, qualification-only transcription benchmark contracts.

The harness emits External test evidence. It never selects a production provider,
grants transcript authority, or serializes media paths, raw provider payloads, or
credentials.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import NAMESPACE_URL, uuid5

from app.contexts.transcription_evidence import (
    NormalizedTranscriptResult,
    TranscriptEvidenceStatus,
    TranscriptExecutionProvenance,
    TranscriptionExecutionPort,
    TranscriptionExecutionRequest,
    TranscriptSegment,
    TranscriptWord,
)
from app.shared.ids import EntityId

HARNESS_NAME = "stageflow-transcription-engine-evaluation"
HARNESS_VERSION = "1.0"
CORPUS_SCHEMA = "stageflow.transcription-evaluation-corpus"
REPORT_SCHEMA = "stageflow.transcription-evaluation-report"
SCHEMA_VERSION = "1.0"
MAX_ITEMS = 100
MAX_MEDIA_BYTES = 8 * 1024 * 1024 * 1024
MAX_REFERENCE_CHARACTERS = 100_000
SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)(authorization|credential|password|private[_ -]?key|secret|token)\s*[:=]"
)


class EvaluationError(RuntimeError):
    """An operator-correctable failure with a privacy-safe message."""


def _safe_identifier(value: str, field_name: str) -> str:
    normalized = value.strip()
    if (
        SAFE_IDENTIFIER.fullmatch(normalized) is None
        or SENSITIVE_ASSIGNMENT.search(normalized)
    ):
        raise EvaluationError(f"{field_name} is not a sanitized stable identifier")
    return normalized


def _digest(value: str, field_name: str) -> str:
    normalized = value.strip()
    if DIGEST.fullmatch(normalized) is None:
        raise EvaluationError(f"{field_name} must be a lowercase SHA-256 digest")
    return normalized


def _finite_nonnegative(value: float, field_name: str) -> float:
    if not math.isfinite(value) or value < 0:
        raise EvaluationError(f"{field_name} must be finite and non-negative")
    return value


def _file_digest(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class EngineIdentity:
    provider_id: str
    provider_version: str
    model_id: str
    model_version: str
    execution_tool_id: str
    execution_tool_version: str
    execution_revision: str
    device: str
    compute_type: str
    capabilities: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "provider_id",
            "provider_version",
            "model_id",
            "model_version",
            "execution_tool_id",
            "execution_tool_version",
            "execution_revision",
            "device",
            "compute_type",
        ):
            object.__setattr__(
                self,
                field_name,
                _safe_identifier(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self,
            "capabilities",
            tuple(sorted({_safe_identifier(value, "capability") for value in self.capabilities})),
        )
        object.__setattr__(
            self,
            "limitations",
            tuple(sorted({_safe_identifier(value, "limitation") for value in self.limitations})),
        )


@dataclass(frozen=True, slots=True)
class CorpusItem:
    alias: str
    media_path: Path
    media_sha256: str
    duration_seconds: float
    language: str | None
    reference_text: str | None
    condition: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "alias", _safe_identifier(self.alias, "alias"))
        object.__setattr__(self, "media_sha256", _digest(self.media_sha256, "media_sha256"))
        object.__setattr__(
            self,
            "duration_seconds",
            _finite_nonnegative(self.duration_seconds, "duration_seconds"),
        )
        if self.duration_seconds <= 0 or self.duration_seconds > 4 * 60 * 60:
            raise EvaluationError("duration_seconds is outside the bounded range")
        if self.language is not None:
            object.__setattr__(
                self,
                "language",
                _safe_identifier(self.language, "language"),
            )
        if self.reference_text is not None:
            reference = self.reference_text.strip()
            if (
                not reference
                or len(reference) > MAX_REFERENCE_CHARACTERS
                or "\x00" in reference
            ):
                raise EvaluationError("reference_text is empty or exceeds its bound")
            object.__setattr__(self, "reference_text", reference)
        object.__setattr__(
            self,
            "condition",
            _safe_identifier(self.condition, "condition"),
        )
        path = self.media_path.resolve(strict=False)
        if not path.is_file():
            raise EvaluationError(f"media for alias {self.alias} is unavailable")
        size = path.stat().st_size
        if size <= 0 or size > MAX_MEDIA_BYTES:
            raise EvaluationError(f"media for alias {self.alias} is outside the size bound")
        if _file_digest(path) != self.media_sha256:
            raise EvaluationError(f"media digest mismatch for alias {self.alias}")
        object.__setattr__(self, "media_path", path)


@dataclass(frozen=True, slots=True)
class EngineWord:
    text: str
    start_seconds: float
    end_seconds: float
    confidence: float | None = None
    confidence_semantics: str | None = None

    def __post_init__(self) -> None:
        text_value = self.text.strip()
        if not text_value or len(text_value) > 512 or "\x00" in text_value:
            raise EvaluationError("engine word text is empty or exceeds its bound")
        object.__setattr__(self, "text", text_value)
        start = _finite_nonnegative(self.start_seconds, "word.start_seconds")
        end = _finite_nonnegative(self.end_seconds, "word.end_seconds")
        if end < start:
            raise EvaluationError("engine word end precedes its start")
        if self.confidence is not None:
            if not 0 <= self.confidence <= 1 or self.confidence_semantics is None:
                raise EvaluationError("word confidence requires bounded known semantics")
            object.__setattr__(
                self,
                "confidence_semantics",
                _safe_identifier(self.confidence_semantics, "confidence_semantics"),
            )
        elif self.confidence_semantics is not None:
            raise EvaluationError("word confidence semantics require a value")


@dataclass(frozen=True, slots=True)
class EngineSegment:
    text: str
    start_seconds: float
    end_seconds: float
    words: tuple[EngineWord, ...] = ()
    confidence: float | None = None
    confidence_semantics: str | None = None
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        text_value = self.text.strip()
        if not text_value or len(text_value) > 20_000 or "\x00" in text_value:
            raise EvaluationError("engine segment text is empty or exceeds its bound")
        object.__setattr__(self, "text", text_value)
        start = _finite_nonnegative(self.start_seconds, "segment.start_seconds")
        end = _finite_nonnegative(self.end_seconds, "segment.end_seconds")
        if end < start:
            raise EvaluationError("engine segment end precedes its start")
        for word in self.words:
            if word.start_seconds < start or word.end_seconds > end:
                raise EvaluationError("engine word timing must remain within its segment")
        if self.confidence is not None:
            if not 0 <= self.confidence <= 1 or self.confidence_semantics is None:
                raise EvaluationError("segment confidence requires bounded known semantics")
            object.__setattr__(
                self,
                "confidence_semantics",
                _safe_identifier(self.confidence_semantics, "confidence_semantics"),
            )
        elif self.confidence_semantics is not None:
            raise EvaluationError("segment confidence semantics require a value")
        object.__setattr__(
            self,
            "limitations",
            tuple(sorted({_safe_identifier(value, "limitation") for value in self.limitations})),
        )


@dataclass(frozen=True, slots=True)
class EngineTranscript:
    language: str | None
    segments: tuple[EngineSegment, ...]
    produced_at: datetime
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.segments:
            raise EvaluationError("engine transcript requires at least one segment")
        if self.produced_at.tzinfo is None or self.produced_at.utcoffset() is None:
            raise EvaluationError("produced_at must be timezone-aware")
        if self.language is not None:
            object.__setattr__(
                self,
                "language",
                _safe_identifier(self.language, "language"),
            )
        object.__setattr__(
            self,
            "limitations",
            tuple(sorted({_safe_identifier(value, "limitation") for value in self.limitations})),
        )


class EvaluationEngine(Protocol):
    @property
    def identity(self) -> EngineIdentity: ...

    @property
    def initialization_seconds(self) -> float: ...

    def transcribe(
        self,
        item: CorpusItem,
        renew_lease: Callable[[], None],
    ) -> EngineTranscript: ...


def _entity_id(seed: str) -> EntityId:
    return EntityId.parse(str(uuid5(NAMESPACE_URL, seed)))


def normalize_transcript(
    identity: EngineIdentity,
    item: CorpusItem,
    transcript: EngineTranscript,
) -> NormalizedTranscriptResult:
    segments: list[TranscriptSegment] = []
    for segment_ordinal, segment in enumerate(transcript.segments):
        words = tuple(
            TranscriptWord(
                id=_entity_id(
                    f"{identity.execution_revision}:{item.media_sha256}:"
                    f"{segment_ordinal}:{word_ordinal}"
                ),
                ordinal=word_ordinal,
                text=word.text,
                asset_start_microseconds=round(word.start_seconds * 1_000_000),
                asset_end_microseconds=round(word.end_seconds * 1_000_000),
                confidence=word.confidence,
                confidence_semantics=word.confidence_semantics,
            )
            for word_ordinal, word in enumerate(segment.words)
        )
        segments.append(
            TranscriptSegment(
                id=_entity_id(
                    f"{identity.execution_revision}:{item.media_sha256}:{segment_ordinal}"
                ),
                ordinal=segment_ordinal,
                text=segment.text,
                asset_start_microseconds=round(segment.start_seconds * 1_000_000),
                asset_end_microseconds=round(segment.end_seconds * 1_000_000),
                confidence=segment.confidence,
                confidence_semantics=segment.confidence_semantics,
                words=words,
                limitations=segment.limitations,
            )
        )
    return NormalizedTranscriptResult(
        status=TranscriptEvidenceStatus.COMPLETE,
        provenance=TranscriptExecutionProvenance(
            provider_id=identity.provider_id,
            provider_version=identity.provider_version,
            model_id=identity.model_id,
            model_version=identity.model_version,
            execution_tool_id=identity.execution_tool_id,
            execution_tool_version=identity.execution_tool_version,
            execution_revision=identity.execution_revision,
            produced_at=transcript.produced_at.astimezone(UTC),
        ),
        language=transcript.language,
        segments=tuple(segments),
        limitations=transcript.limitations,
    )


@dataclass(slots=True)
class QualificationExecutionPort(TranscriptionExecutionPort):
    engine: EvaluationEngine
    locate_media: Callable[[TranscriptionExecutionRequest], CorpusItem]

    def execute(
        self,
        request: TranscriptionExecutionRequest,
        renew_lease: Callable[[], None],
    ) -> NormalizedTranscriptResult:
        item = self.locate_media(request)
        renew_lease()
        transcript = self.engine.transcribe(item, renew_lease)
        renew_lease()
        return normalize_transcript(self.engine.identity, item, transcript)


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(
        re.findall(r"[^\W_]+(?:['’][^\W_]+)?", normalized, flags=re.UNICODE)
    ).replace("’", "'")


def _edit_distance(reference: Sequence[str], hypothesis: Sequence[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for reference_index, reference_value in enumerate(reference, start=1):
        current = [reference_index]
        for hypothesis_index, hypothesis_value in enumerate(hypothesis, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[hypothesis_index] + 1,
                    previous[hypothesis_index - 1]
                    + (reference_value != hypothesis_value),
                )
            )
        previous = current
    return previous[-1]


def word_error_rate(reference: str, hypothesis: str) -> float:
    reference_words = normalize_text(reference).split()
    hypothesis_words = normalize_text(hypothesis).split()
    if not reference_words:
        raise EvaluationError("WER reference must contain at least one normalized word")
    return _edit_distance(reference_words, hypothesis_words) / len(reference_words)


def character_error_rate(reference: str, hypothesis: str) -> float:
    reference_characters = list(normalize_text(reference).replace(" ", ""))
    hypothesis_characters = list(normalize_text(hypothesis).replace(" ", ""))
    if not reference_characters:
        raise EvaluationError("CER reference must contain at least one normalized character")
    return _edit_distance(reference_characters, hypothesis_characters) / len(
        reference_characters
    )


def _transcript_text(result: NormalizedTranscriptResult) -> str:
    return " ".join(segment.text for segment in result.segments)


def _nvidia_used_memory_mib() -> int | None:
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used",
                "--format=csv,noheader,nounits",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    try:
        return sum(int(value.strip()) for value in completed.stdout.splitlines())
    except ValueError:
        return None


def run_benchmark(
    engine: EvaluationEngine,
    corpus: Sequence[CorpusItem],
    *,
    repetitions: int,
) -> dict[str, Any]:
    if not 1 <= repetitions <= 20:
        raise EvaluationError("repetitions must be between one and twenty")
    if not corpus or len(corpus) > MAX_ITEMS:
        raise EvaluationError("corpus item count is outside the supported bound")
    if len({item.alias for item in corpus}) != len(corpus):
        raise EvaluationError("corpus aliases must be unique")

    trials: list[dict[str, Any]] = []
    for repetition in range(1, repetitions + 1):
        for item in corpus:
            before_memory = _nvidia_used_memory_mib()
            renewals = 0

            def renew() -> None:
                nonlocal renewals
                renewals += 1

            started = time.perf_counter()
            transcript = engine.transcribe(item, renew)
            elapsed = time.perf_counter() - started
            result = normalize_transcript(engine.identity, item, transcript)
            after_memory = _nvidia_used_memory_mib()
            text_value = _transcript_text(result)
            trial: dict[str, Any] = {
                "item_alias": item.alias,
                "condition": item.condition,
                "media_sha256": item.media_sha256,
                "duration_seconds": item.duration_seconds,
                "repetition": repetition,
                "thermal_state": (
                    "cold_subprocess_model_load_included"
                    if "subprocess-isolation" in engine.identity.capabilities
                    else "first_inference_model_loaded"
                    if not trials
                    else "warm_inference_model_loaded"
                ),
                "elapsed_seconds": elapsed,
                "real_time_factor": elapsed / item.duration_seconds,
                "audio_seconds_per_wall_second": item.duration_seconds / elapsed,
                "sessions_per_hour_at_item_duration": 3600 / elapsed,
                "language": result.language,
                "segment_count": len(result.segments),
                "word_timing_count": sum(len(segment.words) for segment in result.segments),
                "transcript_sha256": sha256(text_value.encode("utf-8")).hexdigest(),
                "lease_renewal_count": renewals,
                "gpu_memory_used_before_mib": before_memory,
                "gpu_memory_used_after_mib": after_memory,
                "resource_observation_method": "nvidia_smi_host_aggregate_before_after",
                "limitations": list(result.limitations),
            }
            if item.reference_text is not None:
                trial["word_error_rate"] = word_error_rate(item.reference_text, text_value)
                trial["character_error_rate"] = character_error_rate(
                    item.reference_text,
                    text_value,
                )
            trials.append(trial)

    return {
        "schema_name": REPORT_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "harness": {"name": HARNESS_NAME, "version": HARNESS_VERSION},
        "generated_at": datetime.now(UTC).isoformat(),
        "epistemic_kind": "external_test_evidence",
        "authority_use_prohibited": True,
        "environment": {
            "os": platform.system(),
            "os_release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "engine": {
            "provider_id": engine.identity.provider_id,
            "provider_version": engine.identity.provider_version,
            "model_id": engine.identity.model_id,
            "model_version": engine.identity.model_version,
            "execution_tool_id": engine.identity.execution_tool_id,
            "execution_tool_version": engine.identity.execution_tool_version,
            "execution_revision": engine.identity.execution_revision,
            "device": engine.identity.device,
            "compute_type": engine.identity.compute_type,
            "capabilities": list(engine.identity.capabilities),
            "limitations": list(engine.identity.limitations),
            "initialization_seconds": engine.initialization_seconds,
        },
        "corpus": [
            {
                "alias": item.alias,
                "condition": item.condition,
                "media_sha256": item.media_sha256,
                "duration_seconds": item.duration_seconds,
                "language": item.language,
                "reference_available": item.reference_text is not None,
            }
            for item in corpus
        ],
        "trials": trials,
        "limitations": [
            "benchmark_results_do_not_select_a_production_provider",
            "media_paths_and_raw_provider_payloads_are_not_serialized",
            "host_aggregate_gpu_memory_is_not_process_peak_memory",
        ],
    }


def load_corpus_manifest(path: Path) -> tuple[CorpusItem, ...]:
    try:
        raw_document: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvaluationError("corpus manifest could not be read") from exc
    if not isinstance(raw_document, Mapping):
        raise EvaluationError("corpus manifest root must be an object")
    document = cast(Mapping[str, object], raw_document)
    if (
        document.get("schema_name") != CORPUS_SCHEMA
        or document.get("schema_version") != SCHEMA_VERSION
    ):
        raise EvaluationError("corpus manifest schema is unsupported")
    raw_items_value = document.get("items")
    if not isinstance(raw_items_value, list):
        raise EvaluationError("corpus manifest items must be an array")
    raw_items = cast(list[object], raw_items_value)
    if not 1 <= len(raw_items) <= MAX_ITEMS:
        raise EvaluationError("corpus manifest item count is outside the supported bound")
    items: list[CorpusItem] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, Mapping):
            raise EvaluationError("corpus item must be an object")
        item = cast(Mapping[str, object], raw_item)
        raw_language = item.get("language")
        raw_reference = item.get("reference_text")
        raw_duration = item.get("duration_seconds")
        if not isinstance(raw_duration, int | float):
            raise EvaluationError("duration_seconds must be numeric")
        items.append(
            CorpusItem(
                alias=str(item.get("alias", "")),
                media_path=Path(str(item.get("media_path", ""))),
                media_sha256=str(item.get("media_sha256", "")),
                duration_seconds=float(raw_duration),
                language=None if raw_language is None else str(raw_language),
                reference_text=None if raw_reference is None else str(raw_reference),
                condition=str(item.get("condition", "")),
            )
        )
    if len({item.alias for item in items}) != len(items):
        raise EvaluationError("corpus aliases must be unique")
    return tuple(items)

def _atomic_create(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise EvaluationError("output already exists") from exc
        except OSError as exc:
            raise EvaluationError("output could not be published atomically") from exc
    finally:
        temporary.unlink(missing_ok=True)


def write_report(path: Path, report: Mapping[str, object]) -> None:
    serialized = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if SENSITIVE_ASSIGNMENT.search(serialized):
        raise EvaluationError("report contains a sensitive assignment pattern")
    _atomic_create(path, serialized)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="StageFlow transcription evaluation")
    parser.add_argument("--corpus-manifest", required=True, type=Path)
    parser.add_argument("--engine", required=True, choices=("faster-whisper", "whisper-cpp"))
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-version", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--compute-type", default="float16")
    parser.add_argument("--executable", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if __name__ == "__main__":
        sys.modules.setdefault("transcription_benchmark", sys.modules[__name__])
    try:
        try:
            from qualification.transcription_engines import (
                FasterWhisperEngine,
                WhisperCppEngine,
            )
        except ModuleNotFoundError:
            from transcription_engines import FasterWhisperEngine, WhisperCppEngine

        corpus = load_corpus_manifest(args.corpus_manifest)
        if args.engine == "faster-whisper":
            engine: EvaluationEngine = FasterWhisperEngine(
                model=args.model,
                model_version=args.model_version,
                device=args.device,
                compute_type=args.compute_type,
            )
        else:
            if args.executable is None:
                raise EvaluationError("--executable is required for whisper-cpp")
            engine = WhisperCppEngine(
                executable=args.executable,
                model=Path(args.model),
                model_version=args.model_version,
                device=args.device,
                compute_type=args.compute_type,
            )
        write_report(
            args.output,
            run_benchmark(engine, corpus, repetitions=args.repetitions),
        )
    except EvaluationError as exc:
        print(f"transcription evaluation failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())