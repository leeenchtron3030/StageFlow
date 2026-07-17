from __future__ import annotations

from dataclasses import replace

import pytest
from runtime_fixtures import entity_id, make_runtime
from software_agent_runtime_fixtures import (
    PREPARED_AT,
    RecordingAgentRuntimeSink,
    make_agent,
    make_dependencies,
    prepare_request,
    start_request,
)

from app.contexts.production.runtime import (
    RuntimeAvailabilityStatus,
    RuntimeEventModeKind,
    RuntimeHealthStatus,
    RuntimeLimitationSeverity,
    RuntimeProfile,
)
from app.contexts.production.software_agent_runtime import (
    AgentRuntimeExecutionPermission,
    AgentRuntimeLifecycleState,
    AgentRuntimeOperationOutcome,
    AgentRuntimeTransitionReasonCode,
)
from app.shared.ids import EntityId


def test_valid_agent_prepare_and_start_sequence() -> None:
    agent, _ = make_agent()

    prepared = agent.prepare(prepare_request(agent))
    started = agent.start(start_request(agent))

    assert prepared.current_snapshot.lifecycle_state is AgentRuntimeLifecycleState.READY
    assert started.current_snapshot.lifecycle_state is AgentRuntimeLifecycleState.RUNNING
    assert started.current_snapshot.lifecycle_revision == 3
    assert started.current_snapshot.execution_permission is (AgentRuntimeExecutionPermission.NORMAL)
    assert started.current_snapshot.health.status is RuntimeHealthStatus.HEALTHY
    assert started.current_snapshot.availability.status is (RuntimeAvailabilityStatus.AVAILABLE)
    assert [transition.next_state for transition in agent.transition_history] == [
        AgentRuntimeLifecycleState.VALIDATED,
        AgentRuntimeLifecycleState.READY,
        AgentRuntimeLifecycleState.RUNNING,
    ]


def test_prepare_makes_embedded_configuration_authoritative_for_execution() -> None:
    agent, _ = make_agent()
    agent.prepare(prepare_request(agent))

    assert agent.execution_configuration is agent.runtime.configuration
    assert agent.snapshot.configuration_id == agent.runtime.configuration.id
    assert agent.snapshot.runtime_id == agent.runtime.configuration.runtime_id


def test_development_profile_requires_explicit_permission() -> None:
    rejected_agent, _ = make_agent(profile=RuntimeProfile.DEVELOPMENT)
    accepted_agent, _ = make_agent(profile=RuntimeProfile.DEVELOPMENT)

    rejected = rejected_agent.prepare(prepare_request(rejected_agent))
    accepted = accepted_agent.prepare(prepare_request(accepted_agent, allow_development=True))

    assert rejected.outcome is AgentRuntimeOperationOutcome.INVALID_RUNTIME
    assert rejected_agent.snapshot.lifecycle_state is AgentRuntimeLifecycleState.CREATED
    assert accepted.outcome is AgentRuntimeOperationOutcome.APPLIED
    assert accepted_agent.snapshot.lifecycle_state is AgentRuntimeLifecycleState.READY
    assert AgentRuntimeTransitionReasonCode.DEVELOPMENT_PROFILE_ACCEPTED in (accepted.reasons)


@pytest.mark.parametrize(
    "profile",
    [
        RuntimeProfile.NODE,
        RuntimeProfile.EXTERNAL_COMPATIBLE,
        RuntimeProfile.UNKNOWN,
    ],
)
def test_non_agent_profiles_are_rejected_without_coercion(
    profile: RuntimeProfile,
) -> None:
    agent, sink = make_agent(profile=profile)
    before = agent.snapshot

    result = agent.prepare(prepare_request(agent))

    assert result.outcome is AgentRuntimeOperationOutcome.INVALID_RUNTIME
    assert result.previous_snapshot == result.current_snapshot == before
    assert agent.transition_history == ()
    assert sink.publications == []


def test_invalid_ed0050_drift_blocks_startup_and_retains_validation_result() -> None:
    runtime = make_runtime(profile=RuntimeProfile.AGENT)
    drifted = replace(
        runtime,
        capability_set=replace(runtime.capability_set, id=entity_id(6100)),
    )
    agent, _ = make_agent(runtime=drifted)

    result = agent.prepare(prepare_request(agent))

    assert result.outcome is AgentRuntimeOperationOutcome.INVALID_CONFIGURATION
    assert result.validation_result is not None
    assert result.validation_result.outcome.value == "invalid"
    assert agent.snapshot.lifecycle_state is AgentRuntimeLifecycleState.CREATED
    assert agent.transition_history == ()


def test_disabled_configuration_is_a_non_error_disabled_startup() -> None:
    agent, _ = make_agent(mode=RuntimeEventModeKind.DISABLED)

    result = agent.prepare(prepare_request(agent))

    assert result.outcome is AgentRuntimeOperationOutcome.DISABLED
    assert agent.snapshot.lifecycle_state is AgentRuntimeLifecycleState.DISABLED
    assert agent.snapshot.availability.status is RuntimeAvailabilityStatus.DISABLED
    assert agent.snapshot.execution_permission is AgentRuntimeExecutionPermission.NONE
    assert agent.snapshot.failure is None


