from __future__ import annotations

import os
import sys
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from dataclasses import FrozenInstanceError, dataclass, replace
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Any, Literal, Self, cast
from unittest.mock import Mock
from uuid import uuid4

import psycopg
import pytest
import test_transcription_worker_postgres as transcription_fixtures
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.transaction import Transaction
from test_transcription_worker_substrate import (
    claimed_operation,
    enqueue_request,
    operation_input,
    transcript_result,
)

from app.contexts.transcription_evidence import (
    TranscriptionExecutionPort,
    prepare_transcript_evidence,
)
from app.contexts.work_execution import (
    AttemptOutcome,
    ClaimRequest,
    EnqueueRenderOperation,
    EnqueueTranscriptionOperation,
    EventNetworkPolicy,
    ExecutionLocality,
    OperationFailure,
    OperationInput,
    OperationStatus,
    PendingOperation,
    RenderOperationInput,
    TranscriptionOperationApplication,
    TranscriptionOperationInput,
    TranscriptionWorker,
    Worker,
    WorkerCapability,
    WorkerCycleOutcome,
    WorkerHealth,
    WorkerPressure,
    WorkExecutionConflictError,
    WorkExecutionLeaseLostError,
    WorkExecutionNotFoundError,
    WorkExecutionRepository,
)
from app.contexts.work_execution.application import (
    enqueue_request_digest,
    pending_render_operation,
    render_work_key,
    transcription_work_key,
)
from app.contexts.work_execution.memory import InMemoryWorkExecutionRepository
from app.infrastructure.postgres import PostgresMigrationRunner, PostgresWorkExecutionRepository
from app.shared.ids import EntityId

seed_asset = cast(Callable[..., tuple[EntityId, EntityId, EntityId]],
                  vars(transcription_fixtures)["_seed_asset"])

NOW = datetime(2026, 9, 25, tzinfo=UTC)


def general_repository(dsn: str) -> PostgresWorkExecutionRepository[OperationInput]:
    return PostgresWorkExecutionRepository[OperationInput](
        dsn, input_types=(TranscriptionOperationInput, RenderOperationInput),
    )


@dataclass
class MutableClock:
    at: datetime = NOW

    def now(self) -> datetime:
        return self.at


def render_request() -> EnqueueRenderOperation:
    return EnqueueRenderOperation(
        operation_id=EntityId.new(), idempotency_key="render-" + uuid4().hex,
        deployment_id="test-deployment", event_id=None,
        input=RenderOperationInput(EntityId.new(), "test-profile", "v1", "opaque-output"),
        priority=10, eligible_at=NOW, max_attempts=3, retry_delay=timedelta(seconds=5),
        required_for_event=False, requested_at=NOW,
    )


class TransactionalConnection(psycopg.Connection[dict[str, Any]]):
    """Run repository transactions as savepoints inside a rolled-back test transaction."""

    def __enter__(self) -> Self:
        transaction = self.transaction()
        transaction.__enter__()
        self.transactions.append(transaction)
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None,
                 traceback: TracebackType | None) -> None:
        transaction = self.transactions.pop()
        try:
            if exc_type is None:
                self.execute("SET CONSTRAINTS ALL IMMEDIATE")
                self.execute("SET CONSTRAINTS ALL DEFERRED")
        except BaseException:
            transaction.__exit__(*sys.exc_info())
            raise
        transaction.__exit__(exc_type, exc, traceback)

    transactions: list[AbstractContextManager[Transaction]]


class SanitizedDsn(str):
    def __repr__(self) -> str:
        return "<isolated PostgreSQL test connection>"


