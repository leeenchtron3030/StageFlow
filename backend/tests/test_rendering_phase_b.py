from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, LiteralString, cast
from unittest.mock import Mock
from uuid import UUID

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app.api.v1 import demo as demo_api
from app.api.v1 import rendering as rendering_api
from app.api.v1.router import router
from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.assembly.contracts import (
    ApprovalState,
    CompletedMediaAssetContent,
    ExternalContent,
)
from app.contexts.assembly.session_contracts import (
    AssemblyAction,
    AssemblyRevision,
    AssemblySlot,
    AssemblyValidation,
    CompletionMember,
    MetadataField,
    MetadataOverrideAction,
    MetadataValue,
    PlacementRole,
    SessionAssembly,
    SlotBinding,
)
from app.contexts.assembly.session_service import SessionAssemblyService
from app.contexts.events import EventStageBootstrapRequest, StageBootstrapDefinition
from app.contexts.production.event_mode_kernel import DurableEventModeKernel
from app.contexts.production.event_mode_kernel.contracts import (
    MediaCandidate,
    MediaRegistrationState,
    RegisteredMediaAsset,
    StartSessionRequest,
)
from app.contexts.rendering.contracts import (
    FIRST_RENDER_PROFILE,
    FFmpegIdentity,
    RenderActor,
    RenderedOutput,
    RenderError,
    RenderPlan,
    RenderProfile,
    RenderReason,
    VideoInput,
)
from app.contexts.rendering.planning import build_render_plan
from app.contexts.rendering.service import RenderingService, RenderWorker
from app.contexts.work_execution import (
    ClaimRequest,
    DurableOperation,
    OperationClaim,
    OperationStatus,
    PendingOperation,
    RenderOperationInput,
    WorkExecutionConflictError,
    WorkExecutionLeaseLostError,
    WorkExecutionRepository,
)
from app.contexts.work_execution.application import pending_render_operation
from app.contexts.work_execution.memory import InMemoryWorkExecutionRepository
from app.core.config.deployment import (
    EffectiveKernelConfiguration,
    LocalRenderConfiguration,
    RuntimeProfile,
)
from app.core.config.settings import get_settings
from app.demo import controller
from app.demo.controller import worker_summary
from app.demo.render_worker import render_capability
from app.demo.service import DemoApplication, ReconcileMediaRequest
from app.infrastructure.postgres import (
    PostgresEventModeKernelRepository,
    PostgresWorkExecutionRepository,
)
from app.infrastructure.postgres.render_repository import PostgresRenderRepository
from app.infrastructure.postgres.session_assembly_repository import (
    PostgresSessionAssemblyRepository,
)
from app.infrastructure.rendering.execution import LocalRenderExecution
from app.infrastructure.rendering.ffmpeg import FFmpegAdapter, concat_list_content
from app.infrastructure.rendering.storage import OutputStore, PackagingContentResolver
from app.infrastructure.transcription import KernelMediaPathResolver
from app.shared.ids import EntityId
from app.shared.time import FixedClock
from tests.test_packaging_asset_foundation import HEADERS, SyncHttpClient
from tests.test_render_work_execution import (
    NOW,
    Harness,
    MutableClock,
    claim_request,
    general_repository,
    render_request,
    worker,
)
from tests.test_render_work_execution import (
    render_postgres_dsn as render_postgres_dsn,
)

PROFILE = FIRST_RENDER_PROFILE


def assembly() -> SessionAssembly:
    revision = AssemblyRevision(
        EntityId.new(), EntityId.new(), EntityId.new(), 1, None, EntityId.new(), 1, EntityId.new(),
        (CompletionMember(EntityId.new(), 1, NOW),),
        (SlotBinding("intro", EntityId.new(), "bound"),
         SlotBinding("media", None, "session_media")),
        (MetadataValue(MetadataField.SESSION_TITLE, ("Frozen title",), EntityId.new(), 2,
                       "operator_override"),), AssemblyValidation(()), EntityId.new(), NOW,
    )
    return SessionAssembly(revision, 1, False, ApprovalState.APPROVED, 1, None)


def plan_for(value: SessionAssembly) -> RenderPlan:
    reference = ExternalContent("synthetic", "a" * 64, 10, "video/mp4")
    return build_render_plan(value, PROFILE,
        {b.packaging_revision_id: VideoInput(reference, "video/mp4")
         for b in value.revision.bindings
         if b.packaging_revision_id is not None},
        {m.asset_id: VideoInput(CompletedMediaAssetContent(m.asset_id), "video/mp4")
         for m in value.revision.membership})


def test_plan_template_then_timeline_order_and_frozen_override_provenance() -> None:
    source = assembly()
    first, second = source.revision.membership[0], CompletionMember(EntityId.new(), 2,
                                                                    NOW + timedelta(seconds=2))
    source = replace(source, revision=replace(source.revision, membership=(second, first)))
    plan = plan_for(source)
    assert [item.reference for item in plan.inputs[1:]] == [
        CompletedMediaAssetContent(first.asset_id), CompletedMediaAssetContent(second.asset_id),
    ]
    assert plan.manifest.metadata == source.revision.metadata
    assert plan.manifest.metadata[0].source == "operator_override"
    with pytest.raises(FrozenInstanceError):
        plan.manifest.metadata[0].__setattr__("values", ("changed",))
    with pytest.raises(FrozenInstanceError):
        plan.profile.__setattr__("audio", True)
    invalid = replace(source.revision.metadata[0], values=cast(Any, ({"mutable": []},)))
    with pytest.raises(RenderError, match="render_metadata_invalid"):
        plan_for(replace(source, revision=replace(source.revision, metadata=(invalid,))))


