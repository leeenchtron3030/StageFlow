from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.contexts.production.runtime_clock.time_boundary_status import TimeBoundaryStatus
from app.contexts.production.runtime_clock.time_boundary_type import TimeBoundaryType
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata
from app.shared.time import require_aware_datetime


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class TimeBoundary:
    """A meaningful temporal boundary worth reporting when crossed."""

    id: EntityId
    boundary_type: TimeBoundaryType
    boundary_status: TimeBoundaryStatus
    boundary_timestamp: datetime
    stage_id: EntityId | None = None
    recording_block_id: EntityId | None = None
    scheduled_activity_id: EntityId | None = None
    label: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware_datetime(
            self.boundary_timestamp, "TimeBoundary.boundary_timestamp"
        )
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def is_crossed_by(self, current_timestamp: datetime) -> bool:
        require_aware_datetime(current_timestamp, "current_timestamp")
        return (
            self.boundary_status is TimeBoundaryStatus.PENDING
            and self.boundary_timestamp <= current_timestamp
        )
