from dataclasses import fields
from datetime import UTC, datetime
from inspect import getmembers, isfunction

from app.contexts.production.evidence import (
    EvidenceConcern,
    EvidenceItem,
    EvidencePurpose,
    EvidenceRole,
    EvidenceSet,
    EvidenceSignal,
    EvidenceSignalReference,
    EvidenceStrength,
)
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
from app.contexts.production.recording_transition_policy import (
    RecordingTransitionPolicy,
    RecordingTransitionRule,
    RecordingTransitionSummary,
    mapping_for_recording_marker,
    mapping_for_recording_signal,
)
from app.contexts.production.transition_policy import TransitionPolicyResult
from app.shared.ids import CorrelationId, EntityId


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


def _evidence(
    *,
    signal: EvidenceSignal,
    concern: EvidenceConcern = EvidenceConcern.RECORDING_COVERAGE,
    role: EvidenceRole = EvidenceRole.SUPPORTS,
    marker: str | None = None,
) -> EvidenceSet:
    item = EvidenceItem(
        id=EntityId.new(),
        observation_id=EntityId.new(),
        role=role,
        strength=(
            EvidenceStrength.CONTRADICTORY
            if role is EvidenceRole.CONTRADICTS
            else EvidenceStrength.STRONG
        ),
    )
    return EvidenceSet(
        id=EntityId.new(),
        recording_block_id=EntityId.new(),
        concern=concern,
        purpose=EvidencePurpose.TRANSITION_SUPPORT,
        items=(item,),
        signals=(
            EvidenceSignalReference(
                signal=signal,
                evidence_item_ids=(item.id,),
                observation_ids=(item.observation_id,),
            ),
        ),
        correlation_id=CorrelationId.new(),
        metadata=(
            {"recording_transition_marker": marker}
            if marker is not None
            else {}
        ),
    )


def _legacy_marker_evidence(marker: str) -> EvidenceSet:
    item = EvidenceItem(
        id=EntityId.new(),
        observation_id=EntityId.new(),
        role=EvidenceRole.SUPPORTS,
        strength=EvidenceStrength.STRONG,
    )
    return EvidenceSet(
        id=EntityId.new(),
        recording_block_id=EntityId.new(),
        concern=EvidenceConcern.RECORDING_COVERAGE,
        purpose=EvidencePurpose.TRANSITION_SUPPORT,
        items=(item,),
        correlation_id=CorrelationId.new(),
        metadata={"recording_transition_marker": marker},
    )


def test_recording_transition_policy_creation() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())

    assert policy.name == "Recording Transition Policy"
    assert policy.evaluated_state_kind is OperationalStateKind.RECORDING_STATE
    assert len(policy.rules) == 4


def test_recording_inactive_to_active_evaluation() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    evidence = _evidence(signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED)

    evaluation = policy.evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(evidence,),
    )

    assert evaluation.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert evaluation.proposed_state is OperationalStateValue.ACTIVE
    assert evaluation.supporting_evidence_ids == (evidence.id,)
    assert "active recording" in evaluation.rationale.message


def test_recording_active_to_paused_evaluation() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    evidence = _evidence(signal=EvidenceSignal.RECORDING_PAUSE_INDICATED)

    evaluation = policy.evaluate(
        current_state=_state(OperationalStateValue.ACTIVE),
        evidence_sets=(evidence,),
    )

    assert evaluation.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert evaluation.proposed_state is OperationalStateValue.PAUSED
    assert evaluation.supporting_evidence_ids == (evidence.id,)


def test_recording_paused_to_active_evaluation() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    evidence = _evidence(signal=EvidenceSignal.RECORDING_CONTINUITY_RESTORED)

    evaluation = policy.evaluate(
        current_state=_state(OperationalStateValue.PAUSED),
        evidence_sets=(evidence,),
    )

    assert evaluation.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert evaluation.proposed_state is OperationalStateValue.ACTIVE


def test_recording_active_to_stopped_evaluation() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    evidence = _evidence(signal=EvidenceSignal.RECORDING_END_INDICATED)

    evaluation = policy.evaluate(
        current_state=_state(OperationalStateValue.ACTIVE),
        evidence_sets=(evidence,),
    )

    assert evaluation.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert evaluation.proposed_state is OperationalStateValue.STOPPED
    assert "stopped recording" in evaluation.rationale.message


def test_recording_transition_returns_insufficient_evidence() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    evidence = _evidence(
        signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
        concern=EvidenceConcern.TRANSCRIPT_CONTINUITY,
    )

    evaluation = policy.evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(evidence,),
    )

    assert evaluation.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE
    assert evaluation.proposed_state is None
    assert evaluation.supporting_evidence_ids == ()
    assert "incomplete" in evaluation.rationale.message


def test_recording_transition_returns_already_current() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    evidence = _evidence(signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED)

    evaluation = policy.evaluate(
        current_state=_state(OperationalStateValue.ACTIVE),
        evidence_sets=(evidence,),
    )

    assert evaluation.outcome is TransitionPolicyResult.ALREADY_CURRENT
    assert evaluation.proposed_state is OperationalStateValue.ACTIVE
    assert evaluation.supporting_evidence_ids == (evidence.id,)


