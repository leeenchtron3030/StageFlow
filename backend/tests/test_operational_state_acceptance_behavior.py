from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.contexts.production.evidence import EvidenceSignal
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
from app.contexts.production.operational_state_acceptance import (
    OPERATIONAL_STATE_ACCEPTANCE_RULES,
    RECORDING_TRANSITION_POLICY_KIND,
    SESSION_TRANSITION_POLICY_KIND,
    OperationalStateAcceptance,
    OperationalStateAcceptanceContext,
    OperationalStateAcceptanceHistory,
    OperationalStateAcceptanceLineage,
    OperationalStateAcceptanceOutcome,
    OperationalStateAcceptanceReasonCode,
    OperationalStateAcceptanceRequest,
    OperationalStateAcceptanceSummary,
)
from app.contexts.production.transition_policy import (
    TransitionEvaluation,
    TransitionPolicyResult,
    TransitionReason,
)
from app.shared.ids import EntityId

EVALUATED_AT = datetime(2026, 7, 16, 17, 5, tzinfo=UTC)
ACCEPTED_AT = EVALUATED_AT + timedelta(seconds=2)
BOUNDARY_ANCHOR = datetime(2026, 7, 16, 17, 3, 30, tzinfo=UTC).isoformat()


def _acceptance_rule(
    kind: OperationalStateKind,
    current: OperationalStateValue,
    proposed: OperationalStateValue,
    *,
    occurrence: int = 0,
):
    matches = [
        rule
        for rule in OPERATIONAL_STATE_ACCEPTANCE_RULES
        if rule.state_kind is kind
        and rule.effective_current_value is current
        and rule.proposed_value is proposed
    ]
    return matches[occurrence]


def _subject_for(kind: OperationalStateKind, block_id: EntityId):
    if kind is OperationalStateKind.RECORDING_STATE:
        return OperationalStateSubject(
            subject_type=OperationalStateSubjectType.RECORDING_BLOCK,
            subject_identifier=block_id.to_json(),
        )
    return OperationalStateSubject(
        subject_type=OperationalStateSubjectType.SESSION_CANDIDATE,
        subject_identifier="candidate-a",
    )


def _family_for(kind: OperationalStateKind) -> OperationalStateFamily:
    if kind is OperationalStateKind.RECORDING_STATE:
        return OperationalStateFamily.DIRECTLY_OBSERVABLE
    return OperationalStateFamily.EVIDENCE_DERIVED


