from dataclasses import fields, replace
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
    RecordingTransitionContext,
    RecordingTransitionEvidenceProfile,
    RecordingTransitionPolicy,
    RecordingTransitionResult,
    RecordingTransitionRule,
    RecordingTransitionSummary,
    mapping_for_recording_marker,
    mapping_for_recording_signal,
)
from app.contexts.production.transition_policy import TransitionPolicyResult
from app.shared.ids import CorrelationId, EntityId


def _state(
    value: OperationalStateValue,
    *,
    recording_block_id: EntityId | None = None,
    stage_id: EntityId | None = None,
    kind: OperationalStateKind = OperationalStateKind.RECORDING_STATE,
    subject_type: OperationalStateSubjectType = OperationalStateSubjectType.RECORDING_BLOCK,
    subject_identifier: str | None = None,
    status: OperationalStateStatus = OperationalStateStatus.CURRENT,
    family: OperationalStateFamily = OperationalStateFamily.DIRECTLY_OBSERVABLE,
) -> OperationalState:
    block = recording_block_id or EntityId.new()
    identifier = subject_identifier
    if identifier is None:
        identifier = (
            block.to_json()
            if subject_type is OperationalStateSubjectType.RECORDING_BLOCK
            else "stageflow"
        )
    return OperationalState(
        id=EntityId.new(),
        family=family,
        kind=kind,
        subject=OperationalStateSubject(
            subject_type=subject_type,
            subject_identifier=identifier,
        ),
        value=value,
        status=status,
        basis=OperationalStateBasis(observation_ids=(EntityId.new(),)),
        observed_or_derived_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        recording_block_id=(
            block if subject_type is OperationalStateSubjectType.RECORDING_BLOCK else None
        ),
        stage_id=stage_id,
    )


def _evidence(
    *,
    signal: EvidenceSignal | None,
    concern: EvidenceConcern = EvidenceConcern.RECORDING_COVERAGE,
    role: EvidenceRole = EvidenceRole.SUPPORTS,
    marker: str | None = None,
    recording_block_id: EntityId | None = None,
    stage_id: EntityId | None = None,
    correlation_id: CorrelationId | None = None,
    artifact_id: str | None = None,
    created_at: datetime | None = None,
    timeline_end: float | None = None,
    evidence_set_id: EntityId | None = None,
    signal_references: tuple[EvidenceSignalReference, ...] | None = None,
    items: tuple[EvidenceItem, ...] | None = None,
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
        metadata=(
            {"timeline_offset_seconds": timeline_end}
            if timeline_end is not None
            else {}
        ),
    )
    retained_items = items or (item,)
    references = signal_references
    if references is None:
        references = (
            (
                EvidenceSignalReference(
                    signal=signal,
                    evidence_item_ids=(retained_items[0].id,),
                    observation_ids=(retained_items[0].observation_id,),
                ),
            )
            if signal is not None
            else ()
        )
    metadata: dict[str, object] = {}
    if marker is not None:
        metadata["recording_transition_marker"] = marker
    if stage_id is not None:
        metadata["stage_id"] = stage_id.to_json()
    if artifact_id is not None:
        metadata["artifact_id"] = artifact_id
    return EvidenceSet(
        id=evidence_set_id or EntityId.new(),
        recording_block_id=recording_block_id,
        concern=concern,
        purpose=EvidencePurpose.TRANSITION_SUPPORT,
        items=retained_items,
        signals=references,
        correlation_id=correlation_id or CorrelationId.new(),
        created_at=created_at or datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        metadata=metadata,
    )


def _evaluation(
    current_value: OperationalStateValue,
    signal: EvidenceSignal,
) -> tuple[OperationalState, EvidenceSet]:
    block = EntityId.new()
    return (
        _state(current_value, recording_block_id=block),
        _evidence(signal=signal, recording_block_id=block),
    )


def test_recording_transition_context_is_immutable_id_only_and_hashable() -> None:
    block = EntityId.new()
    context = RecordingTransitionContext(
        recording_block_id=block,
        stage_id=EntityId.new(),
        correlation_id=CorrelationId.new(),
        source_evidence_set_id=EntityId.new(),
        timeline_range_seconds=(5.0, 10.0),
    )

    assert context.has_recording_identity
    assert context in {context}
    assert context.recording_block_id == block
    assert context.timeline_range_seconds == (5.0, 10.0)


def test_recording_transition_policy_creation_and_result_contract() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    result = policy.evaluate_result(current_state=None, evidence_sets=())

    assert policy.name == "Recording Transition Policy"
    assert policy.evaluated_state_kind is OperationalStateKind.RECORDING_STATE
    assert len(policy.rules) == 4
    assert isinstance(result, RecordingTransitionResult)
    assert isinstance(result.evidence_profile, RecordingTransitionEvidenceProfile)


