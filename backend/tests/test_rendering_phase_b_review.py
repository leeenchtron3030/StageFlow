from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock

import psycopg
import pytest

from app.contexts.assembly.contracts import (
    ApprovalAction,
    CompletedMediaAssetContent,
    ExternalContent,
    PackagingAssetRole,
    RevisionContent,
)
from app.contexts.assembly.service import PackagingAssetService
from app.contexts.assembly.session_contracts import (
    AssemblyAction,
    AssemblyRevision,
    AssemblySlot,
    PlacementRole,
)
from app.contexts.assembly.session_service import SessionAssemblyService
from app.contexts.events import EventStageBootstrapRequest, StageBootstrapDefinition
from app.contexts.production.event_mode_kernel import (
    DurableEventModeKernel,
    InMemoryEventModeKernelRepository,
)
from app.contexts.production.event_mode_kernel.contracts import (
    MediaCandidate,
    MediaRegistrationState,
    RegisteredMediaAsset,
)
from app.contexts.rendering.contracts import RenderError, RenderPlan, RenderReason, VideoInput
from app.contexts.rendering.service import (
    RenderingService,
    RenderResultCommitAmbiguousError,
    RenderWorker,
)
from app.contexts.transcription_evidence import TranscriptionExecutionError
from app.contexts.work_execution import (
    OperationClaim,
    OperationStatus,
    RenderOperationInput,
    WorkExecutionConflictError,
    WorkExecutionLeaseLostError,
    WorkExecutionRepository,
    WorkExecutionStorageUnavailableError,
)
from app.infrastructure.postgres.packaging_asset_repository import PostgresPackagingAssetRepository
from app.infrastructure.postgres.render_repository import PostgresRenderRepository
from app.infrastructure.postgres.session_assembly_repository import (
    PostgresSessionAssemblyRepository,
)
from app.infrastructure.rendering import storage
from app.infrastructure.rendering.execution import LocalRenderExecution
from app.infrastructure.rendering.ffmpeg import FFmpegAdapter
from app.infrastructure.rendering.storage import OutputStore, PackagingContentResolver
from app.infrastructure.transcription import KernelMediaPathResolver
from app.shared.ids import EntityId
from app.shared.time import FixedClock
from tests.test_rendering_phase_b import (
    NOW,
    PROFILE,
    MemoryRendering,
    RenderActor,
    output_for,
    plan_for,
)
from tests.test_rendering_phase_b import approved_revision as approved_revision
from tests.test_rendering_phase_b import fake_ffmpeg as fake_ffmpeg
from tests.test_rendering_phase_b import render_postgres_dsn as render_postgres_dsn


@pytest.mark.parametrize("sync_fails", [False, True])
def test_publish_fsync_uses_writable_descriptor_and_always_closes(
    monkeypatch: pytest.MonkeyPatch, sync_fails: bool,
) -> None:
    # No filesystem/temp fixture: exercise publish's handle contract on Windows too.
    root = Path.cwd() / "synthetic-output"
    store = object.__new__(OutputStore)
    store.root, store.temp = root, root / ".tmp"
    path = store.temp / "synthetic.mp4"
    monkeypatch.setattr(store, "validate", Mock())
    monkeypatch.setattr(storage, "safe_path", Mock(return_value=path))
    monkeypatch.setattr(storage, "digest_file", Mock(return_value=("a" * 64, 12)))
    opened, closed, synced, renamed = Mock(return_value=91), Mock(), Mock(), Mock()
    if sync_fails:
        synced.side_effect = OSError("synthetic sync failure")
    monkeypatch.setattr(os, "open", opened)
    monkeypatch.setattr(os, "close", closed)
    monkeypatch.setattr(os, "fsync", synced)
    monkeypatch.setattr(Path, "rename", renamed)
    if sync_fails:
        with pytest.raises(OSError, match="synthetic sync failure"):
            store.publish(path)
        renamed.assert_not_called()
    else:
        result = store.publish(path)
        assert result.sha256 == "a" * 64 and result.byte_size == 12
        renamed.assert_called_once_with(root / result.key)
    opened.assert_called_once_with(path, os.O_RDWR | getattr(os, "O_BINARY", 0))
    synced.assert_called_once_with(91)
    closed.assert_called_once_with(91)


