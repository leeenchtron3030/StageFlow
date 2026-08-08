from __future__ import annotations

from dataclasses import dataclass

from app.contexts.production.dispatcher.dispatch_result import (
    DispatchResult,
    interpreter_status_semantics,
)
from app.contexts.production.interpreter.interpreter_status import InterpreterStatus
from app.shared.ids import EntityId


def _is_clean_success(
    interpreter_status: InterpreterStatus,
    has_warnings: bool,
) -> bool:
    semantics = interpreter_status_semantics(interpreter_status)
    return semantics.successful and not semantics.warning and not has_warnings


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
                if _is_clean_success(
                    interpreter_result.interpreter_status,
                    bool(interpreter_result.warnings),
                )
            ),
            declined_interpreter_count=result.declined_interpreter_count,
            warning_count=len(result.warnings),
        )
