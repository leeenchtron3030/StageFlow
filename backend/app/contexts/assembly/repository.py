from typing import Protocol

from app.shared.ids import EntityId

from .contracts import (
    ApprovalAction,
    AssetPage,
    CommandIdentity,
    PackagingAsset,
    PackagingAssetApprovalDecision,
    PackagingAssetRevision,
    RevisionPage,
)


class PackagingAssetConflictError(RuntimeError):
    pass


class PackagingAssetNotFoundError(LookupError):
    pass


class PackagingAssetStorageUnavailableError(RuntimeError):
    pass


class PackagingAssetRepository(Protocol):
    def register(self, command: CommandIdentity, asset: PackagingAsset) -> PackagingAsset: ...

    def revise(
        self, command: CommandIdentity, revision: PackagingAssetRevision, *, expected_revision: int,
    ) -> PackagingAssetRevision: ...

    def decide(
        self, command: CommandIdentity, *, decision_id: EntityId, packaging_asset_id: EntityId,
        revision_number: int, expected_revision: int, action: ApprovalAction, reason: str,
    ) -> PackagingAssetApprovalDecision: ...

    def list_assets(
        self, event_id: EntityId, *, after: EntityId | None = None, limit: int = 50,
    ) -> AssetPage: ...

    def list_revisions(
        self, event_id: EntityId, packaging_asset_id: EntityId, *, after: int = 0, limit: int = 50,
    ) -> RevisionPage: ...
