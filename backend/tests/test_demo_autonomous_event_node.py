from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import psycopg
import pytest
from pydantic import ValidationError

from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.integration.local_schedule import LocalScheduleFileSource
from app.contexts.integration.program_source import ProgramSourceUnavailableError
from app.contexts.production.event_mode_kernel import (
    DurableEventModeKernel,
    InMemoryEventModeKernelRepository,
    StartSessionRequest,
)
from app.contexts.work_execution import (
    DurableOperation,
    OperationStatus,
    PendingOperation,
    TranscriptionOperationApplication,
    WorkExecutionRepository,
)
from app.core.config.deployment import (
    EffectiveKernelConfiguration,
    load_kernel_deployment_configuration,
)
from app.demo.autonomous import AutonomousEventNodeCoordinator, AutonomousEventNodeStatus
from app.demo.service import DemoApplication, ProcessTranscriptionRequest
from app.infrastructure.postgres import PostgresWorkExecutionRepository
from app.shared.ids import EntityId

NOW = datetime(2026, 8, 20, 18, 0, tzinfo=UTC)
ACTOR_ID = EntityId("71000000-0000-4000-8000-000000000001")


@dataclass(slots=True)
class MutableClock:
    current: datetime

    def now(self) -> datetime:
        return self.current


class MemoryWorkRepository:
    def __init__(self, *, fail_enqueue_numbers: set[int] | None = None) -> None:
        self.operations: list[DurableOperation] = []
        self.enqueue_calls = 0
        self.fail_enqueue_numbers = fail_enqueue_numbers or set()

    def list_operations(self, **_: object) -> tuple[DurableOperation, ...]:
        return tuple(self.operations)

    def enqueue(self, pending: PendingOperation) -> DurableOperation:
        self.enqueue_calls += 1
        if self.enqueue_calls in self.fail_enqueue_numbers:
            raise RuntimeError("synthetic_enqueue_failure")
        request = pending.request
        operation = DurableOperation(
            id=request.operation_id,
            kind="transcription",
            schema_version="v1",
            deployment_id=request.deployment_id,
            event_id=request.event_id,
            input=request.input,
            idempotency_key=request.idempotency_key,
            request_digest=pending.request_digest,
            work_key=pending.work_key,
            priority=request.priority,
            eligible_at=request.eligible_at,
            status=OperationStatus.PENDING,
            max_attempts=request.max_attempts,
            retry_delay=request.retry_delay,
            required_for_event=request.required_for_event,
            attempt_count=0,
            fence_generation=0,
            current_attempt_id=None,
            lease_owner_worker_id=None,
            lease_expires_at=None,
            cancellation_requested_at=None,
            terminal_result_type=None,
            terminal_result_id=None,
            terminal_result_revision=None,
            last_reason_code=None,
            revision=1,
            created_at=request.requested_at,
            updated_at=request.requested_at,
        )
        self.operations.append(operation)
        return operation


def _write_schedule(path: Path, *, title: str = "Opening") -> None:
    path.write_text(json.dumps({
        "schema_version": "1.0", "event_key": "example-event",
        "sessions": [{
            "session_key": "opening", "stage_key": "main", "title": title,
            "speakers": ["Example Speaker"], "planned_start": NOW.isoformat(),
            "planned_end": (NOW + timedelta(minutes=30)).isoformat(),
        }],
    }), encoding="utf-8")


def _configuration(tmp_path: Path, source_path: Path) -> EffectiveKernelConfiguration:
    path = tmp_path / "demo2.toml"
    path.write_text(
        f"""
schema_version = "1.0"
deployment_id = "example-deployment"
node_id = "example-node"
runtime_profile = "demo-single-stage"
node_role = "node"
event_mode = "rehearsal"
network_policy = "optional"
postgres_dsn_secret_ref = "DEMO2_DSN"
schedule_source_reference = "{(tmp_path / "schedule.json").as_posix()}"

[local_schedule]
path = "{(tmp_path / "schedule.json").as_posix()}"

[local_transcription]
model_version = "0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf"
model_path = "C:/StageFlowDemo/models/faster-whisper-large-v3-turbo"

[autonomous_event_node]
enabled = true
media_reconciliation_interval_seconds = 5
program_refresh_interval_seconds = 120

[resources]
minimum_stable_seconds = 5

[event]
key = "example-event"
name = "Example Event"

[[event.stages]]
key = "main"
name = "Main Stage"

[[event.stages.sources]]
key = "recordings"
path = "{source_path.as_posix()}"
""".strip(),
        encoding="utf-8",
    )
    return load_kernel_deployment_configuration(
        path,
        environment={"DEMO2_DSN": "postgresql://not-used-by-memory-test"},
    )


