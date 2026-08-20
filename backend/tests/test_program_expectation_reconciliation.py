from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.contexts.events import (
    EventStageBootstrapRequest,
    ProgramExpectationLifecycle,
    StageBootstrapDefinition,
)
from app.contexts.integration.devcon import DevconProgramSync, ExternalProgramItem
from app.contexts.production.event_mode_kernel import (
    InMemoryEventModeKernelRepository,
    KernelConflictError,
)
from app.contexts.production.event_mode_kernel.contracts import StartSessionRequest
from app.infrastructure.devcon import DevconReadError
from app.shared.ids import EntityId
from app.shared.time import FixedClock

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
ACTOR_ID = EntityId("51000000-0000-4000-8000-000000000001")


class SnapshotSource:
    provider = "devcon"
    event_id = "test-devcon-8"
    room_id = "stage-1"

    def __init__(self, items: tuple[ExternalProgramItem, ...]) -> None:
        self.items = items
        self.available = True

    def fetch_program(self) -> tuple[ExternalProgramItem, ...]:
        if not self.available:
            raise DevconReadError("devcon_read_unavailable")
        return self.items


def _item(
    session_id: str,
    *,
    title: str | None = None,
    start: datetime = NOW,
    speakers: tuple[str, ...] = ("Ada",),
) -> ExternalProgramItem:
    return ExternalProgramItem(
        event_id="test-devcon-8",
        session_id=session_id,
        room_id="stage-1",
        room_name="Stage 1",
        title=title or f"Program {session_id}",
        speakers=speakers,
        planned_start=start,
        planned_end=start + timedelta(minutes=30),
    )


