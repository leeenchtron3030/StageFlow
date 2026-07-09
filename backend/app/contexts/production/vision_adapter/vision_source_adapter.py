from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from app.contexts.production.production_event.production_event import ProductionEvent
from app.contexts.production.vision_adapter.vision_adapter_capability import (
    VisionAdapterCapability,
)
from app.contexts.production.vision_adapter.vision_adapter_identity import (
    VisionAdapterIdentity,
)
from app.contexts.production.vision_adapter.visual_detection_event import VisualDetectionEvent
from app.shared.ids import CorrelationId, EntityId


class VisionAdapterStatus(StrEnum):
    UNKNOWN = "unknown"
    CONFIGURED = "configured"
    READY = "ready"
    DEGRADED = "degraded"
    FAILED = "failed"
    ARCHIVED = "archived"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class VisionSourceAdapter:
    """Generic adapter contract for reporting visual detection activity."""

    id: EntityId
    identity: VisionAdapterIdentity
    status: VisionAdapterStatus
    supported_capabilities: Sequence[VisionAdapterCapability]
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "supported_capabilities", tuple(self.supported_capabilities))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def supports_capability(self, capability: VisionAdapterCapability) -> bool:
        return capability in self.supported_capabilities

    def production_event_from_detection_event(
        self,
        detection_event: VisualDetectionEvent,
        correlation_id: CorrelationId,
        received_at: datetime | None = None,
    ) -> ProductionEvent:
        return detection_event.to_production_event(
            correlation_id=correlation_id,
            received_at=received_at,
        )
