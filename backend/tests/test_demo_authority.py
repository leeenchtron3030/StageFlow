from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.contexts.events import EventStageBootstrapRequest, StageBootstrapDefinition
from app.contexts.production.event_mode_kernel import (
    DurableEventModeKernel,
    InMemoryEventModeKernelRepository,
    KernelConflictError,
)
from app.contexts.production.event_mode_kernel.contracts import (
    SessionPackageState,
    StartSessionRequest,
)
from app.infrastructure.postgres import PostgresMigrationRunner
from app.shared.ids import EntityId
from app.shared.time import FixedClock

NOW = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
ACTOR = EntityId("80000000-0000-0000-0000-000000000001")


def _id(number: int) -> EntityId:
    return EntityId(f"80000000-0000-0000-0000-{number:012d}")


def _started_kernel() -> tuple[DurableEventModeKernel, EntityId]:
    repository = InMemoryEventModeKernelRepository()
    kernel = DurableEventModeKernel(repository=repository, clock=FixedClock(NOW))
    bootstrapped = kernel.bootstrap(
        EventStageBootstrapRequest(
            operation_id=_id(2),
            event_key="demo-one",
            event_name="Demo One",
            stages=(
                StageBootstrapDefinition(
                    key="main",
                    name="Main",
                    source_bindings={"vmix": "C:/demo/media"},
                ),
            ),
            actor_id=ACTOR,
            requested_at=NOW,
        )
    )
    assert bootstrapped.event is not None
    session = kernel.start_session(
        StartSessionRequest(
            operation_id=_id(3),
            event_id=bootstrapped.event.id,
            stage_id=bootstrapped.stages[0].id,
            actor_id=ACTOR,
            authoritative_start=NOW,
            requested_at=NOW,
        )
    )
    return kernel, session.id


def test_package_ready_is_actor_attributed_idempotent_human_authority() -> None:
    kernel, session_id = _started_kernel()

    with pytest.raises(KernelConflictError, match="presentation_not_ended"):
        kernel.declare_package_ready(
            operation_id=_id(4),
            session_id=session_id,
            actor_id=ACTOR,
            reason="producer review",
        )

    ended = kernel.correct_session_boundary(
        operation_id=_id(5),
        session_id=session_id,
        boundary_kind="end",
        boundary_at=NOW,
        actor_id=ACTOR,
        reason="presentation ended",
    )
    ready = kernel.declare_package_ready(
        operation_id=_id(6),
        session_id=session_id,
        actor_id=ACTOR,
        reason="producer review",
    )
    replay = kernel.declare_package_ready(
        operation_id=_id(6),
        session_id=session_id,
        actor_id=ACTOR,
        reason="producer review",
    )

    assert ready == replay
    assert ready.package_state is SessionPackageState.READY_FOR_REVIEW
    assert ready.package_revision == ended.package_revision
    assert ready.revision == ended.revision + 1

    with pytest.raises(KernelConflictError, match="operation_id_conflict"):
        kernel.declare_package_ready(
            operation_id=_id(6),
            session_id=session_id,
            actor_id=ACTOR,
            reason="different command",
        )


def test_0008_migration_is_exact_and_restrictive() -> None:
    sql_root = Path(__file__).parents[1] / "app" / "infrastructure" / "postgres" / "sql"
    forward = (sql_root / "0008_demo_vertical_slice_forward.sql").read_text(
        encoding="utf-8"
    )
    reverse = (sql_root / "0008_demo_vertical_slice_reverse.sql").read_text(
        encoding="utf-8"
    )

    assert forward.count("CREATE TABLE stageflow.") == 2
    assert "CREATE TABLE stageflow.session_package_ready_history" in forward
    assert "CREATE TABLE stageflow.editorial_candidate_moment" in forward
    assert "'package_ready'" in forward
    assert "'editorial_moment_declaration'" in forward
    assert "CASCADE" not in forward.upper()

    assert reverse.count("DROP TABLE stageflow.") == 2
    assert "DROP TABLE stageflow.session_package_ready_history" in reverse
    assert "DROP TABLE stageflow.editorial_candidate_moment" in reverse
    assert "CASCADE" not in reverse.upper()
    assert "command_kind IN ('package_ready', 'editorial_moment_declaration')" in reverse


def test_migration_runner_keeps_0008_explicit() -> None:
    assert hasattr(PostgresMigrationRunner, "apply_demo_vertical_slice_v1")
    assert hasattr(PostgresMigrationRunner, "reverse_demo_vertical_slice_v1")