def _repository() -> tuple[InMemoryEventModeKernelRepository, EntityId, EntityId]:
    repository = InMemoryEventModeKernelRepository()
    result = repository.bootstrap(
        EventStageBootstrapRequest(
            operation_id=EntityId("51000000-0000-4000-8000-000000000002"),
            event_key="program-reconciliation",
            event_name="Program Reconciliation",
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
    assert result.event is not None
    return repository, result.event.id, result.stages[0].id


def _synchronize(
    repository: InMemoryEventModeKernelRepository,
    event_id: EntityId,
    stage_id: EntityId,
    source: SnapshotSource,
    observed_at: datetime,
):
    return DevconProgramSync(
        repository=repository,
        source=source,
        clock=FixedClock(observed_at),
    ).synchronize(event_id=event_id, stage_id=stage_id)


def test_initial_and_identical_snapshots_preserve_identity_and_content_revision() -> None:
    repository, event_id, stage_id = _repository()
    source = SnapshotSource((_item("one"), _item("two", start=NOW + timedelta(hours=1))))

    initial = _synchronize(repository, event_id, stage_id, source, NOW)
    repeated = _synchronize(repository, event_id, stage_id, source, NOW + timedelta(minutes=5))

    assert (initial.added, initial.changed, initial.unchanged) == (2, 0, 0)
    assert (repeated.added, repeated.changed, repeated.unchanged) == (0, 0, 2)
    assert [item.id for item in repeated.expectations] == [item.id for item in initial.expectations]
    assert all(item.revision == 1 for item in repeated.expectations)
    assert all(
        item.last_observed_at == NOW + timedelta(minutes=5) for item in repeated.expectations
    )
    assert all(
        len(repository.list_program_expectation_revisions(item.id)) == 1
        for item in repeated.expectations
    )


def test_changed_added_withdrawn_and_restored_items_reconcile_deterministically() -> None:
    repository, event_id, stage_id = _repository()
    source = SnapshotSource((_item("one", start=NOW), _item("two", start=NOW + timedelta(hours=1))))
    initial = _synchronize(repository, event_id, stage_id, source, NOW)
    by_key = {item.key: item for item in initial.expectations}

    source.items = (
        _item(
            "two",
            title="Renamed program",
            speakers=("Ada", "Lin"),
            start=NOW - timedelta(hours=1),
        ),
        _item("three", start=NOW + timedelta(hours=2)),
    )
    changed = _synchronize(repository, event_id, stage_id, source, NOW + timedelta(minutes=5))

    assert (
        changed.observed,
        changed.added,
        changed.changed,
        changed.unchanged,
        changed.withdrawn,
        changed.restored,
    ) == (2, 1, 1, 0, 1, 0)
    assert [item.key for item in changed.expectations] == [
        "devcon:test-devcon-8:two",
        "devcon:test-devcon-8:three",
    ]
    updated_two = changed.expectations[0]
    assert updated_two.id == by_key["devcon:test-devcon-8:two"].id
    assert updated_two.revision == 2
    assert {field.field for field in changed.changes[0].fields} >= {
        "title",
        "speakers",
        "planned start",
        "planned end",
    }
    withdrawn_one = next(
        item
        for item in repository.list_program_expectations(event_id)
        if item.key == "devcon:test-devcon-8:one"
    )
    assert withdrawn_one.lifecycle_state is ProgramExpectationLifecycle.WITHDRAWN
    assert len(repository.list_program_expectation_revisions(withdrawn_one.id)) == 2

    source.items = (
        _item("one", start=NOW + timedelta(hours=3)),
        source.items[0],
        source.items[1],
    )
    restored = _synchronize(repository, event_id, stage_id, source, NOW + timedelta(minutes=10))
    restored_one = next(item for item in restored.expectations if item.key.endswith(":one"))
    assert restored.restored == 1
    assert restored_one.id == by_key["devcon:test-devcon-8:one"].id
    assert restored_one.lifecycle_state is ProgramExpectationLifecycle.CURRENT
    assert restored_one.revision == 3


def test_withdrawal_never_rewrites_realized_session_and_cannot_start_a_new_one() -> None:
    repository, event_id, stage_id = _repository()
    source = SnapshotSource((_item("one"),))
    expectation = _synchronize(repository, event_id, stage_id, source, NOW).expectations[0]
    session = repository.start_session(
        StartSessionRequest(
            operation_id=EntityId("51000000-0000-4000-8000-000000000003"),
            event_id=event_id,
            stage_id=stage_id,
            program_expectation_id=expectation.id,
            actor_id=ACTOR_ID,
            authoritative_start=NOW + timedelta(minutes=4),
            requested_at=NOW + timedelta(minutes=4),
        )
    )

    source.items = ()
    result = _synchronize(repository, event_id, stage_id, source, NOW + timedelta(minutes=10))

    assert result.withdrawn == 1
    reconstructed = repository.get_session(session.id)
    assert reconstructed == session
    assert reconstructed is not None
    assert reconstructed.authoritative_start == NOW + timedelta(minutes=4)
    assert reconstructed.program_expectation_id == expectation.id
    with pytest.raises(KernelConflictError, match="program_expectation_withdrawn"):
        repository.start_session(
            StartSessionRequest(
                operation_id=EntityId("51000000-0000-4000-8000-000000000004"),
                event_id=event_id,
                stage_id=stage_id,
                program_expectation_id=expectation.id,
                actor_id=ACTOR_ID,
                authoritative_start=NOW + timedelta(minutes=11),
                requested_at=NOW + timedelta(minutes=11),
            )
        )


def test_failed_fetch_preserves_current_snapshot_and_latest_successful_result() -> None:
    repository, event_id, stage_id = _repository()
    source = SnapshotSource((_item("one"),))
    initial = _synchronize(repository, event_id, stage_id, source, NOW)
    source.items = ()
    source.available = False

    with pytest.raises(DevconReadError, match="unavailable"):
        _synchronize(repository, event_id, stage_id, source, NOW + timedelta(minutes=5))

    retained = repository.list_program_expectations(event_id)
    assert len(retained) == 1
    assert retained[0].lifecycle_state is ProgramExpectationLifecycle.CURRENT
    assert repository.get_latest_program_reconciliation(event_id, stage_id) == initial
