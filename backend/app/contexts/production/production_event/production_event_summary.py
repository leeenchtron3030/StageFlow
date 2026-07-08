from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.contexts.production.production_event.production_event import ProductionEvent
from app.contexts.production.production_event.production_event_source import (
    ProductionEventSource,
)
from app.contexts.production.production_event.production_event_type import ProductionEventType
from app.shared.ids import CorrelationId, EntityId


@dataclass(frozen=True, slots=True)
class ProductionEventSummary:
    """Lightweight event representation for logs and diagnostics."""

    production_event_id: EntityId
    event_type: ProductionEventType
    source: ProductionEventSource
    occurred_at: datetime
    received_at: datetime
    reference_count: int
    payload_key_count: int
    correlation_id: CorrelationId

    @classmethod
    def from_production_event(cls, event: ProductionEvent) -> ProductionEventSummary:
        return cls(
            production_event_id=event.id,
            event_type=event.event_type,
            source=event.source,
            occurred_at=event.occurred_at,
            received_at=event.received_at,
            reference_count=len(event.references),
            payload_key_count=event.payload.key_count,
            correlation_id=event.correlation_id,
        )
