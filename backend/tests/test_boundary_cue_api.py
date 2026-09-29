from typing import cast
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.router import router
from app.api.v1.session_suggestions import service
from app.contexts.editorial.derivation_contracts import EditorialPhraseList
from app.contexts.production.session_suggestions.contracts import SuggestionStorageUnavailableError
from app.shared.ids import EntityId
from tests.test_api_authentication import AUTH_HEADERS, SyncHttpClient
from tests.test_boundary_cue_composition import CONFERENCE
from tests.test_durable_event_mode_kernel import ACTOR_ID
from tests.test_session_suggestions import Harness


def client_for(h: Harness) -> SyncHttpClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[service] = lambda: h.service
    return cast(SyncHttpClient, TestClient(app))


def body() -> dict[str, object]:
    return {"actor_id": ACTOR_ID.value, "command_id": EntityId.new().value,
            "catalog_version": 1, "profile_key": "conference",
            "group_keys": list(CONFERENCE.group_keys)}


def test_authenticated_catalog_publication_history_and_run_references() -> None:
    h = Harness()
    client = client_for(h)
    root = f"/api/v1/session-suggestions/events/{h.event.value}"
    for path in ("boundary-cue-catalog", "boundary-cues", "boundary-cues/history"):
        assert client.get(f"{root}/{path}").status_code == 401
    assert client.post(f"{root}/boundary-cues", json=body()).status_code == 401
    catalog = client.get(f"{root}/boundary-cue-catalog", headers=AUTH_HEADERS).json()
    assert catalog["id"] == "boundary-cue-catalog"
    assert len(catalog["groups"]) == 21 and len(catalog["profiles"]) == 11
    assert len(catalog["digest"]) == 64
    assert client.get(f"{root}/boundary-cues", headers=AUTH_HEADERS).json() == {"current": None}
    request = body()
    first = client.post(f"{root}/boundary-cues", headers=AUTH_HEADERS, json=request)
    assert first.status_code == 200
    data = first.json()
    assert data["catalog_digest"] == catalog["digest"]
    assert data["composed_by"] == ACTOR_ID.value and data["version"] == 1
    assert client.post(f"{root}/boundary-cues", headers=AUTH_HEADERS,
                       json=request).json() == data
    conflict = client.post(f"{root}/boundary-cues", headers=AUTH_HEADERS,
                           json={**request, "profile_key": None})
    assert conflict.status_code == 409
    second = client.post(f"{root}/boundary-cues", headers=AUTH_HEADERS, json=body()).json()
    assert second["version"] == 2
    assert client.get(f"{root}/boundary-cues", headers=AUTH_HEADERS).json()["current"] == second
    page = client.get(f"{root}/boundary-cues/history?limit=1", headers=AUTH_HEADERS).json()
    assert page["items"] == [data] and page["next_after"] == 1
    page = client.get(f"{root}/boundary-cues/history?after=1", headers=AUTH_HEADERS).json()
    assert page["items"] == [second] and page["next_after"] is None
    run = client.post(f"{root}/stages/{h.stage.value}/runs", headers=AUTH_HEADERS,
                      json={"actor_id": ACTOR_ID.value}).json()
    assert run["start_cue_list"] == second["start_cue_list"]
    assert run["end_cue_list"] == second["end_cue_list"]
    other = root.replace(h.event.value, EntityId.new().value)
    assert client.get(f"{other}/boundary-cues", headers=AUTH_HEADERS).status_code == 404
    assert client.post(f"{other}/boundary-cues", headers=AUTH_HEADERS,
                       json=body()).status_code == 404
    with patch.object(h.repository, "transaction", side_effect=SuggestionStorageUnavailableError):
        assert client.get(f"{root}/boundary-cues", headers=AUTH_HEADERS).status_code == 503


def test_editorial_publish_conflict_returns_409_and_rolls_back() -> None:
    h = Harness()
    # Simulate a conflicting reserved end-list version at the persistence boundary.
    # The first (start) insert must roll back when the second (end) insert conflicts.
    h.repository.editorial.events.add(h.event)
    existing = h.repository.editorial.publish(EditorialPhraseList(
        EntityId.new(), h.event, "boundary-cues-end", 1, "Existing end cues",
        ("Synthetic closing",), ACTOR_ID, h.service.clock.now()))
    with patch.object(h.repository, "publish_cue_list", side_effect=h.repository.editorial.publish):
        response = client_for(h).post(
            f"/api/v1/session-suggestions/events/{h.event.value}/boundary-cues",
            headers=AUTH_HEADERS, json=body())
    assert response.status_code == 409
    assert response.json() == {"detail": "phrase_list_version_exists"}
    assert not h.repository.compositions
    assert h.repository.editorial.phrases == {(existing.id, existing.version): existing}


@pytest.mark.parametrize("change", [
    {"catalog_version": 2}, {"catalog_version": True}, {"group_keys": ["absent"]},
    {"profile_key": "absent"}, {"group_keys": ["press"] * 21},
    {"group_keys": ["x" * 101]}, {"authority_kind": "automatic"}, {"unexpected": True},
    {"custom_phrases": [{"text": "inside", "role": "segment"}]},
    {"custom_phrases": [{"text": "!!!", "role": "start"}]},
    {"custom_phrases": [{"text": "x" * 101, "role": "start"}]},
    {"custom_phrases": [{"text": "x", "role": "start"}] * 401},
    {"include": [{"group_key": "conference.mc-handoffs", "phrase": "please welcome"}]},
    {"exclude": [{"group_key": "conference.mc-handoffs", "phrase": "ladies and gentlemen"}]},
])
def test_bounded_composition_refusals_have_no_writes(change: dict[str, object]) -> None:
    h = Harness()
    client = client_for(h)
    response = client.post(f"/api/v1/session-suggestions/events/{h.event.value}/boundary-cues",
                           headers=AUTH_HEADERS, json={**body(), **change})
    assert response.status_code == 422
    assert not h.repository.compositions and not h.repository.editorial.phrases


@pytest.mark.parametrize("count", [0, 201])
def test_size_refusal_has_structured_count(count: int) -> None:
    h = Harness()
    response = client_for(h).post(
        f"/api/v1/session-suggestions/events/{h.event.value}/boundary-cues",
        headers=AUTH_HEADERS, json={**body(), "group_keys": [], "custom_phrases": [
            {"text": f"Synthetic cue {n}", "role": "changeover"} for n in range(count)]})
    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "cue_list_empty" if count == 0 else "cue_list_too_large",
        "role": "start", "count": count}


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "after=-1", "after=2147483648"])
def test_history_bounds(query: str) -> None:
    h = Harness()
    assert client_for(h).get(
        f"/api/v1/session-suggestions/events/{h.event.value}/boundary-cues/history?{query}",
        headers=AUTH_HEADERS).status_code == 422
