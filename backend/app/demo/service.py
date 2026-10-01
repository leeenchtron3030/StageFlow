from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.production.event_mode_kernel.repository import KernelNotFoundError
from app.contexts.production.media_segmentation_evidence.enqueue import MediaSegmentationEnqueue
from app.contexts.production.media_timing_evidence.enqueue import (
    MediaTimingEnqueue,
)
from app.contexts.work_execution import (
    DurableOperation,
    EnqueueTranscriptionOperation,
    TranscriptionOperationApplication,
    TranscriptionOperationInput,
    WorkExecutionConflictError,
    WorkExecutionStorageUnavailableError,
)
from app.infrastructure.postgres import PostgresWorkExecutionRepository
from app.infrastructure.postgres.media_segmentation_repository import (
    PostgresMediaSegmentationRepository,
)
from app.infrastructure.postgres.media_timing_work_repository import (
    PostgresMediaTimingWorkRepository,
)
from app.shared.ids import EntityId
from app.shared.time import require_aware_datetime


@dataclass(frozen=True, slots=True)
class ReconcileMediaRequest:
    scope: str
    requested_at: datetime
    session_id: EntityId | None = None

    def __post_init__(self) -> None:
        if not self.scope.strip():
            raise ValueError("scope must not be empty")
        require_aware_datetime(self.requested_at, "requested_at")


@dataclass(frozen=True, slots=True)
class MediaTranscriptionReconciliation:
    scope: str
    candidates_seen: int
    assets_registered: int
    operations: tuple[DurableOperation, ...]
    operations_enqueued: int
    enqueue_failures: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProcessTranscriptionRequest:
    operation_id: EntityId
    session_id: EntityId
    requested_at: datetime

    def __post_init__(self) -> None:
        require_aware_datetime(self.requested_at, "requested_at")


