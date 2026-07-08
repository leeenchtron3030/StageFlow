from dataclasses import fields
from datetime import UTC, datetime, timedelta
from inspect import getmembers, isfunction

from app.contexts.production.production_event import (
    ProductionEvent,
    ProductionEventReferenceType,
    ProductionEventSource,
    ProductionEventType,
)
from app.contexts.production.recording_adapter import (
    RecordingAdapterCapability,
    RecordingAdapterIdentity,
    RecordingAdapterKind,
    RecordingAdapterSummary,
    RecordingSessionEvent,
    RecordingSessionEventKind,
    RecordingSystemAdapter,
    RecordingSystemStatus,
)
from app.shared.ids import CorrelationId, EntityId


def _identity() -> RecordingAdapterIdentity:
    return RecordingAdapterIdentity(
        adapter_name="Generic recording adapter",
        adapter_kind=RecordingAdapterKind.SOFTWARE_RECORDER,
        location_label="Control room",
        stage_label="Main stage",
        metadata={"configured": True},
    )


def _adapter() -> RecordingSystemAdapter:
    return RecordingSystemAdapter(
        id=EntityId.new(),
        identity=_identity(),
        status=RecordingSystemStatus.READY,
        supported_capabilities=[
            RecordingAdapterCapability.REPORTS_RECORDING_START,
            RecordingAdapterCapability.REPORTS_RECORDING_STOP,
            RecordingAdapterCapability.REPORTS_RECORDING_STATUS,
        ],
        metadata={"scope": "recording"},
    )


def _session_event(
    event_kind: RecordingSessionEventKind = RecordingSessionEventKind.RECORDING_STARTED,
) -> RecordingSessionEvent:
    return RecordingSessionEvent(
        recording_system_identifier="recording-system-1",
        event_kind=event_kind,
        occurred_at=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
        recording_block_id=EntityId.new(),
        stage_id=EntityId.new(),
        label="Recording activity",
        metadata={"source": "adapter"},
    )


def test_recording_system_adapter_creation() -> None:
    adapter = _adapter()

    assert adapter.identity.adapter_name == "Generic recording adapter"
    assert adapter.status is RecordingSystemStatus.READY
    assert adapter.supports_capability(RecordingAdapterCapability.REPORTS_RECORDING_START)
    assert not adapter.supports_capability(RecordingAdapterCapability.REPORTS_HEALTH)
    assert dict(adapter.metadata) == {"scope": "recording"}


def test_recording_system_status_allowed_values() -> None:
    assert {status.value for status in RecordingSystemStatus} == {
        "unknown",
        "configured",
        "ready",
        "recording",
        "paused",
        "stopped",
        "degraded",
        "failed",
        "archived",
    }


def test_recording_session_event_creation() -> None:
    session_event = _session_event()

    assert session_event.recording_system_identifier == "recording-system-1"
    assert session_event.event_kind is RecordingSessionEventKind.RECORDING_STARTED
    assert session_event.recording_block_id is not None
    assert session_event.stage_id is not None
    assert session_event.label == "Recording activity"
    assert dict(session_event.metadata) == {"source": "adapter"}


def test_recording_session_event_kind_allowed_values() -> None:
    assert {event_kind.value for event_kind in RecordingSessionEventKind} == {
        "recording_started",
        "recording_paused",
        "recording_resumed",
        "recording_stopped",
        "recording_failed",
        "recording_status_changed",
        "unknown",
    }


def test_recording_adapter_capability_allowed_values() -> None:
    assert {capability.value for capability in RecordingAdapterCapability} == {
        "reports_recording_start",
        "reports_recording_stop",
        "reports_recording_pause",
        "reports_recording_status",
        "reports_livestream_status",
        "reports_health",
        "unknown",
    }


def test_recording_adapter_identity_creation() -> None:
    identity = _identity()

    assert identity.adapter_name == "Generic recording adapter"
    assert identity.adapter_kind is RecordingAdapterKind.SOFTWARE_RECORDER
    assert identity.location_label == "Control room"
    assert identity.stage_label == "Main stage"
    assert dict(identity.metadata) == {"configured": True}


def test_recording_adapter_kind_allowed_values() -> None:
    assert {adapter_kind.value for adapter_kind in RecordingAdapterKind} == {
        "software_recorder",
        "hardware_recorder",
        "livestream_encoder",
        "manual_operator",
        "simulated_recorder",
        "unknown",
    }


def test_recording_adapter_summary_generation() -> None:
    adapter = _adapter()

    summary = RecordingAdapterSummary.from_adapter(adapter)

    assert summary.adapter_id == adapter.id
    assert summary.adapter_name == adapter.identity.adapter_name
    assert summary.adapter_kind is RecordingAdapterKind.SOFTWARE_RECORDER
    assert summary.status is RecordingSystemStatus.READY
    assert summary.capability_count == 3
    assert summary.stage_label == "Main stage"
    assert summary.location_label == "Control room"


