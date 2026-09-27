from __future__ import annotations

import hashlib
import subprocess
import sys
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock

import psycopg
import pytest
from psycopg.rows import dict_row
from test_render_work_execution import NOW, MutableClock, seed_asset
from test_render_work_execution import render_postgres_dsn as render_postgres_dsn

from app.contexts.production.media_timing_evidence import (
    ApplyMediaTimingEvidenceRequest,
    InMemoryMediaTimingEvidenceRepository,
    MediaTimingEvidence,
    MediaTimingEvidenceApplication,
    MediaTimingEvidenceStorageUnavailableError,
)
from app.contexts.production.media_timing_evidence.enqueue import (
    MediaTimingEnqueue,
    RegisteredTimingAsset,
)
from app.contexts.production.media_timing_evidence.inspection import (
    InspectionFields,
    MediaTimingError,
    inspection_result,
)
from app.contexts.production.media_timing_evidence.worker import (
    MediaTimingResultCommitAmbiguousError,
    MediaTimingWorker,
)
from app.contexts.work_execution import (
    AttemptOutcome,
    ClaimRequest,
    EventNetworkPolicy,
    MediaTimingOperationInput,
    OperationStatus,
    Worker,
    WorkerHealth,
    WorkerPressure,
    WorkExecutionLeaseLostError,
    WorkExecutionRepository,
    WorkExecutionStorageUnavailableError,
)
from app.contexts.work_execution.memory import InMemoryWorkExecutionRepository
from app.demo.media_timing_worker import timing_capability
from app.infrastructure.media_timing.ffprobe import FFprobeAdapter, FFprobeIdentity
from app.infrastructure.postgres.media_timing_evidence_repository import (
    PostgresMediaTimingEvidenceRepository,
)
from app.infrastructure.postgres.media_timing_work_repository import (
    PostgresMediaTimingWorkRepository,
)
from app.shared.ids import EntityId
from app.shared.time import FixedClock

FIELDS = InspectionFields("2026-09-25T03:00:00+03:00", "60.125", "-0.025", "60")

FAKE_FFPROBE = r'''
import json, os, sys, time
mode = os.environ.get("STAGEFLOW_FAKE_TIMING", "valid")
if "-version" in sys.argv:
    print("ffprobe version 8.0.1 synthetic")
    flag = "--enable-" + mode if mode in ("gpl", "nonfree") else "--disable-gpl"
    print("configuration: " + flag)
    raise SystemExit(0)
assert sys.argv[1:3] == ["-protocol_whitelist", "file"]
assert sys.argv[3:-1] == ["-v", "error", "-print_format", "json", "-show_format", "-show_streams"]
assert sys.stdin.read() == ""
sys.stderr.write("secret=never-persist /private/recording.mp4\n")
if mode == "timeout": time.sleep(10)
if mode == "nonzero": raise SystemExit(7)
if mode == "malformed": print("invalid"); raise SystemExit(0)
if mode == "oversized": print("x" * 1100000); raise SystemExit(0)
data = {"format": {"duration": "60.125", "tags": {"creation_time": "2026-09-25T03:00:00+03:00"},
                   "filename": "/private/recording.mp4"},
        "streams": [{"codec_type": "audio", "start_time": "9"},
                    {"codec_type": "video", "start_time": "-0.025", "duration": "60"}]}
if mode == "missing": data["format"]["tags"] = {}
if mode == "naive": data["format"]["tags"]["creation_time"] = "2026-09-25T00:00:00"
print(json.dumps(data))
'''


