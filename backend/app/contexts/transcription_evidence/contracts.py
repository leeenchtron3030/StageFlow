from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.contexts.production.media_timing_evidence import (
    RecorderProfileQualificationStatus,
)
from app.shared.ids import EntityId
from app.shared.time import require_aware_datetime

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_REASON = re.compile(r"^[a-z][a-z0-9_]{0,127}$")


def _identifier(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not _IDENTIFIER.fullmatch(normalized):
        raise ValueError(f"{field_name} must be a sanitized stable identifier.")
    return normalized


def _optional_identifier(value: str | None, field_name: str) -> str | None:
    return None if value is None else _identifier(value, field_name)


def _reason(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not _REASON.fullmatch(normalized):
        raise ValueError(f"{field_name} must be a sanitized reason code.")
    return normalized


def _digest(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not _DIGEST.fullmatch(normalized):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest.")
    return normalized


def _bounded_text(value: str, field_name: str, maximum: int) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > maximum or "\x00" in normalized:
        raise ValueError(f"{field_name} must be non-empty and bounded.")
    return normalized


def _limitations(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    return tuple(
        sorted({_bounded_text(value, field_name, 256) for value in values})
    )


def _confidence(
    value: float | None,
    semantics: str | None,
    field_name: str,
) -> tuple[float | None, str | None]:
    if value is None:
        if semantics is not None:
            raise ValueError(f"{field_name} semantics require a confidence value.")
        return None, None
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{field_name} must be a finite value between zero and one.")
    if semantics is None:
        raise ValueError(f"{field_name} requires explicit known semantics.")
    return value, _identifier(semantics, f"{field_name}_semantics")


class TranscriptEvidenceStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class SpeakerEvidenceKind(StrEnum):
    PROVIDER_INFERRED = "provider_inferred"
    PROVIDER_DECLARED = "provider_declared"
    UNKNOWN = "unknown"


class TranscriptTimingEpistemicKind(StrEnum):
    OBSERVED = "observed"
    DERIVED = "derived"


@dataclass(frozen=True, slots=True)
class TranscriptExecutionProvenance:
    provider_id: str
    provider_version: str
    model_id: str
    model_version: str
    execution_tool_id: str
    execution_tool_version: str
    execution_revision: str
    produced_at: datetime

    def __post_init__(self) -> None:
        for field_name in (
            "provider_id",
            "provider_version",
            "model_id",
            "model_version",
            "execution_tool_id",
            "execution_tool_version",
            "execution_revision",
        ):
            object.__setattr__(
                self,
                field_name,
                _identifier(getattr(self, field_name), field_name),
            )
        require_aware_datetime(self.produced_at, "produced_at")


@dataclass(frozen=True, slots=True)
class TranscriptWord:
    id: EntityId
    ordinal: int
    text: str
    asset_start_microseconds: int
    asset_end_microseconds: int
    confidence: float | None = None
    confidence_semantics: str | None = None
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.ordinal < 0:
            raise ValueError("word ordinal must not be negative.")
        object.__setattr__(self, "text", _bounded_text(self.text, "word.text", 512))
        if self.asset_start_microseconds < 0:
            raise ValueError("word start must not be negative.")
        if self.asset_end_microseconds < self.asset_start_microseconds:
            raise ValueError("word end must not precede word start.")
        value, semantics = _confidence(
            self.confidence,
            self.confidence_semantics,
            "word.confidence",
        )
        object.__setattr__(self, "confidence", value)
        object.__setattr__(self, "confidence_semantics", semantics)
        object.__setattr__(
            self,
            "limitations",
            _limitations(self.limitations, "word.limitation"),
        )

    @property
    def epistemic_kind(self) -> TranscriptTimingEpistemicKind:
        return TranscriptTimingEpistemicKind.OBSERVED


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    id: EntityId
    ordinal: int
    text: str
    asset_start_microseconds: int
    asset_end_microseconds: int
    speaker_label: str | None = None
    speaker_evidence_kind: SpeakerEvidenceKind | None = None
    confidence: float | None = None
    confidence_semantics: str | None = None
    words: tuple[TranscriptWord, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.ordinal < 0:
            raise ValueError("segment ordinal must not be negative.")
        object.__setattr__(
            self,
            "text",
            _bounded_text(self.text, "segment.text", 20_000),
        )
        if self.asset_start_microseconds < 0:
            raise ValueError("segment start must not be negative.")
        if self.asset_end_microseconds < self.asset_start_microseconds:
            raise ValueError("segment end must not precede segment start.")
        if (self.speaker_label is None) != (self.speaker_evidence_kind is None):
            raise ValueError("speaker label and evidence kind must be supplied together.")
        if self.speaker_label is not None:
            object.__setattr__(
                self,
                "speaker_label",
                _bounded_text(self.speaker_label, "speaker_label", 256),
            )
        value, semantics = _confidence(
            self.confidence,
            self.confidence_semantics,
            "segment.confidence",
        )
        object.__setattr__(self, "confidence", value)
        object.__setattr__(self, "confidence_semantics", semantics)
        words = tuple(sorted(self.words, key=lambda item: item.ordinal))
        if len({item.id for item in words}) != len(words):
            raise ValueError("word identities must be unique within a segment.")
        if len({item.ordinal for item in words}) != len(words):
            raise ValueError("word ordinals must be unique within a segment.")
        for word in words:
            if (
                word.asset_start_microseconds < self.asset_start_microseconds
                or word.asset_end_microseconds > self.asset_end_microseconds
            ):
                raise ValueError("word timing must remain within its segment.")
        object.__setattr__(self, "words", words)
        object.__setattr__(
            self,
            "limitations",
            _limitations(self.limitations, "segment.limitation"),
        )

    @property
    def epistemic_kind(self) -> TranscriptTimingEpistemicKind:
        return TranscriptTimingEpistemicKind.OBSERVED


@dataclass(frozen=True, slots=True)
class NormalizedTranscriptResult:
    status: TranscriptEvidenceStatus
    provenance: TranscriptExecutionProvenance
    language: str | None
    segments: tuple[TranscriptSegment, ...]
    limitations: tuple[str, ...] = ()
    partial_reason: str | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "language",
            _optional_identifier(self.language, "language"),
        )
        segments = tuple(sorted(self.segments, key=lambda item: item.ordinal))
        if len({item.id for item in segments}) != len(segments):
            raise ValueError("segment identities must be unique.")
        if len({item.ordinal for item in segments}) != len(segments):
            raise ValueError("segment ordinals must be unique.")
        object.__setattr__(self, "segments", segments)
        object.__setattr__(
            self,
            "limitations",
            _limitations(self.limitations, "transcript.limitation"),
        )
        if self.partial_reason is not None:
            object.__setattr__(
                self,
                "partial_reason",
                _reason(self.partial_reason, "partial_reason"),
            )
        if self.failure_reason is not None:
            object.__setattr__(
                self,
                "failure_reason",
                _reason(self.failure_reason, "failure_reason"),
            )
        if self.status is TranscriptEvidenceStatus.COMPLETE:
            if not segments or self.partial_reason is not None or self.failure_reason is not None:
                raise ValueError("complete evidence requires segments and no failure reason.")
        elif self.status is TranscriptEvidenceStatus.PARTIAL:
            if not segments or self.partial_reason is None or self.failure_reason is not None:
                raise ValueError("partial evidence requires segments and a partial reason.")
        elif segments or self.failure_reason is None or self.partial_reason is not None:
            raise ValueError("failed evidence requires only a failure reason.")


@dataclass(frozen=True, slots=True)
class DerivedTranscriptAlignment:
    id: EntityId
    segment_id: EntityId
    media_timing_evidence_id: EntityId
    qualification_status: RecorderProfileQualificationStatus
    wall_clock_started_at: datetime
    wall_clock_ended_at: datetime
    derived_at: datetime
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_aware_datetime(self.wall_clock_started_at, "wall_clock_started_at")
        require_aware_datetime(self.wall_clock_ended_at, "wall_clock_ended_at")
        require_aware_datetime(self.derived_at, "derived_at")
        if self.wall_clock_ended_at < self.wall_clock_started_at:
            raise ValueError("aligned end must not precede aligned start.")
        object.__setattr__(
            self,
            "limitations",
            _limitations(self.limitations, "alignment.limitation"),
        )

    @property
    def epistemic_kind(self) -> TranscriptTimingEpistemicKind:
        return TranscriptTimingEpistemicKind.DERIVED


@dataclass(frozen=True, slots=True)
class PendingTranscriptEvidence:
    id: EntityId
    operation_id: EntityId
    work_key: str
    result_digest: str
    asset_id: EntityId
    manifest_id: EntityId
    manifest_version: str
    result: NormalizedTranscriptResult
    alignments: tuple[DerivedTranscriptAlignment, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "work_key", _digest(self.work_key, "work_key"))
        object.__setattr__(
            self,
            "result_digest",
            _digest(self.result_digest, "result_digest"),
        )
        object.__setattr__(
            self,
            "manifest_version",
            _identifier(self.manifest_version, "manifest_version"),
        )
        alignments = tuple(sorted(self.alignments, key=lambda item: item.segment_id.value))
        segment_ids = {item.id for item in self.result.segments}
        if any(item.segment_id not in segment_ids for item in alignments):
            raise ValueError("alignment must reference a segment in this result.")
        if len({item.segment_id for item in alignments}) != len(alignments):
            raise ValueError("each segment may have at most one persisted alignment.")
        object.__setattr__(self, "alignments", alignments)


@dataclass(frozen=True, slots=True)
class TranscriptEvidenceRevision:
    id: EntityId
    operation_id: EntityId
    work_key: str
    result_digest: str
    asset_id: EntityId
    manifest_id: EntityId
    manifest_version: str
    revision: int
    predecessor_evidence_id: EntityId | None
    applied_at: datetime
    result: NormalizedTranscriptResult
    alignments: tuple[DerivedTranscriptAlignment, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "work_key", _digest(self.work_key, "work_key"))
        object.__setattr__(
            self,
            "result_digest",
            _digest(self.result_digest, "result_digest"),
        )
        object.__setattr__(
            self,
            "manifest_version",
            _identifier(self.manifest_version, "manifest_version"),
        )
        if self.revision < 1:
            raise ValueError("transcript evidence revision must be positive.")
        if (self.revision == 1) != (self.predecessor_evidence_id is None):
            raise ValueError("transcript evidence predecessor must match its revision.")
        require_aware_datetime(self.applied_at, "applied_at")


__all__ = [
    "DerivedTranscriptAlignment",
    "NormalizedTranscriptResult",
    "PendingTranscriptEvidence",
    "SpeakerEvidenceKind",
    "TranscriptEvidenceRevision",
    "TranscriptEvidenceStatus",
    "TranscriptExecutionProvenance",
    "TranscriptSegment",
    "TranscriptTimingEpistemicKind",
    "TranscriptWord",
]

