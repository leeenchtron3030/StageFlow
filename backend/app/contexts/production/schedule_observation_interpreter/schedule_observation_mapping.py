from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.contexts.production.production_event.production_event_type import ProductionEventType


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class ScheduleObservationMapping:
    """Declarative mapping from schedule events to objective observations."""

    production_event_type: ProductionEventType
    observation_note: str
    schedule_lifecycle: str
    activity_status: str | None = None
    requires_schedule_metadata: bool = False
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.observation_note.strip():
            raise ValueError("ScheduleObservationMapping observation_note is required.")
        if not self.schedule_lifecycle.strip():
            raise ValueError("ScheduleObservationMapping schedule_lifecycle is required.")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


SCHEDULE_OBSERVATION_MAPPINGS: tuple[ScheduleObservationMapping, ...] = (
    ScheduleObservationMapping(
        production_event_type=ProductionEventType.SCHEDULE_ARTIFACT_UPDATED,
        observation_note="Scheduled activity was cancelled.",
        schedule_lifecycle="cancelled",
        activity_status="cancelled",
    ),
    ScheduleObservationMapping(
        production_event_type=ProductionEventType.SCHEDULE_ARTIFACT_UPDATED,
        observation_note="Scheduled activity was updated.",
        schedule_lifecycle="updated",
    ),
    ScheduleObservationMapping(
        production_event_type=ProductionEventType.SCHEDULE_BOUNDARY_REACHED,
        observation_note="Scheduled activity entered its planned time window.",
        schedule_lifecycle="planned_time_window_entered",
    ),
    ScheduleObservationMapping(
        production_event_type=ProductionEventType.SYSTEM_STATUS_CHANGED,
        observation_note="Schedule source status changed.",
        schedule_lifecycle="schedule_source_status_changed",
        requires_schedule_metadata=True,
    ),
)


def mapping_for_schedule(
    event_type: ProductionEventType,
    activity_status: str | None = None,
) -> ScheduleObservationMapping | None:
    """Return the objective schedule mapping for a generic event payload."""

    if event_type is ProductionEventType.SCHEDULE_ARTIFACT_UPDATED:
        for mapping in SCHEDULE_OBSERVATION_MAPPINGS:
            if (
                mapping.production_event_type is event_type
                and mapping.activity_status == activity_status
            ):
                return mapping
        for mapping in SCHEDULE_OBSERVATION_MAPPINGS:
            if mapping.production_event_type is event_type and mapping.activity_status is None:
                return mapping
        return None

    for mapping in SCHEDULE_OBSERVATION_MAPPINGS:
        if mapping.production_event_type is event_type:
            return mapping
    return None