@pytest.mark.parametrize("case", ["unapproved", "stale", "non_video", "missing"])
def test_plan_typed_ineligibility(case: str) -> None:
    source = assembly()
    if case == "unapproved":
        source = replace(source, approval_state=ApprovalState.UNREVIEWED)
    if case == "stale":
        source = replace(source, stale=True)
    reference = ExternalContent("synthetic", "a" * 64, 10,
                                "image/png" if case == "non_video" else "video/mp4")
    packaging = {b.packaging_revision_id: VideoInput(reference, reference.media_type)
                 for b in source.revision.bindings if b.packaging_revision_id is not None}
    media = {m.asset_id: VideoInput(CompletedMediaAssetContent(m.asset_id), "video/mp4")
             for m in source.revision.membership}
    with pytest.raises(RenderError) as failure:
        build_render_plan(source, PROFILE, {} if case == "missing" else packaging, media)
    assert failure.value.code == {
        "unapproved": RenderReason.NOT_APPROVED, "stale": RenderReason.STALE,
        "non_video": RenderReason.NOT_VIDEO, "missing": RenderReason.INPUT_MISSING,
    }[case]


class MemoryRendering:
    def __init__(self) -> None:
        self.clock = MutableClock()
        self.work = InMemoryWorkExecutionRepository(self.clock)
        self.source = assembly()
        self.outputs: list[RenderedOutput] = []

    def event_for_revision(self, revision_id: EntityId) -> EntityId:
        return self.source.revision.event_id

    def request(self, pending: PendingOperation[RenderOperationInput]) -> DurableOperation[
        RenderOperationInput
    ]:
        if not any(o.work_key == pending.work_key or o.id == pending.request.operation_id
                   for o in self.work.operations.values()):
            self.load_plan(pending.request.input.assembly_revision_id, PROFILE)
        return cast(DurableOperation[RenderOperationInput], self.work.enqueue(pending))

    def load_plan(self, revision_id: EntityId, profile: RenderProfile) -> RenderPlan:
        return plan_for(self.source)

    def apply_render_result(
        self, claim: OperationClaim[RenderOperationInput], output: RenderedOutput,
    ) -> RenderedOutput:
        raise AssertionError("failure cases must not register output")

    def service(self) -> RenderingService:
        return RenderingService(self, self.clock, "test-deployment")

    def claim_request(self) -> ClaimRequest:
        envelope = replace(render_request(), event_id=self.source.revision.event_id,
                           input=RenderOperationInput(self.source.revision.id, PROFILE.id,
                                                      PROFILE.version, "synthetic"))
        harness = Harness(self.work, envelope, self.clock, None)
        value = worker(harness, "render", profile=PROFILE.version)
        capability = next(iter(self.work.capabilities.values()))
        self.work.capabilities[capability.id] = replace(capability, execution_profile_id=PROFILE.id)
        return claim_request(value)


@pytest.mark.parametrize("state", [OperationStatus.TERMINAL_FAILED, OperationStatus.CANCELLED,
                                   OperationStatus.SUCCEEDED])
def test_request_replays_existing_terminal_state_and_conflicts(state: OperationStatus) -> None:
    memory = MemoryRendering()
    actor, command = RenderActor(EntityId.new()), EntityId.new()
    operation = memory.service().request_render(memory.source.revision.id, PROFILE, actor, command)
    memory.work.operations[operation.id] = replace(operation, status=state)
    memory.clock.at += timedelta(hours=1)
    memory.source = replace(memory.source, stale=True)
    replay = memory.service().request_render(memory.source.revision.id, PROFILE, actor, command)
    assert replay.status == state and replay.id == operation.id
    assert memory.service().request_render(memory.source.revision.id, PROFILE, actor,
                                            EntityId.new()).id == operation.id
    with pytest.raises(WorkExecutionConflictError):
        memory.service().request_render(memory.source.revision.id, PROFILE,
                                         RenderActor(EntityId.new()), command)


