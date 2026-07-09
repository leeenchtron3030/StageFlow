from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from app.contexts.production.operator_adapter.operator_event_status import OperatorEventStatus
from app.contexts.production.operator_adapter.operator_event_type import OperatorEventType
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
from app.shared.ids import CorrelationId, EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


_EVENT_TYPE_BY_STATUS = {
    OperatorEventStatus.CREATED: ProductionEventType.OPERATOR_INPUT_RECEIVED,
    OperatorEventStatus.UPDATED: ProductionEventType.OPERATOR_INPUT_RECEIVED,
    OperatorEventStatus.REMOVED: ProductionEventType.OPERATOR_INPUT_RECEIVED,
    OperatorEventStatus.CANCELLED: ProductionEventType.SYSTEM_STATUS_CHANGED,
    OperatorEventStatus.UNKNOWN: ProductionEventType.SYSTEM_STATUS_CHANGED,
}


@dataclass(frozen=True, slots=True)
class OperatorEvent:
    """Intentional operator-supplied information before conversion into a Production Event."""

    operator_event_identifier: str
    event_type: OperatorEventType
    event_status: OperatorEventStatus
    occurred_at: datetime
    recording_block_id: EntityId | None = None
    stage_id: EntityId | None = None
    timeline_range_reference: str | None = None
    label: str | None = None
    note: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.operator_event_identifier.strip():
            raise ValueError("OperatorEvent operator_event_identifier must not be empty.")
        if self.timeline_range_reference is not None and not self.timeline_range_reference.strip():
            raise ValueError("OperatorEvent timeline_range_reference must not be empty.")
        if self.label is not None and not self.label.strip():
            raise ValueError("OperatorEvent label must not be empty.")
        if self.note is not None and not self.note.strip():
            raise ValueError("OperatorEvent note must not be empty.")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_production_event(
        self,
        correlation_id: CorrelationId,
        received_at: datetime | None = None,
    ) -> ProductionEvent:
        return ProductionEvent(
            id=EntityId.new(),
            event_type=_EVENT_TYPE_BY_STATUS[self.event_status],
            source=ProductionEventSource.OPERATOR,
            payload=ProductionEventPayload(self._payload_data()),
            references=self._production_event_references(),
            correlation_id=correlation_id,
            occurred_at=self.occurred_at,
            received_at=received_at or datetime.now(UTC),
            metadata={"operator_adapter_event": True},
            notes=self.note,
        )

    def _payload_data(self) -> Mapping[str, Any]:
        data: dict[str, Any] = {
            "operator_event_id": self.operator_event_identifier,
            "operator_event_type": self.event_type.value,
            "operator_event_status": self.event_status.value,
        }
        if self.timeline_range_reference is not None:
            data["timeline_range_reference"] = self.timeline_range_reference
        if self.label is not None:
            data["label"] = self.label
        if self.note is not None:
            data["note"] = self.note
        return data

    def _production_event_references(self) -> tuple[ProductionEventReference, ...]:
        references: list[ProductionEventReference] = [
            ProductionEventReference(
                reference_type=ProductionEventReferenceType.EXTERNAL_OBJECT,
                external_reference=self.operator_event_identifier,
                label="operator event",
            )
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
        if self.timeline_range_reference is not None:
            references.append(
                ProductionEventReference(
                    reference_type=ProductionEventReferenceType.TIMELINE_RANGE,
                    external_reference=self.timeline_range_reference,
                    label="timeline range",
                )
            )
        return tuple(references)
