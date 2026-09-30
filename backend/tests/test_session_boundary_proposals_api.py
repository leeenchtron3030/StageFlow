"""Authenticated and bounded Session refinement endpoints."""
from unittest.mock import patch

import pytest

from app.contexts.production.session_suggestions.contracts import SuggestionStorageUnavailableError
from app.shared.ids import EntityId
from app.shared.time import FixedClock
from tests.test_api_authentication import AUTH_HEADERS
from tests.test_durable_event_mode_kernel import ACTOR_ID
from tests.test_session_boundary_proposals import boundaries, proposal, realized
from tests.test_session_suggestion_policy import at
from tests.test_session_suggestions_surfaces import client_for


def test_boundary_api_authentication_shapes_apply_dismiss_history_and_run_count() -> None:
    h, session, _ = realized()
    client = client_for(h)
    root = f"/api/v1/session-suggestions/events/{h.event}"
    path = f"{root}/sessions/{session.id}/boundary-proposals"
    body = {"actor_id": ACTOR_ID.value, "command_id": EntityId.new().value}
    p = proposal(h, session)
    for url in (path, path + "/history"):
        assert client.get(url).status_code == 401
    for action in ("apply", "dismiss"):
        assert client.post(f"{path}/{p.id}/{action}", json=body).status_code == 401
    run = client.post(f"{root}/stages/{h.stage}/runs", headers=AUTH_HEADERS,
                       json={"actor_id": ACTOR_ID.value})
    assert run.status_code == 200 and run.json()["boundary_proposals_created"] == 1
    assert client.get(f"{root}/stages/{h.stage}/runs/latest",
                      headers=AUTH_HEADERS).json() == run.json()
    response = client.get(path, headers=AUTH_HEADERS)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    assert all(i["authorized_use"] == "advisory_only" and i["evidence_ids"] for i in items)
    start = next(i for i in items if i["boundary_kind"] == "start")
    end = next(i for i in items if i["boundary_kind"] == "end")
    assert start["proposal_id"] == p.id.value
    applied = client.post(f"{path}/{p.id}/apply", headers=AUTH_HEADERS, json=body)
    assert applied.status_code == 200 and applied.json()["kind"] == "applied"
    replay = client.post(f"{path}/{p.id}/apply", headers=AUTH_HEADERS, json=body)
    assert replay.json() == applied.json()
    assert client.post(f"{path}/{p.id}/dismiss", headers=AUTH_HEADERS, json={
        **body, "command_id": EntityId.new().value,
    }).json() == {"detail": "boundary_proposal_decided"}
    dismissed = client.post(f"{path}/{end['proposal_id']}/dismiss", headers=AUTH_HEADERS, json={
        **body, "command_id": EntityId.new().value, "reason": "  Keep current end  ",
    })
    assert dismissed.status_code == 200 and dismissed.json()["reason"] == "Keep current end"
    assert not client.get(path, headers=AUTH_HEADERS).json()["items"]
    first = client.get(path + "/history?limit=1", headers=AUTH_HEADERS).json()
    second = client.get(path + f"/history?limit=1&after={first['next_after']}",
                        headers=AUTH_HEADERS).json()
    assert len(first["items"]) == len(second["items"]) == 1
    assert first["next_after"] and second["next_after"] is None
    history = {row["proposal_id"]: row for row in first["items"] + second["items"]}
    assert history == {
        p.id.value: {**applied.json(), "boundary_kind": "start"},
        end["proposal_id"]: {**dismissed.json(), "boundary_kind": "end"},
    }
    assert "boundary_kind" not in applied.json() and "boundary_kind" not in dismissed.json()


@pytest.mark.parametrize("action", ["apply", "dismiss"])
def test_boundary_api_scope_stale_bounds_human_and_storage_errors(action: str) -> None:
    h, session, _ = realized()
    p = proposal(h, session)
    client = client_for(h)
    path = f"/api/v1/session-suggestions/events/{h.event}/sessions/{session.id}/boundary-proposals"
    url = f"{path}/{p.id}/{action}"
    body = {"actor_id": ACTOR_ID.value, "command_id": EntityId.new().value}
    for original in (h.event.value, session.id.value, p.id.value):
        assert client.post(url.replace(original, EntityId.new().value),
                           headers=AUTH_HEADERS, json=body).status_code == 404
    for extra in ({"authority_kind": "automatic"}, {"unknown": 1}):
        assert client.post(url, headers=AUTH_HEADERS, json={**body, **extra}).status_code == 422
    for limit in (0, 101):
        assert client.get(path + f"/history?limit={limit}", headers=AUTH_HEADERS).status_code == 422
    if action == "dismiss":
        for reason in ("x" * 501, "", " ", "x\x00y"):
            assert client.post(url, headers=AUTH_HEADERS,
                               json={**body, "reason": reason}).status_code == 422
    with patch.object(h.repository, "transaction",
                      side_effect=SuggestionStorageUnavailableError("postgresql_unavailable")):
        assert client.get(path, headers=AUTH_HEADERS).status_code == 503
        assert client.post(url, headers=AUTH_HEADERS, json=body).status_code == 503
    h.service.clock = FixedClock(at(2))
    proposal(h, session, seconds=10)
    stale = client.post(url, headers=AUTH_HEADERS, json=body)
    assert stale.status_code == 409 and stale.json() == {"detail": "boundary_proposal_stale"}
    assert len(boundaries(h).open(h.event, session.id)) == 1
