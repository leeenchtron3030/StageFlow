from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.shared.domain_events import DomainEvent
from app.shared.errors import DomainError, StageFlowError, ValidationError
from app.shared.ids import CorrelationId, EntityId
from app.shared.result import Result
from app.shared.time import FixedClock, SystemClock, TimeRange


def test_entity_id_creation_and_comparison() -> None:
    value = "018f0f2a-3d91-7a43-9d82-fc34cdaaa111"

    entity_id = EntityId.parse(value)

    assert entity_id == EntityId(value)
    assert str(entity_id) == value
    assert entity_id.to_json() == value
    assert UUID(str(EntityId.new()))


def test_correlation_id_generation_is_distinct_from_entity_id() -> None:
    correlation_id = CorrelationId.new()

    assert UUID(str(correlation_id))
    assert correlation_id != EntityId.parse(str(correlation_id))
    assert correlation_id.to_json() == str(correlation_id)


def test_result_success_and_failure_behavior() -> None:
    success: Result[str] = Result.ok("ready")
    error = ValidationError("validation.failed", "Validation failed.")
    failure = Result[str].fail(error)

    assert success.is_success
    assert not success.is_failure
    assert success.value == "ready"
    assert failure.is_failure
    assert not failure.is_success
    assert failure.error == error


def test_error_serialization_and_string_representation() -> None:
    error = DomainError(
        code="domain.failed",
        message="Domain rule failed.",
        details={"field": "value"},
    )

    assert str(error) == "domain.failed: Domain rule failed."
    assert error.to_dict() == {
        "code": "domain.failed",
        "message": "Domain rule failed.",
        "details": {"field": "value"},
    }


def test_fixed_clock_returns_deterministic_time() -> None:
    fixed_at = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)
    clock = FixedClock(fixed_at)

    assert clock.now() == fixed_at
    assert SystemClock().now().tzinfo == UTC


def test_time_range_duration_and_validation() -> None:
    start = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)
    end = start + timedelta(minutes=5)

    time_range = TimeRange(start=start, end=end)

    assert time_range.duration == timedelta(minutes=5)
    with pytest.raises(ValueError, match="end must be after start"):
        TimeRange(start=end, end=start)


def test_domain_event_base_properties() -> None:
    occurred_at = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)
    correlation_id = CorrelationId.new()
    event_id = EntityId.new()

    event = DomainEvent(
        event_type="generic.event",
        correlation_id=correlation_id,
        occurred_at=occurred_at,
        event_id=event_id,
        actor="operator",
        metadata={"source": "test"},
    )

    assert event.event_id == event_id
    assert event.event_type == "generic.event"
    assert event.occurred_at == occurred_at
    assert event.correlation_id == correlation_id
    assert event.actor == "operator"
    assert dict(event.metadata) == {"source": "test"}


def test_stageflow_error_without_details_serializes_minimally() -> None:
    error = StageFlowError("configuration.missing", "Configuration is missing.")

    assert error.to_dict() == {
        "code": "configuration.missing",
        "message": "Configuration is missing.",
    }
