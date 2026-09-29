from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock

import psycopg
import pytest
from test_render_work_execution import NOW, MutableClock, schema_contract, seed_asset
from test_render_work_execution import render_postgres_dsn as render_postgres_dsn

from app.contexts.production.media_segmentation_evidence.contracts import (
    CURRENT_SEGMENTATION_PROFILE,
    MediaSegmentationError,
    MediaSegmentationEvidence,
    SegmentationInterval,
    SegmentationResult,
)
from app.contexts.production.media_segmentation_evidence.enqueue import (
    MediaSegmentationEnqueue,
    RegisteredSegmentationAsset,
)
from app.contexts.production.media_segmentation_evidence.repository import (
    InMemoryMediaSegmentationRepository,
)
from app.contexts.production.media_segmentation_evidence.worker import (
    MediaSegmentationWorker,
    SegmentationResultCommitAmbiguousError,
)
from app.contexts.rendering.contracts import FFmpegIdentity
from app.contexts.work_execution import (
    ClaimRequest,
    EventNetworkPolicy,
    MediaSegmentationOperationInput,
    OperationFailure,
    OperationStatus,
    Worker,
    WorkerHealth,
    WorkerPressure,
    WorkExecutionConflictError,
    WorkExecutionLeaseLostError,
    WorkExecutionRepository,
)
from app.contexts.work_execution.application import (
    media_segmentation_work_key,
    pending_media_segmentation_operation,
)
from app.demo.media_segmentation_worker import segmentation_capability
from app.infrastructure.media_segmentation.ffmpeg import FFmpegSegmentationAdapter, parse_intervals
from app.infrastructure.postgres import PostgresMigrationRunner
from app.infrastructure.postgres.media_segmentation_repository import (
    PostgresMediaSegmentationRepository,
)
from app.shared.ids import EntityId


def log(kind: str, edge: str, value: str) -> str:
    detector = "freezedetect" if kind == "freeze" else "silencedetect"
    return f"[{detector} @ 000abc] {kind}_{edge}: {value}\n"


def result() -> SegmentationResult:
    return SegmentationResult((SegmentationInterval("freeze", 0, 5_000_000),),
                              10_000_000, "8.1.2", "a" * 64, NOW)


def test_profile_parser_open_empty_overlap_order_and_microseconds() -> None:
    profile = CURRENT_SEGMENTATION_PROFILE
    assert profile.video_filter == "fps=5,scale=320:-2,freezedetect=n=0.003:d=4"
    assert profile.audio_filter == "silencedetect=n=-40dB:d=3" and profile.decode == "cpu"
    raw = (log("freeze", "start", "0.2") + log("silence", "start", "1.000001")
           + log("freeze", "end", "4.5"))
    assert parse_intervals(raw, 10_000_000) == (
        SegmentationInterval("freeze", 200_000, 4_500_000),
        SegmentationInterval("silence", 1_000_001, 10_000_000))
    assert parse_intervals("unrelated private diagnostic", 10_000_000) == ()
    tiny = parse_intervals(log("silence", "start", "2.26757e-05"), 10_000_000)
    assert tiny[0].start_microseconds == 22
    assert parse_intervals(log("silence", "start", "-0.001"), 10_000_000)[0].start_microseconds == 0
    opened = parse_intervals(log("freeze", "start", "1"), 10_000_000)
    assert opened[0].end_microseconds == 10_000_000


@pytest.mark.parametrize("interleaved", [False, True])
def test_parser_real_ffmpeg_81_lines(interleaved: bool) -> None:
    freeze_start = (
        "[Parsed_freezedetect_2 @ 000001d2c3a4b5c0] lavfi.freezedetect.freeze_start: 412.4")
    freeze_duration = (
        "[Parsed_freezedetect_2 @ 000001d2c3a4b5c0] lavfi.freezedetect.freeze_duration: 24")
    freeze_end = (
        "[Parsed_freezedetect_2 @ 000001d2c3a4b5c0] lavfi.freezedetect.freeze_end: 436.4")
    silence_start = "[silencedetect @ 000001d2c3a4b700] silence_start: 417.901167"
    silence_end = (
        "[silencedetect @ 000001d2c3a4b700] silence_end: 438.486146 | silence_duration: 20.584979")
    lines = ([freeze_start, silence_start, freeze_duration, freeze_end, silence_end]
             if interleaved else
             [freeze_start, freeze_duration, freeze_end, silence_start, silence_end])
    assert parse_intervals("\n".join(lines), 600_000_000) == (
        SegmentationInterval("freeze", 412_400_000, 436_400_000),
        SegmentationInterval("silence", 417_901_167, 438_486_146),
    )


