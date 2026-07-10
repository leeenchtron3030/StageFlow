from dataclasses import fields
from datetime import UTC, datetime, timedelta
from inspect import getmembers, isfunction

from app.contexts.production.evidence import (
    EvidenceConcern,
    EvidenceRole,
    EvidenceSignal,
    EvidenceStrength,
)
from app.contexts.production.observation import (
    Observation,
    ObservationConfidence,
    ObservationLocation,
    ObservationSource,
    ObservationType,
)
from app.contexts.production.operational_state import OperationalStateValue
from app.contexts.production.recording_coverage_evidence_builder import (
    RecordingCoverageEvidenceBuilder,
    RecordingCoverageEvidenceBuilderStatus,
    RecordingCoverageEvidenceMapping,
    RecordingCoverageEvidenceResult,
    RecordingCoverageEvidenceRule,
    RecordingCoverageEvidenceSummary,
    make_recording_coverage_evidence_builder,
    mapping_for_recording_activity,
    mapping_for_recording_event_kind,
)
from app.contexts.production.recording_transition_policy import RecordingTransitionPolicy
from app.contexts.production.timeline import TimelinePosition, TimelineRange
from app.contexts.production.transition_policy import TransitionPolicyResult
from app.shared.ids import CorrelationId, EntityId


def _observation(
    activity: str | None,
    *,
    observation_id: EntityId | None = None,
    recording_block_id: EntityId | None = None,
    stage_id: EntityId | None = None,
    observed_at: datetime | None = None,
    location: ObservationLocation | None = None,
    observation_type: ObservationType = ObservationType.RECORDING_ACTIVITY,
    metadata: dict[str, object] | None = None,
) -> Observation:
    resolved_recording_block_id = recording_block_id
    resolved_location = location
    if resolved_location is None:
        if recording_block_id is not None and stage_id is not None:
            resolved_location = ObservationLocation.composite(
                recording_block=recording_block_id,
                stage_id=stage_id,
            )
        elif recording_block_id is not None:
            resolved_location = ObservationLocation.for_recording_block(recording_block_id)
        elif stage_id is not None:
            resolved_location = ObservationLocation.for_stage(stage_id)
        else:
            resolved_location = ObservationLocation.at_wall_clock(
                datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
            )

    if resolved_recording_block_id is None:
        resolved_recording_block_id = resolved_location.recording_block_id

    observation_metadata = dict(metadata or {})
    if activity is not None:
        observation_metadata.setdefault("recording_activity", activity)

    return Observation(
        id=observation_id or EntityId.new(),
        recording_block_id=resolved_recording_block_id,
        observation_type=observation_type,
        observation_source=ObservationSource.SYSTEM,
        location=resolved_location,
        confidence=ObservationConfidence(1.0),
        correlation_id=CorrelationId.new(),
        observed_at=observed_at or datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        metadata=observation_metadata,
        notes=f"recording activity {activity}" if activity is not None else None,
    )


def _build_one(activity: str) -> RecordingCoverageEvidenceResult:
    builder = make_recording_coverage_evidence_builder()
    return builder.build((_observation(activity, recording_block_id=EntityId.new()),))


def test_recording_coverage_evidence_builder_creation() -> None:
    builder = make_recording_coverage_evidence_builder()

    assert builder.name == "Recording Coverage Evidence Builder"
    assert builder.status is RecordingCoverageEvidenceBuilderStatus.READY
    assert builder.can_build()
    assert len(builder.rules) == 4


def test_recording_coverage_evidence_rule_creation() -> None:
    rule = RecordingCoverageEvidenceRule(
        id=EntityId.new(),
        recognized_observation_type=ObservationType.RECORDING_ACTIVITY,
        recognized_recording_activity="began",
        target_signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
    )

    assert rule.target_concern is EvidenceConcern.RECORDING_COVERAGE
    assert rule.evidence_role is EvidenceRole.SUPPORTS
    assert rule.evidence_strength is EvidenceStrength.STRONG
    assert "recording_continuity_established" in rule.rationale()


