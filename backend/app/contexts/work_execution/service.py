from __future__ import annotations

from dataclasses import dataclass, replace
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
    OperationInput,
    OperationStatus,
    TranscriptionOperationInput,
)
from .repository import WorkExecutionConflictError, WorkExecutionRepository


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
class TranscriptionWorker[InputT: OperationInput = OperationInput]:
    repository: WorkExecutionRepository[InputT]
    execution_port: TranscriptionExecutionPort

    def run_once(self, request: ClaimRequest) -> WorkerCycleResult:
        claimed = self.repository.claim_next(replace(request, operation_kind="transcription"))
        if claimed is None:
            return WorkerCycleResult(outcome=WorkerCycleOutcome.IDLE)
        active_claim = self.repository.mark_running(claimed)

        def renew_lease() -> None:
            nonlocal active_claim
            active_claim = self.repository.renew(
                active_claim,
                lease_duration=request.lease_duration,
            )

        def execute_attempt(
            operation_input: TranscriptionOperationInput,
        ) -> WorkerCycleResult | OperationFailure:
            execution_request = TranscriptionExecutionRequest(
                operation_id=active_claim.operation.id,
                attempt_id=active_claim.attempt.id,
                fence_generation=active_claim.attempt.fence_generation,
                work_key=active_claim.operation.work_key,
                input=operation_input,
            )
            try:
                result = self.execution_port.execute(execution_request, renew_lease)
            except TranscriptionExecutionError as exc:
                return OperationFailure(
                    reason_code=exc.reason_code,
                    retryable=exc.retryable,
                    diagnostic_summary=exc.diagnostic_summary,
                )

            if result.status is TranscriptEvidenceStatus.FAILED:
                assert result.failure_reason is not None
                return OperationFailure(
                    reason_code=result.failure_reason,
                    retryable=False,
                    diagnostic_summary="normalized provider failure",
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

        if not isinstance(active_claim.operation.input, TranscriptionOperationInput):
            raise WorkExecutionConflictError("transcription_worker_requires_transcription")
        try:
            outcome = execute_attempt(active_claim.operation.input)
        except TranscriptionExecutionError:
            # Only the execution port's typed errors were handled previously.
            raise
        except Exception:
            outcome = OperationFailure(
                reason_code="transcription_internal_error",
                retryable=True,
                diagnostic_summary="transcription_internal_error",
            )
        if isinstance(outcome, WorkerCycleResult):
            return outcome
        # Outside the catch: failure recording is fenced, and lease loss or storage
        # failure must propagate. Never claim a release that PostgreSQL refused.
        operation = self.repository.record_failure(active_claim, outcome)
        return WorkerCycleResult(
            outcome=(
                WorkerCycleOutcome.RETRY_SCHEDULED
                if operation.status is OperationStatus.RETRY_WAIT
                else WorkerCycleOutcome.TERMINAL_FAILED
            ),
            operation_id=operation.id,
            attempt_id=active_claim.attempt.id,
        )


__all__ = [
    "TranscriptionWorker",
    "WorkerCycleOutcome",
    "WorkerCycleResult",
]

