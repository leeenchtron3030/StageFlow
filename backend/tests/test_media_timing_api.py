from __future__ import annotations

import tomllib
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from httpx import Client
from test_media_timing_inspection import FIELDS
from test_render_work_execution import NOW, MutableClock

from app.api.v1 import media_timing
from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.production.event_mode_kernel import (
    DurableEventModeKernel,
    EventModeKernelRepository,
)
from app.contexts.production.media_timing_evidence import (
    ApplyMediaTimingEvidenceRequest,
    InMemoryMediaTimingEvidenceRepository,
    MediaTimingEvidenceApplication,
)
from app.contexts.production.media_timing_evidence.enqueue import (
    MediaTimingEnqueue,
    RegisteredTimingAsset,
)
from app.contexts.production.media_timing_evidence.inspection import inspection_result
from app.contexts.work_execution import MediaTimingOperationInput, WorkExecutionRepository
from app.contexts.work_execution.memory import InMemoryWorkExecutionRepository
from app.core.config.deployment import EffectiveKernelConfiguration, LocalMediaTimingConfiguration
from app.main import create_app
from app.shared.ids import EntityId
from app.shared.time import FixedClock

HEADERS = {"X-StageFlow-API-Secret": "stageflow-test-only-shared-secret-0123456789"}


def test_media_timing_api_auth_bounds_paging_human_command_and_no_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event, asset, manifest = EntityId.new(), EntityId.new(), EntityId.new()
    memory = InMemoryWorkExecutionRepository(MutableClock())
    service = MediaTimingEnqueue(cast(WorkExecutionRepository[MediaTimingOperationInput], memory),
                                "test-deployment", FixedClock(NOW))
    operation = service.enqueue(event, RegisteredTimingAsset(asset, manifest, NOW))
    repository = Mock()
    repository.page.return_value = ((operation,), operation.id)
    repository.asset_page.return_value = ((RegisteredTimingAsset(asset, manifest, NOW),), asset)
    repository.enqueue.side_effect = memory.enqueue
    monkeypatch.setattr(media_timing, "_repository", Mock(return_value=repository))
    evidence = InMemoryMediaTimingEvidenceRepository()
    evidence.register_asset(asset, manifest)
    result = inspection_result(FIELDS, version="8.0.1", digest="a" * 64, inspected_at=NOW)
    applied = MediaTimingEvidenceApplication(evidence).apply(ApplyMediaTimingEvidenceRequest(
        EntityId.new(), asset, manifest, "1.0", NOW, result,
    ))
    kernel = Mock(spec=EventModeKernelRepository)
    config = SimpleNamespace(deployment=SimpleNamespace(
        local_media_timing=SimpleNamespace(enabled=True), deployment_id="test-deployment",
    ))
    components = KernelComponents(cast(EffectiveKernelConfiguration, config),
        cast(EventModeKernelRepository, kernel),
        cast(DurableEventModeKernel, SimpleNamespace(clock=FixedClock(NOW))),
        media_timing_evidence_repository=evidence)
    app = create_app()
    app.state.kernel = components
    client = cast(Client, TestClient(app))
    url = f"/api/v1/media-timing/events/{event.value}"
    latest = f"/api/v1/media-timing/assets/{asset.value}/latest"
    body: dict[str, object] = {
        "actor_id": EntityId.new().value, "confirmed": "confirmed", "limit": 1,
    }
    assert client.get(url + "/operations").status_code == 401
    assert client.get(latest).status_code == 401
    assert client.post(url + "/requests", json=body).status_code == 401
    for limit in (0, 101):
        assert client.get(url + f"/operations?limit={limit}", headers=HEADERS).status_code == 422
        assert client.post(url + "/requests", json={**body, "limit": limit},
                           headers=HEADERS).status_code == 422
    response = client.get(url + "/operations?limit=1", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["next_after"] == operation.id.value
    assert response.json()["items"][0]["asset_id"] == asset.value
    response = client.get(url + f"/operations?limit=1&after={operation.id.value}", headers=HEADERS)
    assert response.status_code == 200
    repository.page.assert_called_with(event, limit=1, after=operation.id)
    first = client.post(url + "/requests", json=body, headers=HEADERS)
    assert first.status_code == 200
    assert first.json() == client.post(url + "/requests", json=body, headers=HEADERS).json()
    assert client.post(url + "/requests", json={**body, "authority_kind": "automatic"},
                       headers=HEADERS).status_code == 422
    assert client.post(url + "/requests", json={"actor_id": body["actor_id"]},
                       headers=HEADERS).status_code == 422
    response = client.get(latest, headers=HEADERS)
    assert response.status_code == 200
    summary = response.json()["evidence"]
    assert summary["revision"] == applied.revision and summary["qualification"] == "unqualified"
    assert summary["candidate_interval"]["started_at"] == NOW.isoformat()
    assert summary["limitations"] and summary["authorized_use"] == "advisory_only"
    assert all(value not in response.text
               for value in ("ffprobe_path", "source_reference", "stderr"))
    many = replace(result, limitations=tuple(f"synthetic-{i}" for i in range(101)))
    MediaTimingEvidenceApplication(evidence).apply(ApplyMediaTimingEvidenceRequest(
        EntityId.new(), asset, manifest, "1.0", NOW, many,
    ))
    summary = client.get(latest, headers=HEADERS).json()["evidence"]
    assert summary["revision"] == 2 and len(summary["limitations"]) == 100
    assert summary["limitations_truncated"] is True
    absent_url = f"/api/v1/media-timing/assets/{EntityId.new().value}/latest"
    assert client.get(absent_url, headers=HEADERS).json()["evidence"] is None
    config.deployment.local_media_timing = None
    assert client.post(url + "/requests", json=body, headers=HEADERS).status_code == 503
    assert client.get(latest, headers=HEADERS).status_code == 200
    kernel.get_asset.return_value = None
    assert client.get(latest, headers=HEADERS).status_code == 404


def test_optional_config_rejects_relative_repository_network_and_batch_paths() -> None:
    for path in ("ffprobe", str(Path.cwd() / "ffprobe.exe"), "//server/tool.exe",
                 str(Path.cwd().parent.parent / "ffprobe.cmd")):
        with pytest.raises(ValueError):
            LocalMediaTimingConfiguration(ffprobe_path=path)
    external = str(Path.cwd().parent.parent / "synthetic-tools" / "ffprobe.exe")
    config = LocalMediaTimingConfiguration(ffprobe_path=external)
    assert config.enabled is False and "synthetic-tools" not in repr(config)


@pytest.mark.parametrize("enabled", [False, True])
def test_timing_config_requires_path_only_when_enabled(enabled: bool) -> None:
    document = tomllib.loads(f"[local_media_timing]\nenabled = {str(enabled).lower()}\n")
    if enabled:
        with pytest.raises(ValueError, match="local_media_timing_path_required"):
            LocalMediaTimingConfiguration.model_validate(document["local_media_timing"])
    else:
        config = LocalMediaTimingConfiguration.model_validate(document["local_media_timing"])
        assert config.enabled is False and config.ffprobe_path is None


@pytest.mark.parametrize("path_kind", ["external", "relative", "repository", "network", "batch"])
def test_enabled_timing_config_validates_path(path_kind: str) -> None:
    external = str(Path.cwd().parent.parent / "synthetic-tools" / "ffprobe.exe")
    path = {
        "external": external, "relative": "ffprobe",
        "repository": str(Path.cwd() / "ffprobe.exe"), "network": "//server/tool.exe",
        "batch": str(Path(external).with_suffix(".cmd")),
    }[path_kind]
    if path_kind == "external":
        config = LocalMediaTimingConfiguration(enabled=True, ffprobe_path=path)
        assert config.enabled is True and config.ffprobe_path == path
    else:
        with pytest.raises(ValueError):
            LocalMediaTimingConfiguration(enabled=True, ffprobe_path=path)
