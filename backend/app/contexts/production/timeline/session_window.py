from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.contexts.production.timeline.schedule_reference import ScheduleReference
from app.contexts.production.timeline.timeline_range import TimelineRange
from app.shared.ids import CorrelationId, EntityId
from app.shared.time import require_aware_datetime


class SessionWindowStatus(StrEnum):
    PROPOSED = "proposed"
    REVIEW_NEEDED = "review_needed"
    VERIFIED = "verified"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class VerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    HUMAN_VERIFIED = "human_verified"
    SYSTEM_VERIFIED = "system_verified"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class SessionWindow:
    """A verified or proposed media range for one scheduled session."""

    id: EntityId
    schedule_reference: ScheduleReference
    recording_block_id: EntityId
    timeline_range: TimelineRange
    correlation_id: CorrelationId
    created_at: datetime
    updated_at: datetime
    window_status: SessionWindowStatus = SessionWindowStatus.PROPOSED
    confidence: float = 0.0
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    notes: str | None = None

    def __post_init__(self) -> None:
        require_aware_datetime(self.created_at, "SessionWindow.created_at")
        require_aware_datetime(self.updated_at, "SessionWindow.updated_at")
        if self.timeline_range.recording_block_id != self.recording_block_id:
            raise ValueError("SessionWindow timeline_range must belong to recording_block_id.")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("SessionWindow confidence must be between 0.0 and 1.0.")
        if self.updated_at < self.created_at:
            raise ValueError("SessionWindow updated_at must not be before created_at.")