def _request(
    *,
    kind: OperationalStateKind = OperationalStateKind.RECORDING_STATE,
    current_value: OperationalStateValue = OperationalStateValue.INACTIVE,
    proposed_value: OperationalStateValue = OperationalStateValue.ACTIVE,
    with_current: bool | None = None,
    rule_occurrence: int = 0,
) -> OperationalStateAcceptanceRequest:
    if with_current is None:
        with_current = current_value is not OperationalStateValue.INACTIVE
    block_id = EntityId.new()
    stage_id = EntityId.new()
    policy_id = EntityId.new()
    evidence_set_id = EntityId.new()
    evidence_item_id = EntityId.new()
    observation_id = EntityId.new()
    production_event_id = EntityId.new()
    rule = _acceptance_rule(
        kind,
        current_value,
        proposed_value,
        occurrence=rule_occurrence,
    )
    subject = _subject_for(kind, block_id)
    current_state = (
        OperationalState(
            id=EntityId.new(),
            family=_family_for(kind),
            kind=kind,
            subject=subject,
            value=current_value,
            status=OperationalStateStatus.CURRENT,
            basis=OperationalStateBasis(
                observation_ids=(EntityId.new(),),
                evidence_set_ids=(EntityId.new(),),
                rationale="Previously accepted state.",
            ),
            observed_or_derived_at=EVALUATED_AT - timedelta(minutes=1),
            recording_block_id=block_id,
            stage_id=stage_id,
        )
        if with_current
        else None
    )
    evaluation_id = EntityId.new()
    policy_kind = (
        RECORDING_TRANSITION_POLICY_KIND
        if kind is OperationalStateKind.RECORDING_STATE
        else SESSION_TRANSITION_POLICY_KIND
    )
    evaluation = TransitionEvaluation(
        id=evaluation_id,
        evaluated_state_kind=kind,
        current_state=current_state,
        proposed_state=proposed_value,
        outcome=TransitionPolicyResult.TRANSITION_SUPPORTED,
        supporting_evidence_ids=(evidence_set_id,),
        blocking_evidence_ids=(),
        rationale=TransitionReason(message="Policy supports the proposed value."),
        evaluated_at=EVALUATED_AT,
        metadata={
            "policy_id": policy_id,
            "policy_kind": policy_kind,
            "applied_rule_id": rule.supported_transition_rule_id,
            "current_state_id": current_state.id if current_state else None,
            "effective_current_state_value": current_value.value,
            "proposed_state_value": proposed_value.value,
            "contributing_observation_ids": (observation_id,),
            "source_production_event_ids": (production_event_id,),
            "missing_current_state_assumed_inactive": current_state is None,
        },
    )
    context = OperationalStateAcceptanceContext(
        stage_id=stage_id,
        recording_block_id=block_id,
        organizational_anchor=BOUNDARY_ANCHOR,
    )
    lineage = OperationalStateAcceptanceLineage(
        evaluation_id=evaluation_id,
        policy_kind=policy_kind,
        policy_id=policy_id,
        applied_rule_id=rule.supported_transition_rule_id,
        evaluated_state_kind=kind,
        current_state_id=current_state.id if current_state else None,
        effective_current_value=current_value,
        proposed_state_value=proposed_value,
        supporting_evidence_set_ids=(evidence_set_id,),
        contributing_evidence_item_ids=(evidence_item_id,),
        contributing_observation_ids=(observation_id,),
        contributing_production_event_ids=(production_event_id,),
        contributing_signals=(EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,),
        satisfied_requirement_ids=(EntityId.new(),),
        interpreter_ids=(EntityId.new(),),
        interpretation_rule_ids=("ed0043.recording.start",),
        organizational_anchors=(BOUNDARY_ANCHOR,),
        context=context,
    )
    return OperationalStateAcceptanceRequest(
        evaluation=evaluation,
        lineage=lineage,
        current_state=current_state,
        target_subject=subject,
        history=OperationalStateAcceptanceHistory(),
        accepted_at=ACCEPTED_AT,
        context=context,
    )


def _accept(request: OperationalStateAcceptanceRequest):
    return OperationalStateAcceptance().accept(request)


@pytest.mark.parametrize(
    "outcome",
    [
        TransitionPolicyResult.TRANSITION_NOT_SUPPORTED,
        TransitionPolicyResult.INSUFFICIENT_EVIDENCE,
        TransitionPolicyResult.ALREADY_CURRENT,
        TransitionPolicyResult.UNKNOWN,
    ],
)
def test_only_transition_supported_evaluations_are_eligible(
    outcome: TransitionPolicyResult,
) -> None:
    request = _request()
    result = _accept(
        request=replace(request, evaluation=replace(request.evaluation, outcome=outcome))
    )

    assert result.outcome is OperationalStateAcceptanceOutcome.REJECTED_INELIGIBLE_EVALUATION
    assert (
        result.reasons[0].code
        is OperationalStateAcceptanceReasonCode.EVALUATION_OUTCOME_NOT_SUPPORTED
    )
    assert result.successor_state is None
    assert result.supersession is None


def test_supported_evaluation_requires_explicit_proposed_value() -> None:
    request = _request()
    result = _accept(replace(request, evaluation=replace(request.evaluation, proposed_state=None)))

    assert result.outcome is OperationalStateAcceptanceOutcome.REJECTED_INELIGIBLE_EVALUATION
    assert result.reasons[0].code is OperationalStateAcceptanceReasonCode.MISSING_PROPOSED_STATE


def test_unsupported_state_kind_is_rejected() -> None:
    request = _request()
    evaluation = replace(
        request.evaluation,
        evaluated_state_kind=OperationalStateKind.TRANSCRIPT_STATE,
    )
    lineage = replace(
        request.lineage,
        evaluated_state_kind=OperationalStateKind.TRANSCRIPT_STATE,
    )
    result = _accept(replace(request, evaluation=evaluation, lineage=lineage))

    assert result.outcome is OperationalStateAcceptanceOutcome.REJECTED_INVALID_TRANSITION
    assert result.reasons[0].code is OperationalStateAcceptanceReasonCode.UNSUPPORTED_STATE_KIND


