from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from app.contexts.production.session_window_product.session_window_product_boundary import (
    SessionWindowProductBoundary,
)
from app.contexts.production.session_window_product.session_window_product_lineage import (
    SessionWindowProductLineage,
)
from app.contexts.production.session_window_product.session_window_product_status import (
    SessionWindowProductStatus,
)
from app.contexts.production.timeline.schedule_reference import ScheduleReference
from app.contexts.production.timeline.timeline_range import TimelineRange
from app.shared.ids import CorrelationId, EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class SessionWindowProduct:
    """Verified production-media window for a scheduled session."""

    id: EntityId
    operational_product_id: EntityId
    recording_block_id: EntityId
    schedule_reference: ScheduleReference
    timeline_range: TimelineRange
    product_status: SessionWindowProductStatus
    boundary: SessionWindowProductBoundary
    lineage: SessionWindowProductLineage
    correlation_id: CorrelationId
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    notes: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

        if self.timeline_range.recording_block_id != self.recording_block_id:
            raise ValueError(
                "SessionWindowProduct timeline_range must belong to recording_block_id."
            )
        if self.lineage.originating_operational_product_id != self.operational_product_id:
            raise ValueError(
                "SessionWindowProduct lineage must reference operational_product_id."
            )
