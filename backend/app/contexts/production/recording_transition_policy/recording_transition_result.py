from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.contexts.production.operational_state import OperationalStateValue
from app.contexts.production.transition_policy import (
    TransitionEvaluation,
    TransitionPolicyResult,
)
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata

from .recording_transition_evidence_profile import RecordingTransitionEvidenceProfile


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RecordingTransitionResult:
    """Recording-specific diagnostics around one generic transition evaluation."""

    evaluation: TransitionEvaluation
    applied_rule_id: EntityId | None
    evidence_profile: RecordingTransitionEvidenceProfile
    ambiguity_reasons: Sequence[str]
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "ambiguity_reasons", tuple(self.ambiguity_reasons))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    @property
    def outcome(self) -> TransitionPolicyResult:
        return self.evaluation.outcome

    @property
    def proposed_state(self) -> OperationalStateValue | None:
        return self.evaluation.proposed_state