def _components(
    tmp_path: Path,
) -> tuple[
    KernelComponents,
    InMemoryEventModeKernelRepository,
    MutableClock,
    Path,
]:
    source_path = tmp_path / "recordings"
    source_path.mkdir()
    configuration = _configuration(tmp_path, source_path)
    repository = InMemoryEventModeKernelRepository()
    clock = MutableClock(NOW)
    kernel = DurableEventModeKernel(repository=repository, clock=clock)
    components = KernelComponents(configuration, repository, kernel)
    components.explicit_bootstrap(operation_id=EntityId.new(), actor_id=ACTOR_ID)
    schedule_path = tmp_path / "schedule.json"
    _write_schedule(schedule_path)
    components.program_source = LocalScheduleFileSource(
        path=schedule_path, event_key=components.event_key, stage_keys=("main",),
        repository=repository, clock=clock,
    )
    return components, repository, clock, source_path


def _application(
    components: KernelComponents,
    repository: MemoryWorkRepository,
) -> DemoApplication:
    return DemoApplication(
        components=components,
        work=TranscriptionOperationApplication(
            cast(WorkExecutionRepository, repository)
        ),
        repository=cast(PostgresWorkExecutionRepository, repository),
    )


def _install_application(
    monkeypatch: pytest.MonkeyPatch,
    application: DemoApplication,
) -> None:
    def from_components(
        cls: type[DemoApplication], components: KernelComponents
    ) -> DemoApplication:
        del cls, components
        return application

    monkeypatch.setattr(DemoApplication, "from_components", classmethod(from_components))


def _start_session(
    components: KernelComponents,
    repository: InMemoryEventModeKernelRepository,
    *,
    program_expectation_id: EntityId | None = None,
) -> object:
    event = repository.get_event_by_key(components.event_key)
    assert event is not None
    stage = repository.list_stages(event.id)[0]
    return components.kernel.start_session(
        StartSessionRequest(
            operation_id=EntityId.new(),
            event_id=event.id,
            stage_id=stage.id,
            actor_id=ACTOR_ID,
            authoritative_start=components.kernel.clock.now(),
            requested_at=components.kernel.clock.now(),
            program_expectation_id=program_expectation_id,
        )
    )


def test_automatic_media_stabilizes_enqueues_once_and_manual_replay_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    components, repository, clock, source_path = _components(tmp_path)
    session = cast(Any, _start_session(components, repository))
    original_session = repository.get_session(session.id)
    work_repository = MemoryWorkRepository()
    application = _application(components, work_repository)
    _install_application(monkeypatch, application)
    coordinator = AutonomousEventNodeCoordinator(components)
    (source_path / "segment-001.mp4").write_bytes(b"synthetic-media")

    coordinator.run_media_cycle()

    first = coordinator.status()
    assert first.media_cycle_count == 1
    assert first.media_assets_registered == 0
    assert work_repository.operations == []

    clock.current += timedelta(seconds=6)
    coordinator.run_media_cycle()
    coordinator.run_media_cycle()
    operation = work_repository.operations[0]
    manual = application.process_transcription(
        ProcessTranscriptionRequest(
            operation_id=EntityId.new(),
            session_id=session.id,
            requested_at=clock.now(),
        )
    )

    assert coordinator.status().media_assets_registered == 0
    assert len(work_repository.operations) == 1
    assert manual.operations == (operation,)
    assert manual.operations_enqueued == 0
    assert repository.get_session(session.id) == original_session

    restarted = AutonomousEventNodeCoordinator(components)
    assert restarted.status().media_last_success_at is not None
    restarted.run_media_cycle()
    assert len(work_repository.operations) == 1


