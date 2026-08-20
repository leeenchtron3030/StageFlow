from __future__ import annotations

from typing import cast

from test_demo_api import NOW, _client  # pyright: ignore[reportPrivateUsage]

from app.contexts.events import ProgramExpectationReconciliation
from app.contexts.integration.devcon import DevconProgramSync
from app.infrastructure.devcon import DevconReadError
from app.shared.ids import EntityId


class StaticSync:
    def __init__(self, result: ProgramExpectationReconciliation) -> None:
        self.result = result

    def synchronize(
        self, *, event_id: EntityId, stage_id: EntityId
    ) -> ProgramExpectationReconciliation:
        assert event_id == self.result.event_id
        assert stage_id == self.result.stage_id
        return self.result


class FailingSync:
    def synchronize(
        self, *, event_id: EntityId, stage_id: EntityId
    ) -> ProgramExpectationReconciliation:
        del event_id, stage_id
        raise DevconReadError("devcon_read_unavailable")


def test_manual_refresh_returns_bounded_external_result_without_session_authority() -> None:
    client, stage_id, components = _client()
    event = components.repository.get_event_by_key(components.event_key)
    assert event is not None
    reconciliation = ProgramExpectationReconciliation(
        event_id=event.id,
        stage_id=EntityId(stage_id),
        provider="devcon",
        synchronization_scope="devcon:test-devcon-8:stage-1",
        synchronized_at=NOW,
        observed=4,
        added=1,
        changed=1,
        unchanged=1,
        withdrawn=1,
        restored=1,
        expectations=(),
        changes=(),
    )
    components.devcon_program_sync = cast(DevconProgramSync, StaticSync(reconciliation))

    response = client.post("/demo/program/refresh", json={})

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.json() == {
        "provider": "devcon",
        "observed": 4,
        "added": 1,
        "changed": 1,
        "unchanged": 1,
        "withdrawn": 1,
        "restored": 1,
        "synchronized_at": reconciliation.synchronized_at.isoformat().replace("+00:00", "Z"),
        "current_expectation_count": 0,
        "changes": [],
        "changes_truncated": False,
        "evidence_kind": "external",
        "authority_notice": ("Program evidence only; no Session authority changed."),
    }
    assert components.repository.list_sessions_for_stage(EntityId(stage_id)) == ()


def test_failed_manual_refresh_uses_last_successful_snapshot_semantics() -> None:
    client, stage_id, components = _client()

    components.devcon_program_sync = cast(DevconProgramSync, FailingSync())

    response = client.post("/demo/program/refresh", json={})

    assert response.status_code == 503
    assert response.json() == {"detail": "program_refresh_failed_using_last_successful_snapshot"}
    assert components.repository.list_sessions_for_stage(EntityId(stage_id)) == ()