@pytest.mark.parametrize("case", ["success", "missing_file", "unconfigured_source"])
def test_real_session_media_resolver_render_and_failure_classification(
    fake_ffmpeg: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str,
) -> None:
    monkeypatch.setenv("STAGEFLOW_FAKE_RENDER", "success")
    kernel = InMemoryEventModeKernelRepository()
    boot = DurableEventModeKernel(repository=kernel, clock=FixedClock(NOW)).bootstrap(
        EventStageBootstrapRequest(
        EntityId.new(), "synthetic", "Synthetic", (StageBootstrapDefinition(
            "main", "Synthetic", {"source": "synthetic"}),), EntityId.new(), NOW,
    ))
    source = tmp_path / "source"
    source.mkdir()
    media = source / "synthetic.mp4"
    if case != "missing_file":
        media.write_bytes(b"synthetic-video")
    asset_id, candidate_id = EntityId.new(), EntityId.new()
    kernel.register_candidate(MediaCandidate(candidate_id, asset_id, boot.stages[0].id,
        "source", str(media), NOW, NOW, MediaRegistrationState.READY, 1))
    kernel.register_asset(RegisteredMediaAsset(asset_id, candidate_id, EntityId.new(),
        boot.stages[0].id, "source", NOW, NOW, NOW + timedelta(seconds=2)))
    resolver = KernelMediaPathResolver(kernel, source_roots=(
        {} if case == "unconfigured_source" else {"source": str(source)}))
    root = tmp_path / "output"
    root.mkdir()
    store = OutputStore(root)
    execution = LocalRenderExecution(FFmpegAdapter(fake_ffmpeg), store,
        PackagingContentResolver(source), resolver, kernel, FixedClock(NOW))
    memory = MemoryRendering()
    operation = memory.service().request_render(memory.source.revision.id, PROFILE,
                                                RenderActor(EntityId.new()), EntityId.new())
    plan = replace(plan_for(memory.source), inputs=(
        VideoInput(CompletedMediaAssetContent(asset_id), "video/mp4"),))
    monkeypatch.setattr(memory, "load_plan", Mock(return_value=plan))
    if case == "success":
        claim = memory.work.claim_next(memory.claim_request())
        assert claim is not None
        output = execution.execute(cast(OperationClaim[RenderOperationInput], claim),
                                   plan, lambda: None)
        assert (root / output.content_key).read_bytes() == b"deterministic-render-bytes"
        assert (root / output.manifest_content_key).is_file()
    else:
        result = RenderWorker(cast(WorkExecutionRepository[RenderOperationInput], memory.work),
                              memory, execution, PROFILE).run_once(memory.claim_request())
        assert result is not None
        assert result.status == (OperationStatus.RETRY_WAIT if case == "missing_file"
                                 else OperationStatus.TERMINAL_FAILED)
        attempt = memory.work.list_attempts(operation.id)[0]
        assert attempt.reason_code == "input_missing"
        assert tuple(root.iterdir()) == (store.temp,)


