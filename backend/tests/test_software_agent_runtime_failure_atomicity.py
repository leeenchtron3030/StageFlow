from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime

import pytest
from runtime_fixtures import entity_id, make_runtime
from software_agent_runtime_fixtures import (
    RecordingAgentRuntimeSink,
    make_agent,
    make_dependencies,
    make_running_agent,
    prepare_request,
    resume_request,
    start_request,
    stop_request,
)

from app.contexts.production.runtime import (
    RuntimeAvailability,
    RuntimeHealth,
    RuntimePressureState,
    RuntimeProfile,
)
from app.contexts.production.software_agent_runtime import (
    AgentRuntimeOperationOutcome,
    AgentRuntimeSnapshot,
    AgentRuntimeSummary,
    AgentRuntimeTransition,
    AgentRuntimeTransitionReasonCode,
    SoftwareAgentRuntime,
)


@dataclass(slots=True)
class ReentrantReadingAgentRuntimeSink(RecordingAgentRuntimeSink):
    agent: SoftwareAgentRuntime | None = None
    views: list[
        tuple[
            AgentRuntimeSnapshot,
            tuple[AgentRuntimeTransition, ...],
            AgentRuntimeSummary,
        ]
    ] = field(
        default_factory=lambda: list[
            tuple[
                AgentRuntimeSnapshot,
                tuple[AgentRuntimeTransition, ...],
                AgentRuntimeSummary,
            ]
        ]()
    )

    def _capture_committed_view(self) -> None:
        if self.agent is not None:
            self.views.append(
                (
                    self.agent.snapshot,
                    self.agent.transition_history,
                    self.agent.summary(),
                )
            )

    def publish_transition(self, transition: AgentRuntimeTransition) -> None:
        super().publish_transition(transition)
        self._capture_committed_view()

    def publish_health(self, health: RuntimeHealth) -> None:
        super().publish_health(health)
        self._capture_committed_view()

    def publish_availability(self, availability: RuntimeAvailability) -> None:
        super().publish_availability(availability)
        self._capture_committed_view()


def _observable(
    agent: SoftwareAgentRuntime,
    sink: RecordingAgentRuntimeSink,
) -> tuple[object, ...]:
    return (
        agent.snapshot,
        agent.transition_history,
        agent.summary(),
        agent.validation_result,
        tuple(sink.publications),
    )


@pytest.mark.parametrize(
    ("request_change", "outcome"),
    [
        ({"runtime_id": entity_id(8100)}, AgentRuntimeOperationOutcome.INVALID_RUNTIME),
        (
            {"configuration_id": entity_id(8101)},
            AgentRuntimeOperationOutcome.INVALID_CONFIGURATION,
        ),
        ({"expected_lifecycle_revision": 9}, AgentRuntimeOperationOutcome.STALE_REVISION),
    ],
)
def test_prepare_rejection_families_are_observably_atomic(
    request_change: dict[str, object],
    outcome: AgentRuntimeOperationOutcome,
) -> None:
    agent, sink = make_agent()
    before = _observable(agent, sink)

    result = agent.prepare(replace(prepare_request(agent), **request_change))

    assert result.outcome is outcome
    assert result.previous_snapshot == result.current_snapshot
    assert _observable(agent, sink) == before


def test_invalid_profile_and_configuration_are_observably_atomic() -> None:
    invalid_profile, profile_sink = make_agent(profile=RuntimeProfile.NODE)
    profile_before = _observable(invalid_profile, profile_sink)
    profile_result = invalid_profile.prepare(prepare_request(invalid_profile))

    runtime = make_runtime(profile=RuntimeProfile.AGENT)
    drifted = replace(
        runtime,
        capability_set=replace(runtime.capability_set, id=entity_id(8102)),
    )
    invalid_configuration, configuration_sink = make_agent(runtime=drifted)
    configuration_before = _observable(invalid_configuration, configuration_sink)
    configuration_result = invalid_configuration.prepare(prepare_request(invalid_configuration))

    assert profile_result.outcome is AgentRuntimeOperationOutcome.INVALID_RUNTIME
    assert _observable(invalid_profile, profile_sink) == profile_before
    assert configuration_result.outcome is AgentRuntimeOperationOutcome.INVALID_CONFIGURATION
    assert _observable(invalid_configuration, configuration_sink) == configuration_before


def test_missing_dependency_and_invalid_transition_are_observably_atomic() -> None:
    dependencies, sink = make_dependencies(missing=("health",))
    missing_agent, _ = make_agent(dependencies=dependencies, sink=sink)
    missing_before = _observable(missing_agent, sink)
    missing_result = missing_agent.prepare(prepare_request(missing_agent))

    running, running_sink = make_running_agent()
    transition_before = _observable(running, running_sink)
    transition_result = running.start(start_request(running, number=82))

    assert missing_result.outcome is AgentRuntimeOperationOutcome.DEPENDENCY_FAILURE
    assert _observable(missing_agent, sink) == missing_before
    assert transition_result.outcome is AgentRuntimeOperationOutcome.INVALID_TRANSITION
    assert _observable(running, running_sink) == transition_before


