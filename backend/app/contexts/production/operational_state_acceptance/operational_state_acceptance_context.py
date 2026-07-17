from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Any

from app.contexts.production.evidence import EvidenceContext
from app.contexts.production.timeline import TimelinePosition, TimelineRange
from app.shared.ids import CorrelationId, EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class OperationalStateAcceptanceContext:
    """ID-only operational context local to state acceptance."""

    stage_id: EntityId | None = None
    recording_block_id: EntityId | None = None
    scheduled_activity_id: EntityId | None = None
    transcript_stream_ids: Sequence[str] = field(default_factory=tuple)
    media_artifact_ids: Sequence[str] = field(default_factory=tuple)
    correlation_id: CorrelationId | None = None
    boundary_evidence_context_id: EntityId | None = None
    organizational_anchor: str | None = None
    timeline_range_seconds: tuple[float, float] | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        for name in ("transcript_stream_ids", "media_artifact_ids"):
            values = tuple(dict.fromkeys(getattr(self, name)))
            if any(not value.strip() for value in values):
                raise ValueError(f"OperationalStateAcceptanceContext {name} must not be blank.")
            object.__setattr__(self, name, values)
        if self.organizational_anchor is not None and not self.organizational_anchor.strip():
            raise ValueError(
                "OperationalStateAcceptanceContext organizational_anchor must not be blank."
            )
        if self.timeline_range_seconds is not None:
            start, end = self.timeline_range_seconds
            if end < start:
                raise ValueError(
                    "OperationalStateAcceptanceContext timeline range must be ordered."
                )
            object.__setattr__(self, "timeline_range_seconds", (float(start), float(end)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @classmethod
    def unknown(cls) -> OperationalStateAcceptanceContext:
        return cls()

    @classmethod
    def from_evidence_context(
        cls,
        context: EvidenceContext,
    ) -> OperationalStateAcceptanceContext:
        organizational_anchor = None
        if context.organizational_anchor is not None:
            organizational_anchor = context.organizational_anchor.isoformat()
        elif context.organizational_anchor_seconds is not None:
            organizational_anchor = str(context.organizational_anchor_seconds)
        return cls(
            stage_id=context.stage_id,
            recording_block_id=context.recording_block_id,
            scheduled_activity_id=context.scheduled_activity_id,
            transcript_stream_ids=context.transcript_stream_ids,
            media_artifact_ids=context.media_artifact_ids,
            correlation_id=(
                context.correlation_ids[0] if len(context.correlation_ids) == 1 else None
            ),
            boundary_evidence_context_id=context.boundary_context_id,
            organizational_anchor=organizational_anchor,
            timeline_range_seconds=context.timeline_range_seconds,
        )

    def to_evidence_context(self) -> EvidenceContext:
        timeline_position: TimelinePosition | None = None
        timeline_range: TimelineRange | None = None
        if self.recording_block_id is not None and self.timeline_range_seconds is not None:
            start, end = self.timeline_range_seconds
            if end > start:
                timeline_range = TimelineRange(
                    TimelinePosition(
                        self.recording_block_id,
                        timedelta(seconds=start),
                    ),
                    TimelinePosition(
                        self.recording_block_id,
                        timedelta(seconds=end),
                    ),
                )
            else:
                timeline_position = TimelinePosition(
                    self.recording_block_id,
                    timedelta(seconds=start),
                )
        organizational_anchor: datetime | None = None
        organizational_anchor_seconds: float | None = None
        if self.organizational_anchor is not None:
            try:
                organizational_anchor = datetime.fromisoformat(self.organizational_anchor)
            except ValueError:
                try:
                    organizational_anchor_seconds = float(self.organizational_anchor)
                except ValueError:
                    pass
        return EvidenceContext(
            stage_id=self.stage_id,
            recording_block_id=self.recording_block_id,
            scheduled_activity_id=self.scheduled_activity_id,
            transcript_stream_ids=self.transcript_stream_ids,
            media_artifact_ids=self.media_artifact_ids,
            correlation_ids=(self.correlation_id,) if self.correlation_id is not None else (),
            timeline_position=timeline_position,
            timeline_range=timeline_range,
            organizational_anchor=organizational_anchor,
            organizational_anchor_seconds=organizational_anchor_seconds,
            boundary_context_id=self.boundary_evidence_context_id,
        )
