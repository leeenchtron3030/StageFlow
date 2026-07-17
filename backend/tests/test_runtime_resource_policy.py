from __future__ import annotations

from dataclasses import fields, replace

import pytest
from runtime_fixtures import make_runtime, synchronize_runtime, validation_codes

from app.contexts.production.runtime import (
    RuntimeAssetRetentionExpectation,
    RuntimeAvailabilityStatus,
    RuntimeEventModeKind,
    RuntimeGpuUsePolicy,
    RuntimeNetworkPolicy,
    RuntimeOptionalActivityPolicy,
    RuntimePressureAction,
    RuntimePressureResponse,
    RuntimePressureState,
    RuntimeResourcePriorityClass,
    RuntimeSourceAccessMode,
    RuntimeValidationOutcome,
    RuntimeValidationReasonCode,
    validate_runtime,
)


def test_resource_budget_is_explicit_and_conservative() -> None:
    budget = make_runtime().resource_policy.budget

    assert budget.maximum_cpu_utilization_percentage == 20
    assert budget.maximum_memory_allocation_bytes == 512_000_000
    assert budget.maximum_disk_read_bytes_per_second == 20_000_000
    assert budget.maximum_disk_write_bytes_per_second == 0
    assert budget.maximum_concurrent_candidate_assessments == 2
    assert budget.maximum_concurrent_read_access_checks == 1


@pytest.mark.parametrize("value", [-0.1, 100.1])
def test_resource_budget_rejects_invalid_percentages(value: float) -> None:
    budget = make_runtime().resource_policy.budget

    with pytest.raises(ValueError, match="between 0 and 100"):
        replace(budget, maximum_cpu_utilization_percentage=value)


def test_resource_budget_rejects_negative_counts_and_rates() -> None:
    budget = make_runtime().resource_policy.budget

    with pytest.raises(ValueError, match="negative"):
        replace(budget, maximum_collections_per_minute=-1)
    with pytest.raises(ValueError, match="negative"):
        replace(budget, maximum_disk_read_bytes_per_second=-1)


def test_resource_budget_is_declarative_not_an_enforcer() -> None:
    names = {field.name for field in fields(type(make_runtime().resource_policy.budget))}

    assert not {
        "acquire",
        "current_cpu",
        "enforce",
        "semaphore",
        "throttle",
        "usage",
    } & names


def test_pressure_policy_contains_all_required_safety_responses() -> None:
    responses = {
        response.pressure_state: response.action
        for response in make_runtime().resource_policy.pressure_responses
    }

    assert responses == {
        RuntimePressureState.NORMAL: RuntimePressureAction.OPERATE_WITHIN_BUDGETS,
        RuntimePressureState.ELEVATED: RuntimePressureAction.REDUCE_OPTIONAL_ACTIVITY,
        RuntimePressureState.CRITICAL: RuntimePressureAction.SUSPEND_OPTIONAL_ACTIVITY,
        RuntimePressureState.RECORDING_SAFETY_UNCERTAIN: (
            RuntimePressureAction.YIELD_NONESSENTIAL_WORK
        ),
    }


def test_pressure_response_rejects_unsafe_action() -> None:
    with pytest.raises(ValueError, match="production priority"):
        RuntimePressureResponse(
            pressure_state=RuntimePressureState.CRITICAL,
            action=RuntimePressureAction.OPERATE_WITHIN_BUDGETS,
        )


def test_resource_policy_requires_each_pressure_state_once() -> None:
    policy = make_runtime().resource_policy

    with pytest.raises(ValueError, match="requires all"):
        replace(policy, pressure_responses=policy.pressure_responses[:-1])
    with pytest.raises(ValueError, match="must be unique"):
        replace(
            policy,
            pressure_responses=(*policy.pressure_responses, policy.pressure_responses[0]),
        )


def test_baseline_event_mode_is_production_subordinate_and_offline_capable() -> None:
    runtime = make_runtime()

    assert runtime.resource_policy.priority_class is (
        RuntimeResourcePriorityClass.PRODUCTION_SUBORDINATE
    )
    assert runtime.event_mode.network_policy is RuntimeNetworkPolicy.NETWORK_OPTIONAL
    assert runtime.resource_policy.gpu_use_policy is RuntimeGpuUsePolicy.FORBIDDEN
    assert runtime.event_mode.asset_retention_expectation is (
        RuntimeAssetRetentionExpectation.SOURCE_OWNED_NO_CHANGE
    )
    assert validate_runtime(runtime).outcome is RuntimeValidationOutcome.VALID


def test_event_mode_rejects_non_subordinate_priority() -> None:
    runtime = make_runtime(priority=RuntimeResourcePriorityClass.DEVELOPMENT)

    assert validate_runtime(runtime).outcome is RuntimeValidationOutcome.INVALID
    assert RuntimeValidationReasonCode.EVENT_MODE_PRIORITY_MISMATCH.value in (
        validation_codes(runtime)
    )


