from __future__ import annotations

from dataclasses import fields, replace

from runtime_fixtures import entity_id, make_runtime, synchronize_runtime, validation_codes

from app.contexts.production.runtime import (
    RuntimeAvailabilityStatus,
    RuntimeConfigurationValidity,
    RuntimeDeclaredComponentStatus,
    RuntimeEventModeKind,
    RuntimeHealthStatus,
    RuntimeLimitationSeverity,
    RuntimeReadinessRoute,
    RuntimeSummary,
    RuntimeValidationOutcome,
    RuntimeValidationReasonCode,
    validate_runtime,
)


def test_health_status_vocabulary_is_exact() -> None:
    assert {status.value for status in RuntimeHealthStatus} == {
        "healthy",
        "degraded",
        "unhealthy",
        "unknown",
    }


def test_availability_status_vocabulary_is_exact() -> None:
    assert {status.value for status in RuntimeAvailabilityStatus} == {
        "available",
        "limited",
        "unavailable",
        "disabled",
        "unknown",
    }


def test_configuration_validity_vocabulary_is_exact() -> None:
    assert {status.value for status in RuntimeConfigurationValidity} == {
        "valid",
        "valid_with_limitations",
        "invalid",
        "unknown",
    }


def test_healthy_available_runtime_is_valid() -> None:
    runtime = make_runtime()

    assert runtime.health.status is RuntimeHealthStatus.HEALTHY
    assert runtime.health.configuration_validity is RuntimeConfigurationValidity.VALID
    assert runtime.availability.status is RuntimeAvailabilityStatus.AVAILABLE
    assert validate_runtime(runtime).outcome is RuntimeValidationOutcome.VALID


def test_nonblocking_limitation_produces_degraded_limited_declaration() -> None:
    runtime = make_runtime(limitation_severity=RuntimeLimitationSeverity.NON_BLOCKING)

    assert runtime.health.status is RuntimeHealthStatus.DEGRADED
    assert runtime.availability.status is RuntimeAvailabilityStatus.LIMITED
    assert validate_runtime(runtime).outcome is (
        RuntimeValidationOutcome.VALID_WITH_LIMITATIONS
    )


def test_blocking_limitation_makes_configuration_invalid() -> None:
    runtime = make_runtime(limitation_severity=RuntimeLimitationSeverity.BLOCKING)

    assert validate_runtime(runtime).outcome is RuntimeValidationOutcome.INVALID
    assert RuntimeValidationReasonCode.BLOCKING_LIMITATION.value in (
        validation_codes(runtime)
    )


def test_health_and_availability_reference_first_class_limitations() -> None:
    runtime = make_runtime(
        route=RuntimeReadinessRoute.STRONG_FINALIZATION,
        limitation_severity=RuntimeLimitationSeverity.NON_BLOCKING,
    )
    limitation = runtime.limitations[0]

    assert runtime.health.limitation_ids == (limitation.id,)
    assert runtime.availability.limitation_ids == (limitation.id,)
    assert limitation.affected_capability_ids
    assert limitation.introduced_at is not None
    assert limitation.description


def test_missing_health_limitation_reference_is_invalid() -> None:
    runtime = make_runtime()
    health = replace(runtime.health, limitation_ids=(entity_id(840),))
    changed = synchronize_runtime(runtime, health=health)

    assert RuntimeValidationReasonCode.LIMITATION_REFERENCE_MISSING.value in (
        validation_codes(changed)
    )


def test_missing_availability_limitation_reference_is_invalid() -> None:
    runtime = make_runtime()
    availability = replace(runtime.availability, limitation_ids=(entity_id(841),))
    changed = synchronize_runtime(runtime, availability=availability)

    assert RuntimeValidationReasonCode.LIMITATION_REFERENCE_MISSING.value in (
        validation_codes(changed)
    )


def test_healthy_status_requires_valid_available_components() -> None:
    runtime = make_runtime()
    health = replace(
        runtime.health,
        capability_availability=RuntimeDeclaredComponentStatus.DEGRADED,
    )
    changed = synchronize_runtime(runtime, health=health)

    assert RuntimeValidationReasonCode.HEALTH_DECLARATION_INCONSISTENT.value in (
        validation_codes(changed)
    )


def test_unhealthy_runtime_cannot_be_declared_available() -> None:
    runtime = make_runtime()
    health = replace(
        runtime.health,
        status=RuntimeHealthStatus.UNHEALTHY,
        configuration_validity=RuntimeConfigurationValidity.INVALID,
        capability_availability=RuntimeDeclaredComponentStatus.UNAVAILABLE,
        collection_plan_validity=RuntimeDeclaredComponentStatus.UNAVAILABLE,
    )
    changed = synchronize_runtime(runtime, health=health)

    assert (
        RuntimeValidationReasonCode.AVAILABILITY_DECLARATION_INCONSISTENT.value
        in validation_codes(changed)
    )


