from dataclasses import fields
from datetime import UTC, datetime, timedelta
from inspect import getmembers, isfunction

from app.contexts.production.media_artifact_adapter import (
    MediaArtifactAdapter,
    MediaArtifactAdapterKind,
    MediaArtifactCapability,
    MediaArtifactEvent,
    MediaArtifactIdentity,
    MediaArtifactStatus,
    MediaArtifactSummary,
    MediaArtifactType,
)
from app.contexts.production.production_event import (
    ProductionEvent,
    ProductionEventReferenceType,
    ProductionEventSource,
    ProductionEventType,
)
from app.shared.ids import CorrelationId, EntityId


def _identity() -> MediaArtifactIdentity:
    return MediaArtifactIdentity(
        adapter_name="Generic media artifact adapter",
        adapter_kind=MediaArtifactAdapterKind.FILESYSTEM_SOURCE,
        location_label="Artifact source",
        stage_label="Main stage",
        metadata={"configured": True},
    )


def _adapter() -> MediaArtifactAdapter:
    return MediaArtifactAdapter(
        id=EntityId.new(),
        identity=_identity(),
        status=MediaArtifactStatus.CREATED,
        supported_capabilities=[
            MediaArtifactCapability.REPORTS_ARTIFACT_CREATED,
            MediaArtifactCapability.REPORTS_ARTIFACT_FINALIZED,
            MediaArtifactCapability.REPORTS_ARTIFACT_LOCATION,
        ],
        metadata={"scope": "artifact-reporting"},
    )


def _artifact_event(
    artifact_status: MediaArtifactStatus = MediaArtifactStatus.CREATED,
) -> MediaArtifactEvent:
    return MediaArtifactEvent(
        artifact_identifier="artifact-123",
        artifact_type=MediaArtifactType.VIDEO,
        artifact_status=artifact_status,
        occurred_at=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
        recording_block_id=EntityId.new(),
        stage_id=EntityId.new(),
        artifact_label="Program recording artifact",
        artifact_uri="artifact://generic/artifact-123",
        size_bytes=2048,
        metadata={"source": "adapter"},
    )


def test_media_artifact_adapter_creation() -> None:
    adapter = _adapter()

    assert adapter.identity.adapter_name == "Generic media artifact adapter"
    assert adapter.status is MediaArtifactStatus.CREATED
    assert adapter.supports_capability(MediaArtifactCapability.REPORTS_ARTIFACT_CREATED)
    assert not adapter.supports_capability(MediaArtifactCapability.REPORTS_ARTIFACT_FAILED)
    assert dict(adapter.metadata) == {"scope": "artifact-reporting"}


def test_media_artifact_event_creation() -> None:
    artifact_event = _artifact_event()

    assert artifact_event.artifact_identifier == "artifact-123"
    assert artifact_event.artifact_type is MediaArtifactType.VIDEO
    assert artifact_event.artifact_status is MediaArtifactStatus.CREATED
    assert artifact_event.recording_block_id is not None
    assert artifact_event.stage_id is not None
    assert artifact_event.artifact_label == "Program recording artifact"
    assert artifact_event.artifact_uri == "artifact://generic/artifact-123"
    assert artifact_event.size_bytes == 2048
    assert dict(artifact_event.metadata) == {"source": "adapter"}


def test_media_artifact_type_allowed_values() -> None:
    assert {artifact_type.value for artifact_type in MediaArtifactType} == {
        "video",
        "audio",
        "image",
        "caption",
        "transcript",
        "metadata",
        "log",
        "manifest",
        "unknown",
    }


def test_media_artifact_status_allowed_values() -> None:
    assert {status.value for status in MediaArtifactStatus} == {
        "created",
        "updating",
        "finalized",
        "failed",
        "deleted",
        "unknown",
    }


def test_media_artifact_capability_allowed_values() -> None:
    assert {capability.value for capability in MediaArtifactCapability} == {
        "reports_artifact_created",
        "reports_artifact_updated",
        "reports_artifact_finalized",
        "reports_artifact_failed",
        "reports_artifact_deleted",
        "reports_artifact_size",
        "reports_artifact_location",
        "unknown",
    }


def test_media_artifact_identity_creation() -> None:
    identity = _identity()

    assert identity.adapter_name == "Generic media artifact adapter"
    assert identity.adapter_kind is MediaArtifactAdapterKind.FILESYSTEM_SOURCE
    assert identity.location_label == "Artifact source"
    assert identity.stage_label == "Main stage"
    assert dict(identity.metadata) == {"configured": True}


def test_media_artifact_adapter_kind_allowed_values() -> None:
    assert {adapter_kind.value for adapter_kind in MediaArtifactAdapterKind} == {
        "filesystem_source",
        "network_source",
        "cloud_source",
        "manual_source",
        "simulated_source",
        "unknown",
    }


def test_media_artifact_summary_generation() -> None:
    adapter = _adapter()

    summary = MediaArtifactSummary.from_adapter(adapter)

    assert summary.adapter_id == adapter.id
    assert summary.adapter_name == adapter.identity.adapter_name
    assert summary.adapter_kind is MediaArtifactAdapterKind.FILESYSTEM_SOURCE
    assert summary.adapter_status is MediaArtifactStatus.CREATED
    assert summary.capability_count == 3
    assert summary.stage_label == "Main stage"
    assert summary.location_label == "Artifact source"


