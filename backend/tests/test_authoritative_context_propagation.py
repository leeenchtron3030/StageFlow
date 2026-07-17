from dataclasses import replace
from datetime import UTC, datetime, timedelta

from app.contexts.production.evidence import (
    EvidenceConcern,
    EvidenceContext,
    EvidenceContextConflictResolution,
    EvidenceItem,
    EvidencePurpose,
    EvidenceRole,
    EvidenceSet,
    EvidenceSignal,
    EvidenceSignalReference,
    EvidenceStrength,
)
from app.contexts.production.observation import (
    Observation,
    ObservationConfidence,
    ObservationContext,
    ObservationLocation,
    ObservationProvenance,
    ObservationSource,
    ObservationType,
)
from app.contexts.production.operational_state import (
    OperationalStateSubject,
    OperationalStateSubjectType,
)
from app.contexts.production.operational_state_acceptance import (
    OperationalStateAcceptance,
    OperationalStateAcceptanceContext,
    OperationalStateAcceptanceHistory,
    OperationalStateAcceptanceLineage,
    OperationalStateAcceptanceOutcome,
    OperationalStateAcceptanceRequest,
)
from app.contexts.production.production_event import ProductionEventType
from app.contexts.production.recording_coverage_evidence_builder import (
    make_recording_coverage_evidence_builder,
)
from app.contexts.production.recording_transition_policy import RecordingTransitionPolicy
from app.contexts.production.session_boundary_evidence_builder import (
    make_session_boundary_evidence_builder,
)
from app.contexts.production.session_transition_policy import SessionTransitionPolicy
from app.contexts.production.timeline import TimelinePosition
from app.contexts.production.transcript_continuity_evidence_builder import (
    make_transcript_continuity_evidence_builder,
)
from app.contexts.production.transition_policy import TransitionPolicyResult
from app.shared.ids import CorrelationId, EntityId

BASE_TIME = datetime(2026, 7, 16, 10, 0, tzinfo=UTC)


def _observation(
    *,
    observation_type: ObservationType,
    source: ObservationSource,
    context: ObservationContext,
    metadata: dict[str, object],
    event_id: EntityId | None = None,
    observed_at: datetime = BASE_TIME,
) -> Observation:
    source_event_id = event_id or EntityId.new()
    return Observation(
        id=EntityId.new(),
        recording_block_id=context.recording_block_id,
        observation_type=observation_type,
        observation_source=source,
        location=(
            ObservationLocation.at_point(context.timeline_position)
            if context.timeline_position is not None
            else ObservationLocation.unknown()
        ),
        confidence=ObservationConfidence(1.0),
        correlation_id=context.correlation_id or CorrelationId.new(),
        observed_at=observed_at,
        metadata=metadata,
        provenance=ObservationProvenance(
            source_event_id=source_event_id,
            source_event_type=(
                ProductionEventType.RECORDING_BLOCK_STARTED
                if observation_type is ObservationType.RECORDING_ACTIVITY
                else ProductionEventType.TRANSCRIPT_SEGMENT_AVAILABLE
            ),
            source_event_occurred_at=observed_at,
            interpreter_kind="deterministic_contract_interpreter",
            interpreter_id=EntityId.new(),
            interpretation_rule_id="ed0045.authoritative-context",
            producer_identifier="contract-test",
        ),
        context=context,
    )


def _source_evidence(
    *,
    concern: EvidenceConcern,
    signal: EvidenceSignal,
    context: EvidenceContext,
    strength: EvidenceStrength = EvidenceStrength.STRONG,
    created_at: datetime = BASE_TIME,
) -> EvidenceSet:
    item = EvidenceItem(
        id=EntityId.new(),
        observation_id=EntityId.new(),
        strength=strength,
        role=EvidenceRole.SUPPORTS,
        metadata={
            "observation_observed_at": created_at.isoformat(),
            "source_production_event_id": EntityId.new().to_json(),
        },
    )
    return EvidenceSet(
        id=EntityId.new(),
        recording_block_id=context.recording_block_id,
        purpose=EvidencePurpose.TRANSITION_SUPPORT,
        items=(item,),
        correlation_id=(
            context.correlation_ids[0] if context.correlation_ids else CorrelationId.new()
        ),
        concern=concern,
        signals=(
            EvidenceSignalReference(
                signal=signal,
                evidence_item_ids=(item.id,),
                observation_ids=(item.observation_id,),
            ),
        ),
        created_at=created_at,
        context=context,
    )


