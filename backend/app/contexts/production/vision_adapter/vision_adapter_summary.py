from __future__ import annotations

from dataclasses import dataclass

from app.contexts.production.vision_adapter.vision_adapter_identity import VisionAdapterKind
from app.contexts.production.vision_adapter.vision_source_adapter import (
    VisionAdapterStatus,
    VisionSourceAdapter,
)
from app.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class VisionAdapterSummary:
    """Lightweight diagnostic summary for a vision source adapter."""

    adapter_id: EntityId
    adapter_name: str
    adapter_kind: VisionAdapterKind
    adapter_status: VisionAdapterStatus
    capability_count: int
    stage_label: str | None = None

    @classmethod
    def from_adapter(cls, adapter: VisionSourceAdapter) -> VisionAdapterSummary:
        return cls(
            adapter_id=adapter.id,
            adapter_name=adapter.identity.adapter_name,
            adapter_kind=adapter.identity.adapter_kind,
            adapter_status=adapter.status,
            capability_count=len(adapter.supported_capabilities),
            stage_label=adapter.identity.stage_label,
        )
