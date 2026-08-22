from __future__ import annotations

import os
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, Protocol, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from app.api.authentication import API_SECRET_HEADER
from app.api.v1.router import router as api_router
from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.editorial import (
    DeclareEditorialMoment,
    EditorialCandidateMoment,
    EditorialCandidateOrigin,
    EditorialGenerationState,
    EditorialLocationConflictReason,
    EditorialMomentConflictError,
    EditorialMomentService,
    EditorialSessionCandidateProjection,
)
from app.contexts.events import EventStageBootstrapRequest, StageBootstrapDefinition
from app.contexts.production.event_mode_kernel import (
    DurableEventModeKernel,
    InMemoryEventModeKernelRepository,
    StartSessionRequest,
)
from app.core.config.deployment import EffectiveKernelConfiguration
from app.shared.ids import EntityId
from app.shared.time import FixedClock

NOW = datetime(2026, 8, 22, 16, 0, tzinfo=UTC)
AUTH_HEADERS = {
    API_SECRET_HEADER: "stageflow-test-only-shared-secret-0123456789"
}


class SyncHttpClient(Protocol):
    def get(
        self, url: str, *, headers: Mapping[str, str] | None = None
    ) -> Response: ...

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        json: object | None = None,
    ) -> Response: ...


class MemoryEditorialRepository:
    """Test double only; PostgreSQL remains the sole runtime authority."""

    def __init__(self, *, session_id: EntityId, revision: int = 1) -> None:
        self.session_id = session_id
        self.session_revision = revision
        self.authoritative_start = NOW
        self.authoritative_end: datetime | None = NOW + timedelta(minutes=60)
        self.by_operation: dict[EntityId, tuple[str, EditorialCandidateMoment]] = {}

    def declare(self, command: DeclareEditorialMoment) -> EditorialCandidateMoment:
        replay = self.by_operation.get(command.operation_id)
        if replay is not None:
            digest, moment = replay
            if digest != command.request_digest:
                raise EditorialMomentConflictError(
                    "human_command_operation_id_conflict"
                )
            return moment
        if command.session_id != self.session_id:
            raise LookupError("session_not_found")
        if command.expected_session_revision != self.session_revision:
            raise EditorialMomentConflictError("session_revision_conflict")
        moment = EditorialCandidateMoment(
            id=command.candidate_moment_id,
            session_id=command.session_id,
            expected_session_revision=command.expected_session_revision,
            timeline_start_microseconds=command.timeline_start_microseconds,
            timeline_end_microseconds=command.timeline_end_microseconds,
            session_authoritative_start=self.authoritative_start,
            session_authoritative_end=self.authoritative_end,
            actor_id=command.actor_id,
            operation_id=command.operation_id,
            note=command.note,
            declared_at=command.declared_at,
        )
        self.by_operation[command.operation_id] = (command.request_digest, moment)
        return moment

    def list_for_session(
        self, session_id: EntityId, *, limit: int = 100
    ) -> tuple[EditorialCandidateMoment, ...]:
        return tuple(
            sorted(
                (
                    moment
                    for _, moment in self.by_operation.values()
                    if moment.session_id == session_id
                ),
                key=lambda item: (item.timeline_start_microseconds, item.id.value),
            )
        )[:limit]

    def projection_for_session(
        self, session_id: EntityId
    ) -> EditorialSessionCandidateProjection:
        moments = self.list_for_session(session_id)
        return EditorialSessionCandidateProjection(
            session_id=session_id,
            candidate_count=len(moments),
            latest_candidate_activity_at=(
                None
                if not moments
                else max((item.updated_at or item.declared_at) for item in moments)
            ),
            generation_state=EditorialGenerationState.HEALTHY,
            location_conflict_count=sum(item.location_conflict for item in moments),
        )

    def projections_for_sessions(
        self, session_ids: tuple[EntityId, ...]
    ) -> tuple[EditorialSessionCandidateProjection, ...]:
        return tuple(self.projection_for_session(item) for item in session_ids)

    def revalidate_session_locations(
        self, session_id: EntityId, *, evaluated_at: datetime
    ) -> tuple[EditorialCandidateMoment, ...]:
        for operation_id, (digest, moment) in tuple(self.by_operation.items()):
            if moment.session_id != session_id:
                continue
            absolute_start = moment.session_authoritative_start + timedelta(
                microseconds=moment.timeline_start_microseconds
            )
            absolute_end = moment.session_authoritative_start + timedelta(
                microseconds=(
                    moment.timeline_start_microseconds
                    if moment.timeline_end_microseconds is None
                    else moment.timeline_end_microseconds
                )
            )
            if absolute_end < self.authoritative_start or (
                self.authoritative_end is not None
                and absolute_start > self.authoritative_end
            ):
                reason = EditorialLocationConflictReason.EXCLUDED
            elif absolute_start < self.authoritative_start or (
                self.authoritative_end is not None
                and absolute_end > self.authoritative_end
            ):
                reason = EditorialLocationConflictReason.PARTIALLY_EXCLUDED
            else:
                reason = None
            self.by_operation[operation_id] = (
                digest,
                replace(
                    moment,
                    updated_at=evaluated_at,
                    location_conflict_reason=reason,
                ),
            )
        return self.list_for_session(session_id)


