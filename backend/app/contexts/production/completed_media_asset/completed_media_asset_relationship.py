from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from app.shared.ids import EntityId

from .completed_media_asset_validation import (
    freeze_metadata,
    normalize_entity_ids,
    require_non_negative_duration,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class CompletedMediaAssetRelationship:
    """Partial relationship to a recording sequence, never to a Session."""

    recording_group_id: EntityId | None = None
    parent_recording_id: EntityId | None = None
    segment_index: int | None = None
    sequence_number: int | None = None
    previous_asset_id: EntityId | None = None
    next_asset_id: EntityId | None = None
    expected_segment_duration: timedelta | None = None
    actual_duration: timedelta | None = None
    is_first_known_segment: bool | None = None
    is_final_known_segment: bool | None = None
    related_asset_ids: Sequence[EntityId] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if self.segment_index is not None and self.segment_index < 0:
            raise ValueError("Completed media segment index must not be negative.")
        if self.sequence_number is not None and self.sequence_number < 0:
            raise ValueError("Completed media sequence number must not be negative.")
        if (
            self.previous_asset_id is not None
            and self.previous_asset_id == self.next_asset_id
        ):
            raise ValueError("Previous and next asset references must be distinct.")
        require_non_negative_duration(
            self.expected_segment_duration,
            "CompletedMediaAssetRelationship.expected_segment_duration",
        )
        require_non_negative_duration(
            self.actual_duration,
            "CompletedMediaAssetRelationship.actual_duration",
        )
        object.__setattr__(
            self,
            "related_asset_ids",
            normalize_entity_ids(
                self.related_asset_ids,
                "CompletedMediaAssetRelationship.related_asset_ids",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_metadata(self.metadata, "CompletedMediaAssetRelationship.metadata"),
        )
