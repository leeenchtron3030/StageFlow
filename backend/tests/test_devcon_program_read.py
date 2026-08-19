from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest

from app.contexts.events import EventStageBootstrapRequest, StageBootstrapDefinition
from app.contexts.integration.devcon import (
    DevconProgramSync,
    ExternalProgramItem,
)
from app.contexts.production.event_mode_kernel import InMemoryEventModeKernelRepository
from app.core.config.deployment import DevconReadConfiguration
from app.infrastructure.devcon import (
    DevconContractError,
    DevconPublicProgramAdapter,
    DevconReadError,
)
from app.shared.ids import EntityId
from app.shared.time import FixedClock

NOW = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
ACTOR_ID = EntityId("41000000-0000-0000-0000-000000000001")


def _session(
    session_id: str,
    *,
    event_id: str = "test-devcon-8",
    room_id: str = "stage-1",
    start_ms: int = 1_793_674_800_000,
) -> dict[str, object]:
    return {
        "id": session_id,
        "eventId": event_id,
        "title": f"Program {session_id}",
        "slot_roomId": room_id,
        "slot_room": {"id": room_id, "name": "Stage 1", "eventId": event_id},
        "slot_start": start_ms,
        "slot_end": start_ms + 1_800_000,
        "speakers": [{"id": "speaker", "name": "Ada"}],
    }


def _configuration(**updates: object) -> DevconReadConfiguration:
    values: dict[str, object] = {
        "event_id": "test-devcon-8",
        "room_id": "stage-1",
        "page_size": 2,
        "maximum_catalog_sessions": 10,
        "timeout_seconds": 5,
    }
    values.update(updates)
    return DevconReadConfiguration.model_validate(values)


def test_public_adapter_paginates_and_filters_unreliable_server_results() -> None:
    catalog = [
        _session("later", start_ms=1_793_676_600_000),
        _session("other-event", event_id="devcon-7"),
        _session("first", start_ms=1_793_674_800_000),
        _session("other-room", room_id="stage-2"),
    ]
    observed_urls: list[str] = []

    def fetch(url: str, timeout: int, maximum_bytes: int) -> Mapping[str, object]:
        observed_urls.append(url)
        assert timeout == 5
        assert maximum_bytes == 8 * 1024 * 1024
        query = parse_qs(urlsplit(url).query)
        assert query["event"] == ["test-devcon-8"]
        assert query["room"] == ["stage-1"]
        offset = int(query["from"][0])
        size = int(query["size"][0])
        return {
            "status": 200,
            "data": {
                "currentPage": offset + 1,
                "total": len(catalog),
                "items": catalog[offset : offset + size],
            },
        }

    result = DevconPublicProgramAdapter(
        _configuration(), fetch_json=fetch
    ).fetch_program()

    assert [item.session_id for item in result] == ["first", "later"]
    assert result[0].speakers == ("Ada",)
    assert result[0].planned_start == datetime(2026, 11, 3, 3, 0, tzinfo=UTC)
    assert len(observed_urls) == 2


def test_public_adapter_enforces_catalog_and_contract_bounds() -> None:
    def oversized(
        url: str, timeout: int, maximum_bytes: int
    ) -> Mapping[str, object]:
        del url, timeout, maximum_bytes
        return {"status": 200, "data": {"total": 11, "items": []}}

    with pytest.raises(DevconReadError, match="configured_bound"):
        DevconPublicProgramAdapter(
            _configuration(), fetch_json=oversized
        ).fetch_program()

    invalid = _session("invalid")
    invalid["slot_start"] = None

    def malformed(
        url: str, timeout: int, maximum_bytes: int
    ) -> Mapping[str, object]:
        del url, timeout, maximum_bytes
        return {"status": 200, "data": {"total": 1, "items": [invalid]}}

    with pytest.raises(DevconContractError, match="slot_start"):
        DevconPublicProgramAdapter(
            _configuration(), fetch_json=malformed
        ).fetch_program()


class MutableProgramSource:
    def __init__(self, items: tuple[ExternalProgramItem, ...]) -> None:
        self.items = items
        self.available = True
        self.calls = 0

    def fetch_program(self) -> tuple[ExternalProgramItem, ...]:
        self.calls += 1
        if not self.available:
            raise DevconReadError("devcon_read_unavailable")
        return self.items


def test_sync_records_external_expectations_without_realizing_session_and_caches() -> None:
    repository = InMemoryEventModeKernelRepository()
    bootstrapped = repository.bootstrap(
        EventStageBootstrapRequest(
            operation_id=EntityId("41000000-0000-0000-0000-000000000002"),
            event_key="demo-event",
            event_name="Demo Event",
            stages=(
                StageBootstrapDefinition(
                    key="main",
                    name="Main",
                    source_bindings={"vmix": "C:/StageFlowDemo/recordings"},
                ),
            ),
            actor_id=ACTOR_ID,
            requested_at=NOW,
        )
    )
    assert bootstrapped.event is not None
    stage = bootstrapped.stages[0]
    source = MutableProgramSource(
        (
            ExternalProgramItem(
                event_id="test-devcon-8",
                session_id="real-program-item",
                room_id="stage-1",
                room_name="Stage 1",
                title="A real external program item",
                speakers=("Ada",),
                planned_start=NOW + timedelta(hours=1),
                planned_end=NOW + timedelta(hours=2),
            ),
        )
    )
    sync = DevconProgramSync(
        repository=repository,
        source=source,
        clock=FixedClock(NOW),
    )

    result = sync.synchronize(event_id=bootstrapped.event.id, stage_id=stage.id)

    assert len(result.expectations) == 1
    expectation = result.expectations[0]
    assert expectation.stage_id == stage.id
    assert expectation.external_references == {
        "devcon_event_id": "test-devcon-8",
        "devcon_room_id": "stage-1",
        "devcon_room_name": "Stage 1",
        "devcon_session_id": "real-program-item",
        "provider": "devcon",
    }
    assert repository.list_sessions_for_stage(stage.id) == ()

    source.available = False
    assert sync.cached_program(event_id=bootstrapped.event.id) == (expectation,)
    assert source.calls == 1
