from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
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
from app.contexts.production.schedule_adapter.scheduled_activity_identity import (
    ScheduledActivityIdentity,
)
from app.contexts.production.schedule_adapter.scheduled_activity_status import (
    ScheduledActivityStatus,
)
from app.contexts.production.schedule_adapter.scheduled_activity_type import (
    ScheduledActivityType,
)
from app.shared.ids import CorrelationId, EntityId
from app.shared.metadata import freeze_metadata
from app.shared.time import require_aware_datetime


def _empty_metadata() -> Mapping[str, Any]:
    return {}


_EVENT_TYPE_BY_STATUS = {
    ScheduledActivityStatus.SCHEDULED: ProductionEventType.SCHEDULE_ARTIFACT_UPDATED,
    ScheduledActivityStatus.UPDATED: ProductionEventType.SCHEDULE_ARTIFACT_UPDATED,
    ScheduledActivityStatus.CANCELLED: ProductionEventType.SCHEDULE_ARTIFACT_UPDATED,
    ScheduledActivityStatus.COMPLETED: ProductionEventType.SCHEDULE_ARTIFACT_UPDATED,
    ScheduledActivityStatus.UNKNOWN: ProductionEventType.SYSTEM_STATUS_CHANGED,
}


@dataclass(frozen=True, slots=True)
class ScheduledActivity:
    """Planned activity information from a schedule source."""

    id: EntityId
    identity: ScheduledActivityIdentity
    activity_type: ScheduledActivityType
    activity_status: ScheduledActivityStatus
    planned_start_at: datetime
    planned_end_at: datetime
    stage_reference: str | None = None
    participant_labels: Sequence[str] = field(default_factory=tuple)
    external_reference: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware_datetime(self.planned_start_at, "ScheduledActivity.planned_start_at")
        require_aware_datetime(self.planned_end_at, "ScheduledActivity.planned_end_at")
        if self.planned_end_at <= self.planned_start_at:
            raise ValueError("ScheduledActivity planned_end_at must be after planned_start_at.")
        if self.stage_reference is not None and not self.stage_reference.strip():
            raise ValueError("ScheduledActivity stage_reference must not be empty.")
        if self.external_reference is not None and not self.external_reference.strip():
            raise ValueError("ScheduledActivity external_reference must not be empty.")
        object.__setattr__(self, "participant_labels", tuple(self.participant_labels))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    @property
    def activity_title(self) -> str:
        return self.identity.activity_title

    def to_production_event(
        self,
        correlation_id: CorrelationId,
        occurred_at: datetime,
        received_at: datetime,
    ) -> ProductionEvent:
        occurred_at = require_aware_datetime(occurred_at, "occurred_at")
        received_at = require_aware_datetime(received_at, "received_at")
        return ProductionEvent(
            id=EntityId.new(),
            event_type=_EVENT_TYPE_BY_STATUS[self.activity_status],
            source=ProductionEventSource.SCHEDULE_SYSTEM,
            payload=ProductionEventPayload(self._payload_data()),
            references=self._production_event_references(),
            correlation_id=correlation_id,
            occurred_at=occurred_at,
            received_at=received_at,
            metadata={"schedule_adapter_event": True},
            notes=self.identity.activity_title,
        )

    def _payload_data(self) -> Mapping[str, Any]:
        data: dict[str, Any] = {
            "scheduled_activity_id": self.id.to_json(),
            "activity_title": self.identity.activity_title,
            "activity_type": self.activity_type.value,
            "activity_status": self.activity_status.value,
            "planned_start_at": self.planned_start_at.isoformat(),
            "planned_end_at": self.planned_end_at.isoformat(),
        }
        if self.identity.subtitle is not None:
            data["subtitle"] = self.identity.subtitle
        if self.stage_reference is not None:
            data["stage_reference"] = self.stage_reference
        if self.participant_labels:
            data["participant_labels"] = tuple(self.participant_labels)
        if self.external_reference is not None:
            data["external_reference"] = self.external_reference
        return data

    def _production_event_references(self) -> tuple[ProductionEventReference, ...]:
        references: list[ProductionEventReference] = [
            ProductionEventReference(
                reference_type=ProductionEventReferenceType.SCHEDULE_ARTIFACT,
                referenced_id=self.id,
                label="scheduled activity",
            )
        ]
        if self.external_reference is not None:
            references.append(
                ProductionEventReference(
                    reference_type=ProductionEventReferenceType.EXTERNAL_OBJECT,
                    external_reference=self.external_reference,
                    label="external schedule reference",
                )
            )
        return tuple(references)
