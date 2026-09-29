"""Immutable policy inputs, components and human decision lineage."""
from dataclasses import dataclass, fields
from datetime import UTC, datetime
from enum import StrEnum

from app.contexts.editorial.derivation_contracts import TimingQualification
from app.contexts.events import ProgramExpectation
from app.contexts.production.media_segmentation_evidence.contracts import SegmentationInterval
from app.shared.ids import EntityId
from app.shared.time import require_aware_datetime

MAX_INPUTS = 10_000
MAX_COUNT = 2_147_483_647


class SuggestionConflictError(RuntimeError):
    pass


class SuggestionNotFoundError(LookupError):
    pass


class SuggestionStorageUnavailableError(RuntimeError):
    pass


class SuggestionStatus(StrEnum):
    OPEN = "open"
    SUPERSEDED = "superseded"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class EdgeKind(StrEnum):
    FREEZE = "freeze"
    GAP = "gap"
    COVERAGE = "coverage"
    SCHEDULE = "schedule"


class Strength(StrEnum):
    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"


@dataclass(frozen=True, slots=True)
class Policy:
    id: str = "boundary-suggestion"
    version: str = "1"
    freeze_merge_seconds: int = 15
    changeover_seconds: int = 30
    edge_window_seconds: int = 1200
    minimum_session_seconds: int = 60
    cue_tie_seconds: int = 60
    start_cue_before_seconds: int = 120
    start_cue_after_seconds: int = 180
    end_cue_before_seconds: int = 180
    end_cue_after_seconds: int = 60
    unscheduled_seconds: int = 120
    clock_margin_seconds: int = 43200


POLICY_V1 = Policy()


@dataclass(frozen=True, slots=True)
class Reference:
    id: EntityId
    revision: int

    def __post_init__(self) -> None:
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be positive")


@dataclass(frozen=True, slots=True)
class Span:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        require_aware_datetime(self.start, "start")
        require_aware_datetime(self.end, "end")
        object.__setattr__(self, "start", self.start.astimezone(UTC))
        object.__setattr__(self, "end", self.end.astimezone(UTC))
        if self.end <= self.start:
            raise ValueError("end must follow start")


