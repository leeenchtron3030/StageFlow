from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta
from typing import TYPE_CHECKING

from app.shared.ids import EntityId

from .contracts import (
    ClaimRequest,
    DurableOperation,
    OperationAttempt,
    OperationClaim,
    OperationFailure,
    PendingOperation,
    Worker,
    WorkerCapability,
    WorkerHealth,
    WorkerPresence,
    WorkerPressure,
    WorkExecutionProjection,
)

if TYPE_CHECKING:
    from app.contexts.transcription_evidence import (
        PendingTranscriptEvidence,
        TranscriptEvidenceRevision,
    )


class WorkExecutionConflictError(RuntimeError):
    pass


class WorkExecutionNotFoundError(LookupError):
    pass


class WorkExecutionLeaseLostError(RuntimeError):
    pass


class WorkExecutionStorageUnavailableError(RuntimeError):
    pass


class WorkExecutionRepository(ABC):
    @abstractmethod
    def enqueue(self, pending: PendingOperation) -> DurableOperation: ...

    @abstractmethod
    def register_worker(self, worker: Worker) -> Worker: ...

    @abstractmethod
    def register_capability(self, capability: WorkerCapability) -> WorkerCapability: ...

    @abstractmethod
    def record_presence(
        self,
        worker_id: EntityId,
        *,
        ttl: timedelta,
        maximum_concurrency: int,
        health: WorkerHealth,
        pressure: WorkerPressure,
    ) -> WorkerPresence: ...

    @abstractmethod
    def claim_next(self, request: ClaimRequest) -> OperationClaim | None: ...

    @abstractmethod
    def mark_running(self, claim: OperationClaim) -> OperationClaim: ...

    @abstractmethod
    def renew(
        self,
        claim: OperationClaim,
        *,
        lease_duration: timedelta,
    ) -> OperationClaim: ...

    @abstractmethod
    def record_failure(
        self,
        claim: OperationClaim,
        failure: OperationFailure,
    ) -> DurableOperation: ...

    @abstractmethod
    def apply_transcript_result(
        self,
        claim: OperationClaim,
        pending: PendingTranscriptEvidence,
    ) -> TranscriptEvidenceRevision: ...

    @abstractmethod
    def reconcile_expired(self, *, limit: int = 100) -> tuple[DurableOperation, ...]: ...

    @abstractmethod
    def get_operation(self, operation_id: EntityId) -> DurableOperation: ...

    @abstractmethod
    def list_attempts(self, operation_id: EntityId) -> tuple[OperationAttempt, ...]: ...

    @abstractmethod
    def get_transcript_evidence(
        self,
        evidence_id: EntityId,
    ) -> TranscriptEvidenceRevision: ...

    @abstractmethod
    def status_projection(
        self,
        *,
        deployment_id: str,
        event_id: EntityId | None,
    ) -> WorkExecutionProjection: ...


__all__ = [
    "WorkExecutionConflictError",
    "WorkExecutionLeaseLostError",
    "WorkExecutionNotFoundError",
    "WorkExecutionRepository",
    "WorkExecutionStorageUnavailableError",
]

