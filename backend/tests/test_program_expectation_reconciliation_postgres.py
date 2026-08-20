from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from app.contexts.events import EventStageBootstrapRequest, StageBootstrapDefinition
from app.contexts.integration.devcon import DevconProgramSync, ExternalProgramItem
from app.contexts.production.event_mode_kernel import KernelStorageUnavailableError
from app.infrastructure.postgres import (
    PostgresEventModeKernelRepository,
    PostgresMigrationRunner,
)
from app.shared.ids import EntityId
from app.shared.time import FixedClock

_POSTGRES_DSN = os.getenv("STAGEFLOW_TEST_POSTGRES_DSN")
NOW = datetime(2026, 8, 19, 18, 0, tzinfo=UTC)
ACTOR_ID = EntityId("52000000-0000-4000-8000-000000000001")


class SnapshotSource:
    provider = "devcon"
    event_id = "test-devcon-8"
    room_id = "stage-1"

    def __init__(self, items: tuple[ExternalProgramItem, ...]) -> None:
        self.items = items

    def fetch_program(self) -> tuple[ExternalProgramItem, ...]:
        return self.items


def _item(session_id: str, *, title: str, start: datetime) -> ExternalProgramItem:
    return ExternalProgramItem(
        event_id="test-devcon-8",
        session_id=session_id,
        room_id="stage-1",
        room_name="Stage 1",
        title=title,
        speakers=("Ada",),
        planned_start=start,
        planned_end=start + timedelta(minutes=30),
    )


@pytest.mark.skipif(
    not _POSTGRES_DSN,
    reason="STAGEFLOW_TEST_POSTGRES_DSN is required for migration 0009 checks.",
)
def test_migration_0009_reversal_is_restrictive_and_reapplies() -> None:
    assert _POSTGRES_DSN is not None
    runner = PostgresMigrationRunner(_POSTGRES_DSN)
    runner.apply_event_mode_kernel_v1()
    suffix = uuid4().hex
    view_name = sql.Identifier(f"program_expectation_0009_dependency_{suffix}")
    try:
        with psycopg.connect(_POSTGRES_DSN) as connection:
            connection.execute(
                sql.SQL(
                    "CREATE VIEW stageflow.{} AS SELECT lifecycle_state "
                    "FROM stageflow.program_expectation"
                ).format(view_name)
            )
        with pytest.raises(psycopg.errors.DependentObjectsStillExist):
            runner.reverse_program_expectation_reconciliation_v1()
        with psycopg.connect(_POSTGRES_DSN) as connection:
            assert connection.execute(
                "SELECT 1 FROM stageflow.schema_migration WHERE version = %s",
                ("0009_program_expectation_reconciliation",),
            ).fetchone() == (1,)
            connection.execute(sql.SQL("DROP VIEW stageflow.{}").format(view_name))

        runner.reverse_program_expectation_reconciliation_v1()
        with psycopg.connect(_POSTGRES_DSN) as connection:
            assert connection.execute(
                "SELECT to_regclass('stageflow.program_expectation_sync_snapshot')"
            ).fetchone() == (None,)
            assert (
                connection.execute(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema = 'stageflow' "
                    "AND table_name = 'program_expectation' "
                    "AND column_name = 'lifecycle_state'"
                ).fetchone()
                is None
            )
        runner.apply_program_expectation_reconciliation_v1()
        with psycopg.connect(_POSTGRES_DSN) as connection:
            assert connection.execute(
                "SELECT 1 FROM stageflow.schema_migration WHERE version = %s",
                ("0009_program_expectation_reconciliation",),
            ).fetchone() == (1,)
    finally:
        runner.apply_program_expectation_reconciliation_v1()
        with psycopg.connect(_POSTGRES_DSN) as connection:
            connection.execute(sql.SQL("DROP VIEW IF EXISTS stageflow.{}").format(view_name))