@dataclass(frozen=True, slots=True)
class AssetInput:
    asset_id: EntityId
    timing: Reference | None = None
    coverage: Span | None = None
    qualification: TimingQualification | None = None
    segmentation_ids: tuple[EntityId, ...] = ()
    intervals: tuple[SegmentationInterval, ...] = ()
    transcript: Reference | None = None
    start_cues: tuple[datetime, ...] = ()
    end_cues: tuple[datetime, ...] = ()

    def __post_init__(self) -> None:
        for name in ("segmentation_ids", "intervals", "start_cues", "end_cues"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        for cue in (*self.start_cues, *self.end_cues):
            require_aware_datetime(cue, "cue")
        if self.coverage is not None and (self.timing is None or self.qualification is None):
            raise ValueError("placed assets require timing lineage")


@dataclass(frozen=True, slots=True)
class SkipCounts:
    no_timing_evidence: int = 0
    no_segmentation: int = 0
    clock_implausible: int = 0
    no_coverage: int = 0
    no_planned_time: int = 0

    def __post_init__(self) -> None:
        if any(type(getattr(self, f.name)) is not int
               or not 0 <= getattr(self, f.name) <= MAX_COUNT for f in fields(self)):
            raise ValueError("skip count out of bounds")


@dataclass(frozen=True, slots=True)
class Candidate:
    expectation: Reference | None
    span: Span
    start_edge_kind: EdgeKind
    end_edge_kind: EdgeKind
    start_plan_offset_seconds: float | None
    end_plan_offset_seconds: float | None
    start_silence_support: bool
    end_silence_support: bool
    start_cue_support: bool
    end_cue_support: bool
    overlap: bool
    strength: Strength
    timing_qualifications: tuple[TimingQualification, ...]
    timing_references: tuple[Reference, ...]
    segmentation_ids: tuple[EntityId, ...]
    transcript_references: tuple[Reference, ...]

    def __post_init__(self) -> None:
        for name in ("timing_qualifications", "timing_references", "segmentation_ids",
                     "transcript_references"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if (self.span.end - self.span.start).total_seconds() <= POLICY_V1.minimum_session_seconds:
            raise ValueError("suggestion must exceed 60 seconds")
        if not self.timing_qualifications or not self.timing_references:
            raise ValueError("suggestion requires timing lineage")
        if ((self.expectation is None) != (self.start_plan_offset_seconds is None)
                or (self.expectation is None) != (self.end_plan_offset_seconds is None)):
            raise ValueError("planned offsets require expectation lineage")
        weak = (self.expectation is None or self.overlap
                or EdgeKind.SCHEDULE in (self.start_edge_kind, self.end_edge_kind))
        supported = (self.start_silence_support or self.end_silence_support
                     or self.start_cue_support or self.end_cue_support)
        strength = Strength.WEAK if weak else Strength.STRONG if supported else Strength.MEDIUM
        if self.strength != strength:
            raise ValueError("strength must follow policy components")


@dataclass(frozen=True, slots=True)
class PolicyResult:
    candidates: tuple[Candidate, ...]
    skips: SkipCounts

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidates", tuple(self.candidates))


@dataclass(frozen=True, slots=True)
class SuggestionRun:
    id: EntityId
    event_id: EntityId
    stage_id: EntityId
    input_digest: str
    actor_id: EntityId
    created_at: datetime
    expectations: tuple[Reference, ...]
    assets: tuple[AssetInput, ...]
    start_cue_list: Reference | None
    end_cue_list: Reference | None
    skips: SkipCounts
    policy: Policy = POLICY_V1

    def __post_init__(self) -> None:
        require_aware_datetime(self.created_at, "created_at")
        object.__setattr__(self, "expectations", tuple(self.expectations))
        object.__setattr__(self, "assets", tuple(self.assets))
        if self.policy != POLICY_V1:
            raise ValueError("unsupported suggestion policy")


@dataclass(frozen=True, slots=True)
class SessionSuggestion:
    id: EntityId
    run_id: EntityId
    event_id: EntityId
    stage_id: EntityId
    candidate: Candidate
    policy_id: str = POLICY_V1.id
    policy_version: str = POLICY_V1.version


@dataclass(frozen=True, slots=True)
class SuggestionDecision:
    command_id: EntityId
    request_digest: str
    suggestion_id: EntityId
    actor_id: EntityId
    decided_at: datetime
    kind: SuggestionStatus
    reason: str | None = None
    session_id: EntityId | None = None
    used_span: Span | None = None

    def __post_init__(self) -> None:
        require_aware_datetime(self.decided_at, "decided_at")
        if self.kind == SuggestionStatus.CONFIRMED:
            if self.session_id is None or self.used_span is None or self.reason is not None:
                raise ValueError("confirmation requires Session and used times")
        elif self.kind == SuggestionStatus.REJECTED:
            if (self.reason is None or not 1 <= len(self.reason.strip()) <= 500
                    or "\x00" in self.reason
                    or self.session_id is not None or self.used_span is not None):
                raise ValueError("rejection requires bounded reason")
            object.__setattr__(self, "reason", self.reason.strip())
        else:
            raise ValueError("invalid decision kind")


@dataclass(frozen=True, slots=True)
class InputSnapshot:
    expectations: tuple[ProgramExpectation, ...]
    assets: tuple[AssetInput, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "expectations", tuple(self.expectations))
        object.__setattr__(self, "assets", tuple(self.assets))
        if len(self.assets) > MAX_INPUTS or len(self.expectations) > MAX_INPUTS:
            raise SuggestionConflictError("suggestion_input_limit")
