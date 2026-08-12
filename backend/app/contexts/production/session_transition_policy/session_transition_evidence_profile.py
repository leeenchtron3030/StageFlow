from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.contexts.production.evidence import (
    EvidenceConcern,
    EvidenceSignal,
    EvidenceStrength,
)
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata

from .session_transition_mapping import SessionTransitionEvidenceCategory


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class SessionTransitionEvidenceProfile:
    """Descriptive, non-scored profile of one boundary Evidence context."""

    target_boundary_concern: EvidenceConcern
    contributing_evidence_set_ids: Sequence[EntityId]
    contributing_evidence_item_ids: Sequence[EntityId]
    contributing_observation_ids: Sequence[EntityId]
    contributing_signals: Sequence[EvidenceSignal]
    evidence_categories: Sequence[SessionTransitionEvidenceCategory]
    strengths: Sequence[EvidenceStrength]
    supporting_count: int
    contradicting_count: int
    contextual_count: int
    unsupported_count: int
    independent_source_count: int
    recording_block_ids: Sequence[EntityId]
    stage_ids: Sequence[EntityId]
    scheduled_activity_ids: Sequence[EntityId]
    boundary_anchors: Sequence[str]
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if self.target_boundary_concern not in {
            EvidenceConcern.POSSIBLE_SESSION_START,
            EvidenceConcern.POSSIBLE_SESSION_END,
        }:
            raise ValueError("Session transition profile requires a boundary concern.")
        for name in (
            "supporting_count",
            "contradicting_count",
            "contextual_count",
            "unsupported_count",
            "independent_source_count",
        ):
            if getattr(self, name) < 0:
                raise ValueError("Session transition profile counts must not be negative.")
        object.__setattr__(
            self,
            "contributing_evidence_set_ids",
            tuple(self.contributing_evidence_set_ids),
        )
        object.__setattr__(
            self,
            "contributing_evidence_item_ids",
            tuple(self.contributing_evidence_item_ids),
        )
        object.__setattr__(
            self,
            "contributing_observation_ids",
            tuple(self.contributing_observation_ids),
        )
        object.__setattr__(self, "contributing_signals", tuple(self.contributing_signals))
        object.__setattr__(self, "evidence_categories", tuple(self.evidence_categories))
        object.__setattr__(self, "strengths", tuple(self.strengths))
        object.__setattr__(self, "recording_block_ids", tuple(self.recording_block_ids))
        object.__setattr__(self, "stage_ids", tuple(self.stage_ids))
        object.__setattr__(
            self,
            "scheduled_activity_ids",
            tuple(self.scheduled_activity_ids),
        )
        object.__setattr__(self, "boundary_anchors", tuple(self.boundary_anchors))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
