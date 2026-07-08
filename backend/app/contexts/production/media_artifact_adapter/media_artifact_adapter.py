from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from app.contexts.production.media_artifact_adapter.media_artifact_capability import (
    MediaArtifactCapability,
)
from app.contexts.production.media_artifact_adapter.media_artifact_event import (
    MediaArtifactEvent,
)
from app.contexts.production.media_artifact_adapter.media_artifact_identity import (
    MediaArtifactIdentity,
)
from app.contexts.production.media_artifact_adapter.media_artifact_status import (
    MediaArtifactStatus,
)
from app.contexts.production.production_event.production_event import ProductionEvent
from app.shared.ids import CorrelationId, EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class MediaArtifactAdapter:
    """Generic adapter contract for reporting media artifact activity."""

    id: EntityId
    identity: MediaArtifactIdentity
    status: MediaArtifactStatus
    supported_capabilities: Sequence[MediaArtifactCapability]
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "supported_capabilities", tuple(self.supported_capabilities))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def supports_capability(self, capability: MediaArtifactCapability) -> bool:
        return capability in self.supported_capabilities

    def production_event_from_artifact_event(
        self,
        artifact_event: MediaArtifactEvent,
        correlation_id: CorrelationId,
        received_at: datetime | None = None,
    ) -> ProductionEvent:
        return artifact_event.to_production_event(
            correlation_id=correlation_id,
            received_at=received_at,
        )
