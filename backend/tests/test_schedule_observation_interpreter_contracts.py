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
from app.contexts.production.schedule_observation_interpreter import (
    SCHEDULE_OBSERVATION_MAPPINGS,
    ScheduleInterpreterRule,
    ScheduleInterpreterSummary,
    ScheduleObservationInterpreter,
    ScheduleObservationMapping,
    mapping_for_schedule,
)
from app.shared.ids import CorrelationId, EntityId

CONTRACTS = (
    ScheduleObservationInterpreter,
    ScheduleInterpreterRule,
    ScheduleInterpreterSummary,
    ScheduleObservationMapping,
)


def _context() -> ObservationInterpreterContext:
    return ObservationInterpreterContext(
        correlation_id=CorrelationId.new(),
        current_timestamp=datetime(2026, 7, 9, 10, 0, 2, tzinfo=UTC),
        stage_id=EntityId.new(),
        metadata={"mode": "schedule-contract"},
    )


def _schedule_event(
    activity_status: str,
    event_type: ProductionEventType,
    source: ProductionEventSource = ProductionEventSource.SCHEDULE_SYSTEM,
    schedule_adapter_event: bool = True,
) -> ProductionEvent:
    occurred_at = datetime(2026, 7, 9, 10, 0, tzinfo=UTC)
    scheduled_activity_id = EntityId.new()
    return ProductionEvent(
        id=EntityId.new(),
        event_type=event_type,
        source=source,
        payload=ProductionEventPayload(
            {
                "scheduled_activity_id": scheduled_activity_id.to_json(),
                "activity_title": "Planned Activity",
                "activity_type": "presentation",
                "activity_status": activity_status,
                "planned_start_at": occurred_at.isoformat(),
                "planned_end_at": (occurred_at + timedelta(hours=1)).isoformat(),
            }
        ),
        references=(
            ProductionEventReference(
                reference_type=ProductionEventReferenceType.SCHEDULE_ARTIFACT,
                referenced_id=scheduled_activity_id,
                label="scheduled activity",
            ),
        ),
        correlation_id=CorrelationId.new(),
        occurred_at=occurred_at,
        received_at=occurred_at,
        metadata={"schedule_adapter_event": schedule_adapter_event},
    )


def _interpreter(
    rules: list[ScheduleInterpreterRule] | None = None,
) -> ScheduleObservationInterpreter:
    return ScheduleObservationInterpreter(
        id=EntityId.new(),
        rules=rules or [],
        metadata={"scope": "schedule"},
    )


def _field_names() -> set[str]:
    return {field.name for contract in CONTRACTS for field in fields(contract)}


