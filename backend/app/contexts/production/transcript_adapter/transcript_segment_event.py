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
from app.contexts.production.transcript_adapter.transcript_artifact_type import (
    TranscriptArtifactType,
)
from app.contexts.production.transcript_adapter.transcript_segment_status import (
    TranscriptSegmentStatus,
)
from app.shared.ids import CorrelationId, EntityId
from app.shared.metadata import freeze_metadata
from app.shared.time import require_aware_datetime


def _empty_metadata() -> Mapping[str, Any]:
    return {}


_EVENT_TYPE_BY_STATUS = {
    TranscriptSegmentStatus.CREATED: ProductionEventType.TRANSCRIPT_SEGMENT_AVAILABLE,
    TranscriptSegmentStatus.UPDATED: ProductionEventType.TRANSCRIPT_SEGMENT_AVAILABLE,
    TranscriptSegmentStatus.FINALIZED: ProductionEventType.TRANSCRIPT_SEGMENT_AVAILABLE,
    TranscriptSegmentStatus.FAILED: ProductionEventType.SYSTEM_STATUS_CHANGED,
    TranscriptSegmentStatus.DELETED: ProductionEventType.SYSTEM_STATUS_CHANGED,
    TranscriptSegmentStatus.UNKNOWN: ProductionEventType.SYSTEM_STATUS_CHANGED,
}


@dataclass(frozen=True, slots=True)
class TranscriptSegmentEvent:
    """Transcript activity before conversion into a Production Event."""

    transcript_segment_identifier: str
    artifact_type: TranscriptArtifactType
    segment_status: TranscriptSegmentStatus
    occurred_at: datetime
    recording_block_id: EntityId | None = None
    stage_id: EntityId | None = None
    timeline_range_reference: str | None = None
    language_label: str | None = None
    text_excerpt: str | None = None
    confidence: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware_datetime(self.occurred_at, "TranscriptSegmentEvent.occurred_at")
        if not self.transcript_segment_identifier.strip():
            raise ValueError(
                "TranscriptSegmentEvent transcript_segment_identifier must not be empty."
            )
        if self.timeline_range_reference is not None and not self.timeline_range_reference.strip():
            raise ValueError("TranscriptSegmentEvent timeline_range_reference must not be empty.")
        if self.language_label is not None and not self.language_label.strip():
            raise ValueError("TranscriptSegmentEvent language_label must not be empty.")
        if self.text_excerpt is not None and not self.text_excerpt.strip():
            raise ValueError("TranscriptSegmentEvent text_excerpt must not be empty.")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("TranscriptSegmentEvent confidence must be between 0.0 and 1.0.")
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def to_production_event(
        self,
        correlation_id: CorrelationId,
        received_at: datetime,
    ) -> ProductionEvent:
        return ProductionEvent(
            id=EntityId.new(),
            event_type=_EVENT_TYPE_BY_STATUS[self.segment_status],
            source=ProductionEventSource.TRANSCRIPT_SYSTEM,
            payload=ProductionEventPayload(self._payload_data()),
            references=self._production_event_references(),
            correlation_id=correlation_id,
            occurred_at=self.occurred_at,
            received_at=require_aware_datetime(received_at, "received_at"),
            metadata={"transcript_adapter_event": True},
            notes=self.language_label,
        )

    def _payload_data(self) -> Mapping[str, Any]:
        data: dict[str, Any] = {
            "transcript_segment_id": self.transcript_segment_identifier,
            "transcript_artifact_type": self.artifact_type.value,
            "transcript_segment_status": self.segment_status.value,
        }
        if self.timeline_range_reference is not None:
            data["timeline_range_reference"] = self.timeline_range_reference
        if self.language_label is not None:
            data["language_label"] = self.language_label
        if self.text_excerpt is not None:
            data["text_excerpt"] = self.text_excerpt
        if self.confidence is not None:
            data["confidence"] = self.confidence
        return data

    def _production_event_references(self) -> tuple[ProductionEventReference, ...]:
        references: list[ProductionEventReference] = [
            ProductionEventReference(
                reference_type=ProductionEventReferenceType.EXTERNAL_OBJECT,
                external_reference=self.transcript_segment_identifier,
                label="transcript segment",
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