def test_sessionless_media_remains_unresolved_then_later_associates_safely(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    components, repository, clock, source_path = _components(tmp_path)
    work_repository = MemoryWorkRepository()
    _install_application(monkeypatch, _application(components, work_repository))
    coordinator = AutonomousEventNodeCoordinator(components)
    (source_path / "before-session.mp4").write_bytes(b"synthetic-media")

    coordinator.run_media_cycle()
    clock.current += timedelta(seconds=6)
    coordinator.run_media_cycle()

    event = repository.get_event_by_key(components.event_key)
    assert event is not None
    media = repository.list_recent_media(event.id, limit=10)[0]
    assert media.asset_id is not None
    assert media.association_status is not None
    assert media.association_status.value == "unresolved"
    assert work_repository.operations == []
    original_association = repository.get_association(media.asset_id)
    assert original_association is not None

    coordinator.run_media_cycle()
    assert repository.get_association(media.asset_id) == original_association

    restarted = AutonomousEventNodeCoordinator(components)
    session = cast(Any, _start_session(components, repository))
    restarted.run_media_cycle()
    reconciled = repository.list_recent_media(event.id, limit=10)[0]

    assert reconciled.asset_id is not None
    assert reconciled.association_status is not None
    assert reconciled.association_status.value == "associated"
    assert reconciled.session_id == session.id
    assert len(work_repository.operations) == 1
    updated_association = repository.get_association(reconciled.asset_id)
    assert updated_association is not None
    assert updated_association.revision == original_association.revision + 1


def test_human_association_is_not_overridden_when_session_inputs_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    components, repository, clock, source_path = _components(tmp_path)
    work_repository = MemoryWorkRepository()
    _install_application(monkeypatch, _application(components, work_repository))
    coordinator = AutonomousEventNodeCoordinator(components)
    (source_path / "human-owned.mp4").write_bytes(b"synthetic-media")
    coordinator.run_media_cycle()
    clock.current += timedelta(seconds=6)
    coordinator.run_media_cycle()
    first = cast(Any, _start_session(components, repository))
    coordinator.run_media_cycle()

    event = repository.get_event_by_key(components.event_key)
    assert event is not None
    media = repository.list_recent_media(event.id, limit=10)[0]
    assert media.asset_id is not None
    human = components.kernel.assign_asset(
        operation_id=EntityId.new(),
        asset_id=media.asset_id,
        session_id=first.id,
        actor_id=ACTOR_ID,
        reason="operator confirmed association",
    )
    clock.current += timedelta(minutes=30)
    components.kernel.correct_session_boundary(
        operation_id=EntityId.new(),
        session_id=first.id,
        boundary_kind="end",
        boundary_at=clock.now(),
        actor_id=ACTOR_ID,
        reason="presentation ended",
    )
    _start_session(components, repository)

    coordinator.run_media_cycle()

    assert repository.get_association(media.asset_id) == human


def test_conflict_association_is_not_overridden_when_session_inputs_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    components, repository, clock, source_path = _components(tmp_path)
    _install_application(monkeypatch, _application(components, MemoryWorkRepository()))
    coordinator = AutonomousEventNodeCoordinator(components)
    (source_path / "conflicted.mp4").write_bytes(b"synthetic-media")
    coordinator.run_media_cycle()
    clock.current += timedelta(seconds=6)
    coordinator.run_media_cycle()

    event = repository.get_event_by_key(components.event_key)
    assert event is not None
    media = repository.list_recent_media(event.id, limit=10)[0]
    assert media.asset_id is not None
    unresolved = repository.get_association(media.asset_id)
    assert unresolved is not None
    conflict = repository.put_association(
        replace(
            unresolved,
            status=type(unresolved.status).CONFLICT,
            reason_codes=("material_contradictory_evidence",),
            revision=unresolved.revision + 1,
            decided_at=clock.now(),
        )
    )
    _start_session(components, repository)

    coordinator.run_media_cycle()

    assert repository.get_association(media.asset_id) == conflict


def test_one_enqueue_failure_does_not_block_later_assets_or_later_cycles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    components, repository, clock, source_path = _components(tmp_path)
    _start_session(components, repository)
    work_repository = MemoryWorkRepository(fail_enqueue_numbers={1})
    _install_application(monkeypatch, _application(components, work_repository))
    coordinator = AutonomousEventNodeCoordinator(components)
    (source_path / "a-bad.mp4").write_bytes(b"first")
    (source_path / "b-good.mp4").write_bytes(b"second")

    coordinator.run_media_cycle()
    clock.current += timedelta(seconds=6)
    coordinator.run_media_cycle()

    assert len(work_repository.operations) == 1
    assert coordinator.status().transcription_enqueue_failures == 1
    event = repository.get_event_by_key(components.event_key)
    assert event is not None
    assert len(repository.list_recent_media(event.id, limit=10)) == 2

    coordinator.run_media_cycle()
    assert len(work_repository.operations) == 2
    assert coordinator.status().media_cycle_count == 3


def test_periodic_program_refresh_preserves_session_authority_and_cached_snapshot(
    tmp_path: Path,
) -> None:
    components, repository, clock, _ = _components(tmp_path)
    event = repository.get_event_by_key(components.event_key)
    assert event is not None
    stage = repository.list_stages(event.id)[0]
    coordinator = AutonomousEventNodeCoordinator(components)

    coordinator.run_program_refresh()
    expectation = repository.list_program_expectations(event.id)[0]
    session = cast(
        Any,
        _start_session(
            components,
            repository,
            program_expectation_id=expectation.id,
        ),
    )
    original_session = repository.get_session(session.id)

    clock.current += timedelta(minutes=2)
    components.sync_program()
    repeated = repository.list_program_expectations(event.id)[0]
    assert repeated.revision == 1

    _write_schedule(tmp_path / "schedule.json", title="Opening updated")
    clock.current += timedelta(minutes=2)
    coordinator.run_program_refresh()
    changed = repository.list_program_expectations(event.id)[0]
    assert changed.revision == 2
    successful = repository.get_latest_program_reconciliation(event.id, stage.id)
    assert successful is not None

    (tmp_path / "schedule.json").unlink()
    clock.current += timedelta(minutes=2)
    coordinator.run_program_refresh()

    retained = repository.list_program_expectations(event.id)[0]
    assert retained.lifecycle_state.value == "current"
    assert repository.get_latest_program_reconciliation(event.id, stage.id) == successful
    assert repository.get_session(session.id) == original_session
    assert coordinator.status().program_last_failure_code == (
        "provider_refresh_unavailable"
    )

    restarted = AutonomousEventNodeCoordinator(components)
    assert restarted.status().program_last_success_at == successful.synchronized_at


def test_coordinator_start_is_exactly_once_and_stop_is_bounded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    components, _, _, _ = _components(tmp_path)
    starts: list[str] = []
    joins: list[float | None] = []

    class FakeThread:
        def __init__(
            self,
            *,
            target: object,
            name: str,
            daemon: bool,
        ) -> None:
            del target
            assert daemon is False
            self.name = name

        def start(self) -> None:
            starts.append(self.name)

        def join(self, timeout: float | None = None) -> None:
            joins.append(timeout)

        def is_alive(self) -> bool:
            return False

    monkeypatch.setattr("app.demo.autonomous.threading.Thread", FakeThread)
    coordinator = AutonomousEventNodeCoordinator(components)

    coordinator.start()
    coordinator.start()
    coordinator.stop(timeout_seconds=100)

    assert starts == ["stageflow-autonomous-event-node"]
    assert joins == [30.0]
    assert coordinator.status().state == "stopped"


def test_unexpected_cycle_failure_degrades_without_killing_owned_loop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    components, _, _, _ = _components(tmp_path)
    coordinator = AutonomousEventNodeCoordinator(components)
    program_attempts = 0

    class FakeStop:
        stopped = False

        def is_set(self) -> bool:
            return self.stopped

        def set(self) -> None:
            self.stopped = True

        def wait(self, timeout: float) -> None:
            assert timeout >= 0

    class FakeConnection:
        def execute(self, query: str) -> None:
            assert query == "SELECT 1"

    fake_stop = FakeStop()

    def run_program_refresh() -> None:
        nonlocal program_attempts
        program_attempts += 1
        if program_attempts == 1:
            raise LookupError("unanticipated provider wrapper failure")
        fake_stop.set()

    monkeypatch.setattr(coordinator, "_stop", fake_stop)
    monkeypatch.setattr(
        "app.demo.autonomous.time.monotonic",
        iter(range(0, 10_000, 120)).__next__,
    )
    monkeypatch.setattr(coordinator, "run_program_refresh", run_program_refresh)
    monkeypatch.setattr(coordinator, "run_media_cycle", lambda: None)

    with caplog.at_level("ERROR", logger="app.demo.autonomous"):
        coordinator._run_owned(FakeConnection())  # type: ignore[arg-type]

    status = coordinator.status()
    assert program_attempts == 2
    assert status.state == "degraded"
    assert status.program_last_failure_code == "unexpected_cycle_failure"
    assert "cycle_kind=program_refresh" in caplog.text
    assert "exception_type=LookupError" in caplog.text


def test_default_configuration_keeps_automation_disabled(tmp_path: Path) -> None:
    source_path = tmp_path / "recordings"
    source_path.mkdir()
    configuration = _configuration(tmp_path, source_path)
    assert configuration.redacted_summary()["autonomous_event_node"] == {
        "enabled": True,
        "media_reconciliation_interval_seconds": 5.0,
        "program_refresh_interval_seconds": 120.0,
    }
    raw = configuration.deployment.model_dump()
    raw.pop("autonomous_event_node")

    disabled = type(configuration.deployment).model_validate(raw)

    assert disabled.autonomous_event_node.enabled is False
    assert disabled.autonomous_event_node.media_reconciliation_interval_seconds == 5
    assert disabled.autonomous_event_node.program_refresh_interval_seconds == 120
    assert disabled.autonomous_event_node.rehearsal_fault_media_cycle is None


@pytest.mark.parametrize("mode", ["event", "development", "rehearsal"])
def test_fault_configuration_is_rehearsal_only(tmp_path: Path, mode: str) -> None:
    components, _, _, _ = _components(tmp_path)
    raw = components.configuration.deployment.model_dump()
    raw["event_mode"] = mode
    raw["autonomous_event_node"]["rehearsal_fault_media_cycle"] = 2
    configuration_type = type(components.configuration.deployment)
    if mode == "rehearsal":
        validated = configuration_type.model_validate(raw)
        assert validated.autonomous_event_node.rehearsal_fault_media_cycle == 2
    else:
        with pytest.raises(ValidationError, match="requires rehearsal"):
            configuration_type.model_validate(raw)


@pytest.mark.parametrize("value", [0, -1, 1.5, True, "2"])
def test_fault_configuration_requires_positive_integer(tmp_path: Path, value: object) -> None:
    components, _, _, _ = _components(tmp_path)
    raw = components.configuration.deployment.model_dump()
    raw["autonomous_event_node"]["rehearsal_fault_media_cycle"] = value
    with pytest.raises(ValidationError):
        type(components.configuration.deployment).model_validate(raw)


def test_environment_override_cannot_enable_fault_outside_rehearsal(tmp_path: Path) -> None:
    _components(tmp_path)
    path = tmp_path / "demo2.toml"
    path.write_text(path.read_text().replace(
        "enabled = true", "enabled = true\nrehearsal_fault_media_cycle = 2",
    ))
    with pytest.raises(ValidationError, match="requires rehearsal"):
        load_kernel_deployment_configuration(path, environment={
            "DEMO2_DSN": "postgresql://not-used-by-memory-test", "STAGEFLOW_EVENT_MODE": "event",
        })


def test_program_source_unavailable_maps_to_bounded_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    components, _, clock, _ = _components(tmp_path)
    source = components.program_source
    assert source is not None

    def unavailable(**_: object) -> None:
        raise ProgramSourceUnavailableError("synthetic source unavailable")

    monkeypatch.setattr(source, "synchronize", unavailable)
    coordinator = AutonomousEventNodeCoordinator(components)
    coordinator.run_program_refresh()
    assert coordinator.status().program_last_failure_code == "provider_refresh_unavailable"
    assert coordinator.status().program_last_failure_at == clock.now()


@pytest.mark.parametrize("kind", ["media", "program"])
def test_owned_loop_recovers_and_retains_failure_until_same_kind_fails_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str,
) -> None:
    components, _, clock, _ = _components(tmp_path)
    application = _application(components, MemoryWorkRepository())
    _install_application(monkeypatch, application)
    coordinator = AutonomousEventNodeCoordinator(components)
    coordinator._update(state="running", owner=True)  # type: ignore[reportPrivateUsage]
    original = application.reconcile_media if kind == "media" else components.sync_program
    attempts = 0

    def failing_once(*args: Any, **kwargs: Any) -> Any:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise LookupError("synthetic unexpected failure")
        return original(*args, **kwargs)

    if kind == "media":
        def reconcile_media(_: DemoApplication, *args: Any, **kwargs: Any) -> Any:
            return failing_once(*args, **kwargs)

        monkeypatch.setattr(DemoApplication, "reconcile_media", reconcile_media)
        monkeypatch.setattr(coordinator, "run_program_refresh", lambda: None)
    else:
        def sync_program(_: KernelComponents) -> Any:
            return failing_once()

        monkeypatch.setattr(KernelComponents, "sync_program", sync_program)
        monkeypatch.setattr(coordinator, "run_media_cycle", lambda: None)
    snapshots: list[AutonomousEventNodeStatus] = []

    class StopAfterThreeCycles:
        def is_set(self) -> bool:
            return len(snapshots) >= 3

        def wait(self, timeout: float) -> None:
            snapshots.append(coordinator.status())
            clock.current += timedelta(minutes=2)

    class Connection:
        def execute(self, query: str) -> None:
            assert query == "SELECT 1"

    monkeypatch.setattr(coordinator, "_stop", StopAfterThreeCycles())
    monkeypatch.setattr("app.demo.autonomous.time.monotonic", iter(range(0, 10_000, 120)).__next__)
    coordinator._run_owned(Connection())  # type: ignore[arg-type]
    assert [status.state for status in snapshots] == ["degraded", "running", "running"]
    for status in snapshots:
        assert getattr(status, f"{kind}_last_failure_code") == "unexpected_cycle_failure"
        assert getattr(status, f"{kind}_last_failure_at") == NOW
    assert attempts == 3

    def anticipated_failure(*args: Any, **kwargs: Any) -> Any:
        raise ValueError("synthetic anticipated failure")

    if kind == "media":
        monkeypatch.setattr(DemoApplication, "reconcile_media", anticipated_failure)
        coordinator.run_media_cycle()
    else:
        monkeypatch.setattr(KernelComponents, "sync_program", anticipated_failure)
        coordinator.run_program_refresh()
    assert getattr(coordinator.status(), f"{kind}_last_failure_at") == clock.now()
    assert getattr(coordinator.status(), f"{kind}_last_failure_code") == (
        "media_reconciliation_failed" if kind == "media" else "program_refresh_failed"
    )


