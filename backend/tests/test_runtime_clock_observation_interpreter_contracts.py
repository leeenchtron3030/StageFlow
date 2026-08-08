from dataclasses import fields
from datetime import UTC, datetime, timedelta
from inspect import getmembers, isfunction

from app.contexts.production.observation import ObservationLocationKind, ObservationType
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
from app.contexts.production.runtime_clock_observation_interpreter import (
    RUNTIME_CLOCK_OBSERVATION_MAPPINGS,
    RuntimeClockInterpreterRule,
    RuntimeClockInterpreterSummary,
    RuntimeClockObservationInterpreter,
    RuntimeClockObservationMapping,
    mapping_for_runtime_clock,
)
from app.shared.ids import CorrelationId, EntityId

CONTRACTS = (
    RuntimeClockObservationInterpreter,
    RuntimeClockInterpreterRule,
    RuntimeClockInterpreterSummary,
    RuntimeClockObservationMapping,
)


def _context(recording_block_id: EntityId | None = None) -> ObservationInterpreterContext:
    return ObservationInterpreterContext(
        correlation_id=CorrelationId.new(),
        current_timestamp=datetime(2026, 7, 9, 10, 0, 2, tzinfo=UTC),
        recording_block_id=recording_block_id,
        stage_id=EntityId.new(),
        metadata={"mode": "runtime-clock-contract"},
    )


