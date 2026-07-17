from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.contexts.production.completed_media_asset import (
    CompletedMediaAssetCompletionMethod,
)
from app.shared.ids import EntityId

from .asset_readiness_validation import (
    freeze_readiness_metadata,
    normalize_limitations,
    require_aware,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class AssetFinalizationObservation:
    """Externally supplied completion signal; no finalization work is performed."""

    id: EntityId
    candidate_id: EntityId
    resource_id: EntityId
    observed_at: datetime
    completion_method: CompletedMediaAssetCompletionMethod
    declaring_entity_id: EntityId
    observer_id: EntityId
    source_runtime_id: EntityId | None = None
    completion_marker_resource_id: EntityId | None = None
    source_event_id: EntityId | None = None
    limitations: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware(self.observed_at, "AssetFinalizationObservation.observed_at")
        object.__setattr__(
            self,
            "limitations",
            normalize_limitations(
                self.limitations,
                "AssetFinalizationObservation.limitations",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_readiness_metadata(
                self.metadata,
                "AssetFinalizationObservation.metadata",
            ),
        )
