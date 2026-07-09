from dataclasses import fields
from datetime import UTC, datetime, timedelta
from inspect import getmembers, isfunction

from app.contexts.production.operator_adapter import (
    OperatorAdapterCapability,
    OperatorAdapterIdentity,
    OperatorAdapterKind,
    OperatorAdapterStatus,
    OperatorAdapterSummary,
    OperatorEvent,
    OperatorEventStatus,
    OperatorEventType,
    OperatorSourceAdapter,
)
from app.contexts.production.production_event import (
    ProductionEvent,
    ProductionEventReferenceType,
    ProductionEventSource,
    ProductionEventType,
)
from app.shared.ids import CorrelationId, EntityId

CONTRACTS = (
    OperatorSourceAdapter,
    OperatorEvent,
    OperatorAdapterIdentity,
    OperatorAdapterSummary,
)


def _identity() -> OperatorAdapterIdentity:
    return OperatorAdapterIdentity(
        adapter_name="Generic operator adapter",
        adapter_kind=OperatorAdapterKind.MANUAL_ENTRY,
        stage_label="Main stage",
        metadata={"configured": True},
    )


def _adapter() -> OperatorSourceAdapter:
    return OperatorSourceAdapter(
        id=EntityId.new(),
        identity=_identity(),
        status=OperatorAdapterStatus.READY,
        supported_capabilities=[
            OperatorAdapterCapability.REPORTS_ANNOTATIONS,
            OperatorAdapterCapability.REPORTS_MARKERS,
            OperatorAdapterCapability.REPORTS_NOTES,
        ],
        metadata={"scope": "operator-reporting"},
    )


def _operator_event(
    event_status: OperatorEventStatus = OperatorEventStatus.CREATED,
) -> OperatorEvent:
    return OperatorEvent(
        operator_event_identifier="operator-event-123",
        event_type=OperatorEventType.NOTE_CREATED,
        event_status=event_status,
        occurred_at=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
        recording_block_id=EntityId.new(),
        stage_id=EntityId.new(),
        timeline_range_reference="range-123",
        label="Operator note",
        note="Operator supplied descriptive note.",
        metadata={"source": "adapter"},
    )


def _field_names() -> set[str]:
    return {field.name for contract in CONTRACTS for field in fields(contract)}


def _method_names() -> set[str]:
    return {
        name
        for contract in (OperatorSourceAdapter, OperatorEvent)
        for name, value in getmembers(contract)
        if isfunction(value)
    }


def test_operator_source_adapter_creation() -> None:
    adapter = _adapter()

    assert adapter.identity.adapter_name == "Generic operator adapter"
    assert adapter.status is OperatorAdapterStatus.READY
    assert adapter.supports_capability(OperatorAdapterCapability.REPORTS_ANNOTATIONS)
    assert not adapter.supports_capability(OperatorAdapterCapability.REPORTS_REQUESTS)
    assert dict(adapter.metadata) == {"scope": "operator-reporting"}


def test_operator_event_creation() -> None:
    operator_event = _operator_event()

    assert operator_event.operator_event_identifier == "operator-event-123"
    assert operator_event.event_type is OperatorEventType.NOTE_CREATED
    assert operator_event.event_status is OperatorEventStatus.CREATED
    assert operator_event.recording_block_id is not None
    assert operator_event.stage_id is not None
    assert operator_event.timeline_range_reference == "range-123"
    assert operator_event.label == "Operator note"
    assert operator_event.note == "Operator supplied descriptive note."
    assert dict(operator_event.metadata) == {"source": "adapter"}


def test_operator_event_type_allowed_values() -> None:
    assert {event_type.value for event_type in OperatorEventType} == {
        "annotation_created",
        "annotation_updated",
        "annotation_removed",
        "marker_created",
        "marker_removed",
        "flag_created",
        "flag_removed",
        "note_created",
        "note_updated",
        "decision_requested",
        "custom",
        "unknown",
    }


def test_operator_event_status_allowed_values() -> None:
    assert {status.value for status in OperatorEventStatus} == {
        "created",
        "updated",
        "removed",
        "cancelled",
        "unknown",
    }


def test_operator_adapter_capability_allowed_values() -> None:
    assert {capability.value for capability in OperatorAdapterCapability} == {
        "reports_annotations",
        "reports_markers",
        "reports_flags",
        "reports_notes",
        "reports_requests",
        "unknown",
    }


def test_operator_adapter_identity_creation() -> None:
    identity = _identity()

    assert identity.adapter_name == "Generic operator adapter"
    assert identity.adapter_kind is OperatorAdapterKind.MANUAL_ENTRY
    assert identity.stage_label == "Main stage"
    assert dict(identity.metadata) == {"configured": True}


def test_operator_adapter_kind_allowed_values() -> None:
    assert {adapter_kind.value for adapter_kind in OperatorAdapterKind} == {
        "desktop_operator",
        "mobile_operator",
        "control_surface",
        "manual_entry",
        "simulated_source",
        "unknown",
    }


