from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

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
from app.contexts.production.session_boundary_evidence_builder import (
    SessionBoundaryEvidenceContext,
    make_session_boundary_evidence_builder,
)
from app.contexts.production.session_transition_policy import (
    SESSION_TRANSITION_MAPPINGS,
    SESSION_TRANSITION_RULES,
    SUPPORTED_SESSION_TRANSITIONS,
    SessionTransitionContradictionBehavior,
    SessionTransitionEvidenceCategory,
    SessionTransitionEvidenceProfile,
    SessionTransitionMapping,
    SessionTransitionPolicy,
    SessionTransitionRequirement,
    SessionTransitionResult,
    SessionTransitionRule,
    SessionTransitionSummary,
    make_session_transition_policy,
    mapping_for_session_signal,
)
from app.contexts.production.transition_policy import (
    TransitionEvaluation,
    TransitionPolicyResult,
)
from app.shared.ids import CorrelationId, EntityId

BASE_TIME = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _state(
    value: OperationalStateValue,
    *,
    kind: OperationalStateKind = OperationalStateKind.SESSION_STATE,
    subject_type: OperationalStateSubjectType = (OperationalStateSubjectType.SESSION_CANDIDATE),
    evidence_set_ids: tuple[EntityId, ...] = (),
    recording_block_id: EntityId | None = None,
    metadata: dict[str, object] | None = None,
) -> OperationalState:
    return OperationalState(
        id=EntityId.new(),
        family=(
            OperationalStateFamily.EVIDENCE_DERIVED
            if kind is OperationalStateKind.SESSION_STATE
            else OperationalStateFamily.DIRECTLY_OBSERVABLE
        ),
        kind=kind,
        subject=OperationalStateSubject(
            subject_type=subject_type,
            subject_identifier=EntityId.new().to_json(),
        ),
        value=value,
        status=OperationalStateStatus.CURRENT,
        basis=OperationalStateBasis(evidence_set_ids=evidence_set_ids),
        observed_or_derived_at=BASE_TIME,
        recording_block_id=recording_block_id,
        metadata=metadata or {},
    )


def _boundary_evidence(
    concern: EvidenceConcern,
    signals: tuple[EvidenceSignal, ...],
    *,
    roles: tuple[EvidenceRole, ...] | None = None,
    observation_ids: tuple[EntityId, ...] | None = None,
    strengths: tuple[EvidenceStrength, ...] | None = None,
    evidence_set_id: EntityId | None = None,
    correlation_id: CorrelationId | None = None,
    recording_block_id: EntityId | None = None,
    stage_id: EntityId | None = None,
    scheduled_activity_id: EntityId | None = None,
    boundary_context_id: EntityId | None = None,
    anchor_seconds: float | None = 10.0,
    created_at: datetime = BASE_TIME,
) -> EvidenceSet:
    roles = roles or tuple(EvidenceRole.SUPPORTS for _signal in signals)
    observation_ids = observation_ids or tuple(EntityId.new() for _signal in signals)
    strengths = strengths or tuple(EvidenceStrength.MODERATE for _signal in signals)
    items = tuple(
        EvidenceItem(
            id=EntityId.new(),
            observation_id=observation_id,
            role=role,
            strength=strength,
            rationale="Structured Session Boundary Evidence contribution.",
        )
        for observation_id, role, strength in zip(
            observation_ids,
            roles,
            strengths,
            strict=True,
        )
    )
    references = tuple(
        EvidenceSignalReference(
            signal=signal,
            evidence_item_ids=(item.id,),
            observation_ids=(item.observation_id,),
            rationale="Boundary Signal remains non-conclusive.",
        )
        for signal, item in zip(signals, items, strict=True)
    )
    return EvidenceSet(
        id=evidence_set_id or EntityId.new(),
        recording_block_id=recording_block_id,
        concern=concern,
        purpose=EvidencePurpose.TRANSITION_SUPPORT,
        items=items,
        signals=references,
        correlation_id=correlation_id or CorrelationId.new(),
        created_at=created_at,
        metadata={
            "stage_id": stage_id.to_json() if stage_id is not None else None,
            "scheduled_activity_id": (
                scheduled_activity_id.to_json() if scheduled_activity_id is not None else None
            ),
            "boundary_context_id": (
                boundary_context_id.to_json() if boundary_context_id is not None else None
            ),
            "boundary_anchor_seconds": anchor_seconds,
            "final_boundary_timestamp": None,
        },
    )


def _start_evidence(**kwargs: object) -> EvidenceSet:
    return _boundary_evidence(
        EvidenceConcern.POSSIBLE_SESSION_START,
        (
            EvidenceSignal.SPEAKER_INTRODUCTION_INDICATED,
            EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
        ),
        **kwargs,  # type: ignore[arg-type]
    )


