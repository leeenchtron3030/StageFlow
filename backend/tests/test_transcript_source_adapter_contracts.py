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
from app.contexts.production.transcript_adapter import (
    TranscriptAdapterCapability,
    TranscriptAdapterIdentity,
    TranscriptAdapterKind,
    TranscriptAdapterStatus,
    TranscriptAdapterSummary,
    TranscriptArtifactType,
    TranscriptSegmentEvent,
    TranscriptSegmentStatus,
    TranscriptSourceAdapter,
)
from app.shared.ids import CorrelationId, EntityId

CONTRACTS = (
    TranscriptSourceAdapter,
    TranscriptSegmentEvent,
    TranscriptAdapterIdentity,
    TranscriptAdapterSummary,
)


def _identity() -> TranscriptAdapterIdentity:
    return TranscriptAdapterIdentity(
        adapter_name="Generic transcript adapter",
        adapter_kind=TranscriptAdapterKind.LOCAL_TRANSCRIPTION_SOURCE,
        stage_label="Main stage",
        language_label="en",
        metadata={"configured": True},
    )


def _adapter() -> TranscriptSourceAdapter:
    return TranscriptSourceAdapter(
        id=EntityId.new(),
        identity=_identity(),
        status=TranscriptAdapterStatus.READY,
        supported_capabilities=[
            TranscriptAdapterCapability.REPORTS_PARTIAL_TRANSCRIPTS,
            TranscriptAdapterCapability.REPORTS_FINAL_TRANSCRIPTS,
            TranscriptAdapterCapability.REPORTS_CONFIDENCE,
        ],
        metadata={"scope": "transcript-reporting"},
    )


def _segment_event(
    segment_status: TranscriptSegmentStatus = TranscriptSegmentStatus.CREATED,
) -> TranscriptSegmentEvent:
    return TranscriptSegmentEvent(
        transcript_segment_identifier="segment-123",
        artifact_type=TranscriptArtifactType.PARTIAL_TRANSCRIPT,
        segment_status=segment_status,
        occurred_at=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
        recording_block_id=EntityId.new(),
        stage_id=EntityId.new(),
        timeline_range_reference="range-123",
        language_label="en",
        text_excerpt="Generic lightweight transcript excerpt.",
        confidence=0.91,
        metadata={"source": "adapter"},
    )


def _field_names() -> set[str]:
    return {field.name for contract in CONTRACTS for field in fields(contract)}


def _method_names() -> set[str]:
    return {
        name
        for contract in (TranscriptSourceAdapter, TranscriptSegmentEvent)
        for name, value in getmembers(contract)
        if isfunction(value)
    }


def test_transcript_source_adapter_creation() -> None:
    adapter = _adapter()

    assert adapter.identity.adapter_name == "Generic transcript adapter"
    assert adapter.status is TranscriptAdapterStatus.READY
    assert adapter.supports_capability(TranscriptAdapterCapability.REPORTS_PARTIAL_TRANSCRIPTS)
    assert not adapter.supports_capability(TranscriptAdapterCapability.REPORTS_TRANSLATIONS)
    assert dict(adapter.metadata) == {"scope": "transcript-reporting"}


def test_transcript_segment_event_creation() -> None:
    segment_event = _segment_event()

    assert segment_event.transcript_segment_identifier == "segment-123"
    assert segment_event.artifact_type is TranscriptArtifactType.PARTIAL_TRANSCRIPT
    assert segment_event.segment_status is TranscriptSegmentStatus.CREATED
    assert segment_event.recording_block_id is not None
    assert segment_event.stage_id is not None
    assert segment_event.timeline_range_reference == "range-123"
    assert segment_event.language_label == "en"
    assert segment_event.text_excerpt == "Generic lightweight transcript excerpt."
    assert segment_event.confidence == 0.91
    assert dict(segment_event.metadata) == {"source": "adapter"}


def test_transcript_segment_event_confidence_describes_source_confidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        TranscriptSegmentEvent(
            transcript_segment_identifier="segment-123",
            artifact_type=TranscriptArtifactType.FINAL_TRANSCRIPT,
            segment_status=TranscriptSegmentStatus.CREATED,
            occurred_at=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
            confidence=1.5,
        )


def test_transcript_artifact_type_allowed_values() -> None:
    assert {artifact_type.value for artifact_type in TranscriptArtifactType} == {
        "partial_transcript",
        "final_transcript",
        "caption",
        "subtitle",
        "word_timestamps",
        "speaker_labels",
        "translation",
        "metadata",
        "unknown",
    }


def test_transcript_segment_status_allowed_values() -> None:
    assert {status.value for status in TranscriptSegmentStatus} == {
        "created",
        "updated",
        "finalized",
        "failed",
        "deleted",
        "unknown",
    }


def test_transcript_adapter_capability_allowed_values() -> None:
    assert {capability.value for capability in TranscriptAdapterCapability} == {
        "reports_partial_transcripts",
        "reports_final_transcripts",
        "reports_word_timestamps",
        "reports_speaker_labels",
        "reports_language",
        "reports_confidence",
        "reports_translations",
        "unknown",
    }


