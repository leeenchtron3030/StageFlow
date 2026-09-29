"""Evidence repository contract and non-durable test double; never a runtime fallback."""
from dataclasses import replace
from typing import Protocol, cast

from app.contexts.work_execution import (
    AttemptOutcome,
    DurableOperation,
    MediaSegmentationOperationInput,
    OperationClaim,
    OperationStatus,
    WorkExecutionConflictError,
)
from app.contexts.work_execution.memory import InMemoryWorkExecutionRepository
from app.shared.ids import EntityId
from app.shared.time import Clock

from .contracts import MediaSegmentationEvidence
from .enqueue import RegisteredSegmentationAsset


def check_result_identity(claim: OperationClaim[MediaSegmentationOperationInput],
                          evidence: MediaSegmentationEvidence) -> None:
    value = claim.operation.input
    if (evidence.operation_id != claim.operation.id or evidence.asset_id != value.asset_id
            or evidence.manifest_id != value.manifest_id
            or evidence.manifest_version != value.manifest_version
            or evidence.producing_attempt_id != claim.attempt.id
            or evidence.result.profile.id != value.segmentation_profile_id
            or evidence.result.profile.version != value.segmentation_profile_version):
        raise WorkExecutionConflictError("media_segmentation_result_identity_conflict")


class SegmentationEvidenceReader(Protocol):
    def evidence_page(self, *, asset_id: EntityId | None = None,
                      session_id: EntityId | None = None, limit: int = 5,
                      after: EntityId | None = None
                      ) -> tuple[tuple[MediaSegmentationEvidence, ...], EntityId | None]: ...


def check_page(asset_id: EntityId | None, session_id: EntityId | None, limit: int) -> None:
    if (asset_id is None) == (session_id is None) or not 1 <= limit <= 10:
        raise ValueError("media_segmentation_page_invalid")


class InMemoryMediaSegmentationRepository(InMemoryWorkExecutionRepository):
    def __init__(self, clock: Clock) -> None:
        super().__init__(clock, input_types=(MediaSegmentationOperationInput,))
        self.segmentation_evidence: dict[EntityId, MediaSegmentationEvidence] = {}
        self.assets: dict[EntityId, tuple[RegisteredSegmentationAsset, ...]] = {}
        self.session_assets: dict[EntityId, tuple[EntityId, ...]] = {}

    def apply_result(self, claim: OperationClaim[MediaSegmentationOperationInput],
                     evidence: MediaSegmentationEvidence) -> MediaSegmentationEvidence:
        check_result_identity(claim, evidence)
        with self._lock:
            operation = self._active(claim)
            if evidence.id in self.segmentation_evidence:
                raise WorkExecutionConflictError("media_segmentation_evidence_identity_conflict")
            if any(old.operation_id == evidence.operation_id
                   for old in self.segmentation_evidence.values()):
                raise WorkExecutionConflictError("media_segmentation_result_already_applied")
            operation = self._finalize(operation, OperationStatus.SUCCEEDED,
                AttemptOutcome.SUCCEEDED, "result_applied", "media_segmentation_result_applied",
                False, operation.retry_delay)
            self.operations[operation.id] = replace(operation,
                terminal_result_type="media_segmentation_evidence",
                terminal_result_media_segmentation_evidence_id=evidence.id)
            self.segmentation_evidence[evidence.id] = evidence
            return evidence

    def page(
        self, event_id: EntityId, *, limit: int = 50, after: EntityId | None = None,
    ) -> tuple[tuple[DurableOperation[MediaSegmentationOperationInput], ...], EntityId | None]:
        if not 1 <= limit <= 100:
            raise ValueError("media_segmentation_limit_out_of_bounds")
        items = sorted((cast(DurableOperation[MediaSegmentationOperationInput], item)
                        for item in self.operations.values() if item.event_id == event_id
                        and (after is None or item.id.value > after.value)),
                       key=lambda item: item.id.value)
        return tuple(items[:limit]), items[limit-1].id if len(items) > limit else None

    def asset_page(self, event_id: EntityId, *, limit: int = 50,
                   after: EntityId | None = None
                   ) -> tuple[tuple[RegisteredSegmentationAsset, ...], EntityId | None]:
        if not 1 <= limit <= 100:
            raise ValueError("media_segmentation_limit_out_of_bounds")
        items = sorted((asset for asset in self.assets.get(event_id, ())
                        if after is None or asset.asset_id.value > after.value),
                       key=lambda asset: asset.asset_id.value)
        return tuple(items[:limit]), items[limit-1].asset_id if len(items) > limit else None

    def assets_without_operation(self, event_id: EntityId, *, limit: int = 100
                                 ) -> tuple[RegisteredSegmentationAsset, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("media_segmentation_limit_out_of_bounds")
        existing = {op.input.asset_id for op in self.operations.values()
                    if isinstance(op.input, MediaSegmentationOperationInput)
                    and op.event_id == event_id}
        return tuple(sorted((asset for asset in self.assets.get(event_id, ())
                             if asset.asset_id not in existing),
                            key=lambda asset: asset.asset_id.value)[:limit])

    def evidence_page(self, *, asset_id: EntityId | None = None,
                      session_id: EntityId | None = None, limit: int = 5,
                      after: EntityId | None = None
                      ) -> tuple[tuple[MediaSegmentationEvidence, ...], EntityId | None]:
        check_page(asset_id, session_id, limit)
        assets = ((asset_id,) if asset_id is not None else
                  self.session_assets.get(session_id, ()) if session_id is not None else ())
        items = sorted((item for item in self.segmentation_evidence.values()
                        if item.asset_id in assets
                        and (after is None or item.id.value > after.value)),
                       key=lambda item: item.id.value)
        return tuple(items[:limit]), items[limit-1].id if len(items) > limit else None