def test_recording_coverage_evidence_mapping_creation() -> None:
    mapping = RecordingCoverageEvidenceMapping(
        recording_activity="paused",
        recording_event_kind="recording_paused",
        evidence_signal=EvidenceSignal.RECORDING_PAUSE_INDICATED,
        rationale="Recording pause was observed.",
    )

    assert mapping.evidence_signal is EvidenceSignal.RECORDING_PAUSE_INDICATED
    assert mapping_for_recording_activity("paused") is not None
    assert mapping_for_recording_event_kind("recording_paused") is not None


def test_recording_coverage_result_and_summary_creation() -> None:
    result = _build_one("began")
    summary = RecordingCoverageEvidenceSummary.from_result(result)

    assert isinstance(result, RecordingCoverageEvidenceResult)
    assert summary.input_observation_count == 1
    assert summary.recognized_recording_observation_count == 1
    assert summary.produced_evidence_set_count == 1
    assert summary.produced_evidence_item_count == 1
    assert summary.produced_signal_count == 1
    assert summary.signals == (EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,)


def test_recording_began_observation_mapping() -> None:
    result = _build_one("began")
    evidence = result.evidence_sets[0]

    assert evidence.concern is EvidenceConcern.RECORDING_COVERAGE
    assert evidence.signals[0].signal is EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED


def test_recording_paused_observation_mapping() -> None:
    result = _build_one("paused")

    assert result.evidence_sets[0].signals[0].signal is EvidenceSignal.RECORDING_PAUSE_INDICATED


def test_recording_resumed_observation_mapping() -> None:
    result = _build_one("resumed")

    assert (
        result.evidence_sets[0].signals[0].signal
        is EvidenceSignal.RECORDING_CONTINUITY_RESTORED
    )


def test_recording_ended_observation_mapping() -> None:
    result = _build_one("ended")

    assert result.evidence_sets[0].signals[0].signal is EvidenceSignal.RECORDING_END_INDICATED


def test_evidence_item_and_signal_are_traceable_id_only() -> None:
    observation = _observation("began", recording_block_id=EntityId.new())
    result = make_recording_coverage_evidence_builder().build((observation,))
    evidence = result.evidence_sets[0]
    item = evidence.items[0]
    signal = evidence.signals[0]

    assert item.observation_id == observation.id
    assert signal.observation_ids == (observation.id,)
    assert signal.evidence_item_ids == (item.id,)
    assert "observation" not in {
        field.name for field in fields(type(signal)) if field.name != "observation_ids"
    }


def test_evidence_role_and_strength_assignment() -> None:
    evidence = _build_one("began").evidence_sets[0]

    assert evidence.items[0].role is EvidenceRole.SUPPORTS
    assert evidence.items[0].strength is EvidenceStrength.STRONG


def test_recording_block_context_preserved() -> None:
    recording_block_id = EntityId.new()
    evidence = _build_one_for_observation(
        _observation("began", recording_block_id=recording_block_id)
    )

    assert evidence.recording_block_id == recording_block_id
    assert evidence.metadata["recording_block_id"] == recording_block_id.to_json()
    assert evidence.signals[0].metadata["recording_block_id"] == (
        recording_block_id.to_json()
    )


def _build_one_for_observation(observation: Observation):
    return make_recording_coverage_evidence_builder().build((observation,)).evidence_sets[0]


def test_stage_context_preserved_where_available() -> None:
    stage_id = EntityId.new()
    evidence = _build_one_for_observation(_observation("began", stage_id=stage_id))

    assert evidence.metadata["stage_id"] == stage_id.to_json()
    assert evidence.signals[0].metadata["stage_id"] == stage_id.to_json()


def test_timeline_context_preserved_where_available() -> None:
    recording_block_id = EntityId.new()
    location = ObservationLocation.at_point(
        TimelinePosition(recording_block_id, timedelta(seconds=12))
    )
    evidence = _build_one_for_observation(
        _observation("began", location=location, recording_block_id=recording_block_id)
    )

    location_metadata = evidence.items[0].metadata["observation_location"]
    assert location_metadata["timeline_offset_seconds"] == 12.0


