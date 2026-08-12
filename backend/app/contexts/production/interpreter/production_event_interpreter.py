from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.contexts.production.interpreter.interpreter_context import InterpreterContext
from app.contexts.production.interpreter.interpreter_result import InterpreterResult
from app.contexts.production.interpreter.interpreter_rule import InterpreterRule
from app.contexts.production.interpreter.interpreter_status import InterpreterStatus
from app.contexts.production.production_event.production_event import ProductionEvent
from app.contexts.production.production_event.production_event_source import (
    ProductionEventSource,
)
from app.contexts.production.production_event.production_event_type import ProductionEventType
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata


def _empty_metadata() -> Mapping[str, Any]:
    return {}


_INTERPRETABLE_STATUSES = {
    InterpreterStatus.READY,
    InterpreterStatus.ACTIVE,
    InterpreterStatus.DEGRADED,
    InterpreterStatus.EXPERIMENTAL,
}


@dataclass(frozen=True, slots=True)
class ProductionEventInterpreter:
    """Generic contract for translating Production Events into Observations."""

    id: EntityId
    name: str
    supported_event_types: Sequence[ProductionEventType]
    supported_event_sources: Sequence[ProductionEventSource]
    status: InterpreterStatus
    rules: Sequence[InterpreterRule] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("ProductionEventInterpreter name must not be empty.")
        object.__setattr__(self, "supported_event_types", tuple(self.supported_event_types))
        object.__setattr__(self, "supported_event_sources", tuple(self.supported_event_sources))
        object.__setattr__(self, "rules", tuple(self.rules))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def supports_event_type(self, event_type: ProductionEventType) -> bool:
        return event_type in self.supported_event_types

    def supports_source(self, source: ProductionEventSource) -> bool:
        return source in self.supported_event_sources

    def can_interpret(self, event: ProductionEvent) -> bool:
        return (
            self.status in _INTERPRETABLE_STATUSES
            and self.supports_event_type(event.event_type)
            and self.supports_source(event.source)
        )

    def interpret(
        self,
        event: ProductionEvent,
        context: InterpreterContext,
    ) -> InterpreterResult:
        warnings = ()
        if not self.can_interpret(event):
            warnings = ("ProductionEvent is not supported by this interpreter.",)

        return InterpreterResult(
            source_production_event_id=event.id,
            observations=(),
            interpreter_status=self.status,
            warnings=warnings,
            metadata={"correlation_id": context.correlation_id.to_json()},
        )