def _session_start_evidence(
    context: EvidenceContext,
    *,
    metadata: dict[str, object] | None = None,
) -> EvidenceSet:
    observations = (EntityId.new(), EntityId.new())
    items = tuple(
        EvidenceItem(
            id=EntityId.new(),
            observation_id=observation_id,
            strength=EvidenceStrength.STRONG,
            role=EvidenceRole.SUPPORTS,
        )
        for observation_id in observations
    )
    signals = tuple(
        EvidenceSignalReference(
            signal=signal,
            evidence_item_ids=(item.id,),
            observation_ids=(item.observation_id,),
        )
        for signal, item in zip(
            (
                EvidenceSignal.SPEAKER_INTRODUCTION_INDICATED,
                EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
            ),
            items,
            strict=True,
        )
    )
    return EvidenceSet(
        id=EntityId.new(),
        recording_block_id=context.recording_block_id,
        purpose=EvidencePurpose.TRANSITION_SUPPORT,
        items=items,
        correlation_id=(
            context.correlation_ids[0] if context.correlation_ids else CorrelationId.new()
        ),
        concern=EvidenceConcern.POSSIBLE_SESSION_START,
        signals=signals,
        created_at=BASE_TIME,
        metadata=metadata or {},
        context=context,
    )


def test_recording_context_propagates_from_observation_through_successor_state() -> None:
    stage_id = EntityId.new()
    conflicting_stage_id = EntityId.new()
    block_id = EntityId.new()
    event_id = EntityId.new()
    correlation_id = CorrelationId.new()
    observation = _observation(
        observation_type=ObservationType.RECORDING_ACTIVITY,
        source=ObservationSource.SYSTEM,
        context=ObservationContext(
            stage_id=stage_id,
            recording_block_id=block_id,
            correlation_id=correlation_id,
            media_artifact_id="artifact-1",
            timeline_position=TimelinePosition(block_id, timedelta(seconds=10)),
        ),
        metadata={
            "recording_activity": "began",
            "stage_id": conflicting_stage_id.to_json(),
        },
        event_id=event_id,
    )

    evidence = make_recording_coverage_evidence_builder().build((observation,)).evidence_sets[0]
    policy_result = RecordingTransitionPolicy(id=EntityId.new()).evaluate_result(
        current_state=None,
        evidence_sets=(evidence,),
        evaluated_at=BASE_TIME + timedelta(seconds=90),
    )
    lineage = OperationalStateAcceptanceLineage.from_recording_result(policy_result)
    acceptance_context = OperationalStateAcceptanceContext.from_evidence_context(
        policy_result.evaluation.context
    )
    request = OperationalStateAcceptanceRequest(
        evaluation=policy_result.evaluation,
        lineage=lineage,
        current_state=None,
        target_subject=OperationalStateSubject(
            subject_type=OperationalStateSubjectType.RECORDING_BLOCK,
            subject_identifier=block_id.to_json(),
        ),
        history=OperationalStateAcceptanceHistory(),
        accepted_at=BASE_TIME + timedelta(seconds=92),
        context=acceptance_context,
    )
    accepted = OperationalStateAcceptance().accept(request)

    assert evidence.context.stage_id == stage_id
    assert evidence.context.recording_block_id == block_id
    assert evidence.context.media_artifact_ids == ("artifact-1",)
    assert evidence.context.correlation_ids == (correlation_id,)
    assert evidence.context.timeline_range_seconds == (10.0, 10.0)
    assert evidence.context.source_context_ids == (observation.id,)
    assert evidence.context_resolution is not None
    assert any(
        conflict.field_name == "stage_id"
        and conflict.resolution is EvidenceContextConflictResolution.FIRST_CLASS_VALUE_RETAINED
        for conflict in evidence.context_resolution.conflicts
    )
    assert evidence.items[0].observation_id == observation.id
    assert event_id.to_json() == evidence.items[0].metadata["source_production_event_id"]
    assert policy_result.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert policy_result.evaluation.context.stage_id == stage_id
    assert policy_result.evaluation.context.recording_block_id == block_id
    assert policy_result.evaluation.context.media_artifact_ids == ("artifact-1",)
    assert policy_result.evaluation.evaluated_at == BASE_TIME + timedelta(seconds=90)
    assert accepted.outcome is OperationalStateAcceptanceOutcome.ACCEPTED
    assert accepted.accepted_at == BASE_TIME + timedelta(seconds=92)
    assert accepted.successor_state is not None
    assert accepted.successor_state.subject.subject_identifier == block_id.to_json()
    assert accepted.successor_state.basis.evidence_context == policy_result.evaluation.context
    assert accepted.successor_state.basis.transition_evaluation_ids == (
        policy_result.evaluation.id,
    )
    assert accepted.successor_state.basis.evidence_context is not None
    assert accepted.successor_state.basis.evidence_context.stage_id == stage_id
    assert accepted.successor_state.metadata["boundary_anchor_verified"] is False


