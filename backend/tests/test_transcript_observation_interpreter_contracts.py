from dataclasses import fields
from datetime import UTC, datetime, timedelta
from inspect import getmembers, isfunction

from app.contexts.production.observation import (
    ObservationLocationKind,
    ObservationSource,
    ObservationType,
)
from app.contexts.production.observation_interpreter import (
    ObservationInterpreterContext,
    ObservationInterpreterStatus,
)
from app.contexts.production.production_event import (
    ProductionEvent,
    ProductionEventPayload,
    ProductionEventReference,
    ProductionEventReferenceType,
    ProductionEventSource,
    ProductionEventType,
)
from app.contexts.production.transcript_observation_interpreter import (
    TRANSCRIPT_OBSERVATION_MAPPINGS,
    TranscriptInterpreterRule,
    TranscriptInterpreterSummary,
    TranscriptObservationInterpreter,
    TranscriptObservationMapping,
    mapping_for_transcript,
)
from app.shared.ids import CorrelationId, EntityId

CONTRACTS = (
    TranscriptObservationInterpreter,
    TranscriptInterpreterRule,
    TranscriptInterpreterSummary,
    TranscriptObservationMapping,
)


TRANSCRIPT_TEXT = "Please welcome our keynote speaker."


def _context(recording_block_id: EntityId | None = None) -> ObservationInterpreterContext:
    return ObservationInterpreterContext(
        correlation_id=CorrelationId.new(),
        current_timestamp=datetime(2026, 7, 9, 10, 0, 2, tzinfo=UTC),
        recording_block_id=recording_block_id,
        stage_id=EntityId.new(),
        metadata={"mode": "transcript-contract"},
    )


def _transcript_event(
    segment_status: str,
    event_type: ProductionEventType,
    recording_block_id: EntityId | None = None,
    source: ProductionEventSource = ProductionEventSource.TRANSCRIPT_SYSTEM,
    transcript_adapter_event: bool = True,
    text_excerpt: str | None = TRANSCRIPT_TEXT,
) -> ProductionEvent:
    occurred_at = datetime(2026, 7, 9, 10, 0, tzinfo=UTC)
    references = [
        ProductionEventReference(
            reference_type=ProductionEventReferenceType.EXTERNAL_OBJECT,
            external_reference="segment-123",
            label="transcript segment",
        ),
        ProductionEventReference(
            reference_type=ProductionEventReferenceType.TIMELINE_RANGE,
            external_reference="range-123",
            label="timeline range",
        ),
    ]
    if recording_block_id is not None:
        references.append(
            ProductionEventReference(
                reference_type=ProductionEventReferenceType.RECORDING_BLOCK,
                referenced_id=recording_block_id,
                label="recording block",
            )
        )

    payload: dict[str, object] = {
        "transcript_segment_id": "segment-123",
        "transcript_artifact_type": "partial_transcript",
        "transcript_segment_status": segment_status,
        "timeline_range_reference": "range-123",
        "language_label": "en",
        "confidence": 0.82,
    }
    if text_excerpt is not None:
        payload["text_excerpt"] = text_excerpt

    return ProductionEvent(
        id=EntityId.new(),
        event_type=event_type,
        source=source,
        payload=ProductionEventPayload(payload),
        references=references,
        correlation_id=CorrelationId.new(),
        occurred_at=occurred_at,
        received_at=occurred_at + timedelta(seconds=1),
        metadata={"transcript_adapter_event": transcript_adapter_event},
    )


def _interpreter(
    rules: list[TranscriptInterpreterRule] | None = None,
) -> TranscriptObservationInterpreter:
    return TranscriptObservationInterpreter(
        id=EntityId.new(),
        rules=rules or [],
        metadata={"scope": "transcript"},
    )


transcript_event_fixture = _transcript_event
interpreter_fixture = _interpreter


def _field_names() -> set[str]:
    return {field.name for contract in CONTRACTS for field in fields(contract)}


def _method_names() -> set[str]:
    return {
        name
        for name, value in getmembers(TranscriptObservationInterpreter)
        if isfunction(value)
    }


def _assert_single_observation(
    event: ProductionEvent,
    expected_note: str,
    recording_block_id: EntityId | None = None,
) -> None:
    result = _interpreter().interpret(event, _context(recording_block_id))

    assert result.source_production_event_ids == (event.id,)
    assert len(result.observations) == 1

    observation = result.observations[0]
    assert observation.observation_type is ObservationType.TRANSCRIPT_ACTIVITY
    assert observation.observation_source is ObservationSource.TRANSCRIPT
    assert observation.notes == expected_note
    assert observation.correlation_id == event.correlation_id
    assert dict(observation.metadata)["source_production_event_ids"] == (
        event.id.to_json(),
    )
    assert dict(observation.metadata)["observation_interpreter_id"] == (
        result.interpreter_id.to_json()
    )