def test_rehearsal_fault_fires_once_through_owned_loop_and_recovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    components, _, clock, _ = _components(tmp_path)
    raw = components.configuration.deployment.model_dump()
    raw["autonomous_event_node"]["rehearsal_fault_media_cycle"] = 2
    components.configuration = components.configuration.model_copy(update={
        "deployment": type(components.configuration.deployment).model_validate(raw),
    })
    _install_application(monkeypatch, _application(components, MemoryWorkRepository()))
    coordinator = AutonomousEventNodeCoordinator(components)
    coordinator._update(state="running", owner=True)  # type: ignore[reportPrivateUsage]
    monkeypatch.setattr(coordinator, "run_program_refresh", lambda: None)
    snapshots: list[AutonomousEventNodeStatus] = []

    class StopAfterFourCycles:
        def is_set(self) -> bool:
            return len(snapshots) >= 4

        def wait(self, timeout: float) -> None:
            snapshots.append(coordinator.status())
            clock.current += timedelta(seconds=5)

    class Connection:
        def execute(self, query: str) -> None:
            assert query == "SELECT 1"

    monkeypatch.setattr(coordinator, "_stop", StopAfterFourCycles())
    monkeypatch.setattr("app.demo.autonomous.time.monotonic", iter(range(0, 10_000, 120)).__next__)
    coordinator._run_owned(Connection())  # type: ignore[arg-type]
    assert [status.state for status in snapshots] == ["running", "degraded", "running", "running"]
    assert [status.media_cycle_count for status in snapshots] == [1, 1, 2, 3]
    assert snapshots[0].media_last_failure_code is None
    for status in snapshots[1:]:
        assert status.media_last_failure_code == "unexpected_cycle_failure"
        assert status.media_last_failure_at == NOW + timedelta(seconds=5)