@pytest.mark.parametrize("raw", [
    "[freezedetect @ 123] freeze_start: 1 | freeze_end:",
    log("freeze", "start", "nan"), log("freeze", "start", "inf"),
    log("freeze", "start", "1e9"), log("freeze", "start", ""),
    log("freeze", "end", "2"), log("freeze", "start", "11"),
    log("freeze", "start", "-2"),
    log("freeze", "start", "2") + log("freeze", "end", "1"),
    log("freeze", "start", "1") * 2,
    log("freeze", "start", "1") + log("freeze", "end", "2") + log("freeze", "start", "1"),
])
def test_parser_rejects_malformed_and_contradictory_values(raw: str) -> None:
    with pytest.raises(MediaSegmentationError, match="render_output_invalid"):
        parse_intervals(raw, 10_000_000)


def test_interval_cap_is_failure_not_truncation() -> None:
    raw = "".join(log("freeze", "start", str(i * 2)) + log("freeze", "end", str(i * 2 + 1))
                  for i in range(10_000))
    assert len(parse_intervals(raw, 30_000_000_000)) == 10_000
    with pytest.raises(MediaSegmentationError, match="media_segmentation_interval_limit"):
        parse_intervals(raw + log("silence", "start", "0"), 30_000_000_000)


def test_evidence_is_immutable_aware_bounded_and_has_profile_lineage() -> None:
    values = [SegmentationInterval("silence", 0, 1)]
    observed = SegmentationResult(tuple(values), 10, "8.1.2", "a" * 64, NOW)
    values.clear()
    assert len(observed.intervals) == 1 and observed.profile == CURRENT_SEGMENTATION_PROFILE
    with pytest.raises(FrozenInstanceError):
        observed.profile.__setattr__("decode", "gpu")
    with pytest.raises(ValueError):
        replace(observed, inspected_at=NOW.replace(tzinfo=None))
    with pytest.raises(ValueError):
        replace(observed, ffmpeg_version="/private/tool")
    with pytest.raises(ValueError):
        SegmentationInterval("freeze", 3, 2)


FAKE = r'''
import os, sys, time
mode = os.environ.get("STAGEFLOW_FAKE_SEGMENTATION", "valid")
if "-version" in sys.argv:
    print("ffmpeg version 8.1.2 synthetic")
    flag = "--enable-" + mode if mode in ("gpl", "nonfree") else "--disable-gpl"
    print("configuration: " + flag)
    raise SystemExit(0)
assert sys.argv[1:] == ["-nostdin", "-hide_banner", "-nostats", "-loglevel", "info",
    "-progress", "pipe:1", "-protocol_whitelist", "file", "-format_whitelist",
    "mov,mp4,m4a,3gp,3g2,mj2,matroska,webm,mxf,wav", "-hwaccel", "none", "-i", sys.argv[15],
    "-map", "0:v:0?", "-map", "0:a:0?", "-vf", "fps=5,scale=320:-2,freezedetect=n=0.003:d=4",
    "-af", "silencedetect=n=-40dB:d=3", "-f", "null", "-"]
assert sys.stdin.read() == ""
sys.stderr.write("private diagnostic never retained\n")
if mode == "nonzero": raise SystemExit(7)
if mode in ("timeout", "heartbeat"): time.sleep(6)
if mode == "oversized": sys.stderr.write("x" * 10000)
if mode == "malformed": sys.stderr.write("[freezedetect @ 123] freeze_start: nan\n")
if mode != "empty":
    sys.stderr.write("[freezedetect @ 123] freeze_start: 1\n")
    sys.stderr.write("[freezedetect @ 123] freeze_end: 5\n")
    sys.stderr.write("[silencedetect @ 123] silence_start: 6\n")
print("out_time_us=10000000")
print("progress=end")
'''


@pytest.fixture
def fake_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    script = tmp_path / "synthetic_ffmpeg.py"
    script.write_text(FAKE, encoding="utf-8")
    popen = subprocess.Popen

    def launch(args: list[str], **kwargs: Any) -> Any:
        assert args[0] == str(script) and kwargs["shell"] is False
        return popen([sys.executable, str(script), *args[1:]], **kwargs)

    monkeypatch.setattr(subprocess, "Popen", launch)
    return script