def _ended_evidence(**kwargs: object) -> EvidenceSet:
    return _boundary_evidence(
        EvidenceConcern.POSSIBLE_SESSION_END,
        (
            EvidenceSignal.SESSION_END_INDICATED,
            EvidenceSignal.TRANSCRIPT_END_INDICATED,
        ),
        **kwargs,  # type: ignore[arg-type]
    )


def test_policy_requirement_rule_mapping_profile_result_and_summary_creation() -> None:
    policy = make_session_transition_policy()
    requirement = SESSION_TRANSITION_RULES[0].requirements[0]
    rule = SESSION_TRANSITION_RULES[0]
    mapping = SESSION_TRANSITION_MAPPINGS[0]
    result = policy.evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(_start_evidence(),),
        evaluated_at=BASE_TIME,
    )
    summary = SessionTransitionSummary.from_result(result)

    assert isinstance(policy, SessionTransitionPolicy)
    assert isinstance(requirement, SessionTransitionRequirement)
    assert isinstance(rule, SessionTransitionRule)
    assert isinstance(mapping, SessionTransitionMapping)
    assert isinstance(result, SessionTransitionResult)
    assert isinstance(result.evaluation, TransitionEvaluation)
    assert isinstance(result.evidence_profile, SessionTransitionEvidenceProfile)
    assert summary.evaluation_outcome is TransitionPolicyResult.TRANSITION_SUPPORTED


@pytest.mark.parametrize(
    ("concern", "signal", "category"),
    [
        (
            EvidenceConcern.POSSIBLE_SESSION_START,
            EvidenceSignal.SPEAKER_INTRODUCTION_INDICATED,
            SessionTransitionEvidenceCategory.SESSION_SPECIFIC,
        ),
        (
            EvidenceConcern.POSSIBLE_SESSION_START,
            EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
            SessionTransitionEvidenceCategory.CONTINUITY_CONTEXT,
        ),
        (
            EvidenceConcern.POSSIBLE_SESSION_START,
            EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
            SessionTransitionEvidenceCategory.MEDIA_CORROBORATION,
        ),
        (
            EvidenceConcern.POSSIBLE_SESSION_START,
            EvidenceSignal.SCHEDULED_WINDOW_ACTIVE,
            SessionTransitionEvidenceCategory.SCHEDULE_CONTEXT,
        ),
        (
            EvidenceConcern.POSSIBLE_SESSION_END,
            EvidenceSignal.SESSION_END_INDICATED,
            SessionTransitionEvidenceCategory.END_SPECIFIC,
        ),
        (
            EvidenceConcern.POSSIBLE_SESSION_END,
            EvidenceSignal.RECORDING_END_INDICATED,
            SessionTransitionEvidenceCategory.END_CORROBORATION,
        ),
        (
            EvidenceConcern.POSSIBLE_SESSION_END,
            EvidenceSignal.MEDIA_FINALIZATION_INDICATED,
            SessionTransitionEvidenceCategory.END_CONTEXT,
        ),
    ],
)
def test_signal_to_policy_category_mappings(
    concern: EvidenceConcern,
    signal: EvidenceSignal,
    category: SessionTransitionEvidenceCategory,
) -> None:
    mapping = mapping_for_session_signal(concern, signal)

    assert mapping is not None
    assert mapping.category is category


def test_supported_transition_scope_is_narrow() -> None:
    assert (
        OperationalStateValue.INACTIVE,
        OperationalStateValue.ACTIVE,
    ) in SUPPORTED_SESSION_TRANSITIONS
    assert (
        OperationalStateValue.ACTIVE,
        OperationalStateValue.ENDED,
    ) in SUPPORTED_SESSION_TRANSITIONS
    assert (
        OperationalStateValue.ENDING,
        OperationalStateValue.ACTIVE,
    ) not in SUPPORTED_SESSION_TRANSITIONS
    assert (
        OperationalStateValue.INACTIVE,
        OperationalStateValue.ENDED,
    ) not in SUPPORTED_SESSION_TRANSITIONS


def test_rules_use_only_the_four_supported_session_lifecycle_values() -> None:
    rule_values = {
        value
        for rule in SESSION_TRANSITION_RULES
        for value in (rule.current_state_value, rule.proposed_state_value)
    }

    assert rule_values == {
        OperationalStateValue.INACTIVE,
        OperationalStateValue.ACTIVE,
        OperationalStateValue.ENDING,
        OperationalStateValue.ENDED,
    }


def test_rule_contract_rejects_transition_outside_supported_scope() -> None:
    requirement = SESSION_TRANSITION_RULES[0].requirements[0]
    with pytest.raises(ValueError, match="outside supported scope"):
        SessionTransitionRule(
            id=EntityId.new(),
            current_state_value=OperationalStateValue.INACTIVE,
            proposed_state_value=OperationalStateValue.ENDED,
            required_boundary_concern=EvidenceConcern.POSSIBLE_SESSION_END,
            requirements=(requirement,),
            allowed_evidence_roles=(EvidenceRole.SUPPORTS,),
            contradiction_behavior=SessionTransitionContradictionBehavior.BLOCK,
            rationale_template="Unsupported transition.",
        )


