from dataclasses import fields
from datetime import UTC, datetime, timedelta
from inspect import getmembers, isfunction

from app.contexts.production.observation import ObservationType
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
from app.contexts.production.recording_activity_observation_interpreter import (
    RECORDING_ACTIVITY_OBSERVATION_MAPPINGS,
    RecordingActivityInterpreterRule,
    RecordingActivityInterpreterSummary,
    RecordingActivityObservationInterpreter,
    RecordingActivityObservationMapping,
    mapping_for_recording_activity,
)
from app.shared.ids import CorrelationId, EntityId

CONTRACTS = (
    RecordingActivityObservationInterpreter,
    RecordingActivityInterpreterRule,
    RecordingActivityInterpreterSummary,
    RecordingActivityObservationMapping,
)


def _context(recording_block_id: EntityId | None = None) -> ObservationInterpreterContext:
    return ObservationInterpreterContext(
        correlation_id=CorrelationId.new(),
        current_timestamp=datetime(2026, 7, 8, 10, 0, 2, tzinfo=UTC),
        recording_block_id=recording_block_id,
        stage_id=EntityId.new(),
        metadata={"mode": "recording-activity-contract"},
    )


def _recording_event(
    recording_event_kind: str,
    event_type: ProductionEventType,
    recording_block_id: EntityId | None = None,
    source: ProductionEventSource = ProductionEventSource.RECORDING_SYSTEM,
) -> ProductionEvent:
    occurred_at = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)
    references: list[ProductionEventReference] = []
    if recording_block_id is not None:
        references.append(
            ProductionEventReference(
                reference_type=ProductionEventReferenceType.RECORDING_BLOCK,
                referenced_id=recording_block_id,
                label="recording block",
            )
        )
    return ProductionEvent(
        id=EntityId.new(),
        event_type=event_type,
        source=source,
        payload=ProductionEventPayload({"recording_event_kind": recording_event_kind}),
        references=references,
        correlation_id=CorrelationId.new(),
        occurred_at=occurred_at,
        received_at=occurred_at + timedelta(seconds=1),
    )


def _interpreter(
    rules: list[RecordingActivityInterpreterRule] | None = None,
) -> RecordingActivityObservationInterpreter:
    return RecordingActivityObservationInterpreter(
        id=EntityId.new(),
        rules=rules or [],
        metadata={"scope": "recording-activity"},
    )


def _field_names() -> set[str]:
    return {field.name for contract in CONTRACTS for field in fields(contract)}


def _method_names() -> set[str]:
    return {
        name
        for name, value in getmembers(RecordingActivityObservationInterpreter)
        if isfunction(value)
    }


def _assert_single_observation(
    event: ProductionEvent,
    recording_block_id: EntityId,
    expected_note: str,
) -> None:
    result = _interpreter().interpret(event, _context(recording_block_id))

    assert result.source_production_event_ids == (event.id,)
    assert len(result.observations) == 1

    observation = result.observations[0]
    assert observation.recording_block_id == recording_block_id
    assert observation.observation_type is ObservationType.RECORDING_ACTIVITY
    assert observation.notes == expected_note
    assert observation.location.is_point
    assert observation.correlation_id == event.correlation_id
    assert dict(observation.metadata)["source_production_event_ids"] == (
        event.id.to_json(),
    )
    assert dict(observation.metadata)["observation_interpreter_id"] == (
        result.interpreter_id.to_json()
    )


def test_recording_activity_observation_interpreter_creation() -> None:
    rule = RecordingActivityInterpreterRule(
        id=EntityId.new(),
        description="Translate recording activity events into objective observations.",
    )
    interpreter = _interpreter(rules=[rule])

    assert interpreter.name == "Recording activity observation interpreter"
    assert interpreter.status is ObservationInterpreterStatus.ACTIVE
    assert interpreter.supported_event_sources == (ProductionEventSource.RECORDING_SYSTEM,)
    assert interpreter.intended_observation_types == (ObservationType.RECORDING_ACTIVITY,)
    assert interpreter.rules == (rule,)
    assert dict(interpreter.metadata) == {"scope": "recording-activity"}


