from dataclasses import fields
from datetime import UTC, datetime, timedelta
from inspect import getmembers, isfunction

import pytest

from app.contexts.production.observation import (
    Observation,
    ObservationConfidence,
    ObservationLocation,
    ObservationSource,
    ObservationType,
)
from app.contexts.production.observation_interpreter import (
    ObservationInterpreter,
    ObservationInterpreterContext,
    ObservationInterpreterPolicy,
    ObservationInterpreterResult,
    ObservationInterpreterRule,
    ObservationInterpreterStatus,
    ObservationInterpreterSummary,
)
from app.contexts.production.production_event import (
    ProductionEvent,
    ProductionEventPayload,
    ProductionEventSource,
    ProductionEventType,
)
from app.contexts.production.timeline import TimelinePosition
from app.shared.ids import CorrelationId, EntityId

CONTRACTS = (
    ObservationInterpreter,
    ObservationInterpreterResult,
    ObservationInterpreterContext,
    ObservationInterpreterRule,
    ObservationInterpreterPolicy,
    ObservationInterpreterSummary,
)


def _event(
    event_type: ProductionEventType = ProductionEventType.MEDIA_FILE_FINALIZED,
    source: ProductionEventSource = ProductionEventSource.FILESYSTEM,
) -> ProductionEvent:
    occurred_at = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)
    return ProductionEvent(
        id=EntityId.new(),
        event_type=event_type,
        source=source,
        payload=ProductionEventPayload({"artifact_id": "artifact-123"}),
        correlation_id=CorrelationId.new(),
        occurred_at=occurred_at,
        received_at=occurred_at + timedelta(seconds=1),
    )


def _context(recording_block_id: EntityId | None = None) -> ObservationInterpreterContext:
    return ObservationInterpreterContext(
        correlation_id=CorrelationId.new(),
        current_timestamp=datetime(2026, 7, 8, 10, 0, 2, tzinfo=UTC),
        recording_block_id=recording_block_id or EntityId.new(),
        stage_id=EntityId.new(),
        metadata={"mode": "contract"},
    )


def _rule() -> ObservationInterpreterRule:
    return ObservationInterpreterRule(
        id=EntityId.new(),
        supported_event_types=[ProductionEventType.MEDIA_FILE_FINALIZED],
        supported_event_sources=[ProductionEventSource.FILESYSTEM],
        intended_observation_types=[ObservationType.UNKNOWN],
        description="Media artifact availability may become an objective observation.",
        metadata={"scope": "media"},
    )


def _interpreter(
    status: ObservationInterpreterStatus = ObservationInterpreterStatus.ACTIVE,
    policy: ObservationInterpreterPolicy | None = None,
    rules: list[ObservationInterpreterRule] | None = None,
) -> ObservationInterpreter:
    return ObservationInterpreter(
        id=EntityId.new(),
        name="Generic observation interpreter",
        supported_event_types=[ProductionEventType.MEDIA_FILE_FINALIZED],
        supported_event_sources=[ProductionEventSource.FILESYSTEM],
        intended_observation_types=[ObservationType.UNKNOWN],
        status=status,
        policy=policy or ObservationInterpreterPolicy(),
        rules=rules or [],
        metadata={"scope": "observation-translation"},
    )


def _observation(recording_block_id: EntityId, seconds: int) -> Observation:
    return Observation(
        id=EntityId.new(),
        recording_block_id=recording_block_id,
        observation_type=ObservationType.UNKNOWN,
        observation_source=ObservationSource.SYSTEM,
        location=ObservationLocation.at_point(
            TimelinePosition(recording_block_id, timedelta(seconds=seconds))
        ),
        confidence=ObservationConfidence(1.0),
        correlation_id=CorrelationId.new(),
        observed_at=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
        notes="Objective runtime observation.",
    )


def _field_names() -> set[str]:
    return {field.name for contract in CONTRACTS for field in fields(contract)}


def _method_names() -> set[str]:
    return {
        name
        for name, value in getmembers(ObservationInterpreter)
        if isfunction(value)
    }


