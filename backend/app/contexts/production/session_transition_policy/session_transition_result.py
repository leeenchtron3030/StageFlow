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

from .session_transition_evidence_profile import SessionTransitionEvidenceProfile


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class SessionTransitionResult:
    """Descriptive policy result with evaluation and Evidence diagnostics."""

    evaluation: TransitionEvaluation
    applied_rule_id: EntityId | None
    evidence_profile: SessionTransitionEvidenceProfile | None
    satisfied_requirement_ids: Sequence[EntityId]
    unmet_requirement_ids: Sequence[EntityId]
    ignored_evidence_set_ids: Sequence[EntityId]
    unsupported_evidence_set_ids: Sequence[EntityId]
    duplicate_evidence_set_ids: Sequence[EntityId]
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "satisfied_requirement_ids",
            tuple(self.satisfied_requirement_ids),
        )
        object.__setattr__(
            self,
            "unmet_requirement_ids",
            tuple(self.unmet_requirement_ids),
        )
        object.__setattr__(
            self,
            "ignored_evidence_set_ids",
            tuple(self.ignored_evidence_set_ids),
        )
        object.__setattr__(
            self,
            "unsupported_evidence_set_ids",
            tuple(self.unsupported_evidence_set_ids),
        )
        object.__setattr__(
            self,
            "duplicate_evidence_set_ids",
            tuple(self.duplicate_evidence_set_ids),
        )
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    @property
    def outcome(self) -> TransitionPolicyResult:
        return self.evaluation.outcome

    @property
    def proposed_state(self) -> OperationalStateValue | None:
        return self.evaluation.proposed_state

    @property
    def supporting_evidence_ids(self) -> tuple[EntityId, ...]:
        return tuple(self.evaluation.supporting_evidence_ids)

    @property
    def blocking_evidence_ids(self) -> tuple[EntityId, ...]:
        return tuple(self.evaluation.blocking_evidence_ids)
