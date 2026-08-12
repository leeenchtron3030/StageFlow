from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.contexts.production.evidence import (
    EvidenceConcern,
    EvidencePurpose,
    EvidenceRole,
    EvidenceSignal,
    EvidenceStrength,
)
from app.contexts.production.observation import ObservationType
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata


def _empty_metadata() -> Mapping[str, Any]:
    return {}


_LEGACY_CONCERN_VALUES = {
    "recording_activity": EvidenceConcern.RECORDING_COVERAGE,
    "media_artifact_availability": EvidenceConcern.MEDIA_AVAILABILITY,
    "time_boundary": EvidenceConcern.SCHEDULE_ALIGNMENT,
    "scheduled_activity": EvidenceConcern.SCHEDULE_ALIGNMENT,
    "transcript_activity": EvidenceConcern.TRANSCRIPT_CONTINUITY,
    "vision_activity": EvidenceConcern.VISUAL_TRANSITION_CONTEXT,
}


def _coerce_concern(concern: EvidenceConcern | str) -> EvidenceConcern:
    if isinstance(concern, EvidenceConcern):
        return concern
    if concern in _LEGACY_CONCERN_VALUES:
        return _LEGACY_CONCERN_VALUES[concern]
    return EvidenceConcern(concern)


@dataclass(frozen=True, slots=True)
class EvidenceBuilderRule:
    """Declarative grouping intent for one operational concern."""

    id: EntityId
    operational_concern: EvidenceConcern | str
    supporting_observation_types: Sequence[ObservationType] = field(default_factory=tuple)
    evidence_purpose: EvidencePurpose = EvidencePurpose.OPERATIONAL_CONTEXT
    evidence_signal: EvidenceSignal = EvidenceSignal.UNKNOWN
    supporting_strength: EvidenceStrength = EvidenceStrength.MODERATE
    contradicting_observation_types: Sequence[ObservationType] = field(default_factory=tuple)
    contextual_observation_types: Sequence[ObservationType] = field(default_factory=tuple)
    neutral_observation_types: Sequence[ObservationType] = field(default_factory=tuple)
    description: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        concern = _coerce_concern(self.operational_concern)
        if self.supporting_strength is EvidenceStrength.CONTRADICTORY:
            raise ValueError("Supporting EvidenceBuilderRule strength must not be contradictory.")

        object.__setattr__(self, "operational_concern", concern)
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
        object.__setattr__(
            self,
            "neutral_observation_types",
            tuple(self.neutral_observation_types),
        )
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    @property
    def concern(self) -> EvidenceConcern:
        return _coerce_concern(self.operational_concern)

    def role_for(self, observation_type: ObservationType) -> EvidenceRole | None:
        if observation_type in self.supporting_observation_types:
            return EvidenceRole.SUPPORTS
        if observation_type in self.contradicting_observation_types:
            return EvidenceRole.CONTRADICTS
        if observation_type in self.contextual_observation_types:
            return EvidenceRole.CONTEXTUALIZES
        if observation_type in self.neutral_observation_types:
            return EvidenceRole.NEUTRAL
        return None

    def strength_for_role(self, role: EvidenceRole) -> EvidenceStrength:
        if role is EvidenceRole.SUPPORTS:
            return self.supporting_strength
        if role is EvidenceRole.CONTRADICTS:
            return EvidenceStrength.CONTRADICTORY
        return EvidenceStrength.UNKNOWN