def test_observation_interpreter_creation() -> None:
    rule = _rule()
    interpreter = _interpreter(rules=[rule])

    assert interpreter.name == "Generic observation interpreter"
    assert interpreter.status is ObservationInterpreterStatus.ACTIVE
    assert interpreter.supported_event_types == (ProductionEventType.MEDIA_FILE_FINALIZED,)
    assert interpreter.supported_event_sources == (ProductionEventSource.FILESYSTEM,)
    assert interpreter.intended_observation_types == (ObservationType.UNKNOWN,)
    assert interpreter.rules == (rule,)
    assert dict(interpreter.metadata) == {"scope": "observation-translation"}


def test_interpreter_declares_supported_production_event_types() -> None:
    interpreter = _interpreter()

    assert interpreter.supports_event_type(ProductionEventType.MEDIA_FILE_FINALIZED)
    assert not interpreter.supports_event_type(ProductionEventType.OPERATOR_INPUT_RECEIVED)


def test_interpreter_declares_supported_production_event_sources() -> None:
    interpreter = _interpreter()

    assert interpreter.supports_source(ProductionEventSource.FILESYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.OPERATOR)


def test_interpreter_declares_intended_observation_types() -> None:
    interpreter = _interpreter()

    assert ObservationType.UNKNOWN in interpreter.intended_observation_types


def test_interpreter_can_accept_one_production_event() -> None:
    interpreter = _interpreter()
    event = _event()

    assert interpreter.can_interpret_event(event)
    assert interpreter.can_interpret_events([event])


def test_interpreter_can_accept_multiple_production_events() -> None:
    interpreter = _interpreter()
    first = _event()
    second = _event()

    assert interpreter.can_interpret_events([first, second])


def test_interpreter_declines_unsupported_event_groups() -> None:
    interpreter = _interpreter()
    unsupported_event = _event(source=ProductionEventSource.OPERATOR)

    assert not interpreter.can_interpret_event(unsupported_event)

    result = interpreter.interpret(unsupported_event, _context())
    assert result.observations == ()
    assert result.warnings == ("ProductionEvent group is not supported by this interpreter.",)


def test_interpreter_can_return_zero_observations() -> None:
    event = _event()
    interpreter = _interpreter()

    result = interpreter.interpret(event, _context())

    assert result.source_production_event_ids == (event.id,)
    assert result.observations == ()
    assert result.interpreter_id == interpreter.id


def test_interpreter_can_return_multiple_observations() -> None:
    recording_block_id = EntityId.new()
    first_observation = _observation(recording_block_id, 10)
    second_observation = _observation(recording_block_id, 20)
    event = _event()
    interpreter = _interpreter()

    result = interpreter.interpret(
        event,
        _context(recording_block_id),
        observations=[first_observation, second_observation],
    )

    assert len(result.observations) == 2
    assert result.observations[0].id == first_observation.id
    assert result.observations[1].id == second_observation.id


def test_observation_interpreter_result_preserves_source_production_event_ids() -> None:
    first = _event()
    second = _event()
    interpreter = _interpreter()

    result = interpreter.interpret([first, second], _context())

    assert result.source_production_event_ids == (first.id, second.id)
    assert dict(result.metadata)["source_event_count"] == 2


def test_observations_receive_traceability_metadata() -> None:
    recording_block_id = EntityId.new()
    event = _event()
    observation = _observation(recording_block_id, 10)

    result = _interpreter().interpret(
        event,
        _context(recording_block_id),
        observations=[observation],
    )

    traced_observation = result.observations[0]

    assert traced_observation.id == observation.id
    assert dict(traced_observation.metadata)["source_production_event_ids"] == (
        event.id.to_json(),
    )
    assert dict(traced_observation.metadata)["observation_interpreter_id"] == (
        result.interpreter_id.to_json()
    )


def test_observation_interpreter_result_creation() -> None:
    event = _event()
    interpreter_id = EntityId.new()

    result = ObservationInterpreterResult(
        source_production_event_ids=[event.id],
        observations=[],
        interpreter_id=interpreter_id,
        warnings=["No objective observation created."],
        metadata={"reason": "unsupported details"},
    )

    assert result.source_production_event_ids == (event.id,)
    assert result.observations == ()
    assert result.interpreter_id == interpreter_id
    assert result.warnings == ("No objective observation created.",)
    assert dict(result.metadata) == {"reason": "unsupported details"}