@pytest.mark.skipif(
    not _POSTGRES_DSN,
    reason="STAGEFLOW_TEST_POSTGRES_DSN is required for reconciliation rollback checks.",
)
def test_postgres_reconciliation_rolls_back_atomically_and_reconstructs_after_restart() -> None:
    assert _POSTGRES_DSN is not None
    PostgresMigrationRunner(_POSTGRES_DSN).apply_event_mode_kernel_v1()
    repository = PostgresEventModeKernelRepository(_POSTGRES_DSN)
    suffix = uuid4().hex
    result = repository.bootstrap(
        EventStageBootstrapRequest(
            operation_id=EntityId.new(),
            event_key=f"program-rollback-{suffix}",
            event_name="Program Rollback",
            stages=(
                StageBootstrapDefinition(
                    key="main",
                    name="Main",
                    source_bindings={"vmix": f"C:/program-rollback/{suffix}"},
                ),
            ),
            actor_id=ACTOR_ID,
            requested_at=NOW,
        )
    )
    assert result.event is not None
    event_id = result.event.id
    stage_id = result.stages[0].id
    source = SnapshotSource(
        (
            _item("one", title="One", start=NOW),
            _item("two", title="Two", start=NOW + timedelta(hours=1)),
        )
    )
    first = DevconProgramSync(
        repository=repository, source=source, clock=FixedClock(NOW)
    ).synchronize(event_id=event_id, stage_id=stage_id)
    repeated = DevconProgramSync(
        repository=repository,
        source=source,
        clock=FixedClock(NOW + timedelta(minutes=1)),
    ).synchronize(event_id=event_id, stage_id=stage_id)
    assert (repeated.added, repeated.changed, repeated.unchanged) == (0, 0, 2)
    assert all(item.revision == 1 for item in repeated.expectations)
    blocked_id = next(item.id for item in first.expectations if item.key.endswith(":two"))
    function_name = sql.Identifier(f"reject_program_revision_{suffix}")
    trigger_name = sql.Identifier(f"reject_program_revision_{suffix}")
    try:
        with psycopg.connect(_POSTGRES_DSN) as connection:
            connection.execute(
                sql.SQL(
                    "CREATE FUNCTION stageflow.{}() RETURNS trigger LANGUAGE plpgsql AS $$ "
                    "BEGIN RAISE EXCEPTION 'program reconciliation rollback probe'; END $$"
                ).format(function_name)
            )
            connection.execute(
                sql.SQL(
                    "CREATE TRIGGER {} BEFORE INSERT ON "
                    "stageflow.program_expectation_revision FOR EACH ROW "
                    "WHEN (NEW.expectation_id = {}::uuid AND "
                    "NEW.expectation_revision = 2) EXECUTE FUNCTION stageflow.{}()"
                ).format(trigger_name, sql.Literal(blocked_id.value), function_name)
            )

        source.items = (
            _item("one", title="One changed", start=NOW),
            _item("two", title="Two changed", start=NOW + timedelta(hours=1)),
        )
        with pytest.raises(KernelStorageUnavailableError, match="reconciliation_failed"):
            DevconProgramSync(
                repository=repository,
                source=source,
                clock=FixedClock(NOW + timedelta(minutes=5)),
            ).synchronize(event_id=event_id, stage_id=stage_id)

        restarted = PostgresEventModeKernelRepository(_POSTGRES_DSN)
        retained = restarted.list_program_expectations(event_id)
        assert [item.title for item in retained] == ["One", "Two"]
        assert all(item.revision == 1 for item in retained)
        assert restarted.get_latest_program_reconciliation(event_id, stage_id) == repeated
    finally:
        with psycopg.connect(_POSTGRES_DSN) as connection:
            connection.execute(
                sql.SQL(
                    "DROP TRIGGER IF EXISTS {} ON stageflow.program_expectation_revision"
                ).format(trigger_name)
            )
            connection.execute(
                sql.SQL("DROP FUNCTION IF EXISTS stageflow.{}()").format(function_name)
            )
            connection.execute(
                "DELETE FROM stageflow.program_expectation_sync_snapshot WHERE event_id = %s",
                (event_id.value,),
            )
            connection.execute(
                "DELETE FROM stageflow.program_expectation_revision "
                "WHERE expectation_id IN ("
                "SELECT expectation_id FROM stageflow.program_expectation "
                "WHERE event_id = %s)",
                (event_id.value,),
            )
            connection.execute(
                "DELETE FROM stageflow.program_expectation WHERE event_id = %s",
                (event_id.value,),
            )
            connection.execute(
                "DELETE FROM stageflow.stage_source_binding WHERE stage_id = %s",
                (stage_id.value,),
            )
            connection.execute(
                "DELETE FROM stageflow.event_stage_bootstrap_operation WHERE event_id = %s",
                (event_id.value,),
            )
            connection.execute(
                "DELETE FROM stageflow.stage WHERE event_id = %s",
                (event_id.value,),
            )
            connection.execute(
                "DELETE FROM stageflow.business_event WHERE event_id = %s",
                (event_id.value,),
            )
