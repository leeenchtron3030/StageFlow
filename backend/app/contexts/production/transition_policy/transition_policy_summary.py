from __future__ import annotations

from dataclasses import dataclass

from app.contexts.production.operational_state import OperationalStateKind
from app.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class TransitionPolicySummary:
    """Lightweight diagnostics for an Operational State Transition Policy."""

    policy_id: EntityId
    policy_name: str
    evaluated_state_kind: OperationalStateKind
    rule_count: int

    @classmethod
    def from_policy(
        cls,
        policy: OperationalStateTransitionPolicy,
    ) -> TransitionPolicySummary:
        return cls(
            policy_id=policy.id,
            policy_name=policy.name,
            evaluated_state_kind=policy.evaluated_state_kind,
            rule_count=policy.rule_count,
        )


from app.contexts.production.transition_policy.operational_state_transition_policy import (  # noqa: E402
    OperationalStateTransitionPolicy,
)
