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
from app.contexts.production.vision_adapter import (
    VisionAdapterCapability,
    VisionAdapterIdentity,
    VisionAdapterKind,
    VisionAdapterStatus,
    VisionAdapterSummary,
    VisionSourceAdapter,
    VisualDetectionEvent,
    VisualDetectionStatus,
    VisualDetectionType,
)
from app.shared.ids import CorrelationId, EntityId

CONTRACTS = (
    VisionSourceAdapter,
    VisualDetectionEvent,
    VisionAdapterIdentity,
    VisionAdapterSummary,
)


def _identity() -> VisionAdapterIdentity:
    return VisionAdapterIdentity(
        adapter_name="Generic vision adapter",
        adapter_kind=VisionAdapterKind.LOCAL_VISION_SOURCE,
        stage_label="Main stage",
        metadata={"configured": True},
    )


def _adapter() -> VisionSourceAdapter:
    return VisionSourceAdapter(
        id=EntityId.new(),
        identity=_identity(),
        status=VisionAdapterStatus.READY,
        supported_capabilities=[
            VisionAdapterCapability.REPORTS_TEXT_REGIONS,
            VisionAdapterCapability.REPORTS_IMAGE_CHANGES,
            VisionAdapterCapability.REPORTS_CONFIDENCE,
        ],
        metadata={"scope": "vision-reporting"},
    )


def _detection_event(
    detection_status: VisualDetectionStatus = VisualDetectionStatus.CREATED,
) -> VisualDetectionEvent:
    return VisualDetectionEvent(
        detection_identifier="detection-123",
        detection_type=VisualDetectionType.TEXT_REGION,
        detection_status=detection_status,
        occurred_at=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
        recording_block_id=EntityId.new(),
        stage_id=EntityId.new(),
        timeline_range_reference="range-123",
        confidence=0.82,
        region_reference="region-123",
        metadata={"source": "adapter"},
    )


def _field_names() -> set[str]:
    return {field.name for contract in CONTRACTS for field in fields(contract)}


def _method_names() -> set[str]:
    return {
        name
        for contract in (VisionSourceAdapter, VisualDetectionEvent)
        for name, value in getmembers(contract)
        if isfunction(value)
    }


def test_vision_source_adapter_creation() -> None:
    adapter = _adapter()

    assert adapter.identity.adapter_name == "Generic vision adapter"
    assert adapter.status is VisionAdapterStatus.READY
    assert adapter.supports_capability(VisionAdapterCapability.REPORTS_TEXT_REGIONS)
    assert not adapter.supports_capability(VisionAdapterCapability.REPORTS_MOTION)
    assert dict(adapter.metadata) == {"scope": "vision-reporting"}


def test_visual_detection_event_creation() -> None:
    detection_event = _detection_event()

    assert detection_event.detection_identifier == "detection-123"
    assert detection_event.detection_type is VisualDetectionType.TEXT_REGION
    assert detection_event.detection_status is VisualDetectionStatus.CREATED
    assert detection_event.recording_block_id is not None
    assert detection_event.stage_id is not None
    assert detection_event.timeline_range_reference == "range-123"
    assert detection_event.confidence == 0.82
    assert detection_event.region_reference == "region-123"
    assert dict(detection_event.metadata) == {"source": "adapter"}


def test_visual_detection_event_confidence_describes_source_confidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        VisualDetectionEvent(
            detection_identifier="detection-123",
            detection_type=VisualDetectionType.IMAGE_CHANGE,
            detection_status=VisualDetectionStatus.CREATED,
            occurred_at=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
            confidence=-0.1,
        )


def test_visual_detection_type_allowed_values() -> None:
    assert {detection_type.value for detection_type in VisualDetectionType} == {
        "text_region",
        "image_change",
        "slide_change",
        "face_region",
        "person_region",
        "screen_transition",
        "camera_obstruction",
        "camera_motion",
        "brightness_change",
        "color_change",
        "graphic_region",
        "unknown",
    }


def test_visual_detection_status_allowed_values() -> None:
    assert {status.value for status in VisualDetectionStatus} == {
        "created",
        "updated",
        "finalized",
        "failed",
        "deleted",
        "unknown",
    }


def test_vision_adapter_capability_allowed_values() -> None:
    assert {capability.value for capability in VisionAdapterCapability} == {
        "reports_text_regions",
        "reports_slide_changes",
        "reports_image_changes",
        "reports_faces",
        "reports_motion",
        "reports_screen_transitions",
        "reports_confidence",
        "unknown",
    }


def test_vision_adapter_identity_creation() -> None:
    identity = _identity()

    assert identity.adapter_name == "Generic vision adapter"
    assert identity.adapter_kind is VisionAdapterKind.LOCAL_VISION_SOURCE
    assert identity.stage_label == "Main stage"
    assert dict(identity.metadata) == {"configured": True}


def test_vision_adapter_kind_allowed_values() -> None:
    assert {adapter_kind.value for adapter_kind in VisionAdapterKind} == {
        "local_vision_source",
        "cloud_vision_source",
        "camera_analysis_source",
        "manual_annotation_source",
        "simulated_source",
        "unknown",
    }


def test_vision_adapter_status_allowed_values() -> None:
    assert {status.value for status in VisionAdapterStatus} == {
        "unknown",
        "configured",
        "ready",
        "degraded",
        "failed",
        "archived",
    }