@pytest.mark.parametrize("mode,code,retryable", [
    ("valid", None, False), ("empty", None, False), ("heartbeat", None, False),
    ("gpl", "render_identity_refused", False), ("nonfree", "render_identity_refused", False),
    ("nonzero", "render_exit_nonzero", True), ("timeout", "media_segmentation_timeout", True),
    ("oversized", "render_output_invalid", False), ("malformed", "render_output_invalid", False),
])
def test_fake_binary_arguments_identity_failures_and_heartbeats(
    fake_binary: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    mode: str, code: str | None, retryable: bool,
) -> None:
    monkeypatch.setenv("STAGEFLOW_FAKE_SEGMENTATION", mode)
    media = tmp_path / "synthetic ; input.mp4"
    media.write_bytes(b"synthetic")
    heartbeat = Mock()

    def execute() -> SegmentationResult:
        adapter = FFmpegSegmentationAdapter(fake_binary, MutableClock(),
            timeout=0.1 if mode == "timeout" else 20, output_limit=1000)
        return adapter.inspect(media, heartbeat)

    if code is not None:
        with pytest.raises(MediaSegmentationError, match=code) as caught:
            execute()
        assert caught.value.retryable is retryable
    else:
        observed = execute()
        assert len(observed.intervals) == (0 if mode == "empty" else 2)
        assert "private" not in repr(observed)
        assert heartbeat.call_count >= (3 if mode == "heartbeat" else 2)


type Repo = InMemoryMediaSegmentationRepository | PostgresMediaSegmentationRepository


@pytest.fixture(params=["memory", "postgres"])
def repository(
    request: pytest.FixtureRequest,
) -> tuple[Repo, EntityId, RegisteredSegmentationAsset]:
    if request.param == "memory":
        event, asset, manifest = EntityId.new(), EntityId.new(), EntityId.new()
        repo = InMemoryMediaSegmentationRepository(MutableClock())
        registered = RegisteredSegmentationAsset(asset, manifest, NOW)
        repo.assets[event] = (registered,)
        return repo, event, registered
    dsn: str = request.getfixturevalue("render_postgres_dsn")
    event, asset, manifest = seed_asset(dsn, observed_at=NOW)
    return (PostgresMediaSegmentationRepository(dsn), event,
            RegisteredSegmentationAsset(asset, manifest, NOW))


def setup(repo: Repo, event: EntityId) -> ClaimRequest:
    value = repo.register_worker(Worker(EntityId.new(), "synthetic", "test-deployment", event,
                                       True, False, "1", 1, NOW, NOW))
    repo.register_capability(segmentation_capability(
        value.id, FFmpegIdentity("8.1.2", "a"*64), NOW))
    repo.record_presence(value.id, ttl=timedelta(minutes=2), maximum_concurrency=1,
                         health=WorkerHealth.AVAILABLE, pressure=WorkerPressure.NORMAL)
    return ClaimRequest(value.id, EventNetworkPolicy.LOCAL_ONLY, timedelta(minutes=5))


def test_work_key_idempotency_backfill_bounds_and_worker_round_trip(
    repository: tuple[Repo, EntityId, RegisteredSegmentationAsset],
) -> None:
    repo, event, asset = repository
    work = cast(WorkExecutionRepository[MediaSegmentationOperationInput], repo)
    enqueue = MediaSegmentationEnqueue(work, "test-deployment", MutableClock())
    operation = enqueue.enqueue(event, asset)
    assert enqueue.enqueue(event, asset) == operation
    assert repo.assets_without_operation(event) == ()
    for limit in (0, 101):
        with pytest.raises(ValueError):
            repo.assets_without_operation(event, limit=limit)
    with pytest.raises(ValueError):
        enqueue.enqueue_existing(repo, event, actor_id=EntityId.new(), authority_kind="automatic",
                                 confirmed=True)
    page, _ = enqueue.enqueue_existing(repo, event, actor_id=EntityId.new(), authority_kind="human",
                                       confirmed=True)
    assert page == (operation,)
    inspector, resolver = Mock(), Mock()
    def inspect(path: Path, heartbeat: Callable[[], None]) -> SegmentationResult:
        heartbeat()
        return result()

    inspector.inspect.side_effect = inspect
    completed = MediaSegmentationWorker(work, repo, resolver, inspector, MutableClock()).run_once(
        setup(repo, event))
    assert completed is not None and completed.status == OperationStatus.SUCCEEDED
    evidence, cursor = repo.evidence_page(asset_id=asset.asset_id)
    assert len(evidence) == 1 and cursor is None
    assert evidence[0].result == result() and evidence[0].operation_id == operation.id
    assert completed.terminal_result_media_segmentation_evidence_id == evidence[0].id
    assert enqueue.enqueue(event, asset).id == operation.id
    assert len(repo.list_attempts(operation.id)) == 1


