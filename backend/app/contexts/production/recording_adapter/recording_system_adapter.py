from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from app.contexts.production.production_event.production_event import ProductionEvent
from app.contexts.production.recording_adapter.recording_adapter_capability import (
    RecordingAdapterCapability,
)
from app.contexts.production.recording_adapter.recording_adapter_identity import (
    RecordingAdapterIdentity,
)
from app.contexts.production.recording_adapter.recording_session_event import (
    RecordingSessionEvent,
)
from app.contexts.production.recording_adapter.recording_system_status import (
    RecordingSystemStatus,
)
from app.shared.ids import CorrelationId, EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RecordingSystemAdapter:
    """Generic adapter contract for reporting recording system activity."""

    id: EntityId
    identity: RecordingAdapterIdentity
    status: RecordingSystemStatus
    supported_capabilities: Sequence[RecordingAdapterCapability]
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "supported_capabilities", tuple(self.supported_capabilities))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def supports_capability(self, capability: RecordingAdapterCapability) -> bool:
        return capability in self.supported_capabilities

    def production_event_from_session_event(
        self,
        session_event: RecordingSessionEvent,
        correlation_id: CorrelationId,
        received_at: datetime | None = None,
    ) -> ProductionEvent:
        return session_event.to_production_event(
            correlation_id=correlation_id,
            received_at=received_at,
        )
