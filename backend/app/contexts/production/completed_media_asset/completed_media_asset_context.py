from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.contexts.production.timeline import TimelinePosition, TimelineRange
from app.shared.ids import CorrelationId, EntityId

from .completed_media_asset_validation import (
    freeze_metadata,
    normalize_correlation_ids,
    normalize_strings,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class CompletedMediaAssetContext:
    """Explicit partial production context; filenames never establish authority."""

    stage_id: EntityId | None = None
    recording_block_id: EntityId | None = None
    scheduled_activity_id: EntityId | None = None
    correlation_ids: Sequence[CorrelationId] = field(default_factory=tuple)
    recording_source_id: EntityId | None = None
    transcript_stream_ids: Sequence[str] = field(default_factory=tuple)
    timeline_position: TimelinePosition | None = None
    timeline_range: TimelineRange | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if self.timeline_position is not None and self.timeline_range is not None:
            raise ValueError("Completed media context cannot contain two timeline anchors.")
        timeline_block_id = (
            self.timeline_position.recording_block_id
            if self.timeline_position is not None
            else self.timeline_range.recording_block_id
            if self.timeline_range is not None
            else None
        )
        if (
            timeline_block_id is not None
            and self.recording_block_id is not None
            and timeline_block_id != self.recording_block_id
        ):
            raise ValueError("Timeline anchor must match explicit recording block context.")
        object.__setattr__(
            self,
            "correlation_ids",
            normalize_correlation_ids(
                self.correlation_ids,
                "CompletedMediaAssetContext.correlation_ids",
            ),
        )
        object.__setattr__(
            self,
            "transcript_stream_ids",
            normalize_strings(
                self.transcript_stream_ids,
                "CompletedMediaAssetContext.transcript_stream_ids",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_metadata(self.metadata, "CompletedMediaAssetContext.metadata"),
        )

    @classmethod
    def unknown(cls) -> CompletedMediaAssetContext:
        return cls()
