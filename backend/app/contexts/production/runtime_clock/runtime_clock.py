from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from app.contexts.production.production_event.production_event import ProductionEvent
from app.contexts.production.runtime_clock.clock_capability import ClockCapability
from app.contexts.production.runtime_clock.clock_event import ClockEvent
from app.contexts.production.runtime_clock.time_boundary import TimeBoundary
from app.shared.ids import CorrelationId, EntityId


class RuntimeClockStatus(StrEnum):
    UNKNOWN = "unknown"
    CONFIGURED = "configured"
    READY = "ready"
    DEGRADED = "degraded"
    DISABLED = "disabled"
    ARCHIVED = "archived"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RuntimeClock:
    """Generic clock contract that reports crossed time boundaries."""

    id: EntityId
    clock_name: str
    supported_capabilities: Sequence[ClockCapability]
    clock_status: RuntimeClockStatus
    time_boundaries: Sequence[TimeBoundary] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.clock_name.strip():
            raise ValueError("RuntimeClock clock_name must not be empty.")
        object.__setattr__(self, "supported_capabilities", tuple(self.supported_capabilities))
        object.__setattr__(self, "time_boundaries", tuple(self.time_boundaries))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def supports_capability(self, capability: ClockCapability) -> bool:
        return capability in self.supported_capabilities

    def evaluate_boundaries(
        self,
        current_timestamp: datetime,
        boundaries: Sequence[TimeBoundary] | None = None,
    ) -> tuple[TimeBoundary, ...]:
        evaluated_boundaries = self.time_boundaries if boundaries is None else boundaries
        return tuple(
            boundary
            for boundary in evaluated_boundaries
            if boundary.is_crossed_by(current_timestamp)
        )

    def clock_event_from_boundary(
        self,
        boundary: TimeBoundary,
        occurred_at: datetime,
    ) -> ClockEvent:
        return ClockEvent(
            clock_id=self.id,
            time_boundary_id=boundary.id,
            boundary_type=boundary.boundary_type,
            occurred_at=occurred_at,
            stage_id=boundary.stage_id,
            recording_block_id=boundary.recording_block_id,
            scheduled_activity_id=boundary.scheduled_activity_id,
            label=boundary.label,
        )

    def production_event_from_clock_event(
        self,
        clock_event: ClockEvent,
        correlation_id: CorrelationId,
        received_at: datetime | None = None,
    ) -> ProductionEvent:
        return clock_event.to_production_event(
            correlation_id=correlation_id,
            received_at=received_at,
        )
