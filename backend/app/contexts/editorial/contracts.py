from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.shared.ids import EntityId
from app.shared.time import require_aware_datetime


class EditorialCandidateOrigin(StrEnum):
    OBSERVED = "observed"
    DERIVED = "derived"
    INFERRED = "inferred"
    DECLARED = "declared"


class EditorialCandidateSourceKind(StrEnum):
    PRODUCER_DECLARATION = "producer_declaration"


class EditorialReviewState(StrEnum):
    UNREVIEWED = 'unreviewed'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    REVISION_REQUESTED = 'revision_requested'
    DEFERRED = 'deferred'


class EditorialMomentReviewAction(StrEnum):
    APPROVE_AND_CREATE_CLIP = 'approve_and_create_clip'
    REJECT = 'reject'
    REVISE_RANGE = 'revise_range'
    DEFER = 'defer'

    @property
    def projected_state(self) -> EditorialReviewState:
        return {
            EditorialMomentReviewAction.APPROVE_AND_CREATE_CLIP: (
                EditorialReviewState.APPROVED
            ),
            EditorialMomentReviewAction.REJECT: EditorialReviewState.REJECTED,
            EditorialMomentReviewAction.REVISE_RANGE: (
                EditorialReviewState.REVISION_REQUESTED
            ),
            EditorialMomentReviewAction.DEFER: EditorialReviewState.DEFERRED,
        }[self]


class EditorialGenerationState(StrEnum):
    HEALTHY = "healthy"
    UNKNOWN = "unknown"


class EditorialLocationConflictReason(StrEnum):
    PARTIALLY_EXCLUDED = "partially_excluded_by_session_boundary"
    EXCLUDED = "excluded_by_session_boundary"


@dataclass(frozen=True, slots=True)
class EditorialCandidateLocation:
    session_revision: int
    timeline_start_microseconds: int
    timeline_end_microseconds: int | None
    session_authoritative_start: datetime
    session_authoritative_end: datetime | None

    def __post_init__(self) -> None:
        if self.session_revision < 1:
            raise ValueError("session_revision must be positive")
        if self.timeline_start_microseconds < 0:
            raise ValueError("timeline_start_microseconds must be nonnegative")
        if (
            self.timeline_end_microseconds is not None
            and self.timeline_end_microseconds < self.timeline_start_microseconds
        ):
            raise ValueError("timeline_end_microseconds cannot precede the start")
        require_aware_datetime(
            self.session_authoritative_start, "session_authoritative_start"
        )
        if self.session_authoritative_end is not None:
            require_aware_datetime(
                self.session_authoritative_end, "session_authoritative_end"
            )
            if self.session_authoritative_end < self.session_authoritative_start:
                raise ValueError("session_authoritative_end cannot precede the start")


@dataclass(frozen=True, slots=True)
class DeclareEditorialMoment:
    candidate_moment_id: EntityId
    operation_id: EntityId
    session_id: EntityId
    expected_session_revision: int
    timeline_start_microseconds: int
    timeline_end_microseconds: int | None
    actor_id: EntityId
    note: str | None
    declared_at: datetime
    request_digest: str

    def __post_init__(self) -> None:
        if self.expected_session_revision < 1:
            raise ValueError("expected_session_revision must be positive")
        if self.timeline_start_microseconds < 0:
            raise ValueError("timeline_start_microseconds must be nonnegative")
        if (
            self.timeline_end_microseconds is not None
            and self.timeline_end_microseconds < self.timeline_start_microseconds
        ):
            raise ValueError("timeline_end_microseconds cannot precede the start")
        if self.note is not None:
            normalized = self.note.strip()
            if not normalized:
                raise ValueError("note must be nonempty when supplied")
            object.__setattr__(self, "note", normalized)
        require_aware_datetime(self.declared_at, "declared_at")
        if len(self.request_digest) != 64:
            raise ValueError("request_digest must be a sha256 hex digest")


