from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from runtime_fixtures import CONFIGURED_AT, entity_id, make_runtime

from app.contexts.production.runtime import (
    RuntimeAvailability,
    RuntimeEventModeKind,
    RuntimeHealth,
    RuntimePressureState,
    RuntimeProfile,
    StageFlowRuntime,
)
from app.contexts.production.software_agent_runtime import (
    AgentRuntimeCancellation,
    AgentRuntimeDependencies,
    AgentRuntimeFailure,
    AgentRuntimePrepareRequest,
    AgentRuntimePressureDeclaration,
    AgentRuntimePressureUpdate,
    AgentRuntimeResumeRequest,
    AgentRuntimeStartRequest,
    AgentRuntimeStopRequest,
    AgentRuntimeTransition,
    LifecycleEventSink,
    RuntimeAvailabilitySink,
    RuntimeHealthSink,
    SoftwareAgentRuntime,
)
from app.shared.ids import EntityId

CREATED_AT = CONFIGURED_AT + timedelta(minutes=1)
PREPARED_AT = CREATED_AT + timedelta(seconds=1)
STARTED_AT = CREATED_AT + timedelta(seconds=2)
PRESSURE_AT = CREATED_AT + timedelta(seconds=3)
RESUMED_AT = CREATED_AT + timedelta(seconds=4)
STOPPED_AT = CREATED_AT + timedelta(seconds=5)
AGENT_INSTANCE_ID = entity_id(2000)
PRESSURE_SOURCE_ID = entity_id(2001)
OPERATOR_ID = entity_id(2002)


@dataclass(slots=True)
class RecordingAgentRuntimeSink(
    LifecycleEventSink,
    RuntimeHealthSink,
    RuntimeAvailabilitySink,
):
    fail_kinds: frozenset[str] = field(default_factory=lambda: frozenset[str]())
    publications: list[tuple[str, object]] = field(
        default_factory=lambda: list[tuple[str, object]]()
    )

    def publish_transition(self, transition: AgentRuntimeTransition) -> None:
        self.publications.append(("lifecycle", transition))
        if "lifecycle" in self.fail_kinds:
            raise RuntimeError("synthetic lifecycle publication failure")

    def publish_health(self, health: RuntimeHealth) -> None:
        self.publications.append(("health", health))
        if "health" in self.fail_kinds:
            raise RuntimeError("synthetic health publication failure")

    def publish_availability(self, availability: RuntimeAvailability) -> None:
        self.publications.append(("availability", availability))
        if "availability" in self.fail_kinds:
            raise RuntimeError("synthetic availability publication failure")


def operation_id(number: int) -> EntityId:
    return entity_id(3000 + number)


def make_pressure(
    state: RuntimePressureState = RuntimePressureState.NORMAL,
    *,
    assessed_at: datetime = STARTED_AT,
    reason_codes: Sequence[str] = ("synthetic_pressure",),
) -> AgentRuntimePressureDeclaration:
    return AgentRuntimePressureDeclaration(
        pressure_state=state,
        assessed_at=assessed_at,
        source_id=PRESSURE_SOURCE_ID,
        reason_codes=reason_codes,
    )


def make_dependencies(
    sink: RecordingAgentRuntimeSink | None = None,
    *,
    missing: Sequence[str] = (),
) -> tuple[AgentRuntimeDependencies, RecordingAgentRuntimeSink]:
    resolved_sink = RecordingAgentRuntimeSink() if sink is None else sink
    return (
        AgentRuntimeDependencies(
            lifecycle_event_sink=(None if "lifecycle" in missing else resolved_sink),
            runtime_health_sink=None if "health" in missing else resolved_sink,
            runtime_availability_sink=(None if "availability" in missing else resolved_sink),
        ),
        resolved_sink,
    )


def make_agent(
    *,
    runtime: StageFlowRuntime | None = None,
    profile: RuntimeProfile = RuntimeProfile.AGENT,
    mode: RuntimeEventModeKind = RuntimeEventModeKind.EVENT,
    dependencies: AgentRuntimeDependencies | None = None,
    sink: RecordingAgentRuntimeSink | None = None,
    agent_instance_id: EntityId = AGENT_INSTANCE_ID,
) -> tuple[SoftwareAgentRuntime, RecordingAgentRuntimeSink]:
    if dependencies is None:
        dependencies, resolved_sink = make_dependencies(sink)
    else:
        resolved_sink = RecordingAgentRuntimeSink() if sink is None else sink
    resolved_runtime = make_runtime(profile=profile, mode=mode) if runtime is None else runtime
    return (
        SoftwareAgentRuntime(
            resolved_runtime,
            dependencies,
            agent_instance_id=agent_instance_id,
            created_at=CREATED_AT,
        ),
        resolved_sink,
    )


def prepare_request(
    agent: SoftwareAgentRuntime,
    *,
    number: int = 1,
    revision: int | None = None,
    allow_development: bool = False,
) -> AgentRuntimePrepareRequest:
    return AgentRuntimePrepareRequest(
        operation_id=operation_id(number),
        runtime_id=agent.runtime.identity.runtime_id,
        configuration_id=agent.runtime.configuration.id,
        expected_lifecycle_revision=(
            agent.snapshot.lifecycle_revision if revision is None else revision
        ),
        requested_at=PREPARED_AT,
        allow_development_profile=allow_development,
    )


