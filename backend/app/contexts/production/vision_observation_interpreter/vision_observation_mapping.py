from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from app.contexts.production.production_event.production_event_type import ProductionEventType
from app.shared.metadata import freeze_metadata


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class VisionObservationMapping:
    """Declarative mapping from vision events to objective observations."""

    production_event_type: ProductionEventType
    observation_note: str
    vision_lifecycle: str
    visual_detection_type: str | None = None
    requires_vision_metadata: bool = False
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.observation_note.strip():
            raise ValueError("VisionObservationMapping observation_note is required.")
        if not self.vision_lifecycle.strip():
            raise ValueError("VisionObservationMapping vision_lifecycle is required.")
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))


VISION_OBSERVATION_MAPPINGS: tuple[VisionObservationMapping, ...] = (
    VisionObservationMapping(
        production_event_type=ProductionEventType.VISUAL_DETECTION_AVAILABLE,
        observation_note="Visual text region was detected.",
        vision_lifecycle="text_region_detected",
        visual_detection_type="text_region",
    ),
    VisionObservationMapping(
        production_event_type=ProductionEventType.VISUAL_DETECTION_AVAILABLE,
        observation_note="Visual slide change was detected.",
        vision_lifecycle="slide_change_detected",
        visual_detection_type="slide_change",
    ),
    VisionObservationMapping(
        production_event_type=ProductionEventType.VISUAL_DETECTION_AVAILABLE,
        observation_note="Visual image change was detected.",
        vision_lifecycle="image_change_detected",
        visual_detection_type="image_change",
    ),
    VisionObservationMapping(
        production_event_type=ProductionEventType.VISUAL_DETECTION_AVAILABLE,
        observation_note="Visual camera obstruction was detected.",
        vision_lifecycle="camera_obstruction_detected",
        visual_detection_type="camera_obstruction",
    ),
    VisionObservationMapping(
        production_event_type=ProductionEventType.VISUAL_DETECTION_AVAILABLE,
        observation_note="Visual phenomenon was detected.",
        vision_lifecycle="visual_detection_available",
    ),
    VisionObservationMapping(
        production_event_type=ProductionEventType.SYSTEM_STATUS_CHANGED,
        observation_note="Vision source status changed.",
        vision_lifecycle="vision_source_status_changed",
        requires_vision_metadata=True,
    ),
)


def mapping_for_vision(
    event_type: ProductionEventType,
    visual_detection_type: str | None = None,
) -> VisionObservationMapping | None:
    """Return the objective vision mapping for a generic event payload."""

    if event_type is ProductionEventType.VISUAL_DETECTION_AVAILABLE:
        for mapping in VISION_OBSERVATION_MAPPINGS:
            if (
                mapping.production_event_type is event_type
                and mapping.visual_detection_type == visual_detection_type
            ):
                return mapping
        for mapping in VISION_OBSERVATION_MAPPINGS:
            if (
                mapping.production_event_type is event_type
                and mapping.visual_detection_type is None
            ):
                return mapping
        return None

    for mapping in VISION_OBSERVATION_MAPPINGS:
        if mapping.production_event_type is event_type:
            return mapping
    return None