def test_transcript_observation_interpreter_creation() -> None:
    rule = TranscriptInterpreterRule(
        id=EntityId.new(),
        description="Translate transcript events into objective observations.",
    )
    interpreter = _interpreter(rules=[rule])

    assert interpreter.name == "Transcript observation interpreter"
    assert interpreter.status is ObservationInterpreterStatus.ACTIVE
    assert interpreter.supported_event_sources == (ProductionEventSource.TRANSCRIPT_SYSTEM,)
    assert interpreter.intended_observation_types == (ObservationType.TRANSCRIPT_ACTIVITY,)
    assert interpreter.rules == (rule,)
    assert dict(interpreter.metadata) == {"scope": "transcript"}


def test_supported_production_event_types_are_transcript_related_only() -> None:
    interpreter = _interpreter()

    assert interpreter.supported_event_types == (
        ProductionEventType.TRANSCRIPT_SEGMENT_AVAILABLE,
        ProductionEventType.SYSTEM_STATUS_CHANGED,
    )
    assert interpreter.supports_event_type(ProductionEventType.TRANSCRIPT_SEGMENT_AVAILABLE)
    assert not interpreter.supports_event_type(ProductionEventType.MEDIA_FILE_FINALIZED)


def test_supported_production_event_sources_are_transcript_system_only() -> None:
    interpreter = _interpreter()

    assert interpreter.supports_source(ProductionEventSource.TRANSCRIPT_SYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.SCHEDULE_SYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.RECORDING_SYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.VISION_SYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.OPERATOR)
    assert not interpreter.supports_source(ProductionEventSource.INTERNAL_SYSTEM)


def test_transcript_segment_available_mapping_creates_objective_observation() -> None:
    recording_block_id = EntityId.new()
    event = _transcript_event(
        "created",
        ProductionEventType.TRANSCRIPT_SEGMENT_AVAILABLE,
        recording_block_id,
    )

    _assert_single_observation(event, "Transcript segment became available.", recording_block_id)


def test_transcript_related_system_status_changed_mapping_creates_observation() -> None:
    event = _transcript_event(
        "failed",
        ProductionEventType.SYSTEM_STATUS_CHANGED,
        transcript_adapter_event=True,
    )

    _assert_single_observation(event, "Transcript source status changed.")


def test_non_transcript_system_status_changed_is_ignored_when_distinguishable() -> None:
    event = _transcript_event(
        "failed",
        ProductionEventType.SYSTEM_STATUS_CHANGED,
        transcript_adapter_event=False,
    )

    result = _interpreter().interpret(event, _context())

    assert result.source_production_event_ids == (event.id,)
    assert result.observations == ()


def test_unknown_event_handling_returns_zero_observations() -> None:
    event = _transcript_event(
        "created",
        ProductionEventType.UNKNOWN,
    )

    result = _interpreter().interpret(event, _context())

    assert result.source_production_event_ids == (event.id,)
    assert result.observations == ()
    assert result.warnings == ("ProductionEvent group is not supported by this interpreter.",)


def test_wrong_source_returns_zero_observations() -> None:
    event = _transcript_event(
        "created",
        ProductionEventType.TRANSCRIPT_SEGMENT_AVAILABLE,
        source=ProductionEventSource.SCHEDULE_SYSTEM,
    )

    result = _interpreter().interpret(event, _context())

    assert result.source_production_event_ids == (event.id,)
    assert result.observations == ()
    assert result.warnings == ("ProductionEvent group is not supported by this interpreter.",)


def test_recording_block_location_is_used_when_available() -> None:
    recording_block_id = EntityId.new()
    event = _transcript_event(
        "created",
        ProductionEventType.TRANSCRIPT_SEGMENT_AVAILABLE,
        recording_block_id,
    )

    result = _interpreter().interpret(event, _context())
    observation = result.observations[0]

    assert observation.recording_block_id == recording_block_id
    assert observation.location.kind is ObservationLocationKind.RECORDING_BLOCK
    assert observation.location.recording_block_id == recording_block_id
    assert observation.location.point is None


def test_wall_clock_location_is_used_without_recording_block() -> None:
    event = _transcript_event(
        "created",
        ProductionEventType.TRANSCRIPT_SEGMENT_AVAILABLE,
    )

    result = _interpreter().interpret(event, _context())
    observation = result.observations[0]

    assert observation.recording_block_id is None
    assert observation.location.kind is ObservationLocationKind.WALL_CLOCK
    assert observation.location.wall_clock_at == event.occurred_at
    assert observation.location.point is None
    assert observation.location.range is None


