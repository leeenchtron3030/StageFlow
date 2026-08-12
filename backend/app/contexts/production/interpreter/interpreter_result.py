from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.contexts.production.interpreter.interpreter_status import InterpreterStatus
from app.contexts.production.observation.observation import Observation
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class InterpreterResult:
    """Result of translating one Production Event into zero or more Observations."""

    source_production_event_id: EntityId
    observations: Sequence[Observation]
    interpreter_status: InterpreterStatus
    warnings: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "observations", tuple(self.observations))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