@dataclass(frozen=True, slots=True)
class EditorialCandidateMoment:
    id: EntityId
    session_id: EntityId
    expected_session_revision: int
    timeline_start_microseconds: int
    timeline_end_microseconds: int | None
    session_authoritative_start: datetime
    session_authoritative_end: datetime | None
    actor_id: EntityId
    operation_id: EntityId
    note: str | None
    declared_at: datetime
    revision: int = 1
    origin: EditorialCandidateOrigin = EditorialCandidateOrigin.DECLARED
    epistemic_kind: EditorialCandidateOrigin = EditorialCandidateOrigin.DECLARED
    reason_code: str = "human_mark_moment"
    source_kind: EditorialCandidateSourceKind = (
        EditorialCandidateSourceKind.PRODUCER_DECLARATION
    )
    review_state: EditorialReviewState = EditorialReviewState.UNREVIEWED
    updated_at: datetime | None = None
    location_conflict_reason: EditorialLocationConflictReason | None = None

    def __post_init__(self) -> None:
        if self.revision < 1:
            raise ValueError('Editorial Candidate Moment revision must be positive')
        origin = EditorialCandidateOrigin(self.origin)
        epistemic_kind = EditorialCandidateOrigin(self.epistemic_kind)
        source_kind = EditorialCandidateSourceKind(self.source_kind)
        review_state = EditorialReviewState(self.review_state)
        conflict_reason = (
            None
            if self.location_conflict_reason is None
            else EditorialLocationConflictReason(self.location_conflict_reason)
        )
        if (
            origin is not EditorialCandidateOrigin.DECLARED
            or epistemic_kind is not EditorialCandidateOrigin.DECLARED
        ):
            raise ValueError("human-declared Editorial Candidate Moment must be declared")
        if source_kind is not EditorialCandidateSourceKind.PRODUCER_DECLARATION:
            raise ValueError("human-declared source kind must be producer_declaration")
        if self.reason_code != "human_mark_moment":
            raise ValueError("Editorial Candidate Moment reason is fixed")
        EditorialCandidateLocation(
            session_revision=self.expected_session_revision,
            timeline_start_microseconds=self.timeline_start_microseconds,
            timeline_end_microseconds=self.timeline_end_microseconds,
            session_authoritative_start=self.session_authoritative_start,
            session_authoritative_end=self.session_authoritative_end,
        )
        require_aware_datetime(self.declared_at, "declared_at")
        updated_at = self.declared_at if self.updated_at is None else self.updated_at
        require_aware_datetime(updated_at, "updated_at")
        object.__setattr__(self, "origin", origin)
        object.__setattr__(self, "epistemic_kind", epistemic_kind)
        object.__setattr__(self, "source_kind", source_kind)
        object.__setattr__(self, "review_state", review_state)
        object.__setattr__(self, "updated_at", updated_at)
        object.__setattr__(self, "location_conflict_reason", conflict_reason)

    @property
    def created_at(self) -> datetime:
        return self.declared_at

    @property
    def location(self) -> EditorialCandidateLocation:
        return EditorialCandidateLocation(
            session_revision=self.expected_session_revision,
            timeline_start_microseconds=self.timeline_start_microseconds,
            timeline_end_microseconds=self.timeline_end_microseconds,
            session_authoritative_start=self.session_authoritative_start,
            session_authoritative_end=self.session_authoritative_end,
        )

    @property
    def location_conflict(self) -> bool:
        return self.location_conflict_reason is not None


@dataclass(frozen=True, slots=True)
class EditorialReviewRange:
    timeline_start_microseconds: int
    timeline_end_microseconds: int

    def __post_init__(self) -> None:
        if self.timeline_start_microseconds < 0:
            raise ValueError('timeline_start_microseconds must be nonnegative')
        if self.timeline_end_microseconds < self.timeline_start_microseconds:
            raise ValueError('timeline_end_microseconds cannot precede the start')


