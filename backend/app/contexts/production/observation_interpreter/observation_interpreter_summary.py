from __future__ import annotations

from dataclasses import dataclass

from app.contexts.production.observation_interpreter.observation_interpreter import (
    ObservationInterpreter,
    ObservationInterpreterStatus,
)
from app.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class ObservationInterpreterSummary:
    """Lightweight Observation Interpreter diagnostics."""

    interpreter_id: EntityId
    interpreter_name: str
    status: ObservationInterpreterStatus
    supported_event_type_count: int
    supported_source_count: int
    intended_observation_type_count: int
    rule_count: int

    @classmethod
    def from_interpreter(
        cls,
        interpreter: ObservationInterpreter,
    ) -> ObservationInterpreterSummary:
        return cls(
            interpreter_id=interpreter.id,
            interpreter_name=interpreter.name,
            status=interpreter.status,
            supported_event_type_count=len(interpreter.supported_event_types),
            supported_source_count=len(interpreter.supported_event_sources),
            intended_observation_type_count=len(interpreter.intended_observation_types),
            rule_count=len(interpreter.rules),
        )
