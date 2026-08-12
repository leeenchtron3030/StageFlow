from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.contexts.production.media_artifact_observation_interpreter import (
    MediaArtifactObservationInterpreter,
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
from app.contexts.production.observation_interpreter import (
    ObservationInterpreterContext,
    observation_context_from_event,
)
from app.contexts.production.production_event import (
    ProductionEvent,
    ProductionEventPayload,
    ProductionEventReference,
    ProductionEventReferenceType,
    ProductionEventSource,
    ProductionEventType,
)
from app.contexts.production.recording_activity_observation_interpreter import (
    RecordingActivityObservationInterpreter,
)
from app.contexts.production.recording_coverage_evidence_builder import (
    make_recording_coverage_evidence_builder,
)
from app.contexts.production.session_boundary_evidence_builder import (
    make_session_boundary_evidence_builder,
)
from app.contexts.production.session_transition_policy import (
    make_session_transition_policy,
)
from app.contexts.production.transcript_continuity_evidence_builder import (
    make_transcript_continuity_evidence_builder,
)
from app.contexts.production.transcript_observation_interpreter import (
    TranscriptObservationInterpreter,
)
from app.shared.ids import CorrelationId, EntityId
from tests.timestamp_fixtures import AWARE_TIMESTAMP

EVENT_TIME = datetime(2026, 7, 16, 10, 0, tzinfo=timezone(timedelta(hours=-7)))
OBSERVATION_TIME = datetime(2026, 7, 16, 17, 0, 2, tzinfo=UTC)


def _context(
    *,
    correlation_id: CorrelationId,
    recording_block_id: EntityId | None = None,
    stage_id: EntityId | None = None,
) -> ObservationInterpreterContext:
    return ObservationInterpreterContext(
        correlation_id=correlation_id,
        current_timestamp=OBSERVATION_TIME,
        recording_block_id=recording_block_id,
        stage_id=stage_id,
    )


def _event(
    *,
    event_type: ProductionEventType,
    source: ProductionEventSource,
    payload: dict[str, object],
    correlation_id: CorrelationId,
    stage_id: EntityId | None = None,
    recording_block_id: EntityId | None = None,
    metadata: dict[str, object] | None = None,
) -> ProductionEvent:
    references: list[ProductionEventReference] = []
    if stage_id is not None:
        references.append(
            ProductionEventReference(
                reference_type=ProductionEventReferenceType.STAGE,
                referenced_id=stage_id,
            )
        )
    if recording_block_id is not None:
        references.append(
            ProductionEventReference(
                reference_type=ProductionEventReferenceType.RECORDING_BLOCK,
                referenced_id=recording_block_id,
            )
        )
    return ProductionEvent(
        id=EntityId.new(),
        event_type=event_type,
        source=source,
        payload=ProductionEventPayload(payload),
        correlation_id=correlation_id,
        occurred_at=EVENT_TIME,
        received_at=EVENT_TIME + timedelta(seconds=1),
        references=tuple(references),
        metadata=metadata or {},
    )


def _recording_event(
    *,
    correlation_id: CorrelationId,
    stage_id: EntityId,
    recording_block_id: EntityId,
    ended: bool = False,
) -> ProductionEvent:
    return _event(
        event_type=(
            ProductionEventType.RECORDING_BLOCK_ENDED
            if ended
            else ProductionEventType.RECORDING_BLOCK_STARTED
        ),
        source=ProductionEventSource.RECORDING_SYSTEM,
        payload={
            "recording_event_kind": "recording_stopped" if ended else "recording_started",
            "recording_system_id": "recorder-a",
        },
        correlation_id=correlation_id,
        stage_id=stage_id,
        recording_block_id=recording_block_id,
    )


def _transcript_event(
    *,
    correlation_id: CorrelationId,
    stage_id: EntityId,
    recording_block_id: EntityId,
    stream_id: str = "stream-a",
) -> ProductionEvent:
    return _event(
        event_type=ProductionEventType.TRANSCRIPT_SEGMENT_AVAILABLE,
        source=ProductionEventSource.TRANSCRIPT_SYSTEM,
        payload={
            "transcript_segment_id": "segment-a",
            "transcript_stream_id": stream_id,
        },
        correlation_id=correlation_id,
        stage_id=stage_id,
        recording_block_id=recording_block_id,
        metadata={"stream_id": stream_id, "transcript_adapter_event": True},
    )


def test_provenance_and_context_are_immutable_id_only_contracts() -> None:
    provenance = ObservationProvenance(
        source_event_id=EntityId.new(),
        source_event_type=ProductionEventType.RECORDING_BLOCK_STARTED,
        source_event_occurred_at=EVENT_TIME,
        interpreter_kind="recording_activity_interpreter",
        interpreter_id=EntityId.new(),
        interpretation_rule_id="recording_activity:recording_started",
        producer_identifier="recorder-a",
        metadata={"origin": "adapter"},
    )
    context = ObservationContext(
        stage_id=EntityId.new(),
        recording_block_id=EntityId.new(),
        correlation_id=CorrelationId.new(),
        transcript_stream_id="stream-a",
        media_artifact_id="artifact-a",
        metadata={"stage_id_source": "event.references.stage"},
    )

    with pytest.raises(FrozenInstanceError):
        provenance.interpreter_kind = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        context.stage_id = EntityId.new()  # type: ignore[misc]
    with pytest.raises(TypeError):
        provenance.metadata["origin"] = "changed"  # type: ignore[index]
    with pytest.raises(TypeError):
        context.metadata["stage_id_source"] = "changed"  # type: ignore[index]

    assert all(
        not isinstance(getattr(provenance, item.name), ProductionEvent)
        for item in fields(ObservationProvenance)
    )
    assert all(
        not isinstance(getattr(context, item.name), ProductionEvent)
        for item in fields(ObservationContext)
    )


def test_legacy_observation_construction_derives_first_class_context() -> None:
    recording_block_id = EntityId.new()
    correlation_id = CorrelationId.new()
    observation = Observation(
                      observed_at=AWARE_TIMESTAMP,

        id=EntityId.new(),
        recording_block_id=recording_block_id,
        observation_type=ObservationType.UNKNOWN,
        observation_source=ObservationSource.SYSTEM,
        location=ObservationLocation.for_recording_block(recording_block_id),
        confidence=ObservationConfidence(1.0),
        correlation_id=correlation_id,
    )

    assert observation.provenance is None
    assert observation.context.recording_block_id == recording_block_id
    assert observation.context.correlation_id == correlation_id


def test_recording_interpreter_preserves_exact_lineage_context_and_time() -> None:
    correlation_id = CorrelationId.new()
    stage_id = EntityId.new()
    recording_block_id = EntityId.new()
    event = _recording_event(
        correlation_id=correlation_id,
        stage_id=stage_id,
        recording_block_id=recording_block_id,
    )
    original_metadata = dict(event.metadata)
    interpreter = RecordingActivityObservationInterpreter(id=EntityId.new())

    result = interpreter.interpret(
        event,
        _context(correlation_id=correlation_id),
    )
    observation = result.observations[0]

    assert observation.provenance is not None
    assert observation.provenance.source_event_id == event.id
    assert observation.provenance.source_event_type is event.event_type
    assert observation.provenance.source_event_occurred_at == EVENT_TIME
    source_event_time = observation.provenance.source_event_occurred_at
    assert source_event_time is not None
    assert source_event_time.utcoffset() == timedelta(hours=-7)
    assert observation.provenance.interpreter_id == interpreter.id
    assert observation.provenance.interpreter_kind == "recording_activity_interpreter"
    assert observation.provenance.interpretation_rule_id is not None
    assert observation.provenance.producer_identifier == "recorder-a"
    assert observation.observed_at == OBSERVATION_TIME
    assert observation.observed_at != observation.provenance.source_event_occurred_at
    assert observation.context.stage_id == stage_id
    assert observation.context.recording_block_id == recording_block_id
    assert observation.context.correlation_id == correlation_id
    assert dict(event.metadata) == original_metadata


def test_equivalent_transcript_stream_candidates_and_unknown_context_are_deterministic() -> None:
    correlation_id = CorrelationId.new()
    stage_id = EntityId.new()
    recording_block_id = EntityId.new()
    event = _transcript_event(
        correlation_id=correlation_id,
        stage_id=stage_id,
        recording_block_id=recording_block_id,
        stream_id="payload-stream",
    )
    observation = TranscriptObservationInterpreter(id=EntityId.new()).interpret(
        event,
        _context(correlation_id=correlation_id),
    ).observations[0]

    assert observation.context.transcript_stream_id == "payload-stream"
    assert (
        observation.context.metadata["transcript_stream_id_source"]
        == "event_payload.transcript_stream_id"
    )

    context = observation_context_from_event(
        _event(
            event_type=ProductionEventType.SYSTEM_STATUS_CHANGED,
            source=ProductionEventSource.INTERNAL_SYSTEM,
            payload={},
            correlation_id=correlation_id,
        ),
        _context(correlation_id=correlation_id),
    )
    assert context.stage_id is None
    assert context.recording_block_id is None
    assert context.transcript_stream_id is None
    assert context.media_artifact_id is None


def test_equivalent_reference_and_metadata_context_is_recorded() -> None:
    correlation_id = CorrelationId.new()
    referenced_stage_id = EntityId.new()
    event = _event(
        event_type=ProductionEventType.MEDIA_FILE_CREATED,
        source=ProductionEventSource.INTERNAL_SYSTEM,
        payload={"artifact_id": "artifact-a"},
        correlation_id=correlation_id,
        stage_id=referenced_stage_id,
        metadata={"stage_id": referenced_stage_id.to_json()},
    )
    context = observation_context_from_event(
        event,
        _context(correlation_id=correlation_id),
    )

    assert context.stage_id == referenced_stage_id
    assert context.metadata["stage_id_source"] == "event.references.stage"

    fallback_event = replace(event, references=())
    fallback_context = observation_context_from_event(
        fallback_event,
        _context(correlation_id=correlation_id),
    )
    assert fallback_context.stage_id == referenced_stage_id
    assert fallback_context.metadata["stage_id_source"] == "event_metadata.stage_id"


def test_media_schedule_artifact_and_correlation_context_are_preserved() -> None:
    correlation_id = CorrelationId.new()
    scheduled_activity_id = EntityId.new()
    event = _event(
        event_type=ProductionEventType.MEDIA_FILE_FINALIZED,
        source=ProductionEventSource.INTERNAL_SYSTEM,
        payload={"artifact_id": "artifact-a"},
        correlation_id=correlation_id,
    )
    event = replace(
        event,
        references=(
            ProductionEventReference(
                reference_type=ProductionEventReferenceType.MEDIA_FILE,
                external_reference="artifact-a",
            ),
            ProductionEventReference(
                reference_type=ProductionEventReferenceType.SCHEDULE_ARTIFACT,
                referenced_id=scheduled_activity_id,
            ),
        ),
    )
    observation = MediaArtifactObservationInterpreter(id=EntityId.new()).interpret(
        event,
        _context(correlation_id=correlation_id),
    ).observations[0]

    assert observation.context.media_artifact_id == "artifact-a"
    assert observation.context.scheduled_activity_id == scheduled_activity_id
    assert observation.context.correlation_id == correlation_id


def test_evidence_builders_prefer_first_class_context_and_retain_lineage() -> None:
    correlation_id = CorrelationId.new()
    stage_id = EntityId.new()
    conflicting_stage_id = EntityId.new()
    recording_block_id = EntityId.new()
    event = _recording_event(
        correlation_id=correlation_id,
        stage_id=stage_id,
        recording_block_id=recording_block_id,
    )
    observation = RecordingActivityObservationInterpreter(id=EntityId.new()).interpret(
        event,
        _context(correlation_id=correlation_id),
    ).observations[0]
    observation = replace(
        observation,
        metadata={**observation.metadata, "stage_id": conflicting_stage_id.to_json()},
    )

    evidence_set = make_recording_coverage_evidence_builder().build(
        (observation,)
    ).evidence_sets[0]
    item = evidence_set.items[0]

    assert evidence_set.metadata["stage_id"] == stage_id.to_json()
    assert evidence_set.metadata["source_production_event_ids"] == (
        event.id.to_json(),
    )
    assert item.observation_id == observation.id
    assert item.metadata["source_production_event_id"] == event.id.to_json()


def test_recording_and_transcript_lineage_reaches_transition_evaluation() -> None:
    correlation_id = CorrelationId.new()
    stage_id = EntityId.new()
    recording_block_id = EntityId.new()
    recording_event = _recording_event(
        correlation_id=correlation_id,
        stage_id=stage_id,
        recording_block_id=recording_block_id,
    )
    transcript_event = _transcript_event(
        correlation_id=correlation_id,
        stage_id=stage_id,
        recording_block_id=recording_block_id,
    )
    context = _context(correlation_id=correlation_id)
    recording_observation = RecordingActivityObservationInterpreter(
        id=EntityId.new()
    ).interpret(recording_event, context).observations[0]
    transcript_observation = TranscriptObservationInterpreter(
        id=EntityId.new()
    ).interpret(transcript_event, context).observations[0]
    recording_evidence = make_recording_coverage_evidence_builder().build(
        (recording_observation,)
    ).evidence_sets[0]
    transcript_evidence = make_transcript_continuity_evidence_builder().build(
        (transcript_observation,)
    ).evidence_sets[0]
    boundary = make_session_boundary_evidence_builder().build(
        (recording_evidence, transcript_evidence)
    ).start_boundary_evidence_sets[0]
    transition = make_session_transition_policy().evaluate(
        current_state=None,
        evidence_sets=(boundary,),
        evaluated_at=OBSERVATION_TIME,
    )

    source_event_ids = transition.evaluation.metadata["source_production_event_ids"]
    assert set(source_event_ids) == {
        recording_event.id.to_json(),
        transcript_event.id.to_json(),
    }
    assert transition.evidence_profile is not None
    assert set(
        transition.evidence_profile.metadata["source_production_event_ids"]
    ) == set(source_event_ids)


def test_session_end_lineage_retains_two_exact_source_events() -> None:
    correlation_id = CorrelationId.new()
    stage_id = EntityId.new()
    recording_block_id = EntityId.new()
    recording_event = _recording_event(
        correlation_id=correlation_id,
        stage_id=stage_id,
        recording_block_id=recording_block_id,
        ended=True,
    )
    transcript_event = _transcript_event(
        correlation_id=correlation_id,
        stage_id=stage_id,
        recording_block_id=recording_block_id,
    )
    context = _context(correlation_id=correlation_id)
    recording_observation = RecordingActivityObservationInterpreter(
        id=EntityId.new()
    ).interpret(recording_event, context).observations[0]
    transcript_observation = TranscriptObservationInterpreter(
        id=EntityId.new()
    ).interpret(transcript_event, context).observations[0]
    transcript_observation = replace(
        transcript_observation,
        metadata={
            **transcript_observation.metadata,
            "transcript_lifecycle": "transcript_activity_ended",
        },
    )
    recording_evidence = make_recording_coverage_evidence_builder().build(
        (recording_observation,)
    ).evidence_sets[0]
    transcript_evidence = make_transcript_continuity_evidence_builder().build(
        (transcript_observation,)
    ).evidence_sets[0]
    boundary = make_session_boundary_evidence_builder().build(
        (recording_evidence, transcript_evidence)
    ).end_boundary_evidence_sets[0]
    transition = make_session_transition_policy().evaluate(
        current_state=None,
        evidence_sets=(boundary,),
        evaluated_at=OBSERVATION_TIME,
    )

    assert set(transition.evaluation.metadata["source_production_event_ids"]) == {
        recording_event.id.to_json(),
        transcript_event.id.to_json(),
    }
