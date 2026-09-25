"""Thread-safe, non-durable test implementation; never a PostgreSQL fallback."""

from collections.abc import Mapping
from threading import RLock
from typing import TypeVar

from app.shared.ids import EntityId

from .contracts import (
    ApprovalAction,
    ApprovalState,
    AssetPage,
    AssetSummary,
    CommandIdentity,
    CompletedMediaAssetContent,
    PackagingAsset,
    PackagingAssetApprovalDecision,
    PackagingAssetRevision,
    RevisionPage,
    RevisionSummary,
    nonnegative,
    validate_page,
)
from .repository import PackagingAssetConflictError, PackagingAssetNotFoundError

T = TypeVar("T", PackagingAsset, PackagingAssetRevision, PackagingAssetApprovalDecision)


class InMemoryPackagingAssetRepository:
    def __init__(
        self, *, event_ids: frozenset[EntityId], stages: Mapping[EntityId, EntityId],
        completed_asset_ids: frozenset[EntityId] = frozenset(),
    ) -> None:
        self._events = frozenset(event_ids)
        self._stages = dict(stages)
        self._completed = frozenset(completed_asset_ids)
        self._assets: dict[EntityId, PackagingAsset] = {}
        self._revisions: dict[EntityId, list[PackagingAssetRevision]] = {}
        self._decisions: dict[EntityId, list[PackagingAssetApprovalDecision]] = {}
        self._commands: dict[EntityId, tuple[str, object]] = {}
        self._lock = RLock()

    def _replay(self, command: CommandIdentity, result_type: type[T]) -> T | None:
        existing = self._commands.get(command.operation_id)
        if existing is None:
            return None
        digest, result = existing
        if digest != command.request_digest or not isinstance(result, result_type):
            raise PackagingAssetConflictError("human_command_operation_id_conflict")
        return result

    def _check_revision(self, asset_id: EntityId, expected: int) -> None:
        if asset_id not in self._assets:
            raise PackagingAssetNotFoundError("packaging_asset_not_found")
        if len(self._revisions[asset_id]) != expected:
            raise PackagingAssetConflictError("packaging_asset_revision_conflict")

    def register(self, command: CommandIdentity, asset: PackagingAsset) -> PackagingAsset:
        with self._lock:
            replay = self._replay(command, PackagingAsset)
            if replay is not None:
                return replay
            if asset.event_id not in self._events:
                raise PackagingAssetNotFoundError("event_not_found")
            if asset.stage_id is not None and self._stages.get(asset.stage_id) != asset.event_id:
                raise PackagingAssetNotFoundError("stage_not_in_event")
            if asset.id in self._assets:
                raise PackagingAssetConflictError("packaging_asset_identity_conflict")
            self._assets[asset.id] = asset
            self._revisions[asset.id] = []
            self._decisions[asset.id] = []
            self._commands[command.operation_id] = (command.request_digest, asset)
            return asset

    def revise(
        self, command: CommandIdentity, revision: PackagingAssetRevision, *, expected_revision: int,
    ) -> PackagingAssetRevision:
        with self._lock:
            replay = self._replay(command, PackagingAssetRevision)
            if replay is not None:
                return replay
            self._check_revision(revision.packaging_asset_id, expected_revision)
            if revision.revision_number != expected_revision + 1:
                raise PackagingAssetConflictError("packaging_asset_revision_conflict")
            reference = revision.content.reference
            if isinstance(reference, CompletedMediaAssetContent) and reference.asset_id not in (
                self._completed
            ):
                raise PackagingAssetNotFoundError("completed_media_asset_not_found")
            self._revisions[revision.packaging_asset_id].append(revision)
            self._commands[command.operation_id] = (command.request_digest, revision)
            return revision

    def decide(
        self, command: CommandIdentity, *, decision_id: EntityId, packaging_asset_id: EntityId,
        revision_number: int, expected_revision: int, action: ApprovalAction, reason: str,
    ) -> PackagingAssetApprovalDecision:
        with self._lock:
            replay = self._replay(command, PackagingAssetApprovalDecision)
            if replay is not None:
                return replay
            self._check_revision(packaging_asset_id, expected_revision)
            if not 1 <= revision_number <= expected_revision:
                raise PackagingAssetNotFoundError("packaging_asset_revision_not_found")
            history = self._decisions[packaging_asset_id]
            decision = PackagingAssetApprovalDecision(
                decision_id, packaging_asset_id, revision_number, len(history) + 1,
                command.actor_id, command.recorded_at, action, reason,
            )
            history.append(decision)
            self._commands[command.operation_id] = (command.request_digest, decision)
            return decision

    def list_assets(
        self, event_id: EntityId, *, after: EntityId | None = None, limit: int = 50,
    ) -> AssetPage:
        validate_page(limit)
        with self._lock:
            assets = sorted(
                (asset for asset in self._assets.values() if asset.event_id == event_id),
                key=lambda asset: asset.id.value,
            )
            selected = [asset for asset in assets if after is None or asset.id.value > after.value]
            items = tuple(AssetSummary(
                asset, len(self._revisions[asset.id]), len(self._decisions[asset.id]),
            ) for asset in selected[:limit])
            return AssetPage(
                items, len(assets), items[-1].asset.id if len(selected) > limit else None,
            )

    def list_revisions(
        self, event_id: EntityId, packaging_asset_id: EntityId, *, after: int = 0, limit: int = 50,
    ) -> RevisionPage:
        validate_page(limit)
        nonnegative(after, "after")
        with self._lock:
            asset = self._assets.get(packaging_asset_id)
            if asset is None or asset.event_id != event_id:
                raise PackagingAssetNotFoundError("packaging_asset_not_found")
            revisions = self._revisions[asset.id]
            selected = [revision for revision in revisions if revision.revision_number > after]
            items: list[RevisionSummary] = []
            for revision in selected[:limit]:
                decisions = [decision for decision in self._decisions[asset.id]
                             if decision.revision_number == revision.revision_number]
                latest = decisions[-1] if decisions else None
                items.append(RevisionSummary(
                    revision, ApprovalState.UNREVIEWED if latest is None else latest.approval_state,
                    len(decisions), latest,
                ))
            return RevisionPage(
                tuple(items), len(revisions),
                items[-1].revision.revision_number if len(selected) > limit else None,
            )
