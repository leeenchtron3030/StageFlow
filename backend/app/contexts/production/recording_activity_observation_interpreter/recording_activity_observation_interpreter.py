from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
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
from app.contexts.production.timeline import TimelinePosition
from app.shared.ids import EntityId

from .recording_activity_interpreter_rule import (
    RecordingActivityInterpreterRule,
)
from .recording_activity_observation_mapping import (
    RECORDING_ACTIVITY_OBSERVATION_MAPPINGS,
    RecordingActivityObservationMapping,
    mapping_for_recording_activity,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


_INTERPRETABLE_STATUSES = {
    ObservationInterpreterStatus.READY,
    ObservationInterpreterStatus.ACTIVE,
    ObservationInterpreterStatus.DEGRADED,
}


@dataclass(frozen=True, slots=True)
class RecordingActivityObservationInterpreter:
    """Concrete interpreter for objective recording activity observations."""

    id: EntityId
    name: str = "Recording activity observation interpreter"
    status: ObservationInterpreterStatus = ObservationInterpreterStatus.ACTIVE
    policy: ObservationInterpreterPolicy = field(default_factory=ObservationInterpreterPolicy)
    mappings: Sequence[RecordingActivityObservationMapping] = field(
        default_factory=lambda: RECORDING_ACTIVITY_OBSERVATION_MAPPINGS
    )
    rules: Sequence[RecordingActivityInterpreterRule] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("RecordingActivityObservationInterpreter name must not be empty.")
        object.__setattr__(self, "mappings", tuple(self.mappings))
        object.__setattr__(self, "rules", tuple(self.rules))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def supported_event_types(self) -> tuple[ProductionEventType, ...]:
        return tuple(dict.fromkeys(mapping.production_event_type for mapping in self.mappings))

    @property
    def supported_event_sources(self) -> tuple[ProductionEventSource, ...]:
        return (ProductionEventSource.RECORDING_SYSTEM,)

    @property
    def intended_observation_types(self) -> tuple[ObservationType, ...]:
        return (ObservationType.RECORDING_ACTIVITY,)

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
                "RecordingActivityObservationInterpreter requires at least one ProductionEvent."
            )
        return event_tuple

    def _observation_for_event(
        self,
        event: ProductionEvent,
        context: ObservationInterpreterContext,
    ) -> tuple[Observation, ...]:
        mapping = self._mapping_for_event(event)
        recording_block_id = self._recording_block_id(event, context)
        if mapping is None or recording_block_id is None:
            return ()

        return (
            Observation(
                id=EntityId.new(),
                recording_block_id=recording_block_id,
                observation_type=ObservationType.RECORDING_ACTIVITY,
                observation_source=ObservationSource.SYSTEM,
                location=ObservationLocation.at_point(
                    TimelinePosition(recording_block_id, timedelta(0))
                ),
                confidence=ObservationConfidence(1.0),
                correlation_id=event.correlation_id,
                observed_at=context.current_timestamp,
                metadata={
                    "recording_activity": mapping.activity_label,
                    "recording_event_kind": mapping.recording_event_kind,
                },
                notes=mapping.observation_note,
            ),
        )

    def _mapping_for_event(
        self,
        event: ProductionEvent,
    ) -> RecordingActivityObservationMapping | None:
        if not self.supports_event_type(event.event_type) or not self.supports_source(
            event.source
        ):
            return None

        return mapping_for_recording_activity(
            event.event_type,
            event.payload.get("recording_event_kind"),
        )

    def _recording_block_id(
        self,
        event: ProductionEvent,
        context: ObservationInterpreterContext,
    ) -> EntityId | None:
        for reference in event.references:
            if reference.reference_type is ProductionEventReferenceType.RECORDING_BLOCK:
                return reference.referenced_id
        return context.recording_block_id
