from __future__ import annotations

from dataclasses import dataclass

from app.contexts.production.media_artifact_adapter.media_artifact_adapter import (
    MediaArtifactAdapter,
)
from app.contexts.production.media_artifact_adapter.media_artifact_identity import (
    MediaArtifactAdapterKind,
)
from app.contexts.production.media_artifact_adapter.media_artifact_status import (
    MediaArtifactStatus,
)
from app.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class MediaArtifactSummary:
    """Lightweight diagnostic summary for a media artifact adapter."""

    adapter_id: EntityId
    adapter_name: str
    adapter_kind: MediaArtifactAdapterKind
    adapter_status: MediaArtifactStatus
    capability_count: int
    stage_label: str | None = None
    location_label: str | None = None

    @classmethod
    def from_adapter(cls, adapter: MediaArtifactAdapter) -> MediaArtifactSummary:
        return cls(
            adapter_id=adapter.id,
            adapter_name=adapter.identity.adapter_name,
            adapter_kind=adapter.identity.adapter_kind,
            adapter_status=adapter.status,
            capability_count=len(adapter.supported_capabilities),
            stage_label=adapter.identity.stage_label,
            location_label=adapter.identity.location_label,
        )