def test_existing_valid_recording_lifecycle_transitions_are_preserved() -> None:
    cases = (
        (
            OperationalStateValue.INACTIVE,
            EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
            OperationalStateValue.ACTIVE,
        ),
        (
            OperationalStateValue.ACTIVE,
            EvidenceSignal.RECORDING_PAUSE_INDICATED,
            OperationalStateValue.PAUSED,
        ),
        (
            OperationalStateValue.PAUSED,
            EvidenceSignal.RECORDING_CONTINUITY_RESTORED,
            OperationalStateValue.ACTIVE,
        ),
        (
            OperationalStateValue.ACTIVE,
            EvidenceSignal.RECORDING_END_INDICATED,
            OperationalStateValue.STOPPED,
        ),
        (
            OperationalStateValue.PAUSED,
            EvidenceSignal.RECORDING_END_INDICATED,
            OperationalStateValue.STOPPED,
        ),
    )
    policy = RecordingTransitionPolicy(id=EntityId.new())

    for current_value, signal, proposed_value in cases:
        current_state, evidence = _evaluation(current_value, signal)
        evaluation = policy.evaluate(
            current_state=current_state,
            evidence_sets=(evidence,),
        )

        assert evaluation.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
        assert evaluation.proposed_state is proposed_value
        assert evaluation.supporting_evidence_ids == (evidence.id,)
        assert evaluation.metadata["applied_rule_id"] is not None


def test_missing_current_state_is_explicitly_assumed_inactive() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    evidence = _evidence(signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED)

    result = policy.evaluate_result(current_state=None, evidence_sets=(evidence,))

    assert result.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert result.proposed_state is OperationalStateValue.ACTIVE
    assert result.evaluation.metadata["missing_current_state_assumed_inactive"] is True
    assert result.evidence_profile.current_state_validation == "absent_assumed_inactive"


def test_already_current_is_preserved_for_supported_values() -> None:
    cases = (
        (OperationalStateValue.ACTIVE, EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED),
        (OperationalStateValue.PAUSED, EvidenceSignal.RECORDING_PAUSE_INDICATED),
        (OperationalStateValue.STOPPED, EvidenceSignal.RECORDING_END_INDICATED),
    )
    policy = RecordingTransitionPolicy(id=EntityId.new())

    for value, signal in cases:
        current_state, evidence = _evaluation(value, signal)
        evaluation = policy.evaluate(current_state=current_state, evidence_sets=(evidence,))

        assert evaluation.outcome is TransitionPolicyResult.ALREADY_CURRENT
        assert evaluation.proposed_state is value


def test_unsupported_lifecycle_combinations_are_not_silently_supported() -> None:
    cases = (
        (OperationalStateValue.STOPPED, EvidenceSignal.RECORDING_PAUSE_INDICATED),
        (OperationalStateValue.INACTIVE, EvidenceSignal.RECORDING_CONTINUITY_RESTORED),
        (OperationalStateValue.PAUSED, EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED),
    )
    policy = RecordingTransitionPolicy(id=EntityId.new())

    for value, signal in cases:
        current_state, evidence = _evaluation(value, signal)
        evaluation = policy.evaluate(current_state=current_state, evidence_sets=(evidence,))

        assert evaluation.outcome is TransitionPolicyResult.TRANSITION_NOT_SUPPORTED


def test_different_recording_blocks_return_insufficient_without_a_rule_winner() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    first = _evidence(
        signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
        recording_block_id=EntityId.new(),
    )
    second = _evidence(
        signal=EvidenceSignal.RECORDING_END_INDICATED,
        recording_block_id=EntityId.new(),
    )

    result = policy.evaluate_result(current_state=None, evidence_sets=(second, first))

    assert result.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE
    assert result.proposed_state is None
    assert result.ambiguity_reasons == ("multiple_incompatible_recording_contexts",)
    assert len(result.evidence_profile.conflicting_contexts) == 2
    assert set(result.evidence_profile.conflicting_evidence_set_ids) == {first.id, second.id}
    assert set(result.evaluation.metadata["conflicting_evidence_ids"]) == {
        first.id.to_json(),
        second.id.to_json(),
    }
    assert result.evaluation.metadata["applied_rule_id"] is None


