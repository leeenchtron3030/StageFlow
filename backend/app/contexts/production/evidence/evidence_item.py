from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.contexts.production.evidence.evidence_strength import EvidenceStrength
from app.shared.ids import EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """One observation reference used as evidence."""

    id: EntityId
    observation_id: EntityId
    strength: EvidenceStrength
    weight: float | None = None
    rationale: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if self.weight is not None and not 0.0 <= self.weight <= 1.0:
            raise ValueError("EvidenceItem weight must be between 0.0 and 1.0 when provided.")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
