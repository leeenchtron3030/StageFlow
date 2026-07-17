from __future__ import annotations

from dataclasses import replace
from threading import Event, Thread

from media_collection_fixtures import (
    RecordingDiscoveryPort,
    make_candidate,
    make_coordinator,
    make_cycle_request,
)

from app.contexts.production.media_collection import MediaCollectionCycleOutcome
from app.contexts.production.runtime import RuntimeProfile, RuntimeReadinessRoute
from app.contexts.production.software_agent_runtime import (
    AgentRuntimeExecutionPermission,
    AgentRuntimeLifecycleState,
)


def test_essential_only_permission_denies_without_media_port_call() -> None:
    coordinator, agent_port, discovery, observations = make_coordinator()
    agent_port.snapshots[0] = replace(
        agent_port.snapshots[0],
        execution_permission=AgentRuntimeExecutionPermission.ESSENTIAL_ONLY,
    )

    result = coordinator.run_cycle(make_cycle_request())

    assert result.outcome is MediaCollectionCycleOutcome.PERMISSION_DENIED
    assert discovery.calls == []
    assert observations.calls == []
    assert coordinator.snapshot.coordinator_revision == 0
    assert coordinator.list_cycle_history().cycle_history == ()


def test_reduced_permission_requires_request_opt_in() -> None:
    coordinator, agent_port, discovery, _ = make_coordinator()
    reduced = replace(
        agent_port.snapshots[0],
        lifecycle_state=AgentRuntimeLifecycleState.YIELDING,
        execution_permission=AgentRuntimeExecutionPermission.REDUCED,
    )
    agent_port.snapshots[:] = [reduced]

    denied = coordinator.run_cycle(make_cycle_request(permit_reduced=False))

    assert denied.outcome is MediaCollectionCycleOutcome.PERMISSION_DENIED
    assert discovery.calls == []


def test_reduced_permission_runs_required_and_defers_optional_calls() -> None:
    coordinator, agent_port, _, observations = make_coordinator(
        candidates=(make_candidate(),),
        route=RuntimeReadinessRoute.STRONG_FINALIZATION,
    )
    reduced = replace(
        agent_port.snapshots[0],
        lifecycle_state=AgentRuntimeLifecycleState.YIELDING,
        execution_permission=AgentRuntimeExecutionPermission.REDUCED,
    )
    agent_port.snapshots[:] = [reduced]

    result = coordinator.run_cycle(make_cycle_request())

    assert result.outcome is MediaCollectionCycleOutcome.COMPLETED_WITH_PARTIAL_RESULTS
    assert all(request.required for request in observations.calls)
    assert len(observations.calls) == 2
    assert len(result.observation_collection_results) == 5
    assert (
        sum(item.outcome.value == "deferred" for item in result.observation_collection_results) == 3
    )


def test_permission_revocation_mid_cycle_retains_discovery_and_stops_media_calls() -> None:
    coordinator, agent_port, discovery, observations = make_coordinator(
        candidates=(make_candidate(),)
    )
    normal = agent_port.snapshots[0]
    stopped = replace(
        normal,
        lifecycle_state=AgentRuntimeLifecycleState.STOPPED,
        execution_permission=AgentRuntimeExecutionPermission.NONE,
    )
    agent_port.snapshots[:] = [normal, normal, normal, stopped]

    result = coordinator.run_cycle(make_cycle_request())

    assert result.outcome is MediaCollectionCycleOutcome.INTERRUPTED
    assert len(discovery.calls) == 1
    assert observations.calls == []
    assert len(result.newly_discovered_candidate_ids) == 1
    assert result.final_agent_snapshot is not None
    assert result.final_agent_snapshot.lifecycle_state is AgentRuntimeLifecycleState.STOPPED
    assert coordinator.snapshot.coordinator_revision == 1


def test_exact_completed_replay_returns_original_times_without_ports_or_revision() -> None:
    coordinator, agent, discovery, observations = make_coordinator(candidates=(make_candidate(),))
    request = make_cycle_request()
    original = coordinator.run_cycle(request)
    counts = (len(agent.calls), len(discovery.calls), len(observations.calls))

    replay = coordinator.run_cycle(request)

    assert replay.outcome is MediaCollectionCycleOutcome.ALREADY_APPLIED
    assert replay.started_at == original.started_at
    assert replay.completed_at == original.completed_at
    assert replay.current_coordinator_snapshot == original.current_coordinator_snapshot
    assert (len(agent.calls), len(discovery.calls), len(observations.calls)) == counts
    assert coordinator.snapshot.coordinator_revision == 1
    assert len(coordinator.list_cycle_history().cycle_history) == 1


def test_conflicting_replay_and_stale_revision_do_not_invoke_ports() -> None:
    coordinator, agent, discovery, observations = make_coordinator(candidates=(make_candidate(),))
    request = make_cycle_request()
    coordinator.run_cycle(request)
    counts = (len(agent.calls), len(discovery.calls), len(observations.calls))

    conflict = coordinator.run_cycle(replace(request, maximum_total_candidates=9))
    stale = coordinator.run_cycle(make_cycle_request(number=2, revision=0))

    assert conflict.outcome is MediaCollectionCycleOutcome.OPERATION_CONFLICT
    assert stale.outcome is MediaCollectionCycleOutcome.STALE_REVISION
    assert (len(agent.calls), len(discovery.calls), len(observations.calls)) == counts
    assert coordinator.snapshot.coordinator_revision == 1


def test_slow_port_does_not_hold_coordinator_lock_and_competing_cycle_is_rejected() -> None:
    entered = Event()
    release = Event()
    discovery = RecordingDiscoveryPort(
        (make_candidate(),),
        entered=entered,
        release=release,
    )
    coordinator, _, _, _ = make_coordinator(discovery=discovery)
    results: list[object] = []

    request = make_cycle_request()
    thread = Thread(
        target=lambda: results.append(coordinator.run_cycle(request)),
        daemon=True,
    )
    thread.start()
    assert entered.wait(timeout=2)

    assert coordinator.snapshot.active_cycle_id is not None
    assert coordinator.list_candidates().candidates == ()
    active_replay = coordinator.run_cycle(request)
    assert active_replay.outcome is MediaCollectionCycleOutcome.CYCLE_IN_PROGRESS
    active_conflict = coordinator.run_cycle(replace(request, maximum_total_candidates=9))
    assert active_conflict.outcome is MediaCollectionCycleOutcome.OPERATION_CONFLICT
    competing = coordinator.run_cycle(make_cycle_request(number=2))
    assert competing.outcome is MediaCollectionCycleOutcome.CYCLE_IN_PROGRESS

    release.set()
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert len(results) == 1


def test_development_profile_requires_explicit_constructor_permission() -> None:
    denied, _, discovery, _ = make_coordinator(profile=RuntimeProfile.DEVELOPMENT)
    denied_result = denied.run_cycle(make_cycle_request())
    assert denied_result.outcome is MediaCollectionCycleOutcome.INVALID_RUNTIME
    assert discovery.calls == []

    allowed, _, _, _ = make_coordinator(
        profile=RuntimeProfile.DEVELOPMENT,
        allow_development=True,
    )
    allowed_result = allowed.run_cycle(make_cycle_request())
    assert allowed_result.outcome is MediaCollectionCycleOutcome.NO_CANDIDATES
