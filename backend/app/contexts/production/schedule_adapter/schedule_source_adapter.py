from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from app.contexts.production.production_event.production_event import ProductionEvent
from app.contexts.production.schedule_adapter.schedule_adapter_capability import (
    ScheduleAdapterCapability,
)
from app.contexts.production.schedule_adapter.scheduled_activity import ScheduledActivity
from app.shared.ids import CorrelationId, EntityId


class ScheduleAdapterStatus(StrEnum):
    UNKNOWN = "unknown"
    CONFIGURED = "configured"
    READY = "ready"
    DEGRADED = "degraded"
    FAILED = "failed"
    ARCHIVED = "archived"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class ScheduleSourceAdapter:
    """Generic source adapter for planned activities."""

    id: EntityId
    adapter_name: str
    status: ScheduleAdapterStatus
    supported_capabilities: Sequence[ScheduleAdapterCapability]
    scheduled_activities: Sequence[ScheduledActivity] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.adapter_name.strip():
            raise ValueError("ScheduleSourceAdapter adapter_name must not be empty.")
        object.__setattr__(self, "supported_capabilities", tuple(self.supported_capabilities))
        object.__setattr__(self, "scheduled_activities", tuple(self.scheduled_activities))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def supports_capability(self, capability: ScheduleAdapterCapability) -> bool:
        return capability in self.supported_capabilities

    def production_event_from_activity(
        self,
        activity: ScheduledActivity,
        correlation_id: CorrelationId,
        received_at: datetime | None = None,
    ) -> ProductionEvent:
        return activity.to_production_event(
            correlation_id=correlation_id,
            received_at=received_at,
        )
