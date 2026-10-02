from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass, field, replace
from datetime import timedelta
from pathlib import Path
from typing import cast

import pytest
from asset_readiness_fixtures import (
    BASE_TIME,
    CANDIDATE_ID,
    EVALUATED_AT,
    OBSERVER_ID,
    RESOURCE_ID,
    RUNTIME_ID,
    make_candidate,
    make_parameters,
    make_policy,
    make_request,
    make_stability_bundle,
    reason_codes,
)
from runtime_fixtures import synchronize_runtime
from test_kernel_composition_and_status import NOW, MutableClock, configuration

from app.bootstrap import media_cycle, runtime_factory
from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.events import Stage
from app.contexts.production.asset_readiness import (
    AssetReadinessEvaluation,
    AssetReadinessEvaluationRequest,
    AssetReadinessObservationBundle,
    AssetReadinessOutcome,
    AssetWriteStateObservation,
    AssetWriteStateStatus,
    ConservativeAssetReadinessPolicy,
    MediaAssetCandidate,
)
from app.contexts.production.event_mode_kernel import (
    DurableEventModeKernel,
    InMemoryEventModeKernelRepository,
)
from app.contexts.production.media_collection import MediaObservationCollectionRequest
from app.contexts.production.runtime import (
    RuntimeCapabilityKind,
    RuntimeCollectionMode,
    RuntimeObservationType,
    RuntimeValidationOutcome,
    RuntimeValidationReasonCode,
    validate_runtime,
)
from app.contexts.production.software_agent_runtime import AgentRuntimeExecutionPermission
from app.core.config.deployment import EffectiveKernelConfiguration, KernelDeploymentConfiguration
from app.infrastructure import windows_write_state as windows
from app.shared.ids import EntityId
from app.shared.time import FixedClock


class FakeWindowsError(OSError):
    def __init__(self, code: int) -> None:
        super().__init__("private path and OS message")
        self.winerror = code


@dataclass
class FakeWindowsFileApi:
    error: int | None = None
    drive: int = 3
    close_error: bool = False
    drive_error: bool = False
    opened: list[str] = field(default_factory=list[str])
    closed: list[int] = field(default_factory=list[int])
    roots: list[str] = field(default_factory=list[str])

    def drive_type(self, root: str) -> int:
        self.roots.append(root)
        if self.drive_error:
            raise FakeWindowsError(5)
        return self.drive

    def open_read_deny_write(self, path: str) -> int:
        self.opened.append(path)
        if self.error is not None:
            raise FakeWindowsError(self.error)
        return 123

    def close(self, handle: int) -> None:
        self.closed.append(handle)
        if self.close_error:
            raise FakeWindowsError(6)


@pytest.fixture
def supported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(windows, "write_state_supported", lambda: True)


@pytest.mark.usefixtures("supported")
@pytest.mark.parametrize(
    ("error", "status", "limitations", "closed"),
    [
        (None, AssetWriteStateStatus.INACTIVE, (), [123]),
        (32, AssetWriteStateStatus.ACTIVE, (), []),
        (5, AssetWriteStateStatus.UNKNOWN, ("write_state_os_error",), []),
        (2, AssetWriteStateStatus.UNKNOWN, ("write_state_os_error",), []),
    ],
)
def test_probe_outcomes_close_only_acquired_handles(
    error: int | None,
    status: AssetWriteStateStatus,
    limitations: tuple[str, ...],
    closed: list[int],
) -> None:
    api = FakeWindowsFileApi(error=error)
    result = windows.WindowsWriteStateProbe(api).probe(Path("C:/synthetic/media.mp4"))
    assert result.status is status
    assert result.limitations == limitations
    assert api.closed == closed
    assert api.roots == ["C:\\"]
    assert api.opened == ["C:\\synthetic\\media.mp4"]


@pytest.mark.usefixtures("supported")
@pytest.mark.parametrize("close_error", [False, True])
def test_handle_close_is_attempted_before_return_even_on_error(close_error: bool) -> None:
    api = FakeWindowsFileApi(close_error=close_error)
    result = windows.WindowsWriteStateProbe(api).probe(Path("C:/synthetic/media.mp4"))
    assert api.closed == [123]
    assert result.status is (
        AssetWriteStateStatus.UNKNOWN if close_error else AssetWriteStateStatus.INACTIVE
    )
    if close_error:
        assert result.limitations == ("write_state_os_error",)