@pytest.mark.skipif(
    not os.getenv("STAGEFLOW_TEST_POSTGRES_DSN"),
    reason="STAGEFLOW_TEST_POSTGRES_DSN is required for restart qualification.",
)
def test_real_postgres_demo_authority_reconstructs_and_cleans_up() -> None:
    from uuid import uuid4

    import psycopg

    from app.contexts.editorial import EditorialMomentService
    from app.infrastructure.postgres import (
        PostgresEditorialMomentRepository,
        PostgresEventModeKernelRepository,
        PostgresMigrationRunner,
    )

    dsn = os.environ["STAGEFLOW_TEST_POSTGRES_DSN"]
    with psycopg.connect(dsn) as connection:
        assert connection.execute("SELECT current_database()").fetchone() == (
            "stageflow_worker_test",
        )
    PostgresMigrationRunner(dsn).apply_event_mode_kernel_v1()
    suffix = uuid4().hex
    actor = EntityId.new()
    operation_ids = [EntityId.new() for _ in range(5)]
    event_id: EntityId | None = None
    stage_id: EntityId | None = None
    session_id: EntityId | None = None
    try:
        repository = PostgresEventModeKernelRepository(dsn)
        kernel = DurableEventModeKernel(repository=repository, clock=FixedClock(NOW))
        bootstrapped = kernel.bootstrap(
            EventStageBootstrapRequest(
                operation_id=operation_ids[0],
                event_key=f"demo-authority-{suffix}",
                event_name="Demo Authority Restart Qualification",
                stages=(
                    StageBootstrapDefinition(
                        key="main",
                        name="Main",
                        source_bindings={f"vmix-{suffix}": f"C:/demo/{suffix}"},
                    ),
                ),
                actor_id=actor,
                requested_at=NOW,
            )
        )
        assert bootstrapped.event is not None
        event_id = bootstrapped.event.id
        stage_id = bootstrapped.stages[0].id
        session = kernel.start_session(
            StartSessionRequest(
                operation_id=operation_ids[1],
                event_id=event_id,
                stage_id=stage_id,
                actor_id=actor,
                authoritative_start=NOW,
                requested_at=NOW,
            )
        )
        session_id = session.id
        kernel.correct_session_boundary(
            operation_id=operation_ids[2],
            session_id=session_id,
            boundary_kind="end",
            boundary_at=NOW,
            actor_id=actor,
            reason="restart qualification ended",
        )
        ready = kernel.declare_package_ready(
            operation_id=operation_ids[3],
            session_id=session_id,
            actor_id=actor,
            reason="restart qualification ready",
        )

        restarted_kernel = DurableEventModeKernel(
            repository=PostgresEventModeKernelRepository(dsn),
            clock=FixedClock(NOW),
        )
        assert restarted_kernel.declare_package_ready(
            operation_id=operation_ids[3],
            session_id=session_id,
            actor_id=actor,
            reason="restart qualification ready",
        ) == ready

        moments = EditorialMomentService(
            PostgresEditorialMomentRepository(dsn),
            FixedClock(NOW),
        )
        declared = moments.mark_moment(
            operation_id=operation_ids[4],
            session_id=session_id,
            expected_session_revision=ready.revision,
            timeline_start_microseconds=0,
            actor_id=actor,
            note="restart qualification mark",
        )
        restarted_moments = EditorialMomentService(
            PostgresEditorialMomentRepository(dsn),
            FixedClock(NOW),
        )
        assert restarted_moments.mark_moment(
            operation_id=operation_ids[4],
            session_id=session_id,
            expected_session_revision=ready.revision,
            timeline_start_microseconds=0,
            actor_id=actor,
            note="restart qualification mark",
        ) == declared
        assert restarted_moments.list_for_session(session_id) == (declared,)
    finally:
        if event_id is not None and stage_id is not None:
            with psycopg.connect(dsn) as connection:
                if session_id is not None:
                    connection.execute(
                        "DELETE FROM stageflow.editorial_candidate_moment WHERE session_id = %s",
                        (session_id.value,),
                    )
                    connection.execute(
                        "DELETE FROM stageflow.session_package_ready_history WHERE session_id = %s",
                        (session_id.value,),
                    )
                    connection.execute(
                        "DELETE FROM stageflow.session_boundary_history WHERE session_id = %s",
                        (session_id.value,),
                    )
                    connection.execute(
                        "DELETE FROM stageflow.session_start_operation WHERE session_id = %s",
                        (session_id.value,),
                    )
                    connection.execute(
                        ("DELETE FROM stageflow.human_command_idempotency "
                        "WHERE operation_id = ANY(%s::uuid[])"),
                        ([item.value for item in operation_ids],),
                    )
                    connection.execute(
                        "DELETE FROM stageflow.session WHERE session_id = %s",
                        (session_id.value,),
                    )
                connection.execute(
                    "DELETE FROM stageflow.stage_source_binding WHERE stage_id = %s",
                    (stage_id.value,),
                )
                connection.execute(
                    "DELETE FROM stageflow.stage WHERE stage_id = %s",
                    (stage_id.value,),
                )
                connection.execute(
                    "DELETE FROM stageflow.event_stage_bootstrap_operation WHERE event_id = %s",
                    (event_id.value,),
                )
                connection.execute(
                    "DELETE FROM stageflow.business_event WHERE event_id = %s",
                    (event_id.value,),
                )