def test_recording_builder_isolates_blocks_and_accumulates_compatible_artifacts() -> None:
    stage_id = EntityId.new()
    block_a = EntityId.new()
    block_b = EntityId.new()
    observations = (
        _observation(
            observation_type=ObservationType.RECORDING_ACTIVITY,
            source=ObservationSource.SYSTEM,
            context=ObservationContext(
                stage_id=stage_id,
                recording_block_id=block_a,
                media_artifact_id="artifact-2",
            ),
            metadata={"recording_activity": "began"},
        ),
        _observation(
            observation_type=ObservationType.RECORDING_ACTIVITY,
            source=ObservationSource.SYSTEM,
            context=ObservationContext(
                stage_id=stage_id,
                recording_block_id=block_a,
                media_artifact_id="artifact-1",
            ),
            metadata={"recording_activity": "began"},
        ),
        _observation(
            observation_type=ObservationType.RECORDING_ACTIVITY,
            source=ObservationSource.SYSTEM,
            context=ObservationContext(
                stage_id=stage_id,
                recording_block_id=block_b,
                media_artifact_id="artifact-3",
            ),
            metadata={"recording_activity": "began"},
        ),
    )

    evidence_sets = (
        make_recording_coverage_evidence_builder()
        .build(tuple(reversed(observations)))
        .evidence_sets
    )
    by_block = {evidence.context.recording_block_id: evidence for evidence in evidence_sets}

    assert set(by_block) == {block_a, block_b}
    assert by_block[block_a].context.media_artifact_ids == (
        "artifact-1",
        "artifact-2",
    )
    assert by_block[block_b].context.media_artifact_ids == ("artifact-3",)
    assert all(evidence.context.stage_id == stage_id for evidence in evidence_sets)


def test_transcript_builder_keeps_streams_distinct_and_preserves_context() -> None:
    stage_id = EntityId.new()
    block_id = EntityId.new()
    observations = tuple(
        _observation(
            observation_type=ObservationType.TRANSCRIPT_ACTIVITY,
            source=ObservationSource.TRANSCRIPT,
            context=ObservationContext(
                stage_id=stage_id,
                recording_block_id=block_id,
                transcript_stream_id=stream_id,
                media_artifact_id=f"artifact-{stream_id}",
                correlation_id=CorrelationId.new(),
            ),
            metadata={"transcript_lifecycle": "segment_available"},
        )
        for stream_id in ("stream-2", "stream-1")
    )

    evidence_sets = make_transcript_continuity_evidence_builder().build(observations).evidence_sets

    assert len(evidence_sets) == 2
    assert {evidence.context.transcript_stream_ids for evidence in evidence_sets} == {
        ("stream-1",),
        ("stream-2",),
    }
    assert all(evidence.context.stage_id == stage_id for evidence in evidence_sets)
    assert all(evidence.context.recording_block_id == block_id for evidence in evidence_sets)
    assert all(evidence.context.media_artifact_ids for evidence in evidence_sets)
    assert all(evidence.context.correlation_ids for evidence in evidence_sets)