def test_supported_production_event_types_are_recording_activity_only() -> None:
    interpreter = _interpreter()

    assert interpreter.supported_event_types == (
        ProductionEventType.RECORDING_BLOCK_STARTED,
        ProductionEventType.RECORDING_BLOCK_STATUS_CHANGED,
        ProductionEventType.RECORDING_BLOCK_ENDED,
    )
    assert interpreter.supports_event_type(ProductionEventType.RECORDING_BLOCK_STARTED)
    assert not interpreter.supports_event_type(ProductionEventType.MEDIA_FILE_FINALIZED)


def test_supported_production_event_sources_are_recording_system_only() -> None:
    interpreter = _interpreter()

    assert interpreter.supports_source(ProductionEventSource.RECORDING_SYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.SCHEDULE_SYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.TRANSCRIPT_SYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.VISION_SYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.OPERATOR)
    assert not interpreter.supports_source(ProductionEventSource.FILESYSTEM)


def test_recording_started_mapping_creates_objective_observation() -> None:
    recording_block_id = EntityId.new()
    event = _recording_event(
        "recording_started",
        ProductionEventType.RECORDING_BLOCK_STARTED,
        recording_block_id,
    )

    _assert_single_observation(event, recording_block_id, "recording activity began")


def test_recording_paused_mapping_creates_objective_observation() -> None:
    recording_block_id = EntityId.new()
    event = _recording_event(
        "recording_paused",
        ProductionEventType.RECORDING_BLOCK_STATUS_CHANGED,
        recording_block_id,
    )

    _assert_single_observation(event, recording_block_id, "recording activity paused")


def test_recording_resumed_mapping_creates_objective_observation() -> None:
    recording_block_id = EntityId.new()
    event = _recording_event(
        "recording_resumed",
        ProductionEventType.RECORDING_BLOCK_STATUS_CHANGED,
        recording_block_id,
    )

    _assert_single_observation(event, recording_block_id, "recording activity resumed")


def test_recording_stopped_mapping_creates_objective_observation() -> None:
    recording_block_id = EntityId.new()
    event = _recording_event(
        "recording_stopped",
        ProductionEventType.RECORDING_BLOCK_ENDED,
        recording_block_id,
    )

    _assert_single_observation(event, recording_block_id, "recording activity ended")


def test_unknown_event_handling_returns_zero_observations() -> None:
    recording_block_id = EntityId.new()
    event = _recording_event(
        "recording_failed",
        ProductionEventType.SYSTEM_STATUS_CHANGED,
        recording_block_id,
    )

    result = _interpreter().interpret(event, _context(recording_block_id))

    assert result.source_production_event_ids == (event.id,)
    assert result.observations == ()
    assert result.warnings == ("ProductionEvent group is not supported by this interpreter.",)


def test_missing_recording_block_returns_zero_observations() -> None:
    event = _recording_event(
        "recording_started",
        ProductionEventType.RECORDING_BLOCK_STARTED,
    )

    result = _interpreter().interpret(event, _context())

    assert result.source_production_event_ids == (event.id,)
    assert result.observations == ()


def test_context_recording_block_can_supply_location_when_event_lacks_reference() -> None:
    recording_block_id = EntityId.new()
    event = _recording_event(
        "recording_started",
        ProductionEventType.RECORDING_BLOCK_STARTED,
    )

    _assert_single_observation(event, recording_block_id, "recording activity began")