@pytest.mark.parametrize(
    ("current_value", "proposed_value"),
    [
        (OperationalStateValue.INACTIVE, OperationalStateValue.ACTIVE),
        (OperationalStateValue.ACTIVE, OperationalStateValue.PAUSED),
        (OperationalStateValue.PAUSED, OperationalStateValue.ACTIVE),
        (OperationalStateValue.ACTIVE, OperationalStateValue.STOPPED),
        (OperationalStateValue.PAUSED, OperationalStateValue.STOPPED),
    ],
)
def test_all_recording_lifecycle_transitions_are_accepted(
    current_value: OperationalStateValue,
    proposed_value: OperationalStateValue,
) -> None:
    request = _request(current_value=current_value, proposed_value=proposed_value)
    result = _accept(request)

    assert result.outcome is OperationalStateAcceptanceOutcome.ACCEPTED
    assert result.successor_state is not None
    assert result.successor_state.family is OperationalStateFamily.DIRECTLY_OBSERVABLE
    assert result.successor_state.kind is OperationalStateKind.RECORDING_STATE
    assert result.successor_state.value is proposed_value


@pytest.mark.parametrize(
    ("current_value", "proposed_value", "rule_occurrence"),
    [
        (OperationalStateValue.INACTIVE, OperationalStateValue.ACTIVE, 0),
        (OperationalStateValue.ACTIVE, OperationalStateValue.ENDING, 0),
        (OperationalStateValue.ACTIVE, OperationalStateValue.ENDING, 1),
        (OperationalStateValue.ACTIVE, OperationalStateValue.ENDED, 0),
        (OperationalStateValue.ENDING, OperationalStateValue.ENDED, 0),
        (OperationalStateValue.ENDED, OperationalStateValue.ACTIVE, 0),
    ],
)
def test_all_session_policy_rules_for_supported_lifecycles_are_accepted(
    current_value: OperationalStateValue,
    proposed_value: OperationalStateValue,
    rule_occurrence: int,
) -> None:
    request = _request(
        kind=OperationalStateKind.SESSION_STATE,
        current_value=current_value,
        proposed_value=proposed_value,
        rule_occurrence=rule_occurrence,
    )
    result = _accept(request)

    assert result.outcome is OperationalStateAcceptanceOutcome.ACCEPTED
    assert result.successor_state is not None
    assert result.successor_state.family is OperationalStateFamily.EVIDENCE_DERIVED
    assert result.successor_state.kind is OperationalStateKind.SESSION_STATE
    assert result.successor_state.value is proposed_value


@pytest.mark.parametrize(
    ("kind", "current_value", "proposed_value"),
    [
        (
            OperationalStateKind.RECORDING_STATE,
            OperationalStateValue.STOPPED,
            OperationalStateValue.PAUSED,
        ),
        (
            OperationalStateKind.SESSION_STATE,
            OperationalStateValue.INACTIVE,
            OperationalStateValue.ENDING,
        ),
    ],
)
def test_invalid_lifecycle_is_rejected_before_rule_selection(
    kind: OperationalStateKind,
    current_value: OperationalStateValue,
    proposed_value: OperationalStateValue,
) -> None:
    valid = _request(kind=kind)
    subject = valid.target_subject
    current = OperationalState(
        id=EntityId.new(),
        family=_family_for(kind),
        kind=kind,
        subject=subject,
        value=current_value,
        status=OperationalStateStatus.CURRENT,
        basis=OperationalStateBasis(),
        observed_or_derived_at=EVALUATED_AT,
        recording_block_id=valid.context.recording_block_id,
        stage_id=valid.context.stage_id,
    )
    evaluation = replace(
        valid.evaluation,
        current_state=current,
        proposed_state=proposed_value,
        metadata={
            **valid.evaluation.metadata,
            "current_state_id": current.id,
            "effective_current_state_value": current_value.value,
            "proposed_state_value": proposed_value.value,
            "missing_current_state_assumed_inactive": False,
        },
    )
    lineage = replace(
        valid.lineage,
        current_state_id=current.id,
        effective_current_value=current_value,
        proposed_state_value=proposed_value,
    )
    result = _accept(replace(valid, evaluation=evaluation, lineage=lineage, current_state=current))

    assert result.outcome is OperationalStateAcceptanceOutcome.REJECTED_INVALID_TRANSITION
    assert (
        result.reasons[0].code is OperationalStateAcceptanceReasonCode.INVALID_LIFECYCLE_TRANSITION
    )


