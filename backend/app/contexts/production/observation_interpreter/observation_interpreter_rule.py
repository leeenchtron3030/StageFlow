from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.contexts.production.observation.observation_type import ObservationType
from app.contexts.production.production_event.production_event_source import (
    ProductionEventSource,
)
from app.contexts.production.production_event.production_event_type import ProductionEventType
from app.shared.ids import EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class ObservationInterpreterRule:
    """Declarative description of what an Observation Interpreter translates."""

    id: EntityId
    supported_event_types: Sequence[ProductionEventType]
    supported_event_sources: Sequence[ProductionEventSource]
    intended_observation_types: Sequence[ObservationType]
    description: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "supported_event_types", tuple(self.supported_event_types))
        object.__setattr__(self, "supported_event_sources", tuple(self.supported_event_sources))
        object.__setattr__(
            self,
            "intended_observation_types",
            tuple(self.intended_observation_types),
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