@pytest.mark.usefixtures("supported")
@pytest.mark.parametrize("path", [r"\\server\share\media.mp4", r"\\?\UNC\server\share\media.mp4"])
def test_unc_paths_are_unknown_without_os_calls(path: str) -> None:
    api = FakeWindowsFileApi()
    result = windows.WindowsWriteStateProbe(api).probe(Path(path))
    assert result == windows.WriteStateProbeResult(
        AssetWriteStateStatus.UNKNOWN, ("write_state_network_path",)
    )
    assert api.opened == api.closed == api.roots == []


@pytest.mark.usefixtures("supported")
@pytest.mark.parametrize("path", ["Z:/media.mp4", r"\\?\Z:\media.mp4"])
def test_remote_drive_is_unknown_without_open(path: str) -> None:
    api = FakeWindowsFileApi(drive=windows.DRIVE_REMOTE)
    result = windows.WindowsWriteStateProbe(api).probe(Path(path))
    assert result.limitations == ("write_state_network_path",)
    assert result.status is AssetWriteStateStatus.UNKNOWN
    assert api.roots == ["Z:\\"]
    assert api.opened == api.closed == []


@pytest.mark.usefixtures("supported")
@pytest.mark.parametrize("drive_error", [False, True])
def test_unidentified_drive_fails_closed(drive_error: bool) -> None:
    api = FakeWindowsFileApi(drive=0, drive_error=drive_error)
    result = windows.WindowsWriteStateProbe(api).probe(Path("C:/media.mp4"))
    assert result.status is AssetWriteStateStatus.UNKNOWN
    assert api.opened == api.closed == []


def test_non_windows_reports_no_support_and_refuses_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Patch the module's platform view, not the interpreter-wide sys.platform.
    @dataclass
    class Platform:
        platform: str = "linux"

    monkeypatch.setattr(windows, "sys", Platform())
    assert windows.write_state_supported() is False
    with pytest.raises(RuntimeError, match="windows_write_state_unsupported"):
        windows.WindowsWriteStateProbe(FakeWindowsFileApi())
    with pytest.raises(RuntimeError, match="windows_write_state_unsupported"):
        windows.CtypesWindowsFileApi()


@pytest.mark.usefixtures("supported")
def test_ctypes_open_uses_read_only_share_mode_and_pointer_sized_handle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @dataclass
    class Function:
        result: int
        argtypes: object = None
        restype: object = None
        calls: list[tuple[object, ...]] = field(default_factory=list[tuple[object, ...]])

        def __call__(self, *args: object) -> int:
            self.calls.append(args)
            return self.result

    @dataclass
    class Kernel32:
        CreateFileW: Function = field(default_factory=lambda: Function(2**40))
        CloseHandle: Function = field(default_factory=lambda: Function(1))
        GetDriveTypeW: Function = field(default_factory=lambda: Function(3))

    dll = Kernel32()

    def load(name: str, *, use_last_error: bool) -> Kernel32:
        assert name == "kernel32" and use_last_error
        return dll

    monkeypatch.setattr(windows.ctypes, "WinDLL", load, raising=False)
    result = windows.WindowsWriteStateProbe().probe(Path("C:/synthetic.mp4"))
    assert result.status is AssetWriteStateStatus.INACTIVE
    assert dll.CreateFileW.calls == [
        ("C:\\synthetic.mp4", 0x80000000, 1, None, 3, 0x80, None)
    ]
    assert dll.CreateFileW.restype is windows.wintypes.HANDLE
    assert dll.CloseHandle.argtypes == (windows.wintypes.HANDLE,)
    assert dll.CloseHandle.calls == [(2**40,)]


