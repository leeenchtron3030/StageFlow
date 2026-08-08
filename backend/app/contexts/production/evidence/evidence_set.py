from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.contexts.production.evidence.evidence_concern import EvidenceConcern
from app.contexts.production.evidence.evidence_context import EvidenceContext
from app.contexts.production.evidence.evidence_context_resolution import (
    EvidenceContextResolution,
)
from app.contexts.production.evidence.evidence_item import EvidenceItem
from app.contexts.production.evidence.evidence_purpose import EvidencePurpose
from app.contexts.production.evidence.evidence_signal_reference import (
    EvidenceSignalReference,
)
from app.shared.ids import CorrelationId, EntityId
from app.shared.metadata import freeze_metadata
from app.shared.time import require_aware_datetime


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
    created_at: datetime
    concern: EvidenceConcern = EvidenceConcern.UNKNOWN
    signals: Sequence[EvidenceSignalReference] = field(default_factory=tuple)
    notes: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)
    context: EvidenceContext = field(default_factory=EvidenceContext.unknown)
    context_resolution: EvidenceContextResolution | None = None

    def __post_init__(self) -> None:
        require_aware_datetime(self.created_at, "EvidenceSet.created_at")
        if len(self.items) == 0:
            raise ValueError("EvidenceSet requires at least one EvidenceItem.")
        object.__setattr__(self, "items", tuple(self.items))
        object.__setattr__(self, "signals", tuple(self.signals))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
