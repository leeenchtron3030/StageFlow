from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.contexts.production.observation.observation_type import ObservationType
from app.contexts.production.observation_interpreter.observation_interpreter_rule import (
    ObservationInterpreterRule,
)
from app.contexts.production.production_event.production_event_source import (
    ProductionEventSource,
)
from app.contexts.production.production_event.production_event_type import ProductionEventType
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata

from .runtime_clock_observation_mapping import (
    RUNTIME_CLOCK_OBSERVATION_MAPPINGS,
    RuntimeClockObservationMapping,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RuntimeClockInterpreterRule:
    """Declarative rule for translating runtime clock events into observations."""

    id: EntityId
    mappings: Sequence[RuntimeClockObservationMapping] = field(
        default_factory=lambda: RUNTIME_CLOCK_OBSERVATION_MAPPINGS
    )
    description: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "mappings", tuple(self.mappings))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    @property
    def supported_event_types(self) -> tuple[ProductionEventType, ...]:
        return tuple(dict.fromkeys(mapping.production_event_type for mapping in self.mappings))

    @property
    def supported_event_sources(self) -> tuple[ProductionEventSource, ...]:
        return (ProductionEventSource.TIMER,)

    @property
    def intended_observation_types(self) -> tuple[ObservationType, ...]:
        return (ObservationType.TIME_BOUNDARY,)

    def to_observation_interpreter_rule(self) -> ObservationInterpreterRule:
        return ObservationInterpreterRule(
            id=self.id,
            supported_event_types=self.supported_event_types,
            supported_event_sources=self.supported_event_sources,
            intended_observation_types=self.intended_observation_types,
            description=self.description,
            metadata=self.metadata,
        )
