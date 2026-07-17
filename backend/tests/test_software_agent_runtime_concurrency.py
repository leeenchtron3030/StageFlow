from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from threading import Barrier, Event, Lock, Thread

from software_agent_runtime_fixtures import (
    RecordingAgentRuntimeSink,
    cancellation_request,
    make_agent,
    make_prepared_agent,
    make_running_agent,
    prepare_request,
    pressure_update,
    resume_request,
    start_request,
    stop_request,
)

from app.contexts.production.runtime import RuntimePressureState
from app.contexts.production.software_agent_runtime import (
    AgentRuntimeExecutionPermission,
    AgentRuntimeLifecycleState,
    AgentRuntimeOperationOutcome,
    AgentRuntimeOperationResult,
    AgentRuntimeTransition,
)


@dataclass(slots=True)
class ControlledBlockingAgentRuntimeSink(RecordingAgentRuntimeSink):
    block_state: AgentRuntimeLifecycleState = AgentRuntimeLifecycleState.VALIDATED
    entered: Event = field(default_factory=Event)
    release: Event = field(default_factory=Event)
    armed: bool = True
    blocked: bool = False

    def publish_transition(self, transition: AgentRuntimeTransition) -> None:
        super().publish_transition(transition)
        if self.armed and not self.blocked and transition.next_state is self.block_state:
            self.blocked = True
            self.entered.set()
            if not self.release.wait(timeout=5):
                raise RuntimeError("controlled notification release was not supplied")


def _race(
    first: Callable[[], AgentRuntimeOperationResult],
    second: Callable[[], AgentRuntimeOperationResult],
) -> tuple[AgentRuntimeOperationResult, AgentRuntimeOperationResult]:
    barrier = Barrier(3)
    result_lock = Lock()
    results: list[AgentRuntimeOperationResult] = []

    def invoke(operation: Callable[[], AgentRuntimeOperationResult]) -> None:
        barrier.wait()
        result = operation()
        with result_lock:
            results.append(result)

    threads = (Thread(target=invoke, args=(first,)), Thread(target=invoke, args=(second,)))
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()
    assert len(results) == 2
    return results[0], results[1]


def test_simultaneous_starts_have_one_authoritative_transition() -> None:
    agent, _ = make_prepared_agent()
    revision = agent.snapshot.lifecycle_revision
    first_request = start_request(agent, number=31, revision=revision)
    second_request = start_request(agent, number=32, revision=revision)

    results = _race(
        lambda: agent.start(first_request),
        lambda: agent.start(second_request),
    )

    assert {result.outcome for result in results} == {
        AgentRuntimeOperationOutcome.APPLIED,
        AgentRuntimeOperationOutcome.STALE_REVISION,
    }
    assert agent.snapshot.lifecycle_state is AgentRuntimeLifecycleState.RUNNING
    assert agent.snapshot.lifecycle_revision == revision + 1
    assert (
        sum(
            transition.next_state is AgentRuntimeLifecycleState.RUNNING
            for transition in agent.transition_history
        )
        == 1
    )


def test_start_after_committed_stop_cannot_restart_instance() -> None:
    agent, _ = make_prepared_agent()
    revision = agent.snapshot.lifecycle_revision
    stop_done = Event()
    results: list[AgentRuntimeOperationResult] = []

    def commit_stop() -> None:
        results.append(agent.stop(stop_request(agent, number=33, revision=revision)))
        stop_done.set()

    def attempt_start() -> None:
        stop_done.wait()
        results.append(agent.start(start_request(agent, number=34, revision=revision)))

    threads = (Thread(target=commit_stop), Thread(target=attempt_start))
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert [result.outcome for result in results] == [
        AgentRuntimeOperationOutcome.APPLIED,
        AgentRuntimeOperationOutcome.STALE_REVISION,
    ]
    assert agent.snapshot.lifecycle_state is AgentRuntimeLifecycleState.STOPPED
    assert all(
        transition.next_state is not AgentRuntimeLifecycleState.RUNNING
        for transition in agent.transition_history[2:]
    )


