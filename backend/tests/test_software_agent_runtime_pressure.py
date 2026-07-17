from __future__ import annotations

from dataclasses import replace

import pytest
from software_agent_runtime_fixtures import (
    PRESSURE_AT,
    RESUMED_AT,
    make_prepared_agent,
    make_running_agent,
    pressure_update,
    resume_request,
    start_request,
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
    AgentRuntimePressureDeclaration,
    AgentRuntimePressureUpdate,
    AgentRuntimeTransitionReasonCode,
)


@pytest.mark.parametrize(
    ("pressure", "state"),
    [
        (RuntimePressureState.NORMAL, AgentRuntimeLifecycleState.RUNNING),
        (RuntimePressureState.ELEVATED, AgentRuntimeLifecycleState.YIELDING),
        (RuntimePressureState.CRITICAL, AgentRuntimeLifecycleState.SUSPENDED),
        (
            RuntimePressureState.RECORDING_SAFETY_UNCERTAIN,
            AgentRuntimeLifecycleState.SUSPENDED,
        ),
        (RuntimePressureState.UNKNOWN, AgentRuntimeLifecycleState.SUSPENDED),
    ],
)
def test_all_approved_initial_pressure_values_map_conservatively(
    pressure: RuntimePressureState,
    state: AgentRuntimeLifecycleState,
) -> None:
    agent, _ = make_prepared_agent()

    result = agent.start(start_request(agent, pressure=pressure))

    assert result.current_snapshot.lifecycle_state is state
    assert result.current_snapshot.latest_pressure is not None
    assert result.current_snapshot.latest_pressure.pressure_state is pressure


def test_elevated_pressure_yields_and_derives_reduced_degraded_limited_state() -> None:
    agent, _ = make_running_agent()

    result = agent.update_pressure(pressure_update(agent, RuntimePressureState.ELEVATED))

    assert result.current_snapshot.lifecycle_state is AgentRuntimeLifecycleState.YIELDING
    assert result.current_snapshot.execution_permission is AgentRuntimeExecutionPermission.REDUCED
    assert result.current_snapshot.health.status is RuntimeHealthStatus.DEGRADED
    assert result.current_snapshot.availability.status is RuntimeAvailabilityStatus.LIMITED
    assert result.current_snapshot.health.assessed_at == PRESSURE_AT
    assert result.current_snapshot.availability.declared_at == PRESSURE_AT


@pytest.mark.parametrize(
    "pressure",
    [
        RuntimePressureState.CRITICAL,
        RuntimePressureState.RECORDING_SAFETY_UNCERTAIN,
        RuntimePressureState.UNKNOWN,
    ],
)
def test_unsafe_or_unknown_pressure_suspends_and_revokes_permission(
    pressure: RuntimePressureState,
) -> None:
    agent, _ = make_running_agent()

    result = agent.update_pressure(pressure_update(agent, pressure))

    assert result.current_snapshot.lifecycle_state is AgentRuntimeLifecycleState.SUSPENDED
    assert result.current_snapshot.execution_permission is AgentRuntimeExecutionPermission.NONE
    assert result.current_snapshot.health.status is RuntimeHealthStatus.DEGRADED
    assert result.current_snapshot.availability.status is RuntimeAvailabilityStatus.UNAVAILABLE
    assert AgentRuntimeTransitionReasonCode.EXPLICIT_RESUME_REQUIRED in result.reasons


def test_favorable_pressure_never_automatically_resumes_suspended_agent() -> None:
    agent, _ = make_running_agent(pressure=RuntimePressureState.CRITICAL)

    result = agent.update_pressure(pressure_update(agent, RuntimePressureState.NORMAL))

    assert result.current_snapshot.lifecycle_state is AgentRuntimeLifecycleState.SUSPENDED
    assert result.current_snapshot.execution_permission is AgentRuntimeExecutionPermission.NONE
    assert result.current_snapshot.latest_pressure is not None
    assert result.current_snapshot.latest_pressure.pressure_state is RuntimePressureState.NORMAL


@pytest.mark.parametrize(
    ("initial", "current", "expected"),
    [
        (
            RuntimePressureState.CRITICAL,
            RuntimePressureState.NORMAL,
            AgentRuntimeLifecycleState.RUNNING,
        ),
        (
            RuntimePressureState.CRITICAL,
            RuntimePressureState.ELEVATED,
            AgentRuntimeLifecycleState.YIELDING,
        ),
        (
            RuntimePressureState.ELEVATED,
            RuntimePressureState.NORMAL,
            AgentRuntimeLifecycleState.RUNNING,
        ),
    ],
)
def test_explicit_resume_maps_permitted_pressure(
    initial: RuntimePressureState,
    current: RuntimePressureState,
    expected: AgentRuntimeLifecycleState,
) -> None:
    agent, _ = make_running_agent(pressure=initial)

    result = agent.resume(resume_request(agent, current))

    assert result.outcome is AgentRuntimeOperationOutcome.APPLIED
    assert result.current_snapshot.lifecycle_state is expected
    assert result.current_snapshot.state_entered_at == RESUMED_AT
    assert AgentRuntimeTransitionReasonCode.RESUME_ACCEPTED in result.reasons