def test_different_stages_return_insufficient_even_when_timeline_is_nearby() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    block = EntityId.new()
    first = _evidence(
        signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
        recording_block_id=block,
        stage_id=EntityId.new(),
        timeline_end=10.0,
    )
    second = _evidence(
        signal=EvidenceSignal.RECORDING_PAUSE_INDICATED,
        recording_block_id=block,
        stage_id=EntityId.new(),
        timeline_end=11.0,
    )

    evaluation = policy.evaluate(current_state=None, evidence_sets=(first, second))

    assert evaluation.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE
    assert "incompatible recording contexts" in evaluation.rationale.message


def test_same_recording_block_and_stage_are_one_compatible_context() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    block = EntityId.new()
    stage = EntityId.new()
    current = _state(OperationalStateValue.ACTIVE, recording_block_id=block, stage_id=stage)
    first = _evidence(
        signal=EvidenceSignal.RECORDING_PAUSE_INDICATED,
        recording_block_id=block,
        stage_id=stage,
    )
    second = _evidence(
        signal=EvidenceSignal.RECORDING_PAUSE_INDICATED,
        recording_block_id=block,
        stage_id=stage,
        correlation_id=CorrelationId.new(),
    )

    result = policy.evaluate_result(current_state=current, evidence_sets=(first, second))

    assert result.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert result.proposed_state is OperationalStateValue.PAUSED
    assert set(result.evaluation.supporting_evidence_ids) == {first.id, second.id}
    assert result.evidence_profile.metadata["correlation_used_as_recording_identity"] is False


def test_known_and_unknown_contexts_are_not_merged() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    known = _evidence(
        signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
        recording_block_id=EntityId.new(),
    )
    unknown = _evidence(signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED)

    evaluation = policy.evaluate(current_state=None, evidence_sets=(known, unknown))

    assert evaluation.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE


def test_unknown_contexts_can_combine_only_for_one_compatible_signal() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    first = _evidence(signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED)
    second = _evidence(signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED)

    evaluation = policy.evaluate(current_state=None, evidence_sets=(first, second))

    assert evaluation.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert set(evaluation.supporting_evidence_ids) == {first.id, second.id}


def test_unknown_contexts_with_conflicting_signals_are_insufficient() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    first = _evidence(signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED)
    second = _evidence(signal=EvidenceSignal.RECORDING_END_INDICATED)

    evaluation = policy.evaluate(current_state=None, evidence_sets=(first, second))

    assert evaluation.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE
    assert "conflicting lifecycle Signals" in evaluation.rationale.message


def test_media_artifact_identity_is_secondary_to_a_shared_recording_block() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    block = EntityId.new()
    first = _evidence(
        signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
        recording_block_id=block,
        artifact_id="segment-a.mov",
    )
    second = _evidence(
        signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
        recording_block_id=block,
        artifact_id="segment-b.mov",
    )
    unrelated_artifact = _evidence(
        signal=EvidenceSignal.RECORDING_END_INDICATED,
        artifact_id="other-recording.mov",
    )

    assert policy.evaluate(current_state=None, evidence_sets=(first, second)).outcome is (
        TransitionPolicyResult.TRANSITION_SUPPORTED
    )
    assert policy.evaluate(
        current_state=None,
        evidence_sets=(first, unrelated_artifact),
    ).outcome is (
        TransitionPolicyResult.INSUFFICIENT_EVIDENCE
    )


def test_current_state_kind_subject_value_and_status_are_validated() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    block = EntityId.new()
    evidence = _evidence(
        signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
        recording_block_id=block,
    )
    invalid_states = (
        _state(
            OperationalStateValue.ACTIVE,
            recording_block_id=block,
            kind=OperationalStateKind.SESSION_STATE,
            subject_type=OperationalStateSubjectType.SESSION_CANDIDATE,
            subject_identifier="session-candidate",
            family=OperationalStateFamily.EVIDENCE_DERIVED,
        ),
        _state(
            OperationalStateValue.ACTIVE,
            recording_block_id=block,
            subject_type=OperationalStateSubjectType.TRANSCRIPT_STREAM,
            subject_identifier="transcript-stream",
        ),
        _state(
            OperationalStateValue.ENDING,
            recording_block_id=block,
        ),
        _state(
            OperationalStateValue.ACTIVE,
            recording_block_id=block,
            subject_identifier="not-an-entity-id",
        ),
        _state(
            OperationalStateValue.ACTIVE,
            recording_block_id=block,
            status=OperationalStateStatus.SUPERSEDED,
        ),
    )

    for current_state in invalid_states:
        evaluation = policy.evaluate(current_state=current_state, evidence_sets=(evidence,))
        assert evaluation.outcome is TransitionPolicyResult.UNKNOWN
        assert evaluation.proposed_state is None
        assert evaluation.metadata["current_state_validation"] != "valid"