def test_boundary_builder_composes_partial_compatible_context_without_identity_collapse() -> None:
    stage_id = EntityId.new()
    block_id = EntityId.new()
    activity_id = EntityId.new()
    correlation_a = CorrelationId.new()
    correlation_b = CorrelationId.new()
    recording = _source_evidence(
        concern=EvidenceConcern.RECORDING_COVERAGE,
        signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
        context=EvidenceContext(
            stage_id=stage_id,
            recording_block_id=block_id,
            media_artifact_ids=("artifact-1",),
            correlation_ids=(correlation_a,),
            timeline_position=TimelinePosition(block_id, timedelta(seconds=10)),
        ),
    )
    transcript = _source_evidence(
        concern=EvidenceConcern.TRANSCRIPT_CONTINUITY,
        signal=EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
        context=EvidenceContext(
            stage_id=stage_id,
            recording_block_id=block_id,
            transcript_stream_ids=("stream-1",),
            correlation_ids=(correlation_b,),
            timeline_position=TimelinePosition(block_id, timedelta(seconds=12)),
        ),
        created_at=BASE_TIME + timedelta(seconds=2),
    )
    schedule = _source_evidence(
        concern=EvidenceConcern.SCHEDULE_ALIGNMENT,
        signal=EvidenceSignal.SCHEDULED_WINDOW_ACTIVE,
        context=EvidenceContext(
            scheduled_activity_id=activity_id,
            organizational_anchor_seconds=11,
        ),
        strength=EvidenceStrength.MODERATE,
        created_at=BASE_TIME + timedelta(seconds=1),
    )
    builder = make_session_boundary_evidence_builder()

    forward = builder.build((recording, transcript, schedule))
    reverse = builder.build((schedule, transcript, recording))

    assert len(forward.start_boundary_evidence_sets) == 1
    boundary = forward.start_boundary_evidence_sets[0]
    context = boundary.context
    assert context == reverse.start_boundary_evidence_sets[0].context
    assert boundary.id == reverse.start_boundary_evidence_sets[0].id
    assert context.stage_id == stage_id
    assert context.recording_block_id == block_id
    assert context.scheduled_activity_id == activity_id
    assert context.transcript_stream_ids == ("stream-1",)
    assert context.media_artifact_ids == ("artifact-1",)
    assert set(context.correlation_ids) == {correlation_a, correlation_b, schedule.correlation_id}
    assert context.timeline_range_seconds == (10.0, 12.0)
    assert context.organizational_anchor_seconds == 10.0
    assert context.organizational_anchor == BASE_TIME
    assert context.boundary_context_id is not None
    assert set(context.source_context_ids) == {recording.id, transcript.id, schedule.id}
    assert {item.strength for item in boundary.items} == {
        EvidenceStrength.STRONG,
        EvidenceStrength.MODERATE,
    }
    assert boundary.metadata["final_boundary_timestamp"] is None
    assert forward.generated_boundary_contexts[0].metadata["session_id"] is None


def test_boundary_builder_never_merges_conflicting_known_identity() -> None:
    block_a = EntityId.new()
    block_b = EntityId.new()
    stage_a = EntityId.new()
    stage_b = EntityId.new()
    activity_a = EntityId.new()
    activity_b = EntityId.new()
    sources = (
        _source_evidence(
            concern=EvidenceConcern.RECORDING_COVERAGE,
            signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
            context=EvidenceContext(
                stage_id=stage_a,
                recording_block_id=block_a,
                scheduled_activity_id=activity_a,
            ),
        ),
        _source_evidence(
            concern=EvidenceConcern.TRANSCRIPT_CONTINUITY,
            signal=EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
            context=EvidenceContext(
                stage_id=stage_b,
                recording_block_id=block_a,
                scheduled_activity_id=activity_a,
            ),
        ),
        _source_evidence(
            concern=EvidenceConcern.TRANSCRIPT_CONTINUITY,
            signal=EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
            context=EvidenceContext(
                stage_id=stage_a,
                recording_block_id=block_b,
                scheduled_activity_id=activity_a,
            ),
        ),
        _source_evidence(
            concern=EvidenceConcern.SCHEDULE_ALIGNMENT,
            signal=EvidenceSignal.SCHEDULED_WINDOW_ACTIVE,
            context=EvidenceContext(
                stage_id=stage_a,
                recording_block_id=block_a,
                scheduled_activity_id=activity_b,
            ),
        ),
    )

    outputs = make_session_boundary_evidence_builder().build(sources).evidence_sets

    assert len(outputs) == 4
    assert all(len(output.context.source_context_ids) == 1 for output in outputs)
    assert all(
        len({output.context.stage_id, output.context.recording_block_id}) == 2 for output in outputs
    )