def test_inactive_to_active_requires_specific_and_independent_corroboration() -> None:
    evidence = _start_evidence()

    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(evidence,),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert result.proposed_state is OperationalStateValue.ACTIVE
    assert result.supporting_evidence_ids == (evidence.id,)
    assert len(result.satisfied_requirement_ids) == 2


def test_policy_consumes_actual_ed0039_boundary_evidence_output() -> None:
    block_id = EntityId.new()
    stage_id = EntityId.new()
    activity_id = EntityId.new()
    correlation_id = CorrelationId.new()
    introduction = _boundary_evidence(
        EvidenceConcern.VISUAL_TRANSITION_CONTEXT,
        (EvidenceSignal.SPEAKER_INTRODUCTION_INDICATED,),
        recording_block_id=block_id,
        stage_id=stage_id,
        scheduled_activity_id=activity_id,
        correlation_id=correlation_id,
        anchor_seconds=10.0,
    )
    speech = _boundary_evidence(
        EvidenceConcern.TRANSCRIPT_CONTINUITY,
        (EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,),
        recording_block_id=block_id,
        stage_id=stage_id,
        scheduled_activity_id=activity_id,
        correlation_id=correlation_id,
        anchor_seconds=20.0,
        created_at=BASE_TIME + timedelta(seconds=10),
    )
    boundary_result = make_session_boundary_evidence_builder().build((introduction, speech))

    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=boundary_result.start_boundary_evidence_sets,
        evaluated_at=BASE_TIME,
    )

    assert len(boundary_result.start_boundary_evidence_sets) == 1
    assert result.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert result.proposed_state is OperationalStateValue.ACTIVE


def test_missing_current_state_is_effective_inactive_without_creating_state() -> None:
    result = make_session_transition_policy().evaluate(
        current_state=None,
        evidence_sets=(_start_evidence(),),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert result.evaluation.current_state is None
    assert result.evaluation.metadata["effective_current_state_value"] == "inactive"
    assert result.evaluation.metadata["missing_current_state_assumed_inactive"] is True


@pytest.mark.parametrize(
    "signals",
    [
        (EvidenceSignal.SPEAKER_INTRODUCTION_INDICATED,),
        (EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,),
        (EvidenceSignal.SCHEDULED_WINDOW_ACTIVE,),
        (EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,),
        (EvidenceSignal.PRESENTATION_TRANSITION_INDICATED,),
    ],
)
def test_single_start_signal_is_insufficient(
    signals: tuple[EvidenceSignal, ...],
) -> None:
    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(_boundary_evidence(EvidenceConcern.POSSIBLE_SESSION_START, signals),),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE
    assert result.proposed_state is None


def test_recording_and_media_only_are_insufficient_for_active() -> None:
    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(
            _boundary_evidence(
                EvidenceConcern.POSSIBLE_SESSION_START,
                (
                    EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
                    EvidenceSignal.MEDIA_AVAILABILITY_INDICATED,
                ),
            ),
        ),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE
    assert result.proposed_state is None


@pytest.mark.parametrize(
    ("specific", "corroboration"),
    [
        (
            EvidenceSignal.PRESENTATION_TRANSITION_INDICATED,
            EvidenceSignal.TRANSCRIPT_CONTINUITY_INDICATED,
        ),
        (
            EvidenceSignal.SESSION_CONTENT_INDICATED,
            EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
        ),
    ],
)
def test_approved_independent_start_combinations_support_active(
    specific: EvidenceSignal,
    corroboration: EvidenceSignal,
) -> None:
    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(
            _boundary_evidence(
                EvidenceConcern.POSSIBLE_SESSION_START,
                (specific, corroboration),
            ),
        ),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert result.proposed_state is OperationalStateValue.ACTIVE


def test_start_context_only_is_insufficient_even_when_ed0039_grouped_it() -> None:
    evidence = _boundary_evidence(
        EvidenceConcern.POSSIBLE_SESSION_START,
        (
            EvidenceSignal.SCHEDULED_WINDOW_ACTIVE,
            EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
            EvidenceSignal.OPERATOR_ATTENTION_INDICATED,
        ),
    )

    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(evidence,),
        evaluated_at=BASE_TIME,
        metadata={"ed0039_composition_window_seconds": 300.0},
    )

    assert result.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE
    assert result.evaluation.metadata["caller_metadata"] == {
        "ed0039_composition_window_seconds": 300.0
    }