def test_current_state_context_mismatch_is_not_supported() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    current = _state(OperationalStateValue.INACTIVE, recording_block_id=EntityId.new())
    evidence = _evidence(
        signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
        recording_block_id=EntityId.new(),
    )

    evaluation = policy.evaluate(current_state=current, evidence_sets=(evidence,))

    assert evaluation.outcome is TransitionPolicyResult.TRANSITION_NOT_SUPPORTED
    assert "different recording block" in evaluation.rationale.message


def test_explicit_contradiction_only_blocks_the_signal_item_it_links() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    block = EntityId.new()
    supports = EvidenceItem(
        id=EntityId.new(),
        observation_id=EntityId.new(),
        role=EvidenceRole.SUPPORTS,
        strength=EvidenceStrength.STRONG,
    )
    unrelated_contradiction = EvidenceItem(
        id=EntityId.new(),
        observation_id=EntityId.new(),
        role=EvidenceRole.CONTRADICTS,
        strength=EvidenceStrength.CONTRADICTORY,
    )
    evidence = _evidence(
        signal=None,
        recording_block_id=block,
        items=(supports, unrelated_contradiction),
        signal_references=(
            EvidenceSignalReference(
                signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
                evidence_item_ids=(supports.id,),
            ),
        ),
    )

    evaluation = policy.evaluate(
        current_state=_state(OperationalStateValue.INACTIVE, recording_block_id=block),
        evidence_sets=(evidence,),
    )

    assert evaluation.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert evaluation.blocking_evidence_ids == ()


def test_linked_contradictory_recording_signal_blocks_transition() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    block = EntityId.new()
    evidence = _evidence(
        signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
        role=EvidenceRole.CONTRADICTS,
        recording_block_id=block,
    )

    evaluation = policy.evaluate(
        current_state=_state(OperationalStateValue.INACTIVE, recording_block_id=block),
        evidence_sets=(evidence,),
    )

    assert evaluation.outcome is TransitionPolicyResult.TRANSITION_NOT_SUPPORTED
    assert evaluation.blocking_evidence_ids == (evidence.id,)


def test_conflicting_signals_use_reliable_order_not_rule_or_input_order() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    block = EntityId.new()
    current = _state(OperationalStateValue.ACTIVE, recording_block_id=block)
    start = _evidence(
        signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
        recording_block_id=block,
        timeline_end=10.0,
    )
    pause = _evidence(
        signal=EvidenceSignal.RECORDING_PAUSE_INDICATED,
        recording_block_id=block,
        timeline_end=20.0,
    )

    first = policy.evaluate(current_state=current, evidence_sets=(start, pause))
    second = policy.evaluate(current_state=current, evidence_sets=(pause, start))

    assert first.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert first.proposed_state is OperationalStateValue.PAUSED
    assert second.outcome is first.outcome
    assert second.proposed_state is first.proposed_state
    assert first.metadata["ordered_lifecycle_signals"] == (
        EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED.value,
        EvidenceSignal.RECORDING_PAUSE_INDICATED.value,
    )


def test_equal_time_conflicts_and_unaccepted_intermediate_transitions_are_insufficient() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    block = EntityId.new()
    equal_time = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    pause = _evidence(
        signal=EvidenceSignal.RECORDING_PAUSE_INDICATED,
        recording_block_id=block,
        created_at=equal_time,
    )
    restored = _evidence(
        signal=EvidenceSignal.RECORDING_CONTINUITY_RESTORED,
        recording_block_id=block,
        created_at=equal_time,
    )
    start = _evidence(
        signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
        recording_block_id=block,
        timeline_end=10.0,
    )
    later_pause = _evidence(
        signal=EvidenceSignal.RECORDING_PAUSE_INDICATED,
        recording_block_id=block,
        timeline_end=20.0,
    )

    equal_result = policy.evaluate(
        current_state=_state(OperationalStateValue.ACTIVE, recording_block_id=block),
        evidence_sets=(pause, restored),
    )
    accumulated_result = policy.evaluate(
        current_state=_state(OperationalStateValue.INACTIVE, recording_block_id=block),
        evidence_sets=(start, later_pause),
    )

    assert equal_result.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE
    assert accumulated_result.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE
    assert "unaccepted intermediate" in accumulated_result.rationale.message


