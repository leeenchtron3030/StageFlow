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
    require_optional_non_empty,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


class AssetResourcePresenceStatus(StrEnum):
    PRESENT = "present"
    MISSING = "missing"
    REPLACED = "replaced"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class AssetResourcePresenceObservation:
    """Supplied resource-presence fact with explicit replacement semantics."""

    id: EntityId
    candidate_id: EntityId
    resource_id: EntityId
    observed_at: datetime
    status: AssetResourcePresenceStatus
    observer_id: EntityId
    source_runtime_id: EntityId | None = None
    observed_resource_identity_token: str | None = None
    replacement_resource_id: EntityId | None = None
    limitations: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware(self.observed_at, "AssetResourcePresenceObservation.observed_at")
        object.__setattr__(
            self,
            "observed_resource_identity_token",
            require_optional_non_empty(
                self.observed_resource_identity_token,
                "AssetResourcePresenceObservation.observed_resource_identity_token",
            ),
        )
        if (
            self.status is AssetResourcePresenceStatus.REPLACED
            and self.replacement_resource_id is None
        ):
            raise ValueError("Replaced resource observation requires replacement_resource_id.")
        if (
            self.status is not AssetResourcePresenceStatus.REPLACED
            and self.replacement_resource_id is not None
        ):
            raise ValueError("Only a replaced resource observation may name a replacement.")
        if self.replacement_resource_id == self.resource_id:
            raise ValueError("Replacement resource ID must differ from observed resource ID.")
        object.__setattr__(
            self,
            "limitations",
            normalize_limitations(
                self.limitations,
                "AssetResourcePresenceObservation.limitations",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_readiness_metadata(
                self.metadata,
                "AssetResourcePresenceObservation.metadata",
            ),
        )
