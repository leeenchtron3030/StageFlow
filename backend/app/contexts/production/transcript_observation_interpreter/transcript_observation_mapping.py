from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.contexts.production.production_event.production_event_type import ProductionEventType


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class TranscriptObservationMapping:
    """Declarative mapping from transcript events to objective observations."""

    production_event_type: ProductionEventType
    observation_note: str
    transcript_lifecycle: str
    requires_transcript_metadata: bool = False
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.observation_note.strip():
            raise ValueError("TranscriptObservationMapping observation_note is required.")
        if not self.transcript_lifecycle.strip():
            raise ValueError("TranscriptObservationMapping transcript_lifecycle is required.")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


TRANSCRIPT_OBSERVATION_MAPPINGS: tuple[TranscriptObservationMapping, ...] = (
    TranscriptObservationMapping(
        production_event_type=ProductionEventType.TRANSCRIPT_SEGMENT_AVAILABLE,
        observation_note="Transcript segment became available.",
        transcript_lifecycle="segment_available",
    ),
    TranscriptObservationMapping(
        production_event_type=ProductionEventType.SYSTEM_STATUS_CHANGED,
        observation_note="Transcript source status changed.",
        transcript_lifecycle="transcript_source_status_changed",
        requires_transcript_metadata=True,
    ),
)


def mapping_for_transcript(
    event_type: ProductionEventType,
) -> TranscriptObservationMapping | None:
    """Return the objective transcript mapping for a generic event type."""

    for mapping in TRANSCRIPT_OBSERVATION_MAPPINGS:
        if mapping.production_event_type is event_type:
            return mapping
    return None
