from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from app.contexts.production.production_event.production_event_type import ProductionEventType
from app.shared.metadata import freeze_metadata


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RecordingActivityObservationMapping:
    """Declarative mapping from recording activity events to objective observations."""

    recording_event_kind: str
    production_event_type: ProductionEventType
    observation_note: str
    activity_label: str
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.recording_event_kind.strip():
            raise ValueError(
                "RecordingActivityObservationMapping recording_event_kind must not be empty."
            )
        if not self.observation_note.strip():
            raise ValueError(
                "RecordingActivityObservationMapping observation_note must not be empty."
            )
        if not self.activity_label.strip():
            raise ValueError(
                "RecordingActivityObservationMapping activity_label must not be empty."
            )
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))


RECORDING_ACTIVITY_OBSERVATION_MAPPINGS: tuple[
    RecordingActivityObservationMapping,
    ...,
] = (
    RecordingActivityObservationMapping(
        recording_event_kind="recording_started",
        production_event_type=ProductionEventType.RECORDING_BLOCK_STARTED,
        observation_note="recording activity began",
        activity_label="began",
    ),
    RecordingActivityObservationMapping(
        recording_event_kind="recording_paused",
        production_event_type=ProductionEventType.RECORDING_BLOCK_STATUS_CHANGED,
        observation_note="recording activity paused",
        activity_label="paused",
    ),
    RecordingActivityObservationMapping(
        recording_event_kind="recording_resumed",
        production_event_type=ProductionEventType.RECORDING_BLOCK_STATUS_CHANGED,
        observation_note="recording activity resumed",
        activity_label="resumed",
    ),
    RecordingActivityObservationMapping(
        recording_event_kind="recording_stopped",
        production_event_type=ProductionEventType.RECORDING_BLOCK_ENDED,
        observation_note="recording activity ended",
        activity_label="ended",
    ),
)


def mapping_for_recording_activity(
    event_type: ProductionEventType,
    recording_event_kind: str | None,
) -> RecordingActivityObservationMapping | None:
    """Return the objective recording activity mapping for a generic event payload."""

    if recording_event_kind is None:
        return None

    for mapping in RECORDING_ACTIVITY_OBSERVATION_MAPPINGS:
        if (
            mapping.production_event_type is event_type
            and mapping.recording_event_kind == recording_event_kind
        ):
            return mapping
    return None
