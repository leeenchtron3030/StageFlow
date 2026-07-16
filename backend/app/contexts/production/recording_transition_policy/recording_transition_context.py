from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from types import MappingProxyType
from typing import Any

from app.shared.ids import CorrelationId, EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RecordingTransitionContext:
    """Policy-local recording identity and ordering context for one EvidenceSet.

    Recording block and stage are the primary recording identity. Correlation remains
    traceability only because it is a workflow identifier, not a recording identity.
    Media artifact identity distinguishes otherwise unidentified recordings, but does
    not split segmented artifacts that share a known recording block.
    """

    recording_block_id: EntityId | None = None
    stage_id: EntityId | None = None
    correlation_id: CorrelationId | None = None
    media_artifact_id: str | None = None
    source_evidence_set_id: EntityId | None = field(
        default=None,
        compare=False,
        hash=False,
    )
    timeline_range_seconds: tuple[float, float] | None = field(
        default=None,
        compare=False,
        hash=False,
    )
    organizational_at: datetime | None = field(
        default=None,
        compare=False,
        hash=False,
    )
    metadata: Mapping[str, Any] = field(
        default_factory=_empty_metadata,
        compare=False,
        hash=False,
    )

    def __post_init__(self) -> None:
        if self.media_artifact_id is not None and not self.media_artifact_id.strip():
            raise ValueError("RecordingTransitionContext media_artifact_id must not be blank.")
        if self.timeline_range_seconds is not None:
            start, end = self.timeline_range_seconds
            if not isfinite(start) or not isfinite(end) or end < start:
                raise ValueError(
                    "RecordingTransitionContext timeline_range_seconds must be finite and ordered."
                )
            object.__setattr__(
                self,
                "timeline_range_seconds",
                (float(start), float(end)),
            )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def has_recording_identity(self) -> bool:
        return any(
            (
                self.recording_block_id is not None,
                self.stage_id is not None,
                self.media_artifact_id is not None,
            )
        )

    def compatibility_key(self) -> tuple[str, str, str]:
        return (
            self.recording_block_id.to_json()
            if self.recording_block_id is not None
            else "",
            self.stage_id.to_json() if self.stage_id is not None else "",
            self.media_artifact_id or "",
        )
