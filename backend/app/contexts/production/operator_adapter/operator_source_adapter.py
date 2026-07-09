from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from app.contexts.production.operator_adapter.operator_adapter_capability import (
    OperatorAdapterCapability,
)
from app.contexts.production.operator_adapter.operator_adapter_identity import (
    OperatorAdapterIdentity,
)
from app.contexts.production.operator_adapter.operator_event import OperatorEvent
from app.contexts.production.production_event.production_event import ProductionEvent
from app.shared.ids import CorrelationId, EntityId


class OperatorAdapterStatus(StrEnum):
    UNKNOWN = "unknown"
    CONFIGURED = "configured"
    READY = "ready"
    DEGRADED = "degraded"
    FAILED = "failed"
    ARCHIVED = "archived"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class OperatorSourceAdapter:
    """Generic adapter contract for reporting intentional operator input."""

    id: EntityId
    identity: OperatorAdapterIdentity
    status: OperatorAdapterStatus
    supported_capabilities: Sequence[OperatorAdapterCapability]
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "supported_capabilities", tuple(self.supported_capabilities))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def supports_capability(self, capability: OperatorAdapterCapability) -> bool:
        return capability in self.supported_capabilities

    def production_event_from_operator_event(
        self,
        operator_event: OperatorEvent,
        correlation_id: CorrelationId,
        received_at: datetime | None = None,
    ) -> ProductionEvent:
        return operator_event.to_production_event(
            correlation_id=correlation_id,
            received_at=received_at,
        )
