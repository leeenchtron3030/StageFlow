from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.shared.ids import EntityId

from .asset_readiness_validation import (
    freeze_readiness_metadata,
    normalize_limitations,
    require_aware,
    require_non_empty,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


class AssetReadAccessStatus(StrEnum):
    READABLE = "readable"
    UNREADABLE = "unreadable"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class AssetReadAccessObservation:
    """Supplied non-destructive read result; this contract performs no access."""

    id: EntityId
    candidate_id: EntityId
    resource_id: EntityId
    observed_at: datetime
    status: AssetReadAccessStatus
    assessment_method_id: str
    access_scope: str
    observer_id: EntityId
    source_runtime_id: EntityId | None = None
    limitations: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware(self.observed_at, "AssetReadAccessObservation.observed_at")
        object.__setattr__(
            self,
            "assessment_method_id",
            require_non_empty(
                self.assessment_method_id,
                "AssetReadAccessObservation.assessment_method_id",
            ),
        )
        object.__setattr__(
            self,
            "access_scope",
            require_non_empty(
                self.access_scope,
                "AssetReadAccessObservation.access_scope",
            ),
        )
        object.__setattr__(
            self,
            "limitations",
            normalize_limitations(
                self.limitations,
                "AssetReadAccessObservation.limitations",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_readiness_metadata(
                self.metadata,
                "AssetReadAccessObservation.metadata",
            ),
        )
