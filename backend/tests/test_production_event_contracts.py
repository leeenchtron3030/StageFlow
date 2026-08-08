from dataclasses import fields
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import Any, cast

import pytest

from app.contexts.production.production_event import (
    ProductionEvent,
    ProductionEventPayload,
    ProductionEventReference,
    ProductionEventReferenceType,
    ProductionEventSource,
    ProductionEventSummary,
    ProductionEventType,
)
from app.shared.ids import CorrelationId, EntityId
from tests.timestamp_fixtures import AWARE_TIMESTAMP


def _event(
    references: list[ProductionEventReference] | None = None,
) -> ProductionEvent:
    occurred_at = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)
    return ProductionEvent(
        id=EntityId.new(),
        event_type=ProductionEventType.RECORDING_BLOCK_STARTED,
        source=ProductionEventSource.RECORDING_SYSTEM,
        payload=ProductionEventPayload(
            {
                "status": "started",
                "offset_seconds": 0,
                "markers": ["start"],
                "details": {"operator_visible": True},
            }
        ),
        references=references or [],
        correlation_id=CorrelationId.new(),
        occurred_at=occurred_at,
        received_at=occurred_at + timedelta(seconds=2),
        metadata={"runtime": "production"},
        notes="Runtime input only.",
    )


def test_production_event_creation() -> None:
    recording_block_id = EntityId.new()
    reference = ProductionEventReference(
        reference_type=ProductionEventReferenceType.RECORDING_BLOCK,
        referenced_id=recording_block_id,
        label="recording block",
    )

    event = _event(references=[reference])

    assert event.event_type is ProductionEventType.RECORDING_BLOCK_STARTED
    assert event.source is ProductionEventSource.RECORDING_SYSTEM
    assert event.payload.get("status") == "started"
    assert event.references == (reference,)
    assert event.references[0].referenced_id == recording_block_id
    assert dict(event.metadata) == {"runtime": "production"}


def test_production_event_type_allowed_values() -> None:
    assert {event_type.value for event_type in ProductionEventType} == {
        "recording_block_started",
        "recording_block_ended",
        "recording_block_status_changed",
        "media_file_created",
        "media_file_finalized",
        "media_file_failed",
        "schedule_artifact_updated",
        "schedule_boundary_reached",
        "transcript_segment_available",
        "visual_detection_available",
        "ocr_text_available",
        "audio_level_changed",
        "audio_spike_detected",
        "operator_input_received",
        "manual_marker_added",
        "operator_note_added",
        "livestream_status_changed",
        "webhook_received",
        "timer_elapsed",
        "system_status_changed",
        "unknown",
    }


def test_production_event_type_avoids_conclusions() -> None:
    forbidden_values = {
        "session_started",
        "session_ended",
        "clip_found",
        "finding_created",
        "alert_created",
        "package_ready",
    }

    assert forbidden_values.isdisjoint({event_type.value for event_type in ProductionEventType})


def test_production_event_source_allowed_values() -> None:
    assert {source.value for source in ProductionEventSource} == {
        "recording_system",
        "filesystem",
        "schedule_system",
        "transcript_system",
        "vision_system",
        "audio_system",
        "livestream_system",
        "operator",
        "timer",
        "webhook",
        "internal_system",
        "unknown",
    }


def test_production_event_payload_accepts_empty_payload() -> None:
    payload = ProductionEventPayload()

    assert dict(payload.data) == {}
    assert payload.key_count == 0
    assert payload.get("missing") is None


def test_production_event_payload_freezes_payload_where_practical() -> None:
    payload = ProductionEventPayload(
        {
            "level": 0.72,
            "markers": ["start", "status"],
            "details": {"visible": True},
        }
    )

    assert isinstance(payload.data, MappingProxyType)
    assert isinstance(payload.data["markers"], tuple)
    assert isinstance(payload.data["details"], MappingProxyType)

    mutable_payload = cast(dict[str, Any], payload.data)
    with pytest.raises(TypeError):
        mutable_payload["level"] = 0.5

    mutable_details = cast(dict[str, Any], payload.data["details"])
    with pytest.raises(TypeError):
        mutable_details["visible"] = False


def test_production_event_payload_rejects_non_json_values() -> None:
    with pytest.raises(ValueError, match="JSON-compatible"):
        ProductionEventPayload({"unsupported": object()})


def test_production_event_payload_rejects_non_string_keys() -> None:
    with pytest.raises(ValueError, match="keys must be strings"):
        ProductionEventPayload(cast(Any, {1: "not-json-object-shaped"}))