def test_worker_retryable_failure_keeps_evidence_absent(
    repository: tuple[Repo, EntityId, RegisteredSegmentationAsset],
) -> None:
    repo, event, asset = repository
    work = cast(WorkExecutionRepository[MediaSegmentationOperationInput], repo)
    operation = MediaSegmentationEnqueue(work, "test-deployment", MutableClock()).enqueue(
        event, asset)
    request = setup(repo, event)
    inspector = Mock()
    inspector.inspect.side_effect = MediaSegmentationError("render_exit_nonzero", retryable=True)
    outcome = MediaSegmentationWorker(
        work, repo, Mock(), inspector, MutableClock()).run_once(request)
    assert outcome is not None and outcome.status == OperationStatus.RETRY_WAIT
    assert repo.evidence_page(asset_id=asset.asset_id)[0] == ()
    attempt = repo.list_attempts(operation.id)[0]
    assert attempt.reason_code == attempt.diagnostic_summary == "render_exit_nonzero"


def test_work_key_changes_only_with_asset_manifest_profile() -> None:
    from app.contexts.work_execution.contracts import EnqueueOperation
    value = MediaSegmentationOperationInput(
        EntityId.new(), EntityId.new(), "1", "freeze-silence", "1")
    request = EnqueueOperation(EntityId.new(), "synthetic", "synthetic", EntityId.new(), value,
                               0, NOW, 3, timedelta(seconds=30), False, NOW)
    baseline = media_segmentation_work_key(request)
    for field in ("asset_id", "manifest_id"):
        assert media_segmentation_work_key(replace(request, input=replace(
            value, **{field: EntityId.new()}))) != baseline
    for field in ("manifest_version", "segmentation_profile_id", "segmentation_profile_version"):
        changed = replace(request, input=replace(value, **{field: "2"}))
        assert media_segmentation_work_key(changed) != baseline
    assert pending_media_segmentation_operation(request).work_key == baseline


def test_migration_0021_exact_reversal_reapply(render_postgres_dsn: str) -> None:
    runner = PostgresMigrationRunner(render_postgres_dsn)
    with psycopg.connect(render_postgres_dsn) as conn:
        conn.prepare_threshold = None
    runner.reverse_media_segmentation_v1()
    original = schema_contract(render_postgres_dsn)
    runner.apply_media_segmentation_v1()
    runner.apply_media_segmentation_v1()
    runner.reverse_media_segmentation_v1()
    assert schema_contract(render_postgres_dsn) == original
    runner.apply_media_segmentation_v1()


def test_postgres_reverse_refusal_immutability_and_atomic_identity(
    render_postgres_dsn: str,
) -> None:
    dsn = render_postgres_dsn
    repo = PostgresMediaSegmentationRepository(dsn)
    event, asset, manifest = seed_asset(dsn, observed_at=NOW)
    operation = MediaSegmentationEnqueue(repo, "test-deployment", MutableClock()).enqueue(
        event, RegisteredSegmentationAsset(asset, manifest, NOW))
    with pytest.raises(psycopg.errors.RaiseException, match="cannot reverse 0021"):
        PostgresMigrationRunner(dsn).reverse_media_segmentation_v1()
    claim = repo.claim_next(setup(repo, event))
    assert claim is not None
    claim = repo.mark_running(claim)
    evidence = MediaSegmentationEvidence(EntityId.new(), operation.id, asset, manifest, "1.0",
                                          claim.attempt.id, result(), NOW)
    with pytest.raises(WorkExecutionConflictError):
        repo.apply_result(claim, replace(evidence, manifest_id=EntityId.new()))
    assert repo.evidence_page(asset_id=asset)[0] == ()
    repo.apply_result(claim, evidence)
    with pytest.raises(WorkExecutionLeaseLostError):
        repo.apply_result(claim, evidence)
    for table in ("media_segmentation_evidence", "media_segmentation_interval"):
        from psycopg import sql
        with pytest.raises(psycopg.errors.RaiseException, match="immutable"):
            with psycopg.connect(dsn) as conn:
                conn.execute(sql.SQL("DELETE FROM stageflow.{}").format(sql.Identifier(table)))
    assert repo.evidence_page(asset_id=asset)[0] == (evidence,)