@pytest.mark.parametrize("phase", ["plan", "adapter", "resolver", "store", "unexpected", "commit"])
def test_worker_all_exceptions_after_running_release_lease_typed(
    phase: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory = MemoryRendering()
    operation = memory.service().request_render(memory.source.revision.id, PROFILE,
                                                 RenderActor(EntityId.new()), EntityId.new())
    claim = memory.claim_request()
    failure = {
        "plan": RenderError(RenderReason.INPUT_MISSING, retryable=True),
        "adapter": RenderError(RenderReason.EXIT_NONZERO, retryable=True),
        "resolver": RenderError(RenderReason.HASH_MISMATCH),
        "store": RenderError(RenderReason.STORE_UNAVAILABLE, retryable=True),
        "unexpected": RuntimeError("sensitive diagnostic must disappear"),
        "commit": RuntimeError("sensitive diagnostic must disappear"),
    }[phase]
    execution = Mock()
    if phase == "plan":
        monkeypatch.setattr(memory, "load_plan", Mock(side_effect=failure))
    elif phase == "commit":
        monkeypatch.setattr(memory, "apply_render_result", Mock(side_effect=failure))
    else:
        execution.execute.side_effect = failure
    result = RenderWorker(cast(WorkExecutionRepository[RenderOperationInput], memory.work), memory,
                          execution, PROFILE).run_once(claim)
    assert result is not None and result.lease_owner_worker_id is None
    assert result.current_attempt_id is None and result.lease_expires_at is None
    assert result.status == (OperationStatus.RETRY_WAIT if isinstance(failure, RenderError)
                             and failure.retryable else OperationStatus.TERMINAL_FAILED)
    attempt = memory.work.list_attempts(operation.id)[0]
    assert attempt.reason_code == (failure.code.value if isinstance(failure, RenderError)
                                   else "render_internal_error")
    assert attempt.diagnostic_summary == attempt.reason_code
    assert memory.outputs == []


FAKE_FFMPEG = '''import os, pathlib, sys
args = sys.argv[1:]
mode = os.environ.get("STAGEFLOW_FAKE_RENDER", "success")
if "-version" in args:
    print("ffmpeg version synthetic-1")
    flag = "--enable-" + mode if mode in ("gpl", "nonfree") else "--enable-nvenc"
    print("configuration: " + flag)
elif "lavfi" in args:
    sys.exit(1 if mode == "nvenc" else 0)
else:
    assert "-nostdin" in args and "-y" in args
    assert args[args.index("-c:v") + 1] == "h264_nvenc"
    assert args[args.index("-preset") + 1] == "p4"
    assert args[args.index("-b:v") + 1] == "8000000"
    assert args[args.index("-g") + 1] == "60" and "-an" in args
    assert args[args.index("-hwaccel") + 1] == "cuda"
    pathlib.Path(args[-1]).write_bytes(b"deterministic-render-bytes")
    print("frame=60\\nout_time_us=2000000\\nprogress=end")
    if mode == "fallback":
        print("Failed setup for format cuda", file=sys.stderr)
    if mode == "nvenc":
        print("OpenEncodeSessionEx failed: synthetic diagnostic", file=sys.stderr)
        sys.exit(1)
    if mode == "fail":
        print("synthetic private diagnostic", file=sys.stderr)
        sys.exit(1)
'''


@pytest.fixture
def fake_ffmpeg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    script = tmp_path / "fake_ffmpeg.py"
    script.write_text(FAKE_FFMPEG, encoding="utf-8")
    popen = subprocess.Popen

    def launch(args: list[str], **kwargs: Any) -> subprocess.Popen[str]:
        assert kwargs.get("shell") is False
        assert args[0] == str(script)
        # Windows has no native shebang execution. Only this test launcher supplies Python;
        # the production adapter still uses an explicit executable and no shell.
        return popen([sys.executable, str(script), *args[1:]], **kwargs)

    monkeypatch.setattr(subprocess, "Popen", launch)
    return script


@pytest.mark.parametrize("mode", ["success", "fail", "fallback", "nvenc", "gpl", "nonfree"])
def test_fake_ffmpeg_identity_profile_failures_and_temp_cleanup(
    fake_ffmpeg: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str,
) -> None:
    monkeypatch.setenv("STAGEFLOW_FAKE_RENDER", mode)
    if mode in {"gpl", "nonfree"}:
        with pytest.raises(RenderError, match="ffmpeg_identity_refused"):
            FFmpegAdapter(fake_ffmpeg)
        return
    adapter = FFmpegAdapter(fake_ffmpeg)
    assert adapter.identity.sha256 == hashlib.sha256(fake_ffmpeg.read_bytes()).hexdigest()
    assert adapter.nvenc_available() == (mode != "nvenc")
    store = OutputStore(tmp_path)
    source = tmp_path / "quote'input.mp4"
    source.write_bytes(b"synthetic")
    assert "'\\''" in concat_list_content((source,))
    with store.temporary(".mp4") as output:
        if mode == "success":
            result = adapter.render((source,), output, store, PROFILE, lambda: None)
            assert result.frame_count == 60 and result.duration_microseconds == 2_000_000
            stored = store.publish(output)
            assert stored.sha256 == hashlib.sha256(b"deterministic-render-bytes").hexdigest()
            assert (tmp_path / stored.key).read_bytes() == b"deterministic-render-bytes"
        else:
            with pytest.raises(RenderError) as failure:
                adapter.render((source,), output, store, PROFILE, lambda: None)
            assert failure.value.code == {"fail": RenderReason.EXIT_NONZERO,
                                          "fallback": RenderReason.CUDA_FALLBACK,
                                          "nvenc": RenderReason.NVENC_UNAVAILABLE}[mode]
    assert list(store.temp.iterdir()) == []


def test_packaging_hash_size_missing_and_output_containment(tmp_path: Path) -> None:
    payload = b"synthetic"
    (tmp_path / "content").write_bytes(payload)
    ref = ExternalContent("content", hashlib.sha256(payload).hexdigest(), len(payload), "video/mp4")
    resolver = PackagingContentResolver(tmp_path)
    assert resolver.resolve(ref) == tmp_path / "content"
    for altered in (replace(ref, sha256="b" * 64), replace(ref, byte_size=999)):
        with pytest.raises(RenderError, match="input_hash_mismatch"):
            resolver.resolve(altered)
    with pytest.raises(RenderError, match="input_missing"):
        resolver.resolve(replace(ref, content_key="absent"))
    with pytest.raises(RenderError):
        PackagingContentResolver(tmp_path / "..")
    with pytest.raises(RenderError, match="render_store_unavailable"):
        OutputStore(tmp_path).publish(tmp_path / "content")


def test_output_and_profile_contracts_reject_paths_naive_time_and_changes() -> None:
    value = output_for(EntityId.new(), EntityId.new(), EntityId.new())
    with pytest.raises(RenderError):
        replace(value, content_key="../escaped")
    with pytest.raises(ValueError):
        replace(value, produced_at=NOW.replace(tzinfo=None))
    with pytest.raises(RenderError, match="render_profile_unsupported"):
        build_render_plan(assembly(), replace(PROFILE, audio=cast(Any, True)), {}, {})
    with pytest.raises(RenderError, match="render_human_required"):
        RenderActor(EntityId.new(), cast(Any, "automatic"))


@pytest.mark.parametrize("mode", ["success", "fail", "fallback", "nvenc"])
def test_execution_sidecar_frozen_provenance_and_no_partial_output(
    fake_ffmpeg: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str,
) -> None:
    monkeypatch.setenv("STAGEFLOW_FAKE_RENDER", mode)
    memory = MemoryRendering()
    operation = memory.service().request_render(memory.source.revision.id, PROFILE,
                                                 RenderActor(EntityId.new()), EntityId.new())
    claim = memory.work.claim_next(memory.claim_request())
    assert claim is not None
    payload = b"synthetic-input"
    (tmp_path / "content").write_bytes(payload)
    reference = ExternalContent("content", hashlib.sha256(payload).hexdigest(), len(payload),
                                "video/mp4")
    plan = replace(plan_for(memory.source), inputs=(VideoInput(reference, "video/mp4"),))
    root = tmp_path / "output"
    root.mkdir()
    store = OutputStore(root)
    execution = LocalRenderExecution(FFmpegAdapter(fake_ffmpeg), store,
        PackagingContentResolver(tmp_path), Mock(spec=KernelMediaPathResolver), Mock(),
        memory.clock)
    if mode == "success":
        output = execution.execute(cast(OperationClaim[RenderOperationInput], claim), plan,
                                    lambda: None)
        sidecar = (root / output.manifest_content_key).read_bytes()
        assert hashlib.sha256(sidecar).hexdigest() == output.manifest_sha256
        document = json.loads(sidecar)
        assert document["metadata"][0]["source"] == "operator_override"
        assert document["metadata"][0]["source_id"] == plan.manifest.metadata[0].source_id.value
        assert document["metadata"][0]["values"] == ["Frozen title"]
        assert output.operation_id == operation.id
    else:
        with pytest.raises(RenderError):
            execution.execute(cast(OperationClaim[RenderOperationInput], claim), plan, lambda: None)
        assert tuple(root.iterdir()) == (store.temp,)
    assert list(store.temp.iterdir()) == []


def test_packaging_refuses_reparse_points(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    payload = b"synthetic"
    target = tmp_path / "content"
    target.write_bytes(payload)
    resolver = PackagingContentResolver(tmp_path)
    lstat = Path.lstat

    def reparse(path: Path, *args: object, **kwargs: object) -> os.stat_result:
        info = lstat(path)
        if path == target:
            return cast(os.stat_result, SimpleNamespace(st_mode=info.st_mode,
                                                       st_file_attributes=0x400))
        return info

    monkeypatch.setattr(Path, "lstat", reparse)
    with pytest.raises(RenderError, match="input_missing"):
        resolver.resolve(ExternalContent("content", hashlib.sha256(payload).hexdigest(),
                                          len(payload), "video/mp4"))


def output_for(operation: EntityId, attempt: EntityId, revision: EntityId) -> RenderedOutput:
    return RenderedOutput(EntityId.new(), revision, PROFILE.id, PROFILE.version, operation, attempt,
                          "opaquevideo", "a" * 64, "opaquemanifest", "b" * 64, 100, "video/mp4",
                          2_000_000, 60, FFmpegIdentity("synthetic-1", "c" * 64), NOW)


@pytest.fixture
def approved_revision(render_postgres_dsn: str) -> AssemblyRevision:
    repo = PostgresEventModeKernelRepository(render_postgres_dsn)
    kernel = DurableEventModeKernel(repository=repo, clock=FixedClock(NOW))
    actor = EntityId.new()
    source = "source-" + EntityId.new().value
    boot = kernel.bootstrap(EventStageBootstrapRequest(
        EntityId.new(), "event-" + EntityId.new().value, "Synthetic Event",
        (StageBootstrapDefinition("main", "Synthetic Stage", {source: "synthetic"}),), actor, NOW,
    ))
    assert boot.event is not None
    event, stage = boot.event.id, boot.stages[0].id
    session = kernel.start_session(StartSessionRequest(
        EntityId.new(), event, stage, actor, NOW, NOW,
    ))
    asset, candidate = EntityId.new(), EntityId.new()
    repo.register_candidate(MediaCandidate(candidate, asset, stage, source, "synthetic.mp4", NOW,
                                           NOW, MediaRegistrationState.READY, 1))
    repo.register_asset(RegisteredMediaAsset(asset, candidate, EntityId.new(), stage, source, NOW,
                                             NOW, NOW + timedelta(seconds=2)))
    kernel.assign_asset(operation_id=EntityId.new(), asset_id=asset, session_id=session.id,
                        actor_id=actor, reason="Synthetic assignment")
    kernel.correct_session_boundary(operation_id=EntityId.new(), session_id=session.id,
                                     boundary_kind="end", boundary_at=NOW + timedelta(seconds=2),
                                     actor_id=actor, reason="Synthetic end")
    kernel.mark_package_ready(session.id)
    session = kernel.complete_package(operation_id=EntityId.new(), session_id=session.id,
                                       actor_id=actor, approved=True, reason="Synthetic completion")
    service = SessionAssemblyService(PostgresSessionAssemblyRepository(render_postgres_dsn),
                                     FixedClock(NOW))
    template = service.create_template(operation_id=EntityId.new(), actor_id=actor, event_id=event,
        template_key="synthetic", expected_version=0, name="Synthetic",
        slots=(AssemblySlot("media", PlacementRole.SESSION_MEDIA, True),))
    revision = service.propose(operation_id=EntityId.new(), actor_id=actor, session_id=session.id,
        template_id=template.id, expected_revision=0,
        expected_package_revision=session.package_revision)
    service.decide(operation_id=EntityId.new(), actor_id=actor, session_id=session.id,
        revision_number=1, expected_revision=1, expected_decision_count=0,
        action=AssemblyAction.APPROVE, reason="Synthetic approval")
    return revision


def test_postgres_atomic_output_commit_restart_fence_and_listing(
    render_postgres_dsn: str, approved_revision: AssemblyRevision, monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo = PostgresRenderRepository(render_postgres_dsn)
    service = RenderingService(repo, FixedClock(NOW), "test-deployment")
    operation = service.request_render(approved_revision.id, PROFILE, RenderActor(EntityId.new()),
                                       EntityId.new())
    envelope = replace(render_request(), event_id=approved_revision.event_id)
    harness = Harness(general_repository(render_postgres_dsn), envelope, MutableClock(),
                      render_postgres_dsn)
    renderer = worker(harness, "render", profile=PROFILE.version)
    with psycopg.connect(render_postgres_dsn) as conn:
        conn.execute("UPDATE stageflow.work_worker_capability SET execution_profile_id=%s "
                     "WHERE worker_id=%s", (PROFILE.id, renderer.id.value))
    claim = repo.claim_next(claim_request(renderer))
    assert claim is not None
    claim = repo.mark_running(claim)
    output = output_for(operation.id, claim.attempt.id, approved_revision.id)
    with pytest.raises(WorkExecutionLeaseLostError):
        repo.apply_render_result(replace(claim, attempt=replace(claim.attempt, fence_generation=9)),
                                  output)
    assert repo.list_outputs(approved_revision.event_id, approved_revision.session_id)[0] == ()
    assert repo.apply_render_result(claim, output) == output
    restarted = PostgresRenderRepository(render_postgres_dsn)
    assert restarted.get_operation(operation.id).terminal_result_rendered_output_id == output.id
    assert restarted.get_operation(operation.id).status == OperationStatus.SUCCEEDED
    assert PostgresWorkExecutionRepository(render_postgres_dsn).list_attempts(operation.id) == ()
    assert len(general_repository(render_postgres_dsn).list_attempts(operation.id)) == 1
    assert restarted.apply_render_result(claim, output) == output
    assert restarted.list_outputs(
        approved_revision.event_id, approved_revision.session_id,
    )[0] == (output,)
    assert restarted.list_outputs(EntityId.new(), approved_revision.session_id)[0] == ()
    assert restarted.list_render_operations(approved_revision.event_id,
                                            approved_revision.session_id)[0][0].id == operation.id

    # A storage failure after inserting bytes identity must roll back both durable writes.
    assemblies = SessionAssemblyService(PostgresSessionAssemblyRepository(render_postgres_dsn),
                                         FixedClock(NOW))
    next_revision = assemblies.propose(operation_id=EntityId.new(), actor_id=EntityId.new(),
        session_id=approved_revision.session_id, template_id=approved_revision.template_id,
        expected_revision=1, expected_package_revision=approved_revision.package_revision)
    assemblies.decide(operation_id=EntityId.new(), actor_id=EntityId.new(),
        session_id=next_revision.session_id, revision_number=2, expected_revision=2,
        expected_decision_count=0, action=AssemblyAction.APPROVE, reason="Synthetic approval")
    next_operation = service.request_render(next_revision.id, PROFILE, RenderActor(EntityId.new()),
                                            EntityId.new())
    next_claim = repo.claim_next(claim_request(renderer))
    assert next_claim is not None and next_claim.operation.id == next_operation.id
    next_output = output_for(next_operation.id, next_claim.attempt.id, next_revision.id)
    with psycopg.connect(render_postgres_dsn) as conn:
        conn.execute("""CREATE FUNCTION stageflow.synthetic_render_commit_fault()
                        RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
                        IF NEW.operation_status='succeeded' THEN
                            RAISE EXCEPTION 'synthetic_commit_fault';
                        END IF; RETURN NEW; END; $$""")
        conn.execute("""CREATE TRIGGER synthetic_render_commit_fault
                        BEFORE UPDATE ON stageflow.work_operation FOR EACH ROW
                        EXECUTE FUNCTION stageflow.synthetic_render_commit_fault()""")
    with pytest.raises(psycopg.errors.RaiseException, match="synthetic_commit_fault"):
        repo.apply_render_result(next_claim, next_output)
    assert repo.get_operation(next_operation.id).status == OperationStatus.LEASED
    assert repo.list_outputs(
        approved_revision.event_id, approved_revision.session_id,
    )[0] == (output,)
    with psycopg.connect(render_postgres_dsn) as conn:
        conn.execute("DROP TRIGGER synthetic_render_commit_fault ON stageflow.work_operation")
        conn.execute("DROP FUNCTION stageflow.synthetic_render_commit_fault()")
    repo.apply_render_result(next_claim, next_output)
    first, cursor = repo.list_outputs(approved_revision.event_id,
                                      approved_revision.session_id, limit=1)
    assert len(first) == 1 and cursor is not None
    second, end = repo.list_outputs(approved_revision.event_id, approved_revision.session_id,
                                    after=cursor, limit=1)
    assert len(second) == 1 and end is None
    assert {item.id for item in (*first, *second)} == {output.id, next_output.id}
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    client = cast(SyncHttpClient, TestClient(app))

    def api_service(request: object) -> RenderingService:
        return service

    monkeypatch.setattr(rendering_api, "_service", api_service)
    def assert_no_private_values(body: object) -> None:
        serialized = json.dumps(body)
        for forbidden in (str(tmp_path), str(tmp_path / "output"),
                          str(tmp_path / "packaging"), "source_reference", render_postgres_dsn,
                          "output_root", "postgres_dsn"):
            assert forbidden not in serialized
            assert json.dumps(forbidden)[1:-1] not in serialized

    posted = client.post("/api/v1/rendering/requests", headers=HEADERS, json={
        "assembly_revision_id": approved_revision.id.value,
        "actor_id": EntityId.new().value, "command_id": EntityId.new().value,
        "confirmed": "confirmed",
    })
    assert posted.status_code == 200
    assert_no_private_values(posted.json())
    for route in ("operations", "outputs"):
        url = f"/api/v1/rendering/{route}?event_id={approved_revision.event_id.value}"
        url += f"&session_id={approved_revision.session_id.value}&limit=1"
        page = client.get(url, headers=HEADERS)
        assert page.status_code == 200
        body = page.json()
        assert_no_private_values(body)
        assert len(body["items"]) == 1 and body["next_after"] is not None
        final_page = client.get(url + "&after=" + body["next_after"], headers=HEADERS)
        assert_no_private_values(final_page.json())
        assert final_page.status_code == 200 and final_page.json()["next_after"] is None
        assert len(final_page.json()["items"]) == 1
        assert not {"output_root", "source_reference", "postgres_dsn"}.intersection(body)
        if route == "outputs":
            assert body["items"][0]["content_key"] == "opaquevideo"
            assert body["items"][0]["manifest_sha256"] == "b" * 64


def test_postgres_render_capability_restart_nvenc_observations(
    render_postgres_dsn: str, approved_revision: AssemblyRevision,
) -> None:
    harness = Harness(general_repository(render_postgres_dsn),
        replace(render_request(), event_id=approved_revision.event_id), MutableClock(),
        render_postgres_dsn)
    renderer = worker(harness, "render")
    repo = PostgresRenderRepository(render_postgres_dsn)
    identity = FFmpegIdentity("7.1+local~build", "e" * 64)
    for sequence, available in enumerate((False, True, False, True), start=1):
        cap = render_capability(renderer.id, identity, available, NOW + timedelta(seconds=sequence))
        encoded = cap.runtime_id.removeprefix("ffmpeg:")
        decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
        assert decoded == identity.version
        assert cap.runtime_version == identity.sha256
        repo.register_render_capability(cap)
        with psycopg.connect(render_postgres_dsn) as conn:
            rows = conn.execute("SELECT capability_id,configured_eligible "
                "FROM stageflow.work_worker_capability WHERE worker_id=%s "
                "AND operation_kind='render' AND effective_until IS NULL",
                (renderer.id.value,)).fetchall()
        assert rows == [{"capability_id": UUID(cap.id.value),
                         "configured_eligible": available}]


@pytest.mark.parametrize("unexpected", [False, True])
def test_postgres_running_render_failure_releases_lease_immediately(
    render_postgres_dsn: str, approved_revision: AssemblyRevision, unexpected: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = PostgresRenderRepository(render_postgres_dsn)
    service = RenderingService(repo, FixedClock(NOW), "test-deployment")
    operation = service.request_render(approved_revision.id, PROFILE, RenderActor(EntityId.new()),
                                       EntityId.new())
    harness = Harness(general_repository(render_postgres_dsn),
        replace(render_request(), event_id=approved_revision.event_id), MutableClock(),
        render_postgres_dsn)
    renderer = worker(harness, "render")
    repo.register_render_capability(render_capability(renderer.id,
        FFmpegIdentity("synthetic-1", "a" * 64), True, NOW + timedelta(seconds=1)))
    execution = Mock()
    execution.execute.side_effect = (RuntimeError("discard synthetic diagnostic") if unexpected
        else RenderError(RenderReason.EXIT_NONZERO, retryable=True))
    # The fixture borrows an outer transaction, which cannot change isolation midstream.
    # This test exercises real claim/failure persistence; the source port supplies pinned facts.
    plan = plan_for(replace(assembly(), revision=approved_revision))
    monkeypatch.setattr(repo, "load_plan", Mock(return_value=plan))
    result = RenderWorker(repo, repo, execution, PROFILE).run_once(claim_request(renderer))
    execution.execute.assert_called_once()
    assert result is not None and result.id == operation.id
    assert result.status == (OperationStatus.TERMINAL_FAILED if unexpected
                             else OperationStatus.RETRY_WAIT)
    assert result.lease_expires_at is None and result.current_attempt_id is None
    assert result.lease_owner_worker_id is None
    attempt = repo.list_attempts(operation.id)[0]
    assert attempt.reason_code == ("render_internal_error" if unexpected else "ffmpeg_exit_nonzero")
    assert attempt.diagnostic_summary == attempt.reason_code
    assert repo.list_outputs(approved_revision.event_id, approved_revision.session_id)[0] == ()


def test_demo_workspace_transcription_status_reconciliation_and_work_queue_isolated(
    render_postgres_dsn: str, approved_revision: AssemblyRevision, monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel_repo = PostgresEventModeKernelRepository(render_postgres_dsn)
    with psycopg.Connection[dict[str, Any]].connect(
        render_postgres_dsn, row_factory=dict_row,
    ) as conn:
        row = conn.execute("SELECT event_key FROM stageflow.business_event WHERE event_id=%s",
                           (approved_revision.event_id.value,)).fetchone()
    assert row is not None
    configuration = cast(EffectiveKernelConfiguration, SimpleNamespace(
        postgres_dsn=render_postgres_dsn, deployment=SimpleNamespace(
            deployment_id="test-deployment", event=SimpleNamespace(key=row["event_key"]),
            runtime_profile=RuntimeProfile.DEMO_SINGLE_STAGE,
            local_transcription=SimpleNamespace(execution_profile_id="synthetic",
                                                 execution_profile_version="1"),
        ),
    ))
    components = KernelComponents(configuration, kernel_repo,
        DurableEventModeKernel(repository=kernel_repo, clock=FixedClock(NOW)))
    monkeypatch.setattr(KernelComponents, "run_media_cycle",
                        Mock(return_value=SimpleNamespace(candidates_seen=0, assets_registered=0)))
    demo = DemoApplication.from_components(components)
    command = ReconcileMediaRequest("synthetic", NOW, approved_revision.session_id)
    demo.reconcile_media(command)
    before_service = demo.reconcile_media(command)
    assert len(before_service.operations) == 1 and before_service.operations_enqueued == 0
    app = FastAPI()
    app.state.kernel = components
    app.include_router(router, prefix="/api/v1")
    client = cast(SyncHttpClient, TestClient(app))
    monkeypatch.setattr(demo_api, "_OPERATION_LIMIT", 1)
    workspace = f"/api/v1/demo/sessions/{approved_revision.session_id.value}/workspace"
    queue = f"/api/v1/producer/events/{approved_revision.event_id.value}/work-queue?limit=1"
    before_workspace = client.get(workspace, headers=HEADERS)
    before_queue = client.get(queue, headers=HEADERS)
    assert before_workspace.status_code == before_queue.status_code == 200
    repository = general_repository(render_postgres_dsn)
    # More rows than both the Demo reconciliation limit (500) and workspace limit (1).
    for ordinal in range(501):
        request = replace(render_request(), event_id=approved_revision.event_id,
                          requested_at=NOW + timedelta(seconds=1),
                          input=RenderOperationInput(approved_revision.id, "synthetic",
                                                     str(ordinal), "synthetic"))
        repository.enqueue(pending_render_operation(request))
    assert demo.reconcile_media(command) == before_service
    assert client.get(workspace, headers=HEADERS).json() == before_workspace.json()
    assert client.get(queue, headers=HEADERS).json() == before_queue.json()


@pytest.mark.parametrize("terminal", ["failed", "cancelled"])
def test_postgres_request_terminal_replay_and_conflict(
    render_postgres_dsn: str, approved_revision: AssemblyRevision, terminal: str,
) -> None:
    repo = PostgresRenderRepository(render_postgres_dsn)
    service = RenderingService(repo, FixedClock(NOW), "test-deployment")
    actor, command = RenderActor(EntityId.new()), EntityId.new()
    operation = service.request_render(approved_revision.id, PROFILE, actor, command)
    status = OperationStatus.TERMINAL_FAILED if terminal == "failed" else OperationStatus.CANCELLED
    with psycopg.connect(render_postgres_dsn) as conn:
        conn.execute("UPDATE stageflow.work_operation SET operation_status=%s "
                     "WHERE operation_id=%s",
                     (status.value, operation.id.value))
    replay = RenderingService(PostgresRenderRepository(render_postgres_dsn),
                               FixedClock(NOW + timedelta(hours=1)), "test-deployment")
    assert replay.request_render(approved_revision.id, PROFILE, actor, command).status == status
    with pytest.raises(WorkExecutionConflictError):
        replay.request_render(approved_revision.id, PROFILE, RenderActor(EntityId.new()), command)


@pytest.mark.parametrize("change", ["override", "package", "unapproved"])
def test_postgres_request_uses_assembly_staleness_and_approval(
    render_postgres_dsn: str, approved_revision: AssemblyRevision, change: str,
) -> None:
    assemblies = SessionAssemblyService(PostgresSessionAssemblyRepository(render_postgres_dsn),
                                         FixedClock(NOW))
    if change == "override":
        assemblies.record_metadata_override(operation_id=EntityId.new(), actor_id=EntityId.new(),
            session_id=approved_revision.session_id, field=MetadataField.SESSION_TITLE,
            action=MetadataOverrideAction.SET, expected_sequence=0, reason="Synthetic correction",
            values=("New value",))
    elif change == "package":
        with psycopg.connect(render_postgres_dsn) as conn:
            conn.execute("UPDATE stageflow.session SET package_revision=package_revision+1 "
                         "WHERE session_id=%s", (approved_revision.session_id.value,))
    else:
        assemblies.decide(operation_id=EntityId.new(), actor_id=EntityId.new(),
            session_id=approved_revision.session_id, revision_number=1, expected_revision=1,
            expected_decision_count=1, action=AssemblyAction.REJECT, reason="Synthetic rejection")
    repo = PostgresRenderRepository(render_postgres_dsn)
    with pytest.raises(RenderError) as failure:
        RenderingService(repo, FixedClock(NOW), "test-deployment").request_render(
            approved_revision.id, PROFILE, RenderActor(EntityId.new()), EntityId.new(),
        )
    assert failure.value.code == (RenderReason.NOT_APPROVED if change == "unapproved"
                                  else RenderReason.STALE)
    assert repo.list_render_operations(approved_revision.event_id,
                                       approved_revision.session_id)[0] == ()


def test_transcription_kind_projection_and_limit_not_crowded(
    render_postgres_dsn: str, approved_revision: AssemblyRevision,
) -> None:
    from app.contexts.work_execution import TranscriptionOperationApplication
    from tests.test_render_work_execution import postgres_harness, transcription_request_for

    harness = postgres_harness(render_postgres_dsn)
    request = replace(transcription_request_for(harness), event_id=approved_revision.event_id)
    typed = PostgresWorkExecutionRepository(render_postgres_dsn)
    operation = TranscriptionOperationApplication(typed).enqueue(request)
    before = typed.list_operations(deployment_id="test-deployment",
                                   event_id=request.event_id, limit=1)
    projection = typed.status_projection(deployment_id="test-deployment", event_id=request.event_id)
    render = RenderingService(PostgresRenderRepository(render_postgres_dsn), FixedClock(NOW),
                               "test-deployment").request_render(approved_revision.id, PROFILE,
                                                                  RenderActor(EntityId.new()),
                                                                  EntityId.new())
    with psycopg.connect(render_postgres_dsn) as conn:
        conn.execute("UPDATE stageflow.work_operation SET created_at=statement_timestamp(), "
                     "updated_at=statement_timestamp(), "
                     "required_for_event=true WHERE operation_id=%s", (render.id.value,))
    assert typed.list_operations(deployment_id="test-deployment", event_id=request.event_id,
                                  limit=1) == before
    after = typed.status_projection(deployment_id="test-deployment", event_id=request.event_id)
    assert after.counts == projection.counts
    assert after.active_lease_count == projection.active_lease_count
    assert after.attention_codes == projection.attention_codes
    assert before[0].id == operation.id


def test_config_default_off_and_refuses_repo_relative_or_parent_paths() -> None:
    external = Path(Path.cwd().anchor) / "synthetic-render-configuration"
    configuration = LocalRenderConfiguration(ffmpeg_path=str(external / "ffmpeg"),
        output_root=str(external / "output"), packaging_content_root=str(external / "packaging"))
    assert not configuration.enabled
    for bad in ("relative", "../parent", str(Path(__file__).resolve())):
        with pytest.raises(ValueError):
            LocalRenderConfiguration(ffmpeg_path=bad, output_root=bad, packaging_content_root=bad)


@pytest.mark.parametrize("has_capability", [True, False])
def test_transcription_worker_presence_limit_not_crowded(
    render_postgres_dsn: str, approved_revision: AssemblyRevision, monkeypatch: pytest.MonkeyPatch,
    has_capability: bool,
) -> None:
    from app.contexts.work_execution import Worker
    from tests.test_render_work_execution import worker

    harness = Harness(general_repository(render_postgres_dsn),
        replace(render_request(), event_id=approved_revision.event_id), MutableClock(),
        render_postgres_dsn)
    if has_capability:
        worker(harness, "transcription")
    else:
        harness.repository.register_worker(Worker(
            EntityId.new(), "synthetic-no-capability", "test-deployment",
            approved_revision.event_id, True, False, "test-v1", 1, NOW, NOW,
        ))

    class Rows:
        def __init__(self, rows: list[dict[str, Any]]) -> None:
            self.rows = rows

        def fetchall(self) -> list[tuple[object, ...]]:
            return [tuple(row.values()) for row in self.rows]

    class Connection:
        def __init__(self, connection: psycopg.Connection[dict[str, Any]]) -> None:
            self.connection = connection

        def execute(self, query: LiteralString, params: tuple[object, ...] | None = None) -> Rows:
            cursor = self.connection.execute(query, params)
            return Rows(cursor.fetchall() if cursor.description else [])

    @contextmanager
    def connect(dsn: str) -> Generator[Connection]:
        with psycopg.Connection[dict[str, Any]].connect(dsn) as conn:
            yield Connection(conn)

    monkeypatch.setattr(controller, "psycopg",
                        SimpleNamespace(connect=connect, Error=psycopg.Error))
    before = worker_summary(render_postgres_dsn, approved_revision.event_id.value,
                            "test-deployment")
    assert before["registered"] == 1
    if not has_capability:
        assert before["state"] == "stale"
        assert before["current"] is True
    for _ in range(21):
        worker(harness, "render")
    assert worker_summary(render_postgres_dsn, approved_revision.event_id.value,
                           "test-deployment") == before


def test_api_auth_human_bounds_and_terminal_state(monkeypatch: pytest.MonkeyPatch) -> None:
    memory = MemoryRendering()
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    client = cast(SyncHttpClient, TestClient(app))
    monkeypatch.setenv("STAGEFLOW_API_SHARED_SECRET",
                       "synthetic-shared-secret-12345678901234567890")
    get_settings.cache_clear()
    headers = {"X-StageFlow-Api-Secret": "synthetic-shared-secret-12345678901234567890"}
    def service(request: object) -> RenderingService:
        return memory.service()

    monkeypatch.setattr(rendering_api, "_service", service)
    body = {"assembly_revision_id": memory.source.revision.id.value,
            "actor_id": EntityId.new().value, "command_id": EntityId.new().value,
            "confirmed": "confirmed"}
    assert client.post("/api/v1/rendering/requests", json=body).status_code == 401
    response = client.post("/api/v1/rendering/requests", json=body, headers=headers)
    assert response.status_code == 200
    operation_id = EntityId(response.json()["operation_id"])
    memory.work.operations[operation_id] = replace(memory.work.operations[operation_id],
                                                  status=OperationStatus.TERMINAL_FAILED)
    assert client.post("/api/v1/rendering/requests", json=body,
                        headers=headers).json()["state"] == "terminal_failed"
    assert client.post("/api/v1/rendering/requests", json={**body, "authority_kind": "automatic"},
                        headers=headers).status_code == 422
    for route in ("operations", "outputs"):
        assert client.get(f"/api/v1/rendering/{route}?event_id={EntityId.new().value}"
                          f"&session_id={EntityId.new().value}&limit=101",
                          headers=headers).status_code == 422
    get_settings.cache_clear()
