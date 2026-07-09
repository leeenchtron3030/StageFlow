from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.contexts.production.production_event.production_event_type import ProductionEventType


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class MediaArtifactObservationMapping:
    """Declarative mapping from media artifact events to objective observations."""

    production_event_type: ProductionEventType
    observation_note: str
    artifact_lifecycle: str
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.observation_note.strip():
            raise ValueError("MediaArtifactObservationMapping observation_note is required.")
        if not self.artifact_lifecycle.strip():
            raise ValueError("MediaArtifactObservationMapping artifact_lifecycle is required.")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


MEDIA_ARTIFACT_OBSERVATION_MAPPINGS: tuple[MediaArtifactObservationMapping, ...] = (
    MediaArtifactObservationMapping(
        production_event_type=ProductionEventType.MEDIA_FILE_CREATED,
        observation_note="Media artifact was created.",
        artifact_lifecycle="created",
    ),
    MediaArtifactObservationMapping(
        production_event_type=ProductionEventType.MEDIA_FILE_FINALIZED,
        observation_note="Media artifact was finalized.",
        artifact_lifecycle="finalized",
    ),
    MediaArtifactObservationMapping(
        production_event_type=ProductionEventType.MEDIA_FILE_FAILED,
        observation_note="Media artifact failed.",
        artifact_lifecycle="failed",
    ),
)


def mapping_for_media_artifact(
    event_type: ProductionEventType,
) -> MediaArtifactObservationMapping | None:
    """Return the objective media artifact mapping for a generic event type."""

    for mapping in MEDIA_ARTIFACT_OBSERVATION_MAPPINGS:
        if mapping.production_event_type is event_type:
            return mapping
    return None
