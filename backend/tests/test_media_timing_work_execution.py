from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import FrozenInstanceError, dataclass, replace
from datetime import timedelta
from types import SimpleNamespace
from typing import TypedDict
from uuid import uuid4

import psycopg
import pytest
from media_timing_evidence_fixtures import evidence_request
from psycopg.rows import tuple_row
from psycopg.types.json import Jsonb
from test_render_work_execution import (
    NOW,
    MutableClock,
    render_postgres_dsn,
    render_request,
    schema_contract,
    seed_asset,
    seed_revision,
)
from test_transcription_worker_substrate import enqueue_request, operation_input

from app.contexts.production.media_timing_evidence import MediaTimingEvidenceApplication
from app.contexts.work_execution import (
    AttemptOutcome,
    ClaimRequest,
    EventNetworkPolicy,
    ExecutionLocality,
    MediaTimingOperationInput,
    OperationFailure,
    OperationInput,
    OperationStatus,
    RenderOperationInput,
    TranscriptionOperationApplication,
    TranscriptionOperationInput,
    Worker,
    WorkerCapability,
    WorkerHealth,
    WorkerPressure,
    WorkExecutionConflictError,
    WorkExecutionLeaseLostError,
    WorkExecutionNotFoundError,
)
from app.contexts.work_execution.application import (
    media_timing_work_key,
    pending_media_timing_operation,
    pending_render_operation,
)
from app.contexts.work_execution.contracts import EnqueueOperation
from app.contexts.work_execution.memory import InMemoryWorkExecutionRepository
from app.demo import controller
from app.infrastructure.postgres import (
    PostgresMediaTimingEvidenceRepository,
    PostgresMigrationRunner,
    PostgresWorkExecutionRepository,
)
from app.infrastructure.postgres.media_timing_work_repository import (
    PostgresMediaTimingWorkRepository,
)
from app.infrastructure.postgres.render_repository import PostgresRenderRepository
from app.shared.ids import EntityId

# Reuse the isolated transactional PostgreSQL fixture, never the operator's live schema.
__all__ = ["render_postgres_dsn"]

INPUT_TYPES = (TranscriptionOperationInput, RenderOperationInput, MediaTimingOperationInput)
type Repository = InMemoryWorkExecutionRepository | PostgresWorkExecutionRepository[OperationInput]


class ProjectionScope(TypedDict):
    deployment_id: str
    event_id: EntityId | None


def timing_request() -> EnqueueOperation[MediaTimingOperationInput]:
    return EnqueueOperation(
        EntityId.new(), "timing-" + uuid4().hex, "test-deployment", None,
        MediaTimingOperationInput(EntityId.new(), EntityId.new(), "v1", "test-profile", "v1"),
        100, NOW, 3, timedelta(seconds=5), True, NOW,
    )


@dataclass
class Harness:
    repository: Repository
    request: EnqueueOperation[MediaTimingOperationInput]
    clock: MutableClock
    dsn: str | None

    def elapse(self, operation_id: EntityId, *, expire: bool = False) -> None:
        self.clock.at += timedelta(minutes=2)
        if self.dsn is not None:
            with psycopg.connect(self.dsn) as conn:
                conn.execute("UPDATE stageflow.work_operation SET eligible_at = "
                             "statement_timestamp() - interval '1 second' WHERE operation_id = %s",
                             (operation_id.value,))
                if expire:
                    conn.execute("UPDATE stageflow.work_operation SET lease_expires_at = "
                                 "statement_timestamp() - interval '1 second' "
                                 "WHERE operation_id = %s", (operation_id.value,))

    def view(self, input_types: tuple[type[OperationInput], ...]) -> Repository:
        if self.dsn is not None:
            return PostgresWorkExecutionRepository[OperationInput](
                self.dsn, input_types=input_types,
            )
        assert isinstance(self.repository, InMemoryWorkExecutionRepository)
        view = InMemoryWorkExecutionRepository(self.clock, input_types=input_types)
        view.operations = self.repository.operations
        view.attempts = self.repository.attempts
        view.workers = self.repository.workers
        view.capabilities = self.repository.capabilities
        view.presence = self.repository.presence
        return view


