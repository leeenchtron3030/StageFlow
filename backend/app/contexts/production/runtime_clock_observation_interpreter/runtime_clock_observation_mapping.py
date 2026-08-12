from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from app.contexts.production.production_event.production_event_type import ProductionEventType
from app.shared.metadata import freeze_metadata


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RuntimeClockObservationMapping:
    """Declarative mapping from runtime clock events to objective observations."""

    production_event_type: ProductionEventType
    observation_note: str
    boundary_lifecycle: str
    requires_clock_metadata: bool = False
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.observation_note.strip():
            raise ValueError("RuntimeClockObservationMapping observation_note is required.")
        if not self.boundary_lifecycle.strip():
            raise ValueError("RuntimeClockObservationMapping boundary_lifecycle is required.")
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))


RUNTIME_CLOCK_OBSERVATION_MAPPINGS: tuple[RuntimeClockObservationMapping, ...] = (
    RuntimeClockObservationMapping(
        production_event_type=ProductionEventType.SCHEDULE_BOUNDARY_REACHED,
        observation_note="Scheduled time boundary was reached.",
        boundary_lifecycle="schedule_boundary_reached",
    ),
    RuntimeClockObservationMapping(
        production_event_type=ProductionEventType.TIMER_ELAPSED,
        observation_note="Timer boundary elapsed.",
        boundary_lifecycle="timer_elapsed",
    ),
    RuntimeClockObservationMapping(
        production_event_type=ProductionEventType.SYSTEM_STATUS_CHANGED,
        observation_note="Runtime clock status changed.",
        boundary_lifecycle="clock_status_changed",
        requires_clock_metadata=True,
    ),
)


def mapping_for_runtime_clock(
    event_type: ProductionEventType,
) -> RuntimeClockObservationMapping | None:
    """Return the objective runtime clock mapping for a generic event type."""

    for mapping in RUNTIME_CLOCK_OBSERVATION_MAPPINGS:
        if mapping.production_event_type is event_type:
            return mapping
    return None