def test_duplicate_sets_and_signal_references_are_deduplicated_without_content_merging() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    block = EntityId.new()
    evidence = _evidence(
        signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
        recording_block_id=block,
    )
    duplicate = replace(evidence, metadata={"duplicate": True})
    distinct = _evidence(
        signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
        recording_block_id=block,
    )
    repeated_reference = replace(
        evidence,
        id=EntityId.new(),
        signals=(evidence.signals[0], evidence.signals[0]),
    )
    current = _state(OperationalStateValue.INACTIVE, recording_block_id=block)

    duplicate_result = policy.evaluate_result(
        current_state=current,
        evidence_sets=(evidence, duplicate),
    )
    distinct_result = policy.evaluate(
        current_state=current,
        evidence_sets=(evidence, distinct),
    )
    reference_result = policy.evaluate(
        current_state=current,
        evidence_sets=(repeated_reference,),
    )

    assert duplicate_result.evidence_profile.duplicate_evidence_set_ids == (evidence.id,)
    assert duplicate_result.evaluation.supporting_evidence_ids == (evidence.id,)
    assert set(distinct_result.supporting_evidence_ids) == {evidence.id, distinct.id}
    assert reference_result.supporting_evidence_ids == (repeated_reference.id,)


def test_first_class_signals_are_authoritative_and_legacy_markers_remain_visible() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    block = EntityId.new()
    legacy = _evidence(
        signal=None,
        marker="recording_stopped",
        recording_block_id=block,
    )
    first_class = _evidence(
        signal=EvidenceSignal.RECORDING_PAUSE_INDICATED,
        marker="recording_stopped",
        recording_block_id=block,
    )
    current = _state(OperationalStateValue.ACTIVE, recording_block_id=block)

    legacy_result = policy.evaluate_result(current_state=current, evidence_sets=(legacy,))
    first_class_result = policy.evaluate(
        current_state=current,
        evidence_sets=(first_class,),
    )

    assert legacy_result.proposed_state is OperationalStateValue.STOPPED
    assert legacy_result.evidence_profile.metadata["legacy_marker_used"] is True
    assert first_class_result.proposed_state is OperationalStateValue.PAUSED
    assert first_class_result.metadata["legacy_marker_used"] is False
    assert mapping_for_recording_marker("recording_stopped") is not None


def test_unrelated_concerns_and_signals_are_ignored() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    unrelated_concern = _evidence(
        signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
        concern=EvidenceConcern.TRANSCRIPT_CONTINUITY,
    )
    unrelated_signal = _evidence(signal=EvidenceSignal.MEDIA_AVAILABILITY_INDICATED)

    result = policy.evaluate_result(
        current_state=None,
        evidence_sets=(unrelated_concern, unrelated_signal),
    )

    assert result.outcome is TransitionPolicyResult.INSUFFICIENT_EVIDENCE
    assert result.evidence_profile.ignored_evidence_set_ids == (unrelated_concern.id,)
    assert result.evidence_profile.unsupported_evidence_set_ids == (unrelated_signal.id,)


def test_traceability_exposes_context_rule_items_observations_and_ambiguity() -> None:
    policy = RecordingTransitionPolicy(id=EntityId.new())
    block = EntityId.new()
    stage = EntityId.new()
    evidence = _evidence(
        signal=EvidenceSignal.RECORDING_END_INDICATED,
        recording_block_id=block,
        stage_id=stage,
    )
    result = policy.evaluate_result(
        current_state=_state(
            OperationalStateValue.ACTIVE,
            recording_block_id=block,
            stage_id=stage,
        ),
        evidence_sets=(evidence,),
    )

    assert result.applied_rule_id is not None
    assert result.evidence_profile.contributing_evidence_item_ids == (evidence.items[0].id,)
    assert result.evidence_profile.contributing_observation_ids == (
        evidence.items[0].observation_id,
    )
    assert result.evidence_profile.selected_context is not None
    assert result.evaluation.metadata["selected_context"]["recording_block_id"] == block.to_json()
    assert result.evaluation.metadata["selected_context"]["stage_id"] == stage.to_json()


def test_recording_transition_mapping_rule_and_summary_contracts() -> None:
    mapping = mapping_for_recording_signal(EvidenceSignal.RECORDING_PAUSE_INDICATED)
    policy = RecordingTransitionPolicy(id=EntityId.new())
    summary = RecordingTransitionSummary.from_policy(policy)

    assert mapping is not None
    assert mapping.proposed_state is OperationalStateValue.PAUSED
    assert mapping.legacy_evidence_marker == "recording_paused"
    assert summary.rule_count == len(policy.rules)
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
            RecordingTransitionContext,
            RecordingTransitionEvidenceProfile,
            RecordingTransitionPolicy,
            RecordingTransitionResult,
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