@pytest.mark.parametrize(
    ("field_name", "reason_code"),
    [
        ("policy_id", OperationalStateAcceptanceReasonCode.INVALID_POLICY_IDENTITY),
        ("applied_rule_id", OperationalStateAcceptanceReasonCode.INVALID_RULE_IDENTITY),
        (
            "supporting_evidence_set_ids",
            OperationalStateAcceptanceReasonCode.MISSING_SUPPORTING_EVIDENCE,
        ),
        (
            "contributing_evidence_item_ids",
            OperationalStateAcceptanceReasonCode.MISSING_SUPPORTING_EVIDENCE,
        ),
        (
            "contributing_observation_ids",
            OperationalStateAcceptanceReasonCode.MISSING_OBSERVATION_LINEAGE,
        ),
        (
            "contributing_production_event_ids",
            OperationalStateAcceptanceReasonCode.MISSING_EVENT_LINEAGE,
        ),
    ],
)
def test_required_first_class_lineage_is_enforced(
    field_name: str,
    reason_code: OperationalStateAcceptanceReasonCode,
) -> None:
    request = _request()
    missing_value = None if field_name in {"policy_id", "applied_rule_id"} else ()
    result = _accept(
        replace(request, lineage=replace(request.lineage, **{field_name: missing_value}))
    )

    assert result.outcome is OperationalStateAcceptanceOutcome.REJECTED_INVALID_LINEAGE
    assert result.reasons[0].code is reason_code


def test_policy_state_kind_and_rule_identity_mismatches_are_rejected() -> None:
    request = _request()
    wrong_policy = _accept(
        replace(
            request,
            lineage=replace(
                request.lineage,
                policy_kind=SESSION_TRANSITION_POLICY_KIND,
            ),
        )
    )
    other_rule = _acceptance_rule(
        OperationalStateKind.RECORDING_STATE,
        OperationalStateValue.ACTIVE,
        OperationalStateValue.PAUSED,
    )
    mismatched_rule = _accept(
        replace(
            request,
            evaluation=replace(
                request.evaluation,
                metadata={
                    **request.evaluation.metadata,
                    "applied_rule_id": other_rule.supported_transition_rule_id,
                },
            ),
            lineage=replace(
                request.lineage,
                applied_rule_id=other_rule.supported_transition_rule_id,
            ),
        )
    )

    assert wrong_policy.outcome is OperationalStateAcceptanceOutcome.REJECTED_INVALID_LINEAGE
    assert (
        wrong_policy.reasons[0].code is OperationalStateAcceptanceReasonCode.INVALID_POLICY_IDENTITY
    )
    assert mismatched_rule.outcome is OperationalStateAcceptanceOutcome.REJECTED_INVALID_LINEAGE
    assert (
        mismatched_rule.reasons[0].code
        is OperationalStateAcceptanceReasonCode.INVALID_RULE_IDENTITY
    )


def test_evaluation_identity_and_metadata_conflicts_are_rejected() -> None:
    request = _request()
    wrong_evaluation = _accept(
        replace(
            request,
            lineage=replace(request.lineage, evaluation_id=EntityId.new()),
        )
    )
    wrong_event = _accept(
        replace(
            request,
            evaluation=replace(
                request.evaluation,
                metadata={
                    **request.evaluation.metadata,
                    "source_production_event_ids": (EntityId.new(),),
                },
            ),
        )
    )

    assert wrong_evaluation.outcome is OperationalStateAcceptanceOutcome.REJECTED_INVALID_LINEAGE
    assert wrong_event.outcome is OperationalStateAcceptanceOutcome.REJECTED_INVALID_LINEAGE
    assert wrong_event.reasons[0].code is OperationalStateAcceptanceReasonCode.MISSING_EVENT_LINEAGE