def test_timeline_range_context_preserved_where_available() -> None:
    recording_block_id = EntityId.new()
    location = ObservationLocation.over_range(
        TimelineRange(
            TimelinePosition(recording_block_id, timedelta(seconds=10)),
            TimelinePosition(recording_block_id, timedelta(seconds=20)),
        )
    )
    evidence = _build_one_for_observation(
        _observation("began", location=location, recording_block_id=recording_block_id)
    )

    location_metadata = evidence.items[0].metadata["observation_location"]
    assert location_metadata["timeline_range_start_seconds"] == 10.0
    assert location_metadata["timeline_range_end_seconds"] == 20.0


def test_unrelated_observations_ignored() -> None:
    recording = _observation("began", recording_block_id=EntityId.new())
    transcript = _observation(
        None,
        observation_type=ObservationType.TRANSCRIPT_ACTIVITY,
        metadata={"transcript_text": "hello"},
    )
    vision = _observation(
        None,
        observation_type=ObservationType.VISION_ACTIVITY,
        metadata={"visual_detection_type": "title_slide"},
    )

    result = make_recording_coverage_evidence_builder().build(
        (recording, transcript, vision)
    )

    assert result.evidence_count == 1
    assert result.consumed_observation_ids == (recording.id,)
    assert set(result.ignored_observation_ids) == {transcript.id, vision.id}


def test_unsupported_recording_semantics_not_guessed() -> None:
    unsupported = _observation("buffering", recording_block_id=EntityId.new())

    result = make_recording_coverage_evidence_builder().build((unsupported,))

    assert result.evidence_sets == ()
    assert result.unsupported_observation_ids == (unsupported.id,)


