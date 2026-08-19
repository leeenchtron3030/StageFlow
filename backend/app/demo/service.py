from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid5

from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.production.event_mode_kernel.contracts import AssociationStatus
from app.contexts.production.event_mode_kernel.repository import KernelNotFoundError
from app.contexts.work_execution import (
    DurableOperation,
    EnqueueTranscriptionOperation,
    TranscriptionOperationApplication,
    TranscriptionOperationInput,
)
from app.infrastructure.postgres import PostgresWorkExecutionRepository
from app.shared.ids import EntityId
from app.shared.time import require_aware_datetime


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


@dataclass(frozen=True, slots=True)
class DemoApplication:
    components: KernelComponents
    work: TranscriptionOperationApplication

    @classmethod
    def from_components(cls, components: KernelComponents) -> DemoApplication:
        return cls(
            components=components,
            work=TranscriptionOperationApplication(
                PostgresWorkExecutionRepository(
                    components.configuration.postgres_dsn
                )
            ),
        )

    def process_transcription(
        self, request: ProcessTranscriptionRequest
    ) -> ProcessTranscriptionResult:
        event = self.components.repository.get_event_by_key(self.components.event_key)
        if event is None:
            raise KernelNotFoundError("event_not_found")
        session = self.components.repository.get_session(request.session_id)
        if session is None or session.event_id != event.id:
            raise KernelNotFoundError("session_not_found")

        cycle = self.components.run_media_cycle(
            event_id=event.id,
            scope="demo_process_transcription",
        )
        transcription = self.components.configuration.deployment.local_transcription
        if transcription is None:
            raise RuntimeError("local_transcription_not_configured")

        operations: list[DurableOperation] = []
        namespace = UUID(request.operation_id.value)
        for media in self.components.repository.list_recent_media(event.id):
            if (
                media.asset_id is None
                or media.session_id != request.session_id
                or media.association_status is not AssociationStatus.ASSOCIATED
            ):
                continue
            asset = self.components.repository.get_asset(media.asset_id)
            candidate = self.components.repository.get_candidate(media.candidate_id)
            if asset is None or candidate is None:
                continue
            asset_format = Path(candidate.source_reference).suffix.casefold().lstrip(".")
            if not asset_format:
                raise RuntimeError("registered_media_format_unavailable")
            operation_id = EntityId(
                str(uuid5(namespace, f"transcription:{asset.id.value}"))
            )
            operations.append(
                self.work.enqueue(
                    EnqueueTranscriptionOperation(
                        operation_id=operation_id,
                        idempotency_key=(
                            f"demo-process:{request.session_id.value}:{asset.id.value}"
                        ),
                        deployment_id=(
                            self.components.configuration.deployment.deployment_id
                        ),
                        event_id=event.id,
                        input=TranscriptionOperationInput(
                            asset_id=asset.id,
                            manifest_id=asset.manifest_id,
                            manifest_version="1.0",
                            asset_format=asset_format,
                            execution_profile_id=(
                                transcription.execution_profile_id
                            ),
                            execution_profile_version=(
                                transcription.execution_profile_version
                            ),
                            requested_language=None,
                            request_word_timing=True,
                            request_speaker_labels=False,
                            requires_cloud=False,
                        ),
                        priority=0,
                        eligible_at=request.requested_at,
                        max_attempts=3,
                        retry_delay=timedelta(seconds=30),
                        required_for_event=False,
                        requested_at=request.requested_at,
                    )
                )
            )
        return ProcessTranscriptionResult(
            command_operation_id=request.operation_id,
            candidates_seen=cycle.candidates_seen,
            assets_registered=cycle.assets_registered,
            operations=tuple(operations),
        )


__all__ = [
    "DemoApplication",
    "ProcessTranscriptionRequest",
    "ProcessTranscriptionResult",
]
