from __future__ import annotations

from dataclasses import dataclass

from app.contexts.production.dispatcher.dispatch_result import DispatchResult
from app.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class DispatchSummary:
    """Lightweight diagnostics for one dispatch result."""

    dispatched_production_event_id: EntityId
    interpreter_count: int
    successful_interpreter_count: int
    declined_interpreter_count: int
    warning_count: int

    @classmethod
    def from_dispatch_result(cls, result: DispatchResult) -> DispatchSummary:
        return cls(
            dispatched_production_event_id=result.source_production_event_id,
            interpreter_count=result.interpreter_count,
            successful_interpreter_count=sum(
                1
                for interpreter_result in result.interpreter_results
                if not interpreter_result.warnings
            ),
            declined_interpreter_count=result.declined_interpreter_count,
            warning_count=len(result.warnings),
        )
