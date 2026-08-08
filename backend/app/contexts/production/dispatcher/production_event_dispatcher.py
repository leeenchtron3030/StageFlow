from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.contexts.production.dispatcher.dispatch_context import DispatchContext
from app.contexts.production.dispatcher.dispatch_result import (
    DispatchResult,
    interpreter_status_semantics,
)
from app.contexts.production.dispatcher.dispatch_rule import DispatchRule
from app.contexts.production.dispatcher.dispatcher_interpreter import DispatcherInterpreter
from app.contexts.production.dispatcher.interpreter_support_failure import (
    InterpreterSupportFailure,
)
from app.contexts.production.interpreter import InterpreterResult, InterpreterStatus
from app.contexts.production.production_event.production_event import ProductionEvent
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class ProductionEventDispatcher:
    """In-memory router from Production Events to matching interpreters."""

    id: EntityId
    name: str
    interpreters: Sequence[DispatcherInterpreter] = field(default_factory=tuple)
    rules: Sequence[DispatchRule] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("ProductionEventDispatcher name must not be empty.")
        object.__setattr__(self, "interpreters", tuple(self.interpreters))
        object.__setattr__(self, "rules", tuple(self.rules))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def matching_interpreters(
        self,
        event: ProductionEvent,
    ) -> tuple[DispatcherInterpreter, ...]:
        return tuple(
            interpreter for interpreter in self.interpreters if interpreter.can_interpret(event)
        )

    def dispatch(
        self,
        event: ProductionEvent,
        context: DispatchContext,
    ) -> DispatchResult:
        interpreter_context = context.to_interpreter_context()
        matching_interpreters: list[DispatcherInterpreter] = []
        interpreter_results_list: list[InterpreterResult] = []
        support_failures: list[InterpreterSupportFailure] = []
        warnings_list: list[str] = []
        declined_interpreter_count = 0
        for interpreter in self.interpreters:
            try:
                supports_event = interpreter.can_interpret(event)
            except Exception as error:
                failure_code = f"support_evaluation_exception:{type(error).__name__}"
                warning = f"Interpreter support evaluation failure: {failure_code}."
                support_failures.append(
                    InterpreterSupportFailure(
                        interpreter_id=interpreter.id,
                        failure_code=failure_code,
                        warning=warning,
                    )
                )
                warnings_list.append(warning)
                continue
            if not supports_event:
                declined_interpreter_count += 1
                continue

            matching_interpreters.append(interpreter)
            try:
                result = interpreter.interpret(event, interpreter_context)
            except Exception as error:
                failure_code = f"interpreter_exception:{type(error).__name__}"
                result = InterpreterResult(
                    source_production_event_id=event.id,
                    observations=(),
                    interpreter_status=InterpreterStatus.FAILED,
                    warnings=(f"Interpreter dispatch failure: {failure_code}.",),
                    metadata={"failure_code": failure_code},
                )
            else:
                semantics = interpreter_status_semantics(result.interpreter_status)
                if not semantics.supported:
                    result = self._failed_result(event, "unsupported_interpreter_status")
                elif (
                    result.interpreter_status is InterpreterStatus.FAILED
                    and not result.observations
                ):
                    pass
                elif not semantics.observations_survive:
                    result = self._failed_result(
                        event,
                        f"non_interpretable_status:{result.interpreter_status.value}",
                    )
            interpreter_results_list.append(result)
            warnings_list.extend(result.warnings)
        interpreter_results = tuple(interpreter_results_list)

        return DispatchResult(
            source_production_event_id=event.id,
            interpreter_count=len(self.interpreters),
            invoked_interpreter_ids=tuple(
                interpreter.id for interpreter in matching_interpreters
            ),
            interpreter_results=interpreter_results,
            warnings=tuple(warnings_list),
            declined_interpreter_count=declined_interpreter_count,
            support_failures=tuple(support_failures),
            metadata={
                "dispatcher_id": self.id.to_json(),
                "correlation_id": context.correlation_id.to_json(),
            },
        )

    @staticmethod
    def _failed_result(event: ProductionEvent, failure_code: str) -> InterpreterResult:
        return InterpreterResult(
            source_production_event_id=event.id,
            observations=(),
            interpreter_status=InterpreterStatus.FAILED,
            warnings=(f"Interpreter dispatch failure: {failure_code}.",),
            metadata={"failure_code": failure_code},
        )
