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
class RecordingCoverageEvidenceResult:
    """Result of building recording coverage Evidence from Observations."""

    evidence_sets: Sequence[EvidenceSet]
    consumed_observation_ids: Sequence[EntityId]
    ignored_observation_ids: Sequence[EntityId]
    unsupported_observation_ids: Sequence[EntityId]
    duplicate_observation_ids: Sequence[EntityId]
    applied_rule_ids: Sequence[EntityId]
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_sets", tuple(self.evidence_sets))
        object.__setattr__(
            self,
            "consumed_observation_ids",
            tuple(self.consumed_observation_ids),
        )
        object.__setattr__(
            self,
            "ignored_observation_ids",
            tuple(self.ignored_observation_ids),
        )
        object.__setattr__(
            self,
            "unsupported_observation_ids",
            tuple(self.unsupported_observation_ids),
        )
        object.__setattr__(
            self,
            "duplicate_observation_ids",
            tuple(self.duplicate_observation_ids),
        )
        object.__setattr__(self, "applied_rule_ids", tuple(self.applied_rule_ids))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def evidence_count(self) -> int:
        return len(self.evidence_sets)
