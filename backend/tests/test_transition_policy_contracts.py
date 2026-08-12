from dataclasses import fields
from datetime import UTC, datetime
from inspect import getmembers, isfunction

from app.contexts.production.operational_state import (
    OperationalState,
    OperationalStateBasis,
    OperationalStateFamily,
    OperationalStateKind,
    OperationalStateStatus,
    OperationalStateSubject,
    OperationalStateSubjectType,
    OperationalStateValue,
)
from app.contexts.production.transition_policy import (
    OperationalStateTransitionPolicy,
    TransitionEvaluation,
    TransitionPolicyResult,
    TransitionPolicySummary,
    TransitionReason,
)
from app.shared.ids import EntityId
from tests.timestamp_fixtures import AWARE_TIMESTAMP


def _state(value: OperationalStateValue) -> OperationalState:
    return OperationalState(
        id=EntityId.new(),
        family=OperationalStateFamily.DIRECTLY_OBSERVABLE,
        kind=OperationalStateKind.RECORDING_STATE,
        subject=OperationalStateSubject(
            subject_type=OperationalStateSubjectType.RECORDING_BLOCK,
            subject_identifier=EntityId.new().to_json(),
        ),
        value=value,
        status=OperationalStateStatus.CURRENT,
        basis=OperationalStateBasis(observation_ids=(EntityId.new(),)),
        observed_or_derived_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )


def test_generic_policy_creation() -> None:
    policy = OperationalStateTransitionPolicy(
        id=EntityId.new(),
        name="Generic Policy",
        evaluated_state_kind=OperationalStateKind.RECORDING_STATE,
    )

    assert policy.name == "Generic Policy"
    assert policy.evaluated_state_kind is OperationalStateKind.RECORDING_STATE
    assert policy.rule_count == 0


def test_transition_evaluation_creation() -> None:
    current_state = _state(OperationalStateValue.INACTIVE)
    proposed_state = OperationalStateValue.ACTIVE
    supporting_evidence_id = EntityId.new()
    blocking_evidence_id = EntityId.new()

    evaluation = TransitionEvaluation(
        id=EntityId.new(),
        evaluated_state_kind=OperationalStateKind.RECORDING_STATE,
        current_state=current_state,
        proposed_state=proposed_state,
        outcome=TransitionPolicyResult.TRANSITION_SUPPORTED,
        supporting_evidence_ids=(supporting_evidence_id,),
        blocking_evidence_ids=(blocking_evidence_id,),
        rationale=TransitionReason("Recording Evidence supports active recording."),
        evaluated_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )

    assert evaluation.current_state == current_state
    assert evaluation.proposed_state is proposed_state
    assert evaluation.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert evaluation.supporting_evidence_ids == (supporting_evidence_id,)
    assert evaluation.blocking_evidence_ids == (blocking_evidence_id,)


def test_transition_reason_creation() -> None:
    reason = TransitionReason("Recording Evidence incomplete.")

    assert reason.message == "Recording Evidence incomplete."
    assert dict(reason.metadata) == {}


def test_transition_policy_result_allowed_values() -> None:
    assert {result.value for result in TransitionPolicyResult} == {
        "transition_supported",
        "transition_not_supported",
        "insufficient_evidence",
        "already_current",
        "unknown",
    }


def test_generic_policy_evaluation_is_explainable_and_non_executing() -> None:
    policy = OperationalStateTransitionPolicy(
        id=EntityId.new(),
        name="Generic Policy",
        evaluated_state_kind=OperationalStateKind.RECORDING_STATE,
    )
    current_state = _state(OperationalStateValue.INACTIVE)

    evaluation = policy.evaluate(
                     evaluated_at=AWARE_TIMESTAMP,
                     current_state=current_state, evidence_sets=())

    assert evaluation.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE
    assert evaluation.current_state == current_state
    assert evaluation.proposed_state is None
    assert "no concrete rules" in evaluation.rationale.message


def test_transition_policy_summary_generation() -> None:
    policy = OperationalStateTransitionPolicy(
        id=EntityId.new(),
        name="Generic Policy",
        evaluated_state_kind=OperationalStateKind.RECORDING_STATE,
        rule_count=2,
    )

    summary = TransitionPolicySummary.from_policy(policy)

    assert summary.policy_id == policy.id
    assert summary.policy_name == policy.name
    assert summary.evaluated_state_kind is OperationalStateKind.RECORDING_STATE
    assert summary.rule_count == 2


def test_generic_policy_has_no_execution_or_infrastructure_behavior() -> None:
    names = {
        field.name
        for contract in (
            OperationalStateTransitionPolicy,
            TransitionEvaluation,
            TransitionReason,
            TransitionPolicySummary,
        )
        for field in fields(contract)
    } | {
        name
        for name, value in getmembers(OperationalStateTransitionPolicy)
        if isfunction(value)
    }
    forbidden_terms = {
        "mutate",
        "persist",
        "repository",
        "state_machine",
        "dispatch",
        "hypothesis",
        "finding",
        "verification",
        "operational_product",
        "api",
        "queue",
        "worker",
        "frontend",
        "ai",
    }

    assert not any(term in name for name in names for term in forbidden_terms)