@pytest.fixture(params=["memory", "postgres"])
def harness(request: pytest.FixtureRequest) -> Harness:
    clock, enqueue = MutableClock(), timing_request()
    if request.param == "memory":
        return Harness(InMemoryWorkExecutionRepository(clock), enqueue, clock, None)
    dsn: str = request.getfixturevalue("render_postgres_dsn")
    event, asset, manifest = seed_asset(dsn, observed_at=NOW)
    enqueue = replace(enqueue, event_id=event, input=replace(
        enqueue.input, asset_id=asset, manifest_id=manifest,
    ))
    return Harness(PostgresWorkExecutionRepository[OperationInput](dsn, input_types=INPUT_TYPES),
                   enqueue, clock, dsn)


def worker(harness: Harness, kind: str, *, profile: str = "v1",
           eligible: bool = True, worker_id: EntityId | None = None) -> Worker:
    repo = harness.repository
    value = repo.register_worker(Worker(
        worker_id or EntityId.new(), "node-" + uuid4().hex,
        "test-deployment", harness.request.event_id,
        True, False, "v1", 1, NOW, NOW,
    ))
    repo.register_capability(WorkerCapability(
        EntityId.new(), value.id, kind, "v1", "test-profile", profile, ExecutionLocality.LOCAL,
        ("wav",) if kind == "transcription" else None, kind == "transcription", False,
        None, None, None, None, "synthetic-runtime", "v1", eligible, NOW,
    ))
    repo.record_presence(value.id, ttl=timedelta(minutes=30), maximum_concurrency=1,
                         health=WorkerHealth.AVAILABLE, pressure=WorkerPressure.NORMAL)
    return value


def claim_request(value: Worker) -> ClaimRequest:
    return ClaimRequest(value.id, EventNetworkPolicy.LOCAL_ONLY, timedelta(seconds=30))


def test_timing_input_identity_is_immutable_sanitized_and_aware() -> None:
    request = timing_request()
    assert request.input.kind == "media_timing"
    assert request.input.execution_profile_id == request.input.inspection_profile_id
    assert request.input.execution_profile_version == request.input.inspection_profile_version
    assert request.input.requires_cloud is False
    with pytest.raises(FrozenInstanceError):
        request.input.__setattr__("manifest_version", "v2")
    with pytest.raises(ValueError):
        replace(request, requested_at=NOW.replace(tzinfo=None))
    for field in ("manifest_version", "inspection_profile_id", "inspection_profile_version"):
        with pytest.raises(ValueError):
            replace(request.input, **{field: "../invalid"})
        assert media_timing_work_key(request) != media_timing_work_key(replace(
            request, input=replace(request.input, **{field: "v2"}),
        ))
    for field in ("asset_id", "manifest_id"):
        assert media_timing_work_key(request) != media_timing_work_key(replace(
            request, input=replace(request.input, **{field: EntityId.new()}),
        ))


def test_timing_work_key_replay_and_claim_capability(harness: Harness) -> None:
    repo, request = harness.repository, harness.request
    pending = pending_media_timing_operation(request)
    original = repo.enqueue(pending)
    assert repo.enqueue(pending) == original
    replay = replace(request, operation_id=EntityId.new(), idempotency_key="another-request")
    assert repo.enqueue(pending_media_timing_operation(replay)) == original
    with pytest.raises(WorkExecutionConflictError):
        repo.enqueue(pending_media_timing_operation(replace(request, priority=99)))
    for kind in ("transcription", "render"):
        assert repo.claim_next(claim_request(worker(harness, kind))) is None
    for value in (worker(harness, "media_timing", profile="v2"),
                  worker(harness, "media_timing", eligible=False)):
        assert repo.claim_next(claim_request(value)) is None
    inspector = worker(harness, "media_timing")
    assert repo.claim_next(replace(claim_request(inspector), operation_kind="render")) is None
    claim = repo.claim_next(replace(claim_request(inspector), operation_kind="media_timing"))
    assert claim is not None and claim.operation.id == original.id
    assert claim.operation.input == request.input
    assert repo.claim_next(claim_request(inspector)) is None
    if harness.dsn is not None:
        typed = PostgresMediaTimingWorkRepository(harness.dsn)
        assert typed.get_operation(original.id) == claim.operation
        with psycopg.connect(harness.dsn) as conn:
            row = conn.execute("SELECT asset_format, requested_language, request_word_timing, "
                               "request_speaker_labels FROM stageflow.work_operation "
                               "WHERE operation_id = %s", (original.id.value,)).fetchone()
            assert row == {"asset_format": None, "requested_language": None,
                           "request_word_timing": False, "request_speaker_labels": False}