def test_adapter_maps_recording_session_events_to_production_events_only() -> None:
    adapter = _adapter()
    session_event = _session_event(RecordingSessionEventKind.RECORDING_STARTED)
    received_at = session_event.occurred_at + timedelta(seconds=2)

    production_event = adapter.production_event_from_session_event(
        session_event,
        correlation_id=CorrelationId.new(),
        received_at=received_at,
    )

    assert isinstance(production_event, ProductionEvent)
    assert production_event.event_type is ProductionEventType.RECORDING_BLOCK_STARTED
    assert production_event.source is ProductionEventSource.RECORDING_SYSTEM
    assert production_event.occurred_at == session_event.occurred_at
    assert production_event.received_at == received_at
    assert production_event.payload.get("recording_system_id") == "recording-system-1"
    assert production_event.payload.get("recording_event_kind") == "recording_started"
    assert {reference.reference_type for reference in production_event.references} == {
        ProductionEventReferenceType.SYSTEM,
        ProductionEventReferenceType.RECORDING_BLOCK,
        ProductionEventReferenceType.STAGE,
    }


def test_allowed_production_event_mappings() -> None:
    expected_types = {
        RecordingSessionEventKind.RECORDING_STARTED: ProductionEventType.RECORDING_BLOCK_STARTED,
        RecordingSessionEventKind.RECORDING_STOPPED: ProductionEventType.RECORDING_BLOCK_ENDED,
        RecordingSessionEventKind.RECORDING_PAUSED: (
            ProductionEventType.RECORDING_BLOCK_STATUS_CHANGED
        ),
        RecordingSessionEventKind.RECORDING_RESUMED: (
            ProductionEventType.RECORDING_BLOCK_STATUS_CHANGED
        ),
        RecordingSessionEventKind.RECORDING_STATUS_CHANGED: (
            ProductionEventType.RECORDING_BLOCK_STATUS_CHANGED
        ),
        RecordingSessionEventKind.RECORDING_FAILED: ProductionEventType.SYSTEM_STATUS_CHANGED,
        RecordingSessionEventKind.UNKNOWN: ProductionEventType.SYSTEM_STATUS_CHANGED,
    }

    for event_kind, expected_type in expected_types.items():
        session_event = _session_event(event_kind)
        production_event = session_event.to_production_event(
            correlation_id=CorrelationId.new(),
            received_at=session_event.occurred_at + timedelta(seconds=1),
        )

        assert production_event.event_type is expected_type


def test_no_observation_generation_exists() -> None:
    field_names = {
        field.name
        for contract in (
            RecordingSystemAdapter,
            RecordingSessionEvent,
            RecordingAdapterIdentity,
            RecordingAdapterSummary,
        )
        for field in fields(contract)
    }
    method_names = {
        name for name, value in getmembers(RecordingSystemAdapter) if isfunction(value)
    } | {name for name, value in getmembers(RecordingSessionEvent) if isfunction(value)}

    assert "observation" not in " ".join(field_names | method_names)


def test_no_recording_block_mutation_exists() -> None:
    method_names = {
        name for name, value in getmembers(RecordingSystemAdapter) if isfunction(value)
    } | {name for name, value in getmembers(RecordingSessionEvent) if isfunction(value)}
    forbidden_terms = {
        "create_recording_block",
        "update_recording_block",
        "mutate_recording_block",
        "recording_block_lifecycle",
    }

    assert not any(term in method_name for method_name in method_names for term in forbidden_terms)


def test_no_media_file_or_chunk_handling_exists() -> None:
    field_names = {
        field.name
        for contract in (
            RecordingSystemAdapter,
            RecordingSessionEvent,
            RecordingAdapterIdentity,
            RecordingAdapterSummary,
        )
        for field in fields(contract)
    }
    method_names = {
        name for name, value in getmembers(RecordingSystemAdapter) if isfunction(value)
    } | {name for name, value in getmembers(RecordingSessionEvent) if isfunction(value)}
    forbidden_terms = {
        "media_file",
        "file_path",
        "chunk",
        "codec",
        "source_file",
        "timeline_position",
        "timeline_range",
    }

    assert not any(term in name for name in field_names | method_names for term in forbidden_terms)


def test_no_provider_specific_names_appear() -> None:
    enum_values = (
        {status.value for status in RecordingSystemStatus}
        | {event_kind.value for event_kind in RecordingSessionEventKind}
        | {capability.value for capability in RecordingAdapterCapability}
        | {adapter_kind.value for adapter_kind in RecordingAdapterKind}
    )
    field_names = {
        field.name
        for contract in (
            RecordingSystemAdapter,
            RecordingSessionEvent,
            RecordingAdapterIdentity,
            RecordingAdapterSummary,
        )
        for field in fields(contract)
    }
    forbidden_terms = {
        "vmix",
        "obs",
        "blackmagic",
        "ndi",
        "sdi",
        "youtube",
        "twitch",
        "devcon",
        "provider",
        "vendor",
        "brand",
    }

    assert not any(term in value for value in enum_values for term in forbidden_terms)
    assert not any(term in field_name for field_name in field_names for term in forbidden_terms)


def test_no_api_persistence_queue_worker_frontend_or_filesystem_watching_exists() -> None:
    field_names = {
        field.name
        for contract in (
            RecordingSystemAdapter,
            RecordingSessionEvent,
            RecordingAdapterIdentity,
            RecordingAdapterSummary,
        )
        for field in fields(contract)
    }
    method_names = {
        name for name, value in getmembers(RecordingSystemAdapter) if isfunction(value)
    } | {name for name, value in getmembers(RecordingSessionEvent) if isfunction(value)}
    forbidden_terms = {
        "api",
        "database",
        "repository",
        "queue",
        "worker",
        "frontend",
        "watch",
        "filesystem",
        "dispatch",
        "interpret",
    }

    assert not any(term in name for name in field_names | method_names for term in forbidden_terms)
