from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, cast

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.production.event_mode_kernel import (
    DurableEventModeKernel,
    InMemoryEventModeKernelRepository,
    StartSessionRequest,
)
from app.contexts.production.event_mode_kernel.repository import (
    KernelStorageUnavailableError,
)
from app.core.config.deployment import (
    EffectiveKernelConfiguration,
    load_kernel_deployment_configuration,
)
from app.main import create_app
from app.shared.ids import EntityId
from app.shared.time import FixedClock


class SyncHttpClient(Protocol):
    def get(self, url: str) -> Response: ...


NOW = datetime(2026, 8, 8, 20, 0, tzinfo=UTC)


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
    client = cast(SyncHttpClient, TestClient(create_app()))

    response = client.get("/api/v1/kernel/status")

    assert response.status_code == 200
    assert response.json()["configured"] is False
    assert response.json()["ready"] is False
    assert response.json()["attention_codes"] == ["kernel_not_configured"]


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
    source_path.mkdir()
    recovered = components.reconcile_startup(ready.event_id)

    assert ready.ready is True
    assert unavailable.ready is False
    assert "startup_reconciliation_failed" in unavailable.attention_codes
    assert any("source_unavailable" in code for code in unavailable.attention_codes)
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
    app = create_app()
    with TestClient(app) as raw_client:
        app.state.kernel = components
        client = cast(SyncHttpClient, raw_client)
        response = client.get("/api/v1/kernel/status")
    assert response.status_code == 200
    assert response.json()["stages"][0]["session_package_state"] == "assembling"
    assert "postgresql://not-used-by-memory-test" not in response.text
    assert str(source_path) not in response.text


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
    with TestClient(app) as raw_client:
        app.state.kernel = components
        client = cast(SyncHttpClient, raw_client)
        response = client.get("/api/v1/kernel/status")

    assert response.status_code == 503
    assert response.json()["database_available"] is False
    assert response.json()["attention_codes"] == ["postgresql_unavailable"]