@dataclass(frozen=True, slots=True)
class ProcessTranscriptionResult:
    command_operation_id: EntityId
    candidates_seen: int
    assets_registered: int
    operations: tuple[DurableOperation, ...]
    operations_enqueued: int = 0
    enqueue_failures: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DemoApplication:
    components: KernelComponents
    work: TranscriptionOperationApplication
    repository: PostgresWorkExecutionRepository

    @classmethod
    def from_components(cls, components: KernelComponents) -> DemoApplication:
        repository = PostgresWorkExecutionRepository(
            components.configuration.postgres_dsn
        )
        return cls(
            components=components,
            work=TranscriptionOperationApplication(repository),
            repository=repository,
        )

    def reconcile_media(
        self, request: ReconcileMediaRequest
    ) -> MediaTranscriptionReconciliation:
        event = self.components.repository.get_event_by_key(self.components.event_key)
        if event is None:
            raise KernelNotFoundError("event_not_found")
        if request.session_id is not None:
            session = self.components.repository.get_session(request.session_id)
            if session is None or session.event_id != event.id:
                raise KernelNotFoundError("session_not_found")

        cycle = self.components.run_media_cycle(
            event_id=event.id,
            scope=request.scope,
        )
        local_timing = self.components.configuration.deployment.local_media_timing
        timing_failures: list[str] = []
        if local_timing is not None and local_timing.enabled:
            timing_repository = PostgresMediaTimingWorkRepository(
                self.components.configuration.postgres_dsn)
            timing = MediaTimingEnqueue(
                timing_repository,
                self.components.configuration.deployment.deployment_id,
                self.components.kernel.clock,
            )
            try:
                assets = timing_repository.assets_without_operation(event.id, limit=100)
            except (ValueError, RuntimeError):
                timing_failures.append("media_timing_enqueue_failed")
            else:
                for asset in assets:
                    try:
                        timing.enqueue(event.id, asset)
                    except (ValueError, RuntimeError):
                        timing_failures.append("media_timing_enqueue_failed")
        local_segmentation = getattr(
            self.components.configuration.deployment, "local_media_segmentation", None)
        if local_segmentation is not None and local_segmentation.enabled:
            segmentation_repository = PostgresMediaSegmentationRepository(
                self.components.configuration.postgres_dsn)
            segmentation = MediaSegmentationEnqueue(segmentation_repository,
                self.components.configuration.deployment.deployment_id,
                self.components.kernel.clock)
            try:
                segmentation_assets = segmentation_repository.assets_without_operation(
                    event.id, limit=100)
            except (ValueError, RuntimeError):
                timing_failures.append("media_segmentation_enqueue_failed")
            else:
                for segmentation_asset in segmentation_assets:
                    try:
                        segmentation.enqueue(event.id, segmentation_asset)
                    except (ValueError, RuntimeError):
                        timing_failures.append("media_segmentation_enqueue_failed")
        transcription = self.components.configuration.deployment.local_transcription
        if transcription is None:
            raise RuntimeError("local_transcription_not_configured")

        targets = self.repository.list_transcription_targets(
            deployment_id=self.components.configuration.deployment.deployment_id,
            event_id=event.id,
            execution_profile_id=transcription.execution_profile_id,
            execution_profile_version=transcription.execution_profile_version,
            session_id=request.session_id,
            after=(self.components.transcription_scan_after
                   if request.session_id is None else None),
            limit=500,
        )
        operations: list[DurableOperation] = []
        failures: list[str] = timing_failures
        enqueued = 0

        for asset_id, prior in targets:
            if prior is not None:
                operations.append(prior)
                continue
            asset = self.components.repository.get_asset(asset_id)
            candidate = (
                None if asset is None
                else self.components.repository.get_candidate(asset.candidate_id)
            )
            if asset is None or candidate is None:
                failures.append("registered_media_facts_unavailable")
                continue
            asset_format = Path(candidate.source_reference).suffix.casefold().lstrip(".")
            if not asset_format:
                failures.append("registered_media_format_unavailable")
                continue
            operation_id = EntityId(
                str(
                    uuid5(
                        NAMESPACE_URL,
                        (
                            "stageflow:demo-transcription:"
                            f"{self.components.configuration.deployment.deployment_id}:"
                            f"{event.id.value}:{asset.id.value}:"
                            f"{asset.manifest_id.value}:1.0:"
                            f"{transcription.execution_profile_id}:"
                            f"{transcription.execution_profile_version}"
                        ),
                    )
                )
            )
            enqueue = EnqueueTranscriptionOperation(
                operation_id=operation_id,
                idempotency_key=f"demo-process:{operation_id.value}",
                deployment_id=self.components.configuration.deployment.deployment_id,
                event_id=event.id,
                input=TranscriptionOperationInput(
                    asset_id=asset.id,
                    manifest_id=asset.manifest_id,
                    manifest_version="1.0",
                    asset_format=asset_format,
                    execution_profile_id=transcription.execution_profile_id,
                    execution_profile_version=transcription.execution_profile_version,
                    requested_language=None,
                    request_word_timing=True,
                    request_speaker_labels=False,
                    requires_cloud=False,
                ),
                priority=0,
                eligible_at=asset.registered_at,
                max_attempts=3,
                retry_delay=timedelta(seconds=30),
                required_for_event=False,
                requested_at=asset.registered_at,
            )
            try:
                operation = self.work.enqueue(enqueue)
            except WorkExecutionStorageUnavailableError:
                raise
            except (WorkExecutionConflictError, ValueError, RuntimeError):
                failures.append("transcription_enqueue_failed")
                continue
            operations.append(operation)
            enqueued += 1

        if request.session_id is None:
            # Move past persistent per-asset failures as well as successful enqueues.
            # Wrap at the end; restart may safely rescan because operations are durable.
            self.components.transcription_scan_after = (
                targets[-1][0] if len(targets) == 500 else None
            )
        return MediaTranscriptionReconciliation(
            scope=request.scope,
            candidates_seen=cycle.candidates_seen,
            assets_registered=cycle.assets_registered,
            operations=tuple(operations),
            operations_enqueued=enqueued,
            enqueue_failures=tuple(failures[:100]),
        )

    def process_transcription(
        self, request: ProcessTranscriptionRequest
    ) -> ProcessTranscriptionResult:
        result = self.reconcile_media(
            ReconcileMediaRequest(
                scope="demo_process_transcription",
                requested_at=request.requested_at,
                session_id=request.session_id,
            )
        )
        return ProcessTranscriptionResult(
            command_operation_id=request.operation_id,
            candidates_seen=result.candidates_seen,
            assets_registered=result.assets_registered,
            operations=result.operations,
            operations_enqueued=result.operations_enqueued,
            enqueue_failures=result.enqueue_failures,
        )


__all__ = [
    "DemoApplication",
    "MediaTranscriptionReconciliation",
    "ProcessTranscriptionRequest",
    "ProcessTranscriptionResult",
    "ReconcileMediaRequest",
]
