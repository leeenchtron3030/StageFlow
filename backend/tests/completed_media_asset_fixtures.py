from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.contexts.production.completed_media_asset import (
    CompletedMediaAsset,
    CompletedMediaAssetCompletion,
    CompletedMediaAssetCompletionMethod,
    CompletedMediaAssetContext,
    CompletedMediaAssetIntegrity,
    CompletedMediaAssetIntegrityStatus,
    CompletedMediaAssetKind,
    CompletedMediaAssetLocationScheme,
    CompletedMediaAssetManifest,
    CompletedMediaAssetProvenance,
    CompletedMediaAssetReadiness,
    CompletedMediaAssetReadinessStatus,
    CompletedMediaAssetRelatedResourceKind,
    CompletedMediaAssetRelationship,
    CompletedMediaAssetResource,
    CompletedMediaAssetResourceReference,
    CompletedMediaAssetRuntimeProfile,
    CompletedMediaAssetSource,
    CompletedMediaAssetSourceLocation,
    CompletedMediaAssetTechnicalDescription,
)
from app.shared.ids import CorrelationId, EntityId

FILESYSTEM_CREATED_AT = datetime(2026, 7, 16, 10, 2, tzinfo=UTC)
RECORDED_START_AT = datetime(2026, 7, 16, 10, 3, tzinfo=UTC)
RECORDED_END_AT = datetime(2026, 7, 16, 10, 5, tzinfo=UTC)
FINALIZED_AT = datetime(2026, 7, 16, 10, 5, 1, tzinfo=UTC)
READINESS_ASSESSED_AT = datetime(2026, 7, 16, 10, 5, 3, tzinfo=UTC)
INTEGRITY_ASSESSED_AT = datetime(2026, 7, 16, 10, 5, 3, 500000, tzinfo=UTC)
MANIFESTED_AT = datetime(2026, 7, 16, 10, 5, 4, tzinfo=UTC)
FILE_SIZE_BYTES = 1_048_576