def test_simultaneous_pressure_updates_cannot_overwrite_each_other() -> None:
    agent, _ = make_running_agent()
    revision = agent.snapshot.lifecycle_revision
    elevated = pressure_update(
        agent,
        RuntimePressureState.ELEVATED,
        number=35,
        revision=revision,
    )
    critical = pressure_update(
        agent,
        RuntimePressureState.CRITICAL,
        number=36,
        revision=revision,
    )

    results = _race(
        lambda: agent.update_pressure(elevated),
        lambda: agent.update_pressure(critical),
    )

    assert {result.outcome for result in results} == {
        AgentRuntimeOperationOutcome.APPLIED,
        AgentRuntimeOperationOutcome.STALE_REVISION,
    }
    assert agent.snapshot.lifecycle_revision == revision + 1
    applied = next(
        result for result in results if result.outcome is AgentRuntimeOperationOutcome.APPLIED
    )
    assert agent.snapshot == applied.current_snapshot


def test_pressure_versus_resume_commits_one_revision_order() -> None:
    agent, _ = make_running_agent(pressure=RuntimePressureState.CRITICAL)
    revision = agent.snapshot.lifecycle_revision
    update = pressure_update(
        agent,
        RuntimePressureState.NORMAL,
        number=37,
        revision=revision,
    )
    resume = resume_request(
        agent,
        RuntimePressureState.NORMAL,
        number=38,
        revision=revision,
    )

    results = _race(
        lambda: agent.update_pressure(update),
        lambda: agent.resume(resume),
    )

    assert {result.outcome for result in results} == {
        AgentRuntimeOperationOutcome.APPLIED,
        AgentRuntimeOperationOutcome.STALE_REVISION,
    }
    assert agent.snapshot.lifecycle_revision == revision + 1
    assert agent.snapshot.lifecycle_state in (
        AgentRuntimeLifecycleState.SUSPENDED,
        AgentRuntimeLifecycleState.RUNNING,
    )


def test_cancellation_versus_pressure_has_one_order_and_cancellation_blocks_later_work() -> None:
    agent, _ = make_running_agent()
    revision = agent.snapshot.lifecycle_revision
    cancellation = cancellation_request(agent, number=39, revision=revision)
    pressure = pressure_update(
        agent,
        RuntimePressureState.ELEVATED,
        number=40,
        revision=revision,
    )

    results = _race(
        lambda: agent.cancel(cancellation),
        lambda: agent.update_pressure(pressure),
    )

    assert {result.outcome for result in results} == {
        AgentRuntimeOperationOutcome.APPLIED,
        AgentRuntimeOperationOutcome.STALE_REVISION,
    }
    if agent.snapshot.lifecycle_state is not AgentRuntimeLifecycleState.STOPPED:
        follow_up = agent.cancel(cancellation_request(agent, number=41))
        assert follow_up.outcome is AgentRuntimeOperationOutcome.APPLIED
    assert agent.snapshot.lifecycle_state is AgentRuntimeLifecycleState.STOPPED
    assert agent.snapshot.execution_permission is AgentRuntimeExecutionPermission.NONE


def test_duplicate_stop_race_is_applied_once_and_exactly_replayed() -> None:
    agent, _ = make_running_agent()
    request = stop_request(agent, number=42)
    before_count = len(agent.transition_history)

    results = _race(lambda: agent.stop(request), lambda: agent.stop(request))

    assert {result.outcome for result in results} == {
        AgentRuntimeOperationOutcome.APPLIED,
        AgentRuntimeOperationOutcome.ALREADY_APPLIED,
    }
    assert agent.snapshot.lifecycle_state is AgentRuntimeLifecycleState.STOPPED
    assert len(agent.transition_history) == before_count + 2


