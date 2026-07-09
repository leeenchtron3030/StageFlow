from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from app.contexts.production.observation.observation_confidence import ObservationConfidence
from app.contexts.production.observation.observation_location import ObservationLocation
from app.contexts.production.observation.observation_source import ObservationSource
from app.contexts.production.observation.observation_type import ObservationType
from app.shared.ids import CorrelationId, EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class Observation:
    """A timestamped statement about something objectively noticed."""

    id: EntityId
    recording_block_id: EntityId | None
    observation_type: ObservationType
    observation_source: ObservationSource
    location: ObservationLocation
    confidence: ObservationConfidence
    correlation_id: CorrelationId
    observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    actor: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)
    notes: str | None = None

    def __post_init__(self) -> None:
        location_recording_block_id = self.location.recording_block_id
        if self.recording_block_id is None and location_recording_block_id is not None:
            object.__setattr__(self, "recording_block_id", location_recording_block_id)
        elif (
            self.recording_block_id is not None
            and location_recording_block_id is not None
            and location_recording_block_id != self.recording_block_id
        ):
            raise ValueError("Observation location must belong to recording_block_id.")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
