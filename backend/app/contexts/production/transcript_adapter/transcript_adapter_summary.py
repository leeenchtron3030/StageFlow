from __future__ import annotations

from dataclasses import dataclass

from app.contexts.production.transcript_adapter.transcript_adapter_identity import (
    TranscriptAdapterKind,
)
from app.contexts.production.transcript_adapter.transcript_source_adapter import (
    TranscriptAdapterStatus,
    TranscriptSourceAdapter,
)
from app.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class TranscriptAdapterSummary:
    """Lightweight diagnostic summary for a transcript source adapter."""

    adapter_id: EntityId
    adapter_name: str
    adapter_kind: TranscriptAdapterKind
    adapter_status: TranscriptAdapterStatus
    capability_count: int
    stage_label: str | None = None
    language_label: str | None = None

    @classmethod
    def from_adapter(cls, adapter: TranscriptSourceAdapter) -> TranscriptAdapterSummary:
        return cls(
            adapter_id=adapter.id,
            adapter_name=adapter.identity.adapter_name,
            adapter_kind=adapter.identity.adapter_kind,
            adapter_status=adapter.status,
            capability_count=len(adapter.supported_capabilities),
            stage_label=adapter.identity.stage_label,
            language_label=adapter.identity.language_label,
        )