def seed_other_kinds(harness: Harness) -> tuple[EntityId, EntityId]:
    request = harness.request
    transcription = replace(enqueue_request(replace(
        operation_input(), asset_id=request.input.asset_id, manifest_id=request.input.manifest_id,
    )), event_id=request.event_id)
    rendering = replace(render_request(), event_id=request.event_id,
                        requested_at=NOW - timedelta(seconds=1))
    if harness.dsn is not None:
        assert request.event_id is not None
        rendering = replace(rendering, input=replace(
            rendering.input, assembly_revision_id=seed_revision(harness.dsn, request.event_id),
        ))
    return (TranscriptionOperationApplication(harness.repository).enqueue(transcription).id,
            harness.repository.enqueue(pending_render_operation(rendering)).id)


def test_three_kind_isolation_before_claims_lists_counts_and_limits(harness: Harness) -> None:
    repo = harness.repository
    transcript, render = seed_other_kinds(harness)
    # Many higher-priority timing rows must not consume another view's limit or claim.
    timing_ids: list[EntityId] = []
    for index in range(4):
        request = replace(harness.request, operation_id=EntityId.new(),
                          idempotency_key=f"timing-{index}", required_for_event=index == 0,
                          input=replace(
                              harness.request.input, inspection_profile_version=f"v{index + 1}"))
        timing_ids.append(repo.enqueue(pending_media_timing_operation(request)).id)
    args: ProjectionScope = {
        "deployment_id": "test-deployment", "event_id": harness.request.event_id,
    }
    assert len(repo.list_operations(**args)) == 6
    assert repo.list_operations(**args, limit=1)[0].id in timing_ids
    for input_type, expected in ((TranscriptionOperationInput, {transcript}),
                                 (RenderOperationInput, {render}),
                                 (MediaTimingOperationInput, set(timing_ids))):
        view = harness.view((input_type,))
        assert {o.id for o in view.list_operations(**args)} == expected
        assert view.list_operations(**args, limit=1)[0].id in expected
        assert sum(c.count for c in view.status_projection(**args).counts) == len(expected)
        for hidden in {transcript, render, *timing_ids} - expected:
            with pytest.raises(WorkExecutionNotFoundError):
                view.get_operation(hidden)
            assert view.list_attempts(hidden) == ()
    # Explicit two-kind views remain two-kind after the new third kind is added.
    pair = harness.view((TranscriptionOperationInput, RenderOperationInput))
    assert {o.id for o in pair.list_operations(**args)} == {transcript, render}
    assert sum(c.count for c in pair.status_projection(**args).counts) == 2
    for kind, expected in (("transcription", transcript), ("render", render),
                           ("media_timing", timing_ids[0])):
        value = worker(harness, kind)
        claim = repo.claim_next(claim_request(value))
        assert claim is not None and claim.operation.id == expected
        own = harness.view((type(claim.operation.input),))
        assert own.status_projection(**args).active_lease_count == 1
        assert len(own.list_attempts(expected)) == 1
        assert "required_missing_capability" not in own.status_projection(**args).attention_codes
        repo.record_failure(claim, OperationFailure("synthetic_failure", False, "synthetic"))
        assert repo.claim_next(claim_request(value)) is None
    if harness.dsn is not None:
        assert {o.id for o in PostgresWorkExecutionRepository(harness.dsn).list_operations(
            **args)} == {transcript}
        assert {o.id for o in PostgresRenderRepository(harness.dsn).list_operations(
            **args)} == {render}
        assert {o.id for o in PostgresMediaTimingWorkRepository(harness.dsn).list_operations(
            **args)} == set(timing_ids)


