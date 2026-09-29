from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from httpx import Client
from test_media_segmentation import result
from test_render_work_execution import NOW, MutableClock

from app.api.v1 import media_segmentation
from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.production.event_mode_kernel import (
    DurableEventModeKernel,
    EventModeKernelRepository,
)
from app.contexts.production.media_segmentation_evidence.contracts import MediaSegmentationEvidence
from app.contexts.production.media_segmentation_evidence.enqueue import (
    MediaSegmentationEnqueue,
    RegisteredSegmentationAsset,
)
from app.contexts.production.media_segmentation_evidence.repository import (
    InMemoryMediaSegmentationRepository,
)
from app.contexts.work_execution import MediaSegmentationOperationInput, WorkExecutionRepository
from app.core.config.deployment import (
    EffectiveKernelConfiguration,
    LocalMediaSegmentationConfiguration,
)
from app.main import create_app
from app.shared.ids import EntityId

HEADERS = {"X-StageFlow-API-Secret": "stageflow-test-only-shared-secret-0123456789"}


def test_api_auth_bounds_backfill_asset_session_reads_and_no_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event, asset, manifest, session = (EntityId.new() for _ in range(4))
    memory = InMemoryMediaSegmentationRepository(MutableClock())
    memory.assets[event] = (RegisteredSegmentationAsset(asset, manifest, NOW),)
    memory.session_assets[session] = (asset,)
    evidence = MediaSegmentationEvidence(EntityId.new(), EntityId.new(), asset, manifest, "1.0",
                                         EntityId.new(), result(), NOW)
    memory.segmentation_evidence[evidence.id] = evidence
    work = cast(WorkExecutionRepository[MediaSegmentationOperationInput], memory)
    operation = MediaSegmentationEnqueue(work, "test-deployment", MutableClock()).enqueue(
        event, memory.assets[event][0])
    repository = Mock(wraps=memory)
    repository.page.return_value = ((operation,), operation.id)
    monkeypatch.setattr(media_segmentation, "_repository", Mock(return_value=repository))
    kernel = Mock(spec=EventModeKernelRepository)
    config = SimpleNamespace(deployment=SimpleNamespace(
        local_media_segmentation=SimpleNamespace(enabled=True), deployment_id="test-deployment"))
    app = create_app()
    app.state.kernel = KernelComponents(cast(EffectiveKernelConfiguration, config), kernel,
        cast(DurableEventModeKernel, SimpleNamespace(clock=MutableClock())))
    client = cast(Client, TestClient(app))
    base = "/api/v1/media-segmentation"
    asset_url = f"{base}/assets/{asset.value}/evidence"
    session_url = f"{base}/sessions/{session.value}/evidence"
    operations = f"{base}/events/{event.value}/operations"
    command = f"{base}/events/{event.value}/requests"
    body = {"actor_id": EntityId.new().value, "confirmed": "confirmed", "limit": 1}
    for url in (asset_url, session_url, operations):
        assert client.get(url).status_code == 401
    assert client.post(command, json=body).status_code == 401
    for url in (asset_url, session_url):
        response = client.get(url, headers=HEADERS)
        assert response.status_code == 200
        assert response.json()["items"][0]["authorized_use"] == "advisory_only"
        assert response.json()["items"][0]["result"]["profile"]["decode"] == "cpu"
        assert not any(word in response.text for word in (
            "stderr", "ffmpeg_path", "source_reference"))
        for limit in (0, 11):
            assert client.get(url + f"?limit={limit}", headers=HEADERS).status_code == 422
        paged = client.get(url + f"?after={evidence.id.value}", headers=HEADERS)
        assert paged.json()["items"] == []
    assert client.get(operations, headers=HEADERS).json()["next_after"] == operation.id.value
    first = client.post(command, json=body, headers=HEADERS)
    assert first.status_code == 200
    assert first.json() == client.post(command, json=body, headers=HEADERS).json()
    for extra in ({"limit": 101}, {"authority_kind": "automatic"}, {"confirmed": "no"}):
        assert client.post(command, json={**body, **extra}, headers=HEADERS).status_code == 422
    kernel.get_asset.return_value = None
    assert client.get(asset_url, headers=HEADERS).status_code == 404
    kernel.get_session.return_value = None
    assert client.get(session_url, headers=HEADERS).status_code == 404
    config.deployment.local_media_segmentation = None
    assert client.post(command, json=body, headers=HEADERS).status_code == 503


def test_config_default_off_required_path_and_closed_fields() -> None:
    assert LocalMediaSegmentationConfiguration().enabled is False
    for document in ({"enabled": True}, {"ffmpeg_path": "relative"},
                     {"ffmpeg_path": "../ffmpeg"}, {"unknown": "value"}):
        with pytest.raises(ValueError):
            LocalMediaSegmentationConfiguration.model_validate(document)
    assert "ffmpeg_path" not in repr(LocalMediaSegmentationConfiguration())