@pytest.mark.parametrize("failure", ["lease", "conflict", "storage", "ambiguous"])
def test_worker_discards_both_published_files_only_on_definite_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    memory = MemoryRendering()
    operation = memory.service().request_render(memory.source.revision.id, PROFILE,
                                                RenderActor(EntityId.new()), EntityId.new())
    store = OutputStore(tmp_path)
    with store.temporary(".mp4") as video, store.temporary(".json") as sidecar:
        video.write_bytes(b"synthetic-video")
        sidecar.write_bytes(b"{}")
        content, manifest = store.publish(video), store.publish(sidecar)
    output = replace(output_for(operation.id, EntityId.new(), memory.source.revision.id),
        content_key=content.key, sha256=content.sha256, byte_size=content.byte_size,
        manifest_content_key=manifest.key, manifest_sha256=manifest.sha256)
    execution = LocalRenderExecution(Mock(), store, Mock(), Mock(), Mock(), FixedClock(NOW))
    monkeypatch.setattr(execution, "execute", Mock(return_value=output))
    error = {"lease": WorkExecutionLeaseLostError, "conflict": WorkExecutionConflictError,
             "storage": WorkExecutionStorageUnavailableError,
             "ambiguous": RenderResultCommitAmbiguousError}[failure]("synthetic")
    monkeypatch.setattr(memory, "apply_render_result", Mock(side_effect=error))
    if failure == "lease":
        monkeypatch.setattr(memory.work, "record_failure", Mock(side_effect=error))
        with pytest.raises(WorkExecutionLeaseLostError):
            RenderWorker(cast(WorkExecutionRepository[RenderOperationInput], memory.work),
                         memory, execution, PROFILE).run_once(memory.claim_request())
    else:
        RenderWorker(cast(WorkExecutionRepository[RenderOperationInput], memory.work),
                     memory, execution, PROFILE).run_once(memory.claim_request())
    assert (tmp_path / content.key).exists() == (failure == "ambiguous")
    assert (tmp_path / manifest.key).exists() == (failure == "ambiguous")
    assert list(store.temp.iterdir()) == []


@pytest.mark.parametrize(
    "phase", ["statement", "commit", "commit_rejected", "commit_deadlock", "commit_admin_shutdown"],
)
def test_result_repository_distinguishes_definite_and_ambiguous_storage_failure(
    monkeypatch: pytest.MonkeyPatch, phase: str,
) -> None:
    memory = MemoryRendering()
    memory.service().request_render(memory.source.revision.id, PROFILE,
                                   RenderActor(EntityId.new()), EntityId.new())
    claim = memory.work.claim_next(memory.claim_request())
    assert claim is not None
    output = output_for(claim.operation.id, claim.attempt.id, memory.source.revision.id)
    repo = PostgresRenderRepository("synthetic-unused")
    connection = Mock()
    connection.execute.return_value.fetchone.return_value = None
    if phase == "statement":
        connection.execute.side_effect = psycopg.OperationalError("synthetic")
    monkeypatch.setattr(repo, "_assert_active_claim", Mock())

    @contextmanager
    def connect() -> Generator[Any]:
        yield connection
        if phase == "commit_rejected":
            raise psycopg.errors.SerializationFailure("synthetic")
        if phase == "commit_deadlock":
            raise psycopg.errors.DeadlockDetected("synthetic")
        if phase == "commit_admin_shutdown":
            raise psycopg.errors.AdminShutdown("synthetic")
        raise psycopg.OperationalError("synthetic")

    monkeypatch.setattr(repo, "_connect", connect)
    with pytest.raises(WorkExecutionStorageUnavailableError) as failure:
        repo.apply_render_result(cast(OperationClaim[RenderOperationInput], claim), output)
    assert isinstance(failure.value, RenderResultCommitAmbiguousError) == (
        phase in {"commit", "commit_admin_shutdown"}
    )


@pytest.mark.parametrize("code,retryable", [
    ("media_asset_not_found", False), ("media_manifest_conflict", False),
    ("media_candidate_not_registered", False), ("media_source_not_configured", False),
    ("media_resource_unavailable", True),
])
def test_resolver_error_preserves_retry_classification_without_filesystem(
    code: str, retryable: bool,
) -> None:
    memory = MemoryRendering()
    operation = memory.service().request_render(memory.source.revision.id, PROFILE,
                                                RenderActor(EntityId.new()), EntityId.new())
    resolver = Mock(spec=KernelMediaPathResolver)
    resolver.resolve.side_effect = TranscriptionExecutionError(
        code, retryable=retryable, diagnostic_summary="synthetic private diagnostic")
    execution = LocalRenderExecution(Mock(), Mock(), Mock(), resolver, Mock(), FixedClock(NOW))
    result = RenderWorker(cast(WorkExecutionRepository[RenderOperationInput], memory.work),
                          memory, execution, PROFILE).run_once(memory.claim_request())
    resolver.resolve.assert_called_once()
    assert result is not None
    assert result.status == (OperationStatus.RETRY_WAIT if retryable
                             else OperationStatus.TERMINAL_FAILED)
    attempt = memory.work.list_attempts(operation.id)[0]
    assert attempt.reason_code == attempt.diagnostic_summary == "input_missing"
    assert attempt.retryable == retryable


