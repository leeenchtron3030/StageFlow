from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol, cast

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from app.bootstrap import event_mode_kernel as kernel_bootstrap
from app.bootstrap.event_mode_kernel import (
    KernelComponents,
    KernelDatabaseUnavailableError,
    KernelStartupProgress,
    build_kernel_components,
    load_kernel_components_from_environment,
)
from app.contexts.production.event_mode_kernel import (
    DurableEventModeKernel,
    EpistemicKind,
    InMemoryEventModeKernelRepository,
    RegisteredMediaAsset,
    StartSessionRequest,
)
from app.contexts.production.event_mode_kernel.repository import (
    KernelStorageUnavailableError,
)
from app.contexts.production.runtime import RuntimeConfigurationValidity, validate_runtime
from app.core.config.deployment import (
    EffectiveKernelConfiguration,
    load_kernel_deployment_configuration,
)
from app.infrastructure.postgres import PostgresMigrationRunner
from app.main import create_app
from app.shared.ids import EntityId
from app.shared.time import FixedClock


class SyncHttpClient(Protocol):
    def get(self, url: str) -> Response: ...


class FileInspector(Protocol):
    def __call__(self, path: Path, *, root: Path) -> object: ...


NOW = datetime(2026, 8, 8, 20, 0, tzinfo=UTC)
_POSTGRES_DSN = os.getenv("STAGEFLOW_TEST_POSTGRES_DSN")
AUTH_HEADERS = {"X-StageFlow-API-Secret": "stageflow-test-only-shared-secret-0123456789"}


@dataclass(slots=True)
class MutableClock:
    current: datetime

    def now(self) -> datetime:
        return self.current


@dataclass(slots=True)
class FailOnceIngressPublisher:
    calls: int = 0

    def publish(
        self, asset: RegisteredMediaAsset, *, received_at: datetime
    ) -> EntityId:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("simulated_crash_after_asset_registration")
        return EntityId("30000000-0000-0000-0000-000000000099")


def configuration(
    tmp_path: Path, source_path: Path
) -> EffectiveKernelConfiguration:
    path = tmp_path / "kernel.toml"
    path.write_text(
        f"""
schema_version = "1.0"
deployment_id = "razer"
node_id = "razer-node"
node_role = "node"
network_policy = "local_only"
postgres_dsn_secret_ref = "KERNEL_DSN"
[event]
key = "razer-event"
name = "Razer Reference Event"
[[event.stages]]
key = "main"
name = "Main Stage"
[[event.stages.sources]]
key = "main-source"
path = "{source_path.as_posix()}"
""".strip(),
        encoding="utf-8",
    )
    return load_kernel_deployment_configuration(
        path,
        environment={"KERNEL_DSN": "postgresql://not-used-by-memory-test"},
    )


def test_kernel_status_route_is_read_only_and_reports_unconfigured() -> None:
    client = cast(SyncHttpClient, TestClient(create_app(), headers=AUTH_HEADERS))

    response = client.get("/api/v1/kernel/status")

    assert response.status_code == 200
    assert response.json()["configured"] is False
    assert response.json()["runtime_profile"] is None
    assert response.json()["configuration_supplied"] is False
    assert response.json()["configuration_valid"] is None
    assert response.json()["runtime_composed"] is False
    assert response.json()["database_available"] is False
    assert response.json()["ready"] is False
    assert response.json()["attention_codes"] == ["kernel_not_configured"]


def test_kernel_status_retains_invalid_supplied_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    path = tmp_path / "invalid-kernel.toml"
    path.write_text('schema_version = "unsupported"', encoding="utf-8")
    monkeypatch.setenv("STAGEFLOW_KERNEL_CONFIG_PATH", str(path))

    with TestClient(create_app(), headers=AUTH_HEADERS) as raw_client:
        client = cast(SyncHttpClient, raw_client)
        response = client.get("/api/v1/kernel/status")

    payload = response.json()
    assert payload["configured"] is False
    assert payload["configuration_supplied"] is True
    assert payload["configuration_valid"] is False
    assert payload["runtime_composed"] is False
    assert payload["database_available"] is False
    assert payload["ready"] is False
    assert payload["attention_codes"] == ["kernel_startup_failed"]
    assert payload["startup_error"]
    assert "stageflow_kernel_startup_failed" in caplog.text
    assert "exception_type=ValidationError" in caplog.text
    assert str(path) not in caplog.text