def test_same_observation_cannot_supply_start_and_corroboration_independently() -> None:
    observation_id = EntityId.new()
    evidence = _boundary_evidence(
        EvidenceConcern.POSSIBLE_SESSION_START,
        (
            EvidenceSignal.SPEAKER_INTRODUCTION_INDICATED,
            EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
        ),
        observation_ids=(observation_id, observation_id),
    )

    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(evidence,),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE
    assert result.evidence_profile is not None
    assert result.evidence_profile.independent_source_count == 1


def test_explicit_start_contradiction_blocks_satisfied_rule() -> None:
    evidence = _boundary_evidence(
        EvidenceConcern.POSSIBLE_SESSION_START,
        (
            EvidenceSignal.SPEAKER_INTRODUCTION_INDICATED,
            EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
            EvidenceSignal.SESSION_CONTENT_INDICATED,
        ),
        roles=(
            EvidenceRole.SUPPORTS,
            EvidenceRole.SUPPORTS,
            EvidenceRole.CONTRADICTS,
        ),
    )

    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(evidence,),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.TRANSITION_NOT_SUPPORTED
    assert result.blocking_evidence_ids == (evidence.id,)


def test_neutral_evidence_does_not_satisfy_a_start_requirement() -> None:
    evidence = _boundary_evidence(
        EvidenceConcern.POSSIBLE_SESSION_START,
        (
            EvidenceSignal.SPEAKER_INTRODUCTION_INDICATED,
            EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
        ),
        roles=(EvidenceRole.NEUTRAL, EvidenceRole.SUPPORTS),
    )

    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(evidence,),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE
    assert result.proposed_state is None


def test_absent_evidence_is_insufficient_not_contradictory() -> None:
    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE
    assert result.blocking_evidence_ids == ()
    assert result.evidence_profile is None


@pytest.mark.parametrize(
    "signal",
    [
        EvidenceSignal.SESSION_END_INDICATED,
        EvidenceSignal.TRANSCRIPT_END_INDICATED,
    ],
)
def test_active_to_ending_accepts_explicit_end_signal(signal: EvidenceSignal) -> None:
    evidence = _boundary_evidence(
        EvidenceConcern.POSSIBLE_SESSION_END,
        (signal,),
    )

    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.ACTIVE),
        evidence_sets=(evidence,),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert result.proposed_state is OperationalStateValue.ENDING


def test_recording_end_alone_does_not_support_ending() -> None:
    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.ACTIVE),
        evidence_sets=(
            _boundary_evidence(
                EvidenceConcern.POSSIBLE_SESSION_END,
                (EvidenceSignal.RECORDING_END_INDICATED,),
            ),
        ),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE


def test_recording_end_plus_independent_context_supports_ending() -> None:
    evidence = _boundary_evidence(
        EvidenceConcern.POSSIBLE_SESSION_END,
        (
            EvidenceSignal.RECORDING_END_INDICATED,
            EvidenceSignal.MEDIA_FINALIZATION_INDICATED,
        ),
        roles=(EvidenceRole.SUPPORTS, EvidenceRole.CONTEXTUALIZES),
    )

    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.ACTIVE),
        evidence_sets=(evidence,),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert result.proposed_state is OperationalStateValue.ENDING


@pytest.mark.parametrize(
    "current",
    [OperationalStateValue.ACTIVE, OperationalStateValue.ENDING],
)
def test_active_or_ending_to_ended_requires_two_independent_end_indications(
    current: OperationalStateValue,
) -> None:
    evidence = _ended_evidence()

    result = make_session_transition_policy().evaluate(
        current_state=_state(current),
        evidence_sets=(evidence,),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert result.proposed_state is OperationalStateValue.ENDED
    assert result.evidence_profile is not None
    assert result.evidence_profile.independent_source_count == 2


def test_active_to_ended_rule_precedes_ending_when_terminal_evidence_is_complete() -> None:
    evidence = _boundary_evidence(
        EvidenceConcern.POSSIBLE_SESSION_END,
        (
            EvidenceSignal.TRANSCRIPT_END_INDICATED,
            EvidenceSignal.SESSION_END_INDICATED,
        ),
    )
    active_ended_rule = next(
        rule
        for rule in SESSION_TRANSITION_RULES
        if rule.current_state_value is OperationalStateValue.ACTIVE
        and rule.proposed_state_value is OperationalStateValue.ENDED
    )

    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.ACTIVE),
        evidence_sets=(evidence,),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert result.proposed_state is OperationalStateValue.ENDED
    assert result.applied_rule_id == active_ended_rule.id


def test_ending_to_ended_accepts_transcript_end_plus_recording_end() -> None:
    evidence = _boundary_evidence(
        EvidenceConcern.POSSIBLE_SESSION_END,
        (
            EvidenceSignal.TRANSCRIPT_END_INDICATED,
            EvidenceSignal.RECORDING_END_INDICATED,
        ),
    )

    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.ENDING),
        evidence_sets=(evidence,),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert result.proposed_state is OperationalStateValue.ENDED


