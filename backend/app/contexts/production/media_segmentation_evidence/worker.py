"""Provider-neutral segmentation on the shared claims, leases and fencing substrate."""
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import timedelta
from pathlib import Path
from typing import Protocol

from app.contexts.work_execution import (
    ClaimRequest,
    DurableOperation,
    MediaSegmentationOperationInput,
    OperationClaim,
    OperationFailure,
    WorkerHealth,
    WorkerPressure,
    WorkExecutionRepository,
    WorkExecutionStorageUnavailableError,
)
from app.shared.ids import EntityId
from app.shared.time import Clock

from .contracts import (
    CURRENT_SEGMENTATION_PROFILE,
    MediaSegmentationError,
    MediaSegmentationEvidence,
    SegmentationResult,
)


class SegmentationResultCommitAmbiguousError(WorkExecutionStorageUnavailableError):
    """Leave an uncertain commit for durable expiry reconciliation."""


class SegmentationResolver(Protocol):
    def resolve(self, input: MediaSegmentationOperationInput) -> Path: ...


class SegmentationInspector(Protocol):
    def inspect(self, path: Path, heartbeat: Callable[[], None]) -> SegmentationResult: ...


class SegmentationResultRepository(Protocol):
    def apply_result(self, claim: OperationClaim[MediaSegmentationOperationInput],
                     evidence: MediaSegmentationEvidence) -> MediaSegmentationEvidence: ...


@dataclass(slots=True)
class MediaSegmentationWorker:
    work: WorkExecutionRepository[MediaSegmentationOperationInput]
    results: SegmentationResultRepository
    resolver: SegmentationResolver
    inspector: SegmentationInspector
    clock: Clock
    concurrency: int = 1

    def run_once(
        self, request: ClaimRequest,
    ) -> DurableOperation[MediaSegmentationOperationInput] | None:
        claim = self.work.claim_next(replace(request, operation_kind="media_segmentation"))
        if claim is None:
            return None
        active = claim

        def heartbeat() -> None:
            nonlocal active
            active = self.work.renew(active, lease_duration=request.lease_duration)
            self.work.record_presence(request.worker_id, ttl=timedelta(minutes=2),
                maximum_concurrency=self.concurrency, health=WorkerHealth.AVAILABLE,
                pressure=WorkerPressure.NORMAL)

        try:
            active = self.work.mark_running(claim)
            value = active.operation.input
            profile = CURRENT_SEGMENTATION_PROFILE
            if (value.segmentation_profile_id, value.segmentation_profile_version) != (
                    profile.id, profile.version):
                raise MediaSegmentationError("render_identity_refused")
            result = self.inspector.inspect(self.resolver.resolve(value), heartbeat)
            self.results.apply_result(active, MediaSegmentationEvidence(
                EntityId.new(), active.operation.id, value.asset_id, value.manifest_id,
                value.manifest_version, active.attempt.id, result, self.clock.now()))
        except SegmentationResultCommitAmbiguousError:
            raise
        except WorkExecutionStorageUnavailableError:
            return self.work.record_failure(active, OperationFailure(
                "media_segmentation_storage_unavailable", True,
                "media_segmentation_storage_unavailable"))
        except Exception as exc:
            error = exc if isinstance(exc, MediaSegmentationError) else MediaSegmentationError(
                "media_segmentation_internal")
            return self.work.record_failure(active, OperationFailure(
                error.code, error.retryable, error.code))
        return self.work.get_operation(active.operation.id)
