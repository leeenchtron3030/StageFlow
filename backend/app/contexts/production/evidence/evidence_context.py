from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from typing import Any

from app.contexts.production.timeline import TimelinePosition, TimelineRange
from app.shared.ids import CorrelationId, EntityId
from app.shared.metadata import freeze_metadata
from app.shared.time import require_aware_datetime


def _empty_metadata() -> Mapping[str, Any]:
    return {}


def _entity_ids(values: Sequence[EntityId]) -> tuple[EntityId, ...]:
    return tuple(sorted(dict.fromkeys(values), key=lambda item: item.to_json()))


def _correlation_ids(
    values: Sequence[CorrelationId],
) -> tuple[CorrelationId, ...]:
    return tuple(sorted(dict.fromkeys(values), key=lambda item: item.to_json()))


def _identifiers(values: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(value.strip() for value in values)
    if any(not value for value in normalized):
        raise ValueError("EvidenceContext identifiers must not be blank.")
    return tuple(sorted(dict.fromkeys(normalized)))


@dataclass(frozen=True, slots=True)
class EvidenceContext:
    """Partial, first-class operational context locating one EvidenceSet."""

    stage_id: EntityId | None = None
    recording_block_id: EntityId | None = None
    scheduled_activity_id: EntityId | None = None
    transcript_stream_ids: Sequence[str] = field(default_factory=tuple)
    media_artifact_ids: Sequence[str] = field(default_factory=tuple)
    correlation_ids: Sequence[CorrelationId] = field(default_factory=tuple)
    timeline_position: TimelinePosition | None = None
    timeline_range: TimelineRange | None = None
    organizational_anchor: datetime | None = None
    organizational_anchor_seconds: float | None = None
    boundary_context_id: EntityId | None = None
    source_context_ids: Sequence[EntityId] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(
        default_factory=_empty_metadata,
        compare=False,
        hash=False,
    )

    def __post_init__(self) -> None:
        if self.organizational_anchor is not None:
            require_aware_datetime(
                self.organizational_anchor,
                "EvidenceContext.organizational_anchor",
            )
        object.__setattr__(
            self,
            "transcript_stream_ids",
            _identifiers(self.transcript_stream_ids),
        )
        object.__setattr__(
            self,
            "media_artifact_ids",
            _identifiers(self.media_artifact_ids),
        )
        object.__setattr__(
            self,
            "correlation_ids",
            _correlation_ids(self.correlation_ids),
        )
        object.__setattr__(
            self,
            "source_context_ids",
            _entity_ids(self.source_context_ids),
        )
        if self.timeline_position is not None and self.timeline_range is not None:
            raise ValueError(
                "EvidenceContext cannot contain both timeline_position and timeline_range."
            )
        timeline_block_id = None
        if self.timeline_position is not None:
            timeline_block_id = self.timeline_position.recording_block_id
        elif self.timeline_range is not None:
            timeline_block_id = self.timeline_range.recording_block_id
        if (
            timeline_block_id is not None
            and self.recording_block_id is not None
            and timeline_block_id != self.recording_block_id
        ):
            raise ValueError("EvidenceContext timeline must belong to recording_block_id.")
        if self.organizational_anchor_seconds is not None:
            if not isfinite(self.organizational_anchor_seconds):
                raise ValueError("EvidenceContext organizational_anchor_seconds must be finite.")
            object.__setattr__(
                self,
                "organizational_anchor_seconds",
                float(self.organizational_anchor_seconds),
            )
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    @classmethod
    def unknown(cls) -> EvidenceContext:
        return cls()

    @property
    def is_empty(self) -> bool:
        return not any(
            (
                self.stage_id,
                self.recording_block_id,
                self.scheduled_activity_id,
                self.transcript_stream_ids,
                self.media_artifact_ids,
                self.correlation_ids,
                self.timeline_position,
                self.timeline_range,
                self.organizational_anchor,
                self.organizational_anchor_seconds is not None,
                self.boundary_context_id,
                self.source_context_ids,
            )
        )

    @property
    def timeline_range_seconds(self) -> tuple[float, float] | None:
        if self.timeline_position is not None:
            seconds = self.timeline_position.offset.total_seconds()
            return seconds, seconds
        if self.timeline_range is not None:
            return (
                self.timeline_range.start.offset.total_seconds(),
                self.timeline_range.end.offset.total_seconds(),
            )
        return None
