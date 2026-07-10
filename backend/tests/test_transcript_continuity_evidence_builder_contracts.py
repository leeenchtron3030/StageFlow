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
from app.contexts.production.timeline import TimelinePosition, TimelineRange
from app.contexts.production.transcript_continuity_evidence_builder import (
    TranscriptContinuityEvidenceBuilder,
    TranscriptContinuityEvidenceBuilderStatus,
    TranscriptContinuityEvidenceMapping,
    TranscriptContinuityEvidenceResult,
    TranscriptContinuityEvidenceRule,
    TranscriptContinuityEvidenceSummary,
    make_transcript_continuity_evidence_builder,
    mapping_for_transcript_lifecycle,
)
from app.shared.ids import CorrelationId, EntityId


def _observation(
    lifecycle: str | None,
    *,
    observation_id: EntityId | None = None,
    recording_block_id: EntityId | None = None,
    stage_id: EntityId | None = None,
    transcript_stream_id: str | None = "stream-1",
    observed_at: datetime | None = None,
    location: ObservationLocation | None = None,
    observation_type: ObservationType = ObservationType.TRANSCRIPT_ACTIVITY,
    metadata: dict[str, object] | None = None,
) -> Observation:
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

    resolved_recording_block_id = recording_block_id or resolved_location.recording_block_id
    observation_metadata = dict(metadata or {})
    if lifecycle is not None:
        observation_metadata.setdefault("transcript_lifecycle", lifecycle)
    if transcript_stream_id is not None:
        observation_metadata.setdefault("transcript_stream_id", transcript_stream_id)

    return Observation(
        id=observation_id or EntityId.new(),
        recording_block_id=resolved_recording_block_id,
        observation_type=observation_type,
        observation_source=ObservationSource.TRANSCRIPT,
        location=resolved_location,
        confidence=ObservationConfidence(1.0),
        correlation_id=CorrelationId.new(),
        observed_at=observed_at or datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        metadata=observation_metadata,
        notes="Transcript segment became available.",
    )


def _build_one(lifecycle: str) -> TranscriptContinuityEvidenceResult:
    return make_transcript_continuity_evidence_builder().build(
        (_observation(lifecycle, recording_block_id=EntityId.new()),)
    )


def _build_one_for_observation(observation: Observation):
    return make_transcript_continuity_evidence_builder().build((observation,)).evidence_sets[0]


def test_transcript_continuity_evidence_builder_creation() -> None:
    builder = make_transcript_continuity_evidence_builder()

    assert builder.name == "Transcript Continuity Evidence Builder"
    assert builder.status is TranscriptContinuityEvidenceBuilderStatus.READY
    assert builder.can_build()
    assert builder.rules


def test_transcript_continuity_evidence_rule_creation() -> None:
    rule = TranscriptContinuityEvidenceRule(
        id=EntityId.new(),
        recognized_observation_type=ObservationType.TRANSCRIPT_ACTIVITY,
        recognized_transcript_lifecycle="segment_available",
        target_signal=EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
    )

    assert rule.target_concern is EvidenceConcern.TRANSCRIPT_CONTINUITY
    assert rule.evidence_role is EvidenceRole.SUPPORTS
    assert rule.evidence_strength is EvidenceStrength.STRONG
    assert "speech_activity_available" in rule.rationale()


def test_transcript_continuity_evidence_mapping_creation() -> None:
    mapping = TranscriptContinuityEvidenceMapping(
        transcript_lifecycle="transcript_content_continued",
        evidence_signal=EvidenceSignal.TRANSCRIPT_CONTINUITY_INDICATED,
        rationale="Transcript content continued.",
    )

    assert mapping.evidence_signal is EvidenceSignal.TRANSCRIPT_CONTINUITY_INDICATED
    assert mapping_for_transcript_lifecycle("segment_available") is not None


def test_transcript_continuity_result_and_summary_creation() -> None:
    result = _build_one("segment_available")
    summary = TranscriptContinuityEvidenceSummary.from_result(result)

    assert isinstance(result, TranscriptContinuityEvidenceResult)
    assert summary.input_observation_count == 1
    assert summary.recognized_transcript_observation_count == 1
    assert summary.produced_evidence_set_count == 1
    assert summary.produced_evidence_item_count == 1
    assert summary.produced_signal_count == 1
    assert summary.signals == (EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,)


def test_transcript_activity_began_mapping() -> None:
    evidence = _build_one("transcript_activity_began").evidence_sets[0]

    assert evidence.concern is EvidenceConcern.TRANSCRIPT_CONTINUITY
    assert evidence.purpose.value == "transition_support"
    assert evidence.signals[0].signal is EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE


def test_transcript_continuation_mapping() -> None:
    evidence = _build_one("transcript_content_continued").evidence_sets[0]

    assert evidence.signals[0].signal is EvidenceSignal.TRANSCRIPT_CONTINUITY_INDICATED


