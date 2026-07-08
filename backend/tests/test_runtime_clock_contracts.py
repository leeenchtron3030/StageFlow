from dataclasses import fields
from datetime import UTC, datetime, timedelta
from inspect import getmembers, isfunction

from app.contexts.production.production_event import (
    ProductionEvent,
    ProductionEventReferenceType,
    ProductionEventSource,
    ProductionEventType,
)
from app.contexts.production.runtime_clock import (
    ClockCapability,
    ClockEvent,
    ClockSummary,
    RuntimeClock,
    RuntimeClockStatus,
    TimeBoundary,
    TimeBoundaryStatus,
    TimeBoundaryType,
)
from app.shared.ids import CorrelationId, EntityId


def _boundary(
    boundary_type: TimeBoundaryType = TimeBoundaryType.SCHEDULED_ACTIVITY_START,
    boundary_status: TimeBoundaryStatus = TimeBoundaryStatus.PENDING,
    offset_seconds: int = -1,
) -> TimeBoundary:
    now = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)
    return TimeBoundary(
        id=EntityId.new(),
        boundary_type=boundary_type,
        boundary_status=boundary_status,
        boundary_timestamp=now + timedelta(seconds=offset_seconds),
        stage_id=EntityId.new(),
        recording_block_id=EntityId.new(),
        scheduled_activity_id=EntityId.new(),
        label="Boundary",
        metadata={"source": "contract"},
    )


def _clock(boundaries: list[TimeBoundary] | None = None) -> RuntimeClock:
    return RuntimeClock(
        id=EntityId.new(),
        clock_name="Runtime clock",
        supported_capabilities=[
            ClockCapability.EVALUATES_TIME_BOUNDARIES,
            ClockCapability.REPORTS_BOUNDARY_CROSSED,
            ClockCapability.REPORTS_TIMEOUT,
        ],
        clock_status=RuntimeClockStatus.READY,
        time_boundaries=boundaries or [],
        metadata={"scope": "time"},
    )


def test_runtime_clock_creation() -> None:
    boundary = _boundary()
    clock = _clock(boundaries=[boundary])

    assert clock.clock_name == "Runtime clock"
    assert clock.clock_status is RuntimeClockStatus.READY
    assert clock.supports_capability(ClockCapability.EVALUATES_TIME_BOUNDARIES)
    assert not clock.supports_capability(ClockCapability.REPORTS_RETRY_DUE)
    assert clock.time_boundaries == (boundary,)
    assert dict(clock.metadata) == {"scope": "time"}


def test_time_boundary_creation() -> None:
    boundary = _boundary()

    assert boundary.boundary_type is TimeBoundaryType.SCHEDULED_ACTIVITY_START
    assert boundary.boundary_status is TimeBoundaryStatus.PENDING
    assert boundary.stage_id is not None
    assert boundary.recording_block_id is not None
    assert boundary.scheduled_activity_id is not None
    assert boundary.label == "Boundary"
    assert dict(boundary.metadata) == {"source": "contract"}


def test_time_boundary_type_allowed_values() -> None:
    assert {boundary_type.value for boundary_type in TimeBoundaryType} == {
        "scheduled_activity_start",
        "scheduled_activity_end",
        "recording_expected_start",
        "recording_expected_end",
        "timeout",
        "heartbeat_due",
        "retry_due",
        "manual_deadline",
        "custom",
        "unknown",
    }


def test_time_boundary_status_allowed_values() -> None:
    assert {status.value for status in TimeBoundaryStatus} == {
        "pending",
        "crossed",
        "cancelled",
        "expired",
        "archived",
        "unknown",
    }


def test_clock_event_creation() -> None:
    clock_id = EntityId.new()
    boundary_id = EntityId.new()
    occurred_at = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)
    event = ClockEvent(
        clock_id=clock_id,
        time_boundary_id=boundary_id,
        boundary_type=TimeBoundaryType.TIMEOUT,
        occurred_at=occurred_at,
        stage_id=EntityId.new(),
        recording_block_id=EntityId.new(),
        scheduled_activity_id=EntityId.new(),
        label="Timeout boundary",
        metadata={"policy": "generic"},
    )

    assert event.clock_id == clock_id
    assert event.time_boundary_id == boundary_id
    assert event.boundary_type is TimeBoundaryType.TIMEOUT
    assert event.occurred_at == occurred_at
    assert event.label == "Timeout boundary"
    assert dict(event.metadata) == {"policy": "generic"}


def test_clock_capability_allowed_values() -> None:
    assert {capability.value for capability in ClockCapability} == {
        "evaluates_time_boundaries",
        "reports_boundary_crossed",
        "reports_heartbeat_due",
        "reports_timeout",
        "reports_retry_due",
        "unknown",
    }


def test_clock_summary_generation() -> None:
    pending = _boundary(boundary_status=TimeBoundaryStatus.PENDING)
    crossed = _boundary(boundary_status=TimeBoundaryStatus.CROSSED)
    clock = _clock(boundaries=[pending, crossed])

    summary = ClockSummary.from_clock(clock)

    assert summary.clock_id == clock.id
    assert summary.clock_name == "Runtime clock"
    assert summary.clock_status is RuntimeClockStatus.READY
    assert summary.capability_count == 3
    assert summary.pending_boundary_count == 1
    assert summary.crossed_boundary_count == 1


def test_evaluation_identifies_crossed_boundaries() -> None:
    current_timestamp = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)
    crossed = _boundary(offset_seconds=-1)
    future = _boundary(offset_seconds=30)
    already_crossed = _boundary(
        boundary_status=TimeBoundaryStatus.CROSSED,
        offset_seconds=-30,
    )
    clock = _clock(boundaries=[crossed, future, already_crossed])

    result = clock.evaluate_boundaries(current_timestamp)

    assert result == (crossed,)


