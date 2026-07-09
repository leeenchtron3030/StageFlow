from __future__ import annotations

from dataclasses import dataclass

from app.contexts.production.operator_adapter.operator_adapter_identity import (
    OperatorAdapterKind,
)
from app.contexts.production.operator_adapter.operator_source_adapter import (
    OperatorAdapterStatus,
    OperatorSourceAdapter,
)
from app.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class OperatorAdapterSummary:
    """Lightweight diagnostic summary for an operator source adapter."""

    adapter_id: EntityId
    adapter_name: str
    adapter_kind: OperatorAdapterKind
    adapter_status: OperatorAdapterStatus
    capability_count: int
    stage_label: str | None = None

    @classmethod
    def from_adapter(cls, adapter: OperatorSourceAdapter) -> OperatorAdapterSummary:
        return cls(
            adapter_id=adapter.id,
            adapter_name=adapter.identity.adapter_name,
            adapter_kind=adapter.identity.adapter_kind,
            adapter_status=adapter.status,
            capability_count=len(adapter.supported_capabilities),
            stage_label=adapter.identity.stage_label,
        )
