from dataclasses import fields
from datetime import UTC, datetime, timedelta
from inspect import getmembers, isfunction

import pytest

from app.contexts.production.production_event import (
    ProductionEvent,
    ProductionEventReferenceType,
    ProductionEventSource,
    ProductionEventType,
)
from app.contexts.production.schedule_adapter import (
    ScheduleAdapterCapability,
    ScheduleAdapterStatus,
    ScheduleAdapterSummary,
    ScheduledActivity,
    ScheduledActivityIdentity,
    ScheduledActivityStatus,
    ScheduledActivityType,
    ScheduleSourceAdapter,
)
from app.shared.ids import CorrelationId, EntityId


def _identity() -> ScheduledActivityIdentity:
    return ScheduledActivityIdentity(
        activity_title="Opening talk",
        subtitle="Welcome and orientation",
        external_identifier="activity-123",
        organizer_label="Program team",
        metadata={"track": "main"},
    )


def _activity(
    activity_status: ScheduledActivityStatus = ScheduledActivityStatus.SCHEDULED,
) -> ScheduledActivity:
    return ScheduledActivity(
        id=EntityId.new(),
        identity=_identity(),
        activity_type=ScheduledActivityType.PRESENTATION,
        activity_status=activity_status,
        planned_start_at=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
        planned_end_at=datetime(2026, 7, 8, 10, 30, tzinfo=UTC),
        stage_reference="main-stage",
        participant_labels=["Speaker One", "Speaker Two"],
        external_reference="external-activity-123",
        metadata={"published": True},
    )


def _adapter(
    scheduled_activities: list[ScheduledActivity] | None = None,
) -> ScheduleSourceAdapter:
    return ScheduleSourceAdapter(
        id=EntityId.new(),
        adapter_name="Generic schedule adapter",
        status=ScheduleAdapterStatus.READY,
        supported_capabilities=[
            ScheduleAdapterCapability.REPORTS_ACTIVITY_CREATED,
            ScheduleAdapterCapability.REPORTS_ACTIVITY_UPDATED,
            ScheduleAdapterCapability.REPORTS_ACTIVITY_CANCELLED,
        ],
        scheduled_activities=scheduled_activities or [],
        metadata={"scope": "planning"},
    )


def test_schedule_source_adapter_creation() -> None:
    activity = _activity()
    adapter = _adapter(scheduled_activities=[activity])

    assert adapter.adapter_name == "Generic schedule adapter"
    assert adapter.status is ScheduleAdapterStatus.READY
    assert adapter.supports_capability(ScheduleAdapterCapability.REPORTS_ACTIVITY_CREATED)
    assert not adapter.supports_capability(ScheduleAdapterCapability.REPORTS_ACTIVITY_COMPLETED)
    assert adapter.scheduled_activities == (activity,)
    assert dict(adapter.metadata) == {"scope": "planning"}


def test_scheduled_activity_creation() -> None:
    activity = _activity()

    assert activity.activity_title == "Opening talk"
    assert activity.identity.subtitle == "Welcome and orientation"
    assert activity.activity_type is ScheduledActivityType.PRESENTATION
    assert activity.activity_status is ScheduledActivityStatus.SCHEDULED
    assert activity.planned_end_at - activity.planned_start_at == timedelta(minutes=30)
    assert activity.stage_reference == "main-stage"
    assert activity.participant_labels == ("Speaker One", "Speaker Two")
    assert activity.external_reference == "external-activity-123"
    assert dict(activity.metadata) == {"published": True}


def test_scheduled_activity_rejects_invalid_planned_range() -> None:
    with pytest.raises(ValueError, match="planned_end_at"):
        ScheduledActivity(
            id=EntityId.new(),
            identity=_identity(),
            activity_type=ScheduledActivityType.UNKNOWN,
            activity_status=ScheduledActivityStatus.UNKNOWN,
            planned_start_at=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
            planned_end_at=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
        )


def test_scheduled_activity_type_values() -> None:
    assert {activity_type.value for activity_type in ScheduledActivityType} == {
        "presentation",
        "panel",
        "workshop",
        "announcement",
        "music",
        "film",
        "ceremony",
        "networking",
        "meal",
        "break",
        "custom",
        "unknown",
    }


def test_scheduled_activity_status_values() -> None:
    assert {status.value for status in ScheduledActivityStatus} == {
        "scheduled",
        "updated",
        "cancelled",
        "completed",
        "unknown",
    }


def test_scheduled_activity_identity_creation() -> None:
    identity = _identity()

    assert identity.activity_title == "Opening talk"
    assert identity.subtitle == "Welcome and orientation"
    assert identity.external_identifier == "activity-123"
    assert identity.organizer_label == "Program team"
    assert dict(identity.metadata) == {"track": "main"}


def test_schedule_adapter_capability_values() -> None:
    assert {capability.value for capability in ScheduleAdapterCapability} == {
        "reports_activity_created",
        "reports_activity_updated",
        "reports_activity_cancelled",
        "reports_activity_completed",
        "reports_schedule_metadata",
        "unknown",
    }


def test_schedule_adapter_summary_generation() -> None:
    activity = _activity()
    adapter = _adapter(scheduled_activities=[activity])

    summary = ScheduleAdapterSummary.from_adapter(adapter)

    assert summary.adapter_id == adapter.id
    assert summary.adapter_name == adapter.adapter_name
    assert summary.capability_count == 3
    assert summary.activity_count == 1
    assert summary.adapter_status is ScheduleAdapterStatus.READY


