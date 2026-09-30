from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_render_work_execution import (
    NOW,
    Harness,
    MutableClock,
    claim_request,
    general_repository,
    render_request,
    seed_asset,
    transcription_request_for,
    worker,
)
from test_render_work_execution import harness as harness
from test_render_work_execution import render_postgres_dsn as render_postgres_dsn
from test_rendering_phase_b import MemoryRendering
from test_rendering_phase_b import approved_revision as approved_revision
from test_transcription_worker_substrate import transcript_result

from app.api.v1 import rendering as rendering_api
from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.assembly.session_contracts import AssemblyRevision
from app.contexts.production.media_timing_evidence.enqueue import (
    MediaTimingEnqueue,
    RegisteredTimingAsset,
)
from app.contexts.transcription_evidence import (
    TranscriptEvidenceStatus,
    TranscriptionExecutionError,
)
from app.contexts.work_execution import (
    AttemptStatus,
    MediaTimingOperationInput,
    OperationStatus,
    TranscriptionOperationApplication,
    TranscriptionWorker,
    WorkerCycleOutcome,
    WorkExecutionConflictError,
    WorkExecutionLeaseLostError,
    WorkExecutionRepository,
    WorkExecutionStorageUnavailableError,
)
from app.contexts.work_execution import service as worker_service
from app.contexts.work_execution.memory import InMemoryWorkExecutionRepository
from app.demo import service as demo_service
from app.demo.service import DemoApplication, ReconcileMediaRequest
from app.infrastructure.postgres import PostgresWorkExecutionRepository
from app.infrastructure.postgres.media_timing_work_repository import (
    PostgresMediaTimingWorkRepository,
)
from app.infrastructure.postgres.render_repository import PostgresRenderRepository
from app.shared.ids import EntityId
from app.shared.time import FixedClock
from tests.test_packaging_asset_foundation import HEADERS, SyncHttpClient


@pytest.mark.parametrize("phase", ["execute", "prepare", "apply"])
def test_transcription_internal_failure_is_fenced_released_and_bounded(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, phase: str,
) -> None:
    repository = harness.repository
    operation = TranscriptionOperationApplication(repository).enqueue(
        transcription_request_for(harness))
    request = claim_request(worker(harness, "transcription"))
    port = Mock()
    port.execute.return_value = transcript_result()
    failure = RuntimeError("secret=/private/unexpected")
    if phase == "execute":
        port.execute.side_effect = failure
    elif phase == "prepare":
        monkeypatch.setattr(worker_service, "prepare_transcript_evidence",
                            Mock(side_effect=failure))
    else:
        monkeypatch.setattr(repository, "apply_transcript_result", Mock(side_effect=failure))
    runner = TranscriptionWorker(repository, port)
    for number in range(1, operation.max_attempts + 1):
        result = runner.run_once(request)
        stored = repository.get_operation(operation.id)
        assert stored.attempt_count == number
        assert stored.current_attempt_id is stored.lease_owner_worker_id is None
        assert stored.lease_expires_at is None
        assert stored.terminal_result_id is None
        attempt = repository.list_attempts(operation.id)[-1]
        assert attempt.status is AttemptStatus.FINALIZED
        assert attempt.reason_code == attempt.diagnostic_summary == "transcription_internal_error"
        assert attempt.retryable is True
        assert attempt.fence_generation == stored.fence_generation
        if number < operation.max_attempts:
            assert result.outcome is WorkerCycleOutcome.RETRY_SCHEDULED
            assert stored.status is OperationStatus.RETRY_WAIT
            assert runner.run_once(request).outcome is WorkerCycleOutcome.IDLE
            harness.elapse(operation.id)
        else:
            assert result.outcome is WorkerCycleOutcome.TERMINAL_FAILED
            assert stored.status is OperationStatus.TERMINAL_FAILED
    assert runner.run_once(request).outcome is WorkerCycleOutcome.IDLE


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("failure_type", [WorkExecutionLeaseLostError,
                                         WorkExecutionStorageUnavailableError])
def test_transcription_failure_recording_errors_propagate_once(
    monkeypatch: pytest.MonkeyPatch, typed: bool, failure_type: type[RuntimeError],
) -> None:
    clock = MutableClock()
    repo = InMemoryWorkExecutionRepository(clock)
    fixture = Harness(repo, render_request(), clock, None)
    operation = TranscriptionOperationApplication(repo).enqueue(transcription_request_for(fixture))
    request = claim_request(worker(fixture, "transcription"))
    port = Mock()
    port.execute.side_effect = (TranscriptionExecutionError("provider_unavailable",
        retryable=True, diagnostic_summary="bounded") if typed else RuntimeError("private"))
    record = Mock(side_effect=failure_type("synthetic_failure"))
    monkeypatch.setattr(repo, "record_failure", record)
    with pytest.raises(failure_type, match="synthetic_failure"):
        TranscriptionWorker(repo, port).run_once(request)
    record.assert_called_once()
    assert repo.get_operation(operation.id).status is OperationStatus.RUNNING