@pytest.mark.parametrize("support", [True, False])
def test_runtime_write_capability_matches_policy_and_collection_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, support: bool,
) -> None:
    # An absolute path on every platform; CI runs this test on Linux.
    source_path = tmp_path.as_posix()
    monkeypatch.setattr(runtime_factory, "write_state_supported", lambda: support)
    monkeypatch.setattr(media_cycle, "write_state_supported", lambda: support)
    effective = EffectiveKernelConfiguration(
        deployment=KernelDeploymentConfiguration.model_validate({
            "schema_version": "1.0", "deployment_id": "synthetic", "node_id": "node",
            "node_role": "node", "postgres_dsn_secret_ref": "SYNTHETIC_DSN",
            "event": {"key": "event", "name": "Event", "stages": [
                {"key": "main", "name": "Main", "sources": [
                    {"key": "source", "path": source_path},
                ]},
            ]},
        }),
        postgres_dsn="unused", sources={}, field_sources={},
    )
    stage = Stage(
        id=EntityId.new(), event_id=EntityId.new(), key="main", name="Main",
        source_bindings={"source": source_path}, external_references={}, revision=1,
        created_at=NOW, updated_at=NOW,
    )
    runtime = runtime_factory.build_stageflow_runtime(
        effective, stages=(stage,), clock=FixedClock(NOW),
    )
    assert validate_runtime(runtime).outcome is RuntimeValidationOutcome.VALID
    selection = runtime.readiness_policy_selections[0]
    capability = runtime.capability_set.readiness_capabilities[0]
    assert capability.write_state_support is support
    assert selection.policy_parameters.require_inactive_write_when_available is False
    write_capabilities = [
        item.id for item in runtime.capability_set.capabilities
        if item.kind is RuntimeCapabilityKind.WRITE_STATE_OBSERVATION_COLLECTION
    ]
    assert bool(write_capabilities) is support
    assert all(item in selection.required_capability_ids for item in write_capabilities)
    assert (RuntimeObservationType.WRITE_STATE in
            runtime.collection_plans[0].targets[0].enabled_observation_types) is support
    if support:
        invalid = synchronize_runtime(runtime, capability_set=replace(
            runtime.capability_set,
            readiness_capabilities=(replace(capability, write_state_support=False),),
        ))
        # Inactive write is not required, so a runtime without the capability stays valid.
        validation = validate_runtime(invalid)
        assert validation.outcome is RuntimeValidationOutcome.VALID
        assert RuntimeValidationReasonCode.STABILITY_WRITE_STATE_CAPABILITY_MISSING not in {
            reason.code for reason in validation.reasons
        }
    else:
        def forbidden_probe() -> windows.WindowsWriteStateProbe:
            pytest.fail("Non-Windows must not construct a write-state probe")

        monkeypatch.setattr(media_cycle, "WindowsWriteStateProbe", forbidden_probe)
        media_cycle.BoundedMediaCycle(
            configuration=effective, runtime=runtime,
            kernel=DurableEventModeKernel(
                repository=InMemoryEventModeKernelRepository(), clock=FixedClock(NOW),
            ),
            source_availability={},
        )


def collection_request() -> MediaObservationCollectionRequest:
    return MediaObservationCollectionRequest(
        collection_request_id=EntityId.new(),
        collection_cycle_id=EntityId.new(),
        runtime_id=RUNTIME_ID,
        configuration_id=EntityId.new(),
        collection_plan_id=EntityId.new(),
        collection_target_id=EntityId.new(),
        candidate_id=CANDIDATE_ID,
        resource_id=RESOURCE_ID,
        observation_capability_id=EntityId.new(),
        observation_type=RuntimeObservationType.WRITE_STATE,
        collection_mode=RuntimeCollectionMode.SCHEDULED_SAMPLING,
        requested_at=BASE_TIME,
        execution_permission=AgentRuntimeExecutionPermission.NORMAL,
        required=True,
    )