def test_kernel_status_retains_valid_configuration_when_postgresql_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "recordings"
    source_path.mkdir()
    configuration(tmp_path, source_path)
    monkeypatch.setenv(
        "STAGEFLOW_KERNEL_CONFIG_PATH", str(tmp_path / "kernel.toml")
    )
    monkeypatch.setenv("KERNEL_DSN", "postgresql://synthetic-unavailable")

    def unavailable(dsn: str) -> None:
        del dsn
        raise KernelDatabaseUnavailableError("postgresql_unavailable")

    monkeypatch.setattr(kernel_bootstrap, "verify_kernel_schema", unavailable)

    with TestClient(create_app(), headers=AUTH_HEADERS) as raw_client:
        client = cast(SyncHttpClient, raw_client)
        response = client.get("/api/v1/kernel/status")

    payload = response.json()
    assert payload["configured"] is True
    assert payload["configuration_supplied"] is True
    assert payload["configuration_valid"] is True
    assert payload["runtime_composed"] is False
    assert payload["database_available"] is False
    assert payload["ready"] is False
    assert payload["attention_codes"] == ["kernel_startup_failed"]
    assert payload["startup_error"] == "postgresql_unavailable"


@pytest.mark.skipif(
    not _POSTGRES_DSN,
    reason="STAGEFLOW_TEST_POSTGRES_DSN is required for successful startup checks.",
)
def test_real_postgres_successful_environment_startup_reports_complete_progress(
    tmp_path: Path,
) -> None:
    assert _POSTGRES_DSN is not None
    PostgresMigrationRunner(_POSTGRES_DSN).apply_event_mode_kernel_v1()
    suffix = EntityId.new().value.replace("-", "")
    source_path = tmp_path / "recordings"
    source_path.mkdir()
    config_path = tmp_path / "successful-kernel.toml"
    config_path.write_text(
        f"""
schema_version = "1.0"
deployment_id = "startup-{suffix}"
node_id = "node-{suffix}"
node_role = "node"
network_policy = "local_only"
postgres_dsn_secret_ref = "KERNEL_DSN"
[event]
key = "startup-event-{suffix}"
name = "Successful Startup Event"
[[event.stages]]
key = "main"
name = "Main Stage"
[[event.stages.sources]]
key = "source-{suffix}"
path = "{source_path.as_posix()}"
""".strip(),
        encoding="utf-8",
    )
    environment = {
        "STAGEFLOW_KERNEL_CONFIG_PATH": str(config_path),
        "KERNEL_DSN": _POSTGRES_DSN,
    }
    effective = load_kernel_deployment_configuration(
        config_path, environment=environment
    )
    initial = build_kernel_components(effective, clock=FixedClock(NOW))
    bootstrapped = initial.explicit_bootstrap(
        operation_id=EntityId.new(), actor_id=EntityId.new()
    )
    assert bootstrapped.ready is True

    progress = KernelStartupProgress()
    loaded = load_kernel_components_from_environment(
        environment=environment,
        clock=FixedClock(NOW),
        progress=progress,
    )

    assert loaded is not None
    status = loaded.status()
    assert progress.configuration_supplied is True
    assert progress.configuration_valid is True
    assert progress.database_available is True
    assert progress.runtime_composed is True
    assert status is not None and status.ready is True