@pytest.mark.parametrize(
    "signal",
    [
        EvidenceSignal.RECORDING_PAUSE_INDICATED,
        EvidenceSignal.SCHEDULED_ACTIVITY_CHANGED,
        EvidenceSignal.MEDIA_FINALIZATION_INDICATED,
    ],
)
def test_isolated_end_context_signals_are_insufficient(signal: EvidenceSignal) -> None:
    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.ACTIVE),
        evidence_sets=(
            _boundary_evidence(
                EvidenceConcern.POSSIBLE_SESSION_END,
                (signal,),
                roles=(EvidenceRole.CONTEXTUALIZES,),
            ),
        ),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE
    assert result.proposed_state is None


def test_context_only_end_evidence_is_insufficient() -> None:
    evidence = _boundary_evidence(
        EvidenceConcern.POSSIBLE_SESSION_END,
        (
            EvidenceSignal.RECORDING_PAUSE_INDICATED,
            EvidenceSignal.SCHEDULED_ACTIVITY_CHANGED,
            EvidenceSignal.MEDIA_FINALIZATION_INDICATED,
        ),
        roles=(
            EvidenceRole.CONTEXTUALIZES,
            EvidenceRole.CONTEXTUALIZES,
            EvidenceRole.CONTEXTUALIZES,
        ),
    )

    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.ACTIVE),
        evidence_sets=(evidence,),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE
    assert result.proposed_state is None


def test_duplicate_observation_does_not_supply_independent_end_corroboration() -> None:
    observation_id = EntityId.new()
    evidence = _boundary_evidence(
        EvidenceConcern.POSSIBLE_SESSION_END,
        (
            EvidenceSignal.SESSION_END_INDICATED,
            EvidenceSignal.TRANSCRIPT_END_INDICATED,
        ),
        observation_ids=(observation_id, observation_id),
    )

    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.ACTIVE),
        evidence_sets=(evidence,),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert result.proposed_state is OperationalStateValue.ENDING
    assert result.evidence_profile is not None
    assert result.evidence_profile.independent_source_count == 1


def test_context_signal_can_corroborate_ended_but_not_establish_it_alone() -> None:
    sufficient = _boundary_evidence(
        EvidenceConcern.POSSIBLE_SESSION_END,
        (
            EvidenceSignal.SESSION_END_INDICATED,
            EvidenceSignal.MEDIA_FINALIZATION_INDICATED,
        ),
        roles=(EvidenceRole.SUPPORTS, EvidenceRole.CONTEXTUALIZES),
    )
    contextual_only = _boundary_evidence(
        EvidenceConcern.POSSIBLE_SESSION_END,
        (EvidenceSignal.MEDIA_FINALIZATION_INDICATED,),
        roles=(EvidenceRole.CONTEXTUALIZES,),
    )
    policy = make_session_transition_policy()

    supported = policy.evaluate(
        current_state=_state(OperationalStateValue.ACTIVE),
        evidence_sets=(sufficient,),
        evaluated_at=BASE_TIME,
    )
    insufficient = policy.evaluate(
        current_state=_state(OperationalStateValue.ACTIVE),
        evidence_sets=(contextual_only,),
        evaluated_at=BASE_TIME,
    )

    assert supported.proposed_state is OperationalStateValue.ENDED
    assert insufficient.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE


def test_ended_to_active_requires_fresh_start_context() -> None:
    prior_end_evidence_id = EntityId.new()
    current = _state(
        OperationalStateValue.ENDED,
        evidence_set_ids=(prior_end_evidence_id,),
    )
    fresh_start = _start_evidence()

    result = make_session_transition_policy().evaluate(
        current_state=current,
        evidence_sets=(fresh_start,),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert result.proposed_state is OperationalStateValue.ACTIVE


def test_ended_to_active_without_explicit_freshness_is_insufficient() -> None:
    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.ENDED),
        evidence_sets=(_start_evidence(),),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE
    assert len(result.unmet_requirement_ids) == 1


