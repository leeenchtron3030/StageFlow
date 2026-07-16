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
    observation_context_from_event,
    observation_provenance_from_event,
)
from app.contexts.production.production_event import (
    ProductionEvent,
    ProductionEventSource,
    ProductionEventType,
)
from app.shared.ids import EntityId

from .schedule_interpreter_rule import ScheduleInterpreterRule
from .schedule_observation_mapping import (
    SCHEDULE_OBSERVATION_MAPPINGS,
    ScheduleObservationMapping,
    mapping_for_schedule,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


_INTERPRETABLE_STATUSES = {
    ObservationInterpreterStatus.READY,
    ObservationInterpreterStatus.ACTIVE,
    ObservationInterpreterStatus.DEGRADED,
}


@dataclass(frozen=True, slots=True)
class ScheduleObservationInterpreter:
    """Concrete interpreter for objective schedule observations."""

    id: EntityId
    name: str = "Schedule observation interpreter"
    status: ObservationInterpreterStatus = ObservationInterpreterStatus.ACTIVE
    policy: ObservationInterpreterPolicy = field(default_factory=ObservationInterpreterPolicy)
    mappings: Sequence[ScheduleObservationMapping] = field(
        default_factory=lambda: SCHEDULE_OBSERVATION_MAPPINGS
    )
    rules: Sequence[ScheduleInterpreterRule] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("ScheduleObservationInterpreter name must not be empty.")
        object.__setattr__(self, "mappings", tuple(self.mappings))
        object.__setattr__(self, "rules", tuple(self.rules))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def supported_event_types(self) -> tuple[ProductionEventType, ...]:
        return tuple(dict.fromkeys(mapping.production_event_type for mapping in self.mappings))

    @property
    def supported_event_sources(self) -> tuple[ProductionEventSource, ...]:
        return (ProductionEventSource.SCHEDULE_SYSTEM,)

    @property
    def intended_observation_types(self) -> tuple[ObservationType, ...]:
        return (ObservationType.SCHEDULE_ACTIVITY,)

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
                "ScheduleObservationInterpreter requires at least one ProductionEvent."
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

        observation_context = observation_context_from_event(event, context)
        rule_id = next(
            (rule.id for rule in self.rules if mapping in rule.mappings),
            f"schedule:{event.event_type.value}:{mapping.schedule_lifecycle}",
        )

        return (
            Observation(
                id=EntityId.new(),
                recording_block_id=observation_context.recording_block_id,
                observation_type=ObservationType.SCHEDULE_ACTIVITY,
                observation_source=ObservationSource.SCHEDULE,
                location=self._location_for_event(event),
                confidence=ObservationConfidence(1.0),
                correlation_id=event.correlation_id,
                observed_at=context.current_timestamp,
                metadata={
                    "planned_reality_observation": True,
                    "schedule_lifecycle": mapping.schedule_lifecycle,
                    "scheduled_activity_id": event.payload.get("scheduled_activity_id"),
                    "activity_status": event.payload.get("activity_status"),
                    "activity_type": event.payload.get("activity_type"),
                },
                notes=mapping.observation_note,
                provenance=observation_provenance_from_event(
                    event,
                    interpreter_id=self.id,
                    interpreter_kind="schedule_activity_interpreter",
                    interpretation_rule_id=rule_id,
                ),
                context=observation_context,
            ),
        )

    def _mapping_for_event(
        self,
        event: ProductionEvent,
    ) -> ScheduleObservationMapping | None:
        if not self.supports_event_type(event.event_type) or not self.supports_source(
            event.source
        ):
            return None

        mapping = mapping_for_schedule(
            event.event_type,
            activity_status=event.payload.get("activity_status"),
        )
        if mapping is not None and mapping.requires_schedule_metadata:
            if event.metadata.get("schedule_adapter_event") is not True:
                return None
        return mapping

    def _location_for_event(self, event: ProductionEvent) -> ObservationLocation:
        return ObservationLocation.at_wall_clock(event.occurred_at)
