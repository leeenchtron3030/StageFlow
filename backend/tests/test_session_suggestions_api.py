from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.router import router
from app.api.v1.session_suggestions import service
from app.shared.ids import EntityId
from tests.test_api_authentication import AUTH_HEADERS, SyncHttpClient
from tests.test_durable_event_mode_kernel import ACTOR_ID
from tests.test_session_suggestions import Harness


def test_authenticated_bounded_event_scoped_api_shapes_and_errors() -> None:
    h = Harness()
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[service] = lambda: h.service
    client = cast(SyncHttpClient, TestClient(app))
    root = f"/api/v1/session-suggestions/events/{h.event.value}"
    stage = f"{root}/stages/{h.stage.value}"
    actor = {"actor_id": ACTOR_ID.value}
    assert client.post(f"{stage}/runs", json=actor).status_code == 401
    run = client.post(f"{stage}/runs", json=actor, headers=AUTH_HEADERS)
    assert run.status_code == 200 and run.json()["policy"]["version"] == "3"
    assert run.json()["skips"]["no_timing_evidence"] == 0
    assert client.get(f"{stage}/suggestions?limit=101", headers=AUTH_HEADERS).status_code == 422
    invalid = client.get(f"{stage}/suggestions?status=invalid", headers=AUTH_HEADERS)
    assert invalid.status_code == 422
    values = client.get(f"{stage}/suggestions?limit=1", headers=AUTH_HEADERS).json()
    suggestion = values["items"][0]
    assert suggestion["status"] == "open"
    assert suggestion["authorized_use"] == "advisory_only"
    assert suggestion["timing_qualifications"] == ["unqualified"]
    path = f"{root}/suggestions/{suggestion['suggestion_id']}"
    assert client.get(path, headers=AUTH_HEADERS).json() == suggestion
    other = path.replace(h.event.value, EntityId.new().value)
    assert client.get(other, headers=AUTH_HEADERS).status_code == 404
    assert client.post(f"{path}/confirm", headers=AUTH_HEADERS, json={
        **actor, "command_id": EntityId.new().value, "start": "2026-01-01T00:00:00",
    }).status_code == 422
    assert client.post(f"{path}/reject", headers=AUTH_HEADERS, json={
        **actor, "command_id": EntityId.new().value, "reason": "x" * 501,
    }).status_code == 422
    command = {**actor, "command_id": EntityId.new().value}
    confirmed = client.post(f"{path}/confirm", headers=AUTH_HEADERS, json=command)
    assert confirmed.status_code == 200 and confirmed.json()["session_id"]
    replay = client.post(f"{path}/confirm", headers=AUTH_HEADERS, json=command)
    assert replay.json() == confirmed.json()
    assert client.post(f"{path}/reject", headers=AUTH_HEADERS, json={
        **actor, "command_id": EntityId.new().value, "reason": "Different talk",
    }).status_code == 409
    assert client.post(f"{stage}/runs", headers=AUTH_HEADERS, json={
        **actor, "authority_kind": "automatic",
    }).status_code == 422


@pytest.mark.parametrize("cue_field", ["start_cue_list", "end_cue_list"])
@pytest.mark.parametrize("version", [0, -1, 2_147_483_648])
def test_cue_list_version_out_of_bounds_returns_422(cue_field: str, version: int) -> None:
    h = Harness()
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[service] = lambda: h.service
    client = cast(SyncHttpClient, TestClient(app))
    response = client.post(
        f"/api/v1/session-suggestions/events/{h.event.value}/stages/{h.stage.value}/runs",
        headers=AUTH_HEADERS,
        json={"actor_id": ACTOR_ID.value,
              cue_field: {"id": EntityId.new().value, "version": version}},
    )
    assert response.status_code == 422
    assert not h.repository.runs


@pytest.mark.parametrize("cue_field", ["start_cue_list", "end_cue_list"])
@pytest.mark.parametrize("version", [1, 2_147_483_647])
def test_cue_list_version_inclusive_bounds_are_accepted(cue_field: str, version: int) -> None:
    from app.contexts.editorial.derivation_contracts import EditorialPhraseList
    from tests.test_session_suggestion_policy import NOW

    h = Harness()
    phrase_id = EntityId.new()
    h.repository.editorial.phrases[phrase_id, version] = EditorialPhraseList(
        phrase_id, h.event, "cues", version, "Cues", ("welcome",), ACTOR_ID, NOW)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[service] = lambda: h.service
    client = cast(SyncHttpClient, TestClient(app))
    response = client.post(
        f"/api/v1/session-suggestions/events/{h.event.value}/stages/{h.stage.value}/runs",
        headers=AUTH_HEADERS,
        json={"actor_id": ACTOR_ID.value,
              cue_field: {"id": phrase_id.value, "version": version}},
    )
    assert response.status_code == 200