def test_kernel_components_expose_only_neutral_program_names(tmp_path: Path) -> None:
    components, _, _, _ = _components(tmp_path)
    assert "devcon_program_sync" not in inspect.signature(KernelComponents).parameters
    assert not hasattr(components, "devcon_program_sync")
    assert not hasattr(components, "sync_devcon_program")
    assert components.sync_program().added == 1
    assert components.sync_program().unchanged == 1


@pytest.mark.parametrize("media_failures,program_failures", [(2, 0), (2, 1), (1, 2)])
def test_recovery_requires_success_from_each_degraded_cycle_kind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    media_failures: int, program_failures: int,
) -> None:
    components, _, clock, _ = _components(tmp_path)
    application = _application(components, MemoryWorkRepository())
    _install_application(monkeypatch, application)
    coordinator = AutonomousEventNodeCoordinator(components)
    coordinator._update(state="running", owner=True)  # type: ignore[reportPrivateUsage]
    original_media = application.reconcile_media
    original_program = components.sync_program
    media_attempts = program_attempts = 0

    def reconcile_media(_: DemoApplication, *args: Any, **kwargs: Any) -> Any:
        nonlocal media_attempts
        media_attempts += 1
        if media_attempts <= media_failures:
            raise LookupError("synthetic media fault")
        return original_media(*args, **kwargs)

    def sync_program(_: KernelComponents) -> Any:
        nonlocal program_attempts
        program_attempts += 1
        if program_attempts <= program_failures:
            raise LookupError("synthetic program fault")
        return original_program()

    snapshots: list[AutonomousEventNodeStatus] = []

    class StopAfterThreeCycles:
        def is_set(self) -> bool:
            return len(snapshots) >= 3

        def wait(self, timeout: float) -> None:
            snapshots.append(coordinator.status())
            clock.current += timedelta(minutes=2)

    class Connection:
        def execute(self, query: str) -> None:
            assert query == "SELECT 1"

    monkeypatch.setattr(DemoApplication, "reconcile_media", reconcile_media)
    monkeypatch.setattr(KernelComponents, "sync_program", sync_program)
    monkeypatch.setattr(coordinator, "_stop", StopAfterThreeCycles())
    monkeypatch.setattr("app.demo.autonomous.time.monotonic", iter(range(0, 10_000, 120)).__next__)
    coordinator._run_owned(Connection())  # type: ignore[arg-type]

    assert [status.state for status in snapshots] == ["degraded", "degraded", "running"]
    assert media_attempts == program_attempts == 3
    assert snapshots[-1].media_last_failure_code == "unexpected_cycle_failure"
    assert snapshots[-1].media_last_failure_at == NOW + timedelta(minutes=2 * (media_failures - 1))
    if program_failures:
        assert snapshots[-1].program_last_failure_code == "unexpected_cycle_failure"
        assert snapshots[-1].program_last_failure_at == NOW + timedelta(
            minutes=2 * (program_failures - 1),
        )


