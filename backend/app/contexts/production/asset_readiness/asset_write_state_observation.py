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


class AssetWriteStateStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class AssetWriteStateObservation:
    """Supplied knowledge of active writing with no handle inspection behavior."""

    id: EntityId
    candidate_id: EntityId
    resource_id: EntityId
    observed_at: datetime
    status: AssetWriteStateStatus
    assessment_mechanism_id: str
    observer_id: EntityId
    source_runtime_id: EntityId | None = None
    writer_id: EntityId | None = None
    limitations: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware(self.observed_at, "AssetWriteStateObservation.observed_at")
        object.__setattr__(
            self,
            "assessment_mechanism_id",
            require_non_empty(
                self.assessment_mechanism_id,
                "AssetWriteStateObservation.assessment_mechanism_id",
            ),
        )
        object.__setattr__(
            self,
            "limitations",
            normalize_limitations(
                self.limitations,
                "AssetWriteStateObservation.limitations",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_readiness_metadata(
                self.metadata,
                "AssetWriteStateObservation.metadata",
            ),
        )
