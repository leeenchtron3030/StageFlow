from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.contexts.production.evidence import EvidenceSet
from app.contexts.production.operational_state import (
    OperationalState,
    OperationalStateKind,
)
from app.contexts.production.transition_policy.transition_evaluation import (
    TransitionEvaluation,
)
from app.contexts.production.transition_policy.transition_policy_result import (
    TransitionPolicyResult,
)
from app.contexts.production.transition_policy.transition_reason import TransitionReason
from app.shared.ids import EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class OperationalStateTransitionPolicy:
    """Generic deterministic policy contract for evaluating state transitions."""

    id: EntityId
    name: str
    evaluated_state_kind: OperationalStateKind
    rule_count: int = 0
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("OperationalStateTransitionPolicy name must not be empty.")
        if self.rule_count < 0:
            raise ValueError("Transition policy rule_count must not be negative.")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def evaluate(
        self,
        *,
        current_state: OperationalState | None,
        evidence_sets: Sequence[EvidenceSet],
    ) -> TransitionEvaluation:
        evidence_tuple = tuple(evidence_sets)
        return TransitionEvaluation(
            id=EntityId.new(),
            evaluated_state_kind=self.evaluated_state_kind,
            current_state=current_state,
            proposed_state=None,
            outcome=TransitionPolicyResult.INSUFFICIENT_EVIDENCE,
            supporting_evidence_ids=(),
            blocking_evidence_ids=(),
            rationale=TransitionReason(
                "Generic transition policy has no concrete rules for the provided Evidence."
            ),
            metadata={
                "examined_evidence_ids": tuple(
                    evidence_set.id.to_json() for evidence_set in evidence_tuple
                ),
                "policy_id": self.id.to_json(),
            },
        )