@pytest.mark.parametrize(
    "pressure",
    [
        RuntimePressureState.CRITICAL,
        RuntimePressureState.RECORDING_SAFETY_UNCERTAIN,
        RuntimePressureState.UNKNOWN,
    ],
)
def test_explicit_resume_is_blocked_by_unsafe_pressure(
    pressure: RuntimePressureState,
) -> None:
    agent, _ = make_running_agent(pressure=RuntimePressureState.CRITICAL)
    before = agent.snapshot

    result = agent.resume(resume_request(agent, pressure))

    assert result.outcome is AgentRuntimeOperationOutcome.REJECTED
    assert result.previous_snapshot == before == result.current_snapshot
    assert agent.snapshot == before
    assert AgentRuntimeTransitionReasonCode.RESUME_BLOCKED_BY_PRESSURE in result.reasons


def test_yielding_does_not_auto_promote_on_normal_update() -> None:
    agent, _ = make_running_agent(pressure=RuntimePressureState.ELEVATED)

    update = agent.update_pressure(pressure_update(agent, RuntimePressureState.NORMAL))

    assert update.current_snapshot.lifecycle_state is AgentRuntimeLifecycleState.YIELDING
    resumed = agent.resume(resume_request(agent, RuntimePressureState.NORMAL))
    assert resumed.current_snapshot.lifecycle_state is AgentRuntimeLifecycleState.RUNNING


def test_pressure_exact_replay_is_idempotent_and_conflict_is_distinct() -> None:
    agent, _ = make_running_agent()
    request = pressure_update(agent, RuntimePressureState.ELEVATED)
    first = agent.update_pressure(request)
    history = agent.transition_history

    replay = agent.update_pressure(request)
    conflict = agent.update_pressure(replace(request, pressure_state=RuntimePressureState.CRITICAL))

    assert replay.outcome is AgentRuntimeOperationOutcome.ALREADY_APPLIED
    assert replay.current_snapshot == first.current_snapshot
    assert conflict.outcome is AgentRuntimeOperationOutcome.OPERATION_CONFLICT
    assert agent.transition_history == history


def test_resume_stale_revision_is_non_mutating_and_exact_replay_is_idempotent() -> None:
    agent, _ = make_running_agent(pressure=RuntimePressureState.CRITICAL)
    stale = agent.resume(resume_request(agent, RuntimePressureState.NORMAL, revision=2, number=80))

    assert stale.outcome is AgentRuntimeOperationOutcome.STALE_REVISION
    request = resume_request(agent, RuntimePressureState.NORMAL, number=81)
    first = agent.resume(request)
    replay = agent.resume(request)
    assert first.outcome is AgentRuntimeOperationOutcome.APPLIED
    assert replay.outcome is AgentRuntimeOperationOutcome.ALREADY_APPLIED
    assert replay.current_snapshot == first.current_snapshot


def test_invalid_pressure_contracts_fail_before_lifecycle_mutation() -> None:
    agent, _ = make_running_agent()
    before = agent.snapshot

    with pytest.raises(ValueError, match="approved RuntimePressureState"):
        replace(pressure_update(agent, RuntimePressureState.NORMAL), pressure_state="bad")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="approved RuntimePressureState"):
        replace(agent.snapshot.latest_pressure, pressure_state="bad")  # type: ignore[arg-type]

    assert agent.snapshot == before


def test_pressure_contracts_keep_explicit_aware_timestamps() -> None:
    agent, _ = make_running_agent()
    update: AgentRuntimePressureUpdate = pressure_update(
        agent,
        RuntimePressureState.ELEVATED,
    )
    declaration: AgentRuntimePressureDeclaration = update.to_declaration()

    assert declaration.assessed_at == PRESSURE_AT
    assert declaration.assessed_at.tzinfo is not None


def test_same_state_pressure_update_records_one_revision_and_one_notification_set() -> None:
    agent, sink = make_running_agent()
    before_revision = agent.snapshot.lifecycle_revision
    before_publications = len(sink.publications)
    request = pressure_update(
        agent,
        RuntimePressureState.NORMAL,
        number=84,
        revision=before_revision,
    )

    result = agent.update_pressure(request)

    assert result.outcome is AgentRuntimeOperationOutcome.APPLIED
    assert result.current_snapshot.lifecycle_revision == before_revision + 1
    assert len(result.transitions) == 1
    assert result.transition is not None
    assert result.transition.previous_state is AgentRuntimeLifecycleState.RUNNING
    assert result.transition.next_state is AgentRuntimeLifecycleState.RUNNING
    assert [kind for kind, _ in sink.publications[before_publications:]] == [
        "lifecycle",
        "health",
        "availability",
    ]

    replay = agent.update_pressure(request)
    assert replay.outcome is AgentRuntimeOperationOutcome.ALREADY_APPLIED
    assert len(sink.publications) == before_publications + 3
    assert agent.snapshot.lifecycle_revision == before_revision + 1

    stale = agent.update_pressure(
        pressure_update(
            agent,
            RuntimePressureState.ELEVATED,
            number=85,
            revision=before_revision,
        )
    )
    assert stale.outcome is AgentRuntimeOperationOutcome.STALE_REVISION
    assert len(sink.publications) == before_publications + 3
    assert agent.snapshot.latest_pressure == result.current_snapshot.latest_pressure