def test_timing_lease_retry_fence_and_reconciliation(harness: Harness) -> None:
    repo = harness.repository
    operation = repo.enqueue(pending_media_timing_operation(harness.request))
    inspector = worker(harness, "media_timing")
    first = repo.claim_next(claim_request(inspector))
    assert first is not None
    active = repo.mark_running(first)
    renewed = repo.renew(active, lease_duration=timedelta(seconds=45))
    assert renewed.operation.status == OperationStatus.RUNNING
    assert renewed.attempt.lease_expires_at >= first.attempt.lease_expires_at
    failure = OperationFailure("synthetic_failure", True, "synthetic retry")
    assert repo.record_failure(renewed, failure).status == OperationStatus.RETRY_WAIT
    assert repo.claim_next(claim_request(inspector)) is None
    harness.elapse(operation.id)
    second = repo.claim_next(claim_request(inspector))
    assert second is not None and second.attempt.fence_generation == 2
    with pytest.raises(WorkExecutionLeaseLostError):
        repo.renew(first, lease_duration=timedelta(seconds=30))
    with pytest.raises(WorkExecutionLeaseLostError):
        repo.record_failure(first, failure)
    harness.elapse(operation.id, expire=True)
    with pytest.raises(WorkExecutionLeaseLostError):
        repo.mark_running(second)
    other_kinds = harness.view((TranscriptionOperationInput, RenderOperationInput))
    assert other_kinds.reconcile_expired() == ()
    assert repo.reconcile_expired(limit=1)[0].status == OperationStatus.RETRY_WAIT
    harness.elapse(operation.id)
    third = repo.claim_next(claim_request(inspector))
    assert third is not None and third.attempt.fence_generation == 3
    assert repo.record_failure(third, failure).status == OperationStatus.TERMINAL_FAILED
    assert [a.outcome for a in repo.list_attempts(operation.id)] == [
        AttemptOutcome.RETRYABLE_FAILURE, AttemptOutcome.LEASE_LOST,
        AttemptOutcome.TERMINAL_FAILURE,
    ]


def test_migration_0017_restores_exact_schema_preserving_existing_rows(
    render_postgres_dsn: str,
) -> None:
    dsn = render_postgres_dsn
    runner = PostgresMigrationRunner(dsn)
    # The fixture deliberately borrows one connection across DDL; runtime repositories
    # open fresh connections. Avoid cached SELECT * plans surviving add/drop columns.
    with psycopg.connect(dsn) as conn:
        conn.prepare_threshold = None
    runner.reverse_media_timing_operation_v1()
    original = schema_contract(dsn)
    event, asset, manifest = seed_asset(dsn, observed_at=NOW)
    request = replace(timing_request(), event_id=event, input=MediaTimingOperationInput(
        asset, manifest, "v1", "test-profile", "v1",
    ))
    repo = PostgresWorkExecutionRepository[OperationInput](dsn, input_types=INPUT_TYPES)
    harness = Harness(repo, request, MutableClock(), dsn)
    ids = seed_other_kinds(harness)
    before = tuple(repo.get_operation(value) for value in ids)
    runner.apply_media_timing_operation_v1()
    runner.apply_media_timing_operation_v1()
    assert tuple(repo.get_operation(value) for value in ids) == before
    runner.reverse_media_timing_operation_v1()
    assert schema_contract(dsn) == original
    assert tuple(repo.get_operation(value) for value in ids) == before
    runner.apply_media_timing_operation_v1()
    assert tuple(repo.get_operation(value) for value in ids) == before


