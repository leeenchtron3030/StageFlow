"""Read-only status contract in memory and rolled-back PostgreSQL."""
from dataclasses import replace
from typing import Any, cast
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from httpx import Client

from app.api.v1 import transcription
from app.contexts.production.event_mode_kernel.repository import KernelStorageUnavailableError
from app.contexts.production.session_suggestions.service import SessionSuggestionService
from app.contexts.transcription_evidence import (
    TranscriptEvidenceStatus,
    prepare_transcript_evidence,
)
from app.contexts.work_execution import (
    OperationFailure,
    TranscriptionOperationInput,
    WorkExecutionStorageUnavailableError,
)
from app.infrastructure.postgres.session_suggestion_repository import PostgresSuggestionRepository
from app.main import create_app
from app.shared.ids import EntityId
from tests.test_event_asset_transcription import Harness
from tests.test_media_timing_api import HEADERS
from tests.test_render_work_execution import render_postgres_dsn as render_postgres_dsn
from tests.test_transcription_worker_substrate import enqueue_request, transcript_result


def client_for(h: Harness, monkeypatch: pytest.MonkeyPatch) -> Client:
    if h.memory is not None:
        def read(asset_id: EntityId, **kwargs: Any) -> tuple[Any, bool, bool]:
            assert h.memory is not None
            asset = h.kernel_repository.get_asset(asset_id)
            assert asset is not None
            operations = [o for o in h.memory.operations.values()
                          if isinstance(o.input, TranscriptionOperationInput)
                          and o.input.asset_id == asset_id
                          and o.input.manifest_id == asset.manifest_id
                          and o.deployment_id == kwargs["deployment_id"]
                          and o.input.execution_profile_id == kwargs["execution_profile_id"]
                          and o.input.execution_profile_version
                          == kwargs["execution_profile_version"]]
            evidence = [e for e in h.memory.evidence.values() if e.asset_id == asset_id]
            complete = any(e.result.status == TranscriptEvidenceStatus.COMPLETE for e in evidence)
            partial = any(e.result.status == TranscriptEvidenceStatus.PARTIAL for e in evidence)
            return (operations[0] if operations else None, complete, partial and not complete)
        repository = Mock(asset_transcription_status=read)
    else:
        repository = h.repository
    monkeypatch.setattr(transcription, "_repository", Mock(return_value=repository))
    app = create_app()
    app.state.kernel = h.components
    return cast(Client, TestClient(app))


def exercise_status(h: Harness, monkeypatch: pytest.MonkeyPatch, outcome: str) -> None:
    asset = h.asset(0)
    client = client_for(h, monkeypatch)
    url = f"/api/v1/transcription/assets/{asset.id.value}/status"
    assert client.get(url).status_code == 401
    unknown = client.get(f"/api/v1/transcription/assets/{EntityId.new().value}/status",
                         headers=HEADERS)
    assert unknown.status_code == 404
    assert unknown.json() == {"detail": "completed_media_asset_not_found"}
    assert client.get(url, headers=HEADERS).json() == {
        "asset_id": asset.id.value, "operation": None,
        "complete_evidence": False, "partial_evidence": False,
    }
    h.reconcile()
    assert client.get(url, headers=HEADERS).json()["operation"] == {
        "state": "pending", "execution_profile_id": "test-profile",
        "execution_profile_version": "v1",
    }
    claim = h.claim()
    if outcome == "failed":
        h.repository.record_failure(claim, OperationFailure("synthetic_failure", False,
                                                            "private diagnostic C:/secret"))
    else:
        result = transcript_result()
        if outcome == "partial":
            result = replace(result, status=TranscriptEvidenceStatus.PARTIAL,
                             partial_reason="synthetic_partial")
        h.repository.apply_transcript_result(claim, prepare_transcript_evidence(claim, result))
    response = client.get(url, headers=HEADERS)
    assert response.status_code == 200
    assert response.json() == {
        "asset_id": asset.id.value,
        "operation": {"state": "terminal_failed" if outcome == "failed" else "succeeded",
                      "execution_profile_id": "test-profile", "execution_profile_version": "v1"},
        "complete_evidence": outcome == "complete", "partial_evidence": outcome == "partial",
    }
    for forbidden in ("text", "words", "path", "DSN", "diagnostic", "private", "C:/", "worker"):
        assert forbidden not in response.text
    # A configured profile change hides the prior operation, not asset evidence.
    config = h.components.configuration
    local = config.deployment.local_transcription
    assert local is not None
    h.components.configuration = config.model_copy(update={"deployment":
        config.deployment.model_copy(update={"local_transcription":
            local.model_copy(update={"execution_profile_version": "v2"})})})
    assert client.get(url, headers=HEADERS).json()["operation"] is None
    assert client.get(url, headers=HEADERS).json()["complete_evidence"] == (outcome == "complete")


