from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.production.event_mode_kernel.contracts import AssociationStatus
from app.contexts.production.event_mode_kernel.repository import KernelNotFoundError
from app.contexts.work_execution import (
    DurableOperation,
    EnqueueTranscriptionOperation,
    TranscriptionOperationApplication,
    TranscriptionOperationInput,
    WorkExecutionConflictError,
    WorkExecutionStorageUnavailableError,
)
from app.infrastructure.postgres import PostgresWorkExecutionRepository
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
        transcription = self.components.configuration.deployment.local_transcription
        if transcription is None:
            raise RuntimeError("local_transcription_not_configured")

        existing = self.repository.list_operations(
            deployment_id=self.components.configuration.deployment.deployment_id,
            event_id=event.id,
            limit=500,
        )
        by_subject = {
            (
                operation.input.asset_id,
                operation.input.manifest_id,
                operation.input.execution_profile_id,
                operation.input.execution_profile_version,
            ): operation
            for operation in existing
        }
        operations: list[DurableOperation] = []
        failures: list[str] = []
        enqueued = 0
        seen_assets: set[EntityId] = set()

        for media in self.components.repository.list_recent_media(event.id, limit=500):
            if (
                media.asset_id is None
                or media.asset_id in seen_assets
                or media.session_id is None
                or media.association_status is not AssociationStatus.ASSOCIATED
                or (
                    request.session_id is not None
                    and media.session_id != request.session_id
                )
            ):
                continue
            seen_assets.add(media.asset_id)
            asset = self.components.repository.get_asset(media.asset_id)
            candidate = self.components.repository.get_candidate(media.candidate_id)
            if asset is None or candidate is None:
                failures.append("registered_media_facts_unavailable")
                continue
            subject = (
                asset.id,
                asset.manifest_id,
                transcription.execution_profile_id,
                transcription.execution_profile_version,
            )
            prior = by_subject.get(subject)
            if prior is not None:
                operations.append(prior)
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
                            f"{event.id.value}:{media.session_id.value}:{asset.id.value}:"
                            f"{asset.manifest_id.value}:"
                            f"{transcription.execution_profile_id}:"
                            f"{transcription.execution_profile_version}"
                        ),
                    )
                )
            )
            enqueue = EnqueueTranscriptionOperation(
                operation_id=operation_id,
                idempotency_key=(
                    f"demo-process:{media.session_id.value}:{asset.id.value}"
                ),
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
            by_subject[subject] = operation
            enqueued += 1

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