def apply_evidence(dsn: str, request: EnqueueOperation[MediaTimingOperationInput]) -> EntityId:
    # Synthetic evidence is written only through the existing application boundary.
    value = replace(evidence_request(), operation_id=request.operation_id,
                    asset_id=request.input.asset_id, manifest_id=request.input.manifest_id,
                    manifest_version=request.input.manifest_version)
    application = MediaTimingEvidenceApplication(PostgresMediaTimingEvidenceRepository(dsn))
    return application.apply(value).id


@pytest.mark.parametrize("branch", ["operations", "capabilities", "result references"])
def test_migration_0017_refuses_reverse_without_losing_state(
    render_postgres_dsn: str, branch: str,
) -> None:
    dsn = render_postgres_dsn
    event, asset, manifest = seed_asset(dsn, observed_at=NOW)
    request = replace(timing_request(), event_id=event, input=MediaTimingOperationInput(
        asset, manifest, "v1", "test-profile", "v1",
    ))
    repo = PostgresWorkExecutionRepository[OperationInput](dsn, input_types=INPUT_TYPES)
    harness = Harness(repo, request, MutableClock(), dsn)
    if branch == "capabilities":
        worker(harness, "media_timing")
    else:
        operation = repo.enqueue(pending_media_timing_operation(request))
        if branch == "result references":
            evidence = apply_evidence(dsn, request)
            with psycopg.connect(dsn) as conn:
                conn.execute("UPDATE stageflow.work_operation SET operation_status = 'succeeded', "
                             "terminal_result_type = 'media_timing_evidence', "
                             "terminal_result_media_timing_evidence_id = %s "
                             "WHERE operation_id = %s",
                             (evidence.value, operation.id.value))
            hydrated = repo.get_operation(operation.id)
            assert hydrated.terminal_result_media_timing_evidence_id == evidence
    # Isolate the refused 0017 reverse from its separately committed successor reversal.
    PostgresMigrationRunner(dsn).reverse_assembly_timing_evidence_v1()
    before = schema_contract(dsn)
    message = f"cannot reverse 0017: media_timing {branch}"
    with pytest.raises(psycopg.errors.RaiseException, match=message):
        PostgresMigrationRunner(dsn).reverse_media_timing_operation_v1()
    assert schema_contract(dsn) == before


@pytest.mark.parametrize(("kind", "changes", "constraint"), [
    ("media_timing", {"operation_kind": "unknown"}, "work_operation_operation_kind_check"),
    *[(kind, {field: None}, "work_operation_transcription_source_check")
      for kind in ("transcription", "media_timing")
      for field in ("asset_id", "manifest_id", "manifest_version")],
    ("transcription", {"asset_format": None}, "work_operation_transcription_source_check"),
    *[(kind, {"operation_status": "succeeded"}, "work_operation_check4")
      for kind in ("transcription", "render", "media_timing")],
    *[(kind, {"terminal_result_media_timing_evidence_id": str(uuid4())},
       "work_operation_media_timing_result_kind_check") for kind in ("transcription", "render")],
    *[(kind, {"terminal_result_rendered_output_id": str(uuid4())},
       "work_operation_render_result_kind_check") for kind in ("transcription", "media_timing")],
    *[("media_timing", {field: value}, "work_operation_transcription_result_check")
      for field, value in (("terminal_result_id", str(uuid4())), ("terminal_result_revision", 1))],
    ("media_timing", {"terminal_result_media_timing_evidence_id": str(uuid4())},
     "work_operation_media_timing_evidence_fk"),
])
def test_0017_rejects_invalid_operation_inserts(
    render_postgres_dsn: str, kind: str, changes: dict[str, object], constraint: str,
) -> None:
    dsn = render_postgres_dsn
    event, asset, manifest = seed_asset(dsn, observed_at=NOW)
    request = replace(timing_request(), event_id=event, input=MediaTimingOperationInput(
        asset, manifest, "v1", "test-profile", "v1",
    ))
    repo = PostgresMediaTimingWorkRepository(dsn)
    original = repo.enqueue(pending_media_timing_operation(request))
    overrides = {"operation_id": str(uuid4()), "idempotency_key": uuid4().hex,
                 "work_key": uuid4().hex + uuid4().hex, "operation_kind": kind,
                 "asset_format": "wav" if kind == "transcription" else None, **changes}
    with psycopg.connect(dsn) as conn:
        with pytest.raises(psycopg.IntegrityError) as error, conn.transaction():
            conn.execute("INSERT INTO stageflow.work_operation SELECT "
                         "(jsonb_populate_record(NULL::stageflow.work_operation, "
                         "to_jsonb(o) || %s)).* FROM stageflow.work_operation o "
                         "WHERE operation_id = %s", (Jsonb(overrides), original.id.value))
        assert error.value.diag.constraint_name == constraint


