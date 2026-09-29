from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from datetime import datetime
from typing import Any, cast
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.router import router
from app.api.v1.session_suggestions import service
from app.contexts.production.session_suggestions.contracts import (
    ScheduleOffsetEntry,
    ScheduleOffsetSetting,
    SuggestionConflictError,
    SuggestionNotFoundError,
)
from app.shared.ids import EntityId
from tests.test_api_authentication import AUTH_HEADERS, SyncHttpClient
from tests.test_durable_event_mode_kernel import ACTOR_ID
from tests.test_session_suggestion_policy import at
from tests.test_session_suggestions import Harness


def test_setting_replay_clear_history_digest_and_no_kernel_mutations() -> None:
    h = Harness()
    original = h.run()
    command = EntityId.new()
    entries = (ScheduleOffsetEntry(at(0), 0),)
    assert h.service.current_offset(h.event, h.stage) is None
    first = h.service.set_offset(event_id=h.event, stage_id=h.stage, command_id=command,
                                 actor_id=ACTOR_ID, entries=entries)
    run = h.run()
    assert run.id != original.id and run.input_digest != original.input_digest
    assert run.override_setting_version == 1
    assert run.blocks[0].override_setting_version == 1
    assert run.blocks[0].schedule_offset_source == "producer"
    assert h.run() == run
    cleared = h.service.set_offset(event_id=h.event, stage_id=h.stage, command_id=EntityId.new(),
                                   actor_id=ACTOR_ID, entries=())
    assert cleared.version == 2 and cleared.entries == ()
    assert h.service.current_offset(h.event, h.stage) == cleared
    latest = h.run()
    assert latest.input_digest != original.input_digest and latest.input_digest != run.input_digest
    assert latest.override_setting_version == 2
    assert latest.blocks[0].override_setting_version is None
    assert latest.blocks[0].schedule_offset_source == "none"
    assert h.service.set_offset(event_id=h.event, stage_id=h.stage, command_id=command,
                                actor_id=ACTOR_ID, entries=entries) == first
    assert h.service.current_offset(h.event, h.stage) == cleared
    with pytest.raises(SuggestionConflictError, match="command_id_conflict"):
        h.service.set_offset(event_id=h.event, stage_id=h.stage, command_id=command,
                             actor_id=ACTOR_ID, entries=())
    assert h.service.offset_history(h.event, h.stage, limit=1) == ((first,), 1)
    assert h.service.offset_history(h.event, h.stage, after=1) == ((cleared,), None)
    with pytest.raises(FrozenInstanceError):
        first.entries[0].offset_seconds = 600  # type: ignore[misc]
    assert h.kernel_repo.get_program_expectation(h.expectation.id) == h.expectation
    assert not h.kernel_repo.list_sessions_for_stage(h.stage)


@pytest.mark.parametrize("value", [-7201, 7201, True, 1.5, "600"])
def test_offset_bounds_reject_nonintegers(value: Any) -> None:
    with pytest.raises(ValueError):
        ScheduleOffsetEntry(at(0), value)


@pytest.mark.parametrize("value", [-7200, 0, 7200])
def test_inclusive_offset_bounds(value: int) -> None:
    assert ScheduleOffsetEntry(at(0), value).offset_seconds == value


def test_entry_order_count_awareness_and_history_bounds() -> None:
    h = Harness()
    with pytest.raises(ValueError):
        ScheduleOffsetEntry(datetime(2026, 1, 1), 0)
    for entries in ((ScheduleOffsetEntry(at(1), 0), ScheduleOffsetEntry(at(0), 0)),
                    (ScheduleOffsetEntry(at(0), 0),) * 2,
                    tuple(ScheduleOffsetEntry(at(i), 0) for i in range(21))):
        with pytest.raises(ValueError):
            h.service.set_offset(event_id=h.event, stage_id=h.stage, command_id=EntityId.new(),
                                 actor_id=ACTOR_ID, entries=entries)
    for after, limit in ((-1, 1), (2_147_483_648, 1), (0, 0), (0, 101)):
        with pytest.raises(ValueError):
            h.service.offset_history(h.event, h.stage, after=after, limit=limit)
    entries = tuple(ScheduleOffsetEntry(at(i), 0) for i in range(20))
    result = h.service.set_offset(event_id=h.event, stage_id=h.stage, command_id=EntityId.new(),
                                  actor_id=ACTOR_ID, entries=entries)
    assert len(result.entries) == 20


