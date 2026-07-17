from __future__ import annotations

from dataclasses import replace

import pytest
from runtime_fixtures import entity_id
from software_agent_runtime_fixtures import (
    PREPARED_AT,
    failure_request,
    make_agent,
    make_prepared_agent,
    make_running_agent,
    operation_id,
    prepare_request,
    pressure_update,
    resume_request,
    start_request,
    stop_request,
)

from app.contexts.production.runtime import (
    RuntimeAvailabilityStatus,
    RuntimeHealthStatus,
    RuntimePressureState,
)
from app.contexts.production.software_agent_runtime import (
    AgentRuntimeExecutionPermission,
    AgentRuntimeLifecycleState,
    AgentRuntimeOperationOutcome,
    AgentRuntimeTransitionReasonCode,
)


@pytest.mark.parametrize(
    ("pressure", "state", "permission"),
    [
        (
            RuntimePressureState.NORMAL,
            AgentRuntimeLifecycleState.RUNNING,
            AgentRuntimeExecutionPermission.NORMAL,
        ),
        (
            RuntimePressureState.ELEVATED,
            AgentRuntimeLifecycleState.YIELDING,
            AgentRuntimeExecutionPermission.REDUCED,
        ),
        (
            RuntimePressureState.CRITICAL,
            AgentRuntimeLifecycleState.SUSPENDED,
            AgentRuntimeExecutionPermission.NONE,
        ),
    ],
)
def test_ready_starts_in_pressure_derived_state(
    pressure: RuntimePressureState,
    state: AgentRuntimeLifecycleState,
    permission: AgentRuntimeExecutionPermission,
) -> None:
    agent, _ = make_prepared_agent()

    result = agent.start(start_request(agent, pressure=pressure))

    assert result.outcome is AgentRuntimeOperationOutcome.APPLIED
    assert result.current_snapshot.lifecycle_state is state
    assert result.current_snapshot.execution_permission is permission
    assert result.transition is not None
    assert result.transition.previous_state is AgentRuntimeLifecycleState.READY


def test_transition_history_is_immutable_ordered_and_revision_consistent() -> None:
    agent, _ = make_running_agent()
    agent.update_pressure(pressure_update(agent, RuntimePressureState.ELEVATED))
    agent.resume(resume_request(agent, RuntimePressureState.NORMAL))

    history = agent.transition_history

    assert isinstance(history, tuple)
    assert [transition.lifecycle_revision for transition in history] == [1, 2, 3, 4, 5]
    assert tuple(transition.id for transition in history) == (agent.snapshot.transition_lineage_ids)
    assert all(
        earlier.next_state is later.previous_state
        for earlier, later in zip(history, history[1:], strict=False)
    )


def test_representative_forbidden_transitions_do_not_mutate() -> None:
    created, _ = make_agent()
    before = created.snapshot
    pressure_result = created.update_pressure(
        pressure_update(created, RuntimePressureState.ELEVATED)
    )

    assert pressure_result.outcome is AgentRuntimeOperationOutcome.INVALID_TRANSITION
    assert created.snapshot == before
    assert created.transition_history == ()

    prepared, _ = make_prepared_agent()
    prepared.start(start_request(prepared))
    before = prepared.snapshot
    second_start = prepared.start(start_request(prepared, number=90))

    assert second_start.outcome is AgentRuntimeOperationOutcome.INVALID_TRANSITION
    assert prepared.snapshot == before


def test_reported_failure_is_explicit_unhealthy_and_blocks_start_and_resume() -> None:
    agent, _ = make_agent()

    failure = agent.report_failure(failure_request(agent))

    assert failure.outcome is AgentRuntimeOperationOutcome.FAILED
    assert agent.snapshot.lifecycle_state is AgentRuntimeLifecycleState.FAILED
    assert agent.snapshot.health.status is RuntimeHealthStatus.UNHEALTHY
    assert agent.snapshot.availability.status is RuntimeAvailabilityStatus.UNAVAILABLE
    assert agent.snapshot.execution_permission is AgentRuntimeExecutionPermission.NONE

    start = agent.start(start_request(agent, number=91))
    resume = agent.resume(resume_request(agent, RuntimePressureState.NORMAL, number=92))

    assert start.outcome is AgentRuntimeOperationOutcome.INVALID_TRANSITION
    assert resume.outcome is AgentRuntimeOperationOutcome.INVALID_TRANSITION
    assert AgentRuntimeTransitionReasonCode.RESUME_BLOCKED_BY_FAILURE in resume.reasons


def test_exact_replay_preserves_original_result_time_and_does_not_append() -> None:
    agent, _ = make_agent()
    request = prepare_request(agent)
    first = agent.prepare(request)
    history = agent.transition_history

    replay = agent.prepare(request)

    assert replay.outcome is AgentRuntimeOperationOutcome.ALREADY_APPLIED
    assert replay.current_snapshot == first.current_snapshot
    assert replay.previous_snapshot == first.previous_snapshot
    assert replay.transitions == first.transitions
    assert replay.occurred_at == PREPARED_AT
    assert agent.transition_history == history
    assert agent.snapshot.lifecycle_revision == 2


def test_conflicting_operation_replay_does_not_replace_original_record() -> None:
    agent, _ = make_agent()
    request = prepare_request(agent)
    original = agent.prepare(request)
    conflict_request = replace(request, configuration_id=entity_id(7777))

    conflict = agent.prepare(conflict_request)
    replay = agent.prepare(request)

    assert conflict.outcome is AgentRuntimeOperationOutcome.OPERATION_CONFLICT
    assert conflict.current_snapshot == original.current_snapshot
    assert replay.outcome is AgentRuntimeOperationOutcome.ALREADY_APPLIED
    assert replay.current_snapshot == original.current_snapshot
    assert len(agent.transition_history) == 2


def test_stale_revision_cannot_overwrite_current_state() -> None:
    agent, _ = make_running_agent()
    before = agent.snapshot

    result = agent.stop(stop_request(agent, revision=2))

    assert result.outcome is AgentRuntimeOperationOutcome.STALE_REVISION
    assert result.previous_snapshot == before == result.current_snapshot
    assert agent.snapshot == before
    assert len(agent.transition_history) == 3


def test_summary_reports_only_typed_bounded_runtime_state() -> None:
    agent, _ = make_running_agent()

    summary = agent.summary()

    assert summary.lifecycle_state is AgentRuntimeLifecycleState.RUNNING
    assert summary.lifecycle_revision == 3
    assert summary.execution_permission is AgentRuntimeExecutionPermission.NORMAL
    assert summary.transition_count == 3
    assert summary.cancellation_active is False
    assert summary.failure_code is None
    assert not hasattr(summary, "source_path")
    assert not hasattr(summary, "session_id")
    assert not hasattr(summary, "asset_id")


def test_operation_result_and_transition_keep_operation_identity() -> None:
    agent, _ = make_prepared_agent()
    request = start_request(agent, number=94)

    result = agent.start(request)

    assert result.operation_id == operation_id(94)
    assert result.runtime_id == agent.runtime.identity.runtime_id
    assert result.transition is not None
    assert result.transition.operation_id == request.operation_id
    assert result.transition.runtime_id == result.runtime_id
    assert result.transition.configuration_id == agent.execution_configuration.id
