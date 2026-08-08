from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.contexts.production.hypothesis.hypothesis_confidence import HypothesisConfidence
from app.contexts.production.hypothesis.hypothesis_status import HypothesisStatus
from app.contexts.production.hypothesis.hypothesis_support import HypothesisSupport
from app.contexts.production.hypothesis.hypothesis_type import HypothesisType
from app.shared.ids import CorrelationId, EntityId
from app.shared.metadata import freeze_metadata
from app.shared.time import require_aware_datetime


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class Hypothesis:
    """A possible interpretation of evidence."""

    id: EntityId
    recording_block_id: EntityId
    hypothesis_type: HypothesisType
    hypothesis_status: HypothesisStatus
    confidence: HypothesisConfidence
    support: HypothesisSupport
    correlation_id: CorrelationId
    created_at: datetime
    updated_at: datetime | None = None
    notes: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware_datetime(self.created_at, "Hypothesis.created_at")
        if self.updated_at is not None:
            require_aware_datetime(self.updated_at, "Hypothesis.updated_at")
        if self.updated_at is not None and self.updated_at < self.created_at:
            raise ValueError("Hypothesis updated_at must not be before created_at.")
        if self.hypothesis_type not in {HypothesisType.GENERAL_CONTEXT, HypothesisType.UNKNOWN}:
            if self.support.total_count == 0:
                raise ValueError(
                    "Non-general Hypothesis requires at least one EvidenceSet reference."
                )
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