def start_request(
    agent: SoftwareAgentRuntime,
    *,
    number: int = 2,
    revision: int | None = None,
    pressure: RuntimePressureState = RuntimePressureState.NORMAL,
    allow_development: bool = False,
) -> AgentRuntimeStartRequest:
    return AgentRuntimeStartRequest(
        operation_id=operation_id(number),
        runtime_id=agent.runtime.identity.runtime_id,
        configuration_id=agent.runtime.configuration.id,
        expected_lifecycle_revision=(
            agent.snapshot.lifecycle_revision if revision is None else revision
        ),
        requested_at=STARTED_AT,
        initial_pressure=make_pressure(pressure),
        allow_development_profile=allow_development,
    )


def pressure_update(
    agent: SoftwareAgentRuntime,
    state: RuntimePressureState,
    *,
    number: int = 3,
    revision: int | None = None,
) -> AgentRuntimePressureUpdate:
    return AgentRuntimePressureUpdate(
        operation_id=operation_id(number),
        runtime_id=agent.runtime.identity.runtime_id,
        expected_lifecycle_revision=(
            agent.snapshot.lifecycle_revision if revision is None else revision
        ),
        pressure_state=state,
        assessed_at=PRESSURE_AT,
        source_id=PRESSURE_SOURCE_ID,
        reason_codes=("synthetic_pressure_update",),
    )


def resume_request(
    agent: SoftwareAgentRuntime,
    state: RuntimePressureState,
    *,
    number: int = 4,
    revision: int | None = None,
) -> AgentRuntimeResumeRequest:
    return AgentRuntimeResumeRequest(
        operation_id=operation_id(number),
        runtime_id=agent.runtime.identity.runtime_id,
        expected_lifecycle_revision=(
            agent.snapshot.lifecycle_revision if revision is None else revision
        ),
        requested_at=RESUMED_AT,
        current_pressure=make_pressure(state, assessed_at=RESUMED_AT),
        resume_reason="synthetic explicit resume",
        requested_by_id=OPERATOR_ID,
    )


def stop_request(
    agent: SoftwareAgentRuntime,
    *,
    number: int = 5,
    revision: int | None = None,
) -> AgentRuntimeStopRequest:
    return AgentRuntimeStopRequest(
        operation_id=operation_id(number),
        runtime_id=agent.runtime.identity.runtime_id,
        expected_lifecycle_revision=(
            agent.snapshot.lifecycle_revision if revision is None else revision
        ),
        requested_at=STOPPED_AT,
        stop_reason="synthetic graceful stop",
        graceful=True,
        requested_by_id=OPERATOR_ID,
    )


def cancellation_request(
    agent: SoftwareAgentRuntime,
    *,
    number: int = 6,
    revision: int | None = None,
    cancellation_id: EntityId | None = None,
) -> AgentRuntimeCancellation:
    return AgentRuntimeCancellation(
        cancellation_id=(entity_id(4000 + number) if cancellation_id is None else cancellation_id),
        operation_id=operation_id(number),
        runtime_id=agent.runtime.identity.runtime_id,
        expected_lifecycle_revision=(
            agent.snapshot.lifecycle_revision if revision is None else revision
        ),
        requested_at=STOPPED_AT,
        cancellation_reason="synthetic cancellation",
        graceful_shutdown_required=True,
        requested_by_id=OPERATOR_ID,
    )


def failure_request(
    agent: SoftwareAgentRuntime,
    *,
    number: int = 7,
    revision: int | None = None,
) -> AgentRuntimeFailure:
    return AgentRuntimeFailure(
        failure_id=entity_id(5000 + number),
        operation_id=operation_id(number),
        runtime_id=agent.runtime.identity.runtime_id,
        expected_lifecycle_revision=(
            agent.snapshot.lifecycle_revision if revision is None else revision
        ),
        occurred_at=PRESSURE_AT,
        failure_code="synthetic_failure",
        description="Synthetic non-recoverable lifecycle failure.",
    )


def make_prepared_agent(
    *,
    runtime: StageFlowRuntime | None = None,
    profile: RuntimeProfile = RuntimeProfile.AGENT,
    mode: RuntimeEventModeKind = RuntimeEventModeKind.EVENT,
    dependencies: AgentRuntimeDependencies | None = None,
    sink: RecordingAgentRuntimeSink | None = None,
    agent_instance_id: EntityId = AGENT_INSTANCE_ID,
) -> tuple[SoftwareAgentRuntime, RecordingAgentRuntimeSink]:
    agent, resolved_sink = make_agent(
        runtime=runtime,
        profile=profile,
        mode=mode,
        dependencies=dependencies,
        sink=sink,
        agent_instance_id=agent_instance_id,
    )
    agent.prepare(
        prepare_request(
            agent,
            allow_development=profile is RuntimeProfile.DEVELOPMENT,
        )
    )
    return agent, resolved_sink


def make_running_agent(
    *,
    pressure: RuntimePressureState = RuntimePressureState.NORMAL,
    runtime: StageFlowRuntime | None = None,
    profile: RuntimeProfile = RuntimeProfile.AGENT,
    mode: RuntimeEventModeKind = RuntimeEventModeKind.EVENT,
    dependencies: AgentRuntimeDependencies | None = None,
    sink: RecordingAgentRuntimeSink | None = None,
    agent_instance_id: EntityId = AGENT_INSTANCE_ID,
) -> tuple[SoftwareAgentRuntime, RecordingAgentRuntimeSink]:
    agent, resolved_sink = make_prepared_agent(
        runtime=runtime,
        profile=profile,
        mode=mode,
        dependencies=dependencies,
        sink=sink,
        agent_instance_id=agent_instance_id,
    )
    agent.start(
        start_request(
            agent,
            pressure=pressure,
            allow_development=profile is RuntimeProfile.DEVELOPMENT,
        )
    )
    return agent, resolved_sink
