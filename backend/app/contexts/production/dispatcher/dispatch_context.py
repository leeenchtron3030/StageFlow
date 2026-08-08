from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.contexts.production.interpreter.interpreter_context import InterpreterContext
from app.shared.ids import CorrelationId, EntityId
from app.shared.metadata import freeze_metadata
from app.shared.time import require_aware_datetime


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class DispatchContext:
    """Lightweight routing context for one Production Event dispatch."""

    correlation_id: CorrelationId
    timestamp: datetime
    stage_id: EntityId | None = None
    recording_block_id: EntityId | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware_datetime(self.timestamp, "DispatchContext.timestamp")
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def to_interpreter_context(self) -> InterpreterContext:
        return InterpreterContext(
            correlation_id=self.correlation_id,
            current_timestamp=self.timestamp,
            recording_block_id=self.recording_block_id,
            stage_id=self.stage_id,
            metadata=self.metadata,
        )