@dataclass(frozen=True, slots=True)
class ReviewEditorialMoment:
    review_decision_id: EntityId
    clip_id: EntityId | None
    operation_id: EntityId
    candidate_moment_id: EntityId
    expected_candidate_revision: int
    actor_id: EntityId
    action: EditorialMomentReviewAction
    reason: str
    notes: str | None
    adjusted_range: EditorialReviewRange | None
    decided_at: datetime
    request_digest: str

    def __post_init__(self) -> None:
        if self.expected_candidate_revision < 1:
            raise ValueError('expected_candidate_revision must be positive')
        action = EditorialMomentReviewAction(self.action)
        reason = self.reason.strip()
        if not reason:
            raise ValueError('reason must be nonempty')
        notes = None if self.notes is None else self.notes.strip()
        if self.notes is not None and not notes:
            raise ValueError('notes must be nonempty when supplied')
        if action is EditorialMomentReviewAction.REVISE_RANGE:
            if self.adjusted_range is None:
                raise ValueError('revise_range requires an adjusted range')
        elif action in {
            EditorialMomentReviewAction.REJECT,
            EditorialMomentReviewAction.DEFER,
        } and self.adjusted_range is not None:
            raise ValueError(f'{action.value} cannot carry an adjusted range')
        if action is EditorialMomentReviewAction.APPROVE_AND_CREATE_CLIP:
            if self.clip_id is None:
                raise ValueError('approval requires a Clip identity')
        elif self.clip_id is not None:
            raise ValueError('only approval may allocate a Clip identity')
        require_aware_datetime(self.decided_at, 'decided_at')
        if len(self.request_digest) != 64 or any(
            character not in '0123456789abcdef'
            for character in self.request_digest
        ):
            raise ValueError('request_digest must be a sha256 hex digest')
        object.__setattr__(self, 'action', action)
        object.__setattr__(self, 'reason', reason)
        object.__setattr__(self, 'notes', notes)


@dataclass(frozen=True, slots=True)
class EditorialMomentReviewDecision:
    id: EntityId
    sequence: int
    operation_id: EntityId
    candidate_moment_id: EntityId
    candidate_revision: int
    actor_id: EntityId
    action: EditorialMomentReviewAction
    reason: str
    notes: str | None
    adjusted_range: EditorialReviewRange | None
    decided_at: datetime

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError('review decision sequence must be positive')
        if self.candidate_revision < 1:
            raise ValueError('candidate_revision must be positive')
        action = EditorialMomentReviewAction(self.action)
        reason = self.reason.strip()
        if not reason:
            raise ValueError('reason must be nonempty')
        notes = None if self.notes is None else self.notes.strip()
        if self.notes is not None and not notes:
            raise ValueError('notes must be nonempty when supplied')
        if action is EditorialMomentReviewAction.REVISE_RANGE:
            if self.adjusted_range is None:
                raise ValueError('revise_range requires an adjusted range')
        elif action in {
            EditorialMomentReviewAction.REJECT,
            EditorialMomentReviewAction.DEFER,
        } and self.adjusted_range is not None:
            raise ValueError(f'{action.value} cannot carry an adjusted range')
        require_aware_datetime(self.decided_at, 'decided_at')
        object.__setattr__(self, 'action', action)
        object.__setattr__(self, 'reason', reason)
        object.__setattr__(self, 'notes', notes)

    @property
    def review_state(self) -> EditorialReviewState:
        return self.action.projected_state


@dataclass(frozen=True, slots=True)
class EditorialClip:
    id: EntityId
    session_id: EntityId
    candidate_moment_id: EntityId
    candidate_revision: int
    review_decision_id: EntityId
    approved_range: EditorialReviewRange
    created_at: datetime
    revision: int = 1

    def __post_init__(self) -> None:
        if self.candidate_revision < 1:
            raise ValueError('candidate_revision must be positive')
        if self.revision < 1:
            raise ValueError('Editorial Clip revision must be positive')
        require_aware_datetime(self.created_at, 'created_at')


@dataclass(frozen=True, slots=True)
class EditorialMomentReviewResult:
    decision: EditorialMomentReviewDecision
    clip: EditorialClip | None

    def __post_init__(self) -> None:
        approval = (
            self.decision.action
            is EditorialMomentReviewAction.APPROVE_AND_CREATE_CLIP
        )
        if approval != (self.clip is not None):
            raise ValueError('only approval produces an Editorial Clip')
        if self.clip is not None:
            if self.clip.review_decision_id != self.decision.id:
                raise ValueError('Clip decision lineage must match the review decision')
            if self.clip.candidate_moment_id != self.decision.candidate_moment_id:
                raise ValueError('Clip candidate lineage must match the review decision')
            if self.clip.candidate_revision != self.decision.candidate_revision:
                raise ValueError('Clip candidate revision must match the review decision')