def test_blocking_evidence_and_unmet_requirements_are_rejected() -> None:
    request = _request()
    blocker = EntityId.new()
    blocked = _accept(
        replace(
            request,
            evaluation=replace(request.evaluation, blocking_evidence_ids=(blocker,)),
            lineage=replace(request.lineage, blocking_evidence_set_ids=(blocker,)),
        )
    )
    unmet = _accept(
        replace(
            request,
            lineage=replace(request.lineage, unmet_requirement_ids=(EntityId.new(),)),
        )
    )

    assert blocked.outcome is OperationalStateAcceptanceOutcome.REJECTED_INVALID_LINEAGE
    assert (
        blocked.reasons[0].code is OperationalStateAcceptanceReasonCode.MISSING_SUPPORTING_EVIDENCE
    )
    assert unmet.outcome is OperationalStateAcceptanceOutcome.REJECTED_INVALID_LINEAGE
    assert unmet.reasons[0].code is OperationalStateAcceptanceReasonCode.INVALID_RULE_IDENTITY


def test_no_current_state_requires_explicit_effective_inactive_assumption() -> None:
    request = _request()
    invalid_value = _accept(
        replace(
            request,
            lineage=replace(
                request.lineage,
                effective_current_value=OperationalStateValue.ACTIVE,
            ),
        )
    )
    missing_flag = _accept(
        replace(
            request,
            evaluation=replace(
                request.evaluation,
                metadata={
                    **request.evaluation.metadata,
                    "missing_current_state_assumed_inactive": False,
                },
            ),
        )
    )

    assert invalid_value.outcome is OperationalStateAcceptanceOutcome.REJECTED_INVALID_LINEAGE
    assert missing_flag.outcome is OperationalStateAcceptanceOutcome.REJECTED_INVALID_CURRENT_STATE


@pytest.mark.parametrize(
    "status",
    [
        OperationalStateStatus.SUPERSEDED,
        OperationalStateStatus.ARCHIVED,
        OperationalStateStatus.EXPIRED,
        OperationalStateStatus.UNKNOWN,
    ],
)
def test_only_current_status_may_serve_as_predecessor(
    status: OperationalStateStatus,
) -> None:
    request = _request(
        current_value=OperationalStateValue.ACTIVE,
        proposed_value=OperationalStateValue.PAUSED,
    )
    assert request.current_state is not None
    current = replace(request.current_state, status=status)
    evaluation = replace(request.evaluation, current_state=current)
    result = _accept(replace(request, current_state=current, evaluation=evaluation))

    assert result.outcome is OperationalStateAcceptanceOutcome.REJECTED_INVALID_CURRENT_STATE
    assert (
        result.reasons[0].code is OperationalStateAcceptanceReasonCode.INVALID_CURRENT_STATE_STATUS
    )


def test_current_state_identity_family_value_and_subject_are_validated() -> None:
    request = _request(
        current_value=OperationalStateValue.ACTIVE,
        proposed_value=OperationalStateValue.PAUSED,
    )
    assert request.current_state is not None
    identity_mismatch = _accept(
        replace(request, current_state=replace(request.current_state, id=EntityId.new()))
    )
    wrong_family_state = replace(
        request.current_state,
        family=OperationalStateFamily.EVIDENCE_DERIVED,
    )
    wrong_family = _accept(
        replace(
            request,
            current_state=wrong_family_state,
            evaluation=replace(request.evaluation, current_state=wrong_family_state),
            lineage=replace(request.lineage, current_state_id=wrong_family_state.id),
        )
    )
    wrong_value_state = replace(
        request.current_state,
        value=OperationalStateValue.ENDED,
    )
    wrong_value = _accept(
        replace(
            request,
            current_state=wrong_value_state,
            evaluation=replace(request.evaluation, current_state=wrong_value_state),
        )
    )
    other_subject = replace(
        request.target_subject,
        subject_identifier=EntityId.new().to_json(),
    )
    wrong_subject = _accept(replace(request, target_subject=other_subject))

    assert (
        identity_mismatch.outcome
        is OperationalStateAcceptanceOutcome.REJECTED_INVALID_CURRENT_STATE
    )
    assert (
        wrong_family.reasons[0].code
        is OperationalStateAcceptanceReasonCode.INVALID_CURRENT_STATE_KIND
    )
    assert (
        wrong_value.reasons[0].code
        is OperationalStateAcceptanceReasonCode.INVALID_CURRENT_STATE_VALUE
    )
    assert wrong_subject.outcome is OperationalStateAcceptanceOutcome.REJECTED_INVALID_SUBJECT
    assert wrong_subject.reasons[0].code is OperationalStateAcceptanceReasonCode.SUBJECT_MISMATCH


