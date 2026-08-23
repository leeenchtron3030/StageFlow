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
    UNREVIEWED = "unreviewed"


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
        if self.revision != 1:
            raise ValueError("declared Editorial Candidate Moment revision must be one")
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
        if review_state is not EditorialReviewState.UNREVIEWED:
            raise ValueError("Phase 1 Editorial Candidate Moments must be unreviewed")
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
    "EditorialCandidateLocation",
    "EditorialCandidateMoment",
    "EditorialCandidateOrigin",
    "EditorialCandidateSourceKind",
    "EditorialGenerationState",
    "EditorialLocationConflictReason",
    "EditorialReviewState",
    "EditorialSessionCandidateProjection",
]