@pytest.fixture
def render_postgres_dsn(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    dsn = SanitizedDsn(os.getenv("STAGEFLOW_TEST_POSTGRES_DSN") or "")
    if not dsn:
        pytest.skip("STAGEFLOW_TEST_POSTGRES_DSN is required for real PostgreSQL validation")
    try:
        connection = TransactionalConnection.connect(dsn, connect_timeout=3, row_factory=dict_row)
    except psycopg.OperationalError:
        pytest.skip("Real PostgreSQL is unreachable from this environment")
    # Build the current unmerged migration in a disposable transactional schema.
    # Preserve any earlier draft schema verbatim; rollback restores its name and
    # removes all test DDL/data. No CREATEDB or disabled triggers are needed.
    connection.transactions = []
    connection.execute("BEGIN")

    def borrowed(*args: object, **kwargs: object) -> TransactionalConnection:
        return connection

    monkeypatch.setattr(psycopg, "connect", borrowed)
    monkeypatch.setattr(psycopg.Connection, "connect", borrowed)
    try:
        if connection.execute(
            "SELECT 1 FROM pg_namespace WHERE nspname = 'stageflow'",
        ).fetchone() is not None:
            connection.execute(sql.SQL("ALTER SCHEMA stageflow RENAME TO {}").format(
                sql.Identifier("render_test_preserved_" + uuid4().hex),
            ))
        PostgresMigrationRunner(dsn).apply_event_mode_kernel_v1()
        yield dsn
    finally:
        connection.rollback()
        connection.close()


def seed_revision(dsn: str, event_id: EntityId) -> EntityId:
    revision, session, template = EntityId.new(), EntityId.new(), EntityId.new()
    with psycopg.connect(dsn) as connection:
        stage = connection.execute("SELECT stage_id FROM stageflow.stage WHERE event_id = %s",
                                   (event_id.value,)).fetchone()
        assert stage is not None
        connection.execute("""
            INSERT INTO stageflow.session (
                session_id, event_id, stage_id, activity_state, package_state,
                authoritative_start, package_revision, revision, created_by, created_at, updated_at
            ) VALUES (%s, %s, %s, 'presentation_active', 'assembling', %s, 1, 1, %s, %s, %s)
        """, (session.value, event_id.value,
              cast(dict[str, object], cast(object, stage))["stage_id"],
              NOW, EntityId.new().value, NOW, NOW))
        connection.execute("""
            INSERT INTO stageflow.assembly_template (
                template_id, event_id, template_key, version, name, slots,
                required_metadata, created_at
            ) VALUES (%s, %s, 'test-template', 1, 'Synthetic template', '[{}]', '[]', %s)
        """, (template.value, event_id.value, NOW))
        # Only a persistence fixture. Render authorization/approval belongs to the later command.
        connection.execute("""
            INSERT INTO stageflow.assembly_revision (
                revision_id, session_id, event_id, revision_number, template_id, package_revision,
                validation_state, validation_issues, actor_id, created_at
            ) VALUES (%s, %s, %s, 1, %s, 1, 'invalid', '["synthetic_fixture"]', %s, %s)
        """, (revision.value, session.value, event_id.value, template.value,
              EntityId.new().value, NOW))
    return revision


@dataclass
class Harness:
    repository: WorkExecutionRepository[OperationInput]
    request: EnqueueRenderOperation
    clock: MutableClock
    dsn: str | None

    def elapse(self, operation_id: EntityId, *, expire: bool = False) -> None:
        self.clock.at += timedelta(minutes=2)
        if self.dsn is not None:
            with psycopg.connect(self.dsn) as connection:
                connection.execute("""
                    UPDATE stageflow.work_operation SET eligible_at = statement_timestamp()
                        - interval '1 second' WHERE operation_id = %s
                """, (operation_id.value,))
                if expire:
                    connection.execute("""
                        UPDATE stageflow.work_operation SET lease_expires_at = statement_timestamp()
                            - interval '1 second' WHERE operation_id = %s
                    """, (operation_id.value,))


@pytest.fixture(params=["memory", "postgres"])
def harness(request: pytest.FixtureRequest) -> Harness:
    clock = MutableClock()
    enqueue = render_request()
    if request.param == "memory":
        return Harness(InMemoryWorkExecutionRepository(clock), enqueue, clock, None)
    dsn: str = request.getfixturevalue("render_postgres_dsn")
    event, _, _ = seed_asset(dsn, observed_at=NOW)
    revision = seed_revision(dsn, event)
    enqueue = replace(enqueue, event_id=event,
                      input=replace(enqueue.input, assembly_revision_id=revision))
    return Harness(general_repository(dsn), enqueue, clock, dsn)


def worker(harness: Harness, kind: Literal["transcription", "render"], *,
           profile: str = "v1", eligible: bool = True) -> Worker:
    repository = harness.repository
    result = repository.register_worker(Worker(
        EntityId.new(), "test-node-" + uuid4().hex, "test-deployment", harness.request.event_id,
        True, False, "test-v1", 1, NOW, NOW,
    ))
    repository.register_capability(WorkerCapability(
        EntityId.new(), result.id, kind, "v1", "test-profile", profile, ExecutionLocality.LOCAL,
        ("wav",) if kind == "transcription" else None, kind == "transcription", False,
        None, None, None, None, "test-runtime", "1" * 64, eligible, NOW,
    ))
    presence(harness, result)
    return result


def presence(harness: Harness, value: Worker) -> None:
    harness.repository.record_presence(value.id, ttl=timedelta(minutes=30), maximum_concurrency=1,
                                       health=WorkerHealth.AVAILABLE,
                                       pressure=WorkerPressure.NORMAL)


def claim_request(value: Worker) -> ClaimRequest:
    return ClaimRequest(value.id, EventNetworkPolicy.LOCAL_ONLY, timedelta(seconds=30))


def test_render_input_is_tagged_immutable_and_rejects_paths_and_naive_time() -> None:
    request = render_request()
    assert request.input.kind == "render"
    with pytest.raises(FrozenInstanceError):
        request.input.__setattr__("output_token", "changed")
    for token in ("../escape", "C:\\output", "/absolute", "a.b", ""):
        with pytest.raises(ValueError, match="opaque token"):
            replace(request.input, output_token=token)
    with pytest.raises(ValueError):
        replace(request, requested_at=NOW.replace(tzinfo=None))
    assert render_work_key(request) == render_work_key(replace(
        request, input=replace(request.input, output_token="another-output"),
    ))
    assert render_work_key(request) != render_work_key(replace(
        request, input=replace(request.input, execution_profile_version="v2"),
    ))


def test_render_replay_claim_isolation_and_transcription_unchanged(harness: Harness) -> None:
    repository = harness.repository
    pending = pending_render_operation(harness.request)
    rendered = repository.enqueue(pending)
    assert repository.enqueue(pending) == rendered
    repeated = replace(harness.request, operation_id=EntityId.new(),
                       idempotency_key="another-command", input=replace(
                           harness.request.input, output_token="another-output"))
    assert repository.enqueue(pending_render_operation(repeated)) == rendered
    with pytest.raises(WorkExecutionConflictError):
        repository.enqueue(pending_render_operation(replace(harness.request, priority=99)))
    transcription_worker = worker(harness, "transcription")
    assert repository.claim_next(claim_request(transcription_worker)) is None
    assert repository.claim_next(claim_request(worker(harness, "render", profile="v2"))) is None
    assert repository.claim_next(claim_request(worker(harness, "render", eligible=False))) is None
    input_value = operation_input()
    if harness.dsn is not None:
        _, asset, manifest = seed_asset(harness.dsn, observed_at=NOW)
        input_value = replace(input_value, asset_id=asset, manifest_id=manifest)
    transcription_request = replace(enqueue_request(input_value), event_id=harness.request.event_id)
    transcription = TranscriptionOperationApplication(repository).enqueue(transcription_request)
    assert transcription.input == input_value
    renderer = worker(harness, "render")
    render_claim = repository.claim_next(claim_request(renderer))
    assert render_claim is not None and render_claim.operation.id == rendered.id
    assert render_claim.operation.input == harness.request.input
    assert repository.claim_next(claim_request(renderer)) is None
    transcript_claim = repository.claim_next(claim_request(transcription_worker))
    assert transcript_claim is not None and transcript_claim.operation.id == transcription.id
    assert transcript_claim.operation.input == input_value
    if harness.dsn is not None:
        restarted = general_repository(harness.dsn)
        assert restarted.get_operation(rendered.id) == render_claim.operation
        assert restarted.list_operations(deployment_id="test-deployment",
                                         event_id=harness.request.event_id)


def test_render_lease_retry_expiry_fencing_and_attempt_history(harness: Harness) -> None:
    repository = harness.repository
    operation = repository.enqueue(pending_render_operation(harness.request))
    renderer = worker(harness, "render")
    first = repository.claim_next(claim_request(renderer))
    assert first is not None
    active = repository.mark_running(first)
    renewed = repository.renew(active, lease_duration=timedelta(seconds=45))
    assert renewed.operation.status == OperationStatus.RUNNING
    assert renewed.operation.lease_expires_at is not None
    assert renewed.operation.lease_expires_at >= first.attempt.lease_expires_at
    failure = OperationFailure("synthetic_failure", True, "synthetic retry")
    failed = repository.record_failure(renewed, failure)
    assert failed.status == OperationStatus.RETRY_WAIT
    assert repository.claim_next(claim_request(renderer)) is None
    harness.elapse(operation.id)
    second = repository.claim_next(claim_request(renderer))
    assert second is not None and second.attempt.fence_generation == 2
    with pytest.raises(WorkExecutionLeaseLostError):
        repository.renew(first, lease_duration=timedelta(seconds=30))
    with pytest.raises(WorkExecutionLeaseLostError):
        repository.record_failure(first, failure)
    harness.elapse(operation.id, expire=True)
    with pytest.raises(WorkExecutionLeaseLostError):
        repository.mark_running(second)
    assert repository.reconcile_expired()[0].status == OperationStatus.RETRY_WAIT
    harness.elapse(operation.id)
    third = repository.claim_next(claim_request(renderer))
    assert third is not None and third.attempt.fence_generation == 3
    assert repository.record_failure(third, failure).status == OperationStatus.TERMINAL_FAILED
    attempts = repository.list_attempts(operation.id)
    assert [attempt.outcome for attempt in attempts] == [
        AttemptOutcome.RETRYABLE_FAILURE, AttemptOutcome.LEASE_LOST,
        AttemptOutcome.TERMINAL_FAILURE,
    ]
    assert repository.claim_next(claim_request(renderer)) is None


def schema_contract(dsn: str) -> tuple[object, object]:
    with psycopg.connect(dsn) as connection:
        constraints = connection.execute("""
            SELECT rel.relname, c.conname, pg_get_constraintdef(c.oid)
            FROM pg_constraint c JOIN pg_class rel ON rel.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = rel.relnamespace
            WHERE n.nspname = 'stageflow' AND rel.relname IN (
                'work_operation', 'work_worker_capability') ORDER BY 1, 2
        """).fetchall()
        columns = connection.execute("""
            SELECT table_name, column_name, is_nullable FROM information_schema.columns
            WHERE table_schema = 'stageflow' AND table_name IN (
                'work_operation', 'work_worker_capability') ORDER BY 1, 2
        """).fetchall()
    return constraints, columns


def test_migration_restores_exact_original_constraints_and_reapplies(
    render_postgres_dsn: str,
) -> None:
    dsn = render_postgres_dsn
    runner = PostgresMigrationRunner(dsn)
    runner.reverse_transcription_worker_v1()
    runner.apply_transcription_worker_v1()
    original = schema_contract(dsn)
    event, asset, manifest = seed_asset(dsn, observed_at=NOW)
    repository = PostgresWorkExecutionRepository(dsn)
    request = replace(enqueue_request(replace(operation_input(), asset_id=asset,
                                             manifest_id=manifest)), event_id=event)
    before = TranscriptionOperationApplication(repository).enqueue(request)
    runner.apply_render_durable_operation_v1()
    assert repository.get_operation(before.id) == before
    with psycopg.connect(dsn) as connection:
        for column in ("asset_id", "manifest_id", "manifest_version", "asset_format"):
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute(sql.SQL("UPDATE stageflow.work_operation SET {} = NULL "
                                           "WHERE operation_id = %s").format(
                                               sql.Identifier(column)),
                                   (before.id.value,))
    runner.reverse_render_durable_operation_v1()
    assert schema_contract(dsn) == original
    assert repository.get_operation(before.id) == before
    runner.apply_render_durable_operation_v1()
    runner.apply_render_durable_operation_v1()
    assert repository.get_operation(before.id) == before


def insert_output(dsn: str, operation_id: EntityId, attempt_id: EntityId,
                  value: RenderOperationInput, *,
                  manifest_content_key: str | None = "opaque-manifest",
                  manifest_sha256: str | None = "c" * 64) -> EntityId:
    output = EntityId.new()
    with psycopg.connect(dsn) as connection:
        connection.execute("""
            INSERT INTO stageflow.rendered_output (
                output_id, assembly_revision_id, render_profile_id, render_profile_version,
                operation_id, producing_attempt_id, content_key, sha256, byte_size, media_type,
                duration_microseconds, frame_count, ffmpeg_version, ffmpeg_sha256, produced_at,
                manifest_content_key, manifest_sha256
            ) VALUES (%s, %s, %s, %s, %s, %s, 'opaque-content', %s, 100, 'video/mp4',
                      1000000, 30, 'synthetic-version', %s, %s, %s, %s)
        """, (output.value, value.assembly_revision_id.value, value.execution_profile_id,
              value.execution_profile_version, operation_id.value, attempt_id.value,
              "a" * 64, "b" * 64, NOW, manifest_content_key, manifest_sha256))
    return output


def test_render_output_immutability_result_reconciliation_and_refused_reverse(
    render_postgres_dsn: str,
) -> None:
    dsn = render_postgres_dsn
    event, _, _ = seed_asset(dsn, observed_at=NOW)
    request = render_request()
    request = replace(request, event_id=event,
                      input=replace(request.input, assembly_revision_id=seed_revision(dsn, event)))
    repository = general_repository(dsn)
    harness = Harness(repository, request, MutableClock(), dsn)
    operation = repository.enqueue(pending_render_operation(request))
    runner = PostgresMigrationRunner(dsn)
    with pytest.raises(psycopg.errors.RaiseException, match="cannot reverse 0015"):
        runner.reverse_render_durable_operation_v1()
    renderer = worker(harness, "render")
    claim = repository.claim_next(claim_request(renderer))
    assert claim is not None
    with psycopg.connect(dsn) as connection:
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            connection.execute("""
                UPDATE stageflow.work_operation SET operation_status = 'succeeded',
                    current_attempt_id = NULL, lease_owner_worker_id = NULL, lease_expires_at = NULL
                WHERE operation_id = %s
            """, (operation.id.value,))
    output = insert_output(dsn, operation.id, claim.attempt.id, request.input)
    with psycopg.connect(dsn) as connection:
        for statement in (
            "UPDATE stageflow.rendered_output SET frame_count = 1 WHERE output_id = %s",
            "DELETE FROM stageflow.rendered_output WHERE output_id = %s",
        ):
            with pytest.raises(psycopg.errors.RaiseException,
                               match="render_history_is_immutable"), connection.transaction():
                connection.execute(statement, (output.value,))
        with pytest.raises(psycopg.errors.RaiseException,
                           match="render_history_is_immutable"), connection.transaction():
            connection.execute("DELETE FROM stageflow.render_operation_input "
                               "WHERE operation_id = %s",
                               (operation.id.value,))
    harness.elapse(operation.id, expire=True)
    reconciled = tuple(item for item in repository.reconcile_expired() if item.id == operation.id)
    assert len(reconciled) == 1
    assert reconciled[0].status == OperationStatus.SUCCEEDED
    assert reconciled[0].terminal_result_rendered_output_id == output
    assert reconciled[0].terminal_result_id is None
    assert repository.list_attempts(operation.id)[0].outcome == AttemptOutcome.RESULT_RECONCILED
    with pytest.raises(psycopg.errors.RaiseException, match="cannot reverse 0015"):
        runner.reverse_render_durable_operation_v1()
    assert repository.get_operation(operation.id) == reconciled[0]


def test_crossed_enqueue_identities_never_replay_another_operation(harness: Harness) -> None:
    repository = harness.repository
    first = repository.enqueue(pending_render_operation(harness.request))
    other = replace(harness.request, operation_id=EntityId.new(), idempotency_key="second-render",
                    input=replace(harness.request.input, execution_profile_version="v2"))
    second = repository.enqueue(pending_render_operation(other))
    for crossed in (
        replace(harness.request, operation_id=other.operation_id,
                idempotency_key=other.idempotency_key),
        replace(other, input=harness.request.input),
    ):
        with pytest.raises(WorkExecutionConflictError):
            repository.enqueue(pending_render_operation(crossed))
    assert repository.get_operation(first.id) == first
    assert repository.get_operation(second.id) == second


def test_render_capability_projection_and_degraded_presence_match(harness: Harness) -> None:
    repository = harness.repository
    request = replace(harness.request, required_for_event=True)
    operation = repository.enqueue(pending_render_operation(request))
    assert repository.claim_next(claim_request(worker(harness, "transcription"))) is None
    assert "required_missing_capability" in repository.status_projection(
        deployment_id=request.deployment_id, event_id=request.event_id,
    ).attention_codes
    renderer = worker(harness, "render")
    assert "required_missing_capability" not in repository.status_projection(
        deployment_id=request.deployment_id, event_id=request.event_id,
    ).attention_codes
    repository.record_presence(renderer.id, ttl=timedelta(minutes=5), maximum_concurrency=1,
                               health=WorkerHealth.DEGRADED, pressure=WorkerPressure.CONSTRAINED)
    claim = repository.claim_next(claim_request(renderer))
    assert claim is not None and claim.operation.id == operation.id


def test_postgres_typed_views_enforce_kind_for_claim_read_and_reconciliation(
    render_postgres_dsn: str,
) -> None:
    dsn = render_postgres_dsn
    event, _, _ = seed_asset(dsn, observed_at=NOW)
    request = render_request()
    request = replace(request, event_id=event,
                      input=replace(request.input, assembly_revision_id=seed_revision(dsn, event)))
    both = general_repository(dsn)
    harness = Harness(both, request, MutableClock(), dsn)
    operation = both.enqueue(pending_render_operation(request))
    renderer = worker(harness, "render")
    transcription = PostgresWorkExecutionRepository(dsn)
    with pytest.raises(WorkExecutionNotFoundError, match="operation_kind_not_supported"):
        transcription.get_operation(operation.id)
    assert transcription.claim_next(claim_request(renderer)) is None
    render_only = PostgresWorkExecutionRepository(dsn, input_types=(RenderOperationInput,))
    claim = render_only.claim_next(claim_request(renderer))
    assert claim is not None and claim.operation.id == operation.id
    harness.elapse(operation.id, expire=True)
    assert all(item.id != operation.id for item in transcription.reconcile_expired())
    assert both.get_operation(operation.id).status == OperationStatus.LEASED
    reconciled = render_only.reconcile_expired()
    assert len(reconciled) == 1 and reconciled[0].id == operation.id
    assert reconciled[0].status == OperationStatus.RETRY_WAIT


def transcription_request_for(harness: Harness) -> EnqueueTranscriptionOperation:
    value = operation_input()
    if harness.dsn is not None:
        _, asset, manifest = seed_asset(harness.dsn, observed_at=NOW)
        value = replace(value, asset_id=asset, manifest_id=manifest)
    return replace(enqueue_request(value), event_id=harness.request.event_id)


@pytest.mark.parametrize("operation_kind", ["transcription", "render"])
def test_only_eligible_operation_cannot_cross_worker_kind(
    harness: Harness, operation_kind: Literal["transcription", "render"],
) -> None:
    repository = harness.repository
    if operation_kind == "transcription":
        operation = TranscriptionOperationApplication(repository).enqueue(
            transcription_request_for(harness),
        )
        wrong_kind = "render"
    else:
        operation = repository.enqueue(pending_render_operation(harness.request))
        wrong_kind = "transcription"
    wrong_worker = worker(harness, wrong_kind)
    # Deliberately give the render capability every transcription feature. Kind must
    # be the sole mismatch, with only one operation and no existing leases.
    repository.register_capability(WorkerCapability(
        EntityId.new(), wrong_worker.id, wrong_kind, "v1", "test-profile", "v1",
        ExecutionLocality.LOCAL, ("wav",), True, False, None, None, None, None,
        "test-runtime", "1" * 64, True, NOW,
    ))
    assert repository.claim_next(claim_request(wrong_worker)) is None
    assert repository.list_attempts(operation.id) == ()
    assert repository.get_operation(operation.id).status == OperationStatus.ELIGIBLE
    # Positive control: the very same worker has free capacity and can claim once
    # a capability with the matching kind is registered.
    repository.register_capability(WorkerCapability(
        EntityId.new(), wrong_worker.id, operation_kind, "v1", "test-profile", "v1",
        ExecutionLocality.LOCAL, ("wav",), True, False, None, None, None, None,
        "test-runtime", "1" * 64, True, NOW,
    ))
    claim = repository.claim_next(claim_request(wrong_worker))
    assert claim is not None and claim.operation.id == operation.id


def test_transcription_worker_filters_render_on_general_repository(harness: Harness) -> None:
    operation = harness.repository.enqueue(pending_render_operation(harness.request))
    renderer = worker(harness, "render")
    port = Mock(spec=TranscriptionExecutionPort)
    cycle = TranscriptionWorker(harness.repository, port).run_once(claim_request(renderer))
    assert cycle.outcome == WorkerCycleOutcome.IDLE
    port.execute.assert_not_called()
    assert harness.repository.list_attempts(operation.id) == ()
    claim = harness.repository.claim_next(claim_request(renderer))
    assert claim is not None and claim.operation.id == operation.id


def test_render_claim_refuses_transcript_result_at_repository_and_application(
    harness: Harness,
) -> None:
    operation = harness.repository.enqueue(pending_render_operation(harness.request))
    claim = harness.repository.claim_next(claim_request(worker(harness, "render")))
    assert claim is not None
    result = transcript_result()
    pending = prepare_transcript_evidence(claimed_operation(operation_input()), result)
    pending = replace(pending, operation_id=operation.id, work_key=operation.work_key)
    with pytest.raises(WorkExecutionConflictError,
                       match="transcript_result_requires_transcription"):
        harness.repository.apply_transcript_result(claim, pending)
    with pytest.raises(ValueError, match="transcript_result_requires_transcription"):
        prepare_transcript_evidence(claim, result)
    assert harness.repository.get_operation(operation.id) == claim.operation
    with pytest.raises(WorkExecutionNotFoundError):
        harness.repository.get_transcript_evidence(pending.id)


@pytest.mark.parametrize("kind", ["transcription", "render"])
def test_typed_repository_refuses_other_kind_before_storage(
    kind: Literal["transcription", "render"], monkeypatch: pytest.MonkeyPatch,
) -> None:
    connect = Mock(side_effect=AssertionError("kind rejection must precede storage"))
    monkeypatch.setattr(psycopg.Connection, "connect", connect)
    repository = PostgresWorkExecutionRepository[OperationInput](
        "unused", input_types=(TranscriptionOperationInput,) if kind == "transcription"
        else (RenderOperationInput,),
    )
    if kind == "transcription":
        pending = pending_render_operation(render_request())
    else:
        request = enqueue_request(operation_input())
        pending = PendingOperation(request, enqueue_request_digest(request),
                                   transcription_work_key(request))
    with pytest.raises(WorkExecutionConflictError, match="operation_kind_not_supported"):
        repository.enqueue(pending)
    connect.assert_not_called()


def test_transcription_enqueue_refuses_render_returned_by_repository(
    harness: Harness, monkeypatch: pytest.MonkeyPatch,
) -> None:
    operation = harness.repository.enqueue(pending_render_operation(harness.request))
    monkeypatch.setattr(harness.repository, "enqueue", Mock(return_value=operation))
    with pytest.raises(ValueError, match="transcription_enqueue_requires_transcription"):
        TranscriptionOperationApplication(harness.repository).enqueue(enqueue_request(operation_input()))


def test_transcription_worker_reports_typed_error_for_incorrect_repository_claim(
    harness: Harness, monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness.repository.enqueue(pending_render_operation(harness.request))
    renderer = worker(harness, "render")
    claim = harness.repository.claim_next(claim_request(renderer))
    assert claim is not None
    monkeypatch.setattr(harness.repository, "claim_next", Mock(return_value=claim))
    port = Mock(spec=TranscriptionExecutionPort)
    with pytest.raises(WorkExecutionConflictError,
                       match="transcription_worker_requires_transcription"):
        TranscriptionWorker(harness.repository, port).run_once(claim_request(renderer))
    port.execute.assert_not_called()


def postgres_harness(dsn: str) -> Harness:
    event, _, _ = seed_asset(dsn, observed_at=NOW)
    request = render_request()
    return Harness(general_repository(dsn), replace(
        request, event_id=event,
        input=replace(request.input, assembly_revision_id=seed_revision(dsn, event)),
    ), MutableClock(), dsn)


def test_render_input_rejects_transcription_operation(render_postgres_dsn: str) -> None:
    harness = postgres_harness(render_postgres_dsn)
    operation = TranscriptionOperationApplication(harness.repository).enqueue(
        transcription_request_for(harness),
    )
    with psycopg.connect(render_postgres_dsn) as connection:
        with pytest.raises(psycopg.errors.RaiseException,
                           match="render_input_operation_mismatch"), connection.transaction():
            connection.execute("""
                INSERT INTO stageflow.render_operation_input (
                    operation_id, assembly_revision_id, render_profile_id,
                    render_profile_version, output_token
                ) VALUES (%s, %s, 'test-profile', 'v1', 'opaque-output')
            """, (operation.id.value, harness.request.input.assembly_revision_id.value))


def test_render_output_rejects_attempt_from_another_operation(render_postgres_dsn: str) -> None:
    harness = postgres_harness(render_postgres_dsn)
    operation = harness.repository.enqueue(pending_render_operation(harness.request))
    first = harness.repository.claim_next(claim_request(worker(harness, "render")))
    assert first is not None and first.operation.id == operation.id
    other_request = replace(harness.request, operation_id=EntityId.new(),
                            idempotency_key="other-render", input=replace(
                                harness.request.input, execution_profile_version="v2"))
    other = harness.repository.enqueue(pending_render_operation(other_request))
    second = harness.repository.claim_next(claim_request(worker(harness, "render", profile="v2")))
    assert second is not None and second.operation.id == other.id
    with pytest.raises(psycopg.errors.RaiseException, match="render_output_attempt_mismatch"):
        insert_output(render_postgres_dsn, operation.id, second.attempt.id, harness.request.input)
    insert_output(render_postgres_dsn, operation.id, first.attempt.id, harness.request.input)


@pytest.mark.parametrize("mismatch", ["revision", "profile_id", "profile_version"])
def test_render_output_composite_foreign_key_rejects_mismatched_input(
    render_postgres_dsn: str, mismatch: str,
) -> None:
    harness = postgres_harness(render_postgres_dsn)
    operation = harness.repository.enqueue(pending_render_operation(harness.request))
    claim = harness.repository.claim_next(claim_request(worker(harness, "render")))
    assert claim is not None
    value = harness.request.input
    if mismatch == "revision":
        other_event, _, _ = seed_asset(render_postgres_dsn, observed_at=NOW)
        value = replace(value, assembly_revision_id=seed_revision(
            render_postgres_dsn, other_event,
        ))
    elif mismatch == "profile_id":
        value = replace(value, execution_profile_id="another-profile")
    else:
        value = replace(value, execution_profile_version="v2")
    with pytest.raises(psycopg.errors.ForeignKeyViolation) as failure:
        insert_output(render_postgres_dsn, operation.id, claim.attempt.id, value)
    assert failure.value.diag.table_name == "rendered_output"
    assert "render_operation_input" in str(failure.value)
    insert_output(render_postgres_dsn, operation.id, claim.attempt.id, harness.request.input)


@pytest.mark.parametrize("formats", [None, ()])
def test_transcription_capability_contract_still_requires_formats(
    formats: tuple[str, ...] | None,
) -> None:
    with pytest.raises(ValueError, match="requires an accepted asset format"):
        WorkerCapability(
            EntityId.new(), EntityId.new(), "transcription", "v1", "test-profile", "v1",
            ExecutionLocality.LOCAL, formats, True, False, None, None, None, None,
            "test-runtime", "1" * 64, True, NOW,
        )


@pytest.mark.parametrize("formats", [None, []])
def test_forward_migration_preserves_transcription_capability_formats_guard(
    render_postgres_dsn: str, formats: list[str] | None,
) -> None:
    harness = postgres_harness(render_postgres_dsn)
    value = worker(harness, "transcription")
    with psycopg.connect(render_postgres_dsn) as connection:
        with pytest.raises(psycopg.errors.CheckViolation) as failure, connection.transaction():
            connection.execute("""
                UPDATE stageflow.work_worker_capability SET accepted_asset_formats = %s
                WHERE worker_id = %s
            """, (formats, value.id.value))
        assert failure.value.diag.constraint_name == (
            "work_worker_capability_accepted_asset_formats_check"
        )


def test_forward_migration_transcription_success_still_requires_result(
    render_postgres_dsn: str,
) -> None:
    harness = postgres_harness(render_postgres_dsn)
    operation = TranscriptionOperationApplication(harness.repository).enqueue(
        transcription_request_for(harness),
    )
    with psycopg.connect(render_postgres_dsn) as connection:
        with pytest.raises(psycopg.errors.CheckViolation) as failure, connection.transaction():
            connection.execute("""
                UPDATE stageflow.work_operation SET operation_status = 'succeeded'
                WHERE operation_id = %s
            """, (operation.id.value,))
        assert failure.value.diag.constraint_name == "work_operation_check4"
    assert harness.repository.get_operation(operation.id) == operation


def test_reverse_refuses_render_capability_without_render_operations(
    render_postgres_dsn: str,
) -> None:
    harness = postgres_harness(render_postgres_dsn)
    worker(harness, "render")
    with psycopg.connect(render_postgres_dsn) as connection:
        for table in ("work_operation", "render_operation_input", "rendered_output"):
            rows = connection.execute(sql.SQL("SELECT * FROM stageflow.{}").format(
                sql.Identifier(table),
            )).fetchall()
            assert rows == []
    before = schema_contract(render_postgres_dsn)
    with pytest.raises(psycopg.errors.RaiseException, match="cannot reverse 0015"):
        PostgresMigrationRunner(render_postgres_dsn).reverse_render_durable_operation_v1()
    assert schema_contract(render_postgres_dsn) == before


@pytest.mark.parametrize("field", ["terminal_result_id", "terminal_result_revision", "both"])
def test_render_operation_cannot_hold_transcript_terminal_reference(
    render_postgres_dsn: str, field: str,
) -> None:
    harness = postgres_harness(render_postgres_dsn)
    operation = harness.repository.enqueue(pending_render_operation(harness.request))
    with psycopg.connect(render_postgres_dsn) as connection:
        with pytest.raises(psycopg.errors.CheckViolation) as failure, connection.transaction():
            connection.execute("""
                UPDATE stageflow.work_operation
                SET terminal_result_id = %s, terminal_result_revision = %s
                WHERE operation_id = %s
            """, (EntityId.new().value if field != "terminal_result_revision" else None,
                  1 if field != "terminal_result_id" else None, operation.id.value))
        assert failure.value.diag.constraint_name == "work_operation_transcription_result_check"
    assert harness.repository.get_operation(operation.id) == operation


@pytest.mark.parametrize(("key", "digest", "violation"), [
    (None, "c" * 64, psycopg.errors.NotNullViolation),
    ("manifest", None, psycopg.errors.NotNullViolation),
    ("../manifest", "c" * 64, psycopg.errors.CheckViolation),
    ("C:\\manifest", "c" * 64, psycopg.errors.CheckViolation),
    ("", "c" * 64, psycopg.errors.CheckViolation),
    ("manifest", "C" * 64, psycopg.errors.CheckViolation),
    ("manifest", "c" * 63, psycopg.errors.CheckViolation),
    ("manifest", "g" * 64, psycopg.errors.CheckViolation),
])
def test_render_output_requires_opaque_sidecar_manifest_identity(
    render_postgres_dsn: str, key: str | None, digest: str | None,
    violation: type[psycopg.IntegrityError],
) -> None:
    harness = postgres_harness(render_postgres_dsn)
    operation = harness.repository.enqueue(pending_render_operation(harness.request))
    claim = harness.repository.claim_next(claim_request(worker(harness, "render")))
    assert claim is not None
    with pytest.raises(violation):
        insert_output(render_postgres_dsn, operation.id, claim.attempt.id, harness.request.input,
                      manifest_content_key=key, manifest_sha256=digest)
    output = insert_output(render_postgres_dsn, operation.id, claim.attempt.id,
                           harness.request.input)
    with psycopg.connect(render_postgres_dsn) as connection:
        row = connection.execute("""
            SELECT manifest_content_key, manifest_sha256 FROM stageflow.rendered_output
            WHERE output_id = %s
        """, (output.value,)).fetchone()
        assert row == {"manifest_content_key": "opaque-manifest", "manifest_sha256": "c" * 64}