def test_unrelated_evidence_is_ignored() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    transcript_evidence = _evidence(
        signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
        concern=EvidenceConcern.TRANSCRIPT_CONTINUITY,
    )
    vision_evidence = _evidence(
        signal=EvidenceSignal.RECORDING_PAUSE_INDICATED,
        concern=EvidenceConcern.VISUAL_TRANSITION_CONTEXT,
    )

    evaluation = policy.evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(transcript_evidence, vision_evidence),
    )

    assert evaluation.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE
    assert evaluation.metadata["examined_evidence_ids"] == ()


def test_blocking_recording_evidence_prevents_transition() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    blocking_evidence = _evidence(
        signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
        role=EvidenceRole.CONTRADICTS,
    )

    evaluation = policy.evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(blocking_evidence,),
    )

    assert evaluation.outcome is TransitionPolicyResult.TRANSITION_NOT_SUPPORTED
    assert evaluation.blocking_evidence_ids == (blocking_evidence.id,)
    assert evaluation.supporting_evidence_ids == ()


def test_recording_policy_is_deterministic() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    evidence = _evidence(signal=EvidenceSignal.RECORDING_PAUSE_INDICATED)
    current_state = _state(OperationalStateValue.ACTIVE)

    first = policy.evaluate(current_state=current_state, evidence_sets=(evidence,))
    second = policy.evaluate(current_state=current_state, evidence_sets=(evidence,))

    assert first.outcome is second.outcome
    assert first.proposed_state is second.proposed_state
    assert first.supporting_evidence_ids == second.supporting_evidence_ids
    assert first.blocking_evidence_ids == second.blocking_evidence_ids
    assert first.rationale.message == second.rationale.message


def test_recording_policy_explainability() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    evidence = _evidence(signal=EvidenceSignal.RECORDING_END_INDICATED)

    evaluation = policy.evaluate(
        current_state=_state(OperationalStateValue.ACTIVE),
        evidence_sets=(evidence,),
    )

    assert evaluation.metadata["examined_evidence_ids"] == (evidence.id.to_json(),)
    assert evaluation.metadata["examined_signal_values"] == (
        EvidenceSignal.RECORDING_END_INDICATED.value,
    )
    assert evaluation.rationale.message
    assert evaluation.supporting_evidence_ids == (evidence.id,)


def test_recording_transition_summary_generation() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())

    summary = RecordingTransitionSummary.from_policy(policy)

    assert summary.policy_id == policy.id
    assert summary.policy_name == policy.name
    assert summary.evaluated_state_kind is OperationalStateKind.RECORDING_STATE
    assert summary.rule_count == len(policy.rules)


def test_recording_transition_mapping_contract() -> None:
    mapping = mapping_for_recording_signal(EvidenceSignal.RECORDING_PAUSE_INDICATED)

    assert mapping is not None
    assert mapping.proposed_state is OperationalStateValue.PAUSED
    assert mapping.legacy_evidence_marker == "recording_paused"


def test_legacy_recording_transition_marker_remains_secondary_compatibility() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    evidence = _legacy_marker_evidence("recording_stopped")

    evaluation = policy.evaluate(
        current_state=_state(OperationalStateValue.ACTIVE),
        evidence_sets=(evidence,),
    )

    assert evaluation.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert evaluation.proposed_state is OperationalStateValue.STOPPED
    assert mapping_for_recording_marker("recording_stopped") is not None


def test_first_class_signal_overrides_conflicting_legacy_marker() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    evidence = _evidence(
        signal=EvidenceSignal.RECORDING_PAUSE_INDICATED,
        marker="recording_stopped",
    )

    evaluation = policy.evaluate(
        current_state=_state(OperationalStateValue.ACTIVE),
        evidence_sets=(evidence,),
    )

    assert evaluation.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert evaluation.proposed_state is OperationalStateValue.PAUSED


def test_unrelated_signal_is_ignored() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    evidence = _evidence(signal=EvidenceSignal.MEDIA_AVAILABILITY_INDICATED)

    evaluation = policy.evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(evidence,),
    )

    assert evaluation.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE
    assert evaluation.proposed_state is None


def test_recording_transition_rule_rejects_unsupported_target_state() -> None:
    try:
        RecordingTransitionRule(
            id=EntityId.new(),
            evidence_signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
            proposed_state=OperationalStateValue.INTERRUPTED,
        )
    except ValueError as error:
        assert "active, paused, or stopped" in str(error)
    else:
        raise AssertionError("Expected unsupported recording transition state to fail.")


def test_recording_policy_has_no_execution_or_infrastructure_behavior() -> None:
    names = {
        field.name
        for contract in (
            RecordingTransitionPolicy,
            RecordingTransitionRule,
            RecordingTransitionSummary,
        )
        for field in fields(contract)
    } | {
        name
        for name, value in getmembers(RecordingTransitionPolicy)
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
