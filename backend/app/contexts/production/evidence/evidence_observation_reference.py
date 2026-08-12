from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from app.contexts.production.evidence.evidence_role import EvidenceRole
from app.contexts.production.evidence.evidence_strength import EvidenceStrength
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class EvidenceObservationReference:
    """One Observation's relationship to one Evidence concern."""

    observation_id: EntityId
    role: EvidenceRole
    strength: EvidenceStrength | None = None
    weight: float | None = None
    rationale: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if self.weight is not None and not 0.0 <= self.weight <= 1.0:
            raise ValueError(
                "EvidenceObservationReference weight must be between 0.0 and 1.0 when provided."
            )
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