def _mark(
    service: EditorialMomentService,
    *,
    operation_number: int,
    session_id: EntityId,
    revision: int,
    start_minutes: int,
    end_minutes: int | None = None,
    note: str = "producer mark",
) -> EditorialCandidateMoment:
    return service.mark_moment(
        operation_id=EntityId(
            f"91000000-0000-0000-0000-{operation_number:012d}"
        ),
        session_id=session_id,
        expected_session_revision=revision,
        timeline_start_microseconds=start_minutes * 60 * 1_000_000,
        timeline_end_microseconds=(
            None if end_minutes is None else end_minutes * 60 * 1_000_000
        ),
        actor_id=EntityId("91000000-0000-0000-0000-000000000001"),
        note=note,
    )


def test_editorial_candidate_contract_is_strict_immutable_and_future_compatible() -> None:
    session_id = EntityId("91000000-0000-0000-0000-000000000002")
    service = EditorialMomentService(
        MemoryEditorialRepository(session_id=session_id), FixedClock(NOW)
    )
    moment = _mark(
        service,
        operation_number=3,
        session_id=session_id,
        revision=1,
        start_minutes=2,
    )

    assert {item.value for item in EditorialCandidateOrigin} == {
        "observed",
        "derived",
        "inferred",
        "declared",
    }
    assert moment.origin is EditorialCandidateOrigin.DECLARED
    assert moment.source_kind.value == "producer_declaration"
    assert moment.review_state.value == "unreviewed"
    assert moment.location_conflict is False
    with pytest.raises(FrozenInstanceError):
        moment.note = "mutated"  # type: ignore[misc]
    with pytest.raises(ValueError, match="timezone-aware"):
        replace(moment, declared_at=datetime(2026, 8, 22, 16, 0))
    with pytest.raises(ValueError, match="must be declared"):
        replace(moment, origin=EditorialCandidateOrigin.INFERRED)


def test_mark_moment_exact_replay_conflict_and_stale_revision() -> None:
    session_id = EntityId("91000000-0000-0000-0000-000000000010")
    repository = MemoryEditorialRepository(session_id=session_id)
    service = EditorialMomentService(repository, FixedClock(NOW))
    original = _mark(
        service,
        operation_number=11,
        session_id=session_id,
        revision=1,
        start_minutes=5,
    )

    assert _mark(
        service,
        operation_number=11,
        session_id=session_id,
        revision=1,
        start_minutes=5,
    ) == original
    with pytest.raises(
        EditorialMomentConflictError,
        match="human_command_operation_id_conflict",
    ):
        _mark(
            service,
            operation_number=11,
            session_id=session_id,
            revision=1,
            start_minutes=5,
            note="different content",
        )
    repository.session_revision = 2
    with pytest.raises(EditorialMomentConflictError, match="session_revision_conflict"):
        _mark(
            service,
            operation_number=12,
            session_id=session_id,
            revision=1,
            start_minutes=5,
        )