def test_conflicting_replay_and_blocked_resume_are_observably_atomic() -> None:
    agent, sink = make_agent()
    original = prepare_request(agent)
    agent.prepare(original)
    conflict_before = _observable(agent, sink)

    conflict = agent.prepare(replace(original, configuration_id=entity_id(8103)))

    assert conflict.outcome is AgentRuntimeOperationOutcome.OPERATION_CONFLICT
    assert _observable(agent, sink) == conflict_before

    suspended, suspended_sink = make_running_agent(pressure=RuntimePressureState.CRITICAL)
    resume_before = _observable(suspended, suspended_sink)
    blocked = suspended.resume(resume_request(suspended, RuntimePressureState.UNKNOWN))
    assert blocked.outcome is AgentRuntimeOperationOutcome.REJECTED
    assert _observable(suspended, suspended_sink) == resume_before


def test_timezone_naive_request_failure_occurs_before_any_mutation() -> None:
    agent, sink = make_agent()
    before = _observable(agent, sink)

    with pytest.raises(ValueError, match="timezone-aware"):
        replace(prepare_request(agent), requested_at=datetime(2026, 7, 17, 10))

    assert _observable(agent, sink) == before


def test_notifications_publish_lifecycle_health_availability_in_transition_order() -> None:
    agent, sink = make_agent()

    result = agent.prepare(prepare_request(agent))

    assert result.outcome is AgentRuntimeOperationOutcome.APPLIED
    assert [kind for kind, _ in sink.publications] == [
        "lifecycle",
        "health",
        "availability",
        "lifecycle",
        "health",
        "availability",
    ]
    assert sink.publications[0][1] == result.transitions[0]
    assert sink.publications[3][1] == result.transitions[1]


def test_reentrant_read_only_sink_observes_only_fully_committed_state() -> None:
    sink = ReentrantReadingAgentRuntimeSink()
    agent, _ = make_agent(sink=sink)
    sink.agent = agent

    result = agent.prepare(prepare_request(agent))

    assert result.outcome is AgentRuntimeOperationOutcome.APPLIED
    assert len(sink.views) == 6
    for snapshot, history, summary in sink.views:
        assert snapshot == result.current_snapshot
        assert history == result.transitions
        assert summary.lifecycle_revision == 2
        assert summary.transition_count == 2
    assert agent.snapshot == result.current_snapshot
    assert agent.transition_history == result.transitions


@pytest.mark.parametrize(
    ("failures", "expected_count"),
    [
        (frozenset({"health"}), 2),
        (frozenset({"lifecycle", "availability"}), 4),
        (frozenset({"lifecycle", "health", "availability"}), 6),
    ],
)
def test_notification_failure_never_rolls_back_and_is_not_retried(
    failures: frozenset[str],
    expected_count: int,
) -> None:
    sink = RecordingAgentRuntimeSink(fail_kinds=failures)
    agent, _ = make_agent(sink=sink)
    request = prepare_request(agent)

    result = agent.prepare(request)
    committed_snapshot = agent.snapshot
    committed_history = agent.transition_history
    publication_count = len(sink.publications)
    replay = agent.prepare(request)

    assert result.outcome is (AgentRuntimeOperationOutcome.APPLIED_WITH_NOTIFICATION_FAILURE)
    assert len(result.publication_failures) == expected_count
    assert all(failure.lifecycle_transition_committed for failure in result.publication_failures)
    assert AgentRuntimeTransitionReasonCode.DEPENDENCY_PUBLICATION_FAILURE in (result.reasons)
    assert agent.snapshot == committed_snapshot
    assert agent.transition_history == committed_history
    assert replay.outcome is AgentRuntimeOperationOutcome.ALREADY_APPLIED
    assert replay.publication_failures == result.publication_failures
    assert len(sink.publications) == publication_count

    later = agent.start(start_request(agent, number=83, revision=2))
    assert later.outcome is (AgentRuntimeOperationOutcome.APPLIED_WITH_NOTIFICATION_FAILURE)
    assert agent.snapshot.lifecycle_state.value == "running"
    assert agent.snapshot.lifecycle_revision == 3


def test_stop_commit_survives_notification_failure() -> None:
    sink = RecordingAgentRuntimeSink(fail_kinds=frozenset({"lifecycle"}))
    agent, _ = make_running_agent(sink=sink)

    result = agent.stop(stop_request(agent))

    assert result.outcome is AgentRuntimeOperationOutcome.APPLIED_WITH_NOTIFICATION_FAILURE
    assert agent.snapshot.lifecycle_state.value == "stopped"
    assert len(result.transitions) == 2
    assert len(result.publication_failures) == 2
