from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from app.contexts.production.observation.observation import Observation
from app.contexts.production.observation.observation_type import ObservationType
from app.contexts.production.observation_interpreter.event_observation_lineage import (
    observation_provenance_from_event,
)
from app.contexts.production.observation_interpreter.observation_interpreter_context import (
    ObservationInterpreterContext,
)
from app.contexts.production.observation_interpreter.observation_interpreter_policy import (
    ObservationInterpreterPolicy,
)
from app.contexts.production.observation_interpreter.observation_interpreter_result import (
    ObservationInterpreterResult,
)
from app.contexts.production.observation_interpreter.observation_interpreter_rule import (
    ObservationInterpreterRule,
)
from app.contexts.production.production_event.production_event import ProductionEvent
from app.contexts.production.production_event.production_event_source import (
    ProductionEventSource,
)
from app.contexts.production.production_event.production_event_type import ProductionEventType
from app.shared.ids import EntityId


class ObservationInterpreterStatus(StrEnum):
    UNKNOWN = "unknown"
    CONFIGURED = "configured"
    READY = "ready"
    ACTIVE = "active"
    DEGRADED = "degraded"
    FAILED = "failed"
    DISABLED = "disabled"
    ARCHIVED = "archived"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


_INTERPRETABLE_STATUSES = {
    ObservationInterpreterStatus.READY,
    ObservationInterpreterStatus.ACTIVE,
    ObservationInterpreterStatus.DEGRADED,
}


@dataclass(frozen=True, slots=True)
class ObservationInterpreter:
    """Contract for translating Production Events into objective Observations."""

    id: EntityId
    name: str
    supported_event_types: Sequence[ProductionEventType]
    supported_event_sources: Sequence[ProductionEventSource]
    intended_observation_types: Sequence[ObservationType]
    status: ObservationInterpreterStatus
    policy: ObservationInterpreterPolicy = field(default_factory=ObservationInterpreterPolicy)
    rules: Sequence[ObservationInterpreterRule] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("ObservationInterpreter name must not be empty.")
        object.__setattr__(self, "supported_event_types", tuple(self.supported_event_types))
        object.__setattr__(self, "supported_event_sources", tuple(self.supported_event_sources))
        object.__setattr__(
            self,
            "intended_observation_types",
            tuple(self.intended_observation_types),
        )
        object.__setattr__(self, "rules", tuple(self.rules))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def supports_event_type(self, event_type: ProductionEventType) -> bool:
        return event_type in self.supported_event_types

    def supports_source(self, source: ProductionEventSource) -> bool:
        return source in self.supported_event_sources

    def can_interpret_event(self, event: ProductionEvent) -> bool:
        return (
            self.status in _INTERPRETABLE_STATUSES
            and self.supports_event_type(event.event_type)
            and self.supports_source(event.source)
        )

    def can_interpret_events(self, events: Sequence[ProductionEvent]) -> bool:
        return bool(events) and all(self.can_interpret_event(event) for event in events)

    def interpret(
        self,
        events: ProductionEvent | Sequence[ProductionEvent],
        context: ObservationInterpreterContext,
        observations: Sequence[Observation] = (),
    ) -> ObservationInterpreterResult:
        event_tuple = self._event_tuple(events)
        warnings: tuple[str, ...] = ()
        if not self.can_interpret_events(event_tuple):
            warnings = ("ProductionEvent group is not supported by this interpreter.",)

        traced_observations = self._observations_with_traceability(
            observations,
            events=event_tuple,
        )
        self._validate_policy(traced_observations)

        return ObservationInterpreterResult(
            source_production_event_ids=tuple(event.id for event in event_tuple),
            observations=traced_observations,
            interpreter_id=self.id,
            warnings=warnings,
            metadata={
                "correlation_id": context.correlation_id.to_json(),
                "source_event_count": len(event_tuple),
            },
        )

    def _event_tuple(
        self,
        events: ProductionEvent | Sequence[ProductionEvent],
    ) -> tuple[ProductionEvent, ...]:
        if isinstance(events, ProductionEvent):
            return (events,)
        event_tuple = tuple(events)
        if not event_tuple:
            raise ValueError("ObservationInterpreter requires at least one ProductionEvent.")
        return event_tuple

    def _validate_policy(self, observations: Sequence[Observation]) -> None:
        if not observations and not self.policy.allow_zero_observations:
            raise ValueError("ObservationInterpreterPolicy does not allow zero Observations.")
        if len(observations) > 1 and not self.policy.allow_multiple_observations:
            raise ValueError("ObservationInterpreterPolicy does not allow multiple Observations.")

    def _observations_with_traceability(
        self,
        observations: Sequence[Observation],
        events: tuple[ProductionEvent, ...],
    ) -> tuple[Observation, ...]:
        if not self.policy.require_source_event_traceability:
            return tuple(observations)

        source_id_values = tuple(event.id.to_json() for event in events)
        traced_observations: list[Observation] = []
        for observation in observations:
            metadata = dict(observation.metadata)
            metadata["source_production_event_ids"] = source_id_values
            metadata["observation_interpreter_id"] = self.id.to_json()
            provenance = observation.provenance
            if provenance is None and len(events) == 1:
                event = events[0]
                matching_rule = next(
                    (
                        rule
                        for rule in self.rules
                        if event.event_type in rule.supported_event_types
                        and event.source in rule.supported_event_sources
                    ),
                    None,
                )
                provenance = observation_provenance_from_event(
                    event,
                    interpreter_id=self.id,
                    interpreter_kind="generic_observation_interpreter",
                    interpretation_rule_id=(
                        matching_rule.id if matching_rule is not None else None
                    ),
                )
            traced_observations.append(
                replace(
                    observation,
                    metadata=metadata,
                    provenance=provenance,
                )
            )
        return tuple(traced_observations)
