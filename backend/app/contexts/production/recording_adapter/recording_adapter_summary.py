from __future__ import annotations

from dataclasses import dataclass

from app.contexts.production.recording_adapter.recording_adapter_identity import (
    RecordingAdapterKind,
)
from app.contexts.production.recording_adapter.recording_system_adapter import (
    RecordingSystemAdapter,
)
from app.contexts.production.recording_adapter.recording_system_status import (
    RecordingSystemStatus,
)
from app.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class RecordingAdapterSummary:
    """Lightweight diagnostic summary for a recording system adapter."""

    adapter_id: EntityId
    adapter_name: str
    adapter_kind: RecordingAdapterKind
    status: RecordingSystemStatus
    capability_count: int
    stage_label: str | None = None
    location_label: str | None = None

    @classmethod
    def from_adapter(cls, adapter: RecordingSystemAdapter) -> RecordingAdapterSummary:
        return cls(
            adapter_id=adapter.id,
            adapter_name=adapter.identity.adapter_name,
            adapter_kind=adapter.identity.adapter_kind,
            status=adapter.status,
            capability_count=len(adapter.supported_capabilities),
            stage_label=adapter.identity.stage_label,
            location_label=adapter.identity.location_label,
        )
