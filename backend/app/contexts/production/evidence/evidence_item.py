from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from app.contexts.production.evidence.evidence_observation_reference import (
    EvidenceObservationReference,
)
from app.contexts.production.evidence.evidence_role import EvidenceRole
from app.contexts.production.evidence.evidence_strength import EvidenceStrength
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """One observation reference used as evidence."""

    id: EntityId
    observation_id: EntityId
    strength: EvidenceStrength
    role: EvidenceRole = EvidenceRole.UNKNOWN
    weight: float | None = None
    rationale: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if self.weight is not None and not 0.0 <= self.weight <= 1.0:
            raise ValueError("EvidenceItem weight must be between 0.0 and 1.0 when provided.")
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    @property
    def observation_reference(self) -> EvidenceObservationReference:
        return EvidenceObservationReference(
            observation_id=self.observation_id,
            role=self.role,
            strength=self.strength,
            weight=self.weight,
            rationale=self.rationale,
            metadata=self.metadata,
        )
