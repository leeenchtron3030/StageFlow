from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from app.contexts.production.operational_state import (
    OperationalStateKind,
    OperationalStateSubjectType,
    OperationalStateValue,
)
from app.shared.ids import EntityId

from .operational_state_acceptance_outcome import OperationalStateAcceptanceOutcome
from .operational_state_acceptance_reason import OperationalStateAcceptanceReasonCode
from .operational_state_acceptance_result import OperationalStateAcceptanceResult


@dataclass(frozen=True, slots=True)
class OperationalStateAcceptanceSummary:
    acceptance_id: EntityId
    outcome: OperationalStateAcceptanceOutcome
    evaluation_id: EntityId
    policy_id: EntityId | None
    transition_rule_id: EntityId | None
    acceptance_rule_id: EntityId | None
    state_kind: OperationalStateKind
    effective_current_value: OperationalStateValue
    proposed_value: OperationalStateValue
    target_subject_type: OperationalStateSubjectType | None
    target_subject_identifier: str | None
    current_state_id: EntityId | None
    successor_state_id: EntityId | None
    supporting_evidence_set_count: int
    observation_count: int
    source_event_count: int
    accepted_at: datetime
    evaluation_timestamp: datetime
    supersession_described: bool
    reason_codes: Sequence[OperationalStateAcceptanceReasonCode]

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))

    @classmethod
    def from_result(
        cls,
        result: OperationalStateAcceptanceResult,
        *,
        evaluation_timestamp: datetime,
    ) -> OperationalStateAcceptanceSummary:
        successor = result.successor_state
        subject = result.target_subject
        lineage = result.lineage
        return cls(
            acceptance_id=result.id,
            outcome=result.outcome,
            evaluation_id=result.accepted_evaluation_id,
            policy_id=lineage.policy_id,
            transition_rule_id=lineage.applied_rule_id,
            acceptance_rule_id=result.applied_acceptance_rule_id,
            state_kind=lineage.evaluated_state_kind,
            effective_current_value=lineage.effective_current_value,
            proposed_value=lineage.proposed_state_value,
            target_subject_type=subject.subject_type,
            target_subject_identifier=subject.subject_identifier,
            current_state_id=result.current_state_id,
            successor_state_id=successor.id if successor is not None else None,
            supporting_evidence_set_count=len(lineage.supporting_evidence_set_ids),
            observation_count=len(lineage.contributing_observation_ids),
            source_event_count=len(lineage.contributing_production_event_ids),
            accepted_at=result.accepted_at,
            evaluation_timestamp=evaluation_timestamp,
            supersession_described=result.supersession is not None,
            reason_codes=tuple(reason.code for reason in result.reasons),
        )
