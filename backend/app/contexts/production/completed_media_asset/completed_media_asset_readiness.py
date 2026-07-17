from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.shared.ids import EntityId

from .completed_media_asset_validation import (
    freeze_metadata,
    normalize_entity_ids,
    normalize_strings,
    require_aware,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


class CompletedMediaAssetReadinessStatus(StrEnum):
    SAFE_TO_READ = "safe_to_read"
    NOT_SAFE_TO_READ = "not_safe_to_read"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CompletedMediaAssetReadiness:
    """Categorical caller-supplied safe-read declaration with no assessment behavior."""

    id: EntityId
    status: CompletedMediaAssetReadinessStatus
    assessed_at: datetime
    assessment_method_identifiers: Sequence[str] = field(default_factory=tuple)
    supporting_check_ids: Sequence[EntityId] = field(default_factory=tuple)
    limitations: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware(
            self.assessed_at,
            "CompletedMediaAssetReadiness.assessed_at",
        )
        object.__setattr__(
            self,
            "assessment_method_identifiers",
            normalize_strings(
                self.assessment_method_identifiers,
                "CompletedMediaAssetReadiness.assessment_method_identifiers",
            ),
        )
        object.__setattr__(
            self,
            "supporting_check_ids",
            normalize_entity_ids(
                self.supporting_check_ids,
                "CompletedMediaAssetReadiness.supporting_check_ids",
            ),
        )
        object.__setattr__(
            self,
            "limitations",
            normalize_strings(
                self.limitations,
                "CompletedMediaAssetReadiness.limitations",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_metadata(self.metadata, "CompletedMediaAssetReadiness.metadata"),
        )
