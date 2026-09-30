"""Synthetic latest-run and merged Work Queue read contracts."""
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.router import router
from app.api.v1.session_suggestions import service
from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.editorial.derivation_contracts import EditorialPhraseList
from app.contexts.production.event_mode_kernel.contracts import (
    ProducerWorkQueuePosition,
    ProducerWorkQueueSubject,
)
from app.contexts.production.event_mode_kernel.service import DurableEventModeKernel
from app.contexts.production.session_suggestions.contracts import (
    ScheduleOffsetEntry,
    Strength,
    SuggestionNotFoundError,
    SuggestionStatus,
    SuggestionStorageUnavailableError,
)
from app.contexts.production.session_suggestions.memory import InMemorySuggestionRepository
from app.contexts.production.session_suggestions.service import SessionSuggestionService
from app.contexts.production.work_queue import ProducerWorkQueueService
from app.core.config.deployment import EffectiveKernelConfiguration
from app.shared.ids import EntityId
from app.shared.time import FixedClock
from tests.test_api_authentication import AUTH_HEADERS, SyncHttpClient
from tests.test_durable_event_mode_kernel import ACTOR_ID
from tests.test_session_suggestion_policy import NOW, asset, at
from tests.test_session_suggestions import Harness
from tests.test_work_queue_assembly import QueueHarness, kernel_world


def client_for(h: Harness) -> SyncHttpClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[service] = lambda: h.service
    return cast(SyncHttpClient, TestClient(app))


def test_latest_run_api_authentication_absence_lineage_and_scope() -> None:
    h = Harness()
    client = client_for(h)
    url = f"/api/v1/session-suggestions/events/{h.event}/stages/{h.stage}/runs"
    assert client.get(url + "/latest").status_code == 401
    absent = client.get(url + "/latest", headers=AUTH_HEADERS)
    assert absent.status_code == 404
    assert absent.json() == {"detail": "suggestion_run_not_found"}
    phrase_id = EntityId.new()
    h.repository.editorial.phrases[phrase_id, 1] = EditorialPhraseList(
        phrase_id, h.event, "cues", 1, "Cues", ("welcome",), ACTOR_ID, NOW)
    h.service.set_offset(event_id=h.event, stage_id=h.stage, command_id=EntityId.new(),
                         actor_id=ACTOR_ID, entries=(ScheduleOffsetEntry(at(0), 120),))
    cue = {"id": phrase_id.value, "version": 1}
    response = client.post(url, headers=AUTH_HEADERS, json={
        "actor_id": ACTOR_ID.value, "start_cue_list": cue, "end_cue_list": cue,
    })
    assert response.status_code == 200
    latest = client.get(url + "/latest", headers=AUTH_HEADERS)
    assert latest.status_code == 200 and latest.json() == response.json()
    body = latest.json()
    assert body["actor_id"] == ACTOR_ID.value and body["created_at"] == "2026-01-01T00:00:00Z"
    assert body["policy"]["id"] == "boundary-suggestion" and body["policy"]["version"] == "3"
    assert len(body["input_digest"]) == 64 and body["skips"]["no_timing_evidence"] == 0
    assert body["start_cue_list"] == body["end_cue_list"] == cue
    assert body["override_setting_version"] == 1
    assert body["blocks"] == [{
        "ordinal": 0, "first_planned_start": "2026-01-01T00:00:00Z",
        "last_planned_start": "2026-01-01T00:00:00Z", "talk_count": 1,
        "schedule_offset_seconds": 120, "schedule_offset_source": "producer",
        "estimate_score_margin": 0.0, "override_setting_version": 1,
    }]
    assert client.get(url.replace(h.event.value, EntityId.new().value) + "/latest",
                      headers=AUTH_HEADERS).status_code == 404
    assert client.get(url.replace(h.stage.value, EntityId.new().value) + "/latest",
                      headers=AUTH_HEADERS).status_code == 404
    assert not h.kernel_repo.list_sessions_for_stage(h.stage)


def test_latest_run_uses_insertion_order_and_empty_runs_supersede() -> None:
    h = Harness()
    with pytest.raises(SuggestionNotFoundError, match="suggestion_run_not_found"):
        h.service.latest_run(h.event, h.stage)
    first = h.run()
    assert h.service.latest_run(h.event, h.stage) == first
    h.repository.assets[h.stage] = ()
    h.service.clock = FixedClock(NOW - timedelta(days=1))
    latest = h.run()
    assert latest.created_at < first.created_at
    assert h.service.latest_run(h.event, h.stage) == latest
    assert not h.service.list_pending_confirmations(h.event)
    with pytest.raises(FrozenInstanceError):
        attribute = "blocks"
        setattr(latest, attribute, ())


