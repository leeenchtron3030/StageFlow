from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from app.shared.ids import CorrelationId, EntityId


class RecordingStatus(StrEnum):
    PLANNED = "planned"
    READY = "ready"
    RECORDING = "recording"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class LivestreamStatus(StrEnum):
    NOT_STARTED = "not_started"
    LIVE = "live"
    INTERRUPTED = "interrupted"
    ENDED = "ended"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RecordingBlock:
    """One continuous stage recording period."""

    id: EntityId
    stage_id: EntityId
    label: str
    planned_start: datetime
    correlation_id: CorrelationId
    planned_end: datetime | None = None
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    recording_status: RecordingStatus = RecordingStatus.PLANNED
    livestream_status: LivestreamStatus = LivestreamStatus.UNKNOWN
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.planned_end is not None and self.planned_end <= self.planned_start:
            raise ValueError("RecordingBlock planned_end must be after planned_start.")
        if self.actual_start is not None and self.actual_end is not None:
            if self.actual_end <= self.actual_start:
                raise ValueError("RecordingBlock actual_end must be after actual_start.")
        if not self.label.strip():
            raise ValueError("RecordingBlock label must not be empty.")