def test_transcript_adapter_identity_creation() -> None:
    identity = _identity()

    assert identity.adapter_name == "Generic transcript adapter"
    assert identity.adapter_kind is TranscriptAdapterKind.LOCAL_TRANSCRIPTION_SOURCE
    assert identity.stage_label == "Main stage"
    assert identity.language_label == "en"
    assert dict(identity.metadata) == {"configured": True}


def test_transcript_adapter_kind_allowed_values() -> None:
    assert {adapter_kind.value for adapter_kind in TranscriptAdapterKind} == {
        "local_transcription_source",
        "cloud_transcription_source",
        "caption_source",
        "manual_transcript_source",
        "simulated_source",
        "unknown",
    }


def test_transcript_adapter_status_allowed_values() -> None:
    assert {status.value for status in TranscriptAdapterStatus} == {
        "unknown",
        "configured",
        "ready",
        "degraded",
        "failed",
        "archived",
    }


def test_transcript_adapter_summary_generation() -> None:
    adapter = _adapter()

    summary = TranscriptAdapterSummary.from_adapter(adapter)

    assert summary.adapter_id == adapter.id
    assert summary.adapter_name == adapter.identity.adapter_name
    assert summary.adapter_kind is TranscriptAdapterKind.LOCAL_TRANSCRIPTION_SOURCE
    assert summary.adapter_status is TranscriptAdapterStatus.READY
    assert summary.capability_count == 3
    assert summary.stage_label == "Main stage"
    assert summary.language_label == "en"


def test_transcript_segment_event_maps_to_production_events_only() -> None:
    adapter = _adapter()
    segment_event = _segment_event(TranscriptSegmentStatus.CREATED)
    received_at = segment_event.occurred_at + timedelta(seconds=2)

    production_event = adapter.production_event_from_segment_event(
        segment_event,
        correlation_id=CorrelationId.new(),
        received_at=received_at,
    )

    assert isinstance(production_event, ProductionEvent)
    assert production_event.event_type is ProductionEventType.TRANSCRIPT_SEGMENT_AVAILABLE
    assert production_event.source is ProductionEventSource.TRANSCRIPT_SYSTEM
    assert production_event.occurred_at == segment_event.occurred_at
    assert production_event.received_at == received_at
    assert production_event.payload.get("transcript_segment_id") == "segment-123"
    assert production_event.payload.get("transcript_artifact_type") == "partial_transcript"
    assert production_event.payload.get("transcript_segment_status") == "created"
    assert production_event.payload.get("timeline_range_reference") == "range-123"
    assert production_event.payload.get("language_label") == "en"
    assert production_event.payload.get("text_excerpt") == "Generic lightweight transcript excerpt."
    assert production_event.payload.get("confidence") == 0.91
    assert {reference.reference_type for reference in production_event.references} == {
        ProductionEventReferenceType.EXTERNAL_OBJECT,
        ProductionEventReferenceType.RECORDING_BLOCK,
        ProductionEventReferenceType.STAGE,
        ProductionEventReferenceType.TIMELINE_RANGE,
    }


def test_allowed_production_event_mappings() -> None:
    expected_types = {
        TranscriptSegmentStatus.CREATED: ProductionEventType.TRANSCRIPT_SEGMENT_AVAILABLE,
        TranscriptSegmentStatus.UPDATED: ProductionEventType.TRANSCRIPT_SEGMENT_AVAILABLE,
        TranscriptSegmentStatus.FINALIZED: ProductionEventType.TRANSCRIPT_SEGMENT_AVAILABLE,
        TranscriptSegmentStatus.FAILED: ProductionEventType.SYSTEM_STATUS_CHANGED,
        TranscriptSegmentStatus.DELETED: ProductionEventType.SYSTEM_STATUS_CHANGED,
        TranscriptSegmentStatus.UNKNOWN: ProductionEventType.SYSTEM_STATUS_CHANGED,
    }

    for segment_status, expected_type in expected_types.items():
        segment_event = _segment_event(segment_status)
        production_event = segment_event.to_production_event(
            correlation_id=CorrelationId.new(),
            received_at=segment_event.occurred_at + timedelta(seconds=1),
        )

        assert production_event.event_type is expected_type


def test_no_observation_generation_exists() -> None:
    assert "observation" not in " ".join(_field_names() | _method_names())


def test_no_transcript_execution_exists() -> None:
    forbidden_terms = {
        "execute",
        "run",
        "transcribe",
        "audio",
        "model",
        "diarize",
        "detect_language",
        "call",
        "file",
    }

    assert not any(
        term in name for name in _field_names() | _method_names() for term in forbidden_terms
    )


def test_no_session_inference_exists() -> None:
    forbidden_terms = {
        "session",
        "speaker_introduced",
        "quote",
        "clip",
        "applause",
        "important",
        "meaning",
        "infer",
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
        {artifact_type.value for artifact_type in TranscriptArtifactType}
        | {status.value for status in TranscriptSegmentStatus}
        | {capability.value for capability in TranscriptAdapterCapability}
        | {adapter_kind.value for adapter_kind in TranscriptAdapterKind}
        | {status.value for status in TranscriptAdapterStatus}
    )
    forbidden_terms = {
        "whisper",
        "deepgram",
        "assemblyai",
        "google",
        "aws",
        "azure",
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
