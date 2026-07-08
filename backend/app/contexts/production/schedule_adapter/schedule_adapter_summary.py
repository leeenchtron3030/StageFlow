from __future__ import annotations

from dataclasses import dataclass

from app.contexts.production.schedule_adapter.schedule_source_adapter import (
    ScheduleAdapterStatus,
    ScheduleSourceAdapter,
)
from app.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class ScheduleAdapterSummary:
    """Lightweight diagnostic summary for a schedule source adapter."""

    adapter_id: EntityId
    adapter_name: str
    capability_count: int
    activity_count: int
    adapter_status: ScheduleAdapterStatus

    @classmethod
    def from_adapter(cls, adapter: ScheduleSourceAdapter) -> ScheduleAdapterSummary:
        return cls(
            adapter_id=adapter.id,
            adapter_name=adapter.adapter_name,
            capability_count=len(adapter.supported_capabilities),
            activity_count=len(adapter.scheduled_activities),
            adapter_status=adapter.status,
        )