@dataclass(frozen=True, slots=True)
class EditorialReviewQueuePosition:
    review_priority: int
    created_at: datetime
    candidate_moment_id: EntityId

    def __post_init__(self) -> None:
        if self.review_priority < 0:
            raise ValueError('review_priority must be nonnegative')
        require_aware_datetime(self.created_at, 'created_at')


@dataclass(frozen=True, slots=True)
class EditorialReviewQueueItem:
    event_id: EntityId
    stage_id: EntityId
    candidate: EditorialCandidateMoment
    decisions: tuple[EditorialMomentReviewDecision, ...]
    clips: tuple[EditorialClip, ...]
    review_priority: int
    history_truncated: bool = False

    def __post_init__(self) -> None:
        if self.review_priority < 0:
            raise ValueError('review_priority must be nonnegative')
        if any(
            decision.candidate_moment_id != self.candidate.id
            for decision in self.decisions
        ):
            raise ValueError('review history must belong to the queue candidate')
        if any(clip.candidate_moment_id != self.candidate.id for clip in self.clips):
            raise ValueError('Clip history must belong to the queue candidate')
        derived_state = (
            EditorialReviewState.UNREVIEWED
            if not self.decisions
            else self.decisions[-1].review_state
        )
        if self.candidate.review_state is not derived_state:
            raise ValueError('candidate review state must derive from decision history')

    @property
    def position(self) -> EditorialReviewQueuePosition:
        return EditorialReviewQueuePosition(
            review_priority=self.review_priority,
            created_at=self.candidate.created_at,
            candidate_moment_id=self.candidate.id,
        )


@dataclass(frozen=True, slots=True)
class EditorialReviewQueuePage:
    event_id: EntityId
    items: tuple[EditorialReviewQueueItem, ...]
    total_candidate_count: int
    pending_candidate_count: int
    oldest_pending_candidate_at: datetime | None

    def __post_init__(self) -> None:
        if self.total_candidate_count < 0 or self.pending_candidate_count < 0:
            raise ValueError('review queue counts must be nonnegative')
        if self.pending_candidate_count > self.total_candidate_count:
            raise ValueError('pending count cannot exceed total count')
        if self.oldest_pending_candidate_at is not None:
            require_aware_datetime(
                self.oldest_pending_candidate_at,
                'oldest_pending_candidate_at',
            )


@dataclass(frozen=True, slots=True)
class EditorialSessionCandidateProjection:
    session_id: EntityId
    candidate_count: int
    latest_candidate_activity_at: datetime | None
    generation_state: EditorialGenerationState
    location_conflict_count: int = 0

    def __post_init__(self) -> None:
        if self.candidate_count < 0 or self.location_conflict_count < 0:
            raise ValueError("candidate projection counts must be nonnegative")
        if self.location_conflict_count > self.candidate_count:
            raise ValueError("location conflict count cannot exceed candidate count")
        if self.latest_candidate_activity_at is not None:
            require_aware_datetime(
                self.latest_candidate_activity_at, "latest_candidate_activity_at"
            )
        object.__setattr__(
            self, "generation_state", EditorialGenerationState(self.generation_state)
        )


__all__ = [
    "DeclareEditorialMoment",
    "EditorialClip",
    "EditorialCandidateLocation",
    "EditorialCandidateMoment",
    "EditorialCandidateOrigin",
    "EditorialCandidateSourceKind",
    "EditorialGenerationState",
    "EditorialLocationConflictReason",
    "EditorialMomentReviewAction",
    "EditorialMomentReviewDecision",
    "EditorialMomentReviewResult",
    "EditorialReviewQueueItem",
    "EditorialReviewQueuePage",
    "EditorialReviewQueuePosition",
    "EditorialReviewRange",
    "EditorialReviewState",
    "EditorialSessionCandidateProjection",
    "ReviewEditorialMoment",
]
