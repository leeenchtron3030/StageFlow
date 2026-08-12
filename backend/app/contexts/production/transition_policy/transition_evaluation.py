from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.contexts.production.evidence import EvidenceContext, EvidenceContextConflict
from app.contexts.production.operational_state import (
    OperationalState,
    OperationalStateKind,
    OperationalStateValue,
)
from app.contexts.production.transition_policy.transition_policy_result import (
    TransitionPolicyResult,
)
from app.contexts.production.transition_policy.transition_reason import TransitionReason
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata
from app.shared.time import require_aware_datetime


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class TransitionEvaluation:
    """Deterministic evaluation of whether a state transition is supported."""

    id: EntityId
    evaluated_state_kind: OperationalStateKind
    current_state: OperationalState | None
    proposed_state: OperationalStateValue | None
    outcome: TransitionPolicyResult
    supporting_evidence_ids: Sequence[EntityId]
    blocking_evidence_ids: Sequence[EntityId]
    rationale: TransitionReason
    evaluated_at: datetime
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)
    context: EvidenceContext = field(default_factory=EvidenceContext.unknown)
    context_conflicts: Sequence[EvidenceContextConflict] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        require_aware_datetime(self.evaluated_at, "TransitionEvaluation.evaluated_at")
        object.__setattr__(
            self,
            "supporting_evidence_ids",
            tuple(self.supporting_evidence_ids),
        )
        object.__setattr__(
            self,
            "blocking_evidence_ids",
            tuple(self.blocking_evidence_ids),
        )
        object.__setattr__(self, "context_conflicts", tuple(self.context_conflicts))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