def test_interpreter_can_return_multiple_observations_for_multiple_events() -> None:
    recording_block_id = EntityId.new()
    started = _recording_event(
        "recording_started",
        ProductionEventType.RECORDING_BLOCK_STARTED,
        recording_block_id,
    )
    paused = _recording_event(
        "recording_paused",
        ProductionEventType.RECORDING_BLOCK_STATUS_CHANGED,
        recording_block_id,
    )

    result = _interpreter().interpret([started, paused], _context(recording_block_id))

    assert len(result.observations) == 2
    assert result.source_production_event_ids == (started.id, paused.id)
    for observation in result.observations:
        assert dict(observation.metadata)["source_production_event_ids"] == (
            started.id.to_json(),
            paused.id.to_json(),
        )


def test_mapping_contract_documents_supported_translations() -> None:
    recording_event_kinds = {
        mapping.recording_event_kind
        for mapping in RECORDING_ACTIVITY_OBSERVATION_MAPPINGS
    }
    started_mapping = mapping_for_recording_activity(
        ProductionEventType.RECORDING_BLOCK_STARTED,
        "recording_started",
    )

    assert recording_event_kinds == {
        "recording_started",
        "recording_paused",
        "recording_resumed",
        "recording_stopped",
    }
    assert started_mapping is not None
    assert started_mapping.observation_note == "recording activity began"


def test_recording_activity_rule_creation() -> None:
    rule = RecordingActivityInterpreterRule(
        id=EntityId.new(),
        description="Recording activity only.",
        metadata={"scope": "recording"},
    )
    base_rule = rule.to_observation_interpreter_rule()

    assert rule.supported_event_sources == (ProductionEventSource.RECORDING_SYSTEM,)
    assert rule.intended_observation_types == (ObservationType.RECORDING_ACTIVITY,)
    assert base_rule.supported_event_types == rule.supported_event_types
    assert dict(base_rule.metadata) == {"scope": "recording"}


def test_recording_activity_summary_generation() -> None:
    rule = RecordingActivityInterpreterRule(id=EntityId.new())
    interpreter = _interpreter(rules=[rule])

    summary = RecordingActivityInterpreterSummary.from_interpreter(interpreter)

    assert summary.interpreter_id == interpreter.id
    assert summary.interpreter_name == interpreter.name
    assert summary.status is ObservationInterpreterStatus.ACTIVE
    assert summary.supported_event_type_count == 3
    assert summary.supported_source_count == 1
    assert summary.intended_observation_type_count == 1
    assert summary.mapping_count == 4
    assert summary.rule_count == 1


def test_observation_wording_stays_objective() -> None:
    objective_notes = {
        mapping.observation_note for mapping in RECORDING_ACTIVITY_OBSERVATION_MAPPINGS
    }
    forbidden_terms = {
        "keynote",
        "session",
        "presentation",
        "stream",
        "audience",
        "production ready",
        "clip",
        "speaker",
        "performance",
    }

    assert objective_notes == {
        "recording activity began",
        "recording activity paused",
        "recording activity resumed",
        "recording activity ended",
    }
    assert not any(term in note for term in forbidden_terms for note in objective_notes)


def test_no_reasoning_artifacts_are_generated() -> None:
    forbidden_terms = {
        "evidence",
        "hypothesis",
        "finding",
        "verification",
        "operational_product",
        "conclusion",
        "reasoning",
        "decision",
    }

    assert not any(
        term in name for name in _field_names() | _method_names() for term in forbidden_terms
    )


def test_no_cross_domain_interpretation_exists() -> None:
    forbidden_terms = {
        "transcript",
        "schedule",
        "vision",
        "operator",
        "media_artifact",
        "ocr",
        "speaker",
        "session",
    }

    assert not any(
        term in name for name in _field_names() | _method_names() for term in forbidden_terms
    )


def test_no_provider_specific_behavior_exists() -> None:
    enum_values = {
        mapping.recording_event_kind
        for mapping in RECORDING_ACTIVITY_OBSERVATION_MAPPINGS
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

    assert not any(term in value for term in forbidden_terms for value in enum_values)
    assert not any(
        term in name for name in _field_names() | _method_names() for term in forbidden_terms
    )
