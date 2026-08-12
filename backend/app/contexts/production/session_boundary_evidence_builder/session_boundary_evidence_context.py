from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from app.contexts.production.evidence import EvidenceConcern, EvidenceContext
from app.contexts.production.timeline import TimelinePosition, TimelineRange
from app.shared.ids import CorrelationId, EntityId
from app.shared.metadata import freeze_metadata
from app.shared.time import require_aware_datetime


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class SessionBoundaryEvidenceContext:
    """ID-only production and timeline context for possible-boundary Evidence."""

    id: EntityId
    boundary_concern: EvidenceConcern
    recording_block_id: EntityId | None = None
    stage_id: EntityId | None = None
    scheduled_activity_id: EntityId | None = None
    transcript_stream_ids: Sequence[str] = field(default_factory=tuple)
    media_artifact_ids: Sequence[str] = field(default_factory=tuple)
    correlation_ids: Sequence[CorrelationId] = field(default_factory=tuple)
    source_context_ids: Sequence[EntityId] = field(default_factory=tuple)
    timeline_start_seconds: float | None = None
    timeline_end_seconds: float | None = None
    boundary_anchor_seconds: float | None = None
    boundary_anchor_at: datetime | None = None
    context_label: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if self.boundary_anchor_at is not None:
            require_aware_datetime(
                self.boundary_anchor_at,
                "SessionBoundaryEvidenceContext.boundary_anchor_at",
            )
        if self.boundary_concern not in {
            EvidenceConcern.POSSIBLE_SESSION_START,
            EvidenceConcern.POSSIBLE_SESSION_END,
        }:
            raise ValueError("Boundary context requires a possible session boundary concern.")
        if (
            self.timeline_start_seconds is not None
            and self.timeline_end_seconds is not None
            and self.timeline_end_seconds < self.timeline_start_seconds
        ):
            raise ValueError("Boundary context timeline end must not precede its start.")
        object.__setattr__(
            self,
            "transcript_stream_ids",
            tuple(sorted(dict.fromkeys(self.transcript_stream_ids))),
        )
        object.__setattr__(
            self,
            "media_artifact_ids",
            tuple(sorted(dict.fromkeys(self.media_artifact_ids))),
        )
        object.__setattr__(
            self,
            "correlation_ids",
            tuple(
                sorted(
                    dict.fromkeys(self.correlation_ids),
                    key=lambda item: item.to_json(),
                )
            ),
        )
        object.__setattr__(
            self,
            "source_context_ids",
            tuple(
                sorted(
                    dict.fromkeys(self.source_context_ids),
                    key=lambda item: item.to_json(),
                )
            ),
        )
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def to_evidence_context(self) -> EvidenceContext:
        timeline_position: TimelinePosition | None = None
        timeline_range: TimelineRange | None = None
        if self.recording_block_id is not None:
            if (
                self.timeline_start_seconds is not None
                and self.timeline_end_seconds is not None
                and self.timeline_end_seconds > self.timeline_start_seconds
            ):
                timeline_range = TimelineRange(
                    TimelinePosition(
                        self.recording_block_id,
                        timedelta(seconds=self.timeline_start_seconds),
                    ),
                    TimelinePosition(
                        self.recording_block_id,
                        timedelta(seconds=self.timeline_end_seconds),
                    ),
                )
            elif self.boundary_anchor_seconds is not None:
                timeline_position = TimelinePosition(
                    self.recording_block_id,
                    timedelta(seconds=self.boundary_anchor_seconds),
                )
        return EvidenceContext(
            stage_id=self.stage_id,
            recording_block_id=self.recording_block_id,
            scheduled_activity_id=self.scheduled_activity_id,
            transcript_stream_ids=self.transcript_stream_ids,
            media_artifact_ids=self.media_artifact_ids,
            correlation_ids=self.correlation_ids,
            timeline_position=timeline_position,
            timeline_range=timeline_range,
            organizational_anchor=self.boundary_anchor_at,
            organizational_anchor_seconds=self.boundary_anchor_seconds,
            boundary_context_id=self.id,
            source_context_ids=self.source_context_ids,
        )
