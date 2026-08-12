from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from app.contexts.production.timeline import TimelinePosition, TimelineRange
from app.shared.ids import CorrelationId, EntityId
from app.shared.metadata import freeze_metadata


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class ObservationContext:
    """Partial operational context preserved while interpreting an Observation."""

    stage_id: EntityId | None = None
    recording_block_id: EntityId | None = None
    correlation_id: CorrelationId | None = None
    scheduled_activity_id: EntityId | None = None
    transcript_stream_id: str | None = None
    media_artifact_id: str | None = None
    timeline_position: TimelinePosition | None = None
    timeline_range: TimelineRange | None = None
    timeline_reference: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        for field_name in (
            "transcript_stream_id",
            "media_artifact_id",
            "timeline_reference",
        ):
            value = getattr(self, field_name)
            if value is not None and not value.strip():
                raise ValueError(f"ObservationContext {field_name} must not be empty.")
        if (
            self.timeline_position is not None
            and self.timeline_range is not None
        ):
            raise ValueError(
                "ObservationContext cannot contain both timeline_position and timeline_range."
            )
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    @classmethod
    def unknown(cls) -> ObservationContext:
        return cls()
