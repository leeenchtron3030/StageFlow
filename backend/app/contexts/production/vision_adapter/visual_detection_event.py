from __future__ import annotations

from collections.abc import Mapping
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
from app.contexts.production.vision_adapter.visual_detection_status import (
    VisualDetectionStatus,
)
from app.contexts.production.vision_adapter.visual_detection_type import VisualDetectionType
from app.shared.ids import CorrelationId, EntityId
from app.shared.metadata import freeze_metadata
from app.shared.time import require_aware_datetime


def _empty_metadata() -> Mapping[str, Any]:
    return {}


_EVENT_TYPE_BY_STATUS = {
    VisualDetectionStatus.CREATED: ProductionEventType.VISUAL_DETECTION_AVAILABLE,
    VisualDetectionStatus.UPDATED: ProductionEventType.VISUAL_DETECTION_AVAILABLE,
    VisualDetectionStatus.FINALIZED: ProductionEventType.VISUAL_DETECTION_AVAILABLE,
    VisualDetectionStatus.FAILED: ProductionEventType.SYSTEM_STATUS_CHANGED,
    VisualDetectionStatus.DELETED: ProductionEventType.SYSTEM_STATUS_CHANGED,
    VisualDetectionStatus.UNKNOWN: ProductionEventType.SYSTEM_STATUS_CHANGED,
}


@dataclass(frozen=True, slots=True)
class VisualDetectionEvent:
    """Visual activity before conversion into a Production Event."""

    detection_identifier: str
    detection_type: VisualDetectionType
    detection_status: VisualDetectionStatus
    occurred_at: datetime
    recording_block_id: EntityId | None = None
    stage_id: EntityId | None = None
    timeline_range_reference: str | None = None
    confidence: float | None = None
    region_reference: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware_datetime(self.occurred_at, "VisualDetectionEvent.occurred_at")
        if not self.detection_identifier.strip():
            raise ValueError("VisualDetectionEvent detection_identifier must not be empty.")
        if self.timeline_range_reference is not None and not self.timeline_range_reference.strip():
            raise ValueError("VisualDetectionEvent timeline_range_reference must not be empty.")
        if self.region_reference is not None and not self.region_reference.strip():
            raise ValueError("VisualDetectionEvent region_reference must not be empty.")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("VisualDetectionEvent confidence must be between 0.0 and 1.0.")
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def to_production_event(
        self,
        correlation_id: CorrelationId,
        received_at: datetime,
    ) -> ProductionEvent:
        return ProductionEvent(
            id=EntityId.new(),
            event_type=_EVENT_TYPE_BY_STATUS[self.detection_status],
            source=ProductionEventSource.VISION_SYSTEM,
            payload=ProductionEventPayload(self._payload_data()),
            references=self._production_event_references(),
            correlation_id=correlation_id,
            occurred_at=self.occurred_at,
            received_at=require_aware_datetime(received_at, "received_at"),
            metadata={"vision_adapter_event": True},
            notes=self.region_reference,
        )

    def _payload_data(self) -> Mapping[str, Any]:
        data: dict[str, Any] = {
            "visual_detection_id": self.detection_identifier,
            "visual_detection_type": self.detection_type.value,
            "visual_detection_status": self.detection_status.value,
        }
        if self.timeline_range_reference is not None:
            data["timeline_range_reference"] = self.timeline_range_reference
        if self.confidence is not None:
            data["confidence"] = self.confidence
        if self.region_reference is not None:
            data["region_reference"] = self.region_reference
        return data

    def _production_event_references(self) -> tuple[ProductionEventReference, ...]:
        references: list[ProductionEventReference] = [
            ProductionEventReference(
                reference_type=ProductionEventReferenceType.EXTERNAL_OBJECT,
                external_reference=self.detection_identifier,
                label="visual detection",
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
