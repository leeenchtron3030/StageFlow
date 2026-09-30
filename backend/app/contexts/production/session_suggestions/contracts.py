"""Immutable policy inputs, components and human decision lineage."""
from dataclasses import dataclass, fields
from datetime import UTC, datetime
from enum import StrEnum
from math import isfinite

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
class PolicyV2(Policy):
    version: str = "2"
    changeover_seconds: int = 60
    coverage_gap_seconds: int = 30
    strength_cap_seconds: int = 600
    strength_unit_seconds: int = 60
    silence_multiplier: int = 2
    coverage_strength: int = 30
    plan_distance_seconds: int = 30
    cue_bonus: int = 1
    silence_support_share: float = 0.3


POLICY_V2 = PolicyV2()


@dataclass(frozen=True, slots=True)
class PolicyV3(PolicyV2):
    version: str = "3"
    block_gap_seconds: int = 1200
    offset_limit_seconds: int = 3600
    offset_grid_seconds: int = 60
    offset_refine_seconds: int = 10
    offset_support_seconds: int = 180
    offset_penalty_seconds: int = 600
    offset_gate_per_talk: int = 6


POLICY_V3 = PolicyV3()


class ScheduleOffsetSource(StrEnum):
    PRODUCER = "producer"
    ESTIMATED = "estimated"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class ScheduleOffsetEntry:
    effective_from: datetime
    offset_seconds: int

    def __post_init__(self) -> None:
        require_aware_datetime(self.effective_from, "effective_from")
        object.__setattr__(self, "effective_from", self.effective_from.astimezone(UTC))
        if type(self.offset_seconds) is not int or not -7200 <= self.offset_seconds <= 7200:
            raise ValueError("schedule offset must be an integer between -7200 and 7200")


def validate_offset_entries(entries: tuple[ScheduleOffsetEntry, ...]) -> None:
    if len(entries) > 20:
        raise ValueError("at most 20 schedule offset entries")
    if any(a.effective_from >= b.effective_from
           for a, b in zip(entries, entries[1:], strict=False)):
        raise ValueError("schedule offset entries must have strictly increasing effective_from")


@dataclass(frozen=True, slots=True)
class ScheduleOffsetSetting:
    event_id: EntityId
    stage_id: EntityId
    version: int
    command_id: EntityId
    request_digest: str
    set_by: EntityId
    set_at: datetime
    entries: tuple[ScheduleOffsetEntry, ...]

    def __post_init__(self) -> None:
        require_aware_datetime(self.set_at, "set_at")
        object.__setattr__(self, "entries", tuple(self.entries))
        validate_offset_entries(self.entries)
        if type(self.version) is not int or not 1 <= self.version <= MAX_COUNT:
            raise ValueError("schedule offset version out of bounds")
        if len(self.request_digest) != 64 or any(c not in "0123456789abcdef"
                                                for c in self.request_digest):
            raise ValueError("invalid schedule offset request digest")


@dataclass(frozen=True, slots=True)
class ScheduleBlock:
    ordinal: int
    first_planned_start: datetime
    last_planned_start: datetime
    talk_count: int
    schedule_offset_seconds: int
    schedule_offset_source: ScheduleOffsetSource
    estimate_score_margin: float
    override_setting_version: int | None = None

    def __post_init__(self) -> None:
        for name in ("first_planned_start", "last_planned_start"):
            require_aware_datetime(getattr(self, name), name)
        if (type(self.ordinal) is not int or not 0 <= self.ordinal < MAX_INPUTS
                or type(self.talk_count) is not int or not 1 <= self.talk_count <= MAX_INPUTS
                or self.last_planned_start < self.first_planned_start):
            raise ValueError("invalid schedule block")
        validate_schedule_offset(self.schedule_offset_seconds, self.schedule_offset_source)
        if (not isfinite(self.estimate_score_margin)
                or not 0 <= self.estimate_score_margin <= 600000):
            raise ValueError("estimate score margin out of bounds")
        if ((self.schedule_offset_source == ScheduleOffsetSource.PRODUCER)
                != (self.override_setting_version is not None)):
            raise ValueError("producer block requires override setting version")
        if self.override_setting_version is not None and (
                type(self.override_setting_version) is not int
                or not 1 <= self.override_setting_version <= MAX_COUNT):
            raise ValueError("override setting version out of bounds")


def validate_schedule_offset(seconds: int, source: ScheduleOffsetSource) -> None:
    if (type(seconds) is not int or not -7200 <= seconds <= 7200
            or source not in tuple(ScheduleOffsetSource)
            or source == ScheduleOffsetSource.NONE and seconds != 0
            or source == ScheduleOffsetSource.ESTIMATED and abs(seconds) > 3600):
        raise ValueError("invalid schedule offset components")


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
    already_realized: int = 0

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
        self._validate_duration()
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

    def _validate_duration(self) -> None:
        if (self.span.end - self.span.start).total_seconds() <= POLICY_V1.minimum_session_seconds:
            raise ValueError("suggestion must exceed 60 seconds")


