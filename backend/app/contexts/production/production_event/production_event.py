from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.contexts.production.production_event.production_event_payload import (
    ProductionEventPayload,
)
from app.contexts.production.production_event.production_event_reference import (
    ProductionEventReference,
)
from app.contexts.production.production_event.production_event_source import (
    ProductionEventSource,
)
from app.contexts.production.production_event.production_event_type import ProductionEventType
from app.shared.ids import CorrelationId, EntityId
from app.shared.metadata import freeze_metadata
from app.shared.time import require_aware_datetime


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class ProductionEvent:
    """Source-agnostic runtime input entering StageFlow production."""

    id: EntityId
    event_type: ProductionEventType
    source: ProductionEventSource
    payload: ProductionEventPayload
    correlation_id: CorrelationId
    occurred_at: datetime
    received_at: datetime
    references: Sequence[ProductionEventReference] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)
    notes: str | None = None

    def __post_init__(self) -> None:
        require_aware_datetime(self.occurred_at, "ProductionEvent.occurred_at")
        require_aware_datetime(self.received_at, "ProductionEvent.received_at")
        object.__setattr__(self, "references", tuple(self.references))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

        if self.received_at < self.occurred_at:
            raise ValueError("ProductionEvent received_at must not be earlier than occurred_at.")