@pytest.mark.usefixtures("supported")
def test_port_observations_block_stable_writer_then_allow_after_close() -> None:
    api = FakeWindowsFileApi(error=32)
    clock = MutableClock(BASE_TIME + timedelta(seconds=6))
    adapter = windows.WindowsWriteStateObservationAdapter(
        probe=windows.WindowsWriteStateProbe(api),
        resolve_path=lambda request: Path("C:/synthetic/media.mp4"),
        observer_id=OBSERVER_ID,
        clock=clock,
    )
    request = collection_request()
    first = adapter.collect_write_state_observation(request)
    active = first.observations[0]
    assert isinstance(active, AssetWriteStateObservation)
    assert active.observed_at == clock.current
    assert active.candidate_id == CANDIDATE_ID
    assert active.resource_id == RESOURCE_ID
    assert active.source_runtime_id == RUNTIME_ID
    assert first.collection_request_id == request.collection_request_id
    assert first.cycle_id == request.collection_cycle_id
    policy = make_policy()
    bundle = replace(make_stability_bundle(), write_state_observations=(active,))
    blocked = policy.evaluate(make_candidate(), bundle, make_request())
    assert blocked.outcome is not AssetReadinessOutcome.SAFE_TO_READ
    assert {"write_state_unknown", "active_write_observed"}.intersection(reason_codes(blocked))

    api.error = None
    clock.current += timedelta(seconds=1)
    inactive = adapter.collect_write_state_observation(request).observations[0]
    assert isinstance(inactive, AssetWriteStateObservation)
    bundle = replace(bundle, write_state_observations=(active, inactive))
    ready = policy.evaluate(make_candidate(), bundle, make_request())
    assert ready.outcome is AssetReadinessOutcome.SAFE_TO_READ
    assert inactive.id in ready.supporting_observation_ids
    assert "inactive_write_state_observed" in reason_codes(ready)
    assert api.closed == [123]


@pytest.mark.usefixtures("supported")
def test_unknown_network_observation_falls_back_to_stability() -> None:
    adapter = windows.WindowsWriteStateObservationAdapter(
        probe=windows.WindowsWriteStateProbe(FakeWindowsFileApi(drive=4)),
        resolve_path=lambda request: Path("Z:/media.mp4"),
        observer_id=OBSERVER_ID,
        clock=FixedClock(EVALUATED_AT),
    )
    observation = adapter.collect_write_state_observation(collection_request()).observations[0]
    assert isinstance(observation, AssetWriteStateObservation)
    assert observation.limitations == ("write_state_network_path",)
    bundle = replace(make_stability_bundle(), write_state_observations=(observation,))
    # Production parameters: unknown write state does not block; stability qualifies.
    parameters = replace(make_parameters(), require_inactive_write_when_available=False)
    evaluation = make_policy(parameters).evaluate(make_candidate(), bundle, make_request())
    assert evaluation.outcome is AssetReadinessOutcome.SAFE_TO_READ
    assert "write_state_unknown" not in reason_codes(evaluation)