@dataclass(frozen=True, slots=True)
class CandidateV2(Candidate):
    def _validate_duration(self) -> None:
        if (self.span.end - self.span.start).total_seconds() < POLICY_V2.minimum_session_seconds:
            raise ValueError("suggestion must span at least 60 seconds")


@dataclass(frozen=True, slots=True)
class CandidateV3(CandidateV2):
    schedule_offset_seconds: int = 0
    schedule_offset_source: ScheduleOffsetSource = ScheduleOffsetSource.NONE

    def __post_init__(self) -> None:
        CandidateV2.__post_init__(self)
        validate_schedule_offset(self.schedule_offset_seconds, self.schedule_offset_source)
        if self.expectation is None and (
                self.schedule_offset_seconds != 0
                or self.schedule_offset_source != ScheduleOffsetSource.NONE):
            raise ValueError("unscheduled suggestions require zero offset and source none")


@dataclass(frozen=True, slots=True)
class PolicyResult:
    candidates: tuple[Candidate, ...]
    skips: SkipCounts

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidates", tuple(self.candidates))


@dataclass(frozen=True, slots=True)
class PolicyResultV3(PolicyResult):
    blocks: tuple[ScheduleBlock, ...] = ()

    def __post_init__(self) -> None:
        PolicyResult.__post_init__(self)
        object.__setattr__(self, "blocks", tuple(self.blocks))


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
    blocks: tuple[ScheduleBlock, ...] = ()
    override_setting_version: int | None = None
    boundary_proposals_created: int = 0

    def __post_init__(self) -> None:
        require_aware_datetime(self.created_at, "created_at")
        if (type(self.boundary_proposals_created) is not int
                or not 0 <= self.boundary_proposals_created <= MAX_COUNT):
            raise ValueError("boundary proposal count out of bounds")
        object.__setattr__(self, "expectations", tuple(self.expectations))
        object.__setattr__(self, "assets", tuple(self.assets))
        object.__setattr__(self, "blocks", tuple(self.blocks))
        if self.policy not in (POLICY_V1, POLICY_V2, POLICY_V3):
            raise ValueError("unsupported suggestion policy")
        if self.policy != POLICY_V3 and (self.blocks or self.override_setting_version is not None):
            raise ValueError("schedule offset lineage requires v3")
        if tuple(b.ordinal for b in self.blocks) != tuple(range(len(self.blocks))):
            raise ValueError("schedule block ordinals must be contiguous")
        if any(b.override_setting_version is not None
               and b.override_setting_version != self.override_setting_version
               for b in self.blocks):
            raise ValueError("schedule block override version must match run")


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


class BoundaryProposalDecisionKind(StrEnum):
    APPLIED = "applied"
    DISMISSED = "dismissed"


@dataclass(frozen=True, slots=True)
class BoundaryProposalDecision:
    proposal_id: EntityId
    session_id: EntityId
    kind: BoundaryProposalDecisionKind
    command_id: EntityId
    request_digest: str
    actor_id: EntityId
    decided_at: datetime
    reason: str | None = None

    def __post_init__(self) -> None:
        require_aware_datetime(self.decided_at, "decided_at")
        if self.kind not in tuple(BoundaryProposalDecisionKind):
            raise ValueError("invalid boundary proposal decision kind")
        if len(self.request_digest) != 64 or any(c not in "0123456789abcdef"
                                                for c in self.request_digest):
            raise ValueError("invalid boundary proposal request digest")
        if self.reason is not None:
            if not 1 <= len(self.reason.strip()) <= 500 or "\x00" in self.reason:
                raise ValueError("boundary proposal reason out of bounds")
            object.__setattr__(self, "reason", self.reason.strip())


@dataclass(frozen=True, slots=True, kw_only=True)
class BoundaryProposalDecisionHistoryItem(BoundaryProposalDecision):
    """Decision read enriched from its immutable linked Kernel proposal."""

    boundary_kind: str

    def __post_init__(self) -> None:
        BoundaryProposalDecision.__post_init__(self)
        if self.boundary_kind not in ("start", "end"):
            raise ValueError("invalid boundary kind")

    @classmethod
    def from_decision(cls, decision: BoundaryProposalDecision,
                      boundary_kind: str
                      ) -> "BoundaryProposalDecisionHistoryItem":
        return cls(decision.proposal_id, decision.session_id, decision.kind,
                   decision.command_id, decision.request_digest, decision.actor_id,
                   decision.decided_at, decision.reason, boundary_kind=boundary_kind)
