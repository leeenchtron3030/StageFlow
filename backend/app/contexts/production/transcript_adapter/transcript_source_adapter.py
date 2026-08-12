from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.contexts.production.production_event.production_event import ProductionEvent
from app.contexts.production.transcript_adapter.transcript_adapter_capability import (
    TranscriptAdapterCapability,
)
from app.contexts.production.transcript_adapter.transcript_adapter_identity import (
    TranscriptAdapterIdentity,
)
from app.contexts.production.transcript_adapter.transcript_segment_event import (
    TranscriptSegmentEvent,
)
from app.shared.ids import CorrelationId, EntityId
from app.shared.metadata import freeze_metadata


class TranscriptAdapterStatus(StrEnum):
    UNKNOWN = "unknown"
    CONFIGURED = "configured"
    READY = "ready"
    DEGRADED = "degraded"
    FAILED = "failed"
    ARCHIVED = "archived"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class TranscriptSourceAdapter:
    """Generic adapter contract for reporting transcript activity."""

    id: EntityId
    identity: TranscriptAdapterIdentity
    status: TranscriptAdapterStatus
    supported_capabilities: Sequence[TranscriptAdapterCapability]
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "supported_capabilities", tuple(self.supported_capabilities))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def supports_capability(self, capability: TranscriptAdapterCapability) -> bool:
        return capability in self.supported_capabilities

    def production_event_from_segment_event(
        self,
        segment_event: TranscriptSegmentEvent,
        correlation_id: CorrelationId,
        received_at: datetime,
    ) -> ProductionEvent:
        return segment_event.to_production_event(
            correlation_id=correlation_id,
            received_at=received_at,
        )
