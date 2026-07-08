from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.contexts.production.dispatcher.dispatch_context import DispatchContext
from app.contexts.production.dispatcher.dispatch_result import DispatchResult
from app.contexts.production.dispatcher.dispatch_rule import DispatchRule
from app.contexts.production.interpreter.production_event_interpreter import (
    ProductionEventInterpreter,
)
from app.contexts.production.production_event.production_event import ProductionEvent
from app.shared.ids import EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class ProductionEventDispatcher:
    """In-memory router from Production Events to matching interpreters."""

    id: EntityId
    name: str
    interpreters: Sequence[ProductionEventInterpreter] = field(default_factory=tuple)
    rules: Sequence[DispatchRule] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("ProductionEventDispatcher name must not be empty.")
        object.__setattr__(self, "interpreters", tuple(self.interpreters))
        object.__setattr__(self, "rules", tuple(self.rules))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def matching_interpreters(
        self,
        event: ProductionEvent,
    ) -> tuple[ProductionEventInterpreter, ...]:
        return tuple(
            interpreter for interpreter in self.interpreters if interpreter.can_interpret(event)
        )

    def dispatch(
        self,
        event: ProductionEvent,
        context: DispatchContext,
    ) -> DispatchResult:
        matching_interpreters = self.matching_interpreters(event)
        interpreter_context = context.to_interpreter_context()
        interpreter_results = tuple(
            interpreter.interpret(event, interpreter_context)
            for interpreter in matching_interpreters
        )
        warnings = tuple(
            warning
            for interpreter_result in interpreter_results
            for warning in interpreter_result.warnings
        )

        return DispatchResult(
            source_production_event_id=event.id,
            interpreter_count=len(self.interpreters),
            invoked_interpreter_ids=tuple(
                interpreter.id for interpreter in matching_interpreters
            ),
            interpreter_results=interpreter_results,
            warnings=warnings,
            declined_interpreter_count=len(self.interpreters) - len(matching_interpreters),
            metadata={
                "dispatcher_id": self.id.to_json(),
                "correlation_id": context.correlation_id.to_json(),
            },
        )
