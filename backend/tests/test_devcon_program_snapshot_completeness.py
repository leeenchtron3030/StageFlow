from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest

from app.contexts.events import EventStageBootstrapRequest, StageBootstrapDefinition
from app.contexts.integration.devcon import DevconProgramSync, ExternalProgramItem
from app.contexts.production.event_mode_kernel import InMemoryEventModeKernelRepository
from app.core.config.deployment import DevconReadConfiguration
from app.infrastructure.devcon import (
    DevconContractError,
    DevconPublicProgramAdapter,
)
from app.shared.ids import EntityId
from app.shared.time import FixedClock

NOW = datetime(2026, 8, 19, 20, 0, tzinfo=UTC)


def _raw(session_id: str) -> dict[str, object]:
    return {
        "id": session_id,
        "eventId": "test-devcon-8",
        "title": f"Program {session_id}",
        "slot_roomId": "stage-1",
        "slot_room": {
            "id": "stage-1",
            "name": "Stage 1",
            "eventId": "test-devcon-8",
        },
        "slot_start": 1_793_674_800_000,
        "slot_end": 1_793_676_600_000,
        "speakers": [{"id": "speaker", "name": "Ada"}],
    }


def _configuration() -> DevconReadConfiguration:
    return DevconReadConfiguration.model_validate(
        {
            "event_id": "test-devcon-8",
            "room_id": "stage-1",
            "page_size": 1,
            "maximum_catalog_sessions": 10,
            "timeout_seconds": 5,
        }
    )


class InitialSource:
    provider = "devcon"
    event_id = "test-devcon-8"
    room_id = "stage-1"

    def fetch_program(self) -> tuple[ExternalProgramItem, ...]:
        return (
            ExternalProgramItem(
                event_id=self.event_id,
                session_id="retained",
                room_id=self.room_id,
                room_name="Stage 1",
                title="Retained",
                speakers=("Ada",),
                planned_start=NOW,
                planned_end=NOW + timedelta(minutes=30),
            ),
        )


def _seed_repository():
    repository = InMemoryEventModeKernelRepository()
    bootstrap = repository.bootstrap(
        EventStageBootstrapRequest(
            operation_id=EntityId("53000000-0000-4000-8000-000000000001"),
            event_key="snapshot-completeness",
            event_name="Snapshot Completeness",
            stages=(
                StageBootstrapDefinition(
                    key="main",
                    name="Main",
                    source_bindings={"vmix": "C:/snapshot-completeness"},
                ),
            ),
            actor_id=EntityId("53000000-0000-4000-8000-000000000002"),
            requested_at=NOW,
        )
    )
    assert bootstrap.event is not None
    event_id = bootstrap.event.id
    stage_id = bootstrap.stages[0].id
    DevconProgramSync(
        repository=repository,
        source=InitialSource(),
        clock=FixedClock(NOW),
    ).synchronize(event_id=event_id, stage_id=stage_id)
    return repository, event_id, stage_id


@pytest.mark.parametrize("failure", ["changed_total", "empty_page"])
def test_incomplete_pagination_cannot_withdraw_previous_snapshot(failure: str) -> None:
    repository, event_id, stage_id = _seed_repository()

    def fetch(url: str, timeout: int, maximum_bytes: int) -> Mapping[str, object]:
        del timeout, maximum_bytes
        offset = int(parse_qs(urlsplit(url).query)["from"][0])
        if offset == 0:
            return {"status": 200, "data": {"total": 2, "items": [_raw("first")]}}
        if failure == "changed_total":
            return {"status": 200, "data": {"total": 3, "items": [_raw("second")]}}
        return {"status": 200, "data": {"total": 2, "items": []}}

    adapter = DevconPublicProgramAdapter(_configuration(), fetch_json=fetch)
    with pytest.raises(
        DevconContractError,
        match="changed_during_read|empty_before_total",
    ):
        DevconProgramSync(
            repository=repository,
            source=adapter,
            clock=FixedClock(NOW + timedelta(minutes=5)),
        ).synchronize(event_id=event_id, stage_id=stage_id)

    retained = repository.list_program_expectations(event_id)
    assert len(retained) == 1
    assert retained[0].title == "Retained"
    assert retained[0].lifecycle_state.value == "current"
    latest = repository.get_latest_program_reconciliation(event_id, stage_id)
    assert latest is not None
    assert latest.synchronized_at == NOW