@pytest.mark.parametrize("kind", ["media", "program"])
@pytest.mark.parametrize("initial_state", ["running", "degraded"])
@pytest.mark.parametrize("stop_state", ["stopping", "stopped", "timeout"])
def test_success_cannot_overwrite_stop_after_reading_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    kind: str, initial_state: str, stop_state: str,
) -> None:
    components, _, clock, _ = _components(tmp_path)
    _install_application(monkeypatch, _application(components, MemoryWorkRepository()))
    coordinator = AutonomousEventNodeCoordinator(components)
    coordinator._update(state=initial_state, owner=True)  # type: ignore[reportPrivateUsage]
    if initial_state == "degraded":
        coordinator._record_cycle_outcome(  # type: ignore[reportPrivateUsage]
            "media" if kind == "media" else "program", failed=True,
        )
    original_update = coordinator._update  # type: ignore[reportPrivateUsage]
    success_field = "media_cycle_count" if kind == "media" else "program_refresh_count"

    class TimedOutThread:
        def join(self, timeout: float) -> None:
            pass

        def is_alive(self) -> bool:
            return True

    def stop_before_success_update(**changes: object) -> None:
        if success_field in changes:
            if stop_state == "stopping":
                original_update(state="stopping")
                coordinator._stop.set()  # type: ignore[reportPrivateUsage]
            else:
                if stop_state == "timeout":
                    monkeypatch.setattr(coordinator, "_thread", TimedOutThread())
                coordinator.stop(timeout_seconds=0.1)
        original_update(**changes)

    monkeypatch.setattr(coordinator, "_update", stop_before_success_update)
    if kind == "media":
        coordinator.run_media_cycle()
    else:
        coordinator.run_program_refresh()

    status = coordinator.status()
    assert coordinator._stop.is_set()  # type: ignore[reportPrivateUsage]
    assert status.state == ("degraded" if stop_state == "timeout" else stop_state)
    assert getattr(status, success_field) == 1
    if stop_state == "timeout":
        assert status.media_last_failure_code == "coordinator_stop_timeout"
        assert status.media_last_failure_at == clock.now()
        assert status.owner is False


