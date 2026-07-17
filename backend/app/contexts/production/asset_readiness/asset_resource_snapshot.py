from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.shared.ids import EntityId

from .asset_readiness_validation import (
    freeze_readiness_metadata,
    normalize_limitations,
    require_aware,
    require_optional_aware,
    require_optional_non_empty,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class AssetResourceSnapshot:
    """Objective point-in-time resource facts supplied by an external collector."""

    id: EntityId
    candidate_id: EntityId
    resource_id: EntityId
    observed_at: datetime
    size_bytes: int
    observer_id: EntityId
    filesystem_modified_at: datetime | None = None
    stable_resource_identity_token: str | None = None
    source_volume_id: EntityId | None = None
    source_host_id: EntityId | None = None
    source_runtime_id: EntityId | None = None
    limitations: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware(self.observed_at, "AssetResourceSnapshot.observed_at")
        require_optional_aware(
            self.filesystem_modified_at,
            "AssetResourceSnapshot.filesystem_modified_at",
        )
        if self.size_bytes < 0:
            raise ValueError("Asset resource snapshot size must not be negative.")
        object.__setattr__(
            self,
            "stable_resource_identity_token",
            require_optional_non_empty(
                self.stable_resource_identity_token,
                "AssetResourceSnapshot.stable_resource_identity_token",
            ),
        )
        object.__setattr__(
            self,
            "limitations",
            normalize_limitations(
                self.limitations,
                "AssetResourceSnapshot.limitations",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_readiness_metadata(self.metadata, "AssetResourceSnapshot.metadata"),
        )
