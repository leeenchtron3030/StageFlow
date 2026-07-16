from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from app.contexts.production.evidence import EvidenceConcern
from app.shared.ids import EntityId


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
    timeline_start_seconds: float | None = None
    timeline_end_seconds: float | None = None
    boundary_anchor_seconds: float | None = None
    boundary_anchor_at: datetime | None = None
    context_label: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
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
        object.__setattr__(self, "transcript_stream_ids", tuple(self.transcript_stream_ids))
        object.__setattr__(self, "media_artifact_ids", tuple(self.media_artifact_ids))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