@pytest.mark.parametrize("ambiguous", [False, True])
def test_worker_storage_failure_and_uncertain_commit_are_distinct(ambiguous: bool) -> None:
    from app.contexts.work_execution import WorkExecutionStorageUnavailableError
    repo = InMemoryMediaSegmentationRepository(MutableClock())
    event = EntityId.new()
    work = cast(WorkExecutionRepository[MediaSegmentationOperationInput], repo)
    operation = MediaSegmentationEnqueue(work, "test-deployment", MutableClock()).enqueue(
        event, RegisteredSegmentationAsset(EntityId.new(), EntityId.new(), NOW))
    inspector, results = Mock(), Mock()
    inspector.inspect.return_value = result()
    results.apply_result.side_effect = (SegmentationResultCommitAmbiguousError("uncertain")
        if ambiguous else WorkExecutionStorageUnavailableError("unavailable"))
    service = MediaSegmentationWorker(work, results, Mock(), inspector, MutableClock())
    if ambiguous:
        with pytest.raises(SegmentationResultCommitAmbiguousError):
            service.run_once(setup(repo, event))
        assert repo.get_operation(operation.id).status == OperationStatus.RUNNING
    else:
        outcome = service.run_once(setup(repo, event))
        assert outcome is not None and outcome.status == OperationStatus.RETRY_WAIT
        assert outcome.last_reason_code == "media_segmentation_storage_unavailable"


def test_retry_expiry_reclaim_and_stale_fence() -> None:
    clock = MutableClock()
    repo = InMemoryMediaSegmentationRepository(clock)
    event = EntityId.new()
    work = cast(WorkExecutionRepository[MediaSegmentationOperationInput], repo)
    operation = MediaSegmentationEnqueue(work, "test-deployment", clock).enqueue(
        event, RegisteredSegmentationAsset(EntityId.new(), EntityId.new(), NOW))
    request = setup(repo, event)
    claim = work.claim_next(request)
    assert claim is not None
    active = work.mark_running(claim)
    work.record_failure(active, OperationFailure(
        "render_exit_nonzero", True, "render_exit_nonzero"))
    clock.at += timedelta(seconds=31)
    reclaimed = work.claim_next(request)
    assert reclaimed is not None and reclaimed.attempt.fence_generation == 2
    with pytest.raises(WorkExecutionLeaseLostError):
        work.renew(active, lease_duration=timedelta(minutes=5))
    clock.at += timedelta(minutes=6)
    assert repo.reconcile_expired()[0].status == OperationStatus.RETRY_WAIT
    assert repo.get_operation(operation.id).attempt_count == 2


def test_bounded_recovery_and_read_pagination() -> None:
    repo = InMemoryMediaSegmentationRepository(MutableClock())
    work = cast(WorkExecutionRepository[MediaSegmentationOperationInput], repo)
    event, other = EntityId.new(), EntityId.new()
    repo.assets[event] = tuple(RegisteredSegmentationAsset(EntityId.new(), EntityId.new(), NOW)
                               for _ in range(105))
    repo.assets[other] = (RegisteredSegmentationAsset(EntityId.new(), EntityId.new(), NOW),)
    first = repo.assets_without_operation(event)
    assert len(first) == 100
    enqueue = MediaSegmentationEnqueue(work, "test-deployment", MutableClock())
    for asset in first:
        enqueue.enqueue(event, asset)
    assert len(repo.assets_without_operation(event)) == 5
    assert len(repo.assets_without_operation(other)) == 1
    for limit in (0, 11):
        with pytest.raises(ValueError):
            repo.evidence_page(asset_id=first[0].asset_id, limit=limit)