def test_transcript_text_is_preserved_exactly_as_observed_data() -> None:
    event = _transcript_event(
        "created",
        ProductionEventType.TRANSCRIPT_SEGMENT_AVAILABLE,
        text_excerpt=TRANSCRIPT_TEXT,
    )

    result = _interpreter().interpret(event, _context())
    metadata = dict(result.observations[0].metadata)

    assert metadata["text_excerpt"] == TRANSCRIPT_TEXT
    assert metadata["language_is_not_meaning"] is True
    assert result.observations[0].notes == "Transcript segment became available."


def test_interpreter_can_return_multiple_observations_for_multiple_events() -> None:
    first = _transcript_event("created", ProductionEventType.TRANSCRIPT_SEGMENT_AVAILABLE)
    second = _transcript_event("finalized", ProductionEventType.TRANSCRIPT_SEGMENT_AVAILABLE)

    result = _interpreter().interpret([first, second], _context())

    assert len(result.observations) == 2
    assert result.source_production_event_ids == (first.id, second.id)
    for observation in result.observations:
        assert dict(observation.metadata)["source_production_event_ids"] == (
            first.id.to_json(),
            second.id.to_json(),
        )


def test_mapping_contract_documents_supported_translations() -> None:
    event_types = {mapping.production_event_type for mapping in TRANSCRIPT_OBSERVATION_MAPPINGS}
    available_mapping = mapping_for_transcript(
        ProductionEventType.TRANSCRIPT_SEGMENT_AVAILABLE,
    )

    assert event_types == {
        ProductionEventType.TRANSCRIPT_SEGMENT_AVAILABLE,
        ProductionEventType.SYSTEM_STATUS_CHANGED,
    }
    assert available_mapping is not None
    assert available_mapping.observation_note == "Transcript segment became available."


def test_transcript_rule_creation() -> None:
    rule = TranscriptInterpreterRule(
        id=EntityId.new(),
        description="Transcript source events only.",
        metadata={"scope": "language-availability"},
    )
    base_rule = rule.to_observation_interpreter_rule()

    assert rule.supported_event_sources == (ProductionEventSource.TRANSCRIPT_SYSTEM,)
    assert rule.intended_observation_types == (ObservationType.TRANSCRIPT_ACTIVITY,)
    assert base_rule.supported_event_types == rule.supported_event_types
    assert dict(base_rule.metadata) == {"scope": "language-availability"}


def test_transcript_summary_generation() -> None:
    rule = TranscriptInterpreterRule(id=EntityId.new())
    interpreter = _interpreter(rules=[rule])

    summary = TranscriptInterpreterSummary.from_interpreter(interpreter)

    assert summary.interpreter_id == interpreter.id
    assert summary.interpreter_name == interpreter.name
    assert summary.status is ObservationInterpreterStatus.ACTIVE
    assert summary.supported_event_type_count == 2
    assert summary.supported_source_count == 1
    assert summary.intended_observation_type_count == 1
    assert summary.mapping_count == 2
    assert summary.rule_count == 1


def test_observation_wording_stays_about_language_availability() -> None:
    objective_notes = {mapping.observation_note for mapping in TRANSCRIPT_OBSERVATION_MAPPINGS}
    forbidden_terms = {
        "keynote",
        "applause",
        "introduction",
        "speaker",
        "topic",
        "sentiment",
        "session",
        "meaning",
    }

    assert objective_notes == {
        "Transcript segment became available.",
        "Transcript source status changed.",
    }
    assert not any(term in note.lower() for term in forbidden_terms for note in objective_notes)


def test_no_language_understanding_speaker_sentiment_topic_or_reasoning_exists() -> None:
    forbidden_terms = {
        "summarize",
        "classify",
        "intent",
        "speaker",
        "sentiment",
        "topic",
        "session",
        "evidence",
        "hypothesis",
        "finding",
        "verification",
        "operational_product",
        "conclusion",
        "reasoning",
    }

    assert not any(
        term in name for name in _field_names() | _method_names() for term in forbidden_terms
    )


def test_no_cross_domain_interpretation_exists() -> None:
    forbidden_terms = {
        "recording_activity",
        "media_artifact",
        "schedule",
        "vision",
        "operator",
        "ocr",
    }

    assert not any(
        term in name for name in _field_names() | _method_names() for term in forbidden_terms
    )


def test_no_provider_specific_behavior_exists() -> None:
    lifecycle_values = {
        mapping.transcript_lifecycle for mapping in TRANSCRIPT_OBSERVATION_MAPPINGS
    }
    forbidden_terms = {
        "pretalx",
        "whisper",
        "deepgram",
        "assemblyai",
        "opencv",
        "vmix",
        "youtube",
        "provider",
        "vendor",
        "brand",
    }

    assert not any(term in value for term in forbidden_terms for value in lifecycle_values)
    assert not any(
        term in name for name in _field_names() | _method_names() for term in forbidden_terms
    )
