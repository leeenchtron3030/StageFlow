"""Immutable Editorial inputs and lineage; no provider or persistence dependencies."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.shared.ids import EntityId
from app.shared.time import require_aware_datetime


def normalize_phrase(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def word_tokens(value: str) -> tuple[str, ...]:
    # Unicode alphanumeric characters, excluding underscore (which \w includes).
    return tuple(re.findall(r"[^\W_]+", normalize_phrase(value)))


def positive(value: int, name: str) -> None:
    if value < 1:
        raise ValueError(f"{name} must be positive")


@dataclass(frozen=True, slots=True)
class EditorialPhraseList:
    id: EntityId
    event_id: EntityId
    key: str
    version: int
    name: str
    phrases: tuple[str, ...]
    created_by: EntityId
    created_at: datetime

    def __post_init__(self) -> None:
        positive(self.version, "version")
        for field, maximum in (("key", 100), ("name", 200)):
            value = getattr(self, field).strip()
            if not 1 <= len(value) <= maximum:
                raise ValueError(f"{field} is outside its bounds")
            object.__setattr__(self, field, value)
        if isinstance(self.phrases, str) or not 1 <= len(self.phrases) <= 200:
            raise ValueError("phrase list must contain 1 to 200 phrases")
        phrases = tuple(phrase.strip() for phrase in self.phrases)
        if any(not 1 <= len(phrase) <= 100 for phrase in phrases):
            raise ValueError("phrases must contain 1 to 100 trimmed characters")
        normalized = tuple(word_tokens(phrase) for phrase in phrases)
        if any(not tokens for tokens in normalized):
            raise ValueError("phrases must contain at least one word token")
        if len(set(normalized)) != len(normalized):
            raise ValueError("duplicate normalized phrases")
        object.__setattr__(self, "phrases", phrases)
        require_aware_datetime(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class EditorialSessionBasis:
    session_id: EntityId
    event_id: EntityId
    revision: int
    authoritative_start: datetime | None
    authoritative_end: datetime | None

    def __post_init__(self) -> None:
        positive(self.revision, "revision")
        for name in ("authoritative_start", "authoritative_end"):
            value = getattr(self, name)
            if value is not None:
                require_aware_datetime(value, name)
        if (self.authoritative_start is not None
                and self.authoritative_end is not None
                and self.authoritative_end < self.authoritative_start):
            raise ValueError("Session end cannot precede start")


@dataclass(frozen=True, slots=True)
class EditorialTranscriptWord:
    id: EntityId
    text: str
    asset_start_microseconds: int
    asset_end_microseconds: int

    def __post_init__(self) -> None:
        if (self.asset_start_microseconds < 0
                or self.asset_end_microseconds < self.asset_start_microseconds):
            raise ValueError("invalid word range")


@dataclass(frozen=True, slots=True)
class EditorialTranscriptSegment:
    id: EntityId
    words: tuple[EditorialTranscriptWord, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "words", tuple(self.words))


class TimingQualification(StrEnum):
    UNQUALIFIED = "unqualified"
    QUALIFIED = "qualified"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class EditorialTimingBasis:
    evidence_id: EntityId
    revision: int
    qualification: TimingQualification
    candidate_started_at: datetime

    def __post_init__(self) -> None:
        positive(self.revision, "timing revision")
        object.__setattr__(self, "qualification", TimingQualification(self.qualification))
        require_aware_datetime(self.candidate_started_at, "candidate_started_at")


@dataclass(frozen=True, slots=True)
class EditorialDerivationInput:
    asset_id: EntityId
    transcript_evidence_id: EntityId | None
    transcript_revision: int | None
    timing: EditorialTimingBasis | None

    def __post_init__(self) -> None:
        if (self.transcript_evidence_id is None) != (self.transcript_revision is None):
            raise ValueError("transcript identity and revision must be paired")
        if self.transcript_revision is not None:
            positive(self.transcript_revision, "transcript revision")


@dataclass(frozen=True, slots=True)
class EditorialCandidateProvenance:
    run_id: EntityId
    phrase_list_id: EntityId
    phrase_list_version: int
    normalized_phrase: str
    asset_id: EntityId
    transcript_evidence_id: EntityId
    transcript_revision: int
    segment_id: EntityId
    first_word_id: EntityId
    last_word_id: EntityId
    asset_start_microseconds: int
    asset_end_microseconds: int
    timing_evidence_id: EntityId
    timing_revision: int
    timing_qualification: TimingQualification

    def __post_init__(self) -> None:
        for name in ("phrase_list_version", "transcript_revision", "timing_revision"):
            positive(getattr(self, name), name)
        if (not word_tokens(self.normalized_phrase)
                or normalize_phrase(self.normalized_phrase) != self.normalized_phrase):
            raise ValueError("matched phrase must be normalized")
        if (self.asset_start_microseconds < 0
                or self.asset_end_microseconds < self.asset_start_microseconds):
            raise ValueError("invalid provenance range")
        object.__setattr__(self, "timing_qualification",
                           TimingQualification(self.timing_qualification))


@dataclass(frozen=True, slots=True)
class EditorialSkipCounts:
    no_transcript: int = 0
    no_timing_evidence: int = 0
    no_session_start: int = 0
    outside_session: int = 0
    limit_reached: int = 0

    def __post_init__(self) -> None:
        if any(getattr(self, name) < 0 for name in self.__dataclass_fields__):
            raise ValueError("skip counts must be nonnegative")


@dataclass(frozen=True, slots=True)
class EditorialDerivationRun:
    id: EntityId
    session_id: EntityId
    phrase_list_id: EntityId
    phrase_list_version: int
    inputs: tuple[EditorialDerivationInput, ...]
    input_digest: str
    created_by: EntityId
    created_at: datetime
    candidate_ids: tuple[EntityId, ...]
    skips: EditorialSkipCounts

    def __post_init__(self) -> None:
        positive(self.phrase_list_version, "phrase_list_version")
        inputs = tuple(self.inputs)
        if inputs != tuple(sorted(inputs, key=lambda item: item.asset_id.value)):
            raise ValueError("run inputs must be sorted by asset")
        if len({item.asset_id for item in inputs}) != len(inputs):
            raise ValueError("run assets must be unique")
        candidates = tuple(self.candidate_ids)
        if len(candidates) > 500 or len(set(candidates)) != len(candidates):
            raise ValueError("run candidates must be unique and bounded to 500")
        if re.fullmatch(r"[0-9a-f]{64}", self.input_digest) is None:
            raise ValueError("invalid input digest")
        object.__setattr__(self, "inputs", inputs)
        object.__setattr__(self, "candidate_ids", candidates)
        require_aware_datetime(self.created_at, "created_at")
