from __future__ import annotations

from dataclasses import dataclass

from app.contexts.production.operational_state import OperationalStateKind
from app.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class RecordingTransitionSummary:
    """Lightweight diagnostics for the Recording Transition Policy."""

    policy_id: EntityId
    policy_name: str
    evaluated_state_kind: OperationalStateKind
    rule_count: int

    @classmethod
    def from_policy(
        cls,
        policy: RecordingTransitionPolicy,
    ) -> RecordingTransitionSummary:
        return cls(
            policy_id=policy.id,
            policy_name=policy.name,
            evaluated_state_kind=policy.evaluated_state_kind,
            rule_count=len(policy.rules),
        )


from app.contexts.production.recording_transition_policy.recording_transition_policy import (  # noqa: E402
    RecordingTransitionPolicy,
)
