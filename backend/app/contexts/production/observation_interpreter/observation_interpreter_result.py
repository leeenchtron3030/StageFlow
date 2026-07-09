from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.contexts.production.observation.observation import Observation
from app.shared.ids import EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class ObservationInterpreterResult:
    """Result of translating Production Events into zero or more Observations."""

    source_production_event_ids: Sequence[EntityId]
    observations: Sequence[Observation]
    interpreter_id: EntityId
    warnings: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_production_event_ids",
            tuple(self.source_production_event_ids),
        )
        object.__setattr__(self, "observations", tuple(self.observations))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

        if not self.source_production_event_ids:
            raise ValueError(
                "ObservationInterpreterResult requires at least one source Production Event ID."
            )
