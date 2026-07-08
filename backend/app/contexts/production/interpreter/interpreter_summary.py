from __future__ import annotations

from dataclasses import dataclass

from app.contexts.production.interpreter.interpreter_status import InterpreterStatus
from app.contexts.production.interpreter.production_event_interpreter import (
    ProductionEventInterpreter,
)
from app.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class InterpreterSummary:
    """Lightweight interpreter description for diagnostics."""

    interpreter_id: EntityId
    name: str
    status: InterpreterStatus
    supported_event_type_count: int
    supported_source_count: int
    rule_count: int

    @classmethod
    def from_interpreter(
        cls,
        interpreter: ProductionEventInterpreter,
    ) -> InterpreterSummary:
        return cls(
            interpreter_id=interpreter.id,
            name=interpreter.name,
            status=interpreter.status,
            supported_event_type_count=len(interpreter.supported_event_types),
            supported_source_count=len(interpreter.supported_event_sources),
            rule_count=len(interpreter.rules),
        )