@pytest.mark.parametrize(
    ("current", "evidence"),
    [
        (OperationalStateValue.INACTIVE, _ended_evidence()),
        (OperationalStateValue.ENDING, _start_evidence()),
    ],
)
def test_unsupported_transitions_are_rejected(
    current: OperationalStateValue,
    evidence: EvidenceSet,
) -> None:
    result = make_session_transition_policy().evaluate(
        current_state=_state(current),
        evidence_sets=(evidence,),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.TRANSITION_NOT_SUPPORTED
    assert result.proposed_state is None
    assert "unsupported Session transition" in result.evaluation.rationale.message


@pytest.mark.parametrize(
    ("current", "evidence", "expected"),
    [
        (OperationalStateValue.ACTIVE, _start_evidence(), OperationalStateValue.ACTIVE),
        (
            OperationalStateValue.ENDING,
            _boundary_evidence(
                EvidenceConcern.POSSIBLE_SESSION_END,
                (EvidenceSignal.SESSION_END_INDICATED,),
            ),
            OperationalStateValue.ENDING,
        ),
        (OperationalStateValue.ENDED, _ended_evidence(), OperationalStateValue.ENDED),
    ],
)
def test_qualifying_current_value_returns_already_current(
    current: OperationalStateValue,
    evidence: EvidenceSet,
    expected: OperationalStateValue,
) -> None:
    result = make_session_transition_policy().evaluate(
        current_state=_state(current),
        evidence_sets=(evidence,),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.ALREADY_CURRENT
    assert result.proposed_state is expected


@pytest.mark.parametrize(
    "current_state",
    [
        _state(
            OperationalStateValue.ACTIVE,
            kind=OperationalStateKind.RECORDING_STATE,
            subject_type=OperationalStateSubjectType.RECORDING_BLOCK,
        ),
        _state(
            OperationalStateValue.ACTIVE,
            subject_type=OperationalStateSubjectType.STAGE,
        ),
        _state(OperationalStateValue.READY),
    ],
)
def test_invalid_current_state_returns_unknown(current_state: OperationalState) -> None:
    result = make_session_transition_policy().evaluate(
        current_state=current_state,
        evidence_sets=(_start_evidence(),),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.UNKNOWN
    assert result.proposed_state is None


def test_unrelated_unsupported_and_duplicate_inputs_are_reported() -> None:
    supported = _start_evidence()
    unrelated = _boundary_evidence(
        EvidenceConcern.RECORDING_COVERAGE,
        (EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,),
    )
    unsupported = _boundary_evidence(
        EvidenceConcern.POSSIBLE_SESSION_START,
        (EvidenceSignal.EDITORIAL_INTEREST_INDICATED,),
    )

    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(supported, supported, unrelated, unsupported),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert result.duplicate_evidence_set_ids == (supported.id,)
    assert result.ignored_evidence_set_ids == (unrelated.id,)
    assert result.unsupported_evidence_set_ids == (unsupported.id,)


def test_multiple_incompatible_qualifying_contexts_are_ambiguous() -> None:
    first = _start_evidence(boundary_context_id=EntityId.new())
    second = _start_evidence(
        boundary_context_id=EntityId.new(),
        created_at=BASE_TIME + timedelta(minutes=10),
        anchor_seconds=610.0,
    )

    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(first, second),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE
    assert result.evidence_profile is None
    assert "Multiple incompatible" in result.evaluation.rationale.message


def test_competing_start_and_end_rules_for_active_state_are_ambiguous() -> None:
    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.ACTIVE),
        evidence_sets=(_start_evidence(), _ended_evidence()),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE
    assert result.proposed_state is None


def test_explicit_shared_boundary_context_allows_cross_set_corroboration() -> None:
    context_id = EntityId.new()
    block_id = EntityId.new()
    stage_id = EntityId.new()
    activity_id = EntityId.new()
    correlation_id = CorrelationId.new()
    specific = _boundary_evidence(
        EvidenceConcern.POSSIBLE_SESSION_START,
        (EvidenceSignal.SPEAKER_INTRODUCTION_INDICATED,),
        boundary_context_id=context_id,
        recording_block_id=block_id,
        stage_id=stage_id,
        scheduled_activity_id=activity_id,
        correlation_id=correlation_id,
    )
    corroboration = _boundary_evidence(
        EvidenceConcern.POSSIBLE_SESSION_START,
        (EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,),
        boundary_context_id=context_id,
        recording_block_id=block_id,
        stage_id=stage_id,
        scheduled_activity_id=activity_id,
        correlation_id=correlation_id,
    )

    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(specific, corroboration),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert set(result.supporting_evidence_ids) == {specific.id, corroboration.id}


def test_explicit_evaluation_context_selects_one_compatible_candidate() -> None:
    block_id = EntityId.new()
    stage_id = EntityId.new()
    activity_id = EntityId.new()
    context_id = EntityId.new()
    selected = _start_evidence(
        recording_block_id=block_id,
        stage_id=stage_id,
        scheduled_activity_id=activity_id,
        boundary_context_id=context_id,
    )
    other = _start_evidence(boundary_context_id=EntityId.new())
    context = SessionBoundaryEvidenceContext(
        id=context_id,
        boundary_concern=EvidenceConcern.POSSIBLE_SESSION_START,
        recording_block_id=block_id,
        stage_id=stage_id,
        scheduled_activity_id=activity_id,
    )

    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(other, selected),
        evaluation_context=context,
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert result.supporting_evidence_ids == (selected.id,)
    assert other.id in result.metadata["context_excluded_evidence_set_ids"]


def test_different_known_stages_are_not_combined() -> None:
    correlation_id = CorrelationId.new()
    specific = _boundary_evidence(
        EvidenceConcern.POSSIBLE_SESSION_START,
        (EvidenceSignal.SPEAKER_INTRODUCTION_INDICATED,),
        correlation_id=correlation_id,
        stage_id=EntityId.new(),
    )
    corroboration = _boundary_evidence(
        EvidenceConcern.POSSIBLE_SESSION_START,
        (EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,),
        correlation_id=correlation_id,
        stage_id=EntityId.new(),
    )

    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(specific, corroboration),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE


@pytest.mark.parametrize(
    "incompatible_dimension",
    ["recording_block", "scheduled_activity", "correlation"],
)
def test_incompatible_known_context_dimensions_are_not_combined(
    incompatible_dimension: str,
) -> None:
    context_id = EntityId.new()
    correlation_id = CorrelationId.new()
    block_id = EntityId.new()
    activity_id = EntityId.new()
    specific_kwargs: dict[str, object] = {
        "boundary_context_id": context_id,
        "correlation_id": correlation_id,
        "recording_block_id": block_id,
        "scheduled_activity_id": activity_id,
    }
    corroboration_kwargs = dict(specific_kwargs)
    if incompatible_dimension == "recording_block":
        corroboration_kwargs["recording_block_id"] = EntityId.new()
    elif incompatible_dimension == "scheduled_activity":
        corroboration_kwargs["scheduled_activity_id"] = EntityId.new()
    else:
        corroboration_kwargs["correlation_id"] = CorrelationId.new()

    specific = _boundary_evidence(
        EvidenceConcern.POSSIBLE_SESSION_START,
        (EvidenceSignal.SPEAKER_INTRODUCTION_INDICATED,),
        **specific_kwargs,  # type: ignore[arg-type]
    )
    corroboration = _boundary_evidence(
        EvidenceConcern.POSSIBLE_SESSION_START,
        (EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,),
        **corroboration_kwargs,  # type: ignore[arg-type]
    )

    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(specific, corroboration),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE
    assert result.proposed_state is None


def test_unknown_boundary_context_is_kept_conservative_across_evidence_sets() -> None:
    correlation_id = CorrelationId.new()
    specific = _boundary_evidence(
        EvidenceConcern.POSSIBLE_SESSION_START,
        (EvidenceSignal.SPEAKER_INTRODUCTION_INDICATED,),
        correlation_id=correlation_id,
        boundary_context_id=None,
    )
    corroboration = _boundary_evidence(
        EvidenceConcern.POSSIBLE_SESSION_START,
        (EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,),
        correlation_id=correlation_id,
        boundary_context_id=None,
    )

    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(specific, corroboration),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE
    assert result.proposed_state is None


def test_strength_is_preserved_but_not_used_as_a_gate_or_score() -> None:
    evidence = _start_evidence(
        strengths=(EvidenceStrength.WEAK, EvidenceStrength.UNKNOWN),
    )

    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(evidence,),
        evaluated_at=BASE_TIME,
    )

    assert result.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert result.evidence_profile is not None
    assert result.evidence_profile.strengths == (
        EvidenceStrength.WEAK,
        EvidenceStrength.UNKNOWN,
    )
    assert result.evidence_profile.metadata["strength_used_as_gate"] is False


def test_traceability_and_evaluation_timestamp_are_preserved() -> None:
    evidence = _start_evidence(anchor_seconds=42.0)
    evaluation_time = BASE_TIME + timedelta(hours=1)

    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(evidence,),
        evaluated_at=evaluation_time,
    )
    profile = result.evidence_profile

    assert profile is not None
    assert profile.contributing_evidence_set_ids == (evidence.id,)
    assert profile.contributing_evidence_item_ids == tuple(item.id for item in evidence.items)
    assert profile.contributing_observation_ids == tuple(
        item.observation_id for item in evidence.items
    )
    assert result.evaluation.evaluated_at == evaluation_time
    assert result.evaluation.metadata["organizational_anchors"] == ("42.0",)
    assert result.evaluation.metadata["final_boundary_timestamp"] is None


