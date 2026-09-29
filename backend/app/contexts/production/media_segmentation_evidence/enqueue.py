"""Idempotent asset inspection requests; the explicit batch command is human-only."""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from app.contexts.work_execution import (
    DurableOperation,
    MediaSegmentationOperationInput,
    WorkExecutionRepository,
)
from app.contexts.work_execution.application import pending_media_segmentation_operation
from app.contexts.work_execution.contracts import EnqueueOperation
from app.shared.human_commands import human_command_digest
from app.shared.ids import EntityId
from app.shared.time import Clock, require_aware_datetime

from .contracts import CURRENT_SEGMENTATION_PROFILE


@dataclass(frozen=True, slots=True)
class RegisteredSegmentationAsset:
    asset_id: EntityId
    manifest_id: EntityId
    registered_at: datetime

    def __post_init__(self) -> None:
        require_aware_datetime(self.registered_at, "registered_at")


class SegmentationAssetReader(Protocol):
    def asset_page(self, event_id: EntityId, *, limit: int, after: EntityId | None
                   ) -> tuple[tuple[RegisteredSegmentationAsset, ...], EntityId | None]: ...


@dataclass(frozen=True, slots=True)
class MediaSegmentationEnqueue:
    work: WorkExecutionRepository[MediaSegmentationOperationInput]
    deployment_id: str
    clock: Clock

    def enqueue(self, event_id: EntityId, asset: RegisteredSegmentationAsset
                ) -> DurableOperation[MediaSegmentationOperationInput]:
        profile = CURRENT_SEGMENTATION_PROFILE
        identity = str(uuid5(NAMESPACE_URL, f"stageflow:media-segmentation:{self.deployment_id}:"
            f"{event_id.value}:{asset.asset_id.value}:{asset.manifest_id.value}:"
            f"{profile.id}:{profile.version}"))
        now = self.clock.now()
        request = EnqueueOperation(
            EntityId(identity), "media-segmentation:" + identity, self.deployment_id, event_id,
            MediaSegmentationOperationInput(asset.asset_id, asset.manifest_id, "1.0",
                                      profile.id, profile.version),
            0, now, 3, timedelta(seconds=30), False, now,
        )
        pending = pending_media_segmentation_operation(request)
        # Receipt time is not caller intent. Concurrent/exact replay retains the first
        # durable operation and its actual request time, even with a changed clock.
        return self.work.enqueue(replace(pending, request_digest=human_command_digest({
            "kind": "media_segmentation_enqueue", "work_key": pending.work_key,
            "deployment_id": self.deployment_id, "event_id": event_id.value,
        })))

    def enqueue_existing(
        self, reader: SegmentationAssetReader, event_id: EntityId, *, actor_id: EntityId,
        authority_kind: str, confirmed: bool, limit: int = 50, after: EntityId | None = None,
    ) -> tuple[tuple[DurableOperation[MediaSegmentationOperationInput], ...], EntityId | None]:
        if authority_kind != "human" or not confirmed or not actor_id.value:
            raise ValueError("media_segmentation_human_confirmation_required")
        if not 1 <= limit <= 100:
            raise ValueError("media_segmentation_limit_out_of_bounds")
        assets, cursor = reader.asset_page(event_id, limit=limit, after=after)
        return tuple(self.enqueue(event_id, asset) for asset in assets), cursor
