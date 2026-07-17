from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.shared.ids import EntityId

from .completed_media_asset_validation import (
    freeze_metadata,
    normalize_entity_ids,
    require_aware,
    require_non_empty,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class CompletedMediaAssetManifest:
    """Versioned serialization-ready identity manifest with no transport state."""

    id: EntityId
    schema_name: str
    schema_version: str
    asset_id: EntityId
    created_at: datetime
    producer_runtime_id: EntityId
    source_resource_id: EntityId
    related_resource_ids: Sequence[EntityId] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema_name",
            require_non_empty(
                self.schema_name,
                "CompletedMediaAssetManifest.schema_name",
            ),
        )
        object.__setattr__(
            self,
            "schema_version",
            require_non_empty(
                self.schema_version,
                "CompletedMediaAssetManifest.schema_version",
            ),
        )
        require_aware(
            self.created_at,
            "CompletedMediaAssetManifest.created_at",
        )
        object.__setattr__(
            self,
            "related_resource_ids",
            normalize_entity_ids(
                self.related_resource_ids,
                "CompletedMediaAssetManifest.related_resource_ids",
            ),
        )
        if self.source_resource_id in self.related_resource_ids:
            raise ValueError("Primary resource must not also be a related resource.")
        object.__setattr__(
            self,
            "metadata",
            freeze_metadata(self.metadata, "CompletedMediaAssetManifest.metadata"),
        )