@pytest.mark.parametrize("mode", ["valid", "oversized", "nonzero", "heartbeat", "cancel"])
def test_adapter_bounded_pipes_and_cooperative_heartbeat_without_files(
    monkeypatch: pytest.MonkeyPatch, mode: str,
) -> None:
    from io import BytesIO

    from app.infrastructure.media_segmentation import ffmpeg
    binary, media = Path("synthetic-ffmpeg").absolute(), Path("synthetic-input.mp4").absolute()
    def safe(value: Path) -> Path:
        return value

    monkeypatch.setattr(ffmpeg, "safe_path", safe)
    monkeypatch.setattr(Path, "is_file", Mock(return_value=True))
    monkeypatch.setattr(ffmpeg, "identify_ffmpeg",
                        Mock(return_value=FFmpegIdentity("8.1.2", "a"*64)))
    process = Mock()
    process.__enter__ = Mock(return_value=process)
    process.__exit__ = Mock(return_value=False)
    process.stdout = BytesIO(b"out_time_us=10000000\nprogress=end\n")
    process.stderr = BytesIO((log("freeze", "start", "0") if mode != "oversized"
                             else "x" * 1001).encode())
    process.returncode = 7 if mode == "nonzero" else 0
    if mode in {"heartbeat", "cancel"}:
        process.wait.side_effect = [subprocess.TimeoutExpired("synthetic", 5), 0]
    launch = Mock(return_value=process)
    monkeypatch.setattr(subprocess, "Popen", launch)
    heartbeat = Mock()
    if mode == "cancel":
        heartbeat.side_effect = [None, WorkExecutionLeaseLostError("cancelled")]
    adapter = FFmpegSegmentationAdapter(binary, MutableClock(), output_limit=1000)
    if mode == "cancel":
        with pytest.raises(WorkExecutionLeaseLostError):
            adapter.inspect(media, heartbeat)
        process.kill.assert_called()
    elif mode in {"oversized", "nonzero"}:
        with pytest.raises(MediaSegmentationError) as caught:
            adapter.inspect(media, heartbeat)
        assert caught.value.code == ("render_output_invalid" if mode == "oversized"
                                     else "render_exit_nonzero")
    else:
        observed = adapter.inspect(media, heartbeat)
        assert observed.intervals == (SegmentationInterval("freeze", 0, 10_000_000),)
        assert heartbeat.call_count == (3 if mode == "heartbeat" else 2)
    assert launch.call_args.kwargs["shell"] is False
    arguments = launch.call_args.args[0]
    assert arguments[arguments.index("-hwaccel")+1] == "none"
    assert arguments[arguments.index("-vf")+1] == CURRENT_SEGMENTATION_PROFILE.video_filter
    assert arguments[arguments.index("-af")+1] == CURRENT_SEGMENTATION_PROFILE.audio_filter
    assert arguments[arguments.index("-format_whitelist")+1] == (
        CURRENT_SEGMENTATION_PROFILE.demuxer_allowlist)


def test_postgres_bounded_enqueue_session_read_and_restart(render_postgres_dsn: str) -> None:
    from psycopg.rows import dict_row
    from test_render_work_execution import seed_revision
    dsn = render_postgres_dsn
    repo = PostgresMediaSegmentationRepository(dsn)
    event, asset, manifest = seed_asset(dsn, observed_at=NOW)
    revision = seed_revision(dsn, event)
    with psycopg.connect(dsn) as conn:
        session = conn.cursor(row_factory=dict_row).execute(
            "SELECT session_id FROM stageflow.assembly_revision WHERE revision_id=%s",
            (revision.value,)).fetchone()
        assert session is not None
        session_id = EntityId(str(session["session_id"]))
        conn.execute("""INSERT INTO stageflow.media_association
            (asset_id, session_id, association_status, authority, reason_codes, evidence_ids,
             revision, decided_at, input_references, policy_id, policy_version)
            VALUES (%s,%s,'associated','deterministic','["synthetic"]','[]',1,%s,
                    '["synthetic"]','synthetic','1')""", (asset.value, session_id.value, NOW))
    operation = MediaSegmentationEnqueue(repo, "test-deployment", MutableClock()).enqueue(
        event, RegisteredSegmentationAsset(asset, manifest, NOW))
    request = setup(repo, event)
    claim = repo.claim_next(request)
    assert claim is not None
    claim = repo.mark_running(claim)
    evidence = MediaSegmentationEvidence(EntityId.new(), operation.id, asset, manifest, "1.0",
                                          claim.attempt.id, result(), NOW)
    repo.apply_result(claim, evidence)
    restarted = PostgresMediaSegmentationRepository(dsn)
    assert restarted.evidence_page(session_id=session_id)[0] == (evidence,)
    assert restarted.evidence_page(session_id=EntityId.new())[0] == ()
    assert restarted.get_operation(operation.id).status == OperationStatus.SUCCEEDED
    assert restarted.assets_without_operation(event) == ()
    assert restarted.evidence_page(asset_id=asset, limit=1, after=evidence.id) == ((), None)


