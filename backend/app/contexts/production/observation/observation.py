from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from app.contexts.production.observation.observation_confidence import ObservationConfidence
from app.contexts.production.observation.observation_context import ObservationContext
from app.contexts.production.observation.observation_location import ObservationLocation
from app.contexts.production.observation.observation_provenance import ObservationProvenance
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
    provenance: ObservationProvenance | None = None
    context: ObservationContext = field(default_factory=ObservationContext.unknown)

    def __post_init__(self) -> None:
        location_recording_block_id = self.location.recording_block_id
        context_recording_block_id = self.context.recording_block_id
        authoritative_recording_block_id = (
            context_recording_block_id
            or self.recording_block_id
            or location_recording_block_id
        )
        if (
            context_recording_block_id is not None
            and self.recording_block_id is not None
            and context_recording_block_id != self.recording_block_id
        ):
            raise ValueError("Observation context must agree with recording_block_id.")
        if (
            authoritative_recording_block_id is not None
            and location_recording_block_id is not None
            and location_recording_block_id != authoritative_recording_block_id
        ):
            raise ValueError("Observation location must belong to recording_block_id.")

        context_stage_id = self.context.stage_id
        if (
            context_stage_id is not None
            and self.location.stage_id is not None
            and context_stage_id != self.location.stage_id
        ):
            raise ValueError("Observation context must agree with location stage_id.")
        if (
            self.context.correlation_id is not None
            and self.context.correlation_id != self.correlation_id
        ):
            raise ValueError("Observation context must agree with correlation_id.")

        object.__setattr__(
            self,
            "recording_block_id",
            authoritative_recording_block_id,
        )
        object.__setattr__(
            self,
            "context",
            replace(
                self.context,
                recording_block_id=authoritative_recording_block_id,
                stage_id=context_stage_id or self.location.stage_id,
                correlation_id=self.context.correlation_id or self.correlation_id,
                timeline_position=(
                    self.context.timeline_position or self.location.point
                ),
                timeline_range=self.context.timeline_range or self.location.range,
            ),
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
