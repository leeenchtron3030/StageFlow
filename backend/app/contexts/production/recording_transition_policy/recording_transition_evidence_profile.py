from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.contexts.production.evidence import EvidenceSignal
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata

from .recording_transition_context import RecordingTransitionContext


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RecordingTransitionEvidenceProfile:
    """Descriptive, non-scored evidence profile for one recording evaluation."""

    qualifying_evidence_set_ids: Sequence[EntityId]
    conflicting_evidence_set_ids: Sequence[EntityId]
    ignored_evidence_set_ids: Sequence[EntityId]
    unsupported_evidence_set_ids: Sequence[EntityId]
    duplicate_evidence_set_ids: Sequence[EntityId]
    contributing_evidence_item_ids: Sequence[EntityId]
    contributing_observation_ids: Sequence[EntityId]
    contributing_signals: Sequence[EvidenceSignal]
    contexts: Sequence[RecordingTransitionContext]
    selected_context: RecordingTransitionContext | None
    conflicting_contexts: Sequence[RecordingTransitionContext]
    ordered_lifecycle_signals: Sequence[EvidenceSignal]
    current_state_validation: str
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        for name in (
            "qualifying_evidence_set_ids",
            "conflicting_evidence_set_ids",
            "ignored_evidence_set_ids",
            "unsupported_evidence_set_ids",
            "duplicate_evidence_set_ids",
            "contributing_evidence_item_ids",
            "contributing_observation_ids",
            "contributing_signals",
            "contexts",
            "conflicting_contexts",
            "ordered_lifecycle_signals",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if not self.current_state_validation.strip():
            raise ValueError(
                "RecordingTransitionEvidenceProfile current_state_validation must not be empty."
            )
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
