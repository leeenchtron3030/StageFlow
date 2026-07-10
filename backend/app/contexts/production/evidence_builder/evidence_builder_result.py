from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.contexts.production.evidence import EvidenceSet
from app.shared.ids import EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class EvidenceBuilderResult:
    """Result of organizing Observations into zero or more Evidence sets."""

    source_observation_ids: Sequence[EntityId]
    evidence_sets: Sequence[EvidenceSet]
    builder_id: EntityId
    warnings: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_observation_ids", tuple(self.source_observation_ids))
        object.__setattr__(self, "evidence_sets", tuple(self.evidence_sets))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def evidence_count(self) -> int:
        return len(self.evidence_sets)
