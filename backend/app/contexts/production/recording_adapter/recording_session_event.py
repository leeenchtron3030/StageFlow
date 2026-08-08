from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
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
from app.shared.ids import CorrelationId, EntityId
from app.shared.metadata import freeze_metadata
from app.shared.time import require_aware_datetime


class RecordingSessionEventKind(StrEnum):
    RECORDING_STARTED = "recording_started"
    RECORDING_PAUSED = "recording_paused"
    RECORDING_RESUMED = "recording_resumed"
    RECORDING_STOPPED = "recording_stopped"
    RECORDING_FAILED = "recording_failed"
    RECORDING_STATUS_CHANGED = "recording_status_changed"
    UNKNOWN = "unknown"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


_EVENT_TYPE_BY_KIND = {
    RecordingSessionEventKind.RECORDING_STARTED: ProductionEventType.RECORDING_BLOCK_STARTED,
    RecordingSessionEventKind.RECORDING_STOPPED: ProductionEventType.RECORDING_BLOCK_ENDED,
    RecordingSessionEventKind.RECORDING_PAUSED: ProductionEventType.RECORDING_BLOCK_STATUS_CHANGED,
    RecordingSessionEventKind.RECORDING_RESUMED: ProductionEventType.RECORDING_BLOCK_STATUS_CHANGED,
    RecordingSessionEventKind.RECORDING_STATUS_CHANGED: (
        ProductionEventType.RECORDING_BLOCK_STATUS_CHANGED
    ),
    RecordingSessionEventKind.RECORDING_FAILED: ProductionEventType.SYSTEM_STATUS_CHANGED,
    RecordingSessionEventKind.UNKNOWN: ProductionEventType.SYSTEM_STATUS_CHANGED,
}


@dataclass(frozen=True, slots=True)
class RecordingSessionEvent:
    """Adapter-level recording activity before conversion into a Production Event."""

    recording_system_identifier: str
    event_kind: RecordingSessionEventKind
    occurred_at: datetime
    recording_block_id: EntityId | None = None
    stage_id: EntityId | None = None
    label: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware_datetime(self.occurred_at, "RecordingSessionEvent.occurred_at")
        if not self.recording_system_identifier.strip():
            raise ValueError(
                "RecordingSessionEvent recording_system_identifier must not be empty."
            )
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def to_production_event(
        self,
        correlation_id: CorrelationId,
        received_at: datetime,
    ) -> ProductionEvent:
        return ProductionEvent(
            id=EntityId.new(),
            event_type=_EVENT_TYPE_BY_KIND[self.event_kind],
            source=ProductionEventSource.RECORDING_SYSTEM,
            payload=ProductionEventPayload(self._payload_data()),
            references=self._production_event_references(),
            correlation_id=correlation_id,
            occurred_at=self.occurred_at,
            received_at=require_aware_datetime(received_at, "received_at"),
            metadata={"recording_adapter_event": True},
            notes=self.label,
        )

    def _payload_data(self) -> Mapping[str, Any]:
        data: dict[str, Any] = {
            "recording_system_id": self.recording_system_identifier,
            "recording_event_kind": self.event_kind.value,
        }
        if self.label is not None:
            data["label"] = self.label
        return data

    def _production_event_references(self) -> tuple[ProductionEventReference, ...]:
        references: list[ProductionEventReference] = [
            ProductionEventReference(
                reference_type=ProductionEventReferenceType.SYSTEM,
                external_reference=self.recording_system_identifier,
                label="recording system",
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
        return tuple(references)