@pytest.mark.parametrize("changes", [
    {"operation_kind": "unknown"},
    {"accepted_asset_formats": ["wav"]},
    {"supports_word_timing": True},
    {"supports_speaker_labels": True},
    {"provider_id": "test", "provider_version": "v1"},
    {"model_id": "test", "model_version": "v1"},
])
def test_0017_rejects_invalid_capability_inserts(
    render_postgres_dsn: str, changes: dict[str, object],
) -> None:
    dsn = render_postgres_dsn
    repo = PostgresWorkExecutionRepository[OperationInput](dsn, input_types=INPUT_TYPES)
    harness = Harness(repo, timing_request(), MutableClock(), dsn)
    value = worker(harness, "media_timing")
    with psycopg.connect(dsn) as conn:
        with pytest.raises(psycopg.errors.CheckViolation) as error, conn.transaction():
            conn.execute("INSERT INTO stageflow.work_worker_capability SELECT "
                         "(jsonb_populate_record(NULL::stageflow.work_worker_capability, "
                         "to_jsonb(c) || %s)).* FROM stageflow.work_worker_capability c "
                         "WHERE worker_id = %s", (Jsonb({"capability_id": str(uuid4()), **changes}),
                                                 value.id.value))
        expected = ("work_worker_capability_operation_kind_check" if "operation_kind" in changes
                    else "work_worker_capability_media_timing_fields_check")
        assert error.value.diag.constraint_name == expected


@pytest.mark.parametrize("result_type", [None, "transcript_evidence", "rendered_output"])
def test_0017_success_requires_media_timing_result_type(
    render_postgres_dsn: str, result_type: str | None,
) -> None:
    dsn = render_postgres_dsn
    event, asset, manifest = seed_asset(dsn, observed_at=NOW)
    request = replace(timing_request(), event_id=event, input=MediaTimingOperationInput(
        asset, manifest, "v1", "test-profile", "v1",
    ))
    repo = PostgresMediaTimingWorkRepository(dsn)
    operation = repo.enqueue(pending_media_timing_operation(request))
    evidence = apply_evidence(dsn, request)
    with psycopg.connect(dsn) as conn:
        with pytest.raises(psycopg.errors.CheckViolation) as error, conn.transaction():
            conn.execute("INSERT INTO stageflow.work_operation SELECT "
                         "(jsonb_populate_record(NULL::stageflow.work_operation, "
                         "to_jsonb(o) || %s)).* FROM stageflow.work_operation o "
                         "WHERE operation_id = %s", (Jsonb({
                             "operation_id": str(uuid4()), "idempotency_key": uuid4().hex,
                             "work_key": uuid4().hex + uuid4().hex,
                             "operation_status": "succeeded", "terminal_result_type": result_type,
                             "terminal_result_media_timing_evidence_id": evidence.value,
                         }), operation.id.value))
        assert error.value.diag.constraint_name == "work_operation_check4"


