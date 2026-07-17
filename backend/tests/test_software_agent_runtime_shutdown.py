from __future__ import annotations

from dataclasses import replace

import pytest
from runtime_fixtures import entity_id
from software_agent_runtime_fixtures import (
    cancellation_request,
    failure_request,
    make_agent,
    make_prepared_agent,
    make_running_agent,
    prepare_request,
    start_request,
    stop_request,
)

from app.contexts.production.runtime import (
    RuntimeAvailabilityStatus,
    RuntimeEventModeKind,
    RuntimePressureState,
)
from app.contexts.production.software_agent_runtime import (
    AgentRuntimeExecutionPermission,
    AgentRuntimeLifecycleState,
    AgentRuntimeOperationOutcome,
    AgentRuntimeTransitionReasonCode,
)


def _agent_in_state(
    state: AgentRuntimeLifecycleState,
):
    if state is AgentRuntimeLifecycleState.CREATED:
        return make_agent()[0]
    if state is AgentRuntimeLifecycleState.READY:
        return make_prepared_agent()[0]
    if state is AgentRuntimeLifecycleState.RUNNING:
        return make_running_agent()[0]
    if state is AgentRuntimeLifecycleState.YIELDING:
        return make_running_agent(pressure=RuntimePressureState.ELEVATED)[0]
    if state is AgentRuntimeLifecycleState.SUSPENDED:
        return make_running_agent(pressure=RuntimePressureState.CRITICAL)[0]
    if state is AgentRuntimeLifecycleState.FAILED:
        agent, _ = make_agent()
        agent.report_failure(failure_request(agent))
        return agent
    if state is AgentRuntimeLifecycleState.DISABLED:
        agent, _ = make_agent(mode=RuntimeEventModeKind.DISABLED)
        agent.prepare(prepare_request(agent))
        return agent
    raise AssertionError(f"unsupported test state: {state}")


@pytest.mark.parametrize(
    "state",
    [
        AgentRuntimeLifecycleState.CREATED,
        AgentRuntimeLifecycleState.READY,
        AgentRuntimeLifecycleState.RUNNING,
        AgentRuntimeLifecycleState.YIELDING,
        AgentRuntimeLifecycleState.SUSPENDED,
        AgentRuntimeLifecycleState.FAILED,
        AgentRuntimeLifecycleState.DISABLED,
    ],
)
def test_stop_is_synchronous_deterministic_and_terminal(
    state: AgentRuntimeLifecycleState,
) -> None:
    agent = _agent_in_state(state)
    previous_health = agent.snapshot.health.status
    previous_revision = agent.snapshot.lifecycle_revision

    result = agent.stop(stop_request(agent))

    assert result.outcome is AgentRuntimeOperationOutcome.APPLIED
    assert agent.snapshot.lifecycle_state is AgentRuntimeLifecycleState.STOPPED
    assert agent.snapshot.execution_permission is AgentRuntimeExecutionPermission.NONE
    assert agent.snapshot.availability.status is RuntimeAvailabilityStatus.UNAVAILABLE
    assert agent.snapshot.health.status is previous_health
    expected_states = (
        [AgentRuntimeLifecycleState.STOPPED]
        if state is AgentRuntimeLifecycleState.CREATED
        else [
            AgentRuntimeLifecycleState.STOPPING,
            AgentRuntimeLifecycleState.STOPPED,
        ]
    )
    assert [transition.next_state for transition in result.transitions] == expected_states
    assert agent.snapshot.lifecycle_revision == previous_revision + len(expected_states)


def test_exact_stop_replay_preserves_original_and_unique_repeated_stop_rejects() -> None:
    agent, _ = make_running_agent()
    request = stop_request(agent)
    first = agent.stop(request)
    history = agent.transition_history

    replay = agent.stop(request)
    repeated = agent.stop(stop_request(agent, number=71))

    assert replay.outcome is AgentRuntimeOperationOutcome.ALREADY_APPLIED
    assert replay.current_snapshot == first.current_snapshot
    assert replay.transitions == first.transitions
    assert repeated.outcome is AgentRuntimeOperationOutcome.REJECTED
    assert AgentRuntimeTransitionReasonCode.ALREADY_STOPPED in repeated.reasons
    assert agent.transition_history == history


@pytest.mark.parametrize(
    "pressure",
    [
        RuntimePressureState.NORMAL,
        RuntimePressureState.ELEVATED,
        RuntimePressureState.CRITICAL,
    ],
)
def test_cancellation_from_active_state_revokes_permission_and_stops(
    pressure: RuntimePressureState,
) -> None:
    agent, _ = make_running_agent(pressure=pressure)
    request = cancellation_request(agent)

    result = agent.cancel(request)

    assert result.outcome is AgentRuntimeOperationOutcome.APPLIED
    assert agent.snapshot.lifecycle_state is AgentRuntimeLifecycleState.STOPPED
    assert agent.snapshot.execution_permission is AgentRuntimeExecutionPermission.NONE
    assert agent.snapshot.cancellation == request
    assert [transition.next_state for transition in result.transitions] == [
        AgentRuntimeLifecycleState.STOPPING,
        AgentRuntimeLifecycleState.STOPPED,
    ]


def test_duplicate_cancellation_is_idempotent_and_identity_conflict_is_typed() -> None:
    agent, _ = make_running_agent()
    request = cancellation_request(agent)
    first = agent.cancel(request)

    replay = agent.cancel(request)
    conflict = agent.cancel(
        replace(
            request,
            operation_id=entity_id(9090),
            cancellation_reason="different meaning",
            expected_lifecycle_revision=agent.snapshot.lifecycle_revision,
        )
    )

    assert replay.outcome is AgentRuntimeOperationOutcome.ALREADY_APPLIED
    assert replay.current_snapshot == first.current_snapshot
    assert conflict.outcome is AgentRuntimeOperationOutcome.OPERATION_CONFLICT
    assert AgentRuntimeTransitionReasonCode.CANCELLATION_IDENTITY_CONFLICT in (conflict.reasons)


def test_cancel_after_stopped_is_non_mutating() -> None:
    agent, _ = make_running_agent()
    agent.stop(stop_request(agent))
    before = agent.snapshot

    result = agent.cancel(cancellation_request(agent, number=72))

    assert result.outcome is AgentRuntimeOperationOutcome.REJECTED
    assert AgentRuntimeTransitionReasonCode.ALREADY_STOPPED in result.reasons
    assert result.current_snapshot == before == agent.snapshot


def test_stopped_instance_cannot_prepare_start_resume_or_accept_pressure() -> None:
    agent, _ = make_running_agent()
    agent.stop(stop_request(agent))
    before = agent.snapshot

    prepare = agent.prepare(prepare_request(agent, number=73))
    start = agent.start(start_request(agent, number=74))

    assert prepare.outcome is AgentRuntimeOperationOutcome.INVALID_TRANSITION
    assert start.outcome is AgentRuntimeOperationOutcome.INVALID_TRANSITION
    assert agent.snapshot == before


def test_cancellation_is_only_in_process_lifecycle_data() -> None:
    agent, _ = make_running_agent()
    result = agent.cancel(cancellation_request(agent))

    assert result.current_snapshot.cancellation is not None
    assert not hasattr(result.current_snapshot.cancellation, "pid")
    assert not hasattr(result.current_snapshot.cancellation, "signal")
    assert not hasattr(result.current_snapshot.cancellation, "process_handle")
