from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.shared.ids import CorrelationId, EntityId
from app.shared.metadata import freeze_metadata
from app.shared.time import require_aware_datetime


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class ObservationInterpreterContext:
    """Lightweight context available while creating Observations from events."""

    correlation_id: CorrelationId
    current_timestamp: datetime
    recording_block_id: EntityId | None = None
    stage_id: EntityId | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware_datetime(
            self.current_timestamp,
            "ObservationInterpreterContext.current_timestamp",
        )
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
