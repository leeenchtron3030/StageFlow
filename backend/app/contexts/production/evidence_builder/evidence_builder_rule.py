from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.contexts.production.evidence import EvidencePurpose, EvidenceStrength
from app.contexts.production.observation import ObservationType
from app.shared.ids import EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class EvidenceBuilderRule:
    """Declarative grouping intent for one operational concern."""

    id: EntityId
    operational_concern: str
    supporting_observation_types: Sequence[ObservationType]
    evidence_purpose: EvidencePurpose = EvidencePurpose.GENERAL_CONTEXT
    supporting_strength: EvidenceStrength = EvidenceStrength.MODERATE
    contradicting_observation_types: Sequence[ObservationType] = field(default_factory=tuple)
    contextual_observation_types: Sequence[ObservationType] = field(default_factory=tuple)
    description: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.operational_concern.strip():
            raise ValueError("EvidenceBuilderRule requires exactly one operational concern.")
        if self.supporting_strength is EvidenceStrength.CONTRADICTORY:
            raise ValueError("Supporting EvidenceBuilderRule strength must not be contradictory.")

        object.__setattr__(
            self,
            "supporting_observation_types",
            tuple(self.supporting_observation_types),
        )
        object.__setattr__(
            self,
            "contradicting_observation_types",
            tuple(self.contradicting_observation_types),
        )
        object.__setattr__(
            self,
            "contextual_observation_types",
            tuple(self.contextual_observation_types),
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def role_for(self, observation_type: ObservationType) -> str | None:
        if observation_type in self.supporting_observation_types:
            return "supporting"
        if observation_type in self.contradicting_observation_types:
            return "contradicting"
        if observation_type in self.contextual_observation_types:
            return "contextual"
        return None

    def strength_for_role(self, role: str) -> EvidenceStrength:
        if role == "supporting":
            return self.supporting_strength
        if role == "contradicting":
            return EvidenceStrength.CONTRADICTORY
        return EvidenceStrength.UNKNOWN
