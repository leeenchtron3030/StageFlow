from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

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
