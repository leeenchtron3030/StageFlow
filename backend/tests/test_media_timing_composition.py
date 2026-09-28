from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import pytest
from test_media_timing_inspection import setup_worker
from test_render_work_execution import NOW, MutableClock

from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.production.event_mode_kernel import AssociationStatus
from app.contexts.production.media_timing_evidence.enqueue import (
    MediaTimingEnqueue,
    RegisteredTimingAsset,
)
from app.contexts.production.media_timing_evidence.worker import MediaTimingWorker
from app.contexts.transcription_evidence import TranscriptionExecutionError
from app.contexts.work_execution import (
    MediaTimingOperationInput,
    OperationStatus,
    TranscriptionOperationApplication,
    WorkExecutionRepository,
    WorkExecutionStorageUnavailableError,
)
from app.contexts.work_execution.memory import InMemoryWorkExecutionRepository
from app.demo import media_timing_worker, service
from app.demo.media_timing_worker import TimingPathResolver
from app.demo.service import DemoApplication, ReconcileMediaRequest
from app.infrastructure.postgres import PostgresWorkExecutionRepository
from app.infrastructure.transcription import KernelMediaPathResolver
from app.shared.ids import EntityId
from app.shared.time import FixedClock


@pytest.mark.parametrize("enabled,asset_count", [
    (False, 2), (True, 2), (True, 0),
])
def test_enabled_reconciliation_enqueues_assets_lacking_a_timing_operation(
    monkeypatch: pytest.MonkeyPatch, enabled: bool, asset_count: int,
) -> None:
    components = Mock(spec=KernelComponents)
    components.event_key = "synthetic"
    components.kernel = SimpleNamespace(clock=FixedClock(NOW))
    components.configuration = SimpleNamespace(postgres_dsn="unused", deployment=SimpleNamespace(
        local_media_timing=None if not enabled else SimpleNamespace(enabled=True),
        local_transcription=object(), deployment_id="synthetic",
    ))
    components.repository.get_event_by_key.return_value = SimpleNamespace(id=EntityId.new())
    assets = tuple(RegisteredTimingAsset(EntityId.new(), EntityId.new(), NOW)
                   for _ in range(asset_count))
    components.repository.list_recent_media.return_value = ()
    components.run_media_cycle.return_value = SimpleNamespace(
        candidates_seen=0, assets_registered=0)
    work = Mock()
    work.list_operations.return_value = ()
    timing = Mock()
    timing.assets_without_operation.return_value = assets
    monkeypatch.setattr(service, "PostgresMediaTimingWorkRepository", Mock(return_value=timing))
    app = DemoApplication(
        cast(KernelComponents, components), cast(TranscriptionOperationApplication, Mock()),
        cast(PostgresWorkExecutionRepository, work),
    )
    result = app.reconcile_media(ReconcileMediaRequest("synthetic", NOW))
    assert timing.enqueue.call_count == (asset_count if enabled else 0)
    assert result.operations == () and not result.enqueue_failures
    if enabled:
        timing.assets_without_operation.assert_called_once_with(
            components.repository.get_event_by_key.return_value.id, limit=100)
        # Association is deliberately not required to gather advisory evidence.
        assert [(call.args[0].request.input.asset_id, call.args[0].request.input.manifest_id)
                for call in timing.enqueue.call_args_list] == [
                    (asset.asset_id, asset.manifest_id) for asset in assets]
    else:
        timing.assets_without_operation.assert_not_called()
        timing.enqueue.assert_not_called()


def test_kernel_resolution_failure_maps_to_input_missing() -> None:
    resolver = Mock(spec=KernelMediaPathResolver)
    resolver.resolve.side_effect = TranscriptionExecutionError(
        "media_resource_unavailable", retryable=True, diagnostic_summary="unavailable",
    )
    from app.contexts.production.media_timing_evidence.inspection import MediaTimingError

    with pytest.raises(MediaTimingError, match="input_missing"):
        TimingPathResolver(cast(KernelMediaPathResolver, resolver)).resolve(
            MediaTimingOperationInput(EntityId.new(), EntityId.new(), "1.0", "profile", "1"),
        )