@pytest.mark.parametrize("network", [False, True])
@pytest.mark.parametrize("support", [True, False])
def test_media_cycle_persists_write_state_and_runtime_validates_on_both_platforms(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, support: bool, network: bool,
) -> None:
    # A local file opened by a writer blocks; a network path is unknown and falls back.
    api = FakeWindowsFileApi(error=32, drive=windows.DRIVE_REMOTE if network else 3)
    monkeypatch.setattr(windows, "write_state_supported", lambda: support)
    monkeypatch.setattr(runtime_factory, "write_state_supported", lambda: support)
    monkeypatch.setattr(media_cycle, "write_state_supported", lambda: support)

    def make_api() -> FakeWindowsFileApi:
        assert support, "Non-Windows must never construct the probe or Win32 API"
        return api

    monkeypatch.setattr(windows, "CtypesWindowsFileApi", make_api)

    class SyntheticWindowsPathProbe(windows.WindowsWriteStateProbe):
        def probe(self, resolved_path: Path) -> windows.WriteStateProbeResult:
            assert resolved_path.is_absolute()
            # Exercise the Windows API seam even when this test runs on POSIX.
            return super().probe(Path("C:/synthetic/media.mp4"))

    monkeypatch.setattr(media_cycle, "WindowsWriteStateProbe", SyntheticWindowsPathProbe)
    bundles: list[AssetReadinessObservationBundle] = []
    evaluate = ConservativeAssetReadinessPolicy.evaluate

    def capture_bundle(
        self: ConservativeAssetReadinessPolicy,
        candidate: MediaAssetCandidate,
        observations: AssetReadinessObservationBundle,
        request: AssetReadinessEvaluationRequest,
    ) -> AssetReadinessEvaluation:
        bundles.append(observations)
        return evaluate(self, candidate, observations, request)

    monkeypatch.setattr(ConservativeAssetReadinessPolicy, "evaluate", capture_bundle)
    source = tmp_path / "recordings"
    source.mkdir()
    (source / "media.mp4").write_bytes(b"synthetic")
    repository = InMemoryEventModeKernelRepository()
    clock = MutableClock(NOW)
    components = KernelComponents(
        configuration(tmp_path, source), repository,
        DurableEventModeKernel(repository=repository, clock=clock),
    )
    initial = components.explicit_bootstrap(operation_id=EntityId.new(), actor_id=EntityId.new())
    runtime = components.runtime
    assert runtime is not None
    assert validate_runtime(runtime).outcome is RuntimeValidationOutcome.VALID
    assert runtime.capability_set.readiness_capabilities[0].write_state_support is support
    selection = runtime.readiness_policy_selections[0]
    assert selection.policy_parameters.require_inactive_write_when_available is False
    write_capabilities = [
        item.id for item in runtime.capability_set.capabilities
        if item.kind is RuntimeCapabilityKind.WRITE_STATE_OBSERVATION_COLLECTION
    ]
    assert bool(write_capabilities) is support
    assert all(item in selection.required_capability_ids for item in write_capabilities)
    assert (RuntimeObservationType.WRITE_STATE in
            runtime.collection_plans[0].targets[0].enabled_observation_types) is support

    clock.current += timedelta(seconds=6)
    blocked = components.run_media_cycle(event_id=initial.event_id)
    held = support and not network
    assert blocked.assets_registered == (0 if held else 1)
    candidate_id = blocked.candidate_results[0].candidate_id
    writes = [item for item in repository.list_observations(candidate_id)
              if item.observation_kind == "asset_write_state"]
    assert bool(writes) is support
    if support and network:
        assert all(item.facts["status"] == "unknown" for item in writes)
        assert writes[-1].facts["limitations"] == ("write_state_network_path",)
        assert bundles[-1].write_state_observations[-1].limitations == (
            "write_state_network_path",
        )
        assert writes[-1].observed_at == clock.current
        assert writes[-1].facts["assessment_mechanism_id"] == windows.ASSESSMENT_MECHANISM
    elif support:
        assert writes[-1].facts["status"] == "active"
        assert bundles[-1].write_state_observations[-1].status is AssetWriteStateStatus.ACTIVE
        api.error = None
        clock.current += timedelta(seconds=1)
        # Recompose to prove the stability evidence comes from observation storage.
        components.compose_media_cycle()
        ready = components.run_media_cycle(event_id=initial.event_id)
        assert ready.assets_registered == 1
        observations = repository.list_observations(candidate_id)
        inactive = next(item for item in observations if item.facts.get("status") == "inactive")
        assert any(
            inactive.id.value in cast(tuple[str, ...], item.facts.get("evidence_ids", ()))
            for item in observations if item.observation_kind == "asset_readiness_evaluation"
        )
    else:
        assert api.opened == api.closed == api.roots == []


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 host integration")
def test_windows_host_child_writer_active_then_inactive(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.mp4"
    signal = tmp_path / "writer-ready"
    script = """
import sys, time
from pathlib import Path
with open(sys.argv[1], 'wb', buffering=0) as stream:
    stream.write(b'synthetic')
    Path(sys.argv[2]).write_text('ready')
    for _ in range(40):
        stream.write(b'.')
        time.sleep(0.05)
"""
    probe = windows.WindowsWriteStateProbe()
    child = subprocess.Popen([sys.executable, "-c", script, str(path), str(signal)])
    try:
        deadline = time.monotonic() + 3
        while not signal.exists() and time.monotonic() < deadline and child.poll() is None:
            time.sleep(0.01)
        assert signal.exists(), "child did not open the synthetic recording"
        assert child.poll() is None
        assert probe.probe(path.resolve()).status is AssetWriteStateStatus.ACTIVE
        assert child.wait(timeout=3) == 0
        assert probe.probe(path.resolve()).status is AssetWriteStateStatus.INACTIVE
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=1)