def test_0017_rejects_media_timing_result_for_different_asset(
    render_postgres_dsn: str,
) -> None:
    dsn = render_postgres_dsn
    event, asset, manifest = seed_asset(dsn, observed_at=NOW)
    request = replace(timing_request(), event_id=event, input=MediaTimingOperationInput(
        asset, manifest, "v1", "test-profile", "v1",
    ))
    repo = PostgresMediaTimingWorkRepository(dsn)
    operation = repo.enqueue(pending_media_timing_operation(request))
    other_event, other_asset, other_manifest = seed_asset(dsn, observed_at=NOW)
    other_request = replace(timing_request(), event_id=other_event, input=MediaTimingOperationInput(
        other_asset, other_manifest, "v1", "test-profile", "v1",
    ))
    evidence = apply_evidence(dsn, other_request)
    assert other_asset != asset
    with psycopg.connect(dsn) as conn:
        with pytest.raises(psycopg.errors.ForeignKeyViolation) as error, conn.transaction():
            conn.execute("UPDATE stageflow.work_operation SET operation_status = 'succeeded', "
                         "terminal_result_type = 'media_timing_evidence', "
                         "terminal_result_media_timing_evidence_id = %s "
                         "WHERE operation_id = %s", (evidence.value, operation.id.value))
        assert error.value.diag.constraint_name == "work_operation_media_timing_evidence_fk"
    assert repo.get_operation(operation.id) == operation


def test_timing_capability_contract_rejects_transcription_fields() -> None:
    value = WorkerCapability(
        EntityId.new(), EntityId.new(), "media_timing", "v1", "test-profile", "v1",
        ExecutionLocality.LOCAL, None, False, False, None, None, None, None,
        "test-runtime", "v1", True, NOW,
    )
    for field, invalid in (("accepted_asset_formats", ("wav",)), ("supports_word_timing", True),
                           ("supports_speaker_labels", True), ("provider_id", "test"),
                           ("provider_version", "v1"), ("model_id", "test"),
                           ("model_version", "v1")):
        with pytest.raises(ValueError, match="cannot declare transcription fields"):
            replace(value, **{field: invalid})


def test_media_timing_asset_manifest_validation(render_postgres_dsn: str) -> None:
    dsn = render_postgres_dsn
    repo = PostgresMediaTimingWorkRepository(dsn)
    request = timing_request()
    with pytest.raises(WorkExecutionNotFoundError, match="completed_media_asset_not_found"):
        repo.enqueue(pending_media_timing_operation(request))
    event, asset, _ = seed_asset(dsn, observed_at=NOW)
    request = replace(request, event_id=event, input=replace(request.input, asset_id=asset))
    with pytest.raises(WorkExecutionConflictError, match="asset_manifest_identity_conflict"):
        repo.enqueue(pending_media_timing_operation(request))


@pytest.mark.parametrize("has_capability", [False, True])
def test_timing_workers_do_not_crowd_transcription_summary(
    render_postgres_dsn: str, monkeypatch: pytest.MonkeyPatch, has_capability: bool,
) -> None:
    dsn = render_postgres_dsn
    event, _, _ = seed_asset(dsn, observed_at=NOW)
    repo = PostgresWorkExecutionRepository[OperationInput](dsn, input_types=INPUT_TYPES)
    harness = Harness(repo, replace(timing_request(), event_id=event), MutableClock(), dsn)
    # Every timing worker sorts before this worker in the bounded SQL listing.
    last_id = EntityId("ffffffff-ffff-ffff-ffff-ffffffffffff")
    if has_capability:
        worker(harness, "transcription", worker_id=last_id)
    else:
        repo.register_worker(Worker(last_id, "unconfigured-node", "test-deployment", event,
                                    True, False, "v1", 1, NOW, NOW))

    @contextmanager
    def connect(dsn: str) -> Generator[psycopg.Connection[tuple[object, ...]]]:
        with psycopg.Connection.connect(dsn) as conn:
            # The shared fixture uses dict rows; the controller consumes tuple rows.
            original_factory = conn.row_factory
            conn.row_factory = tuple_row
            try:
                yield conn
            finally:
                conn.row_factory = original_factory

    monkeypatch.setattr(controller, "psycopg",
                        SimpleNamespace(connect=connect, Error=psycopg.Error))
    before = controller.worker_summary(dsn, event.value, "test-deployment")
    assert before["registered"] == 1
    assert before["available"] == int(has_capability)
    assert before["capacity"] == int(has_capability)
    for _ in range(21):
        worker(harness, "media_timing")
    assert controller.worker_summary(dsn, event.value, "test-deployment") == before