def test_operator_adapter_status_allowed_values() -> None:
    assert {status.value for status in OperatorAdapterStatus} == {
        "unknown",
        "configured",
        "ready",
        "degraded",
        "failed",
        "archived",
    }


def test_operator_adapter_summary_generation() -> None:
    adapter = _adapter()

    summary = OperatorAdapterSummary.from_adapter(adapter)

    assert summary.adapter_id == adapter.id
    assert summary.adapter_name == adapter.identity.adapter_name
    assert summary.adapter_kind is OperatorAdapterKind.MANUAL_ENTRY
    assert summary.adapter_status is OperatorAdapterStatus.READY
    assert summary.capability_count == 3
    assert summary.stage_label == "Main stage"


def test_operator_event_maps_to_production_events_only() -> None:
    adapter = _adapter()
    operator_event = _operator_event(OperatorEventStatus.CREATED)
    received_at = operator_event.occurred_at + timedelta(seconds=2)

    production_event = adapter.production_event_from_operator_event(
        operator_event,
        correlation_id=CorrelationId.new(),
        received_at=received_at,
    )

    assert isinstance(production_event, ProductionEvent)
    assert production_event.event_type is ProductionEventType.OPERATOR_INPUT_RECEIVED
    assert production_event.source is ProductionEventSource.OPERATOR
    assert production_event.occurred_at == operator_event.occurred_at
    assert production_event.received_at == received_at
    assert production_event.payload.get("operator_event_id") == "operator-event-123"
    assert production_event.payload.get("operator_event_type") == "note_created"
    assert production_event.payload.get("operator_event_status") == "created"
    assert production_event.payload.get("timeline_range_reference") == "range-123"
    assert production_event.payload.get("label") == "Operator note"
    assert production_event.payload.get("note") == "Operator supplied descriptive note."
    assert {reference.reference_type for reference in production_event.references} == {
        ProductionEventReferenceType.EXTERNAL_OBJECT,
        ProductionEventReferenceType.RECORDING_BLOCK,
        ProductionEventReferenceType.STAGE,
        ProductionEventReferenceType.TIMELINE_RANGE,
    }


def test_allowed_production_event_mappings() -> None:
    expected_types = {
        OperatorEventStatus.CREATED: ProductionEventType.OPERATOR_INPUT_RECEIVED,
        OperatorEventStatus.UPDATED: ProductionEventType.OPERATOR_INPUT_RECEIVED,
        OperatorEventStatus.REMOVED: ProductionEventType.OPERATOR_INPUT_RECEIVED,
        OperatorEventStatus.CANCELLED: ProductionEventType.SYSTEM_STATUS_CHANGED,
        OperatorEventStatus.UNKNOWN: ProductionEventType.SYSTEM_STATUS_CHANGED,
    }

    for event_status, expected_type in expected_types.items():
        operator_event = _operator_event(event_status)
        production_event = operator_event.to_production_event(
            correlation_id=CorrelationId.new(),
            received_at=operator_event.occurred_at + timedelta(seconds=1),
        )

        assert production_event.event_type is expected_type


def test_no_observation_generation_exists() -> None:
    assert "observation" not in " ".join(_field_names() | _method_names())


def test_no_workflow_implementation_exists() -> None:
    forbidden_terms = {
        "review",
        "approval",
        "approve",
        "assignment",
        "assign",
        "queue",
        "workflow",
        "permission",
        "authentication",
        "auth",
    }

    assert not any(
        term in name for name in _field_names() | _method_names() for term in forbidden_terms
    )


def test_no_reasoning_or_correctness_implementation_exists() -> None:
    forbidden_terms = {
        "validate",
        "correct",
        "truth",
        "infer",
        "session",
        "clip",
        "accepted",
        "confirmed",
        "evidence",
        "hypothesis",
        "finding",
        "operational_product",
        "reason",
    }

    assert not any(
        term in name for name in _field_names() | _method_names() for term in forbidden_terms
    )


def test_no_provider_specific_names_or_ui_assumptions_appear() -> None:
    enum_values = (
        {event_type.value for event_type in OperatorEventType}
        | {status.value for status in OperatorEventStatus}
        | {capability.value for capability in OperatorAdapterCapability}
        | {adapter_kind.value for adapter_kind in OperatorAdapterKind}
        | {status.value for status in OperatorAdapterStatus}
    )
    forbidden_terms = {
        "streamdeck",
        "companion",
        "touchdesigner",
        "obs",
        "vmix",
        "web",
        "button",
        "form",
        "provider",
        "vendor",
        "brand",
    }

    assert not any(term in value for value in enum_values for term in forbidden_terms)
    assert not any(
        term in name for name in _field_names() | _method_names() for term in forbidden_terms
    )


def test_no_api_persistence_queue_worker_auth_permissions_or_frontend_exist() -> None:
    forbidden_terms = {
        "api",
        "database",
        "repository",
        "worker",
        "frontend",
        "request",
        "client",
        "webhook",
        "persist",
        "save",
        "dispatch",
        "interpret",
        "permission",
        "authentication",
        "auth",
    }

    assert not any(
        term in name for name in _field_names() | _method_names() for term in forbidden_terms
    )
