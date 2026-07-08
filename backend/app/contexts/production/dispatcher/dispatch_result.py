from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.contexts.production.interpreter.interpreter_result import InterpreterResult
from app.shared.ids import EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class DispatchResult:
    """Outcome of routing one Production Event to available interpreters."""

    source_production_event_id: EntityId
    interpreter_count: int
    invoked_interpreter_ids: Sequence[EntityId]
    interpreter_results: Sequence[InterpreterResult]
    warnings: Sequence[str] = field(default_factory=tuple)
    declined_interpreter_count: int = 0
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "invoked_interpreter_ids", tuple(self.invoked_interpreter_ids))
        object.__setattr__(self, "interpreter_results", tuple(self.interpreter_results))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

        if self.interpreter_count < 0:
            raise ValueError("DispatchResult interpreter_count must not be negative.")
        if self.declined_interpreter_count < 0:
            raise ValueError("DispatchResult declined_interpreter_count must not be negative.")
        if len(self.invoked_interpreter_ids) != len(self.interpreter_results):
            raise ValueError(
                "DispatchResult invoked_interpreter_ids must match interpreter_results."
            )