def test_demo_timing_enqueue_storage_failure_still_enqueues_transcription(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    components = Mock(spec=KernelComponents)
    components.event_key = "synthetic"
    components.kernel = SimpleNamespace(clock=FixedClock(NOW))
    components.configuration = SimpleNamespace(postgres_dsn="unused", deployment=SimpleNamespace(
        local_media_timing=SimpleNamespace(enabled=True), deployment_id="synthetic",
        local_transcription=SimpleNamespace(execution_profile_id="synthetic",
                                            execution_profile_version="1"),
    ))
    components.repository.get_event_by_key.return_value = SimpleNamespace(id=EntityId.new())
    asset = SimpleNamespace(id=EntityId.new(), manifest_id=EntityId.new(), registered_at=NOW)
    candidate_id = EntityId.new()
    components.repository.get_asset.return_value = asset
    components.repository.get_candidate.return_value = SimpleNamespace(
        proposed_asset_id=asset.id, source_reference="synthetic.mp4")
    components.repository.list_recent_media.return_value = (SimpleNamespace(
        asset_id=asset.id, candidate_id=candidate_id, session_id=EntityId.new(),
        association_status=AssociationStatus.ASSOCIATED),)
    components.run_media_cycle.return_value = SimpleNamespace(
        candidates_seen=1, assets_registered=1,
        candidate_results=(SimpleNamespace(outcome="registered", candidate_id=candidate_id),))
    repository, work, timing = Mock(), Mock(), Mock()
    repository.list_operations.return_value = ()
    timing.assets_without_operation.return_value = (
        RegisteredTimingAsset(asset.id, asset.manifest_id, NOW),)
    timing.enqueue.side_effect = WorkExecutionStorageUnavailableError("synthetic")
    monkeypatch.setattr(service, "PostgresMediaTimingWorkRepository", Mock(return_value=timing))
    app = DemoApplication(cast(KernelComponents, components),
        cast(TranscriptionOperationApplication, work),
        cast(PostgresWorkExecutionRepository, repository))
    result = app.reconcile_media(ReconcileMediaRequest("synthetic", NOW))
    timing.enqueue.assert_called_once()
    work.enqueue.assert_called_once()
    assert work.enqueue.call_args.args[0].input.asset_id == asset.id
    assert result.enqueue_failures == ("media_timing_enqueue_failed",)
    assert result.operations == (work.enqueue.return_value,) and result.operations_enqueued == 1


@pytest.mark.parametrize("code,retryable", [
    ("media_asset_not_found", False), ("media_manifest_conflict", False),
    ("media_candidate_not_registered", False), ("media_source_not_configured", False),
    ("media_resource_unavailable", True),
])
def test_timing_resolver_preserves_retry_classification(code: str, retryable: bool) -> None:
    memory = InMemoryWorkExecutionRepository(
        MutableClock(), input_types=(MediaTimingOperationInput,))
    repo = cast(WorkExecutionRepository[MediaTimingOperationInput], memory)
    event = EntityId.new()
    operation = MediaTimingEnqueue(repo, "test-deployment", FixedClock(NOW)).enqueue(
        event, RegisteredTimingAsset(EntityId.new(), EntityId.new(), NOW))
    kernel = Mock(spec=KernelMediaPathResolver)
    kernel.resolve.side_effect = TranscriptionExecutionError(
        code, retryable=retryable, diagnostic_summary="secret=/private")
    inspector, results = Mock(), Mock()
    worker = MediaTimingWorker(repo, results, TimingPathResolver(kernel),
                               inspector, FixedClock(NOW))
    outcome = worker.run_once(setup_worker(repo, event))
    assert outcome is not None
    assert outcome.status is (OperationStatus.RETRY_WAIT if retryable
                              else OperationStatus.TERMINAL_FAILED)
    assert outcome.current_attempt_id is None and outcome.lease_expires_at is None
    attempt = repo.list_attempts(operation.id)[0]
    assert attempt.reason_code == attempt.diagnostic_summary == "input_missing"
    assert attempt.retryable is retryable
    inspector.inspect.assert_not_called()
    results.apply_result.assert_not_called()


@pytest.mark.parametrize("concurrency", ["0", "9"])
def test_worker_cli_refuses_unbounded_concurrency(concurrency: str,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    load = Mock()
    monkeypatch.setattr(media_timing_worker, "load_kernel_components_from_environment", load)
    assert media_timing_worker.main(["--once", "--concurrency", concurrency]) == 1
    load.assert_not_called()