@pytest.mark.parametrize(
    ("kind", "subject_type", "identifier"),
    [
        (
            OperationalStateKind.RECORDING_STATE,
            OperationalStateSubjectType.TRANSCRIPT_STREAM,
            "stream-a",
        ),
        (
            OperationalStateKind.SESSION_STATE,
            OperationalStateSubjectType.SCHEDULED_ACTIVITY,
            "schedule-a",
        ),
        (
            OperationalStateKind.RECORDING_STATE,
            OperationalStateSubjectType.RECORDING_BLOCK,
            "not-a-uuid",
        ),
    ],
)
def test_invalid_subjects_are_rejected(
    kind: OperationalStateKind,
    subject_type: OperationalStateSubjectType,
    identifier: str,
) -> None:
    request = _request(kind=kind)
    subject = OperationalStateSubject(subject_type, identifier)
    result = _accept(replace(request, target_subject=subject))

    assert result.outcome is OperationalStateAcceptanceOutcome.REJECTED_INVALID_SUBJECT
    assert result.reasons[0].code is OperationalStateAcceptanceReasonCode.INVALID_TARGET_SUBJECT


def test_media_artifact_and_session_candidate_subjects_are_accepted() -> None:
    recording = _request()
    media_subject = OperationalStateSubject(
        OperationalStateSubjectType.MEDIA_ARTIFACT,
        "artifact-a",
    )
    media_context = replace(recording.context, media_artifact_ids=("artifact-a",))
    media_result = _accept(
        replace(
            recording,
            target_subject=media_subject,
            context=media_context,
            lineage=replace(recording.lineage, context=media_context),
        )
    )
    session_result = _accept(_request(kind=OperationalStateKind.SESSION_STATE))

    assert media_result.outcome is OperationalStateAcceptanceOutcome.ACCEPTED
    assert media_result.successor_state is not None
    assert media_result.successor_state.subject is media_subject
    assert session_result.outcome is OperationalStateAcceptanceOutcome.ACCEPTED
    assert session_result.successor_state is not None
    assert (
        session_result.successor_state.subject.subject_type
        is OperationalStateSubjectType.SESSION_CANDIDATE
    )


@pytest.mark.parametrize(
    "kind", [OperationalStateKind.RECORDING_STATE, OperationalStateKind.SESSION_STATE]
)
def test_known_stage_or_recording_context_conflicts_are_rejected(
    kind: OperationalStateKind,
) -> None:
    request = _request(kind=kind)
    conflicting = replace(request.context, stage_id=EntityId.new())
    result = _accept(replace(request, context=conflicting))

    assert result.outcome is OperationalStateAcceptanceOutcome.REJECTED_CONTEXT_MISMATCH
    assert result.reasons[0].code is OperationalStateAcceptanceReasonCode.CONTEXT_MISMATCH


def test_known_history_prevents_duplicate_acceptance_without_global_claim() -> None:
    request = _request()
    history = OperationalStateAcceptanceHistory(
        accepted_evaluation_ids=(request.evaluation.id, request.evaluation.id),
        metadata={"scope": "caller_supplied_only"},
    )
    result = _accept(replace(request, history=history))

    assert history.accepted_evaluation_ids == (request.evaluation.id,)
    assert result.outcome is OperationalStateAcceptanceOutcome.ALREADY_ACCEPTED
    assert (
        result.reasons[0].code is OperationalStateAcceptanceReasonCode.EVALUATION_ALREADY_ACCEPTED
    )
    assert result.successor_state is None
    assert result.supersession is None
    assert result.metadata["known_history_only"] is True