def test_artifact_event_maps_to_production_events_only() -> None:
    adapter = _adapter()
    artifact_event = _artifact_event(MediaArtifactStatus.CREATED)
    received_at = artifact_event.occurred_at + timedelta(seconds=2)

    production_event = adapter.production_event_from_artifact_event(
        artifact_event,
        correlation_id=CorrelationId.new(),
        received_at=received_at,
    )

    assert isinstance(production_event, ProductionEvent)
    assert production_event.event_type is ProductionEventType.MEDIA_FILE_CREATED
    assert production_event.source is ProductionEventSource.INTERNAL_SYSTEM
    assert production_event.occurred_at == artifact_event.occurred_at
    assert production_event.received_at == received_at
    assert production_event.payload.get("artifact_id") == "artifact-123"
    assert production_event.payload.get("artifact_type") == "video"
    assert production_event.payload.get("artifact_status") == "created"
    assert production_event.payload.get("artifact_uri") == "artifact://generic/artifact-123"
    assert production_event.payload.get("size_bytes") == 2048
    assert {reference.reference_type for reference in production_event.references} == {
        ProductionEventReferenceType.MEDIA_FILE,
        ProductionEventReferenceType.RECORDING_BLOCK,
        ProductionEventReferenceType.STAGE,
    }


def test_allowed_production_event_mappings() -> None:
    expected_types = {
        MediaArtifactStatus.CREATED: ProductionEventType.MEDIA_FILE_CREATED,
        MediaArtifactStatus.FINALIZED: ProductionEventType.MEDIA_FILE_FINALIZED,
        MediaArtifactStatus.FAILED: ProductionEventType.MEDIA_FILE_FAILED,
        MediaArtifactStatus.UPDATING: ProductionEventType.SYSTEM_STATUS_CHANGED,
        MediaArtifactStatus.DELETED: ProductionEventType.SYSTEM_STATUS_CHANGED,
        MediaArtifactStatus.UNKNOWN: ProductionEventType.SYSTEM_STATUS_CHANGED,
    }

    for artifact_status, expected_type in expected_types.items():
        artifact_event = _artifact_event(artifact_status)
        production_event = artifact_event.to_production_event(
            correlation_id=CorrelationId.new(),
            received_at=artifact_event.occurred_at + timedelta(seconds=1),
        )

        assert production_event.event_type is expected_type


def test_no_observation_generation_exists() -> None:
    field_names = {
        field.name
        for contract in (
            MediaArtifactAdapter,
            MediaArtifactEvent,
            MediaArtifactIdentity,
            MediaArtifactSummary,
        )
        for field in fields(contract)
    }
    method_names = {
        name for name, value in getmembers(MediaArtifactAdapter) if isfunction(value)
    } | {name for name, value in getmembers(MediaArtifactEvent) if isfunction(value)}

    assert "observation" not in " ".join(field_names | method_names)


def test_no_recording_block_mutation_exists() -> None:
    method_names = {
        name for name, value in getmembers(MediaArtifactAdapter) if isfunction(value)
    } | {name for name, value in getmembers(MediaArtifactEvent) if isfunction(value)}
    forbidden_terms = {
        "create_recording_block",
        "update_recording_block",
        "mutate_recording_block",
        "recording_block_lifecycle",
    }

    assert not any(term in method_name for method_name in method_names for term in forbidden_terms)


def test_no_media_validation_or_processing_exists() -> None:
    field_names = {
        field.name
        for contract in (
            MediaArtifactAdapter,
            MediaArtifactEvent,
            MediaArtifactIdentity,
            MediaArtifactSummary,
        )
        for field in fields(contract)
    }
    method_names = {
        name for name, value in getmembers(MediaArtifactAdapter) if isfunction(value)
    } | {name for name, value in getmembers(MediaArtifactEvent) if isfunction(value)}
    forbidden_terms = {
        "validate",
        "codec",
        "duration",
        "transcode",
        "thumbnail",
        "parse",
        "analyze",
        "ingest",
    }

    assert not any(term in name for name in field_names | method_names for term in forbidden_terms)


def test_no_chunk_registration_exists() -> None:
    field_names = {
        field.name
        for contract in (
            MediaArtifactAdapter,
            MediaArtifactEvent,
            MediaArtifactIdentity,
            MediaArtifactSummary,
        )
        for field in fields(contract)
    }
    method_names = {
        name for name, value in getmembers(MediaArtifactAdapter) if isfunction(value)
    } | {name for name, value in getmembers(MediaArtifactEvent) if isfunction(value)}
    forbidden_terms = {
        "chunk",
        "register",
        "registry",
        "segment",
    }

    assert not any(term in name for name in field_names | method_names for term in forbidden_terms)


def test_no_provider_specific_names_appear() -> None:
    enum_values = (
        {artifact_type.value for artifact_type in MediaArtifactType}
        | {status.value for status in MediaArtifactStatus}
        | {capability.value for capability in MediaArtifactCapability}
        | {adapter_kind.value for adapter_kind in MediaArtifactAdapterKind}
    )
    field_names = {
        field.name
        for contract in (
            MediaArtifactAdapter,
            MediaArtifactEvent,
            MediaArtifactIdentity,
            MediaArtifactSummary,
        )
        for field in fields(contract)
    }
    forbidden_terms = {
        "vmix",
        "obs",
        "blackmagic",
        "ndi",
        "sdi",
        "ffmpeg",
        "whisper",
        "dropbox",
        "youtube",
        "devcon",
        "pretalx",
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
            MediaArtifactAdapter,
            MediaArtifactEvent,
            MediaArtifactIdentity,
            MediaArtifactSummary,
        )
        for field in fields(contract)
    }
    method_names = {
        name for name, value in getmembers(MediaArtifactAdapter) if isfunction(value)
    } | {name for name, value in getmembers(MediaArtifactEvent) if isfunction(value)}
    forbidden_terms = {
        "api",
        "database",
        "repository",
        "queue",
        "worker",
        "frontend",
        "watch",
        "dispatch",
        "interpret",
    }

    assert not any(term in name for name in field_names | method_names for term in forbidden_terms)