@pytest.mark.parametrize("decision", ["confirm", "reject"])
def test_pending_item_exact_counts_read_only_and_disappears_after_decision(decision: str) -> None:
    h = Harness()
    suggestion = h.suggestion()
    # Add a distinct weak suggestion to verify counts exclude decided suggestions.
    weak = replace(suggestion, id=EntityId.new(),
                   candidate=replace(suggestion.candidate, overlap=True, strength=Strength.WEAK))
    h.repository.suggestions[weak.id] = weak
    before = (dict(h.repository.runs), dict(h.repository.suggestions), dict(h.repository.decisions))
    item, = h.service.list_pending_confirmations(h.event)
    assert item.projection_id == f"suggestions:{h.stage}"
    assert item.subject_id == suggestion.run_id and item.subject_revision == 1
    assert item.decision_type.value == "presentation_confirmation_pending"
    assert item.subject_kind.value == "stage_suggestions"
    assert (item.event_id, item.stage_id, item.session_id) == (h.event, h.stage, None)
    assert item.priority == 6 and item.action_reference == f"stage:{h.stage}:suggestions"
    assert item.created_at == item.updated_at == NOW
    expected_weak = 1 + (suggestion.candidate.strength == Strength.WEAK)
    assert set(item.reason_codes) == {
        "presentation_confirmation_pending", "open_count:2", f"weak_count:{expected_weak}",
    }
    assert (h.repository.runs, h.repository.suggestions, h.repository.decisions) == before
    assert h.service.list_pending_confirmations(EntityId.new()) == ()
    with pytest.raises(FrozenInstanceError):
        attribute = "priority"
        setattr(item, attribute, 1)
    h.service.reject(event_id=h.event, suggestion_id=weak.id, command_id=EntityId.new(),
                     actor_id=ACTOR_ID, reason="Synthetic duplicate")
    remaining, = h.service.list_pending_confirmations(h.event)
    assert "open_count:1" in remaining.reason_codes
    assert f"weak_count:{expected_weak - 1}" in remaining.reason_codes
    assert remaining.position == item.position
    if decision == "confirm":
        h.service.confirm(event_id=h.event, suggestion_id=suggestion.id,
                          command_id=EntityId.new(), actor_id=ACTOR_ID)
    else:
        h.service.reject(event_id=h.event, suggestion_id=suggestion.id,
                         command_id=EntityId.new(), actor_id=ACTOR_ID, reason="Synthetic review")
    assert h.service.list_pending_confirmations(h.event) == ()


def test_superseded_open_suggestions_are_not_counted_and_projection_identity_is_stable() -> None:
    h = Harness()
    first = h.suggestion()
    original, = h.service.list_pending_confirmations(h.event)
    h.repository.assets[h.stage] = (replace(asset(0, 1800), segmentation_ids=()),)
    second = h.run()
    latest, = h.service.list_pending_confirmations(h.event)
    assert latest.projection_id == original.projection_id
    assert latest.subject_id == second.id != original.subject_id
    assert "open_count:1" in latest.reason_codes
    assert h.service.read(h.event, first.id)[1] == SuggestionStatus.SUPERSEDED
    h.repository.assets[h.stage] = ()
    empty = h.run()
    assert h.service.latest_run(h.event, h.stage) == empty
    assert h.service.list_pending_confirmations(h.event) == ()


def mixed_queue() -> tuple[SyncHttpClient, ProducerWorkQueueService, EntityId]:
    kernel, event = kernel_world()
    assemblies = QueueHarness(event, count=3)
    repo = InMemorySuggestionRepository(kernel)
    suggestions = SessionSuggestionService(repo, FixedClock(NOW))
    for stage in reversed(kernel.list_stages(event)):
        repo.assets[stage.id] = (asset(0, 1800),)
        suggestions.run(event_id=event, stage_id=stage.id, actor_id=ACTOR_ID)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.state.kernel = KernelComponents(
        cast(EffectiveKernelConfiguration, None), kernel,
        DurableEventModeKernel(repository=kernel, clock=FixedClock(NOW)),
        session_assemblies=assemblies.service, session_suggestions=suggestions,
    )
    queue = ProducerWorkQueueService(kernel, assemblies.repository, suggestions)
    return cast(SyncHttpClient, TestClient(app)), queue, event