def test_observation_interpreter_context_creation() -> None:
    recording_block_id = EntityId.new()
    context = _context(recording_block_id)

    assert context.recording_block_id == recording_block_id
    assert context.stage_id is not None
    assert context.current_timestamp == datetime(2026, 7, 8, 10, 0, 2, tzinfo=UTC)
    assert dict(context.metadata) == {"mode": "contract"}


def test_observation_interpreter_rule_creation() -> None:
    rule = _rule()

    assert rule.supported_event_types == (ProductionEventType.MEDIA_FILE_FINALIZED,)
    assert rule.supported_event_sources == (ProductionEventSource.FILESYSTEM,)
    assert rule.intended_observation_types == (ObservationType.UNKNOWN,)
    assert rule.description == "Media artifact availability may become an objective observation."
    assert dict(rule.metadata) == {"scope": "media"}


def test_observation_interpreter_policy_creation() -> None:
    policy = ObservationInterpreterPolicy(
        allow_zero_observations=False,
        allow_multiple_observations=False,
        require_source_event_traceability=True,
    )

    assert not policy.allow_zero_observations
    assert not policy.allow_multiple_observations
    assert policy.require_source_event_traceability


def test_observation_interpreter_policy_can_reject_zero_observations() -> None:
    interpreter = _interpreter(
        policy=ObservationInterpreterPolicy(allow_zero_observations=False)
    )

    with pytest.raises(ValueError, match="zero Observations"):
        interpreter.interpret(_event(), _context())


def test_observation_interpreter_policy_can_reject_multiple_observations() -> None:
    recording_block_id = EntityId.new()
    interpreter = _interpreter(
        policy=ObservationInterpreterPolicy(allow_multiple_observations=False)
    )

    with pytest.raises(ValueError, match="multiple Observations"):
        interpreter.interpret(
            _event(),
            _context(recording_block_id),
            observations=[
                _observation(recording_block_id, 10),
                _observation(recording_block_id, 20),
            ],
        )


def test_observation_interpreter_summary_generation() -> None:
    interpreter = _interpreter(rules=[_rule()])

    summary = ObservationInterpreterSummary.from_interpreter(interpreter)

    assert summary.interpreter_id == interpreter.id
    assert summary.interpreter_name == interpreter.name
    assert summary.status is ObservationInterpreterStatus.ACTIVE
    assert summary.supported_event_type_count == 1
    assert summary.supported_source_count == 1
    assert summary.intended_observation_type_count == 1
    assert summary.rule_count == 1


def test_observation_interpreter_status_allowed_values() -> None:
    assert {status.value for status in ObservationInterpreterStatus} == {
        "unknown",
        "configured",
        "ready",
        "active",
        "degraded",
        "failed",
        "disabled",
        "archived",
    }


def test_no_later_reasoning_generation_exists() -> None:
    forbidden_terms = {
        "evidence",
        "hypothesis",
        "finding",
        "verification_decision",
        "operational_product",
        "reasoning",
        "conclusion",
        "package",
        "verify",
    }

    assert not any(
        term in name for name in _field_names() | _method_names() for term in forbidden_terms
    )


def test_no_provider_specific_names_appear() -> None:
    enum_values = {status.value for status in ObservationInterpreterStatus}
    forbidden_terms = {
        "pretalx",
        "whisper",
        "opencv",
        "vmix",
        "youtube",
        "devcon",
        "provider",
        "vendor",
        "brand",
    }

    assert not any(term in value for value in enum_values for term in forbidden_terms)
    assert not any(
        term in name for name in _field_names() | _method_names() for term in forbidden_terms
    )


def test_no_api_persistence_queue_worker_frontend_or_adapter_behavior_exists() -> None:
    forbidden_terms = {
        "api",
        "database",
        "repository",
        "queue",
        "worker",
        "frontend",
        "adapter",
        "webhook",
        "file_watcher",
        "persist",
    }

    assert not any(
        term in name for name in _field_names() | _method_names() for term in forbidden_terms
    )