@pytest.mark.parametrize("outcome", ["complete", "partial", "failed"])
def test_status_memory(monkeypatch: pytest.MonkeyPatch, outcome: str) -> None:
    exercise_status(Harness(monkeypatch), monkeypatch, outcome)


@pytest.mark.parametrize("outcome", ["complete", "partial", "failed"])
def test_status_postgres(render_postgres_dsn: str, monkeypatch: pytest.MonkeyPatch,
                         outcome: str) -> None:
    exercise_status(Harness(monkeypatch, render_postgres_dsn), monkeypatch, outcome)


def test_status_missing_composition_and_storage_are_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = cast(Client, TestClient(create_app()))
    url = f"/api/v1/transcription/assets/{EntityId.new().value}/status"
    assert client.get(url, headers=HEADERS).json() == {"detail": "kernel_not_configured"}
    h = Harness(monkeypatch)
    asset = h.asset(0)
    client = client_for(h, monkeypatch)
    url = f"/api/v1/transcription/assets/{asset.id.value}/status"
    for error in (WorkExecutionStorageUnavailableError, KernelStorageUnavailableError):
        monkeypatch.setattr(transcription, "_repository", Mock(side_effect=error("private DSN")))
        response = client.get(url, headers=HEADERS)
        assert response.status_code == 503
        assert response.json() == {"detail": "postgresql_unavailable"}
    config = h.components.configuration
    h.components.configuration = config.model_copy(update={"deployment":
        config.deployment.model_copy(update={"local_transcription": None})})
    response = client.get(url, headers=HEADERS)
    assert response.status_code == 503
    assert response.json() == {"detail": "local_transcription_not_configured"}



def test_status_postgres_complete_survives_later_partial_and_profile_change(
    render_postgres_dsn: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    h = Harness(monkeypatch, render_postgres_dsn)
    asset = h.asset(0)
    client = client_for(h, monkeypatch)
    url = f"/api/v1/transcription/assets/{asset.id.value}/status"
    operation = h.reconcile().operations[0]
    claim = h.claim()
    complete = h.repository.apply_transcript_result(claim,
        prepare_transcript_evidence(claim, transcript_result()))
    # Same asset/manifest, distinct input; later partial evidence is retained.
    request = enqueue_request(replace(operation.input, requested_language="en"))
    h.application.work.enqueue(replace(request, event_id=h.event,
        idempotency_key="synthetic-second-transcript"))
    claim = h.claim()
    partial = replace(transcript_result(), status=TranscriptEvidenceStatus.PARTIAL,
                      partial_reason="synthetic_partial")
    h.repository.apply_transcript_result(claim, prepare_transcript_evidence(claim, partial))
    body = client.get(url, headers=HEADERS).json()
    assert body["complete_evidence"] is True and body["partial_evidence"] is False
    service = SessionSuggestionService(PostgresSuggestionRepository(render_postgres_dsn), h.clock)
    run = service.run(event_id=h.event, stage_id=h.stage, actor_id=EntityId.new())
    assert run.assets[0].transcript is not None
    assert run.assets[0].transcript.id == complete.id
    # Querying a different current profile cannot select either old operation.
    assert h.repository.asset_transcription_status(asset.id, deployment_id="test-deployment",
        execution_profile_id="other-profile", execution_profile_version="v1") == (None, True, False)
    assert h.repository.asset_transcription_status(asset.id, deployment_id="other-deployment",
        execution_profile_id="test-profile", execution_profile_version="v1") == (None, True, False)
