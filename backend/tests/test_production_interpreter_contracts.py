from dataclasses import fields
from datetime import UTC, datetime, timedelta
from inspect import getmembers, isfunction

from app.contexts.production.interpreter import (
    InterpreterContext,
    InterpreterResult,
    InterpreterRule,
    InterpreterStatus,
    InterpreterSummary,
    ProductionEventInterpreter,
)
from app.contexts.production.observation import (
    Observation,
    ObservationConfidence,
    ObservationLocation,
    ObservationSource,
    ObservationType,
)
from app.contexts.production.production_event import (
    ProductionEvent,
    ProductionEventPayload,
    ProductionEventSource,
    ProductionEventType,
)
from app.contexts.production.timeline import TimelinePosition
from app.shared.ids import CorrelationId, EntityId


def _event(
    event_type: ProductionEventType = ProductionEventType.SCHEDULE_BOUNDARY_REACHED,
    source: ProductionEventSource = ProductionEventSource.SCHEDULE_SYSTEM,
) -> ProductionEvent:
    occurred_at = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)
    return ProductionEvent(
        id=EntityId.new(),
        event_type=event_type,
        source=source,
        payload=ProductionEventPayload({"marker": "boundary"}),
        correlation_id=CorrelationId.new(),
        occurred_at=occurred_at,
        received_at=occurred_at + timedelta(seconds=1),
    )


def _interpreter(
    status: InterpreterStatus = InterpreterStatus.ACTIVE,
    rules: list[InterpreterRule] | None = None,
) -> ProductionEventInterpreter:
    return ProductionEventInterpreter(
        id=EntityId.new(),
        name="Generic schedule boundary interpreter",
        supported_event_types=[ProductionEventType.SCHEDULE_BOUNDARY_REACHED],
        supported_event_sources=[ProductionEventSource.SCHEDULE_SYSTEM],
        status=status,
        rules=rules or [],
        metadata={"scope": "runtime"},
    )


def _context() -> InterpreterContext:
    return InterpreterContext(
        recording_block_id=EntityId.new(),
        stage_id=EntityId.new(),
        correlation_id=CorrelationId.new(),
        current_timestamp=datetime(2026, 7, 8, 10, 0, 1, tzinfo=UTC),
        metadata={"mode": "contract"},
    )


def _observation(recording_block_id: EntityId, seconds: int) -> Observation:
    return Observation(
        id=EntityId.new(),
        recording_block_id=recording_block_id,
        observation_type=ObservationType.SCHEDULE_BOUNDARY,
        observation_source=ObservationSource.SCHEDULE,
        location=ObservationLocation.at_point(
            TimelinePosition(recording_block_id, timedelta(seconds=seconds))
        ),
        confidence=ObservationConfidence(1.0),
        correlation_id=CorrelationId.new(),
        observed_at=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
    )


def test_interpreter_creation() -> None:
    rule = InterpreterRule(
        id=EntityId.new(),
        supported_event_types=[ProductionEventType.SCHEDULE_BOUNDARY_REACHED],
        supported_event_sources=[ProductionEventSource.SCHEDULE_SYSTEM],
        intended_observation_types=[ObservationType.SCHEDULE_BOUNDARY],
        description="Generic schedule boundary translation intent.",
    )
    interpreter = _interpreter(rules=[rule])

    assert interpreter.name == "Generic schedule boundary interpreter"
    assert interpreter.status is InterpreterStatus.ACTIVE
    assert interpreter.supported_event_types == (
        ProductionEventType.SCHEDULE_BOUNDARY_REACHED,
    )
    assert interpreter.supported_event_sources == (ProductionEventSource.SCHEDULE_SYSTEM,)
    assert interpreter.rules == (rule,)
    assert dict(interpreter.metadata) == {"scope": "runtime"}


def test_supported_event_type_matching() -> None:
    interpreter = _interpreter()

    assert interpreter.supports_event_type(ProductionEventType.SCHEDULE_BOUNDARY_REACHED)
    assert not interpreter.supports_event_type(ProductionEventType.MEDIA_FILE_CREATED)


def test_supported_source_matching() -> None:
    interpreter = _interpreter()

    assert interpreter.supports_source(ProductionEventSource.SCHEDULE_SYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.FILESYSTEM)


def test_interpreter_can_decline_unsupported_events() -> None:
    interpreter = _interpreter()
    supported_event = _event()
    unsupported_event = _event(source=ProductionEventSource.FILESYSTEM)
    disabled_interpreter = _interpreter(status=InterpreterStatus.DISABLED)

    assert interpreter.can_interpret(supported_event)
    assert not interpreter.can_interpret(unsupported_event)
    assert not disabled_interpreter.can_interpret(supported_event)

    result = interpreter.interpret(unsupported_event, _context())
    assert result.observations == ()
    assert result.warnings == ("ProductionEvent is not supported by this interpreter.",)


def test_interpreter_result_can_contain_zero_observations() -> None:
    event = _event()
    result = InterpreterResult(
        source_production_event_id=event.id,
        observations=[],
        interpreter_status=InterpreterStatus.ACTIVE,
    )

    assert result.source_production_event_id == event.id
    assert result.observations == ()