def test_vision_adapter_summary_generation() -> None:
    adapter = _adapter()

    summary = VisionAdapterSummary.from_adapter(adapter)

    assert summary.adapter_id == adapter.id
    assert summary.adapter_name == adapter.identity.adapter_name
    assert summary.adapter_kind is VisionAdapterKind.LOCAL_VISION_SOURCE
    assert summary.adapter_status is VisionAdapterStatus.READY
    assert summary.capability_count == 3
    assert summary.stage_label == "Main stage"


def test_visual_detection_event_maps_to_production_events_only() -> None:
    adapter = _adapter()
    detection_event = _detection_event(VisualDetectionStatus.CREATED)
    received_at = detection_event.occurred_at + timedelta(seconds=2)

    production_event = adapter.production_event_from_detection_event(
        detection_event,
        correlation_id=CorrelationId.new(),
        received_at=received_at,
    )

    assert isinstance(production_event, ProductionEvent)
    assert production_event.event_type is ProductionEventType.VISUAL_DETECTION_AVAILABLE
    assert production_event.source is ProductionEventSource.VISION_SYSTEM
    assert production_event.occurred_at == detection_event.occurred_at
    assert production_event.received_at == received_at
    assert production_event.payload.get("visual_detection_id") == "detection-123"
    assert production_event.payload.get("visual_detection_type") == "text_region"
    assert production_event.payload.get("visual_detection_status") == "created"
    assert production_event.payload.get("timeline_range_reference") == "range-123"
    assert production_event.payload.get("confidence") == 0.82
    assert production_event.payload.get("region_reference") == "region-123"
    assert {reference.reference_type for reference in production_event.references} == {
        ProductionEventReferenceType.EXTERNAL_OBJECT,
        ProductionEventReferenceType.RECORDING_BLOCK,
        ProductionEventReferenceType.STAGE,
        ProductionEventReferenceType.TIMELINE_RANGE,
    }


def test_allowed_production_event_mappings() -> None:
    expected_types = {
        VisualDetectionStatus.CREATED: ProductionEventType.VISUAL_DETECTION_AVAILABLE,
        VisualDetectionStatus.UPDATED: ProductionEventType.VISUAL_DETECTION_AVAILABLE,
        VisualDetectionStatus.FINALIZED: ProductionEventType.VISUAL_DETECTION_AVAILABLE,
        VisualDetectionStatus.FAILED: ProductionEventType.SYSTEM_STATUS_CHANGED,
        VisualDetectionStatus.DELETED: ProductionEventType.SYSTEM_STATUS_CHANGED,
        VisualDetectionStatus.UNKNOWN: ProductionEventType.SYSTEM_STATUS_CHANGED,
    }

    for detection_status, expected_type in expected_types.items():
        detection_event = _detection_event(detection_status)
        production_event = detection_event.to_production_event(
            correlation_id=CorrelationId.new(),
            received_at=detection_event.occurred_at + timedelta(seconds=1),
        )

        assert production_event.event_type is expected_type


def test_no_observation_generation_exists() -> None:
    assert "observation" not in " ".join(_field_names() | _method_names())


def test_no_ocr_or_model_execution_exists() -> None:
    forbidden_terms = {
        "ocr",
        "execute",
        "run",
        "model",
        "recognize",
        "classify",
        "detect_object",
        "read_text",
        "call",
    }

    assert not any(
        term in name for name in _field_names() | _method_names() for term in forbidden_terms
    )


def test_no_session_or_visual_meaning_inference_exists() -> None:
    forbidden_terms = {
        "session",
        "speaker",
        "title",
        "logo",
        "meaning",
        "clip",
        "infer",
        "semantic",
        "identify",
    }

    assert not any(
        term in name for name in _field_names() | _method_names() for term in forbidden_terms
    )


def test_no_reasoning_artifacts_are_created() -> None:
    forbidden_terms = {
        "evidence",
        "hypothesis",
        "finding",
        "operational_product",
        "reason",
        "decision",
    }

    assert not any(
        term in name for name in _field_names() | _method_names() for term in forbidden_terms
    )


def test_no_provider_specific_names_appear() -> None:
    enum_values = (
        {detection_type.value for detection_type in VisualDetectionType}
        | {status.value for status in VisualDetectionStatus}
        | {capability.value for capability in VisionAdapterCapability}
        | {adapter_kind.value for adapter_kind in VisionAdapterKind}
        | {status.value for status in VisionAdapterStatus}
    )
    forbidden_terms = {
        "opencv",
        "vision_api",
        "google",
        "aws",
        "azure",
        "rekognition",
        "yolo",
        "provider",
        "vendor",
        "brand",
    }

    assert not any(term in value for value in enum_values for term in forbidden_terms)
    assert not any(
        term in name for name in _field_names() | _method_names() for term in forbidden_terms
    )


def test_no_api_persistence_queue_worker_frontend_or_model_calls_exist() -> None:
    forbidden_terms = {
        "api",
        "database",
        "repository",
        "queue",
        "worker",
        "frontend",
        "request",
        "client",
        "webhook",
        "persist",
        "save",
        "dispatch",
        "interpret",
    }

    assert not any(
        term in name for name in _field_names() | _method_names() for term in forbidden_terms
    )