def test_unhealthy_unavailable_declarations_remain_distinct() -> None:
    runtime = make_runtime()
    health = replace(
        runtime.health,
        status=RuntimeHealthStatus.UNHEALTHY,
        configuration_validity=RuntimeConfigurationValidity.INVALID,
        capability_availability=RuntimeDeclaredComponentStatus.UNAVAILABLE,
        collection_plan_validity=RuntimeDeclaredComponentStatus.UNAVAILABLE,
    )
    availability = replace(
        runtime.availability,
        status=RuntimeAvailabilityStatus.UNAVAILABLE,
        expected_capability_availability=RuntimeDeclaredComponentStatus.UNAVAILABLE,
    )
    changed = synchronize_runtime(runtime, health=health, availability=availability)

    assert changed.health.status is RuntimeHealthStatus.UNHEALTHY
    assert changed.availability.status is RuntimeAvailabilityStatus.UNAVAILABLE
    assert RuntimeValidationReasonCode.AVAILABILITY_DECLARATION_INCONSISTENT.value not in (
        validation_codes(changed)
    )


def test_event_mode_requires_event_compatible_availability() -> None:
    runtime = make_runtime()
    availability = replace(runtime.availability, event_mode_compatible=False)
    changed = synchronize_runtime(runtime, availability=availability)

    assert (
        RuntimeValidationReasonCode.AVAILABILITY_DECLARATION_INCONSISTENT.value
        in validation_codes(changed)
    )


def test_maintenance_mode_may_be_healthy_but_limited() -> None:
    runtime = make_runtime(mode=RuntimeEventModeKind.MAINTENANCE)

    assert runtime.health.status is RuntimeHealthStatus.HEALTHY
    assert runtime.availability.status is RuntimeAvailabilityStatus.LIMITED
    assert validate_runtime(runtime).outcome is RuntimeValidationOutcome.VALID


def test_unknown_health_and_availability_are_explicit_not_monitored() -> None:
    runtime = make_runtime()
    health = replace(
        runtime.health,
        status=RuntimeHealthStatus.UNKNOWN,
        configuration_validity=RuntimeConfigurationValidity.UNKNOWN,
        capability_availability=RuntimeDeclaredComponentStatus.UNKNOWN,
        resource_policy_availability=RuntimeDeclaredComponentStatus.UNKNOWN,
        collection_plan_validity=RuntimeDeclaredComponentStatus.UNKNOWN,
    )
    availability = replace(
        runtime.availability,
        status=RuntimeAvailabilityStatus.UNKNOWN,
        expected_capability_availability=RuntimeDeclaredComponentStatus.UNKNOWN,
    )
    changed = synchronize_runtime(runtime, health=health, availability=availability)

    assert validate_runtime(changed).outcome is RuntimeValidationOutcome.VALID
    assert not {"last_probe", "liveness", "monitor", "probe_result"} & {
        field.name for field in fields(type(health))
    }


def test_limitation_order_and_references_are_deterministic() -> None:
    runtime = make_runtime(limitation_severity=RuntimeLimitationSeverity.NON_BLOCKING)
    first = runtime.limitations[0]
    second = replace(first, id=entity_id(842), code="second_limitation")
    limitation_ids = (second.id, first.id)
    health = replace(runtime.health, limitation_ids=limitation_ids)
    availability = replace(runtime.availability, limitation_ids=limitation_ids)
    changed = synchronize_runtime(
        runtime,
        health=health,
        availability=availability,
        limitations=(second, first),
    )

    assert changed.limitations == (first, second)
    assert changed.health.limitation_ids == (first.id, second.id)
    assert changed.availability.limitation_ids == (first.id, second.id)


def test_summary_reports_health_availability_and_validation_without_secrets() -> None:
    runtime = make_runtime(limitation_severity=RuntimeLimitationSeverity.NON_BLOCKING)
    validation = validate_runtime(runtime)
    summary = RuntimeSummary.from_runtime(runtime, validation)

    assert summary.health is RuntimeHealthStatus.DEGRADED
    assert summary.availability is RuntimeAvailabilityStatus.LIMITED
    assert summary.validation_outcome is RuntimeValidationOutcome.VALID_WITH_LIMITATIONS
    assert summary.limitation_count == 1
    assert summary.blocking_limitation_count == 0
    assert "non_blocking_limitation" in summary.warning_codes


def test_health_policy_is_a_reporting_declaration_not_a_scheduler() -> None:
    policy = make_runtime().configuration.health_reporting_policy

    assert policy.enabled is True
    assert policy.expected_reporting_interval is not None
    assert not {"callback", "loop", "next_run", "scheduler", "task"} & {
        field.name for field in fields(type(policy))
    }