def test_duplicate_observation_ids_handled_deterministically() -> None:
    observation_id = EntityId.new()
    duplicate_a = _observation(
        "began",
        observation_id=observation_id,
        observed_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    duplicate_b = _observation(
        "began",
        observation_id=observation_id,
        observed_at=datetime(2026, 1, 1, 12, 1, tzinfo=UTC),
    )

    result = make_recording_coverage_evidence_builder().build((duplicate_b, duplicate_a))

    assert result.evidence_count == 1
    assert result.duplicate_observation_ids == (observation_id,)
    assert len(result.evidence_sets[0].items) == 1


def test_multiple_recording_observations_processed_chronologically() -> None:
    recording_block_id = EntityId.new()
    paused = _observation(
        "paused",
        recording_block_id=recording_block_id,
        observed_at=datetime(2026, 1, 1, 12, 2, tzinfo=UTC),
    )
    began = _observation(
        "began",
        recording_block_id=recording_block_id,
        observed_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )

    evidence = make_recording_coverage_evidence_builder().build((paused, began)).evidence_sets[0]

    assert [signal.signal for signal in evidence.signals] == [
        EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
        EvidenceSignal.RECORDING_PAUSE_INDICATED,
    ]


def test_distinct_recording_blocks_not_merged() -> None:
    first_block = EntityId.new()
    second_block = EntityId.new()
    first = _observation("began", recording_block_id=first_block)
    second = _observation("began", recording_block_id=second_block)

    result = make_recording_coverage_evidence_builder().build((first, second))

    assert result.evidence_count == 2
    assert {evidence.recording_block_id for evidence in result.evidence_sets} == {
        first_block,
        second_block,
    }


def test_distinct_stages_not_merged() -> None:
    first_stage = EntityId.new()
    second_stage = EntityId.new()
    first = _observation("began", stage_id=first_stage)
    second = _observation("began", stage_id=second_stage)

    result = make_recording_coverage_evidence_builder().build((first, second))

    assert result.evidence_count == 2


def test_deterministic_repeated_builds() -> None:
    recording_block_id = EntityId.new()
    observations = (
        _observation("began", recording_block_id=recording_block_id),
        _observation("paused", recording_block_id=recording_block_id),
    )
    builder = make_recording_coverage_evidence_builder()

    first = builder.build(observations)
    second = builder.build(observations)

    assert [signal.signal for signal in first.evidence_sets[0].signals] == [
        signal.signal for signal in second.evidence_sets[0].signals
    ]
    assert first.consumed_observation_ids == second.consumed_observation_ids


def test_source_observations_are_not_mutated() -> None:
    observation = _observation("began", recording_block_id=EntityId.new())
    original_metadata = dict(observation.metadata)

    make_recording_coverage_evidence_builder().build((observation,))

    assert dict(observation.metadata) == original_metadata


def test_builder_output_compatible_with_recording_transition_policy() -> None:
    result = _build_one("began")
    policy = RecordingTransitionPolicy(id=EntityId.new())

    evaluation = policy.evaluate(current_state=None, evidence_sets=result.evidence_sets)

    assert evaluation.outcome is TransitionPolicyResult.TRANSITION_SUPPORTED
    assert evaluation.proposed_state is OperationalStateValue.ACTIVE


def test_pause_signal_produces_paused_policy_proposal() -> None:
    evaluation = RecordingTransitionPolicy(id=EntityId.new()).evaluate(
        current_state=None,
        evidence_sets=_build_one("paused").evidence_sets,
    )

    assert evaluation.proposed_state is OperationalStateValue.PAUSED


def test_resume_signal_produces_active_policy_proposal() -> None:
    evaluation = RecordingTransitionPolicy(id=EntityId.new()).evaluate(
        current_state=None,
        evidence_sets=_build_one("resumed").evidence_sets,
    )

    assert evaluation.proposed_state is OperationalStateValue.ACTIVE


def test_end_signal_produces_stopped_policy_proposal() -> None:
    evaluation = RecordingTransitionPolicy(id=EntityId.new()).evaluate(
        current_state=None,
        evidence_sets=_build_one("ended").evidence_sets,
    )

    assert evaluation.proposed_state is OperationalStateValue.STOPPED


def test_builder_produces_no_cross_domain_evidence() -> None:
    result = make_recording_coverage_evidence_builder().build(
        (
            _observation("began", recording_block_id=EntityId.new()),
            _observation(None, observation_type=ObservationType.TRANSCRIPT_ACTIVITY),
            _observation(None, observation_type=ObservationType.VISION_ACTIVITY),
        )
    )

    assert {evidence.concern for evidence in result.evidence_sets} == {
        EvidenceConcern.RECORDING_COVERAGE
    }
    assert EvidenceConcern.TRANSCRIPT_CONTINUITY not in {
        evidence.concern for evidence in result.evidence_sets
    }
    assert EvidenceConcern.VISUAL_TRANSITION_CONTEXT not in {
        evidence.concern for evidence in result.evidence_sets
    }


def test_builder_has_no_policy_execution_or_downstream_behavior() -> None:
    names = {
        field.name
        for contract in (
            RecordingCoverageEvidenceBuilder,
            RecordingCoverageEvidenceRule,
            RecordingCoverageEvidenceResult,
            RecordingCoverageEvidenceSummary,
        )
        for field in fields(contract)
    } | {
        name
        for name, value in getmembers(RecordingCoverageEvidenceBuilder)
        if isfunction(value)
    }
    forbidden_terms = {
        "operational_state",
        "transition_evaluation",
        "session",
        "editorial",
        "transcript",
        "visual",
        "hypothesis",
        "finding",
        "verification",
        "operational_product",
        "confidence_formula",
        "probability",
        "ai",
        "api",
        "persist",
        "repository",
        "queue",
        "worker",
        "frontend",
        "mutate",
    }

    assert not any(term in name for name in names for term in forbidden_terms)


def test_disabled_builder_creates_no_evidence() -> None:
    builder = RecordingCoverageEvidenceBuilder(
        id=EntityId.new(),
        status=RecordingCoverageEvidenceBuilderStatus.DISABLED,
    )
    observation = _observation("began", recording_block_id=EntityId.new())

    result = builder.build((observation,))

    assert result.evidence_sets == ()
    assert result.ignored_observation_ids == (observation.id,)