def test_explicitly_unavailable_runtime_cannot_prepare() -> None:
    runtime = make_runtime(profile=RuntimeProfile.AGENT)
    unavailable = replace(
        runtime.availability,
        status=RuntimeAvailabilityStatus.UNAVAILABLE,
    )
    runtime = replace(runtime, availability=unavailable)
    agent, _ = make_agent(runtime=runtime)

    result = agent.prepare(prepare_request(agent))

    assert result.outcome is AgentRuntimeOperationOutcome.INVALID_CONFIGURATION
    assert AgentRuntimeTransitionReasonCode.AVAILABILITY_UNAVAILABLE in result.reasons
    assert agent.snapshot.lifecycle_revision == 0


@pytest.mark.parametrize("missing", ["lifecycle", "health", "availability"])
def test_missing_required_notification_dependency_blocks_prepare(missing: str) -> None:
    dependencies, sink = make_dependencies(missing=(missing,))
    agent, _ = make_agent(dependencies=dependencies, sink=sink)

    result = agent.prepare(prepare_request(agent))

    assert result.outcome is AgentRuntimeOperationOutcome.DEPENDENCY_FAILURE
    assert result.previous_snapshot == result.current_snapshot
    assert agent.transition_history == ()
    assert sink.publications == []


def test_runtime_identity_mismatch_rejects_without_validation_or_mutation() -> None:
    agent, _ = make_agent()
    request = replace(prepare_request(agent), runtime_id=entity_id(6200))

    result = agent.prepare(request)

    assert result.outcome is AgentRuntimeOperationOutcome.INVALID_RUNTIME
    assert result.reasons == (AgentRuntimeTransitionReasonCode.RUNTIME_ID_MISMATCH,)
    assert agent.validation_result is None
    assert agent.snapshot.lifecycle_revision == 0


def test_configuration_identity_mismatch_rejects_without_mutation() -> None:
    agent, _ = make_agent()
    request = replace(prepare_request(agent), configuration_id=entity_id(6201))

    result = agent.prepare(request)

    assert result.outcome is AgentRuntimeOperationOutcome.INVALID_CONFIGURATION
    assert result.reasons == (AgentRuntimeTransitionReasonCode.CONFIGURATION_ID_MISMATCH,)
    assert agent.snapshot.lifecycle_revision == 0


def test_start_before_prepare_is_an_invalid_transition() -> None:
    agent, _ = make_agent()

    result = agent.start(start_request(agent, revision=0))

    assert result.outcome is AgentRuntimeOperationOutcome.INVALID_TRANSITION
    assert agent.snapshot.lifecycle_state is AgentRuntimeLifecycleState.CREATED


def test_prepare_with_nonblocking_runtime_limitation_is_degraded_but_ready() -> None:
    runtime = make_runtime(
        profile=RuntimeProfile.AGENT,
        limitation_severity=RuntimeLimitationSeverity.NON_BLOCKING,
    )
    agent, _ = make_agent(runtime=runtime)

    result = agent.prepare(prepare_request(agent))

    assert result.outcome is AgentRuntimeOperationOutcome.APPLIED
    assert agent.snapshot.lifecycle_state is AgentRuntimeLifecycleState.READY
    assert agent.snapshot.health.status is RuntimeHealthStatus.DEGRADED
    assert agent.snapshot.active_limitations == runtime.limitations


def test_prepare_timestamps_are_caller_supplied_and_reused_for_both_steps() -> None:
    agent, _ = make_agent()
    result = agent.prepare(prepare_request(agent))

    assert {transition.occurred_at for transition in result.transitions} == {PREPARED_AT}
    assert result.current_snapshot.state_entered_at == PREPARED_AT
    assert result.current_snapshot.health.assessed_at == PREPARED_AT
    assert result.current_snapshot.availability.declared_at == PREPARED_AT


def test_dependency_bundle_is_explicit_not_a_service_locator() -> None:
    sink = RecordingAgentRuntimeSink()
    dependencies, _ = make_dependencies(sink)
    dependency_fields = set(dependencies.__dataclass_fields__)

    assert dependency_fields == {
        "lifecycle_event_sink",
        "runtime_health_sink",
        "runtime_availability_sink",
    }
    assert not {"database", "filesystem", "network", "repository"} & dependency_fields


def test_two_agents_may_use_distinct_runtime_identity() -> None:
    first_runtime = make_runtime(
        runtime_id=EntityId("20000000-0000-0000-0000-000000000001"),
        profile=RuntimeProfile.AGENT,
    )
    second_runtime = make_runtime(
        runtime_id=EntityId("20000000-0000-0000-0000-000000000002"),
        profile=RuntimeProfile.AGENT,
    )
    first, _ = make_agent(runtime=first_runtime, agent_instance_id=entity_id(6300))
    second, _ = make_agent(runtime=second_runtime, agent_instance_id=entity_id(6301))

    first.prepare(prepare_request(first))

    assert first.snapshot.runtime_id != second.snapshot.runtime_id
    assert first.snapshot.lifecycle_revision == 2
    assert second.snapshot.lifecycle_revision == 0