def test_successor_preserves_lineage_and_distinct_timestamps() -> None:
    request = _request()
    result = _accept(request)
    successor = result.successor_state

    assert successor is not None
    assert successor.id != request.evaluation.id
    assert successor.status is OperationalStateStatus.CURRENT
    assert successor.observed_or_derived_at == EVALUATED_AT
    assert result.accepted_at == ACCEPTED_AT
    assert successor.metadata["accepted_at"] == ACCEPTED_AT.isoformat()
    assert successor.metadata["organizational_anchors"] == (BOUNDARY_ANCHOR,)
    assert successor.metadata["boundary_anchor_verified"] is False
    assert successor.basis.observation_ids == request.lineage.contributing_observation_ids
    assert successor.basis.evidence_set_ids == request.lineage.supporting_evidence_set_ids
    assert successor.basis.transition_evaluation_ids == (request.evaluation.id,)
    assert successor.basis.policy_ids == (request.lineage.policy_id,)
    assert successor.basis.transition_rule_ids == (request.lineage.applied_rule_id,)
    assert successor.basis.metadata["contributing_signals"] == (
        EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED.value,
    )
    assert successor.metadata["persisted"] is False
    assert result.metadata["transition_executed"] is False


def test_supersession_is_descriptive_and_predecessor_is_unchanged() -> None:
    request = _request(
        current_value=OperationalStateValue.ACTIVE,
        proposed_value=OperationalStateValue.PAUSED,
    )
    predecessor = request.current_state
    assert predecessor is not None
    before = predecessor
    result = _accept(request)

    assert predecessor == before
    assert predecessor.value is OperationalStateValue.ACTIVE
    assert predecessor.status is OperationalStateStatus.CURRENT
    assert result.successor_state is not None
    assert result.successor_state.id != predecessor.id
    assert result.supersession is not None
    assert result.supersession.predecessor_state_id == predecessor.id
    assert result.supersession.successor_state_id == result.successor_state.id
    assert result.supersession.transition_evaluation_id == request.evaluation.id
    assert result.supersession.accepted_at == ACCEPTED_AT
    assert result.supersession.metadata["persisted"] is False
    assert result.supersession.metadata["predecessor_mutated"] is False


def test_initial_acceptance_has_no_supersession_and_summary_is_traceable() -> None:
    request = _request()
    result = _accept(request)
    summary = OperationalStateAcceptanceSummary.from_result(
        result,
        evaluation_timestamp=request.evaluation.evaluated_at,
    )

    assert result.supersession is None
    assert summary.outcome is OperationalStateAcceptanceOutcome.ACCEPTED
    assert summary.evaluation_id == request.evaluation.id
    assert summary.policy_id == request.lineage.policy_id
    assert summary.transition_rule_id == request.lineage.applied_rule_id
    assert summary.acceptance_rule_id is not None
    assert summary.successor_state_id == result.successor_state.id  # type: ignore[union-attr]
    assert summary.accepted_at == ACCEPTED_AT
    assert summary.evaluation_timestamp == EVALUATED_AT
    assert summary.supersession_described is False
    assert summary.source_event_count == 1


def test_result_rejects_inconsistent_accepted_and_rejected_shapes() -> None:
    request = _request()
    accepted = _accept(request)
    rejected = _accept(
        replace(
            request,
            evaluation=replace(
                request.evaluation,
                outcome=TransitionPolicyResult.INSUFFICIENT_EVIDENCE,
            ),
        )
    )

    assert accepted.successor_state is not None
    with pytest.raises(ValueError, match="requires successor state"):
        replace(accepted, successor_state=None)
    with pytest.raises(ValueError, match="Non-accepted result"):
        replace(
            rejected,
            successor_state=accepted.successor_state,
        )


def test_repeated_semantic_inputs_have_deterministic_semantics() -> None:
    request = _request()
    first = _accept(request)
    second = _accept(request)

    assert first.outcome == second.outcome
    assert tuple(reason.code for reason in first.reasons) == tuple(
        reason.code for reason in second.reasons
    )
    assert first.applied_acceptance_rule_id == second.applied_acceptance_rule_id
    assert first.successor_state is not None
    assert second.successor_state is not None
    assert first.successor_state.family == second.successor_state.family
    assert first.successor_state.kind == second.successor_state.kind
    assert first.successor_state.subject == second.successor_state.subject
    assert first.successor_state.value == second.successor_state.value
    assert (
        first.successor_state.basis.observation_ids == second.successor_state.basis.observation_ids
    )
    assert (
        first.successor_state.basis.evidence_set_ids
        == second.successor_state.basis.evidence_set_ids
    )