def test_explicit_bootstrap_and_startup_reconciliation_use_observed_source_state(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "recordings"
    source_path.mkdir()
    effective = configuration(tmp_path, source_path)
    repository = InMemoryEventModeKernelRepository()
    kernel = DurableEventModeKernel(repository=repository, clock=FixedClock(NOW))
    components = KernelComponents(
        configuration=effective,
        repository=repository,
        kernel=kernel,
    )

    ready = components.explicit_bootstrap(
        operation_id=EntityId("30000000-0000-0000-0000-000000000001"),
        actor_id=EntityId("30000000-0000-0000-0000-000000000002"),
    )
    assert components.runtime is not None
    assert validate_runtime(components.runtime).outcome is RuntimeConfigurationValidity.VALID
    assert components.runtime.identity.configured_stage_ids == tuple(
        stage.id for stage in repository.list_stages(ready.event_id)
    )
    assert {
        target.metadata["source_binding_key"]
        for target in components.runtime.collection_plans[0].targets
    } == {"main-source"}
    stage = repository.list_stages(ready.event_id)[0]
    session = kernel.start_session(
        StartSessionRequest(
            operation_id=EntityId("30000000-0000-0000-0000-000000000003"),
            event_id=ready.event_id,
            stage_id=stage.id,
            actor_id=EntityId("30000000-0000-0000-0000-000000000002"),
            authoritative_start=NOW,
            requested_at=NOW,
        )
    )
    source_path.rmdir()
    unavailable = components.reconcile_startup(ready.event_id)
    app = create_app()
    with TestClient(app, headers=AUTH_HEADERS) as raw_client:
        app.state.kernel = components
        client = cast(SyncHttpClient, raw_client)
        unavailable_response = client.get("/api/v1/kernel/status")
        source_path.mkdir()
        recovered = components.reconcile_startup(ready.event_id)
        recovered_response = client.get("/api/v1/kernel/status")

    assert ready.ready is True
    assert unavailable.ready is False
    assert "startup_reconciliation_failed" in unavailable.attention_codes
    assert any("source_unavailable" in code for code in unavailable.attention_codes)
    assert unavailable_response.json()["configured"] is True
    assert unavailable_response.json()["runtime_profile"] == "standard"
    assert unavailable_response.json()["configuration_supplied"] is True
    assert unavailable_response.json()["configuration_valid"] is True
    assert unavailable_response.json()["runtime_composed"] is True
    assert unavailable_response.json()["database_available"] is True
    assert unavailable_response.json()["ready"] is False
    assert unavailable_response.json()["stages"][0]["source_available"] is False
    assert recovered.ready is True
    recovered_stage = recovered.stages[0]
    assert recovered_stage.active_or_assembling_session_id == session.id
    assert recovered_stage.session_activity_state is not None
    assert recovered_stage.session_activity_state.value == "presentation_active"
    assert recovered_stage.session_package_state is not None
    assert recovered_stage.session_package_state.value == "assembling"
    assert recovered_stage.session_package_revision == 1
    assert recovered.latest_reconciliation is not None
    assert recovered.latest_reconciliation.status.value == "completed"
    assert recovered_response.status_code == 200
    assert recovered_response.json()["runtime_composed"] is True
    assert recovered_response.json()["database_available"] is True
    assert recovered_response.json()["ready"] is True
    assert recovered_response.json()["stages"][0]["source_available"] is True
    assert recovered_response.json()["stages"][0]["session_package_state"] == "assembling"
    assert recovered_response.json()["stages"][0]["session_limit"] == 20
    assert recovered_response.json()["stages"][0]["recent_sessions"][0]["session_id"] == (
        session.id.value
    )
    assert recovered_response.json()["stages"][0]["recent_sessions_truncated"] is False
    assert "postgresql://not-used-by-memory-test" not in recovered_response.text
    assert str(source_path) not in recovered_response.text


def test_kernel_status_reports_database_unavailability_as_structured_503(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "recordings"
    source_path.mkdir()
    effective = configuration(tmp_path, source_path)
    repository = InMemoryEventModeKernelRepository()
    components = KernelComponents(
        configuration=effective,
        repository=repository,
        kernel=DurableEventModeKernel(repository=repository, clock=FixedClock(NOW)),
    )

    def unavailable(self: KernelComponents) -> None:
        raise KernelStorageUnavailableError("postgresql_unavailable")

    monkeypatch.setattr(KernelComponents, "status", unavailable)
    app = create_app()
    with TestClient(app, headers=AUTH_HEADERS) as raw_client:
        app.state.kernel = components
        client = cast(SyncHttpClient, raw_client)
        response = client.get("/api/v1/kernel/status")

    assert response.status_code == 503
    assert response.json()["database_available"] is False
    assert response.json()["attention_codes"] == ["postgresql_unavailable"]


def test_bounded_media_cycle_persists_observations_registers_and_associates(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "recordings"
    source_path.mkdir()
    media_path = source_path / "segment-001.mp4"
    media_path.write_bytes(b"synthetic-media")
    effective = configuration(tmp_path, source_path)
    repository = InMemoryEventModeKernelRepository()
    clock = MutableClock(NOW)
    kernel = DurableEventModeKernel(repository=repository, clock=clock)
    components = KernelComponents(
        configuration=effective,
        repository=repository,
        kernel=kernel,
    )

    initial = components.explicit_bootstrap(
        operation_id=EntityId("30000000-0000-0000-0000-000000000011"),
        actor_id=EntityId("30000000-0000-0000-0000-000000000012"),
    )
    stage = repository.list_stages(initial.event_id)[0]
    session = kernel.start_session(
        StartSessionRequest(
            operation_id=EntityId("30000000-0000-0000-0000-000000000013"),
            event_id=initial.event_id,
            stage_id=stage.id,
            actor_id=EntityId("30000000-0000-0000-0000-000000000012"),
            authoritative_start=NOW,
            requested_at=NOW,
        )
    )

    clock.current += timedelta(seconds=6)
    cycle = components.run_media_cycle(event_id=initial.event_id)
    replay = components.run_media_cycle(event_id=initial.event_id)
    status = components.status()

    assert cycle.candidates_seen == 1
    assert cycle.assets_registered == 1
    assert cycle.source_failures == ()
    assert cycle.candidate_results[0].outcome == "registered"
    assert replay.assets_registered == 0
    assert replay.candidate_results[0].outcome == "registered_effects_reconciled"
    assert status is not None
    assert status.stages[0].registered_media == 1
    assert status.stages[0].associated_media == 1
    assert status.stages[0].active_or_assembling_session_id == session.id
    observations = repository.list_observations(
        cycle.candidate_results[0].candidate_id
    )
    assert sum(item.observation_kind == "asset_resource_snapshot" for item in observations) == 2
    assert any(item.observation_kind == "asset_readiness_evaluation" for item in observations)
    app = create_app()
    with TestClient(app, headers=AUTH_HEADERS) as raw_client:
        app.state.kernel = components
        client = cast(SyncHttpClient, raw_client)
        response = client.get("/api/v1/kernel/status")
    payload = cast(dict[str, object], response.json())
    media = cast(list[dict[str, object]], payload["recent_media"])[0]
    assert media["association_policy_id"] == "stageflow.kernel.media-association"
    assert media["association_policy_version"] == "1.1.0"
    assert media["association_input_references"]
    assert media["association_evidence_ids"] == []
    assert str(media_path) not in response.text


def test_real_filesystem_interval_less_media_stays_unresolved_during_turnover(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "recordings"
    source_path.mkdir()
    effective = configuration(tmp_path, source_path)
    repository = InMemoryEventModeKernelRepository()
    clock = MutableClock(NOW)
    kernel = DurableEventModeKernel(repository=repository, clock=clock)
    components = KernelComponents(effective, repository, kernel)
    initial = components.explicit_bootstrap(
        operation_id=EntityId.new(), actor_id=EntityId.new()
    )
    stage = repository.list_stages(initial.event_id)[0]
    actor_id = EntityId.new()
    first = kernel.start_session(
        StartSessionRequest(
            operation_id=EntityId.new(),
            event_id=initial.event_id,
            stage_id=stage.id,
            actor_id=actor_id,
            authoritative_start=NOW,
            requested_at=NOW,
        )
    )
    kernel.correct_session_boundary(
        operation_id=EntityId.new(),
        session_id=first.id,
        boundary_kind="end",
        boundary_at=NOW + timedelta(minutes=45),
        actor_id=actor_id,
        reason="ended",
    )
    second = kernel.start_session(
        StartSessionRequest(
            operation_id=EntityId.new(),
            event_id=initial.event_id,
            stage_id=stage.id,
            actor_id=actor_id,
            authoritative_start=NOW + timedelta(minutes=50),
            requested_at=NOW + timedelta(minutes=50),
        )
    )
    (source_path / "turnover-segment.mp4").write_bytes(b"synthetic-turnover-media")

    components.run_media_cycle(event_id=initial.event_id, scope="turnover-observation")
    clock.current += timedelta(seconds=6)
    registered = components.run_media_cycle(
        event_id=initial.event_id, scope="turnover-registration"
    )
    candidate = repository.get_candidate(registered.candidate_results[0].candidate_id)
    assert candidate is not None
    association = repository.get_association(candidate.proposed_asset_id)

    assert association is not None
    assert association.status.value == "unresolved"
    assert "multiple_eligible_sessions" in association.reason_codes
    assert {first.id.value, second.id.value}.issubset(
        {
            value.record_id
            for value in association.input_references
            if value.record_type == "session"
        }
    )


def test_postgresql_loss_requires_fresh_same_process_reconciliation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "recordings"
    source_path.mkdir()
    repository = InMemoryEventModeKernelRepository()
    kernel = DurableEventModeKernel(repository=repository, clock=FixedClock(NOW))
    components = KernelComponents(
        configuration(tmp_path, source_path), repository, kernel
    )
    ready = components.explicit_bootstrap(
        operation_id=EntityId.new(), actor_id=EntityId.new()
    )
    assert ready.ready is True
    assert ready.latest_reconciliation is not None
    pre_outage_id = ready.latest_reconciliation.id
    available_get = repository.get_event_by_key

    def unavailable(event_key: str) -> object:
        del event_key
        raise KernelStorageUnavailableError("postgresql_unavailable")

    monkeypatch.setattr(repository, "get_event_by_key", unavailable)
    with pytest.raises(KernelStorageUnavailableError, match="postgresql_unavailable"):
        components.status()
    monkeypatch.setattr(repository, "get_event_by_key", available_get)

    recovering = components.status()
    assert recovering is not None
    assert recovering.ready is False
    assert recovering.recovering is True
    assert "postgresql_reconciliation_required" in recovering.attention_codes
    assert recovering.latest_reconciliation is not None
    assert recovering.latest_reconciliation.id == pre_outage_id

    recovered = components.reconcile_postgresql_recovery()
    assert recovered is not None
    assert recovered.ready is True
    assert recovered.recovering is False
    assert recovered.latest_reconciliation is not None
    assert recovered.latest_reconciliation.id != pre_outage_id

    monkeypatch.setattr(repository, "get_event_by_key", unavailable)
    with pytest.raises(KernelStorageUnavailableError):
        components.status()
    monkeypatch.setattr(repository, "get_event_by_key", available_get)
    source_path.rmdir()
    failed = components.reconcile_postgresql_recovery()
    assert failed is not None
    assert failed.ready is False
    assert failed.recovering is True
    assert failed.latest_reconciliation is not None
    assert failed.latest_reconciliation.status.value == "failed"


def test_machine_boundary_proposal_is_queryable_and_does_not_mutate_session(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "recordings"
    source_path.mkdir()
    effective = configuration(tmp_path, source_path)
    repository = InMemoryEventModeKernelRepository()
    kernel = DurableEventModeKernel(repository=repository, clock=FixedClock(NOW))
    components = KernelComponents(effective, repository, kernel)
    bootstrapped = components.explicit_bootstrap(
        operation_id=EntityId("30000000-0000-0000-0000-000000000021"),
        actor_id=EntityId("30000000-0000-0000-0000-000000000022"),
    )
    stage = repository.list_stages(bootstrapped.event_id)[0]
    session = kernel.start_session(
        StartSessionRequest(
            operation_id=EntityId("30000000-0000-0000-0000-000000000023"),
            event_id=bootstrapped.event_id,
            stage_id=stage.id,
            actor_id=EntityId("30000000-0000-0000-0000-000000000022"),
            authoritative_start=NOW,
            requested_at=NOW,
        )
    )

    proposal = kernel.propose_session_boundary(
        session_id=session.id,
        boundary_kind="end",
        boundary_at=NOW + timedelta(minutes=45),
        epistemic_kind=EpistemicKind.DERIVED,
        proposer_id=EntityId("30000000-0000-0000-0000-000000000024"),
        evidence_ids=(EntityId("30000000-0000-0000-0000-000000000025"),),
        policy_id="silence-window",
        policy_version="1.0",
        reason="advisory boundary only",
    )

    unchanged = repository.get_session(session.id)
    status = components.status()
    assert unchanged == session
    assert repository.list_boundary_proposals(session.id) == (proposal,)
    assert status is not None
    assert status.boundary_proposals == (proposal,)


def test_media_growth_resets_the_persisted_stability_window(tmp_path: Path) -> None:
    source_path = tmp_path / "recordings"
    source_path.mkdir()
    media_path = source_path / "growing.mp4"
    media_path.write_bytes(b"first")
    effective = configuration(tmp_path, source_path)
    repository = InMemoryEventModeKernelRepository()
    clock = MutableClock(NOW)
    components = KernelComponents(
        effective,
        repository,
        DurableEventModeKernel(repository=repository, clock=clock),
    )
    bootstrapped = components.explicit_bootstrap(
        operation_id=EntityId("30000000-0000-0000-0000-000000000031"),
        actor_id=EntityId("30000000-0000-0000-0000-000000000032"),
    )

    media_path.write_bytes(b"first-and-growing")
    clock.current += timedelta(seconds=6)
    changed = components.run_media_cycle(event_id=bootstrapped.event_id)
    clock.current += timedelta(seconds=6)
    stable = components.run_media_cycle(event_id=bootstrapped.event_id)

    assert changed.assets_registered == 0
    assert changed.candidate_results[0].outcome == "insufficient_observation"
    assert stable.assets_registered == 1


def test_candidate_inspection_failure_is_isolated_from_other_media(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "recordings"
    source_path.mkdir()
    (source_path / "bad.mp4").write_bytes(b"bad")
    (source_path / "good.mp4").write_bytes(b"good")
    effective = configuration(tmp_path, source_path)
    repository = InMemoryEventModeKernelRepository()
    clock = MutableClock(NOW)
    components = KernelComponents(
        effective,
        repository,
        DurableEventModeKernel(repository=repository, clock=clock),
    )
    bootstrapped = components.explicit_bootstrap(
        operation_id=EntityId("30000000-0000-0000-0000-000000000041"),
        actor_id=EntityId("30000000-0000-0000-0000-000000000042"),
    )
    cycle = components.media_cycle
    assert cycle is not None
    inspect_file = cast(
        FileInspector, object.__getattribute__(cycle, "_inspect_file")
    )

    def fail_one(path: Path, *, root: Path) -> object:
        if path.name == "bad.mp4":
            raise OSError("simulated_candidate_failure")
        return inspect_file(path, root=root)

    monkeypatch.setattr(cycle, "_inspect_file", fail_one)
    clock.current += timedelta(seconds=6)

    result = components.run_media_cycle(event_id=bootstrapped.event_id)

    assert result.candidates_seen == 2
    assert result.assets_registered == 1
    assert [item.outcome for item in result.candidate_results] == ["failed", "registered"]
    failed = result.candidate_results[0]
    assert failed.failure_code == "OSError"
    assert any(
        observation.observation_kind == "candidate_inspection_failure"
        for observation in repository.list_observations(failed.candidate_id)
    )


def test_candidate_replacement_has_typed_transient_cycle_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "recordings"
    source_path.mkdir()
    (source_path / "growing.mp4").write_bytes(b"still-growing")
    effective = configuration(tmp_path, source_path)
    repository = InMemoryEventModeKernelRepository()
    clock = MutableClock(NOW)
    components = KernelComponents(
        effective,
        repository,
        DurableEventModeKernel(repository=repository, clock=clock),
    )
    bootstrapped = components.explicit_bootstrap(
        operation_id=EntityId("30000000-0000-0000-0000-000000000043"),
        actor_id=EntityId("30000000-0000-0000-0000-000000000044"),
    )
    fstat = os.fstat

    def changed_fstat(descriptor: int) -> os.stat_result:
        values = list(fstat(descriptor))
        values[6] += 1
        return os.stat_result(values)

    monkeypatch.setattr(os, "fstat", changed_fstat)

    result = components.run_media_cycle(event_id=bootstrapped.event_id)

    assert result.assets_registered == 0
    assert len(result.candidate_results) == 1
    candidate_result = result.candidate_results[0]
    assert candidate_result.outcome == "failed"
    assert candidate_result.failure_code == "candidate_replaced_during_observation"
    observations = repository.list_observations(candidate_result.candidate_id)
    failure = next(
        item
        for item in observations
        if item.observation_kind == "candidate_inspection_failure"
    )
    assert failure.facts["failure_code"] == "candidate_replaced_during_observation"


def test_registered_asset_reconciles_ingress_and_association_after_interruption(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "recordings"
    source_path.mkdir()
    (source_path / "segment.mp4").write_bytes(b"synthetic-media")
    effective = configuration(tmp_path, source_path)
    repository = InMemoryEventModeKernelRepository()
    clock = MutableClock(NOW)
    publisher = FailOnceIngressPublisher()
    kernel = DurableEventModeKernel(
        repository=repository,
        clock=clock,
        asset_ingress_publisher=publisher,
    )
    components = KernelComponents(effective, repository, kernel)
    bootstrapped = components.explicit_bootstrap(
        operation_id=EntityId("30000000-0000-0000-0000-000000000051"),
        actor_id=EntityId("30000000-0000-0000-0000-000000000052"),
    )
    stage = repository.list_stages(bootstrapped.event_id)[0]
    session = kernel.start_session(
        StartSessionRequest(
            operation_id=EntityId("30000000-0000-0000-0000-000000000053"),
            event_id=bootstrapped.event_id,
            stage_id=stage.id,
            actor_id=EntityId("30000000-0000-0000-0000-000000000052"),
            authoritative_start=NOW,
            requested_at=NOW,
        )
    )
    clock.current += timedelta(seconds=6)

    interrupted = components.run_media_cycle(event_id=bootstrapped.event_id)
    candidate_id = interrupted.candidate_results[0].candidate_id
    candidate = repository.get_candidate(candidate_id)
    assert candidate is not None
    assert candidate.state.value == "registered"
    assert repository.get_asset(candidate.proposed_asset_id) is not None
    assert repository.get_association(candidate.proposed_asset_id) is None

    recovered = components.run_media_cycle(event_id=bootstrapped.event_id)

    assert recovered.assets_registered == 0
    assert recovered.candidate_results[0].outcome == "registered_effects_reconciled"
    association = repository.get_association(candidate.proposed_asset_id)
    assert association is not None
    assert association.session_id == session.id
    assert publisher.calls == 2
