from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.contexts.production.observation_interpreter.observation_interpreter import (
    ObservationInterpreterStatus,
)
from app.shared.ids import EntityId

if TYPE_CHECKING:
    from .runtime_clock_observation_interpreter import RuntimeClockObservationInterpreter


@dataclass(frozen=True, slots=True)
class RuntimeClockInterpreterSummary:
    """Lightweight diagnostics for the runtime clock observation interpreter."""

    interpreter_id: EntityId
    interpreter_name: str
    status: ObservationInterpreterStatus
    supported_event_type_count: int
    supported_source_count: int
    intended_observation_type_count: int
    mapping_count: int
    rule_count: int

    @classmethod
    def from_interpreter(
        cls,
        interpreter: RuntimeClockObservationInterpreter,
    ) -> RuntimeClockInterpreterSummary:
        return cls(
            interpreter_id=interpreter.id,
            interpreter_name=interpreter.name,
            status=interpreter.status,
            supported_event_type_count=len(interpreter.supported_event_types),
            supported_source_count=len(interpreter.supported_event_sources),
            intended_observation_type_count=len(interpreter.intended_observation_types),
            mapping_count=len(interpreter.mappings),
            rule_count=len(interpreter.rules),
        )