def test_applied_rule_and_requirement_trace_is_preserved_for_success_and_failure() -> None:
    policy = make_session_transition_policy()
    supported = policy.evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(_start_evidence(),),
        evaluated_at=BASE_TIME,
    )
    insufficient = policy.evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(
            _boundary_evidence(
                EvidenceConcern.POSSIBLE_SESSION_START,
                (EvidenceSignal.SPEAKER_INTRODUCTION_INDICATED,),
            ),
        ),
        evaluated_at=BASE_TIME,
    )

    assert supported.applied_rule_id is not None
    assert supported.satisfied_requirement_ids
    assert supported.unmet_requirement_ids == ()
    assert supported.evaluation.metadata["applied_rule_id"] == (supported.applied_rule_id.to_json())
    assert insufficient.applied_rule_id is not None
    assert insufficient.unmet_requirement_ids
    assert insufficient.evaluation.metadata["unmet_requirement_ids"] == tuple(
        requirement_id.to_json() for requirement_id in insufficient.unmet_requirement_ids
    )


def test_profiles_and_results_use_id_references_without_inventing_session_identity() -> None:
    result = make_session_transition_policy().evaluate(
        current_state=_state(OperationalStateValue.INACTIVE),
        evidence_sets=(_start_evidence(),),
        evaluated_at=BASE_TIME,
    )
    profile = result.evidence_profile

    assert profile is not None
    id_sequences = (
        profile.contributing_evidence_set_ids,
        profile.contributing_evidence_item_ids,
        profile.contributing_observation_ids,
        profile.recording_block_ids,
        profile.stage_ids,
        profile.scheduled_activity_ids,
        result.satisfied_requirement_ids,
        result.unmet_requirement_ids,
    )
    assert all(isinstance(item, EntityId) for sequence in id_sequences for item in sequence)
    assert "session_id" not in {field.name for field in fields(type(profile))}
    assert "session_id" not in {field.name for field in fields(type(result))}
    assert "session_id" not in result.evaluation.metadata