def test_memory_evidence_id_collision_cannot_overwrite_history() -> None:
    repo = InMemoryMediaSegmentationRepository(MutableClock())
    work = cast(WorkExecutionRepository[MediaSegmentationOperationInput], repo)
    event = EntityId.new()
    enqueue = MediaSegmentationEnqueue(work, "test-deployment", MutableClock())
    request = setup(repo, event)
    original: MediaSegmentationEvidence | None = None
    for _ in range(2):
        asset = RegisteredSegmentationAsset(EntityId.new(), EntityId.new(), NOW)
        operation = enqueue.enqueue(event, asset)
        claim = work.claim_next(request)
        assert claim is not None
        claim = work.mark_running(claim)
        evidence = MediaSegmentationEvidence(original.id if original else EntityId.new(),
            operation.id, asset.asset_id, asset.manifest_id, "1.0", claim.attempt.id, result(), NOW)
        if original is None:
            original = repo.apply_result(claim, evidence)
        else:
            with pytest.raises(WorkExecutionConflictError, match="evidence_identity_conflict"):
                repo.apply_result(claim, evidence)
            assert repo.evidence_page(asset_id=original.asset_id)[0] == (original,)
            assert work.get_operation(operation.id).status == OperationStatus.RUNNING


def test_postgres_existing_constraints_unchanged_except_kind_membership_and_success(
    render_postgres_dsn: str,
) -> None:
    from psycopg.rows import dict_row
    dsn = render_postgres_dsn
    runner = PostgresMigrationRunner(dsn)

    def constraints() -> dict[tuple[str, str], str]:
        with psycopg.connect(dsn) as conn:
            conn.prepare_threshold = None
            rows = conn.cursor(row_factory=dict_row).execute(
                """SELECT t.relname, c.conname, pg_get_constraintdef(c.oid) AS definition
                   FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid
                   JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='stageflow'
                   AND t.relname IN ('work_operation','work_worker_capability')""").fetchall()
            return {(row["relname"], row["conname"]): row["definition"] for row in rows}

    runner.reverse_media_segmentation_v1()
    original = constraints()
    runner.apply_media_segmentation_v1()
    current = constraints()
    changed = {key for key in original if original[key] != current[key]}
    assert changed == {
        ("work_operation", "work_operation_operation_kind_check"),
        ("work_operation", "work_operation_check4"),
        ("work_worker_capability", "work_worker_capability_operation_kind_check"),
    }
    for key in changed:
        assert "media_segmentation" in current[key]