def test_boundary_correction_surfaces_partial_and_full_conflicts_without_moving() -> None:
    session_id = EntityId("91000000-0000-0000-0000-000000000020")
    repository = MemoryEditorialRepository(session_id=session_id)
    service = EditorialMomentService(repository, FixedClock(NOW + timedelta(hours=2)))
    declared = (
        _mark(
            service,
            operation_number=21,
            session_id=session_id,
            revision=1,
            start_minutes=5,
            end_minutes=10,
        ),
        _mark(
            service,
            operation_number=22,
            session_id=session_id,
            revision=1,
            start_minutes=15,
            end_minutes=25,
        ),
        _mark(
            service,
            operation_number=23,
            session_id=session_id,
            revision=1,
            start_minutes=35,
            end_minutes=40,
        ),
    )
    repository.session_revision = 2
    repository.authoritative_start = NOW + timedelta(minutes=10)
    repository.authoritative_end = NOW + timedelta(minutes=30)

    corrected = service.revalidate_session_boundary(session_id)

    assert [item.id for item in corrected] == [item.id for item in declared]
    assert [item.timeline_start_microseconds for item in corrected] == [
        item.timeline_start_microseconds for item in declared
    ]
    assert corrected[0].location_conflict_reason is (
        EditorialLocationConflictReason.PARTIALLY_EXCLUDED
    )
    assert corrected[1].location_conflict_reason is None
    assert corrected[2].location_conflict_reason is (
        EditorialLocationConflictReason.EXCLUDED
    )
    projection = service.projection_for_session(session_id)
    assert projection.candidate_count == 3
    assert projection.location_conflict_count == 2
    assert projection.generation_state is EditorialGenerationState.HEALTHY


def test_canonical_editorial_api_is_authenticated_bounded_and_projected() -> None:
    kernel_repository = InMemoryEventModeKernelRepository()
    kernel = DurableEventModeKernel(
        repository=kernel_repository, clock=FixedClock(NOW)
    )
    bootstrapped = kernel.bootstrap(
        EventStageBootstrapRequest(
            operation_id=EntityId("91000000-0000-0000-0000-000000000030"),
            event_key="editorial-api",
            event_name="Editorial API",
            stages=(
                StageBootstrapDefinition(
                    key="main", name="Main", source_bindings={}
                ),
            ),
            actor_id=EntityId("91000000-0000-0000-0000-000000000031"),
            requested_at=NOW,
        )
    )
    assert bootstrapped.event is not None
    session = kernel.start_session(
        StartSessionRequest(
            operation_id=EntityId("91000000-0000-0000-0000-000000000032"),
            event_id=bootstrapped.event.id,
            stage_id=bootstrapped.stages[0].id,
            actor_id=EntityId("91000000-0000-0000-0000-000000000031"),
            authoritative_start=NOW,
            requested_at=NOW,
        )
    )
    editorial_repository = MemoryEditorialRepository(
        session_id=session.id, revision=session.revision
    )
    configuration = cast(
        EffectiveKernelConfiguration,
        cast(
            Any,
            SimpleNamespace(
                deployment=SimpleNamespace(
                    event=SimpleNamespace(key="editorial-api")
                ),
                postgres_dsn="test-dsn-not-returned",
            ),
        ),
    )
    components = KernelComponents(
        configuration=configuration,
        repository=kernel_repository,
        kernel=kernel,
        editorial_moments=EditorialMomentService(
            editorial_repository, FixedClock(NOW)
        ),
    )
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    app.state.kernel = components
    client = cast(SyncHttpClient, TestClient(app))
    command = {
        "actor_id": "91000000-0000-0000-0000-000000000031",
        "confirmed": "confirmed",
        "session_id": session.id.value,
        "expected_session_revision": session.revision,
        "timeline_start_microseconds": 1_000_000,
    }

    assert client.post(
        "/api/v1/editorial/moments/mark",
        json={**command, "operation_id": "91000000-0000-0000-0000-000000000033"},
    ).status_code == 401
    for operation in (33, 34):
        response = client.post(
            "/api/v1/editorial/moments/mark",
            headers=AUTH_HEADERS,
            json={
                **command,
                "operation_id": f"91000000-0000-0000-0000-{operation:012d}",
            },
        )
        assert response.status_code == 200
        assert response.json()["review_state"] == "unreviewed"
    listed = client.get(
        f"/api/v1/editorial/sessions/{session.id.value}/moments?limit=1",
        headers=AUTH_HEADERS,
    )
    assert listed.status_code == 200
    assert listed.json()["candidate_count"] == 2
    assert listed.json()["generation_state"] == "healthy"
    assert listed.json()["items_truncated"] is True
    assert len(listed.json()["items"]) == 1
    assert "test-dsn-not-returned" not in listed.text


