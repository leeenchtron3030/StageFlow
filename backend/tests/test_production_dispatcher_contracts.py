from dataclasses import fields
from datetime import UTC, datetime, timedelta
from inspect import getmembers, isfunction

from app.contexts.production.dispatcher import (
    DispatchContext,
    DispatchResult,
    DispatchRule,
    DispatchSummary,
    ProductionEventDispatcher,
)
from app.contexts.production.interpreter import (
    InterpreterContext,
    InterpreterResult,
    InterpreterStatus,
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


class FixedResultInterpreter(ProductionEventInterpreter):
    fixed_result: InterpreterResult

    def __init__(
        self,
        *,
        interpreter_id: EntityId,
        fixed_result: InterpreterResult,
    ) -> None:
        super().__init__(
            id=interpreter_id,
            name="Fixed result interpreter",
            supported_event_types=[ProductionEventType.SCHEDULE_BOUNDARY_REACHED],
            supported_event_sources=[ProductionEventSource.SCHEDULE_SYSTEM],
            status=InterpreterStatus.ACTIVE,
        )
        object.__setattr__(self, "fixed_result", fixed_result)

    def interpret(
        self,
        event: ProductionEvent,
        context: InterpreterContext,
    ) -> InterpreterResult:
        return self.fixed_result


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


def _context() -> DispatchContext:
    return DispatchContext(
        correlation_id=CorrelationId.new(),
        timestamp=datetime(2026, 7, 8, 10, 0, 2, tzinfo=UTC),
        stage_id=EntityId.new(),
        recording_block_id=EntityId.new(),
        metadata={"mode": "contract"},
    )


def _interpreter(
    interpreter_id: EntityId | None = None,
    source: ProductionEventSource = ProductionEventSource.SCHEDULE_SYSTEM,
    status: InterpreterStatus = InterpreterStatus.ACTIVE,
) -> ProductionEventInterpreter:
    return ProductionEventInterpreter(
        id=interpreter_id or EntityId.new(),
        name="Generic boundary interpreter",
        supported_event_types=[ProductionEventType.SCHEDULE_BOUNDARY_REACHED],
        supported_event_sources=[source],
        status=status,
    )


def _dispatcher(
    interpreters: list[ProductionEventInterpreter] | None = None,
    rules: list[DispatchRule] | None = None,
) -> ProductionEventDispatcher:
    return ProductionEventDispatcher(
        id=EntityId.new(),
        name="Production event dispatcher",
        interpreters=interpreters or [],
        rules=rules or [],
        metadata={"scope": "routing"},
    )


def _observation(recording_block_id: EntityId) -> Observation:
    return Observation(
        id=EntityId.new(),
        recording_block_id=recording_block_id,
        observation_type=ObservationType.SCHEDULE_BOUNDARY,
        observation_source=ObservationSource.SCHEDULE,
        location=ObservationLocation.at_point(
            TimelinePosition(recording_block_id, timedelta(seconds=30))
        ),
        confidence=ObservationConfidence(1.0),
        correlation_id=CorrelationId.new(),
    )


def test_dispatcher_creation() -> None:
    interpreter = _interpreter()
    rule = DispatchRule(
        id=EntityId.new(),
        supported_event_types=[ProductionEventType.SCHEDULE_BOUNDARY_REACHED],
        supported_event_sources=[ProductionEventSource.SCHEDULE_SYSTEM],
        target_interpreter_ids=[interpreter.id],
        description="Route schedule boundary events.",
    )
    dispatcher = _dispatcher(interpreters=[interpreter], rules=[rule])

    assert dispatcher.name == "Production event dispatcher"
    assert dispatcher.interpreters == (interpreter,)
    assert dispatcher.rules == (rule,)
    assert dict(dispatcher.metadata) == {"scope": "routing"}


def test_dispatch_with_zero_interpreters() -> None:
    event = _event()
    dispatcher = _dispatcher()

    result = dispatcher.dispatch(event, _context())

    assert result.source_production_event_id == event.id
    assert result.interpreter_count == 0
    assert result.invoked_interpreter_ids == ()
    assert result.interpreter_results == ()
    assert result.declined_interpreter_count == 0


def test_dispatch_with_one_interpreter() -> None:
    event = _event()
    interpreter = _interpreter()
    dispatcher = _dispatcher(interpreters=[interpreter])

    result = dispatcher.dispatch(event, _context())

    assert result.interpreter_count == 1
    assert result.invoked_interpreter_ids == (interpreter.id,)
    assert len(result.interpreter_results) == 1
    assert result.interpreter_results[0].source_production_event_id == event.id


def test_dispatch_with_multiple_interpreters() -> None:
    event = _event()
    first = _interpreter()
    second = _interpreter()
    dispatcher = _dispatcher(interpreters=[first, second])

    result = dispatcher.dispatch(event, _context())

    assert result.interpreter_count == 2
    assert result.invoked_interpreter_ids == (first.id, second.id)
    assert len(result.interpreter_results) == 2


def test_unsupported_interpreters_are_skipped() -> None:
    event = _event()
    supported = _interpreter()
    unsupported_source = _interpreter(source=ProductionEventSource.FILESYSTEM)
    disabled = _interpreter(status=InterpreterStatus.DISABLED)
    dispatcher = _dispatcher(interpreters=[supported, unsupported_source, disabled])

    result = dispatcher.dispatch(event, _context())

    assert result.interpreter_count == 3
    assert result.invoked_interpreter_ids == (supported.id,)
    assert len(result.interpreter_results) == 1
    assert result.declined_interpreter_count == 2


def test_dispatch_result_generation() -> None:
    event = _event()
    interpreter = _interpreter()
    result = DispatchResult(
        source_production_event_id=event.id,
        interpreter_count=1,
        invoked_interpreter_ids=[interpreter.id],
        interpreter_results=[
            InterpreterResult(
                source_production_event_id=event.id,
                observations=[],
                interpreter_status=InterpreterStatus.ACTIVE,
            )
        ],
        warnings=["diagnostic"],
        metadata={"route": "direct"},
    )

    assert result.source_production_event_id == event.id
    assert result.interpreter_count == 1
    assert result.invoked_interpreter_ids == (interpreter.id,)
    assert len(result.interpreter_results) == 1
    assert result.warnings == ("diagnostic",)
    assert dict(result.metadata) == {"route": "direct"}


def test_dispatch_context_creation() -> None:
    context = _context()
    interpreter_context = context.to_interpreter_context()

    assert context.timestamp == datetime(2026, 7, 8, 10, 0, 2, tzinfo=UTC)
    assert context.stage_id == interpreter_context.stage_id
    assert context.recording_block_id == interpreter_context.recording_block_id
    assert context.correlation_id == interpreter_context.correlation_id
    assert dict(context.metadata) == {"mode": "contract"}


def test_dispatch_rule_creation() -> None:
    interpreter_id = EntityId.new()
    rule = DispatchRule(
        id=EntityId.new(),
        supported_event_types=[
            ProductionEventType.SCHEDULE_BOUNDARY_REACHED,
            ProductionEventType.OPERATOR_NOTE_ADDED,
        ],
        supported_event_sources=[
            ProductionEventSource.SCHEDULE_SYSTEM,
            ProductionEventSource.OPERATOR,
        ],
        target_interpreter_ids=[interpreter_id],
        description="Declarative routing intent.",
        metadata={"priority": "normal"},
    )

    assert rule.supported_event_types == (
        ProductionEventType.SCHEDULE_BOUNDARY_REACHED,
        ProductionEventType.OPERATOR_NOTE_ADDED,
    )
    assert rule.supported_event_sources == (
        ProductionEventSource.SCHEDULE_SYSTEM,
        ProductionEventSource.OPERATOR,
    )
    assert rule.target_interpreter_ids == (interpreter_id,)
    assert dict(rule.metadata) == {"priority": "normal"}


def test_dispatch_summary_generation() -> None:
    event = _event()
    interpreter = _interpreter()
    result = DispatchResult(
        source_production_event_id=event.id,
        interpreter_count=2,
        invoked_interpreter_ids=[interpreter.id],
        interpreter_results=[
            InterpreterResult(
                source_production_event_id=event.id,
                observations=[],
                interpreter_status=InterpreterStatus.ACTIVE,
            )
        ],
        warnings=["one interpreter declined"],
        declined_interpreter_count=1,
    )

    summary = DispatchSummary.from_dispatch_result(result)

    assert summary.dispatched_production_event_id == event.id
    assert summary.interpreter_count == 2
    assert summary.successful_interpreter_count == 1
    assert summary.declined_interpreter_count == 1
    assert summary.warning_count == 1


def test_dispatcher_does_not_modify_interpreter_results() -> None:
    event = _event()
    observation = _observation(EntityId.new())
    interpreter_result = InterpreterResult(
        source_production_event_id=event.id,
        observations=[observation],
        interpreter_status=InterpreterStatus.ACTIVE,
        warnings=["interpreter warning"],
        metadata={"source": "interpreter"},
    )
    interpreter = FixedResultInterpreter(
        interpreter_id=EntityId.new(),
        fixed_result=interpreter_result,
    )
    dispatcher = _dispatcher(interpreters=[interpreter])

    result = dispatcher.dispatch(event, _context())

    assert result.interpreter_results == (interpreter_result,)
    assert result.interpreter_results[0].observations == (observation,)
    assert result.warnings == ("interpreter warning",)


def test_dispatcher_does_not_create_observations_directly() -> None:
    field_names = {
        field.name
        for contract in (
            ProductionEventDispatcher,
            DispatchResult,
            DispatchContext,
            DispatchRule,
            DispatchSummary,
        )
        for field in fields(contract)
    }
    method_names = {
        name
        for name, value in getmembers(ProductionEventDispatcher)
        if isfunction(value)
    }

    assert "observations" not in field_names
    assert "create_observation" not in method_names


def test_dispatcher_does_not_create_reasoning_or_products() -> None:
    field_names = {
        field.name
        for contract in (
            ProductionEventDispatcher,
            DispatchResult,
            DispatchContext,
            DispatchRule,
            DispatchSummary,
        )
        for field in fields(contract)
    }
    method_names = {
        name
        for name, value in getmembers(ProductionEventDispatcher)
        if isfunction(value)
    }
    forbidden_terms = {
        "evidence",
        "hypothesis",
        "finding",
        "verification_decision",
        "operational_product",
        "generate",
        "interpret_event",
    }

    assert not any(term in name for name in field_names | method_names for term in forbidden_terms)


def test_dispatcher_remains_provider_agnostic() -> None:
    field_names = {
        field.name
        for contract in (
            ProductionEventDispatcher,
            DispatchResult,
            DispatchContext,
            DispatchRule,
            DispatchSummary,
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

    assert not any(term in field_name for field_name in field_names for term in forbidden_terms)


def test_no_infrastructure_frontend_or_adapter_behavior_exists() -> None:
    field_names = {
        field.name
        for contract in (
            ProductionEventDispatcher,
            DispatchResult,
            DispatchContext,
            DispatchRule,
            DispatchSummary,
        )
        for field in fields(contract)
    }
    method_names = {
        name
        for name, value in getmembers(ProductionEventDispatcher)
        if isfunction(value)
    }
    forbidden_terms = {
        "queue",
        "worker",
        "retry",
        "schedule",
        "database",
        "repository",
        "frontend",
        "adapter",
        "plugin",
        "registry",
        "event_bus",
        "api",
    }

    assert not any(term in name for name in field_names | method_names for term in forbidden_terms)