def test_policy_is_deterministic_and_does_not_mutate_inputs() -> None:
    current = _state(OperationalStateValue.INACTIVE)
    evidence = _start_evidence()
    policy = make_session_transition_policy(policy_id=EntityId.new())
    items_before = evidence.items
    state_before = current

    first = policy.evaluate(
        current_state=current,
        evidence_sets=(evidence,),
        evaluated_at=BASE_TIME,
    )
    second = policy.evaluate(
        current_state=current,
        evidence_sets=(evidence,),
        evaluated_at=BASE_TIME,
    )

    assert first == second
    assert evidence.items == items_before
    assert current == state_before
    assert first.evaluation.metadata["transition_executed"] is False


def test_equal_timestamps_and_missing_anchors_have_stable_input_ordering() -> None:
    first_evidence = _start_evidence(
        boundary_context_id=EntityId.new(),
        anchor_seconds=None,
        created_at=BASE_TIME,
    )
    second_evidence = _start_evidence(
        boundary_context_id=EntityId.new(),
        anchor_seconds=None,
        created_at=BASE_TIME,
    )
    current = _state(OperationalStateValue.INACTIVE)
    policy = make_session_transition_policy(policy_id=EntityId.new())

    forward = policy.evaluate(
        current_state=current,
        evidence_sets=(first_evidence, second_evidence),
        evaluated_at=BASE_TIME,
    )
    reverse = policy.evaluate(
        current_state=current,
        evidence_sets=(second_evidence, first_evidence),
        evaluated_at=BASE_TIME,
    )

    assert forward == reverse
    assert forward.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE


def test_contracts_are_immutable_and_non_scoring() -> None:
    rule = SESSION_TRANSITION_RULES[0]
    with pytest.raises(FrozenInstanceError):
        rule.rationale_template = "changed"  # type: ignore[misc]

    contract_fields = {
        field.name
        for contract in (
            SessionTransitionRequirement,
            SessionTransitionRule,
            SessionTransitionEvidenceProfile,
            SessionTransitionResult,
            SessionTransitionSummary,
        )
        for field in fields(contract)
    }
    forbidden = {"score", "probability", "confidence", "weight", "rank"}
    assert not any(term in name for name in contract_fields for term in forbidden)
    assert rule.contradiction_behavior is SessionTransitionContradictionBehavior.BLOCK


def test_policy_has_no_execution_infrastructure_or_downstream_reasoning() -> None:
    implementation = (
        Path(__file__).parents[1]
        / "app"
        / "contexts"
        / "production"
        / "session_transition_policy"
        / "session_transition_policy.py"
    ).read_text()
    forbidden_imports = (
        "event import",
        "observation import",
        "session import",
        "hypothesis import",
        "finding import",
        "verification import",
        "operational_product import",
        "repository import",
        "fastapi import",
        "sqlalchemy import",
    )

    assert not any(term in implementation.lower() for term in forbidden_imports)
    assert ".build(" not in implementation
    assert "make_session_boundary_evidence_builder" not in implementation
    assert "final_boundary_timestamp" in implementation
    assert '"final_boundary_timestamp": none' in implementation.lower()
    method_names = {name for name in vars(SessionTransitionPolicy) if not name.startswith("__")}
    assert not method_names.intersection(
        {"execute", "persist", "mutate", "dispatch", "enqueue", "create_session"}
    )