def _method_names() -> set[str]:
    return {
        name
        for name, value in getmembers(ScheduleObservationInterpreter)
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
    assert observation.recording_block_id is None
    assert observation.observation_type is ObservationType.SCHEDULE_ACTIVITY
    assert observation.observation_source is ObservationSource.SCHEDULE
    assert observation.notes == expected_note
    assert observation.location.kind is ObservationLocationKind.WALL_CLOCK
    assert observation.location.wall_clock_at == event.occurred_at
    assert observation.location.point is None
    assert observation.location.range is None
    assert observation.correlation_id == event.correlation_id
    assert dict(observation.metadata)["planned_reality_observation"] is True
    assert dict(observation.metadata)["source_production_event_ids"] == (
        event.id.to_json(),
    )
    assert dict(observation.metadata)["observation_interpreter_id"] == (
        result.interpreter_id.to_json()
    )


def test_schedule_observation_interpreter_creation() -> None:
    rule = ScheduleInterpreterRule(
        id=EntityId.new(),
        description="Translate schedule events into objective observations.",
    )
    interpreter = _interpreter(rules=[rule])

    assert interpreter.name == "Schedule observation interpreter"
    assert interpreter.status is ObservationInterpreterStatus.ACTIVE
    assert interpreter.supported_event_sources == (ProductionEventSource.SCHEDULE_SYSTEM,)
    assert interpreter.intended_observation_types == (ObservationType.SCHEDULE_ACTIVITY,)
    assert interpreter.rules == (rule,)
    assert dict(interpreter.metadata) == {"scope": "schedule"}


def test_supported_production_event_types_are_schedule_related_only() -> None:
    interpreter = _interpreter()

    assert interpreter.supported_event_types == (
        ProductionEventType.SCHEDULE_ARTIFACT_UPDATED,
        ProductionEventType.SCHEDULE_BOUNDARY_REACHED,
        ProductionEventType.SYSTEM_STATUS_CHANGED,
    )
    assert interpreter.supports_event_type(ProductionEventType.SCHEDULE_ARTIFACT_UPDATED)
    assert not interpreter.supports_event_type(ProductionEventType.RECORDING_BLOCK_STARTED)


def test_supported_production_event_sources_are_schedule_system_only() -> None:
    interpreter = _interpreter()

    assert interpreter.supports_source(ProductionEventSource.SCHEDULE_SYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.TIMER)
    assert not interpreter.supports_source(ProductionEventSource.RECORDING_SYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.TRANSCRIPT_SYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.VISION_SYSTEM)
    assert not interpreter.supports_source(ProductionEventSource.OPERATOR)
    assert not interpreter.supports_source(ProductionEventSource.INTERNAL_SYSTEM)


def test_schedule_artifact_updated_mapping_creates_objective_observation() -> None:
    event = _schedule_event(
        "updated",
        ProductionEventType.SCHEDULE_ARTIFACT_UPDATED,
    )

    _assert_single_observation(event, "Scheduled activity was updated.")


def test_schedule_cancelled_mapping_creates_objective_observation() -> None:
    event = _schedule_event(
        "cancelled",
        ProductionEventType.SCHEDULE_ARTIFACT_UPDATED,
    )

    _assert_single_observation(event, "Scheduled activity was cancelled.")


def test_schedule_boundary_reached_mapping_creates_objective_observation() -> None:
    event = _schedule_event(
        "scheduled",
        ProductionEventType.SCHEDULE_BOUNDARY_REACHED,
    )

    _assert_single_observation(event, "Scheduled activity entered its planned time window.")


def test_schedule_related_system_status_changed_mapping_creates_observation() -> None:
    event = _schedule_event(
        "unknown",
        ProductionEventType.SYSTEM_STATUS_CHANGED,
        schedule_adapter_event=True,
    )

    _assert_single_observation(event, "Schedule source status changed.")


def test_non_schedule_system_status_changed_is_ignored_when_distinguishable() -> None:
    event = _schedule_event(
        "unknown",
        ProductionEventType.SYSTEM_STATUS_CHANGED,
        schedule_adapter_event=False,
    )

    result = _interpreter().interpret(event, _context())

    assert result.source_production_event_ids == (event.id,)
    assert result.observations == ()


def test_unknown_event_handling_returns_zero_observations() -> None:
    event = _schedule_event(
        "updated",
        ProductionEventType.UNKNOWN,
    )

    result = _interpreter().interpret(event, _context())

    assert result.source_production_event_ids == (event.id,)
    assert result.observations == ()
    assert result.warnings == ("ProductionEvent group is not supported by this interpreter.",)


def test_runtime_clock_schedule_boundary_event_is_not_interpreted() -> None:
    event = _schedule_event(
        "scheduled",
        ProductionEventType.SCHEDULE_BOUNDARY_REACHED,
        source=ProductionEventSource.TIMER,
    )

    result = _interpreter().interpret(event, _context())

    assert result.source_production_event_ids == (event.id,)
    assert result.observations == ()
    assert result.warnings == ("ProductionEvent group is not supported by this interpreter.",)


def test_wall_clock_location_is_used_without_fake_timeline_offsets() -> None:
    event = _schedule_event(
        "updated",
        ProductionEventType.SCHEDULE_ARTIFACT_UPDATED,
    )

    result = _interpreter().interpret(event, _context())
    observation = result.observations[0]

    assert observation.location.kind is ObservationLocationKind.WALL_CLOCK
    assert observation.location.wall_clock_at == event.occurred_at
    assert observation.location.point is None
    assert observation.location.range is None
    assert observation.recording_block_id is None


def test_interpreter_can_return_multiple_observations_for_multiple_events() -> None:
    updated = _schedule_event("updated", ProductionEventType.SCHEDULE_ARTIFACT_UPDATED)
    cancelled = _schedule_event("cancelled", ProductionEventType.SCHEDULE_ARTIFACT_UPDATED)

    result = _interpreter().interpret([updated, cancelled], _context())

    assert len(result.observations) == 2
    assert result.source_production_event_ids == (updated.id, cancelled.id)
    for observation in result.observations:
        assert dict(observation.metadata)["source_production_event_ids"] == (
            updated.id.to_json(),
            cancelled.id.to_json(),
        )
        assert observation.location.kind is ObservationLocationKind.WALL_CLOCK


def test_mapping_contract_documents_supported_translations() -> None:
    event_types = {mapping.production_event_type for mapping in SCHEDULE_OBSERVATION_MAPPINGS}
    cancelled_mapping = mapping_for_schedule(
        ProductionEventType.SCHEDULE_ARTIFACT_UPDATED,
        activity_status="cancelled",
    )

    assert event_types == {
        ProductionEventType.SCHEDULE_ARTIFACT_UPDATED,
        ProductionEventType.SCHEDULE_BOUNDARY_REACHED,
        ProductionEventType.SYSTEM_STATUS_CHANGED,
    }
    assert cancelled_mapping is not None
    assert cancelled_mapping.observation_note == "Scheduled activity was cancelled."


def test_schedule_rule_creation() -> None:
    rule = ScheduleInterpreterRule(
        id=EntityId.new(),
        description="Schedule source events only.",
        metadata={"scope": "planned-reality"},
    )
    base_rule = rule.to_observation_interpreter_rule()

    assert rule.supported_event_sources == (ProductionEventSource.SCHEDULE_SYSTEM,)
    assert rule.intended_observation_types == (ObservationType.SCHEDULE_ACTIVITY,)
    assert base_rule.supported_event_types == rule.supported_event_types
    assert dict(base_rule.metadata) == {"scope": "planned-reality"}


def test_schedule_summary_generation() -> None:
    rule = ScheduleInterpreterRule(id=EntityId.new())
    interpreter = _interpreter(rules=[rule])

    summary = ScheduleInterpreterSummary.from_interpreter(interpreter)

    assert summary.interpreter_id == interpreter.id
    assert summary.interpreter_name == interpreter.name
    assert summary.status is ObservationInterpreterStatus.ACTIVE
    assert summary.supported_event_type_count == 3
    assert summary.supported_source_count == 1
    assert summary.intended_observation_type_count == 1
    assert summary.mapping_count == 4
    assert summary.rule_count == 1


def test_observation_wording_stays_in_planned_reality() -> None:
    objective_notes = {mapping.observation_note for mapping in SCHEDULE_OBSERVATION_MAPPINGS}
    forbidden_terms = {
        "session started",
        "keynote began",
        "presentation ended",
        "audience entered",
        "recording started",
        "production",
        "speaker",
    }

    assert objective_notes == {
        "Scheduled activity was updated.",
        "Scheduled activity was cancelled.",
        "Scheduled activity entered its planned time window.",
        "Schedule source status changed.",
    }
    assert not any(term in note.lower() for term in forbidden_terms for note in objective_notes)


def test_no_production_inference_reconciliation_or_reasoning_exists() -> None:
    forbidden_terms = {
        "recording",
        "session",
        "speaker",
        "audience",
        "reconcile",
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
        "runtime_clock",
    }

    assert not any(
        term in name for name in _field_names() | _method_names() for term in forbidden_terms
    )


def test_no_provider_specific_behavior_exists() -> None:
    lifecycle_values = {mapping.schedule_lifecycle for mapping in SCHEDULE_OBSERVATION_MAPPINGS}
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