def test_boundary_builder_keeps_unknown_primary_context_isolated() -> None:
    sources = (
        _source_evidence(
            concern=EvidenceConcern.TRANSCRIPT_CONTINUITY,
            signal=EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
            context=EvidenceContext(correlation_ids=(CorrelationId.new(),)),
        ),
        _source_evidence(
            concern=EvidenceConcern.RECORDING_COVERAGE,
            signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
            context=EvidenceContext(correlation_ids=(CorrelationId.new(),)),
        ),
    )

    outputs = make_session_boundary_evidence_builder().build(sources).evidence_sets

    assert len(outputs) == 2
    assert all(len(output.context.source_context_ids) == 1 for output in outputs)


def test_policies_prefer_first_class_context_and_keep_legacy_fallback() -> None:
    stage_a = EntityId.new()
    stage_b = EntityId.new()
    block_id = EntityId.new()
    first_class = EvidenceContext(
        stage_id=stage_a,
        recording_block_id=block_id,
        transcript_stream_ids=("stream-1",),
        media_artifact_ids=("artifact-1",),
        boundary_context_id=EntityId.new(),
        organizational_anchor=BASE_TIME,
    )
    session_evidence = _session_start_evidence(
        first_class,
        metadata={"stage_id": stage_b.to_json()},
    )

    session_result = SessionTransitionPolicy(id=EntityId.new()).evaluate(
        current_state=None,
        evidence_sets=(session_evidence,),
        evaluated_at=BASE_TIME + timedelta(minutes=1),
    )

    assert session_result.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert session_result.evaluation.context.stage_id == stage_a
    assert session_result.evaluation.context.recording_block_id == block_id
    assert session_result.evaluation.context.transcript_stream_ids == ("stream-1",)
    assert any(
        conflict.field_name == "stage_id"
        for conflict in session_result.evaluation.context_conflicts
    )

    legacy = replace(
        session_evidence,
        id=EntityId.new(),
        context=EvidenceContext.unknown(),
        metadata={
            "stage_id": stage_a.to_json(),
            "recording_block_id": block_id.to_json(),
            "boundary_context_id": EntityId.new().to_json(),
            "boundary_anchor_at": BASE_TIME.isoformat(),
        },
    )
    legacy_result = SessionTransitionPolicy(id=EntityId.new()).evaluate(
        current_state=None,
        evidence_sets=(legacy,),
        evaluated_at=BASE_TIME + timedelta(minutes=1),
    )

    assert legacy_result.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert legacy_result.evaluation.context.stage_id == stage_a
    assert legacy_result.evaluation.context.recording_block_id == block_id


def test_acceptance_rejects_request_context_that_conflicts_with_evaluation() -> None:
    block_a = EntityId.new()
    block_b = EntityId.new()
    observation = _observation(
        observation_type=ObservationType.RECORDING_ACTIVITY,
        source=ObservationSource.SYSTEM,
        context=ObservationContext(recording_block_id=block_a),
        metadata={"recording_activity": "began"},
    )
    evidence = make_recording_coverage_evidence_builder().build((observation,)).evidence_sets[0]
    policy_result = RecordingTransitionPolicy(id=EntityId.new()).evaluate_result(
        current_state=None,
        evidence_sets=(evidence,),
        evaluated_at=BASE_TIME,
    )
    lineage = OperationalStateAcceptanceLineage.from_recording_result(policy_result)
    request = OperationalStateAcceptanceRequest(
        evaluation=policy_result.evaluation,
        lineage=lineage,
        current_state=None,
        target_subject=OperationalStateSubject(
            subject_type=OperationalStateSubjectType.RECORDING_BLOCK,
            subject_identifier=block_a.to_json(),
        ),
        history=OperationalStateAcceptanceHistory(),
        accepted_at=BASE_TIME + timedelta(seconds=2),
        context=OperationalStateAcceptanceContext(recording_block_id=block_b),
    )

    result = OperationalStateAcceptance().accept(request)

    assert result.outcome is OperationalStateAcceptanceOutcome.REJECTED_CONTEXT_MISMATCH
    assert result.successor_state is None
