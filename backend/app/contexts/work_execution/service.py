from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.contexts.transcription_evidence import (
    TranscriptEvidenceRevision,
    TranscriptEvidenceStatus,
    TranscriptionExecutionError,
    TranscriptionExecutionPort,
    TranscriptionExecutionRequest,
    prepare_transcript_evidence,
)
from app.shared.ids import EntityId

from .contracts import (
    ClaimRequest,
    OperationFailure,
    OperationStatus,
)
from .repository import WorkExecutionRepository


class WorkerCycleOutcome(StrEnum):
    IDLE = "idle"
    SUCCEEDED = "succeeded"
    RETRY_SCHEDULED = "retry_scheduled"
    TERMINAL_FAILED = "terminal_failed"


@dataclass(frozen=True, slots=True)
class WorkerCycleResult:
    outcome: WorkerCycleOutcome
    operation_id: EntityId | None = None
    attempt_id: EntityId | None = None
    evidence_id: EntityId | None = None


@dataclass(slots=True)
class TranscriptionWorker:
    repository: WorkExecutionRepository
    execution_port: TranscriptionExecutionPort

    def run_once(self, request: ClaimRequest) -> WorkerCycleResult:
        claimed = self.repository.claim_next(request)
        if claimed is None:
            return WorkerCycleResult(outcome=WorkerCycleOutcome.IDLE)
        active_claim = self.repository.mark_running(claimed)

        def renew_lease() -> None:
            nonlocal active_claim
            active_claim = self.repository.renew(
                active_claim,
                lease_duration=request.lease_duration,
            )

        execution_request = TranscriptionExecutionRequest(
            operation_id=active_claim.operation.id,
            attempt_id=active_claim.attempt.id,
            fence_generation=active_claim.attempt.fence_generation,
            work_key=active_claim.operation.work_key,
            input=active_claim.operation.input,
        )
        try:
            result = self.execution_port.execute(execution_request, renew_lease)
        except TranscriptionExecutionError as exc:
            operation = self.repository.record_failure(
                active_claim,
                OperationFailure(
                    reason_code=exc.reason_code,
                    retryable=exc.retryable,
                    diagnostic_summary=exc.diagnostic_summary,
                ),
            )
            return WorkerCycleResult(
                outcome=(
                    WorkerCycleOutcome.RETRY_SCHEDULED
                    if operation.status is OperationStatus.RETRY_WAIT
                    else WorkerCycleOutcome.TERMINAL_FAILED
                ),
                operation_id=operation.id,
                attempt_id=active_claim.attempt.id,
            )

        if result.status is TranscriptEvidenceStatus.FAILED:
            assert result.failure_reason is not None
            operation = self.repository.record_failure(
                active_claim,
                OperationFailure(
                    reason_code=result.failure_reason,
                    retryable=False,
                    diagnostic_summary="normalized provider failure",
                ),
            )
            return WorkerCycleResult(
                outcome=WorkerCycleOutcome.TERMINAL_FAILED,
                operation_id=operation.id,
                attempt_id=active_claim.attempt.id,
            )

        evidence: TranscriptEvidenceRevision = self.repository.apply_transcript_result(
            active_claim,
            prepare_transcript_evidence(active_claim, result),
        )
        return WorkerCycleResult(
            outcome=WorkerCycleOutcome.SUCCEEDED,
            operation_id=active_claim.operation.id,
            attempt_id=active_claim.attempt.id,
            evidence_id=evidence.id,
        )


__all__ = [
    "TranscriptionWorker",
    "WorkerCycleOutcome",
    "WorkerCycleResult",
]

