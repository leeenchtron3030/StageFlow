from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
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
from app.shared.metadata import freeze_metadata
from app.shared.time import require_aware_datetime


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
    created_at: datetime
    notes: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware_datetime(self.created_at, "SessionWindowProduct.created_at")
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

        if self.timeline_range.recording_block_id != self.recording_block_id:
            raise ValueError(
                "SessionWindowProduct timeline_range must belong to recording_block_id."
            )
        if self.lineage.originating_operational_product_id != self.operational_product_id:
            raise ValueError(
                "SessionWindowProduct lineage must reference operational_product_id."
            )