def test_interpreter_result_can_contain_multiple_observations() -> None:
    event = _event()
    recording_block_id = EntityId.new()
    first = _observation(recording_block_id, 10)
    second = _observation(recording_block_id, 20)

    result = InterpreterResult(
        source_production_event_id=event.id,
        observations=[first, second],
        interpreter_status=InterpreterStatus.ACTIVE,
        warnings=["translated into two observations"],
        metadata={"count": 2},
    )

    assert result.source_production_event_id == event.id
    assert result.observations == (first, second)
    assert result.warnings == ("translated into two observations",)
    assert dict(result.metadata) == {"count": 2}


def test_interpreter_result_references_source_production_event_id() -> None:
    event = _event()
    result = _interpreter().interpret(event, _context())

    assert result.source_production_event_id == event.id


def test_interpreter_status_allowed_values() -> None:
    assert {status.value for status in InterpreterStatus} == {
        "active",
        "disabled",
        "degraded",
        "experimental",
        "archived",
    }


def test_interpreter_context_creation() -> None:
    context = _context()

    assert context.recording_block_id is not None
    assert context.stage_id is not None
    assert context.current_timestamp == datetime(2026, 7, 8, 10, 0, 1, tzinfo=UTC)
    assert dict(context.metadata) == {"mode": "contract"}


def test_interpreter_rule_creation() -> None:
    rule = InterpreterRule(
        id=EntityId.new(),
        supported_event_types=[
            ProductionEventType.OPERATOR_NOTE_ADDED,
            ProductionEventType.MANUAL_MARKER_ADDED,
        ],
        supported_event_sources=[ProductionEventSource.OPERATOR],
        intended_observation_types=[
            ObservationType.OPERATOR_MARKER,
            ObservationType.TRANSCRIPT_TEXT_DETECTED,
        ],
        description="Operator-authored runtime input may become observations.",
        metadata={"priority": "normal"},
    )

    assert rule.supported_event_types == (
        ProductionEventType.OPERATOR_NOTE_ADDED,
        ProductionEventType.MANUAL_MARKER_ADDED,
    )
    assert rule.supported_event_sources == (ProductionEventSource.OPERATOR,)
    assert rule.intended_observation_types == (
        ObservationType.OPERATOR_MARKER,
        ObservationType.TRANSCRIPT_TEXT_DETECTED,
    )
    assert dict(rule.metadata) == {"priority": "normal"}


def test_interpreter_summary_generation() -> None:
    rule = InterpreterRule(
        id=EntityId.new(),
        supported_event_types=[ProductionEventType.SCHEDULE_BOUNDARY_REACHED],
        supported_event_sources=[ProductionEventSource.SCHEDULE_SYSTEM],
        intended_observation_types=[ObservationType.SCHEDULE_BOUNDARY],
    )
    interpreter = _interpreter(rules=[rule])

    summary = InterpreterSummary.from_interpreter(interpreter)

    assert summary.interpreter_id == interpreter.id
    assert summary.name == interpreter.name
    assert summary.status is InterpreterStatus.ACTIVE
    assert summary.supported_event_type_count == 1
    assert summary.supported_source_count == 1
    assert summary.rule_count == 1


def test_no_reasoning_generation_exists() -> None:
    field_names = {
        field.name
        for contract in (
            ProductionEventInterpreter,
            InterpreterResult,
            InterpreterContext,
            InterpreterRule,
            InterpreterSummary,
        )
        for field in fields(contract)
    }
    method_names = {
        name
        for name, value in getmembers(ProductionEventInterpreter)
        if isfunction(value)
    }
    forbidden_terms = {
        "evidence",
        "hypothesis",
        "finding",
        "verification_decision",
        "operational_product",
        "generate",
    }

    assert not any(term in name for name in field_names | method_names for term in forbidden_terms)


def test_no_provider_specific_names_appear() -> None:
    enum_values = {status.value for status in InterpreterStatus}
    field_names = {
        field.name
        for contract in (
            ProductionEventInterpreter,
            InterpreterResult,
            InterpreterContext,
            InterpreterRule,
            InterpreterSummary,
        )
        for field in fields(contract)
    }
    forbidden_terms = {
        "pretalx",
        "whisper",
        "vmix",
        "youtube",
        "devcon",
        "github",
        "ffmpeg",
        "provider",
        "vendor",
        "tool",
        "brand",
        "conference",
    }

    assert not any(term in value for value in enum_values for term in forbidden_terms)
    assert not any(term in field_name for field_name in field_names for term in forbidden_terms)


def test_no_api_persistence_queue_worker_frontend_or_adapter_behavior_exists() -> None:
    field_names = {
        field.name
        for contract in (
            ProductionEventInterpreter,
            InterpreterResult,
            InterpreterContext,
            InterpreterRule,
            InterpreterSummary,
        )
        for field in fields(contract)
    }
    method_names = {
        name
        for name, value in getmembers(ProductionEventInterpreter)
        if isfunction(value)
    }
    forbidden_terms = {
        "api",
        "database",
        "repository",
        "queue",
        "worker",
        "frontend",
        "adapter",
        "webhook_handler",
        "file_watcher",
    }

    assert not any(term in name for name in field_names | method_names for term in forbidden_terms)