def test_scope_concurrent_replay_and_transaction_rollback() -> None:
    h = Harness()
    command = EntityId.new()

    def set_once(_: int) -> ScheduleOffsetSetting:
        return h.service.set_offset(event_id=h.event, stage_id=h.stage, command_id=command,
                                    actor_id=ACTOR_ID, entries=())

    with ThreadPoolExecutor(max_workers=4) as pool:
        values = list(pool.map(set_once, range(8)))
    assert all(v == values[0] for v in values) and len(h.repository.offsets) == 1
    for read in (h.service.current_offset, h.service.offset_history):
        with pytest.raises(SuggestionNotFoundError):
            read(EntityId.new(), h.stage)
    original = h.repository.save_offset

    def crash(setting: ScheduleOffsetSetting) -> None:
        original(setting)
        raise RuntimeError("crash")

    with patch.object(h.repository, "save_offset", side_effect=crash):
        with pytest.raises(RuntimeError, match="crash"):
            h.service.set_offset(event_id=h.event, stage_id=h.stage, command_id=EntityId.new(),
                                 actor_id=ACTOR_ID, entries=())
    assert h.service.current_offset(h.event, h.stage) == values[0]
    with pytest.raises(SuggestionConflictError):
        h.service.set_offset(event_id=h.event, stage_id=h.stage, command_id=command,
                             actor_id=EntityId.new(), entries=())
    with pytest.raises(ValueError):
        replace(values[0], version=0)


def test_authenticated_override_api_history_scope_replay_and_v3_response() -> None:
    h = Harness()
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[service] = lambda: h.service
    client = cast(SyncHttpClient, TestClient(app))
    stage = f"/api/v1/session-suggestions/events/{h.event.value}/stages/{h.stage.value}"
    path = f"{stage}/schedule-offset"
    body = {"actor_id": ACTOR_ID.value, "command_id": EntityId.new().value,
            "entries": [{"effective_from": at(0).isoformat(), "offset_seconds": 0}]}
    assert client.get(path).status_code == 401
    assert client.get(path + "/history").status_code == 401
    assert client.post(path, json=body).status_code == 401
    assert client.get(path, headers=AUTH_HEADERS).json() == {"current": None}
    first = client.post(path, json=body, headers=AUTH_HEADERS)
    assert first.status_code == 200
    assert first.json()["version"] == 1 and first.json()["set_by"] == ACTOR_ID.value
    assert client.post(path, json=body, headers=AUTH_HEADERS).json() == first.json()
    assert client.get(path, headers=AUTH_HEADERS).json()["current"] == first.json()
    run = client.post(stage + "/runs", json={"actor_id": ACTOR_ID.value}, headers=AUTH_HEADERS)
    assert run.json()["override_setting_version"] == 1
    assert run.json()["blocks"][0]["schedule_offset_source"] == "producer"
    item = client.get(stage + "/suggestions", headers=AUTH_HEADERS).json()["items"][0]
    assert item["schedule_offset_seconds"] == 0 and item["schedule_offset_source"] == "producer"
    assert client.post(path, json={**body, "entries": []}, headers=AUTH_HEADERS).status_code == 409
    clear = {**body, "command_id": EntityId.new().value, "entries": []}
    assert client.post(path, json=clear, headers=AUTH_HEADERS).status_code == 200
    history = client.get(path + "/history?limit=1", headers=AUTH_HEADERS).json()
    assert history["items"] == [first.json()] and history["next_after"] == 1
    assert client.get(path + "/history?after=1", headers=AUTH_HEADERS).json()["items"][0][
        "entries"] == []
    other = path.replace(h.event.value, EntityId.new().value)
    assert client.get(other, headers=AUTH_HEADERS).status_code == 404
    assert client.get(other + "/history", headers=AUTH_HEADERS).status_code == 404
    assert client.post(other, json=body, headers=AUTH_HEADERS).status_code == 404
    for suffix in ("?limit=101", "?after=-1", "?after=2147483648"):
        assert client.get(path + "/history" + suffix, headers=AUTH_HEADERS).status_code == 422
    for entries in ([{"effective_from": "2026-01-01T00:00:00", "offset_seconds": 0}],
                    [{"effective_from": at(0).isoformat(), "offset_seconds": True}],
                    [{"effective_from": at(0).isoformat(), "offset_seconds": 7201}],
                    body["entries"] * 2, body["entries"] * 21):
        assert client.post(path, json={**body, "entries": entries},
                           headers=AUTH_HEADERS).status_code == 422