def _clock_event(
    boundary_type: str,
    event_type: ProductionEventType,
    recording_block_id: EntityId | None = None,
    source: ProductionEventSource = ProductionEventSource.TIMER,
    runtime_clock_event: bool = True,
) -> ProductionEvent:
    occurred_at = datetime(2026, 7, 9, 10, 0, tzinfo=UTC)
    clock_id = EntityId.new()
    references = [
        ProductionEventReference(
            reference_type=ProductionEventReferenceType.SYSTEM,
            referenced_id=clock_id,
            label="runtime clock",
        ),
        ProductionEventReference(
            reference_type=ProductionEventReferenceType.EXTERNAL_OBJECT,
            external_reference=EntityId.new().to_json(),
            label="time boundary",
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

    return ProductionEvent(
        id=EntityId.new(),
        event_type=event_type,
        source=source,
        payload=ProductionEventPayload(
            {
                "clock_id": clock_id.to_json(),
                "time_boundary_id": EntityId.new().to_json(),
                "boundary_type": boundary_type,
                "boundary_crossed_at": occurred_at.isoformat(),
            }
        ),
        references=references,
        correlation_id=CorrelationId.new(),
        occurred_at=occurred_at,
        received_at=occurred_at + timedelta(seconds=1),
        metadata={"runtime_clock_event": runtime_clock_event},
    )


def _interpreter(
    rules: list[RuntimeClockInterpreterRule] | None = None,
) -> RuntimeClockObservationInterpreter:
    return RuntimeClockObservationInterpreter(
        id=EntityId.new(),
        rules=rules or [],
        metadata={"scope": "runtime-clock"},
    )


clock_event_fixture = _clock_event
interpreter_fixture = _interpreter


def _field_names() -> set[str]:
    return {field.name for contract in CONTRACTS for field in fields(contract)}


def _method_names() -> set[str]:
    return {
        name
        for name, value in getmembers(RuntimeClockObservationInterpreter)
        if isfunction(value)
    }


def _assert_single_observation(
    event: ProductionEvent,
    expected_note: str,
) -> None:
    result = _interpreter().interpret(event, _context())

    assert result.source_production_event_ids == (event.id,)
    assert len(result.observations) == 1

    observation = result.observations[0]
    assert observation.observation_type is ObservationType.TIME_BOUNDARY
    assert observation.notes == expected_note
    assert observation.location.kind is ObservationLocationKind.WALL_CLOCK
    assert observation.location.wall_clock_at == event.occurred_at
    assert not observation.location.is_point
    assert observation.location.point is None
    assert observation.correlation_id == event.correlation_id
    assert dict(observation.metadata)["source_production_event_ids"] == (
        event.id.to_json(),
    )
    assert dict(observation.metadata)["observation_interpreter_id"] == (
        result.interpreter_id.to_json()
    )


def test_runtime_clock_observation_interpreter_creation() -> None:
    rule = RuntimeClockInterpreterRule(
        id=EntityId.new(),
        description="Translate runtime clock events into objective observations.",
    )
    interpreter = _interpreter(rules=[rule])

    assert interpreter.name == "Runtime clock observation interpreter"
    assert interpreter.status is ObservationInterpreterStatus.ACTIVE
    assert interpreter.supported_event_sources == (ProductionEventSource.TIMER,)
    assert interpreter.intended_observation_types == (ObservationType.TIME_BOUNDARY,)
    assert interpreter.rules == (rule,)
    assert dict(interpreter.metadata) == {"scope": "runtime-clock"}


def test_supported_production_event_types_are_clock_related_only() -> None:
    interpreter = _interpreter()

    assert interpreter.supported_event_types == (
        ProductionEventType.SCHEDULE_BOUNDARY_REACHED,
        ProductionEventType.TIMER_ELAPSED,
        ProductionEventType.SYSTEM_STATUS_CHANGED,
    )
    assert interpreter.supports_event_type(ProductionEventType.TIMER_ELAPSED)
    assert not interpreter.supports_event_type(ProductionEventType.MEDIA_FILE_FINALIZED)


def test_supported_production_event_sources_are_timer_only() -> None:
    interpreter = _interpreter()

    assert interpreter.supports_source(ProductionEventSource.TIMER)
    assert not interpreter.supports_source(ProductionEventSource.SCHEDULE_SYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.RECORDING_SYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.TRANSCRIPT_SYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.VISION_SYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.OPERATOR)
    assert not interpreter.supports_source(ProductionEventSource.INTERNAL_SYSTEM)


def test_schedule_boundary_reached_mapping_creates_objective_observation() -> None:
    event = _clock_event(
        "scheduled_activity_start",
        ProductionEventType.SCHEDULE_BOUNDARY_REACHED,
    )

    _assert_single_observation(event, "Scheduled time boundary was reached.")


def test_timer_elapsed_mapping_creates_objective_observation() -> None:
    event = _clock_event(
        "heartbeat_due",
        ProductionEventType.TIMER_ELAPSED,
    )

    _assert_single_observation(event, "Timer boundary elapsed.")


def test_clock_related_system_status_changed_mapping_creates_observation() -> None:
    event = _clock_event(
        "unknown",
        ProductionEventType.SYSTEM_STATUS_CHANGED,
        runtime_clock_event=True,
    )

    _assert_single_observation(event, "Runtime clock status changed.")


def test_non_clock_system_status_changed_is_ignored_when_distinguishable() -> None:
    event = _clock_event(
        "unknown",
        ProductionEventType.SYSTEM_STATUS_CHANGED,
        runtime_clock_event=False,
    )

    result = _interpreter().interpret(event, _context())

    assert result.source_production_event_ids == (event.id,)
    assert result.observations == ()


def test_unknown_event_handling_returns_zero_observations() -> None:
    event = _clock_event(
        "custom",
        ProductionEventType.UNKNOWN,
    )

    result = _interpreter().interpret(event, _context())

    assert result.source_production_event_ids == (event.id,)
    assert result.observations == ()
    assert result.warnings == ("ProductionEvent group is not supported by this interpreter.",)


def test_wrong_source_returns_zero_observations() -> None:
    event = _clock_event(
        "heartbeat_due",
        ProductionEventType.TIMER_ELAPSED,
        source=ProductionEventSource.SCHEDULE_SYSTEM,
    )

    result = _interpreter().interpret(event, _context())

    assert result.source_production_event_ids == (event.id,)
    assert result.observations == ()
    assert result.warnings == ("ProductionEvent group is not supported by this interpreter.",)


def test_wall_clock_location_is_preferred_over_recording_block() -> None:
    recording_block_id = EntityId.new()
    event = _clock_event(
        "scheduled_activity_start",
        ProductionEventType.SCHEDULE_BOUNDARY_REACHED,
        recording_block_id,
    )

    result = _interpreter().interpret(event, _context(recording_block_id))
    observation = result.observations[0]

    assert observation.recording_block_id == recording_block_id
    assert observation.location.kind is ObservationLocationKind.WALL_CLOCK
    assert observation.location.wall_clock_at == event.occurred_at
    assert observation.location.point is None


def test_interpreter_can_return_multiple_observations_for_multiple_events() -> None:
    first = _clock_event(
        "scheduled_activity_start",
        ProductionEventType.SCHEDULE_BOUNDARY_REACHED,
    )
    second = _clock_event(
        "heartbeat_due",
        ProductionEventType.TIMER_ELAPSED,
    )

    result = _interpreter().interpret([first, second], _context())

    assert len(result.observations) == 2
    assert result.source_production_event_ids == (first.id, second.id)
    for observation in result.observations:
        assert dict(observation.metadata)["source_production_event_ids"] == (
            first.id.to_json(),
            second.id.to_json(),
        )
        assert observation.location.kind is ObservationLocationKind.WALL_CLOCK


def test_mapping_contract_documents_supported_translations() -> None:
    event_types = {
        mapping.production_event_type for mapping in RUNTIME_CLOCK_OBSERVATION_MAPPINGS
    }
    timer_mapping = mapping_for_runtime_clock(ProductionEventType.TIMER_ELAPSED)

    assert event_types == {
        ProductionEventType.SCHEDULE_BOUNDARY_REACHED,
        ProductionEventType.TIMER_ELAPSED,
        ProductionEventType.SYSTEM_STATUS_CHANGED,
    }
    assert timer_mapping is not None
    assert timer_mapping.observation_note == "Timer boundary elapsed."


def test_runtime_clock_rule_creation() -> None:
    rule = RuntimeClockInterpreterRule(
        id=EntityId.new(),
        description="Runtime clock boundaries only.",
        metadata={"scope": "clock"},
    )
    base_rule = rule.to_observation_interpreter_rule()

    assert rule.supported_event_sources == (ProductionEventSource.TIMER,)
    assert rule.intended_observation_types == (ObservationType.TIME_BOUNDARY,)
    assert base_rule.supported_event_types == rule.supported_event_types
    assert dict(base_rule.metadata) == {"scope": "clock"}


def test_runtime_clock_summary_generation() -> None:
    rule = RuntimeClockInterpreterRule(id=EntityId.new())
    interpreter = _interpreter(rules=[rule])

    summary = RuntimeClockInterpreterSummary.from_interpreter(interpreter)

    assert summary.interpreter_id == interpreter.id
    assert summary.interpreter_name == interpreter.name
    assert summary.status is ObservationInterpreterStatus.ACTIVE
    assert summary.supported_event_type_count == 3
    assert summary.supported_source_count == 1
    assert summary.intended_observation_type_count == 1
    assert summary.mapping_count == 3
    assert summary.rule_count == 1


def test_observation_wording_stays_objective() -> None:
    objective_notes = {
        mapping.observation_note for mapping in RUNTIME_CLOCK_OBSERVATION_MAPPINGS
    }
    forbidden_terms = {
        "session",
        "activity began",
        "activity completed",
        "failure",
        "retry",
        "recording failed",
        "production delay",
        "package",
        "ready",
    }

    assert objective_notes == {
        "Scheduled time boundary was reached.",
        "Timer boundary elapsed.",
        "Runtime clock status changed.",
    }
    assert not any(term in note.lower() for term in forbidden_terms for note in objective_notes)


def test_no_fake_timeline_offsets_are_created() -> None:
    event = _clock_event(
        "heartbeat_due",
        ProductionEventType.TIMER_ELAPSED,
    )

    result = _interpreter().interpret(event, _context())

    assert result.observations[0].location.kind is ObservationLocationKind.WALL_CLOCK
    assert result.observations[0].location.point is None
    assert result.observations[0].location.range is None


def test_no_schedule_reconciliation_session_retry_timeout_or_reasoning_exists() -> None:
    forbidden_terms = {
        "reconcile",
        "session",
        "execute",
        "retry",
        "timeout",
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
        "recording_activity",
        "media_artifact",
        "transcript",
        "vision",
        "operator",
        "ocr",
        "speaker",
    }

    assert not any(
        term in name for name in _field_names() | _method_names() for term in forbidden_terms
    )


def test_no_provider_specific_behavior_exists() -> None:
    lifecycle_values = {
        mapping.boundary_lifecycle for mapping in RUNTIME_CLOCK_OBSERVATION_MAPPINGS
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