def test_helper_production_event_mapping() -> None:
    adapter = _adapter()
    activity = _activity(ScheduledActivityStatus.UPDATED)
    received_at = datetime(2026, 7, 7, 12, 0, tzinfo=UTC)

    production_event = adapter.production_event_from_activity(
        activity,
        correlation_id=CorrelationId.new(),
        received_at=received_at,
    )

    assert isinstance(production_event, ProductionEvent)
    assert production_event.event_type is ProductionEventType.SCHEDULE_ARTIFACT_UPDATED
    assert production_event.source is ProductionEventSource.SCHEDULE_SYSTEM
    assert production_event.occurred_at == received_at
    assert production_event.received_at == received_at
    assert production_event.payload.get("scheduled_activity_id") == activity.id.to_json()
    assert production_event.payload.get("activity_title") == "Opening talk"
    assert production_event.payload.get("activity_type") == "presentation"
    assert production_event.payload.get("activity_status") == "updated"
    assert production_event.payload.get("planned_start_at") == activity.planned_start_at.isoformat()
    assert production_event.payload.get("planned_end_at") == activity.planned_end_at.isoformat()
    assert production_event.payload.get("stage_reference") == "main-stage"
    assert production_event.payload.get("participant_labels") == ("Speaker One", "Speaker Two")
    assert {reference.reference_type for reference in production_event.references} == {
        ProductionEventReferenceType.SCHEDULE_ARTIFACT,
        ProductionEventReferenceType.EXTERNAL_OBJECT,
    }


def test_allowed_production_event_mappings() -> None:
    expected_types = {
        ScheduledActivityStatus.SCHEDULED: ProductionEventType.SCHEDULE_ARTIFACT_UPDATED,
        ScheduledActivityStatus.UPDATED: ProductionEventType.SCHEDULE_ARTIFACT_UPDATED,
        ScheduledActivityStatus.CANCELLED: ProductionEventType.SCHEDULE_ARTIFACT_UPDATED,
        ScheduledActivityStatus.COMPLETED: ProductionEventType.SCHEDULE_ARTIFACT_UPDATED,
        ScheduledActivityStatus.UNKNOWN: ProductionEventType.SYSTEM_STATUS_CHANGED,
    }

    for activity_status, expected_type in expected_types.items():
        activity = _activity(activity_status)
        production_event = activity.to_production_event(
            correlation_id=CorrelationId.new(),
            received_at=datetime(2026, 7, 7, 12, 0, tzinfo=UTC),
        )

        assert production_event.event_type is expected_type


def test_no_session_observation_or_reasoning_generation_exists() -> None:
    field_names = {
        field.name
        for contract in (
            ScheduleSourceAdapter,
            ScheduledActivity,
            ScheduledActivityIdentity,
            ScheduleAdapterSummary,
        )
        for field in fields(contract)
    }
    method_names = {
        name for name, value in getmembers(ScheduleSourceAdapter) if isfunction(value)
    } | {name for name, value in getmembers(ScheduledActivity) if isfunction(value)}
    forbidden_terms = {
        "session",
        "session_window_product",
        "observation",
        "evidence",
        "finding",
        "operational_product",
        "generate",
    }

    assert not any(term in name for name in field_names | method_names for term in forbidden_terms)


def test_no_recording_block_or_media_references_exist() -> None:
    field_names = {
        field.name
        for contract in (
            ScheduleSourceAdapter,
            ScheduledActivity,
            ScheduledActivityIdentity,
            ScheduleAdapterSummary,
        )
        for field in fields(contract)
    }
    method_names = {
        name for name, value in getmembers(ScheduleSourceAdapter) if isfunction(value)
    } | {name for name, value in getmembers(ScheduledActivity) if isfunction(value)}
    forbidden_terms = {
        "recording_block",
        "media",
        "file",
        "chunk",
        "timeline_range",
        "timeline_position",
    }

    assert not any(term in name for name in field_names | method_names for term in forbidden_terms)


def test_no_provider_specific_names() -> None:
    enum_values = (
        {activity_type.value for activity_type in ScheduledActivityType}
        | {status.value for status in ScheduledActivityStatus}
        | {capability.value for capability in ScheduleAdapterCapability}
        | {status.value for status in ScheduleAdapterStatus}
    )
    field_names = {
        field.name
        for contract in (
            ScheduleSourceAdapter,
            ScheduledActivity,
            ScheduledActivityIdentity,
            ScheduleAdapterSummary,
        )
        for field in fields(contract)
    }
    forbidden_terms = {
        "pretalx",
        "sessionize",
        "cvent",
        "google",
        "calendar",
        "airtable",
        "csv",
        "provider",
        "vendor",
        "conference",
    }

    assert not any(term in value for value in enum_values for term in forbidden_terms)
    assert not any(term in field_name for field_name in field_names for term in forbidden_terms)


def test_no_api_persistence_queue_worker_or_frontend_exists() -> None:
    field_names = {
        field.name
        for contract in (
            ScheduleSourceAdapter,
            ScheduledActivity,
            ScheduledActivityIdentity,
            ScheduleAdapterSummary,
        )
        for field in fields(contract)
    }
    method_names = {
        name for name, value in getmembers(ScheduleSourceAdapter) if isfunction(value)
    } | {name for name, value in getmembers(ScheduledActivity) if isfunction(value)}
    forbidden_terms = {
        "api",
        "database",
        "repository",
        "queue",
        "worker",
        "frontend",
        "sync",
        "parse",
        "import",
        "reconcile",
    }

    assert not any(term in name for name in field_names | method_names for term in forbidden_terms)