@pytest.fixture
def fake_ffprobe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    script = tmp_path / "fake_ffprobe.py"
    script.write_text(FAKE_FFPROBE, encoding="utf-8")
    popen = subprocess.Popen

    def launch(args: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
        assert args[0] == str(script) and Path(args[0]).is_absolute()
        assert kwargs["shell"] is False and kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["stderr"] == subprocess.DEVNULL
        # Explicit test wrapper supplies Python on Windows; production never uses a shell.
        return cast("subprocess.Popen[bytes]", popen(
            [sys.executable, str(script), *args[1:]], **kwargs,
        ))

    monkeypatch.setattr(subprocess, "Popen", launch)
    return script


@pytest.mark.parametrize("mode", ["valid", "missing", "naive", "malformed", "oversized",
                                  "timeout", "nonzero", "gpl", "nonfree"])
def test_ffprobe_bounded_execution(fake_ffprobe: Path, tmp_path: Path,
                                 monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    monkeypatch.setenv("STAGEFLOW_FAKE_TIMING", mode)
    if mode in {"gpl", "nonfree"}:
        with pytest.raises(MediaTimingError, match="media_timing_tool_refused"):
            FFprobeAdapter(fake_ffprobe, FixedClock(NOW))
        return
    adapter = FFprobeAdapter(fake_ffprobe, FixedClock(NOW), timeout=0.5 if mode == "timeout" else 5)
    assert adapter.identity.sha256 == hashlib.sha256(fake_ffprobe.read_bytes()).hexdigest()
    media = tmp_path / "synthetic 'quoted'.mp4"
    media.write_bytes(b"synthetic")
    if mode in {"malformed", "oversized", "timeout", "nonzero"}:
        code = "media_timing_timeout" if mode == "timeout" else "media_timing_output_invalid"
        with pytest.raises(MediaTimingError, match=code):
            adapter.inspect(media)
        return
    result = adapter.inspect(media)
    assert bool(result.derivations) == (mode == "valid")
    assert result.qualification.status.value == "unqualified"
    assert "/private" not in repr(result) and "secret=" not in repr(result)
    assert result.provenance.tool_id.endswith(adapter.identity.sha256)
    if mode == "naive":
        assert "creation_time_timezone_unknown" in result.limitations
    if mode == "missing":
        assert "creation_time_missing" in result.limitations


def test_profile_observations_derivation_and_application_replay() -> None:
    result = inspection_result(FIELDS, version="8.0.1", digest="a" * 64, inspected_at=NOW)
    assert len(result.observations) == 4 and len(result.derivations) == 1
    observations = {item.kind: item for item in result.observations}
    creation = observations["creation_time"]
    assert creation.original_representation == FIELDS.creation_time
    assert creation.normalized_timestamp == NOW
    assert creation.timezone_kind.value == "explicit_offset"
    assert observations["video_start"].normalized_value == "-0.025"
    interval = result.derivations[0]
    assert interval.candidate_started_at == NOW
    assert interval.candidate_ended_at == NOW + timedelta(seconds=60.125)
    assert set(interval.input_observation_ids) == {
        creation.id, observations["container_duration"].id,
    }
    assert interval.rule_id == "creation_time_plus_duration" and interval.rule_version == "1"
    assert all("unqualified" in value or "not qualified" in value for value in result.limitations)
    repository = InMemoryMediaTimingEvidenceRepository()
    asset, manifest = EntityId.new(), EntityId.new()
    repository.register_asset(asset, manifest)
    request = ApplyMediaTimingEvidenceRequest(EntityId.new(), asset, manifest, "1.0", NOW, result)
    app = MediaTimingEvidenceApplication(repository)
    applied = app.apply(request)
    assert app.apply(request) == applied == repository.get_active(asset)
    assert len(repository.history(asset)) == 1
    with pytest.raises(FrozenInstanceError):
        result.__setattr__("limitations", ())


@pytest.mark.parametrize("case,code", [
    ("missing_binary", "media_timing_tool_unavailable"),
    ("batch_binary", "media_timing_tool_refused"),
    ("changed_binary", "media_timing_tool_refused"),
    ("missing_media", "input_missing"),
])
def test_ffprobe_security_paths(fake_ffprobe: Path, tmp_path: Path,
                               case: str, code: str) -> None:
    if case in {"missing_binary", "batch_binary"}:
        path = fake_ffprobe.with_name("missing.exe")
        if case == "batch_binary":
            path = fake_ffprobe.with_suffix(".cmd")
            path.write_bytes(fake_ffprobe.read_bytes())
        with pytest.raises(MediaTimingError, match=code):
            FFprobeAdapter(path, FixedClock(NOW))
        return
    adapter = FFprobeAdapter(fake_ffprobe, FixedClock(NOW))
    media = tmp_path / "synthetic.mp4"
    if case == "changed_binary":
        media.write_bytes(b"synthetic")
        with fake_ffprobe.open("ab") as script:
            script.write(b"\n")
    with pytest.raises(MediaTimingError, match=code):
        adapter.inspect(media)


@pytest.mark.parametrize("error_type", [MediaTimingEvidenceStorageUnavailableError,
                                      WorkExecutionStorageUnavailableError,
                                      MediaTimingResultCommitAmbiguousError])
def test_worker_apply_storage_failure_retry_or_reconciliation(
    error_type: type[RuntimeError],
) -> None:
    memory = InMemoryWorkExecutionRepository(
        MutableClock(), input_types=(MediaTimingOperationInput,))
    repo = cast(WorkExecutionRepository[MediaTimingOperationInput], memory)
    event = EntityId.new()
    operation = MediaTimingEnqueue(repo, "test-deployment", FixedClock(NOW)).enqueue(
        event, RegisteredTimingAsset(EntityId.new(), EntityId.new(), NOW))
    results, inspector = Mock(), Mock()
    inspector.inspect.return_value = inspection_result(
        FIELDS, version="8.0.1", digest="a" * 64, inspected_at=NOW)
    results.apply_result.side_effect = error_type("secret=/private")
    service = MediaTimingWorker(repo, results, Mock(), inspector, FixedClock(NOW))
    request = setup_worker(repo, event)
    if error_type is MediaTimingResultCommitAmbiguousError:
        with pytest.raises(MediaTimingResultCommitAmbiguousError):
            service.run_once(request)
        pending = repo.get_operation(operation.id)
        assert pending.status is OperationStatus.RUNNING
        assert pending.current_attempt_id is not None and pending.lease_expires_at is not None
        assert repo.list_attempts(operation.id)[0].finalized_at is None
    else:
        outcome = service.run_once(request)
        assert outcome is not None and outcome.status is OperationStatus.RETRY_WAIT
        assert outcome.current_attempt_id is None and outcome.lease_owner_worker_id is None
        assert outcome.lease_expires_at is None
        attempt = repo.list_attempts(operation.id)[0]
        assert attempt.retryable is True and attempt.outcome is AttemptOutcome.RETRYABLE_FAILURE
        assert attempt.reason_code == attempt.diagnostic_summary == (
            "media_timing_storage_unavailable")
        assert "/private" not in repr(attempt)
    results.apply_result.assert_called_once()


@pytest.mark.parametrize("phase", ["statement", "commit", "commit_rejected",
                                 "commit_deadlock", "commit_admin_shutdown"])
def test_timing_repository_distinguishes_definite_and_ambiguous_storage_failure(
    monkeypatch: pytest.MonkeyPatch, phase: str,
) -> None:
    memory = InMemoryWorkExecutionRepository(
        MutableClock(), input_types=(MediaTimingOperationInput,))
    repo = cast(WorkExecutionRepository[MediaTimingOperationInput], memory)
    event, asset, manifest = EntityId.new(), EntityId.new(), EntityId.new()
    operation = MediaTimingEnqueue(repo, "test-deployment", FixedClock(NOW)).enqueue(
        event, RegisteredTimingAsset(asset, manifest, NOW))
    claim = repo.claim_next(setup_worker(repo, event))
    assert claim is not None
    request = ApplyMediaTimingEvidenceRequest(operation.id, asset, manifest, "1.0", NOW,
        inspection_result(FIELDS, version="8.0.1", digest="a" * 64, inspected_at=NOW))
    postgres = PostgresMediaTimingWorkRepository("synthetic-unused")
    connection = Mock()
    if phase == "statement":
        connection.execute.side_effect = psycopg.OperationalError("synthetic")
    monkeypatch.setattr(postgres, "_assert_active_claim", Mock())
    monkeypatch.setattr(MediaTimingEvidenceApplication, "apply", Mock())

    @contextmanager
    def connect() -> Generator[Any]:
        yield connection
        error = {"commit_rejected": psycopg.errors.SerializationFailure,
                 "commit_deadlock": psycopg.errors.DeadlockDetected,
                 "commit_admin_shutdown": psycopg.errors.AdminShutdown}.get(
                     phase, psycopg.OperationalError)
        raise error("synthetic")

    monkeypatch.setattr(postgres, "_connect", connect)
    with pytest.raises(WorkExecutionStorageUnavailableError) as failure:
        postgres.apply_result(claim, request)
    assert isinstance(failure.value, MediaTimingResultCommitAmbiguousError) == (
        phase in {"commit", "commit_admin_shutdown"})


@pytest.mark.parametrize("creation,duration,reason", [
    (None, "60", "creation_time_missing"),
    ("2026-09-25T00:00:00", "60", "creation_time_timezone_unknown"),
    ("2026-99-99T00:00:00Z", "60", "creation_time_invalid"),
    (" ", "60", "creation_time_invalid"),
    ("secret=/private/recording.mp4", "60", "creation_time_invalid"),
    (FIELDS.creation_time, "NaN", "container_duration_invalid"),
    (FIELDS.creation_time, "-1", "container_duration_invalid"),
    (FIELDS.creation_time, None, "container_duration_missing"),
])
def test_missing_or_invalid_fields_remain_advisory(creation: str | None,
                                                duration: str | None, reason: str) -> None:
    result = inspection_result(InspectionFields(creation, duration, None, None),
                               version="8.0.1", digest="a" * 64, inspected_at=NOW)
    assert not result.derivations and reason in result.limitations
    assert "/private" not in repr(result)


def setup_worker(repo: WorkExecutionRepository[MediaTimingOperationInput],
                 event: EntityId) -> ClaimRequest:
    worker = repo.register_worker(Worker(EntityId.new(), "timing-node", "test-deployment",
        event, True, False, "v1", 1, NOW, NOW))
    repo.register_capability(timing_capability(worker.id, FFprobeIdentity("8.0.1", "a" * 64), NOW))
    repo.record_presence(worker.id, ttl=timedelta(minutes=5), maximum_concurrency=2,
                         health=WorkerHealth.AVAILABLE, pressure=WorkerPressure.NORMAL)
    return ClaimRequest(worker.id, EventNetworkPolicy.LOCAL_ONLY,
                        timedelta(minutes=5), "media_timing")


@pytest.mark.parametrize("code", ["media_timing_tool_unavailable", "media_timing_tool_refused",
    "media_timing_output_invalid", "media_timing_timeout", "input_missing", "unexpected"])
@pytest.mark.parametrize("storage", ["memory", "postgres"])
def test_worker_failure_releases_lease_and_sanitizes(
    code: str, storage: str, request: pytest.FixtureRequest,
) -> None:
    if storage == "memory":
        memory = InMemoryWorkExecutionRepository(
            MutableClock(), input_types=(MediaTimingOperationInput,),
        )
        repo = cast(WorkExecutionRepository[MediaTimingOperationInput], memory)
        event, asset, manifest = EntityId.new(), EntityId.new(), EntityId.new()
    else:
        dsn: str = request.getfixturevalue("render_postgres_dsn")
        repo = PostgresMediaTimingWorkRepository(dsn)
        event, asset, manifest = seed_asset(dsn, observed_at=NOW)
    operation = MediaTimingEnqueue(repo, "test-deployment", FixedClock(NOW)).enqueue(event,
        RegisteredTimingAsset(asset, manifest, NOW))
    claim_request = setup_worker(repo, event)
    inspector = Mock()
    inspector.inspect.side_effect = (RuntimeError("secret=/private") if code == "unexpected"
                                    else MediaTimingError(code, retryable=True))
    service = MediaTimingWorker(repo, Mock(), Mock(), inspector, FixedClock(NOW))
    outcome = service.run_once(claim_request)
    assert outcome is not None and outcome.id == operation.id
    assert outcome.current_attempt_id is None and outcome.lease_owner_worker_id is None
    assert outcome.lease_expires_at is None
    expected = "media_timing_internal" if code == "unexpected" else code
    assert outcome.last_reason_code == expected
    attempt = repo.list_attempts(operation.id)[0]
    assert attempt.diagnostic_summary == expected and "/private" not in repr(attempt)


def test_enqueue_work_key_idempotency_human_bounds_and_cpu_capability() -> None:
    memory = InMemoryWorkExecutionRepository(MutableClock())
    repo = cast(WorkExecutionRepository[MediaTimingOperationInput], memory)
    clock = MutableClock(NOW + timedelta(days=20))
    service = MediaTimingEnqueue(repo, "test-deployment", clock)
    asset = RegisteredTimingAsset(EntityId.new(), EntityId.new(), NOW)
    event = EntityId.new()
    first = service.enqueue(event, asset)
    assert first.eligible_at == clock.now() and first.eligible_at != asset.registered_at
    clock.at += timedelta(days=1)
    assert service.enqueue(event, asset) == first
    reader = Mock()
    reader.asset_page.return_value = ((asset,), asset.asset_id)
    items, cursor = service.enqueue_existing(reader, event, actor_id=EntityId.new(),
        authority_kind="human", confirmed=True, limit=1)
    assert items == (first,) and cursor == asset.asset_id
    for authority, confirmed, limit in [("automatic", True, 1), ("human", False, 1),
                                         ("human", True, 0), ("human", True, 101)]:
        with pytest.raises(ValueError):
            service.enqueue_existing(reader, event, actor_id=EntityId.new(),
                authority_kind=authority, confirmed=confirmed, limit=limit)
    capability = timing_capability(EntityId.new(), FFprobeIdentity("8.0.1", "a" * 64), NOW)
    assert capability.operation_kind == "media_timing" and capability.locality.value == "local"
    assert capability.model_id is None and capability.runtime_id.startswith("ffprobe-cpu:")


@pytest.mark.parametrize("reconcile", [False, True])
def test_postgres_fenced_commit_roundtrip_and_expired_result_reconciliation(
    render_postgres_dsn: str, reconcile: bool,
) -> None:
    dsn = render_postgres_dsn
    event, asset, manifest = seed_asset(dsn, observed_at=NOW)
    repo = PostgresMediaTimingWorkRepository(dsn)
    operation = MediaTimingEnqueue(repo, "test-deployment", FixedClock(NOW)).enqueue(event,
        RegisteredTimingAsset(asset, manifest, NOW))
    claim = repo.claim_next(setup_worker(repo, event))
    assert claim is not None
    claim = repo.mark_running(claim)
    result = inspection_result(FIELDS, version="8.0.1", digest="a" * 64, inspected_at=NOW)
    request = ApplyMediaTimingEvidenceRequest(operation.id, asset, manifest, "1.0", NOW, result)
    evidence_repo = PostgresMediaTimingEvidenceRepository(dsn)
    if reconcile:
        applied = MediaTimingEvidenceApplication(evidence_repo).apply(request)
        with psycopg.connect(dsn) as conn:
            conn.execute("UPDATE stageflow.work_operation SET lease_expires_at="
                         "statement_timestamp()-interval '1 second' WHERE operation_id=%s",
                         (operation.id.value,))
        recovered = repo.reconcile_expired()
        assert len(recovered) == 1 and recovered[0].id == operation.id
        assert repo.list_attempts(operation.id)[0].outcome is AttemptOutcome.RESULT_RECONCILED
    else:
        with pytest.raises(WorkExecutionLeaseLostError):
            repo.apply_result(replace(claim, attempt=replace(claim.attempt,
                fence_generation=claim.attempt.fence_generation + 1)), request)
        assert evidence_repo.get_active(asset) is None
        applied = repo.apply_result(claim, request)
    assert evidence_repo.get_active(asset) == applied
    assert MediaTimingEvidenceApplication(evidence_repo).apply(request) == applied
    terminal = repo.get_operation(operation.id)
    assert terminal.status is OperationStatus.SUCCEEDED
    assert terminal.terminal_result_media_timing_evidence_id == applied.id
    assert terminal.current_attempt_id is None and len(evidence_repo.history(asset)) == 1
    assert repo.page(event, limit=1)[0] == (terminal,)
    assert repo.asset_page(event, limit=1)[0][0].asset_id == asset
    replay = MediaTimingEnqueue(repo, "test-deployment", FixedClock(NOW + timedelta(days=1)))
    assert replay.enqueue(event, RegisteredTimingAsset(asset, manifest, NOW)) == terminal


def test_postgres_worker_success_and_application_rollback(
    render_postgres_dsn: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    dsn = render_postgres_dsn
    event, asset, manifest = seed_asset(dsn, observed_at=NOW)
    repo = PostgresMediaTimingWorkRepository(dsn)
    operation = MediaTimingEnqueue(repo, "test-deployment", FixedClock(NOW)).enqueue(event,
        RegisteredTimingAsset(asset, manifest, NOW))
    request = setup_worker(repo, event)
    result = inspection_result(FIELDS, version="8.0.1", digest="a" * 64, inspected_at=NOW)
    inspector, resolver = Mock(), Mock()
    inspector.inspect.return_value = result
    service = MediaTimingWorker(repo, repo, resolver, inspector, FixedClock(NOW))
    apply = MediaTimingEvidenceApplication.apply

    def fail_after_append(self: MediaTimingEvidenceApplication,
                          request: ApplyMediaTimingEvidenceRequest) -> MediaTimingEvidence:
        apply(self, request)
        raise RuntimeError("synthetic failure after evidence append")

    with monkeypatch.context() as patch:
        patch.setattr(MediaTimingEvidenceApplication, "apply", fail_after_append)
        failed = service.run_once(request)
    evidence = PostgresMediaTimingEvidenceRepository(dsn)
    assert failed is not None and failed.status is OperationStatus.TERMINAL_FAILED
    assert evidence.get_active(asset) is None
    # A distinct asset drives a successful full worker cycle without resetting journal state.
    event2, asset2, manifest2 = seed_asset(dsn, observed_at=NOW)
    MediaTimingEnqueue(repo, "test-deployment", FixedClock(NOW)).enqueue(event2,
        RegisteredTimingAsset(asset2, manifest2, NOW))
    succeeded = service.run_once(setup_worker(repo, event2))
    assert succeeded is not None and succeeded.status is OperationStatus.SUCCEEDED
    stored = evidence.get_active(asset2)
    assert stored is not None and stored.result == result
    assert succeeded.terminal_result_media_timing_evidence_id == stored.id
    resolver.resolve.assert_called_with(succeeded.input)
    inspector.inspect.assert_called_with(resolver.resolve.return_value)
    with psycopg.Connection[dict[str, Any]].connect(dsn, row_factory=dict_row) as conn:
        row = conn.execute("SELECT media_started_at,media_ended_at "
                           "FROM stageflow.completed_media_asset_registry WHERE asset_id=%s",
                           (asset2.value,)).fetchone()
        assert row is not None
        assert row["media_started_at"] is None and row["media_ended_at"] is None
    assert repo.get_operation(operation.id).terminal_result_media_timing_evidence_id is None


@pytest.mark.parametrize("error_type", [MediaTimingEvidenceStorageUnavailableError,
                                      WorkExecutionStorageUnavailableError])
def test_postgres_apply_storage_outage_rolls_back_and_schedules_retry(
    render_postgres_dsn: str, monkeypatch: pytest.MonkeyPatch, error_type: type[RuntimeError],
) -> None:
    event, asset, manifest = seed_asset(render_postgres_dsn, observed_at=NOW)
    repo = PostgresMediaTimingWorkRepository(render_postgres_dsn)
    operation = MediaTimingEnqueue(repo, "test-deployment", FixedClock(NOW)).enqueue(
        event, RegisteredTimingAsset(asset, manifest, NOW))
    inspector = Mock()
    inspector.inspect.return_value = inspection_result(
        FIELDS, version="8.0.1", digest="a" * 64, inspected_at=NOW)
    apply = MediaTimingEvidenceApplication.apply

    def fail_after_append(self: MediaTimingEvidenceApplication,
                          request: ApplyMediaTimingEvidenceRequest) -> MediaTimingEvidence:
        apply(self, request)
        raise error_type("secret=/private")

    monkeypatch.setattr(MediaTimingEvidenceApplication, "apply", fail_after_append)
    outcome = MediaTimingWorker(repo, repo, Mock(), inspector, FixedClock(NOW)).run_once(
        setup_worker(repo, event))
    assert outcome is not None and outcome.status is OperationStatus.RETRY_WAIT
    assert outcome.terminal_result_media_timing_evidence_id is None
    assert outcome.current_attempt_id is None and outcome.lease_expires_at is None
    assert PostgresMediaTimingEvidenceRepository(render_postgres_dsn).get_active(asset) is None
    attempt = repo.list_attempts(operation.id)[0]
    assert attempt.retryable is True
    assert attempt.reason_code == attempt.diagnostic_summary == (
        "media_timing_storage_unavailable")