def test_postgres_recovery_enqueue_is_bounded_and_event_scoped(render_postgres_dsn: str) -> None:
    from psycopg.rows import dict_row
    dsn = render_postgres_dsn
    event, asset, _ = seed_asset(dsn, observed_at=NOW)
    other, _, _ = seed_asset(dsn, observed_at=NOW)
    with psycopg.connect(dsn) as conn:
        source = conn.cursor(row_factory=dict_row).execute(
            "SELECT stage_id, source_binding_key FROM stageflow.completed_media_asset_registry "
            "WHERE asset_id=%s", (asset.value,)).fetchone()
        assert source is not None
        for _ in range(104):
            candidate, registered, manifest = (EntityId.new() for _ in range(3))
            conn.execute(
                """INSERT INTO stageflow.media_candidate (
                   candidate_id, proposed_asset_id, stage_id, source_binding_key, source_reference,
                   discovered_at, last_observed_at, registration_state, revision)
                   VALUES (%s,%s,%s,%s,'synthetic',%s,%s,'registered',1)""",
                (candidate.value, registered.value, source["stage_id"],
                 source["source_binding_key"], NOW, NOW))
            conn.execute(
                """INSERT INTO stageflow.completed_media_asset_registry (
                   asset_id,candidate_id,manifest_id,stage_id,source_binding_key,registered_at)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (registered.value, candidate.value, manifest.value, source["stage_id"],
                 source["source_binding_key"], NOW))
    repo = PostgresMediaSegmentationRepository(dsn)
    first = repo.assets_without_operation(event)
    assert len(first) == 100
    enqueue = MediaSegmentationEnqueue(repo, "test-deployment", MutableClock())
    for registered in first:
        enqueue.enqueue(event, registered)
    assert len(repo.assets_without_operation(event)) == 5
    assert len(repo.assets_without_operation(other)) == 1
    assert len(repo.page(event, limit=100)[0]) == 100
    assert repo.page(other)[0] == ()


def test_postgres_capability_only_rows_refuse_reverse(render_postgres_dsn: str) -> None:
    repo = PostgresMediaSegmentationRepository(render_postgres_dsn)
    event, _, _ = seed_asset(render_postgres_dsn, observed_at=NOW)
    setup(repo, event)
    with pytest.raises(psycopg.errors.RaiseException, match="cannot reverse 0021"):
        PostgresMigrationRunner(render_postgres_dsn).reverse_media_segmentation_v1()


@pytest.mark.parametrize("configuration", ["--enable-gpl", "--enable-nonfree", "--disable-gpl"])
def test_shared_ffmpeg_identity_refusal_and_replacement_without_temp_files(
    monkeypatch: pytest.MonkeyPatch, configuration: str,
) -> None:
    from types import SimpleNamespace
    completed = SimpleNamespace(returncode=0,
        stdout=f"ffmpeg version 8.1.2 synthetic\nconfiguration: {configuration}\n")
    run = Mock(return_value=completed)
    monkeypatch.setattr(subprocess, "run", run)
    # Only the subprocess is faked; exercise the shared path, hash and build check.
    path = Path(__file__).resolve()
    if configuration != "--disable-gpl":
        with pytest.raises(MediaSegmentationError, match="render_identity_refused"):
            FFmpegSegmentationAdapter(path, MutableClock())
    else:
        adapter = FFmpegSegmentationAdapter(path, MutableClock())
        assert len(adapter.identity.sha256) == 64
        completed.stdout = "ffmpeg version 9.0 synthetic\nconfiguration: --disable-gpl\n"
        with pytest.raises(MediaSegmentationError, match="render_identity_refused"):
            adapter.inspect(path, Mock())
    assert run.call_args.kwargs["shell"] is False


def test_postgres_expiry_reconciles_matching_durable_result(render_postgres_dsn: str) -> None:
    repo = PostgresMediaSegmentationRepository(render_postgres_dsn)
    event, asset, manifest = seed_asset(render_postgres_dsn, observed_at=NOW)
    operation = MediaSegmentationEnqueue(repo, "test-deployment", MutableClock()).enqueue(
        event, RegisteredSegmentationAsset(asset, manifest, NOW))
    request = setup(repo, event)
    claim = repo.claim_next(request)
    assert claim is not None
    claim = repo.mark_running(claim)
    evidence = MediaSegmentationEvidence(EntityId.new(), operation.id, asset, manifest, "1.0",
                                          claim.attempt.id, result(), NOW)
    repo.apply_result(claim, evidence)
    # Synthetic interrupted terminal-reference projection with a committed owning result.
    with psycopg.connect(render_postgres_dsn) as conn:
        conn.execute(
            """UPDATE stageflow.work_operation SET operation_status='running',
               current_attempt_id=%s, lease_owner_worker_id=%s,
               lease_expires_at=statement_timestamp()-interval '1 second',
               terminal_result_type=NULL, terminal_result_media_segmentation_evidence_id=NULL
               WHERE operation_id=%s""",
            (claim.attempt.id.value, request.worker_id.value, operation.id.value))
    recovered = repo.reconcile_expired()
    assert len(recovered) == 1 and recovered[0].status == OperationStatus.SUCCEEDED
    assert recovered[0].terminal_result_media_segmentation_evidence_id == evidence.id
    assert recovered[0].last_reason_code == "result_reconciled"
    assert repo.claim_next(request) is None


@pytest.mark.parametrize("overshoot_us,expected_end", [
    (20_000, 10_000_000), (1_000_000, 10_000_000),
])
def test_parser_clamps_small_end_overshoot_at_eof(overshoot_us: int, expected_end: int) -> None:
    end = (10_000_000 + overshoot_us) / 1_000_000
    stderr = ("[silencedetect @ 0000] silence_start: 6.5\n"
              f"[silencedetect @ 0000] silence_end: {end} | silence_duration: {end - 6.5}\n")
    intervals = parse_intervals(stderr, 10_000_000)
    assert [(i.kind, i.start_microseconds, i.end_microseconds) for i in intervals] == [
        ("silence", 6_500_000, expected_end)]


def test_parser_rejects_end_overshoot_beyond_tolerance_and_any_start_overshoot() -> None:
    too_far = ("[silencedetect @ 0000] silence_start: 6.5\n"
               "[silencedetect @ 0000] silence_end: 11.2 | silence_duration: 4.7\n")
    with pytest.raises(MediaSegmentationError, match="render_output_invalid"):
        parse_intervals(too_far, 10_000_000)
    late_start = "[Parsed_freezedetect_2 @ 0000] lavfi.freezedetect.freeze_start: 10.2\n"
    with pytest.raises(MediaSegmentationError, match="render_output_invalid"):
        parse_intervals(late_start, 10_000_000)
