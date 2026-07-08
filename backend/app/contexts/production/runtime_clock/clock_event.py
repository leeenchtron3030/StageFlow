from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from app.contexts.production.production_event.production_event import ProductionEvent
from app.contexts.production.production_event.production_event_payload import (
    ProductionEventPayload,
)
from app.contexts.production.production_event.production_event_reference import (
    ProductionEventReference,
    ProductionEventReferenceType,
)
from app.contexts.production.production_event.production_event_source import (
    ProductionEventSource,
)
from app.contexts.production.production_event.production_event_type import ProductionEventType
from app.contexts.production.runtime_clock.time_boundary_type import TimeBoundaryType
from app.shared.ids import CorrelationId, EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


_EVENT_TYPE_BY_BOUNDARY_TYPE = {
    TimeBoundaryType.SCHEDULED_ACTIVITY_START: ProductionEventType.SCHEDULE_BOUNDARY_REACHED,
    TimeBoundaryType.SCHEDULED_ACTIVITY_END: ProductionEventType.SCHEDULE_BOUNDARY_REACHED,
    TimeBoundaryType.RECORDING_EXPECTED_START: ProductionEventType.SCHEDULE_BOUNDARY_REACHED,
    TimeBoundaryType.RECORDING_EXPECTED_END: ProductionEventType.SCHEDULE_BOUNDARY_REACHED,
    TimeBoundaryType.TIMEOUT: ProductionEventType.TIMER_ELAPSED,
    TimeBoundaryType.HEARTBEAT_DUE: ProductionEventType.TIMER_ELAPSED,
    TimeBoundaryType.RETRY_DUE: ProductionEventType.TIMER_ELAPSED,
    TimeBoundaryType.MANUAL_DEADLINE: ProductionEventType.TIMER_ELAPSED,
    TimeBoundaryType.CUSTOM: ProductionEventType.TIMER_ELAPSED,
    TimeBoundaryType.UNKNOWN: ProductionEventType.SYSTEM_STATUS_CHANGED,
}


@dataclass(frozen=True, slots=True)
class ClockEvent:
    """Clock-level event before conversion into a Production Event."""

    clock_id: EntityId
    time_boundary_id: EntityId
    boundary_type: TimeBoundaryType
    occurred_at: datetime
    stage_id: EntityId | None = None
    recording_block_id: EntityId | None = None
    scheduled_activity_id: EntityId | None = None
    label: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_production_event(
        self,
        correlation_id: CorrelationId,
        received_at: datetime | None = None,
    ) -> ProductionEvent:
        event_timestamp = received_at or datetime.now(UTC)
        return ProductionEvent(
            id=EntityId.new(),
            event_type=_EVENT_TYPE_BY_BOUNDARY_TYPE[self.boundary_type],
            source=ProductionEventSource.TIMER,
            payload=ProductionEventPayload(self._payload_data()),
            references=self._production_event_references(),
            correlation_id=correlation_id,
            occurred_at=self.occurred_at,
            received_at=event_timestamp,
            metadata={"runtime_clock_event": True},
            notes=self.label,
        )

    def _payload_data(self) -> Mapping[str, Any]:
        data: dict[str, Any] = {
            "clock_id": self.clock_id.to_json(),
            "time_boundary_id": self.time_boundary_id.to_json(),
            "boundary_type": self.boundary_type.value,
            "boundary_crossed_at": self.occurred_at.isoformat(),
        }
        if self.label is not None:
            data["label"] = self.label
        return data

    def _production_event_references(self) -> tuple[ProductionEventReference, ...]:
        references: list[ProductionEventReference] = [
            ProductionEventReference(
                reference_type=ProductionEventReferenceType.SYSTEM,
                referenced_id=self.clock_id,
                label="runtime clock",
            ),
            ProductionEventReference(
                reference_type=ProductionEventReferenceType.EXTERNAL_OBJECT,
                external_reference=self.time_boundary_id.to_json(),
                label="time boundary",
            ),
        ]
        if self.recording_block_id is not None:
            references.append(
                ProductionEventReference(
                    reference_type=ProductionEventReferenceType.RECORDING_BLOCK,
                    referenced_id=self.recording_block_id,
                    label="recording block",
                )
            )
        if self.stage_id is not None:
            references.append(
                ProductionEventReference(
                    reference_type=ProductionEventReferenceType.STAGE,
                    referenced_id=self.stage_id,
                    label="stage",
                )
            )
        if self.scheduled_activity_id is not None:
            references.append(
                ProductionEventReference(
                    reference_type=ProductionEventReferenceType.SCHEDULE_ARTIFACT,
                    referenced_id=self.scheduled_activity_id,
                    label="scheduled activity",
                )
            )
        return tuple(references)
