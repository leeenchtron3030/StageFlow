"""Provider-neutral inspection orchestration on the shared lease substrate."""
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from app.contexts.work_execution import (
    ClaimRequest,
    DurableOperation,
    MediaTimingOperationInput,
    OperationClaim,
    OperationFailure,
    WorkExecutionRepository,
    WorkExecutionStorageUnavailableError,
)
from app.shared.time import Clock

from .contracts import (
    ApplyMediaTimingEvidenceRequest,
    MediaTimingEvidence,
    MediaTimingInspectionResult,
)
from .inspection import CURRENT_INSPECTION_PROFILE, MediaTimingError
from .repository import MediaTimingEvidenceStorageUnavailableError


class MediaTimingResultCommitAmbiguousError(WorkExecutionStorageUnavailableError):
    """The result may have committed; leave the lease for expiry reconciliation."""


class TimingResolver(Protocol):
    def resolve(self, input: MediaTimingOperationInput) -> Path: ...


class TimingInspector(Protocol):
    def inspect(self, path: Path) -> MediaTimingInspectionResult: ...


class TimingResultRepository(Protocol):
    def apply_result(self, claim: OperationClaim[MediaTimingOperationInput],
                     request: ApplyMediaTimingEvidenceRequest) -> MediaTimingEvidence: ...


@dataclass(slots=True)
class MediaTimingWorker:
    work: WorkExecutionRepository[MediaTimingOperationInput]
    results: TimingResultRepository
    resolver: TimingResolver
    inspector: TimingInspector
    clock: Clock

    def run_once(self, request: ClaimRequest) -> DurableOperation[MediaTimingOperationInput] | None:
        claim = self.work.claim_next(replace(request, operation_kind="media_timing"))
        if claim is None:
            return None
        active = claim
        try:
            active = self.work.mark_running(claim)
            value = active.operation.input
            profile = CURRENT_INSPECTION_PROFILE
            if (value.inspection_profile_id, value.inspection_profile_version) != (
                    profile.id, profile.version):
                raise MediaTimingError("media_timing_tool_refused")
            path = self.resolver.resolve(value)
            result = self.inspector.inspect(path)
            self.results.apply_result(active, ApplyMediaTimingEvidenceRequest(
                active.operation.id, value.asset_id, value.manifest_id,
                value.manifest_version, self.clock.now(), result,
            ))
        except MediaTimingResultCommitAmbiguousError:
            # Do not finalize an attempt whose result may already be durable.
            raise
        except (MediaTimingEvidenceStorageUnavailableError, WorkExecutionStorageUnavailableError):
            return self.work.record_failure(active, OperationFailure(
                "media_timing_storage_unavailable", True, "media_timing_storage_unavailable",
            ))
        except Exception as exc:
            error = exc if isinstance(exc, MediaTimingError) else MediaTimingError(
                "media_timing_internal")
            return self.work.record_failure(active, OperationFailure(
                error.code, error.retryable, error.code,
            ))
        return self.work.get_operation(active.operation.id)