def test_explicit_interruption_mapping() -> None:
    evidence = _build_one("transcript_activity_interrupted").evidence_sets[0]

    assert evidence.signals[0].signal is EvidenceSignal.TRANSCRIPT_INTERRUPTION_INDICATED
    assert evidence.items[0].role is EvidenceRole.SUPPORTS


def test_transcript_ending_mapping() -> None:
    evidence = _build_one("transcript_activity_ended").evidence_sets[0]

    assert evidence.signals[0].signal is EvidenceSignal.TRANSCRIPT_END_INDICATED


def test_segment_available_first_creates_availability_signal() -> None:
    result = _build_one("segment_available")

    assert result.evidence_sets[0].signals[0].signal is EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE


def test_repeated_segments_support_continuity_and_remain_traceable() -> None:
    recording_block_id = EntityId.new()
    first = _observation(
        "segment_available",
        recording_block_id=recording_block_id,
        observed_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    second = _observation(
        "segment_available",
        recording_block_id=recording_block_id,
        observed_at=datetime(2026, 1, 1, 12, 1, tzinfo=UTC),
    )

    evidence = make_transcript_continuity_evidence_builder().build((first, second)).evidence_sets[0]

    assert [signal.signal for signal in evidence.signals] == [
        EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE,
        EvidenceSignal.TRANSCRIPT_CONTINUITY_INDICATED,
    ]
    assert [signal.observation_ids[0] for signal in evidence.signals] == [
        first.id,
        second.id,
    ]


def test_missing_segments_do_not_imply_interruption() -> None:
    recording_block_id = EntityId.new()
    first = _observation(
        "segment_available",
        recording_block_id=recording_block_id,
        observed_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    second = _observation(
        "segment_available",
        recording_block_id=recording_block_id,
        observed_at=datetime(2026, 1, 1, 12, 30, tzinfo=UTC),
    )

    evidence = make_transcript_continuity_evidence_builder().build((first, second)).evidence_sets[0]

    assert EvidenceSignal.TRANSCRIPT_INTERRUPTION_INDICATED not in {
        signal.signal for signal in evidence.signals
    }


def test_observation_references_remain_id_only() -> None:
    observation = _observation("segment_available", recording_block_id=EntityId.new())
    evidence = _build_one_for_observation(observation)
    item = evidence.items[0]
    signal = evidence.signals[0]

    assert item.observation_id == observation.id
    assert signal.observation_ids == (observation.id,)
    assert signal.evidence_item_ids == (item.id,)
    assert "observation" not in {
        field.name for field in fields(type(signal)) if field.name != "observation_ids"
    }


def test_transcript_stream_context_preserved() -> None:
    evidence = _build_one_for_observation(
        _observation("segment_available", transcript_stream_id="stream-a")
    )

    assert evidence.metadata["transcript_stream_id"] == "stream-a"
    assert evidence.signals[0].metadata["transcript_stream_id"] == "stream-a"


def test_recording_block_context_preserved() -> None:
    recording_block_id = EntityId.new()
    evidence = _build_one_for_observation(
        _observation("segment_available", recording_block_id=recording_block_id)
    )

    assert evidence.recording_block_id == recording_block_id
    assert evidence.metadata["recording_block_id"] == recording_block_id.to_json()


def test_stage_context_preserved() -> None:
    stage_id = EntityId.new()
    evidence = _build_one_for_observation(
        _observation("segment_available", stage_id=stage_id)
    )

    assert evidence.metadata["stage_id"] == stage_id.to_json()
    assert evidence.signals[0].metadata["stage_id"] == stage_id.to_json()


def test_timeline_context_preserved() -> None:
    recording_block_id = EntityId.new()
    location = ObservationLocation.over_range(
        TimelineRange(
            TimelinePosition(recording_block_id, timedelta(seconds=10)),
            TimelinePosition(recording_block_id, timedelta(seconds=20)),
        )
    )
    evidence = _build_one_for_observation(
        _observation(
            "segment_available",
            location=location,
            recording_block_id=recording_block_id,
            metadata={"timeline_range_reference": "range-1"},
        )
    )

    location_metadata = evidence.items[0].metadata["observation_location"]
    assert location_metadata["timeline_range_start_seconds"] == 10.0
    assert location_metadata["timeline_range_end_seconds"] == 20.0
    assert evidence.items[0].metadata["timeline_range_reference"] == "range-1"


def test_unrelated_observations_ignored() -> None:
    transcript = _observation("segment_available")
    recording = _observation(
        None,
        observation_type=ObservationType.RECORDING_ACTIVITY,
        metadata={"recording_activity": "began"},
    )
    vision = _observation(
        None,
        observation_type=ObservationType.VISION_ACTIVITY,
        metadata={"visual_detection_type": "title_slide"},
    )

    result = make_transcript_continuity_evidence_builder().build(
        (recording, transcript, vision)
    )

    assert result.evidence_count == 1
    assert result.consumed_observation_ids == (transcript.id,)
    assert set(result.ignored_observation_ids) == {recording.id, vision.id}


def test_unsupported_transcript_semantics_not_guessed() -> None:
    unsupported = _observation("transcript_source_status_changed")

    result = make_transcript_continuity_evidence_builder().build((unsupported,))

    assert result.evidence_sets == ()
    assert result.unsupported_observation_ids == (unsupported.id,)


def test_duplicate_observation_ids_handled_deterministically() -> None:
    observation_id = EntityId.new()
    duplicate_a = _observation(
        "segment_available",
        observation_id=observation_id,
        observed_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    duplicate_b = _observation(
        "segment_available",
        observation_id=observation_id,
        observed_at=datetime(2026, 1, 1, 12, 1, tzinfo=UTC),
    )

    result = make_transcript_continuity_evidence_builder().build((duplicate_b, duplicate_a))

    assert result.evidence_count == 1
    assert result.duplicate_observation_ids == (observation_id,)
    assert len(result.evidence_sets[0].items) == 1


def test_distinct_transcript_streams_not_merged() -> None:
    first = _observation("segment_available", transcript_stream_id="stream-a")
    second = _observation("segment_available", transcript_stream_id="stream-b")

    result = make_transcript_continuity_evidence_builder().build((first, second))

    assert result.evidence_count == 2
    assert {evidence.metadata["transcript_stream_id"] for evidence in result.evidence_sets} == {
        "stream-a",
        "stream-b",
    }


def test_distinct_recording_blocks_not_merged() -> None:
    first_block = EntityId.new()
    second_block = EntityId.new()
    first = _observation("segment_available", recording_block_id=first_block)
    second = _observation("segment_available", recording_block_id=second_block)

    result = make_transcript_continuity_evidence_builder().build((first, second))

    assert result.evidence_count == 2


def test_distinct_stages_not_merged() -> None:
    first = _observation("segment_available", stage_id=EntityId.new())
    second = _observation("segment_available", stage_id=EntityId.new())

    result = make_transcript_continuity_evidence_builder().build((first, second))

    assert result.evidence_count == 2


def test_deterministic_chronological_ordering() -> None:
    recording_block_id = EntityId.new()
    later = _observation(
        "segment_available",
        recording_block_id=recording_block_id,
        observed_at=datetime(2026, 1, 1, 12, 1, tzinfo=UTC),
    )
    earlier = _observation(
        "segment_available",
        recording_block_id=recording_block_id,
        observed_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )

    evidence = make_transcript_continuity_evidence_builder().build(
        (later, earlier)
    ).evidence_sets[0]

    assert [signal.observation_ids[0] for signal in evidence.signals] == [
        earlier.id,
        later.id,
    ]


def test_deterministic_repeated_builds() -> None:
    observations = (
        _observation("segment_available"),
        _observation("segment_available"),
    )
    builder = make_transcript_continuity_evidence_builder()

    first = builder.build(observations)
    second = builder.build(observations)

    assert first.consumed_observation_ids == second.consumed_observation_ids
    assert [signal.signal for signal in first.evidence_sets[0].signals] == [
        signal.signal for signal in second.evidence_sets[0].signals
    ]


def test_source_observations_are_not_mutated() -> None:
    observation = _observation("segment_available")
    original_metadata = dict(observation.metadata)

    make_transcript_continuity_evidence_builder().build((observation,))

    assert dict(observation.metadata) == original_metadata


def test_transcript_content_is_not_semantically_analyzed() -> None:
    observation = _observation(
        "segment_available",
        metadata={"text_excerpt": "Please welcome the keynote speaker."},
    )

    evidence = _build_one_for_observation(observation)

    assert "keynote" not in (evidence.notes or "").lower()
    assert "speaker" not in (evidence.items[0].rationale or "").lower()
    assert evidence.signals[0].signal is EvidenceSignal.SPEECH_ACTIVITY_AVAILABLE


def test_builder_has_no_policy_or_downstream_behavior() -> None:
    names = {
        field.name
        for contract in (
            TranscriptContinuityEvidenceBuilder,
            TranscriptContinuityEvidenceRule,
            TranscriptContinuityEvidenceResult,
            TranscriptContinuityEvidenceSummary,
        )
        for field in fields(contract)
    } | {
        name
        for name, value in getmembers(TranscriptContinuityEvidenceBuilder)
        if isfunction(value)
    }
    forbidden_terms = {
        "operational_state",
        "transition_evaluation",
        "session",
        "speaker",
        "meaning",
        "hypothesis",
        "finding",
        "verification",
        "operational_product",
        "confidence_formula",
        "probability",
        "timeout",
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
    builder = TranscriptContinuityEvidenceBuilder(
        id=EntityId.new(),
        status=TranscriptContinuityEvidenceBuilderStatus.DISABLED,
    )
    observation = _observation("segment_available")

    result = builder.build((observation,))

    assert result.evidence_sets == ()
    assert result.ignored_observation_ids == (observation.id,)
