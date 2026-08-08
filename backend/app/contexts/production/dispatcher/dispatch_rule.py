from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.contexts.production.production_event.production_event_source import (
    ProductionEventSource,
)
from app.contexts.production.production_event.production_event_type import ProductionEventType
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class DispatchRule:
    """Declarative routing intent for Production Events."""

    id: EntityId
    supported_event_types: Sequence[ProductionEventType]
    supported_event_sources: Sequence[ProductionEventSource]
    target_interpreter_ids: Sequence[EntityId]
    description: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "supported_event_types", tuple(self.supported_event_types))
        object.__setattr__(self, "supported_event_sources", tuple(self.supported_event_sources))
        object.__setattr__(self, "target_interpreter_ids", tuple(self.target_interpreter_ids))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