def make_completed_media_asset(
    *,
    kind: CompletedMediaAssetKind = CompletedMediaAssetKind.RECORDING_SEGMENT,
    runtime_profile: CompletedMediaAssetRuntimeProfile = (
        CompletedMediaAssetRuntimeProfile.AGENT
    ),
    asset_id: EntityId | None = None,
    runtime_id: EntityId | None = None,
    filename: str = "x7q9.mp4",
    source_location_value: str = "/synthetic/source/x7q9.mp4",
    duration: timedelta = timedelta(seconds=60),
    segment_index: int = 7,
    is_finalized: bool = True,
    readiness_status: CompletedMediaAssetReadinessStatus = (
        CompletedMediaAssetReadinessStatus.SAFE_TO_READ
    ),
    include_integrity: bool = True,
    context: CompletedMediaAssetContext | None = None,
) -> CompletedMediaAsset:
    resolved_asset_id = asset_id or EntityId.new()
    resolved_runtime_id = runtime_id or EntityId.new()
    manifest_id = EntityId.new()
    primary_resource_id = EntityId.new()
    related_resource_id = EntityId.new()
    host_id = EntityId.new()
    recorder_id = EntityId.new()
    adapter_id = EntityId.new()
    producer_id = EntityId.new()
    source_event_id = EntityId.new()
    readiness_id = EntityId.new()
    integrity_id = EntityId.new() if include_integrity else None
    stage_id = EntityId.new()
    recording_block_id = EntityId.new()
    recording_group_id = EntityId.new()
    primary = CompletedMediaAssetResource(
        id=primary_resource_id,
        original_filename=filename,
        source_location=CompletedMediaAssetSourceLocation(
            location_scheme=CompletedMediaAssetLocationScheme.LOCAL_FILESYSTEM,
            location_value=source_location_value,
            volume_id=EntityId.new(),
            host_id=host_id,
            metadata={"visibility": "internal"},
        ),
        file_size_bytes=FILE_SIZE_BYTES,
        media_type="video/mp4",
        container_type="mp4",
        filesystem_created_at=FILESYSTEM_CREATED_AT,
        filesystem_modified_at=FINALIZED_AT,
        metadata={"recorder_file_reference": "synthetic"},
    )
    related = CompletedMediaAssetResourceReference(
        resource_id=related_resource_id,
        resource_kind=CompletedMediaAssetRelatedResourceKind.RECORDER_SIDECAR_METADATA,
        label="synthetic recorder sidecar",
    )
    manifest = CompletedMediaAssetManifest(
        id=manifest_id,
        schema_name="stageflow.completed_media_asset",
        schema_version="1.0",
        asset_id=resolved_asset_id,
        created_at=MANIFESTED_AT,
        producer_runtime_id=resolved_runtime_id,
        source_resource_id=primary_resource_id,
        related_resource_ids=(related_resource_id,),
        metadata={"serialization_contract": "ed-0048"},
    )
    source = CompletedMediaAssetSource(
        runtime_id=resolved_runtime_id,
        runtime_profile=runtime_profile,
        host_id=host_id,
        recorder_application_id=recorder_id,
        recorder_application_version="9.4",
        adapter_id=adapter_id,
        producer_id=producer_id,
        source_event_id=source_event_id,
        compatibility_identifiers=("generic-media-v1", "mp4"),
        metadata={"deployment_provenance": "descriptive_only"},
    )
    completion = CompletedMediaAssetCompletion(
        id=EntityId.new(),
        method=CompletedMediaAssetCompletionMethod.CLOSED_SEGMENT_NOTIFICATION,
        is_finalized=is_finalized,
        finalized_at=FINALIZED_AT,
        declaring_runtime_or_adapter_id=adapter_id,
        source_reference_ids=(primary_resource_id,),
        completion_marker_reference_id=related_resource_id,
    )
    readiness = CompletedMediaAssetReadiness(
        id=readiness_id,
        status=readiness_status,
        assessed_at=READINESS_ASSESSED_AT,
        assessment_method_identifiers=("closed-handle-check", "stable-observation"),
        supporting_check_ids=(EntityId.new(), EntityId.new()),
        limitations=("readability does not prove semantic correctness",),
    )
    integrity = (
        CompletedMediaAssetIntegrity(
            id=integrity_id,
            status=CompletedMediaAssetIntegrityStatus.CONFIRMED,
            assessed_at=INTEGRITY_ASSESSED_AT,
            assessor_id=resolved_runtime_id,
            checksum_algorithm="sha256",
            checksum_value="a" * 64,
            checksum_byte_size=FILE_SIZE_BYTES,
            container_probe_status=CompletedMediaAssetIntegrityStatus.CONFIRMED,
            media_readability_status=CompletedMediaAssetIntegrityStatus.CONFIRMED,
            source_consistency_status=CompletedMediaAssetIntegrityStatus.CONFIRMED,
        )
        if integrity_id is not None
        else None
    )
    provenance = CompletedMediaAssetProvenance(
        source_runtime_id=resolved_runtime_id,
        finalized_at=FINALIZED_AT,
        readiness_declaration_id=readiness_id,
        manifest_id=manifest_id,
        source_host_id=host_id,
        recorder_application_id=recorder_id,
        producer_id=producer_id,
        source_event_ids=(source_event_id,),
        recording_started_at=RECORDED_START_AT,
        recording_ended_at=RECORDED_END_AT,
        integrity_declaration_id=integrity_id,
        adapter_id=adapter_id,
    )
    resolved_context = context or CompletedMediaAssetContext(
        stage_id=stage_id,
        recording_block_id=recording_block_id,
        scheduled_activity_id=EntityId.new(),
        correlation_ids=(CorrelationId.new(), CorrelationId.new()),
        recording_source_id=recorder_id,
        transcript_stream_ids=("transcript-b", "transcript-a"),
        metadata={"authority": "explicit_runtime_context"},
    )
    relationship = (
        CompletedMediaAssetRelationship(
            recording_group_id=recording_group_id,
            segment_index=segment_index,
            sequence_number=segment_index,
            expected_segment_duration=timedelta(seconds=60),
            actual_duration=duration,
            is_first_known_segment=segment_index == 0,
            is_final_known_segment=False,
        )
        if kind is CompletedMediaAssetKind.RECORDING_SEGMENT
        else CompletedMediaAssetRelationship(recording_group_id=recording_group_id)
        if kind is CompletedMediaAssetKind.COMPLETE_RECORDING
        else None
    )
    return CompletedMediaAsset(
        id=resolved_asset_id,
        kind=kind,
        manifest=manifest,
        primary_resource=primary,
        related_resources=(related,),
        source=source,
        provenance=provenance,
        context=resolved_context,
        relationship=relationship,
        completion=completion,
        readiness=readiness,
        integrity=integrity,
        technical_description=CompletedMediaAssetTechnicalDescription(
            container_format="mp4",
            video_codec="h264",
            audio_codec="aac",
            width=1920,
            height=1080,
            frame_rate=29.97,
            audio_sample_rate=48000,
            audio_channel_count=2,
            duration=duration,
            timecode_start="10:00:00:00",
            timecode_end="10:01:00:00",
            media_stream_count=2,
        ),
        finalized_at=FINALIZED_AT,
        manifested_at=MANIFESTED_AT,
        recorded_start_at=RECORDED_START_AT,
        recorded_end_at=RECORDED_END_AT,
        metadata={"compatibility": {"profile": "shared"}, "tags": ["finalized"]},
    )