@pytest.mark.parametrize("limit", [1, 4, 7, 100])
def test_three_source_api_order_pagination_truncation_and_replay(
    limit: int,
) -> None:
    client, queue, event = mixed_queue()
    all_items = queue.list_items(event, limit=100)
    assert [i.priority for i in all_items] == [4] * 4 + [5] * 3 + [6] * 4
    expected = [i.projection_id for i in all_items]
    url = f"/api/v1/producer/events/{event}/work-queue?limit={limit}"
    seen: list[str] = []
    cursor: str | None = None
    while True:
        page_url = url + (f"&cursor={cursor}" if cursor else "")
        response = client.get(page_url, headers=AUTH_HEADERS)
        assert response.status_code == 200
        payload = cast(dict[str, Any], response.json())
        assert client.get(page_url, headers=AUTH_HEADERS).json() == payload
        seen.extend(i["item_id"] for i in payload["items"])
        assert len(payload["items"]) <= limit
        assert payload["items_truncated"] == (len(seen) < len(expected))
        for item in payload["items"]:
            if item["priority"] == 6:
                assert item["subject_kind"] == "stage_suggestions"
                assert item["session_id"] is None
        cursor = payload["next_cursor"]
        if cursor is None:
            break
        assert client.get(page_url.replace(event.value, EntityId.new().value)
                          + f"&cursor={cursor}", headers=AUTH_HEADERS).status_code == 422
    assert seen == expected and len(seen) == len(set(seen))


def test_pending_read_cursor_limits_and_application_fetches_sentinel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, queue, event = mixed_queue()
    suggestions = queue.suggestions
    assert suggestions is not None
    items = suggestions.list_pending_confirmations(event, limit=101)
    assert len(items) == 4
    assert suggestions.list_pending_confirmations(event, after=items[0].position, limit=1) == (
        items[1],)
    assert suggestions.list_pending_confirmations(
        event, after=ProducerWorkQueuePosition(7, NOW, "later")) == ()
    for limit in (0, 102, True):
        with pytest.raises(ValueError):
            suggestions.list_pending_confirmations(event, limit=limit)
    calls: list[tuple[EntityId, ProducerWorkQueuePosition | None, int]] = []
    original = suggestions.list_pending_confirmations
    def read(event_id: EntityId, *, after: ProducerWorkQueuePosition | None = None,
             limit: int = 50) -> tuple[ProducerWorkQueueSubject, ...]:
        calls.append((event_id, after, limit))
        return original(event_id, after=after, limit=limit)
    monkeypatch.setattr(suggestions, "list_pending_confirmations", read)
    after = [i.position for i in queue.list_items(event) if i.priority == 5][-1]
    calls.clear()
    assert queue.list_items(event, after=after, limit=1) == items[:2]
    assert calls == [(event, after, 2)]


def test_new_reads_return_bounded_storage_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(*args: object, **kwargs: object) -> object:
        raise SuggestionStorageUnavailableError("private storage diagnostics")
    h = Harness()
    monkeypatch.setattr(h.repository, "latest_run", unavailable)
    response = client_for(h).get(
        f"/api/v1/session-suggestions/events/{h.event}/stages/{h.stage}/runs/latest",
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 503 and response.json() == {"detail": "postgresql_unavailable"}
    client, queue, event = mixed_queue()
    assert queue.suggestions is not None
    monkeypatch.setattr(queue.suggestions, "list_pending_confirmations", unavailable)
    response = client.get(f"/api/v1/producer/events/{event}/work-queue", headers=AUTH_HEADERS)
    assert response.status_code == 503 and response.json() == {"detail": "postgresql_unavailable"}


def test_run_and_latest_api_expose_realized_skip_after_confirm() -> None:
    h = Harness()
    client = client_for(h)
    root = f"/api/v1/session-suggestions/events/{h.event}"
    url = f"{root}/stages/{h.stage}/runs"
    first = client.post(url, headers=AUTH_HEADERS, json={"actor_id": ACTOR_ID.value})
    assert first.status_code == 200 and first.json()["skips"]["already_realized"] == 0
    suggestion, = h.service.page(h.event, h.stage)[0]
    confirmed = client.post(f"{root}/suggestions/{suggestion.id}/confirm", headers=AUTH_HEADERS,
                            json={"actor_id": ACTOR_ID.value, "command_id": EntityId.new().value})
    assert confirmed.status_code == 200
    second = client.post(url, headers=AUTH_HEADERS, json={"actor_id": ACTOR_ID.value})
    assert second.status_code == 200 and second.json()["skips"]["already_realized"] == 1
    assert second.json()["input_digest"] != first.json()["input_digest"]
    latest = client.get(url + "/latest", headers=AUTH_HEADERS)
    assert latest.status_code == 200 and latest.json() == second.json()
    assert h.service.page(h.event, h.stage)[0] == ()