def test_outer_loop_recovers_postgresql_ownership_without_clearing_cycle_faults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    components, _, clock, _ = _components(tmp_path)
    _install_application(monkeypatch, _application(components, MemoryWorkRepository()))
    coordinator = AutonomousEventNodeCoordinator(components)
    coordinator._record_cycle_outcome("media", failed=True)  # type: ignore[reportPrivateUsage]
    coordinator._record_cycle_outcome("program", failed=True)  # type: ignore[reportPrivateUsage]
    snapshots: list[AutonomousEventNodeStatus] = []
    connections = 0
    unlocked = closed = False

    class RetryStop:
        stopped = False

        def is_set(self) -> bool:
            return self.stopped

        def set(self) -> None:
            self.stopped = True

        def wait(self, timeout: float) -> None:
            assert timeout == 5.0
            snapshots.append(coordinator.status())
            clock.current += timedelta(seconds=5)

    class Connection:
        def __enter__(self) -> Connection:
            return self

        def __exit__(self, *args: object) -> None:
            nonlocal closed
            closed = True

        def execute(self, query: str, parameters: tuple[str]) -> Connection:
            nonlocal unlocked
            assert parameters == ("stageflow:autonomous-event-node:example-deployment",)
            assert query in {
                "SELECT pg_try_advisory_lock(hashtextextended(%s, 0))",
                "SELECT pg_advisory_unlock(hashtextextended(%s, 0))",
            }
            unlocked = "pg_advisory_unlock" in query
            return self

        def fetchone(self) -> tuple[bool]:
            return (True,)

    def connect(*args: object, **kwargs: object) -> Connection:
        nonlocal connections
        connections += 1
        if connections == 1:
            raise psycopg.OperationalError("synthetic PostgreSQL outage")
        assert connections == 2
        return Connection()

    def run_owned(connection: object) -> None:
        snapshots.append(coordinator.status())
        # A fresh media catch-all still requires recovery of the earlier program fault.
        coordinator._record_cycle_outcome("media", failed=True)  # type: ignore[reportPrivateUsage]
        coordinator.run_media_cycle()
        assert coordinator.status().state == "degraded"
        coordinator.run_program_refresh()
        assert coordinator.status().state == "running"
        coordinator.stop()

    monkeypatch.setattr(coordinator, "_stop", RetryStop())
    monkeypatch.setattr("app.demo.autonomous.psycopg.connect", connect)
    monkeypatch.setattr(coordinator, "_run_owned", run_owned)
    coordinator._run()  # type: ignore[reportPrivateUsage]

    assert connections == 2
    assert [status.state for status in snapshots] == ["degraded", "running"]
    assert [status.owner for status in snapshots] == [False, True]
    for status in snapshots:
        assert status.media_last_failure_code == "postgresql_unavailable"
        assert status.media_last_failure_at == NOW
    assert coordinator.status().state == "stopped"
    assert coordinator.status().owner is False
    assert unlocked and closed
