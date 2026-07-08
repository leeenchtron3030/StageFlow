from dataclasses import fields
from datetime import UTC, datetime, timedelta

import pytest

from app.contexts.production.session_window_product import (
    ScheduleReferenceSummary,
    SessionWindowProduct,
    SessionWindowProductBoundary,
    SessionWindowProductLineage,
    SessionWindowProductStatus,
    SessionWindowProductSummary,
    TimelineRangeSummary,
)
from app.contexts.production.timeline import ScheduleReference, TimelinePosition, TimelineRange
from app.shared.ids import CorrelationId, EntityId


def _timeline_range(recording_block_id: EntityId) -> TimelineRange:
    return TimelineRange(
        start=TimelinePosition(recording_block_id, timedelta(minutes=4, seconds=32)),
        end=TimelinePosition(recording_block_id, timedelta(minutes=35, seconds=18)),
    )


def _schedule_reference() -> ScheduleReference:
    return ScheduleReference(
        external_system_id=EntityId.new(),
        external_schedule_id="schedule-session-123",
        external_version="revision-2",
        source_label="Published schedule",
    )


def _lineage(operational_product_id: EntityId) -> SessionWindowProductLineage:
    return SessionWindowProductLineage(
        originating_finding_ids=[EntityId.new()],
        originating_verification_decision_ids=[EntityId.new()],
        originating_operational_product_id=operational_product_id,
        source_label="accepted session boundary",
    )


def _product() -> SessionWindowProduct:
    recording_block_id = EntityId.new()
    operational_product_id = EntityId.new()
    return SessionWindowProduct(
        id=EntityId.new(),
        operational_product_id=operational_product_id,
        recording_block_id=recording_block_id,
        schedule_reference=_schedule_reference(),
        timeline_range=_timeline_range(recording_block_id),
        product_status=SessionWindowProductStatus.ACTIVE,
        boundary=SessionWindowProductBoundary(0.8, 0.9),
        lineage=_lineage(operational_product_id),
        correlation_id=CorrelationId.new(),
        created_at=datetime(2026, 7, 8, 12, 0, tzinfo=UTC),
        metadata={"quality": "reviewed"},
        notes="Verified product window.",
    )


def test_session_window_product_creation() -> None:
    product = _product()

    assert product.product_status is SessionWindowProductStatus.ACTIVE
    assert product.timeline_range.recording_block_id == product.recording_block_id
    assert product.lineage.originating_operational_product_id == product.operational_product_id
    assert dict(product.metadata) == {"quality": "reviewed"}


def test_product_references_operational_product_id_only() -> None:
    product = _product()
    field_names = {field.name for field in fields(SessionWindowProduct)}

    assert product.operational_product_id == product.lineage.originating_operational_product_id
    assert "operational_product_id" in field_names
    assert "operational_product" not in field_names


def test_product_references_schedule_reference() -> None:
    product = _product()

    assert isinstance(product.schedule_reference, ScheduleReference)
    assert product.schedule_reference.external_schedule_id == "schedule-session-123"


def test_product_references_timeline_range() -> None:
    product = _product()

    assert isinstance(product.timeline_range, TimelineRange)
    assert product.timeline_range.duration == timedelta(minutes=30, seconds=46)


def test_product_rejects_timeline_range_from_different_recording_block() -> None:
    operational_product_id = EntityId.new()

    with pytest.raises(ValueError, match="timeline_range"):
        SessionWindowProduct(
            id=EntityId.new(),
            operational_product_id=operational_product_id,
            recording_block_id=EntityId.new(),
            schedule_reference=_schedule_reference(),
            timeline_range=_timeline_range(EntityId.new()),
            product_status=SessionWindowProductStatus.CREATED,
            boundary=SessionWindowProductBoundary(0.5, 0.5),
            lineage=_lineage(operational_product_id),
            correlation_id=CorrelationId.new(),
        )


def test_product_rejects_lineage_for_different_operational_product() -> None:
    recording_block_id = EntityId.new()

    with pytest.raises(ValueError, match="lineage"):
        SessionWindowProduct(
            id=EntityId.new(),
            operational_product_id=EntityId.new(),
            recording_block_id=recording_block_id,
            schedule_reference=_schedule_reference(),
            timeline_range=_timeline_range(recording_block_id),
            product_status=SessionWindowProductStatus.CREATED,
            boundary=SessionWindowProductBoundary(0.5, 0.5),
            lineage=_lineage(EntityId.new()),
            correlation_id=CorrelationId.new(),
        )


def test_session_window_product_status_allowed_values() -> None:
    assert {status.value for status in SessionWindowProductStatus} == {
        "created",
        "active",
        "ready_for_package",
        "completed",
        "cancelled",
        "superseded",
        "archived",
    }


