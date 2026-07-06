from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from app.contexts.production.verification.verification_action import VerificationAction
from app.contexts.production.verification.verification_decision import VerificationDecision
from app.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class VerificationSummary:
    """Summary of the known append-only decision history for one finding."""

    finding_id: EntityId
    decision_count: int
    count_by_action: MappingProxyType[VerificationAction, int]
    latest_action: VerificationAction | None
    latest_decided_at: datetime | None
    has_accept_decision: bool
    has_reject_decision: bool
    has_adjustment_decision: bool
    has_escalation_decision: bool

    @classmethod
    def from_decisions(
        cls,
        finding_id: EntityId,
        decisions: Sequence[VerificationDecision],
    ) -> VerificationSummary:
        related_decisions = tuple(
            decision for decision in decisions if decision.finding_id == finding_id
        )
        counts = {action: 0 for action in VerificationAction}
        for decision in related_decisions:
            counts[decision.action] += 1

        latest_decision = max(
            related_decisions,
            key=lambda decision: decision.decided_at,
            default=None,
        )

        return cls(
            finding_id=finding_id,
            decision_count=len(related_decisions),
            count_by_action=MappingProxyType(counts),
            latest_action=latest_decision.action if latest_decision is not None else None,
            latest_decided_at=latest_decision.decided_at if latest_decision is not None else None,
            has_accept_decision=counts[VerificationAction.ACCEPT] > 0,
            has_reject_decision=counts[VerificationAction.REJECT] > 0,
            has_adjustment_decision=counts[VerificationAction.ADJUST] > 0,
            has_escalation_decision=counts[VerificationAction.ESCALATE] > 0,
        )