@pytest.mark.skipif(
    not os.getenv("STAGEFLOW_TEST_POSTGRES_DSN"),
    reason="STAGEFLOW_TEST_POSTGRES_DSN is required for durability qualification.",
)
def test_postgres_replay_concurrency_restart_and_boundary_conflicts() -> None:
    from uuid import uuid4

    import psycopg

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
    operation_ids = [EntityId.new() for _ in range(11)]
    event_id: EntityId | None = None
    stage_id: EntityId | None = None
    session_id: EntityId | None = None
    try:
        kernel_repository = PostgresEventModeKernelRepository(dsn)
        kernel = DurableEventModeKernel(
            repository=kernel_repository, clock=FixedClock(NOW)
        )
        bootstrapped = kernel.bootstrap(
            EventStageBootstrapRequest(
                operation_id=operation_ids[0],
                event_key=f"editorial-phase1-{suffix}",
                event_name="Editorial Phase 1 Qualification",
                stages=(
                    StageBootstrapDefinition(
                        key="main",
                        name="Main",
                        source_bindings={f"source-{suffix}": f"C:/synthetic/{suffix}"},
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
        session = kernel.correct_session_boundary(
            operation_id=operation_ids[2],
            session_id=session_id,
            boundary_kind="end",
            boundary_at=NOW + timedelta(minutes=60),
            actor_id=actor,
            reason="initial qualification boundary",
        )
        moments = EditorialMomentService(
            PostgresEditorialMomentRepository(dsn), FixedClock(NOW)
        )

        def declare(
            operation_id: EntityId,
            start_minutes: int,
            end_minutes: int | None,
        ) -> EditorialCandidateMoment:
            return moments.mark_moment(
                operation_id=operation_id,
                session_id=session_id,
                expected_session_revision=session.revision,
                timeline_start_microseconds=start_minutes * 60 * 1_000_000,
                timeline_end_microseconds=(
                    None if end_minutes is None else end_minutes * 60 * 1_000_000
                ),
                actor_id=actor,
                note=f"qualification {start_minutes}",
            )

        partial = declare(operation_ids[3], 5, 10)
        contained = declare(operation_ids[4], 15, 25)
        excluded = declare(operation_ids[5], 35, 40)
        assert declare(operation_ids[3], 5, 10) == partial
        with pytest.raises(
            EditorialMomentConflictError,
            match="human_command_operation_id_conflict",
        ):
            moments.mark_moment(
                operation_id=operation_ids[3],
                session_id=session_id,
                expected_session_revision=session.revision,
                timeline_start_microseconds=5 * 60 * 1_000_000,
                timeline_end_microseconds=10 * 60 * 1_000_000,
                actor_id=actor,
                note="conflicting replay",
            )
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(declare, operation_ids[6], 20, None)
            second = executor.submit(declare, operation_ids[7], 21, None)
            concurrent = (
                first.result(),
                second.result(),
            )
        assert len({item.id for item in concurrent}) == 2

        session = kernel.correct_session_boundary(
            operation_id=operation_ids[8],
            session_id=session_id,
            boundary_kind="start",
            boundary_at=NOW + timedelta(minutes=10),
            actor_id=actor,
            reason="exclude initial lead-in",
        )
        moments.revalidate_session_boundary(session_id)
        session = kernel.correct_session_boundary(
            operation_id=operation_ids[9],
            session_id=session_id,
            boundary_kind="end",
            boundary_at=NOW + timedelta(minutes=30),
            actor_id=actor,
            reason="exclude trailing material",
        )
        moments.revalidate_session_boundary(session_id)

        restarted = EditorialMomentService(
            PostgresEditorialMomentRepository(dsn), FixedClock(NOW)
        )
        reconstructed = restarted.list_for_session(session_id)
        by_id = {item.id: item for item in reconstructed}
        assert len(reconstructed) == 5
        assert by_id[partial.id].location_conflict_reason is (
            EditorialLocationConflictReason.PARTIALLY_EXCLUDED
        )
        assert by_id[contained.id].location_conflict_reason is None
        assert by_id[excluded.id].location_conflict_reason is (
            EditorialLocationConflictReason.EXCLUDED
        )
        projection = restarted.projection_for_session(session_id)
        assert projection.candidate_count == 5
        assert projection.location_conflict_count == 2
        with psycopg.connect(dsn) as connection:
            history_count = connection.execute(
                """
                SELECT count(*)
                FROM stageflow.editorial_candidate_moment_location_history
                WHERE candidate_moment_id = ANY(%s::uuid[])
                """,
                ([item.id.value for item in reconstructed],),
            ).fetchone()
            assert history_count == (10,)
        with pytest.raises(EditorialMomentConflictError, match="session_revision_conflict"):
            moments.mark_moment(
                operation_id=operation_ids[10],
                session_id=session_id,
                expected_session_revision=session.revision - 1,
                timeline_start_microseconds=22 * 60 * 1_000_000,
                actor_id=actor,
            )
    finally:
        if event_id is not None and stage_id is not None:
            with psycopg.connect(dsn) as connection:
                if session_id is not None:
                    connection.execute(
                        """
                        DELETE FROM stageflow.editorial_candidate_moment_location_history
                        WHERE candidate_moment_id IN (
                            SELECT candidate_moment_id
                            FROM stageflow.editorial_candidate_moment
                            WHERE session_id = %s
                        )
                        """,
                        (session_id.value,),
                    )
                    connection.execute(
                        "DELETE FROM stageflow.editorial_candidate_moment WHERE session_id = %s",
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
                        "DELETE FROM stageflow.human_command_idempotency "
                        "WHERE operation_id = ANY(%s::uuid[])",
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


@pytest.mark.skipif(
    not os.getenv("STAGEFLOW_TEST_POSTGRES_DSN"),
    reason="STAGEFLOW_TEST_POSTGRES_DSN is required for migration qualification.",
)
def test_0010_reversal_preserves_0008_candidate_authority() -> None:
    import psycopg

    from app.infrastructure.postgres import PostgresMigrationRunner

    dsn = os.environ["STAGEFLOW_TEST_POSTGRES_DSN"]
    runner = PostgresMigrationRunner(dsn)
    runner.apply_event_mode_kernel_v1()
    try:
        runner.reverse_editorial_candidate_moment_v1()
        with psycopg.connect(dsn) as connection:
            assert connection.execute(
                "SELECT to_regclass('stageflow.editorial_candidate_moment')"
            ).fetchone() == ("stageflow.editorial_candidate_moment",)
            assert connection.execute(
                "SELECT to_regclass("
                "'stageflow.editorial_candidate_moment_location_history')"
            ).fetchone() == (None,)
    finally:
        runner.apply_editorial_candidate_moment_v1()
