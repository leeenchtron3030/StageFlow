from __future__ import annotations

from typing import Protocol, cast
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from media_timing_evidence_fixtures import ASSET_ID, MANIFEST_ID, NOW, evidence_request

from app.api.v1.media_timing_evidence import router
from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.production.event_mode_kernel import (
    DurableEventModeKernel,
    EventModeKernelRepository,
    RegisteredMediaAsset,
)
from app.contexts.production.media_timing_evidence import (
    InMemoryMediaTimingEvidenceRepository,
    MediaTimingEvidenceApplication,
)
from app.core.config.deployment import EffectiveKernelConfiguration
from app.main import create_app
from app.shared.ids import EntityId

AUTH_HEADERS = {"X-StageFlow-API-Secret": "stageflow-test-only-shared-secret-0123456789"}


class SyncHttpClient(Protocol):
    def get(self, url: str) -> Response: ...


def test_mte_read_api_requires_composed_kernel() -> None:
    client = cast(SyncHttpClient, TestClient(create_app(), headers=AUTH_HEADERS))

    response = client.get(
        f"/api/v1/media-assets/{ASSET_ID.value}/timing-evidence"
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "kernel_not_configured"}


def test_mte_read_api_exposes_bounded_advisory_sanitized_history() -> None:
    evidence_repository = InMemoryMediaTimingEvidenceRepository()
    evidence_repository.register_asset(ASSET_ID, MANIFEST_ID)
    applied = MediaTimingEvidenceApplication(evidence_repository).apply(
        evidence_request()
    )
    asset = RegisteredMediaAsset(
        id=ASSET_ID,
        candidate_id=EntityId.new(),
        manifest_id=MANIFEST_ID,
        stage_id=EntityId.new(),
        source_binding_key="sanitized-source",
        registered_at=NOW,
    )
    kernel_repository = MagicMock(spec=EventModeKernelRepository)
    kernel_repository.get_asset.return_value = asset
    components = KernelComponents(
        configuration=cast(EffectiveKernelConfiguration, object()),
        repository=cast(EventModeKernelRepository, kernel_repository),
        kernel=cast(DurableEventModeKernel, object()),
        media_timing_evidence_repository=evidence_repository,
    )
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.state.kernel = components
    client = cast(SyncHttpClient, TestClient(app))

    response = client.get(
        f"/api/v1/media-assets/{ASSET_ID.value}/timing-evidence"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["asset_id"] == ASSET_ID.value
    assert payload["active_revision"] == 1
    assert payload["evidence"][0]["evidence_id"] == applied.id.value
    assert payload["evidence"][0]["authorized_use"] == "advisory_only"
    assert payload["evidence"][0]["qualification_status"] == "unqualified"
    assert payload["evidence"][0]["observations"][0]["epistemic_kind"] == "observed"
    assert payload["evidence"][0]["derivations"][0]["epistemic_kind"] == "derived"
    serialized = response.text.casefold()
    assert "operation_id" not in serialized
    assert "request_digest" not in serialized
    assert "c:\\" not in serialized
    assert "/private/" not in serialized
