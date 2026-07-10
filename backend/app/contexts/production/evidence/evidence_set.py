from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from app.contexts.production.evidence.evidence_concern import EvidenceConcern
from app.contexts.production.evidence.evidence_item import EvidenceItem
from app.contexts.production.evidence.evidence_purpose import EvidencePurpose
from app.shared.ids import CorrelationId, EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class EvidenceSet:
    """A group of evidence items that may support a future conclusion."""

    id: EntityId
    recording_block_id: EntityId | None
    purpose: EvidencePurpose
    items: Sequence[EvidenceItem]
    correlation_id: CorrelationId
    concern: EvidenceConcern = EvidenceConcern.UNKNOWN
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    notes: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if len(self.items) == 0:
            raise ValueError("EvidenceSet requires at least one EvidenceItem.")
        object.__setattr__(self, "items", tuple(self.items))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
