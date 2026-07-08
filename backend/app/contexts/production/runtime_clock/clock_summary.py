from __future__ import annotations

from dataclasses import dataclass

from app.contexts.production.runtime_clock.runtime_clock import (
    RuntimeClock,
    RuntimeClockStatus,
)
from app.contexts.production.runtime_clock.time_boundary_status import TimeBoundaryStatus
from app.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class ClockSummary:
    """Lightweight diagnostics for a runtime clock."""

    clock_id: EntityId
    clock_name: str
    clock_status: RuntimeClockStatus
    capability_count: int
    pending_boundary_count: int | None = None
    crossed_boundary_count: int | None = None

    @classmethod
    def from_clock(cls, clock: RuntimeClock) -> ClockSummary:
        return cls(
            clock_id=clock.id,
            clock_name=clock.clock_name,
            clock_status=clock.clock_status,
            capability_count=len(clock.supported_capabilities),
            pending_boundary_count=sum(
                1
                for boundary in clock.time_boundaries
                if boundary.boundary_status is TimeBoundaryStatus.PENDING
            ),
            crossed_boundary_count=sum(
                1
                for boundary in clock.time_boundaries
                if boundary.boundary_status is TimeBoundaryStatus.CROSSED
            ),
        )