def test_production_event_reference_creation() -> None:
    referenced_id = EntityId.new()
    id_reference = ProductionEventReference(
        reference_type=ProductionEventReferenceType.STAGE,
        referenced_id=referenced_id,
        label="stage",
        metadata={"scope": "event"},
    )
    external_reference = ProductionEventReference(
        reference_type=ProductionEventReferenceType.EXTERNAL_OBJECT,
        external_reference="external-runtime-object",
    )

    assert id_reference.reference_type is ProductionEventReferenceType.STAGE
    assert id_reference.referenced_id == referenced_id
    assert id_reference.external_reference is None
    assert dict(id_reference.metadata) == {"scope": "event"}
    assert external_reference.external_reference == "external-runtime-object"


def test_production_event_reference_requires_one_reference_value() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        ProductionEventReference(reference_type=ProductionEventReferenceType.UNKNOWN)

    with pytest.raises(ValueError, match="exactly one"):
        ProductionEventReference(
            reference_type=ProductionEventReferenceType.UNKNOWN,
            referenced_id=EntityId.new(),
            external_reference="external-runtime-object",
        )


def test_production_event_reference_type_allowed_values() -> None:
    assert {reference_type.value for reference_type in ProductionEventReferenceType} == {
        "recording_block",
        "stage",
        "timeline_position",
        "timeline_range",
        "media_file",
        "schedule_artifact",
        "external_object",
        "operator",
        "system",
        "unknown",
    }


def test_production_event_summary_generation() -> None:
    event = _event(
        references=[
            ProductionEventReference(
                reference_type=ProductionEventReferenceType.RECORDING_BLOCK,
                referenced_id=EntityId.new(),
            )
        ]
    )

    summary = ProductionEventSummary.from_production_event(event)

    assert summary.production_event_id == event.id
    assert summary.event_type is event.event_type
    assert summary.source is event.source
    assert summary.occurred_at == event.occurred_at
    assert summary.received_at == event.received_at
    assert summary.reference_count == 1
    assert summary.payload_key_count == event.payload.key_count
    assert summary.correlation_id == event.correlation_id


def test_received_at_rejects_timestamps_earlier_than_occurred_at() -> None:
    occurred_at = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="received_at"):
        ProductionEvent(
            id=EntityId.new(),
            event_type=ProductionEventType.TIMER_ELAPSED,
            source=ProductionEventSource.TIMER,
            payload=ProductionEventPayload(),
            correlation_id=CorrelationId.new(),
            occurred_at=occurred_at,
            received_at=occurred_at - timedelta(seconds=1),
        )


def test_event_references_are_optional() -> None:
    event = ProductionEvent(
                received_at=AWARE_TIMESTAMP,

        id=EntityId.new(),
        event_type=ProductionEventType.UNKNOWN,
        source=ProductionEventSource.UNKNOWN,
        payload=ProductionEventPayload(),
        correlation_id=CorrelationId.new(),
        occurred_at=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
    )

    assert event.references == ()


def test_payload_does_not_require_provider_schema() -> None:
    payload = ProductionEventPayload(
        {
            "external_id": "runtime-object-123",
            "available": True,
            "measurements": [0.1, 0.2, 0.3],
        }
    )

    assert payload.get("external_id") == "runtime-object-123"
    assert payload.key_count == 3


def test_no_observation_finding_or_operational_product_generation_exists() -> None:
    field_names = {
        field.name
        for contract in (
            ProductionEvent,
            ProductionEventPayload,
            ProductionEventReference,
            ProductionEventSummary,
        )
        for field in fields(contract)
    }
    forbidden_terms = {
        "observation",
        "evidence",
        "hypothesis",
        "finding",
        "verification_decision",
        "operational_product",
        "generate",
        "create",
    }

    assert not any(term in field_name for field_name in field_names for term in forbidden_terms)


def test_no_provider_specific_names_appear() -> None:
    enum_values = (
        {event_type.value for event_type in ProductionEventType}
        | {source.value for source in ProductionEventSource}
        | {reference_type.value for reference_type in ProductionEventReferenceType}
    )
    field_names = {
        field.name
        for contract in (
            ProductionEvent,
            ProductionEventPayload,
            ProductionEventReference,
            ProductionEventSummary,
        )
        for field in fields(contract)
    }
    forbidden_terms = {
        "pretalx",
        "whisper",
        "vmix",
        "youtube",
        "devcon",
        "github",
        "ffmpeg",
        "provider",
        "vendor",
        "tool",
        "brand",
        "conference",
    }

    assert not any(term in value for value in enum_values for term in forbidden_terms)
    assert not any(term in field_name for field_name in field_names for term in forbidden_terms)


def test_no_api_persistence_queue_worker_frontend_or_adapter_behavior_exists() -> None:
    field_names = {
        field.name
        for contract in (ProductionEvent, ProductionEventReference, ProductionEventSummary)
        for field in fields(contract)
    }
    forbidden_terms = {
        "api",
        "database",
        "repository",
        "queue",
        "worker",
        "frontend",
        "adapter",
        "webhook_handler",
        "file_watcher",
    }

    assert not any(term in field_name for field_name in field_names for term in forbidden_terms)
