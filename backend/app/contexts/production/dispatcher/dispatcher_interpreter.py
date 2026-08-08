from __future__ import annotations

from typing import Protocol

from app.contexts.production.interpreter import InterpreterContext, InterpreterResult
from app.contexts.production.production_event import ProductionEvent
from app.shared.ids import EntityId


class DispatcherInterpreter(Protocol):
    """Minimal structural contract required by ProductionEventDispatcher."""

    @property
    def id(self) -> EntityId: ...

    def can_interpret(self, event: ProductionEvent) -> bool: ...

    def interpret(
        self,
        event: ProductionEvent,
        context: InterpreterContext,
    ) -> InterpreterResult: ...