def test_slow_sink_does_not_hold_lifecycle_lock_and_pending_replay_is_deterministic() -> None:
    sink = ControlledBlockingAgentRuntimeSink()
    agent, _ = make_agent(sink=sink)
    prepare = prepare_request(agent, number=43, revision=0)
    prepare_results: list[AgentRuntimeOperationResult] = []
    replay_results: list[AgentRuntimeOperationResult] = []
    start_results: list[AgentRuntimeOperationResult] = []
    replay_done = Event()
    start_done = Event()

    prepare_thread = Thread(target=lambda: prepare_results.append(agent.prepare(prepare)))

    def replay_prepare() -> None:
        replay_results.append(agent.prepare(prepare))
        replay_done.set()

    start = start_request(agent, number=44, revision=2)

    def start_agent() -> None:
        start_results.append(agent.start(start))
        start_done.set()

    prepare_thread.start()
    assert sink.entered.wait(timeout=2)
    assert agent.snapshot.lifecycle_state is AgentRuntimeLifecycleState.READY
    assert agent.snapshot.lifecycle_revision == 2

    replay_thread = Thread(target=replay_prepare)
    start_thread = Thread(target=start_agent)
    replay_thread.start()
    start_thread.start()

    assert start_done.wait(timeout=2)
    assert not replay_done.is_set()
    assert agent.snapshot.lifecycle_state is AgentRuntimeLifecycleState.RUNNING
    assert agent.snapshot.lifecycle_revision == 3

    sink.release.set()
    for thread in (prepare_thread, replay_thread, start_thread):
        thread.join(timeout=2)
        assert not thread.is_alive()

    assert prepare_results[0].outcome is AgentRuntimeOperationOutcome.APPLIED
    assert replay_results[0].outcome is AgentRuntimeOperationOutcome.ALREADY_APPLIED
    assert replay_results[0].current_snapshot == prepare_results[0].current_snapshot
    assert start_results[0].outcome is AgentRuntimeOperationOutcome.APPLIED


def test_stop_commits_while_running_notification_is_blocked() -> None:
    sink = ControlledBlockingAgentRuntimeSink(
        block_state=AgentRuntimeLifecycleState.RUNNING,
        armed=False,
    )
    agent, _ = make_prepared_agent(sink=sink)
    sink.armed = True
    start_results: list[AgentRuntimeOperationResult] = []
    stop_results: list[AgentRuntimeOperationResult] = []
    stop_done = Event()

    start_thread = Thread(
        target=lambda: start_results.append(
            agent.start(start_request(agent, number=45, revision=2))
        )
    )

    def stop_agent() -> None:
        stop_results.append(agent.stop(stop_request(agent, number=46, revision=3)))
        stop_done.set()

    start_thread.start()
    assert sink.entered.wait(timeout=2)
    original_running_transition = next(
        value
        for kind, value in sink.publications
        if kind == "lifecycle"
        and isinstance(value, AgentRuntimeTransition)
        and value.next_state is AgentRuntimeLifecycleState.RUNNING
    )

    stop_thread = Thread(target=stop_agent)
    stop_thread.start()
    assert stop_done.wait(timeout=2)
    assert agent.snapshot.lifecycle_state is AgentRuntimeLifecycleState.STOPPED
    assert agent.snapshot.lifecycle_revision == 5
    assert original_running_transition.next_state is AgentRuntimeLifecycleState.RUNNING
    assert original_running_transition.lifecycle_revision == 3

    sink.release.set()
    for thread in (start_thread, stop_thread):
        thread.join(timeout=2)
        assert not thread.is_alive()

    assert start_results[0].outcome is AgentRuntimeOperationOutcome.APPLIED
    assert stop_results[0].outcome is AgentRuntimeOperationOutcome.APPLIED
    assert [transition.lifecycle_revision for transition in agent.transition_history] == [
        1,
        2,
        3,
        4,
        5,
    ]