def test_evaluation_does_not_mutate_boundaries() -> None:
    current_timestamp = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)
    boundary = _boundary(offset_seconds=-1)
    clock = _clock(boundaries=[boundary])

    result = clock.evaluate_boundaries(current_timestamp)

    assert result == (boundary,)
    assert boundary.boundary_status is TimeBoundaryStatus.PENDING
    assert clock.time_boundaries == (boundary,)


def test_clock_event_maps_to_production_events_only() -> None:
    current_timestamp = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)
    boundary = _boundary(TimeBoundaryType.SCHEDULED_ACTIVITY_START)
    clock = _clock(boundaries=[boundary])
    clock_event = clock.clock_event_from_boundary(boundary, occurred_at=current_timestamp)

    production_event = clock.production_event_from_clock_event(
        clock_event,
        correlation_id=CorrelationId.new(),
        received_at=current_timestamp + timedelta(seconds=1),
    )

    assert isinstance(production_event, ProductionEvent)
    assert production_event.event_type is ProductionEventType.SCHEDULE_BOUNDARY_REACHED
    assert production_event.source is ProductionEventSource.TIMER
    assert production_event.occurred_at == current_timestamp
    assert production_event.payload.get("clock_id") == clock.id.to_json()
    assert production_event.payload.get("time_boundary_id") == boundary.id.to_json()
    assert production_event.payload.get("boundary_type") == "scheduled_activity_start"
    assert {reference.reference_type for reference in production_event.references} == {
        ProductionEventReferenceType.SYSTEM,
        ProductionEventReferenceType.EXTERNAL_OBJECT,
        ProductionEventReferenceType.RECORDING_BLOCK,
        ProductionEventReferenceType.STAGE,
        ProductionEventReferenceType.SCHEDULE_ARTIFACT,
    }


def test_allowed_production_event_mappings() -> None:
    expected_types = {
        TimeBoundaryType.SCHEDULED_ACTIVITY_START: ProductionEventType.SCHEDULE_BOUNDARY_REACHED,
        TimeBoundaryType.SCHEDULED_ACTIVITY_END: ProductionEventType.SCHEDULE_BOUNDARY_REACHED,
        TimeBoundaryType.RECORDING_EXPECTED_START: ProductionEventType.SCHEDULE_BOUNDARY_REACHED,
        TimeBoundaryType.RECORDING_EXPECTED_END: ProductionEventType.SCHEDULE_BOUNDARY_REACHED,
        TimeBoundaryType.TIMEOUT: ProductionEventType.TIMER_ELAPSED,
        TimeBoundaryType.HEARTBEAT_DUE: ProductionEventType.TIMER_ELAPSED,
        TimeBoundaryType.RETRY_DUE: ProductionEventType.TIMER_ELAPSED,
        TimeBoundaryType.MANUAL_DEADLINE: ProductionEventType.TIMER_ELAPSED,
        TimeBoundaryType.CUSTOM: ProductionEventType.TIMER_ELAPSED,
        TimeBoundaryType.UNKNOWN: ProductionEventType.SYSTEM_STATUS_CHANGED,
    }

    for boundary_type, expected_type in expected_types.items():
        clock_event = ClockEvent(
            clock_id=EntityId.new(),
            time_boundary_id=EntityId.new(),
            boundary_type=boundary_type,
            occurred_at=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
        )
        production_event = clock_event.to_production_event(
            correlation_id=CorrelationId.new(),
            received_at=datetime(2026, 7, 8, 10, 0, 1, tzinfo=UTC),
        )

        assert production_event.event_type is expected_type


def test_no_observation_generation_or_schedule_reconciliation_exists() -> None:
    field_names = {
        field.name
        for contract in (RuntimeClock, TimeBoundary, ClockEvent, ClockSummary)
        for field in fields(contract)
    }
    method_names = {
        name for name, value in getmembers(RuntimeClock) if isfunction(value)
    } | {name for name, value in getmembers(ClockEvent) if isfunction(value)}
    forbidden_terms = {
        "observation",
        "evidence",
        "finding",
        "operational_product",
        "reconcile",
        "decide",
    }

    assert not any(term in name for name in field_names | method_names for term in forbidden_terms)


def test_no_job_or_retry_execution_exists() -> None:
    field_names = {
        field.name
        for contract in (RuntimeClock, TimeBoundary, ClockEvent, ClockSummary)
        for field in fields(contract)
    }
    method_names = {
        name for name, value in getmembers(RuntimeClock) if isfunction(value)
    } | {name for name, value in getmembers(ClockEvent) if isfunction(value)}
    forbidden_terms = {
        "execute",
        "job",
        "cron",
        "scheduler",
        "background",
        "run_retry",
        "execute_retry",
        "timeout_execution",
    }

    assert not any(term in name for name in field_names | method_names for term in forbidden_terms)


def test_no_api_persistence_queue_worker_frontend_or_provider_behavior_exists() -> None:
    field_names = {
        field.name
        for contract in (RuntimeClock, TimeBoundary, ClockEvent, ClockSummary)
        for field in fields(contract)
    }
    method_names = {
        name for name, value in getmembers(RuntimeClock) if isfunction(value)
    } | {name for name, value in getmembers(ClockEvent) if isfunction(value)}
    forbidden_terms = {
        "api",
        "database",
        "repository",
        "queue",
        "worker",
        "frontend",
        "provider",
        "vendor",
        "integration",
    }

    assert not any(term in name for name in field_names | method_names for term in forbidden_terms)
