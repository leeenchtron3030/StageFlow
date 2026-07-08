from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from app.contexts.production.session_window_product.session_window_product import (
    SessionWindowProduct,
)
from app.contexts.production.session_window_product.session_window_product_status import (
    SessionWindowProductStatus,
)
from app.contexts.production.timeline.schedule_reference import ScheduleReference
from app.contexts.production.timeline.timeline_range import TimelineRange
from app.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class TimelineRangeSummary:
    """Lightweight description of a product timeline range."""

    recording_block_id: EntityId
    start_offset: timedelta
    end_offset: timedelta
    duration: timedelta

    @classmethod
    def from_timeline_range(cls, timeline_range: TimelineRange) -> TimelineRangeSummary:
        return cls(
            recording_block_id=timeline_range.recording_block_id,
            start_offset=timeline_range.start.offset,
            end_offset=timeline_range.end.offset,
            duration=timeline_range.duration,
        )


@dataclass(frozen=True, slots=True)
class ScheduleReferenceSummary:
    """Lightweight description of a product schedule reference."""

    external_system_id: EntityId
    external_schedule_id: str
    external_version: str | None
    source_label: str | None

    @classmethod
    def from_schedule_reference(
        cls,
        schedule_reference: ScheduleReference,
    ) -> ScheduleReferenceSummary:
        return cls(
            external_system_id=schedule_reference.external_system_id,
            external_schedule_id=schedule_reference.external_schedule_id,
            external_version=schedule_reference.external_version,
            source_label=schedule_reference.source_label,
        )


@dataclass(frozen=True, slots=True)
class SessionWindowProductSummary:
    """Lightweight session window product representation for future surfaces."""

    session_window_product_id: EntityId
    operational_product_id: EntityId
    recording_block_id: EntityId
    product_status: SessionWindowProductStatus
    timeline_range_summary: TimelineRangeSummary
    schedule_reference_summary: ScheduleReferenceSummary
    start_boundary_confidence: float
    end_boundary_confidence: float
    originating_finding_count: int
    originating_verification_decision_count: int

    @classmethod
    def from_session_window_product(
        cls,
        product: SessionWindowProduct,
    ) -> SessionWindowProductSummary:
        return cls(
            session_window_product_id=product.id,
            operational_product_id=product.operational_product_id,
            recording_block_id=product.recording_block_id,
            product_status=product.product_status,
            timeline_range_summary=TimelineRangeSummary.from_timeline_range(
                product.timeline_range
            ),
            schedule_reference_summary=ScheduleReferenceSummary.from_schedule_reference(
                product.schedule_reference
            ),
            start_boundary_confidence=product.boundary.start_confidence,
            end_boundary_confidence=product.boundary.end_confidence,
            originating_finding_count=len(product.lineage.originating_finding_ids),
            originating_verification_decision_count=len(
                product.lineage.originating_verification_decision_ids
            ),
        )