def test_transcription_wrong_kind_still_raises_without_recording_failure(
    harness: Harness, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.contexts.work_execution.application import pending_render_operation

    operation = harness.repository.enqueue(pending_render_operation(harness.request))
    request = claim_request(worker(harness, "render"))
    claim = harness.repository.claim_next(request)
    assert claim is not None
    monkeypatch.setattr(harness.repository, "claim_next", Mock(return_value=claim))
    record_failure = Mock(wraps=harness.repository.record_failure)
    monkeypatch.setattr(harness.repository, "record_failure", record_failure)
    port = Mock()
    with pytest.raises(WorkExecutionConflictError,
                       match="transcription_worker_requires_transcription"):
        TranscriptionWorker(harness.repository, port).run_once(request)
    port.execute.assert_not_called()
    stored = harness.repository.get_operation(operation.id)
    assert stored.status is OperationStatus.RUNNING
    assert stored.current_attempt_id == claim.attempt.id
    assert stored.lease_owner_worker_id == claim.operation.lease_owner_worker_id
    assert stored.lease_expires_at == claim.operation.lease_expires_at
    assert stored.last_reason_code is None
    assert harness.repository.list_attempts(operation.id)[0].status is AttemptStatus.RUNNING
    record_failure.assert_not_called()


def test_transcription_expired_renewal_never_finalizes_a_stale_attempt() -> None:
    clock = MutableClock()
    repo = InMemoryWorkExecutionRepository(clock)
    fixture = Harness(repo, render_request(), clock, None)
    operation = TranscriptionOperationApplication(repo).enqueue(transcription_request_for(fixture))
    request = claim_request(worker(fixture, "transcription"))
    port = Mock()

    def expire(execution_request: object, renew: object) -> None:
        clock.at += timedelta(minutes=1)
        assert callable(renew)
        renew()

    port.execute.side_effect = expire
    with pytest.raises(WorkExecutionLeaseLostError):
        TranscriptionWorker(repo, port).run_once(request)
    assert repo.list_attempts(operation.id)[0].status is AttemptStatus.RUNNING
    assert repo.reconcile_expired()[0].status is OperationStatus.RETRY_WAIT
    assert repo.list_attempts(operation.id)[0].reason_code == "lease_expired"


@pytest.mark.parametrize("outcome", ["complete", "partial", "failed", "retry", "terminal"])
def test_transcription_handled_outcomes_retain_results_and_diagnostics(outcome: str) -> None:
    clock = MutableClock()
    repo = InMemoryWorkExecutionRepository(clock)
    fixture = Harness(repo, render_request(), clock, None)
    operation = TranscriptionOperationApplication(repo).enqueue(transcription_request_for(fixture))
    request = claim_request(worker(fixture, "transcription"))
    port = Mock()
    result = transcript_result()
    if outcome in {"retry", "terminal"}:
        port.execute.side_effect = TranscriptionExecutionError(
            "provider_unavailable", retryable=outcome == "retry", diagnostic_summary="bounded")
    else:
        if outcome == "partial":
            result = replace(result, status=TranscriptEvidenceStatus.PARTIAL,
                             partial_reason="partial_provider_result")
        elif outcome == "failed":
            result = replace(result, status=TranscriptEvidenceStatus.FAILED,
                             segments=(), failure_reason="provider_failed")
        port.execute.return_value = result
    actual = TranscriptionWorker(repo, port).run_once(request)
    stored = repo.get_operation(operation.id)
    attempt = repo.list_attempts(operation.id)[0]
    assert stored.current_attempt_id is stored.lease_owner_worker_id is None
    assert stored.lease_expires_at is None
    if outcome in {"complete", "partial"}:
        assert actual.outcome is WorkerCycleOutcome.SUCCEEDED
        assert actual.evidence_id is not None
        assert repo.get_transcript_evidence(actual.evidence_id).result == result
    else:
        assert actual.evidence_id is None and stored.terminal_result_id is None
        assert actual.outcome is (WorkerCycleOutcome.RETRY_SCHEDULED if outcome == "retry"
                                  else WorkerCycleOutcome.TERMINAL_FAILED)
        assert attempt.retryable is (outcome == "retry")
        assert attempt.reason_code == ("provider_failed" if outcome == "failed"
                                       else "provider_unavailable")
        assert attempt.diagnostic_summary == ("normalized provider failure" if outcome == "failed"
                                              else "bounded")


def test_render_api_timestamps_preserve_aware_operation_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory = MemoryRendering()
    monkeypatch.setattr(rendering_api, "_service", Mock(return_value=memory.service()))
    app = FastAPI()
    app.include_router(rendering_api.router)
    client = cast(SyncHttpClient, TestClient(app))

    response = client.post("/rendering/requests", headers=HEADERS, json={
        "assembly_revision_id": memory.source.revision.id.value,
        "actor_id": EntityId.new().value, "command_id": EntityId.new().value,
        "confirmed": "confirmed",
    })
    assert response.status_code == 200
    body = response.json()
    operation = memory.work.get_operation(EntityId(body["operation_id"]))
    for field in ("created_at", "updated_at"):
        value = datetime.fromisoformat(body[field])
        assert value.utcoffset() is not None
        assert value == getattr(operation, field)
    operation = replace(operation, updated_at=operation.created_at + timedelta(minutes=1))
    repo = PostgresRenderRepository("unused")
    listing = Mock(return_value=((operation,), None))
    monkeypatch.setattr(repo, "list_render_operations", listing)
    monkeypatch.setattr(rendering_api, "_service",
                        Mock(return_value=SimpleNamespace(repository=repo)))
    event, session = EntityId.new(), EntityId.new()
    page = client.get(f"/rendering/operations?event_id={event.value}&session_id={session.value}",
                      headers=HEADERS)
    assert page.status_code == 200
    listed = page.json()["items"][0]
    assert listed["created_at"] == operation.created_at.isoformat()
    assert listed["updated_at"] == operation.updated_at.isoformat()
    listing.assert_called_once_with(event, session, limit=50, after=None, newest_first=True)


def test_render_chronological_pages_ties_and_legacy_order(
    render_postgres_dsn: str, approved_revision: AssemblyRevision,
) -> None:
    from app.contexts.work_execution.application import pending_render_operation

    repo = PostgresRenderRepository(render_postgres_dsn)
    created: list[tuple[datetime, str]] = []
    for ordinal in range(4):
        request = replace(render_request(), event_id=approved_revision.event_id,
            input=replace(render_request().input, assembly_revision_id=approved_revision.id,
                          execution_profile_version=str(ordinal)))
        operation = general_repository(render_postgres_dsn).enqueue(
            pending_render_operation(request))
        at = NOW + timedelta(minutes=ordinal // 2)
        with psycopg.connect(render_postgres_dsn) as conn:
            conn.execute("UPDATE stageflow.work_operation SET created_at=%s, updated_at=%s "
                         "WHERE operation_id=%s", (at, at, operation.id.value))
        created.append((at, operation.id.value))
    event, session = approved_revision.event_id, approved_revision.session_id
    expected = [identity for _, identity in sorted(created, reverse=True)]
    ids: list[str] = []
    cursor = None
    for _ in range(4):
        page, cursor = repo.list_render_operations(event, session, limit=1, after=cursor,
                                                  newest_first=True)
        assert len(page) == 1
        ids.append(page[0].id.value)
    assert cursor is None and ids == expected
    legacy, _ = repo.list_render_operations(event, session)
    assert [item.id.value for item in legacy] == sorted(expected)
    assert repo.list_render_operations(EntityId.new(), session, newest_first=True)[0] == ()


@pytest.mark.parametrize("enabled", [None, False, True])
def test_demo_recovery_timing_covers_all_assets_in_bounded_idempotent_cycles(
    monkeypatch: pytest.MonkeyPatch, enabled: bool | None,
) -> None:
    event = EntityId.new()
    assets = tuple(RegisteredTimingAsset(EntityId.new(), EntityId.new(), NOW) for _ in range(205))
    memory = InMemoryWorkExecutionRepository(
        MutableClock(), input_types=(MediaTimingOperationInput,))
    timing = Mock(wraps=memory)

    def missing(event_id: EntityId, *, limit: int) -> tuple[RegisteredTimingAsset, ...]:
        assert event_id == event and limit == 100
        existing = {op.input.asset_id for op in memory.operations.values()
                    if isinstance(op.input, MediaTimingOperationInput)}
        return tuple(asset for asset in assets if asset.asset_id not in existing)[:limit]

    timing.assets_without_operation = Mock(side_effect=missing)
    factory = Mock(return_value=timing)
    monkeypatch.setattr(demo_service, "PostgresMediaTimingWorkRepository", factory)
    components = Mock(spec=KernelComponents)
    components.event_key = "synthetic"
    components.transcription_scan_after = None
    components.kernel = SimpleNamespace(clock=FixedClock(NOW))
    components.configuration = SimpleNamespace(postgres_dsn="unused", deployment=SimpleNamespace(
        local_media_timing=None if enabled is None else SimpleNamespace(enabled=enabled),
        local_transcription=SimpleNamespace(execution_profile_id="synthetic",
                                            execution_profile_version="1"),
        deployment_id="synthetic"))
    components.repository.get_event_by_key.return_value = SimpleNamespace(id=event)
    # No registrations in this cycle: all assets came from startup/recovery.
    components.run_media_cycle.return_value = SimpleNamespace(
        candidates_seen=0, assets_registered=0)
    work = Mock()
    work.list_transcription_targets.return_value = ()
    for expected in (100, 200, 205, 205):
        app = DemoApplication(components, cast(TranscriptionOperationApplication, Mock()),
                              cast(PostgresWorkExecutionRepository, work))
        result = app.reconcile_media(ReconcileMediaRequest("recovery", NOW))
        assert result.enqueue_failures == ()
        assert len(memory.operations) == (expected if enabled else 0)
    if enabled:
        operation = next(iter(memory.operations.values()))
        enqueue = MediaTimingEnqueue(
            cast(WorkExecutionRepository[MediaTimingOperationInput], memory),
                                    "synthetic", FixedClock(NOW + timedelta(days=1)))
        assert enqueue.enqueue(event, assets[0]).id == operation.id
        assert len(memory.operations) == 205
    else:
        factory.assert_not_called()


def test_postgres_timing_missing_selection_is_event_scoped_and_excludes_any_outcome(
    render_postgres_dsn: str,
) -> None:
    event, asset, manifest = seed_asset(render_postgres_dsn, observed_at=NOW)
    other_event, other_asset, _ = seed_asset(render_postgres_dsn, observed_at=NOW)
    repo = PostgresMediaTimingWorkRepository(render_postgres_dsn)
    assert [item.asset_id for item in repo.assets_without_operation(event)] == [asset]
    assert [item.asset_id for item in repo.assets_without_operation(other_event)] == [other_asset]
    operation = MediaTimingEnqueue(repo, "test-deployment", FixedClock(NOW)).enqueue(
        event, RegisteredTimingAsset(asset, manifest, NOW))
    assert repo.assets_without_operation(event) == ()
    with psycopg.connect(render_postgres_dsn) as conn:
        conn.execute("UPDATE stageflow.work_operation SET operation_status='terminal_failed' "
                     "WHERE operation_id=%s", (operation.id.value,))
    assert repo.assets_without_operation(event) == ()
    for limit in (0, 101):
        with pytest.raises(ValueError, match="limit_out_of_bounds"):
            repo.assets_without_operation(event, limit=limit)


def test_timing_selection_failure_preserves_transcription_reconciliation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    components = Mock(spec=KernelComponents)
    components.event_key = "synthetic"
    components.transcription_scan_after = None
    components.kernel = SimpleNamespace(clock=FixedClock(NOW))
    components.configuration = SimpleNamespace(postgres_dsn="unused", deployment=SimpleNamespace(
        local_media_timing=SimpleNamespace(enabled=True), deployment_id="synthetic",
        local_transcription=SimpleNamespace(execution_profile_id="synthetic",
                                            execution_profile_version="1")))
    components.repository.get_event_by_key.return_value = SimpleNamespace(id=EntityId.new())
    asset = SimpleNamespace(id=EntityId.new(), manifest_id=EntityId.new(), registered_at=NOW,
                            candidate_id=EntityId.new())
    components.repository.get_asset.return_value = asset
    components.repository.get_candidate.return_value = SimpleNamespace(source_reference="test.mp4")
    components.run_media_cycle.return_value = SimpleNamespace(
        candidates_seen=0, assets_registered=0)
    repository, work, timing = Mock(), Mock(), Mock()
    repository.list_transcription_targets.return_value = ((asset.id, None),)
    timing.assets_without_operation.side_effect = WorkExecutionStorageUnavailableError("synthetic")
    monkeypatch.setattr(demo_service, "PostgresMediaTimingWorkRepository",
                        Mock(return_value=timing))
    app = DemoApplication(components, cast(TranscriptionOperationApplication, work),
                          cast(PostgresWorkExecutionRepository, repository))
    result = app.reconcile_media(ReconcileMediaRequest("recovery", NOW))
    timing.enqueue.assert_not_called()
    work.enqueue.assert_called_once()
    assert work.enqueue.call_args.args[0].input.asset_id == asset.id
    assert result.enqueue_failures == ("media_timing_enqueue_failed",)
    assert result.operations == (work.enqueue.return_value,) and result.operations_enqueued == 1
