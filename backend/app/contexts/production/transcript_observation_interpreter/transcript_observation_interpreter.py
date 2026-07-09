from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.contexts.production.observation import (
    Observation,
    ObservationConfidence,
    ObservationLocation,
    ObservationSource,
    ObservationType,
)
from app.contexts.production.observation_interpreter import (
    ObservationInterpreter,
    ObservationInterpreterContext,
    ObservationInterpreterPolicy,
    ObservationInterpreterResult,
    ObservationInterpreterStatus,
)
from app.contexts.production.production_event import (
    ProductionEvent,
    ProductionEventReferenceType,
    ProductionEventSource,
    ProductionEventType,
)
from app.shared.ids import EntityId

from .transcript_interpreter_rule import TranscriptInterpreterRule
from .transcript_observation_mapping import (
    TRANSCRIPT_OBSERVATION_MAPPINGS,
    TranscriptObservationMapping,
    mapping_for_transcript,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


_INTERPRETABLE_STATUSES = {
    ObservationInterpreterStatus.READY,
    ObservationInterpreterStatus.ACTIVE,
    ObservationInterpreterStatus.DEGRADED,
}


@dataclass(frozen=True, slots=True)
class TranscriptObservationInterpreter:
    """Concrete interpreter for objective transcript observations."""

    id: EntityId
    name: str = "Transcript observation interpreter"
    status: ObservationInterpreterStatus = ObservationInterpreterStatus.ACTIVE
    policy: ObservationInterpreterPolicy = field(default_factory=ObservationInterpreterPolicy)
    mappings: Sequence[TranscriptObservationMapping] = field(
        default_factory=lambda: TRANSCRIPT_OBSERVATION_MAPPINGS
    )
    rules: Sequence[TranscriptInterpreterRule] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("TranscriptObservationInterpreter name must not be empty.")
        object.__setattr__(self, "mappings", tuple(self.mappings))
        object.__setattr__(self, "rules", tuple(self.rules))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def supported_event_types(self) -> tuple[ProductionEventType, ...]:
        return tuple(dict.fromkeys(mapping.production_event_type for mapping in self.mappings))

    @property
    def supported_event_sources(self) -> tuple[ProductionEventSource, ...]:
        return (ProductionEventSource.TRANSCRIPT_SYSTEM,)

    @property
    def intended_observation_types(self) -> tuple[ObservationType, ...]:
        return (ObservationType.TRANSCRIPT_ACTIVITY,)

    def supports_event_type(self, event_type: ProductionEventType) -> bool:
        return event_type in self.supported_event_types

    def supports_source(self, source: ProductionEventSource) -> bool:
        return source in self.supported_event_sources

    def can_interpret_event(self, event: ProductionEvent) -> bool:
        return (
            self.status in _INTERPRETABLE_STATUSES
            and self.supports_event_type(event.event_type)
            and self.supports_source(event.source)
            and self._mapping_for_event(event) is not None
        )

    def can_interpret_events(self, events: Sequence[ProductionEvent]) -> bool:
        return bool(events) and all(self.can_interpret_event(event) for event in events)

    def interpret(
        self,
        events: ProductionEvent | Sequence[ProductionEvent],
        context: ObservationInterpreterContext,
    ) -> ObservationInterpreterResult:
        event_tuple = self._event_tuple(events)
        observations = tuple(
            observation
            for event in event_tuple
            for observation in self._observation_for_event(event, context)
        )

        return self._base_interpreter().interpret(
            event_tuple,
            context,
            observations=observations,
        )

    def _base_interpreter(self) -> ObservationInterpreter:
        return ObservationInterpreter(
            id=self.id,
            name=self.name,
            supported_event_types=self.supported_event_types,
            supported_event_sources=self.supported_event_sources,
            intended_observation_types=self.intended_observation_types,
            status=self.status,
            policy=self.policy,
            rules=tuple(rule.to_observation_interpreter_rule() for rule in self.rules),
            metadata=self.metadata,
        )

    def _event_tuple(
        self,
        events: ProductionEvent | Sequence[ProductionEvent],
    ) -> tuple[ProductionEvent, ...]:
        if isinstance(events, ProductionEvent):
            return (events,)
        event_tuple = tuple(events)
        if not event_tuple:
            raise ValueError(
                "TranscriptObservationInterpreter requires at least one ProductionEvent."
            )
        return event_tuple

    def _observation_for_event(
        self,
        event: ProductionEvent,
        context: ObservationInterpreterContext,
    ) -> tuple[Observation, ...]:
        mapping = self._mapping_for_event(event)
        if mapping is None:
            return ()

        recording_block_id = self._recording_block_id(event, context)
        return (
            Observation(
                id=EntityId.new(),
                recording_block_id=recording_block_id,
                observation_type=ObservationType.TRANSCRIPT_ACTIVITY,
                observation_source=ObservationSource.TRANSCRIPT,
                location=self._location_for_event(event, recording_block_id),
                confidence=ObservationConfidence(1.0),
                correlation_id=event.correlation_id,
                observed_at=context.current_timestamp,
                metadata={
                    "language_is_not_meaning": True,
                    "transcript_lifecycle": mapping.transcript_lifecycle,
                    "transcript_segment_id": event.payload.get("transcript_segment_id"),
                    "transcript_artifact_type": event.payload.get("transcript_artifact_type"),
                    "transcript_segment_status": event.payload.get(
                        "transcript_segment_status"
                    ),
                    "timeline_range_reference": event.payload.get(
                        "timeline_range_reference"
                    ),
                    "language_label": event.payload.get("language_label"),
                    "text_excerpt": event.payload.get("text_excerpt"),
                    "confidence": event.payload.get("confidence"),
                },
                notes=mapping.observation_note,
            ),
        )

    def _mapping_for_event(
        self,
        event: ProductionEvent,
    ) -> TranscriptObservationMapping | None:
        if not self.supports_event_type(event.event_type) or not self.supports_source(
            event.source
        ):
            return None

        mapping = mapping_for_transcript(event.event_type)
        if mapping is not None and mapping.requires_transcript_metadata:
            if event.metadata.get("transcript_adapter_event") is not True:
                return None
        return mapping

    def _recording_block_id(
        self,
        event: ProductionEvent,
        context: ObservationInterpreterContext,
    ) -> EntityId | None:
        for reference in event.references:
            if reference.reference_type is ProductionEventReferenceType.RECORDING_BLOCK:
                return reference.referenced_id
        return context.recording_block_id

    def _location_for_event(
        self,
        event: ProductionEvent,
        recording_block_id: EntityId | None,
    ) -> ObservationLocation:
        if recording_block_id is not None:
            return ObservationLocation.for_recording_block(recording_block_id)
        return ObservationLocation.at_wall_clock(event.occurred_at)