def test_event_mode_rejects_required_network() -> None:
    runtime = make_runtime(network_policy=RuntimeNetworkPolicy.NETWORK_REQUIRED)

    assert RuntimeValidationReasonCode.EVENT_MODE_NETWORK_REQUIRED.value in (
        validation_codes(runtime)
    )


def test_event_mode_rejects_source_observation_disk_writes() -> None:
    runtime = make_runtime(disk_write_budget=1)

    assert RuntimeValidationReasonCode.EVENT_MODE_DISK_WRITE_FORBIDDEN.value in (
        validation_codes(runtime)
    )


def test_event_mode_rejects_unconstrained_gpu_use() -> None:
    runtime = make_runtime(gpu_policy=RuntimeGpuUsePolicy.ALLOWED)

    assert RuntimeValidationReasonCode.EVENT_MODE_GPU_UNCONSTRAINED.value in (
        validation_codes(runtime)
    )


def test_event_mode_rejects_optional_activity_that_cannot_yield() -> None:
    runtime = make_runtime(optional_activity=RuntimeOptionalActivityPolicy.CONTINUE)

    assert RuntimeValidationReasonCode.EVENT_MODE_OPTIONAL_ACTIVITY_UNSAFE.value in (
        validation_codes(runtime)
    )


def test_event_mode_rejects_source_retention_change() -> None:
    runtime = make_runtime()
    event_mode = replace(
        runtime.event_mode,
        asset_retention_expectation=(
            RuntimeAssetRetentionExpectation.RETAIN_SOURCE_REFERENCE
        ),
    )
    changed = synchronize_runtime(runtime, event_mode=event_mode)

    assert RuntimeValidationReasonCode.EVENT_MODE_RETENTION_UNSAFE.value in (
        validation_codes(changed)
    )


def test_event_mode_rejects_write_access_to_an_active_recording_source() -> None:
    runtime = make_runtime()
    source = replace(
        runtime.capability_set.source_capabilities[0],
        access_mode=RuntimeSourceAccessMode.READ_WRITE_DECLARED,
    )
    capability_set = replace(
        runtime.capability_set,
        source_capabilities=(source,),
    )
    changed = synchronize_runtime(runtime, capability_set=capability_set)

    assert RuntimeValidationReasonCode.EVENT_MODE_SOURCE_WRITE_ACCESS.value in (
        validation_codes(changed)
    )


@pytest.mark.parametrize(
    "network_policy",
    [
        RuntimeNetworkPolicy.OFFLINE_CAPABLE,
        RuntimeNetworkPolicy.LOCAL_NETWORK_ONLY,
        RuntimeNetworkPolicy.NETWORK_OPTIONAL,
    ],
)
def test_event_mode_supports_non_internet_dependent_network_policies(
    network_policy: RuntimeNetworkPolicy,
) -> None:
    runtime = make_runtime(network_policy=network_policy)

    assert validate_runtime(runtime).outcome is RuntimeValidationOutcome.VALID


def test_disabled_mode_has_no_active_collection_and_disabled_availability() -> None:
    runtime = make_runtime(mode=RuntimeEventModeKind.DISABLED)

    assert runtime.configuration.enabled is False
    assert all(not plan.enabled for plan in runtime.collection_plans)
    assert runtime.availability.status is RuntimeAvailabilityStatus.DISABLED
    assert validate_runtime(runtime).outcome is RuntimeValidationOutcome.VALID


def test_disabled_mode_with_active_plan_is_invalid() -> None:
    runtime = make_runtime(mode=RuntimeEventModeKind.DISABLED)
    plan = replace(runtime.collection_plans[0], enabled=True)
    changed = synchronize_runtime(runtime, collection_plans=(plan,))

    assert RuntimeValidationReasonCode.DISABLED_RUNTIME_HAS_ACTIVE_PLAN.value in (
        validation_codes(changed)
    )


def test_disabled_mode_with_available_declaration_is_invalid() -> None:
    runtime = make_runtime(mode=RuntimeEventModeKind.DISABLED)
    availability = replace(
        runtime.availability,
        status=RuntimeAvailabilityStatus.AVAILABLE,
    )
    changed = synchronize_runtime(runtime, availability=availability)

    assert (
        RuntimeValidationReasonCode.DISABLED_RUNTIME_AVAILABILITY_MISMATCH.value
        in validation_codes(changed)
    )


def test_event_mode_contract_has_no_process_or_control_surface() -> None:
    names = {field.name for field in fields(type(make_runtime().event_mode))}

    assert not {
        "activate",
        "daemon",
        "process_id",
        "recorder_control",
        "service",
        "start",
        "stop",
    } & names