@pytest.mark.parametrize("media_type", ["video/mp4", "image/png"])
def test_postgres_bound_packaging_order_revocation_and_nonvideo_request(
    render_postgres_dsn: str, approved_revision: AssemblyRevision, media_type: str,
) -> None:
    actor = EntityId.new()
    packaging = PackagingAssetService(PostgresPackagingAssetRepository(render_postgres_dsn),
                                      FixedClock(NOW))
    asset = packaging.register(operation_id=EntityId.new(), actor_id=actor,
        event_id=approved_revision.event_id, name="Synthetic intro",
        role=PackagingAssetRole.OPENING_BUMPER)
    reference = ExternalContent("synthetic-intro", "a" * 64, 10, media_type)
    packaging_revision = packaging.revise(operation_id=EntityId.new(), actor_id=actor,
        packaging_asset_id=asset.id, expected_revision=0, content=RevisionContent(reference))
    packaging.decide(operation_id=EntityId.new(), actor_id=actor, packaging_asset_id=asset.id,
        revision_number=1, expected_revision=1, action=ApprovalAction.APPROVE,
        reason="Synthetic approval")
    assemblies = SessionAssemblyService(PostgresSessionAssemblyRepository(render_postgres_dsn),
                                         FixedClock(NOW))
    template = assemblies.create_template(operation_id=EntityId.new(), actor_id=actor,
        event_id=approved_revision.event_id, template_key="packaged", expected_version=0,
        name="Synthetic packaged", slots=(
            AssemblySlot("intro", PlacementRole.OPENING_BUMPER, True),
            AssemblySlot("media", PlacementRole.SESSION_MEDIA, True)))
    revision = assemblies.propose(operation_id=EntityId.new(), actor_id=actor,
        session_id=approved_revision.session_id, template_id=template.id, expected_revision=1,
        expected_package_revision=approved_revision.package_revision)
    assert revision.bindings[0].packaging_revision_id == packaging_revision.id
    assemblies.decide(operation_id=EntityId.new(), actor_id=actor, session_id=revision.session_id,
        revision_number=2, expected_revision=2, expected_decision_count=0,
        action=AssemblyAction.APPROVE, reason="Synthetic approval")
    repo = PostgresRenderRepository(render_postgres_dsn)
    service = RenderingService(repo, FixedClock(NOW), "test-deployment")
    if media_type == "image/png":
        with pytest.raises(RenderError, match="render_input_not_video"):
            service.request_render(revision.id, PROFILE, RenderActor(actor), EntityId.new())
        assert repo.list_render_operations(revision.event_id, revision.session_id)[0] == ()
        return
    # Borrowed fixture transactions cannot change isolation; use the same real SQL planner.
    class FixtureRepository(PostgresRenderRepository):
        def pinned_plan(self) -> RenderPlan:
            with self._connect() as conn:
                return self._plan(conn, revision.id, PROFILE, lock=False)

    plan = FixtureRepository(render_postgres_dsn).pinned_plan()
    assert tuple(item.reference for item in plan.inputs) == (
        reference, *(CompletedMediaAssetContent(m.asset_id) for m in revision.membership))
    packaging.decide(operation_id=EntityId.new(), actor_id=actor, packaging_asset_id=asset.id,
        revision_number=1, expected_revision=1, action=ApprovalAction.REVOKE,
        reason="Synthetic revocation")
    with pytest.raises(RenderError) as failure:
        service.request_render(revision.id, PROFILE, RenderActor(actor), EntityId.new())
    assert failure.value.code == RenderReason.STALE
    assert repo.list_render_operations(revision.event_id, revision.session_id)[0] == ()