def test_boundary_confidence_accepts_zero_and_one() -> None:
    boundary = SessionWindowProductBoundary(start_confidence=0.0, end_confidence=1.0)

    assert boundary.start_confidence == 0.0
    assert boundary.end_confidence == 1.0


def test_boundary_confidence_rejects_below_zero() -> None:
    with pytest.raises(ValueError, match="start_confidence"):
        SessionWindowProductBoundary(start_confidence=-0.01, end_confidence=0.5)


def test_boundary_confidence_rejects_above_one() -> None:
    with pytest.raises(ValueError, match="end_confidence"):
        SessionWindowProductBoundary(start_confidence=0.5, end_confidence=1.01)


def test_lineage_references_finding_ids() -> None:
    finding_id = EntityId.new()
    lineage = SessionWindowProductLineage(
        originating_finding_ids=[finding_id],
        originating_verification_decision_ids=[],
        originating_operational_product_id=EntityId.new(),
    )

    assert lineage.originating_finding_ids == (finding_id,)
    assert "findings" not in {field.name for field in fields(SessionWindowProductLineage)}


def test_lineage_references_verification_decision_ids() -> None:
    decision_id = EntityId.new()
    lineage = SessionWindowProductLineage(
        originating_finding_ids=[],
        originating_verification_decision_ids=[decision_id],
        originating_operational_product_id=EntityId.new(),
    )

    assert lineage.originating_verification_decision_ids == (decision_id,)
    assert "verification_decisions" not in {
        field.name for field in fields(SessionWindowProductLineage)
    }


def test_lineage_requires_at_least_one_reasoning_reference() -> None:
    with pytest.raises(ValueError, match="requires at least one"):
        SessionWindowProductLineage(
            originating_finding_ids=[],
            originating_verification_decision_ids=[],
            originating_operational_product_id=EntityId.new(),
        )


def test_summary_generation() -> None:
    product = _product()

    summary = SessionWindowProductSummary.from_session_window_product(product)

    assert summary.session_window_product_id == product.id
    assert summary.operational_product_id == product.operational_product_id
    assert summary.recording_block_id == product.recording_block_id
    assert summary.product_status is SessionWindowProductStatus.ACTIVE
    assert isinstance(summary.timeline_range_summary, TimelineRangeSummary)
    assert summary.timeline_range_summary.duration == product.timeline_range.duration
    assert isinstance(summary.schedule_reference_summary, ScheduleReferenceSummary)
    assert (
        summary.schedule_reference_summary.external_schedule_id
        == product.schedule_reference.external_schedule_id
    )
    assert summary.start_boundary_confidence == 0.8
    assert summary.end_boundary_confidence == 0.9
    assert summary.originating_finding_count == 1
    assert summary.originating_verification_decision_count == 1


def test_no_session_aggregate_behavior() -> None:
    field_names = {field.name for field in fields(SessionWindowProduct)}
    forbidden_terms = {
        "session_id",
        "session_title",
        "session_metadata",
        "speaker",
        "scheduled_start",
        "scheduled_end",
        "schedule_sync",
    }

    assert not any(term in field_name for field_name in field_names for term in forbidden_terms)


def test_no_file_path_or_media_chunk_behavior() -> None:
    contract_fields = {
        field.name
        for contract in (
            SessionWindowProduct,
            SessionWindowProductBoundary,
            SessionWindowProductLineage,
            SessionWindowProductSummary,
            TimelineRangeSummary,
            ScheduleReferenceSummary,
        )
        for field in fields(contract)
    }
    forbidden_terms = {
        "file",
        "path",
        "chunk",
        "codec",
        "source_file",
        "media_id",
        "transcript",
    }

    assert not any(term in field_name for field_name in contract_fields for term in forbidden_terms)


def test_no_package_generation_behavior() -> None:
    field_names = {
        field.name
        for contract in (SessionWindowProduct, SessionWindowProductSummary)
        for field in fields(contract)
    }
    forbidden_terms = {
        "package_id",
        "package_manifest",
        "clip",
        "render",
        "generate",
        "workflow",
        "queue",
        "worker",
    }

    assert not any(term in field_name for field_name in field_names for term in forbidden_terms)


def test_no_provider_specific_names() -> None:
    enum_values = {status.value for status in SessionWindowProductStatus}
    field_names = {
        field.name
        for contract in (
            SessionWindowProduct,
            SessionWindowProductBoundary,
            SessionWindowProductLineage,
            SessionWindowProductSummary,
            TimelineRangeSummary,
            ScheduleReferenceSummary,
        )
        for field in fields(contract)
    }
    forbidden_terms = {
        "provider",
        "vendor",
        "brand",
        "conference",
        "pretalx",
    }

    assert not any(term in value for value in enum_values for term in forbidden_terms)
    assert not any(term in field_name for field_name in field_names for term in forbidden_terms)
