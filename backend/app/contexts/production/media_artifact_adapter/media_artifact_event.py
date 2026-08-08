from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.contexts.production.media_artifact_adapter.media_artifact_status import (
    MediaArtifactStatus,
)
from app.contexts.production.media_artifact_adapter.media_artifact_type import (
    MediaArtifactType,
)
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


def _empty_metadata() -> Mapping[str, Any]:
    return {}


_EVENT_TYPE_BY_STATUS = {
    MediaArtifactStatus.CREATED: ProductionEventType.MEDIA_FILE_CREATED,
    MediaArtifactStatus.FINALIZED: ProductionEventType.MEDIA_FILE_FINALIZED,
    MediaArtifactStatus.FAILED: ProductionEventType.MEDIA_FILE_FAILED,
    MediaArtifactStatus.UPDATING: ProductionEventType.SYSTEM_STATUS_CHANGED,
    MediaArtifactStatus.DELETED: ProductionEventType.SYSTEM_STATUS_CHANGED,
    MediaArtifactStatus.UNKNOWN: ProductionEventType.SYSTEM_STATUS_CHANGED,
}


@dataclass(frozen=True, slots=True)
class MediaArtifactEvent:
    """Adapter-level media artifact activity before conversion into a Production Event."""

    artifact_identifier: str
    artifact_type: MediaArtifactType
    artifact_status: MediaArtifactStatus
    occurred_at: datetime
    recording_block_id: EntityId | None = None
    stage_id: EntityId | None = None
    artifact_label: str | None = None
    artifact_uri: str | None = None
    size_bytes: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware_datetime(self.occurred_at, "MediaArtifactEvent.occurred_at")
        if not self.artifact_identifier.strip():
            raise ValueError("MediaArtifactEvent artifact_identifier must not be empty.")
        if self.artifact_uri is not None and not self.artifact_uri.strip():
            raise ValueError("MediaArtifactEvent artifact_uri must not be empty.")
        if self.size_bytes is not None and self.size_bytes < 0:
            raise ValueError("MediaArtifactEvent size_bytes must not be negative.")
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def to_production_event(
        self,
        correlation_id: CorrelationId,
        received_at: datetime,
    ) -> ProductionEvent:
        return ProductionEvent(
            id=EntityId.new(),
            event_type=_EVENT_TYPE_BY_STATUS[self.artifact_status],
            source=ProductionEventSource.INTERNAL_SYSTEM,
            payload=ProductionEventPayload(self._payload_data()),
            references=self._production_event_references(),
            correlation_id=correlation_id,
            occurred_at=self.occurred_at,
            received_at=require_aware_datetime(received_at, "received_at"),
            metadata={"media_artifact_adapter_event": True},
            notes=self.artifact_label,
        )

    def _payload_data(self) -> Mapping[str, Any]:
        data: dict[str, Any] = {
            "artifact_id": self.artifact_identifier,
            "artifact_type": self.artifact_type.value,
            "artifact_status": self.artifact_status.value,
        }
        if self.artifact_label is not None:
            data["artifact_label"] = self.artifact_label
        if self.artifact_uri is not None:
            data["artifact_uri"] = self.artifact_uri
        if self.size_bytes is not None:
            data["size_bytes"] = self.size_bytes
        return data

    def _production_event_references(self) -> tuple[ProductionEventReference, ...]:
        references: list[ProductionEventReference] = [
            ProductionEventReference(
                reference_type=ProductionEventReferenceType.MEDIA_FILE,
                external_reference=self.artifact_identifier,
                label="media artifact",
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
