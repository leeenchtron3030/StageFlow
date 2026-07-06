from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from app.contexts.production.finding.finding_confidence import FindingConfidence
from app.contexts.production.finding.finding_location import FindingLocation
from app.contexts.production.finding.finding_origin import FindingOrigin
from app.contexts.production.finding.finding_support import FindingSupport
from app.contexts.production.finding.finding_type import FindingType
from app.shared.ids import CorrelationId, EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class Finding:
    """A human-reviewable reasoning artifact."""

    id: EntityId
    recording_block_id: EntityId
    finding_type: FindingType
    confidence: FindingConfidence
    origin: FindingOrigin
    location: FindingLocation
    support: FindingSupport
    correlation_id: CorrelationId
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    notes: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if self.location.recording_block_id != self.recording_block_id:
            raise ValueError("Finding location must belong to recording_block_id.")
        if self.support.total_count == 0:
            raise ValueError("Finding requires at least one Hypothesis ID reference.")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
