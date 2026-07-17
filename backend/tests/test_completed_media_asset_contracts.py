from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
from datetime import timedelta
from types import MappingProxyType
from typing import Any, cast

import pytest
from completed_media_asset_fixtures import (
    FILE_SIZE_BYTES,
    FINALIZED_AT,
    MANIFESTED_AT,
    READINESS_ASSESSED_AT,
    make_completed_media_asset,
)

from app.contexts.production.completed_media_asset import (
    CompletedMediaAsset,
    CompletedMediaAssetCompletion,
    CompletedMediaAssetCompletionMethod,
    CompletedMediaAssetContext,
    CompletedMediaAssetFrameRateMode,
    CompletedMediaAssetIntegrity,
    CompletedMediaAssetIntegrityStatus,
    CompletedMediaAssetKind,
    CompletedMediaAssetLocationScheme,
    CompletedMediaAssetManifest,
    CompletedMediaAssetReadiness,
    CompletedMediaAssetReadinessStatus,
    CompletedMediaAssetRelatedResourceKind,
    CompletedMediaAssetRelationship,
    CompletedMediaAssetRuntimeProfile,
    CompletedMediaAssetSummary,
    CompletedMediaAssetTechnicalDescription,
)
from app.contexts.production.timeline import TimelinePosition, TimelineRange
from app.shared.ids import EntityId


def test_valid_completed_segment_preserves_complete_contract() -> None:
    asset = make_completed_media_asset()

    assert asset.kind is CompletedMediaAssetKind.RECORDING_SEGMENT
    assert asset.completion.is_finalized
    assert asset.readiness.status is CompletedMediaAssetReadinessStatus.SAFE_TO_READ
    assert asset.primary_resource.file_size_bytes == FILE_SIZE_BYTES
    assert asset.manifest.asset_id == asset.id
    assert asset.manifest.source_resource_id == asset.primary_resource.id
    assert asset.provenance.manifest_id == asset.manifest.id
    assert asset.provenance.readiness_declaration_id == asset.readiness.id
    assert asset.relationship is not None
    assert asset.relationship.segment_index == 7
    assert asset.technical_description is not None
    assert asset.technical_description.duration == timedelta(seconds=60)


def test_asset_kind_values_are_exact_and_semantically_conservative() -> None:
    assert {kind.value for kind in CompletedMediaAssetKind} == {
        "recording_segment",
        "complete_recording",
        "media_clip",
        "audio_recording",
        "video_recording",
        "other_supported_media",
        "unknown",
    }
    forbidden = {"session_recording", "verified_session", "highlight", "approved_clip"}
    assert forbidden.isdisjoint(kind.value for kind in CompletedMediaAssetKind)


@pytest.mark.parametrize(
    "kind",
    (
        CompletedMediaAssetKind.COMPLETE_RECORDING,
        CompletedMediaAssetKind.MEDIA_CLIP,
        CompletedMediaAssetKind.AUDIO_RECORDING,
        CompletedMediaAssetKind.VIDEO_RECORDING,
        CompletedMediaAssetKind.OTHER_SUPPORTED_MEDIA,
        CompletedMediaAssetKind.UNKNOWN,
    ),
)
def test_non_segment_asset_kinds_do_not_require_segment_relationships(
    kind: CompletedMediaAssetKind,
) -> None:
    asset = make_completed_media_asset(kind=kind, duration=timedelta(hours=2))

    assert asset.kind is kind
    assert asset.relationship is None or asset.relationship.segment_index is None


def test_manifest_is_versioned_and_id_oriented() -> None:
    asset = make_completed_media_asset()
    manifest = asset.manifest

    assert manifest.schema_name == "stageflow.completed_media_asset"
    assert manifest.schema_version == "1.0"
    assert manifest.asset_id == asset.id
    assert manifest.producer_runtime_id == asset.source.runtime_id
    assert manifest.created_at == MANIFESTED_AT
    assert manifest.related_resource_ids == tuple(
        reference.resource_id for reference in asset.related_resources
    )
    assert not {
        "transfer_status",
        "queue_position",
        "processing_status",
    } & {field.name for field in fields(CompletedMediaAssetManifest)}


def test_primary_resource_retains_descriptive_media_and_filesystem_facts() -> None:
    resource = make_completed_media_asset().primary_resource

    assert resource.original_filename == "x7q9.mp4"
    assert resource.media_type == "video/mp4"
    assert resource.container_type == "mp4"
    assert resource.file_size_bytes == FILE_SIZE_BYTES
    assert resource.filesystem_created_at is not None
    assert resource.filesystem_modified_at == FINALIZED_AT
    assert resource.source_volume_id == resource.source_location.volume_id
    assert resource.source_location.location_scheme is (
        CompletedMediaAssetLocationScheme.LOCAL_FILESYSTEM
    )


def test_related_resources_remain_lightweight_id_references() -> None:
    asset = make_completed_media_asset()
    related = asset.related_resources[0]

    assert related.resource_kind is (
        CompletedMediaAssetRelatedResourceKind.RECORDER_SIDECAR_METADATA
    )
    assert related.resource_id in asset.manifest.related_resource_ids
    assert not {"bytes", "stream", "file_handle", "source_location"} & {
        field.name for field in fields(type(related))
    }


def test_source_and_provenance_preserve_runtime_recorder_and_event_ids() -> None:
    asset = make_completed_media_asset()

    assert asset.source.runtime_profile is CompletedMediaAssetRuntimeProfile.AGENT
    assert asset.source.runtime_id == asset.provenance.source_runtime_id
    assert asset.source.host_id == asset.provenance.source_host_id
    assert asset.source.recorder_application_id == asset.provenance.recorder_application_id
    assert asset.source.adapter_id == asset.provenance.adapter_id
    assert asset.source.source_event_id in asset.provenance.source_event_ids
    assert asset.source.recorder_application_version == "9.4"
    assert {profile.value for profile in CompletedMediaAssetRuntimeProfile} == {
        "agent",
        "node",
        "external_compatible_source",
        "unknown",
    }


def test_explicit_partial_context_retains_context_without_session_identity() -> None:
    asset = make_completed_media_asset()

    assert asset.context.stage_id is not None
    assert asset.context.recording_block_id is not None
    assert asset.context.scheduled_activity_id is not None
    assert asset.context.correlation_ids
    assert asset.context.transcript_stream_ids == ("transcript-a", "transcript-b")
    assert "session_id" not in {field.name for field in fields(CompletedMediaAssetContext)}
    assert CompletedMediaAssetContext.unknown() == CompletedMediaAssetContext()


def test_context_supports_one_explicit_timeline_position_or_range() -> None:
    block_id = EntityId.new()
    position = TimelinePosition(block_id, timedelta(seconds=5))
    timeline_range = TimelineRange(
        start=position,
        end=TimelinePosition(block_id, timedelta(seconds=65)),
    )

    positioned = CompletedMediaAssetContext(
        recording_block_id=block_id,
        timeline_position=position,
    )
    ranged = CompletedMediaAssetContext(
        recording_block_id=block_id,
        timeline_range=timeline_range,
    )

    assert positioned.timeline_position == position
    assert ranged.timeline_range == timeline_range


def test_segment_relationship_retains_partial_sequence_without_completion_claim() -> None:
    relationship = make_completed_media_asset().relationship

    assert relationship is not None
    assert relationship.recording_group_id is not None
    assert relationship.segment_index == 7
    assert relationship.previous_asset_id is None
    assert relationship.next_asset_id is None
    assert relationship.is_final_known_segment is False
    assert "session" not in {field.name for field in fields(CompletedMediaAssetRelationship)}


@pytest.mark.parametrize("method", tuple(CompletedMediaAssetCompletionMethod))
def test_every_completion_method_is_a_declaration_not_detection_behavior(
    method: CompletedMediaAssetCompletionMethod,
) -> None:
    completion = CompletedMediaAssetCompletion(
        id=EntityId.new(),
        method=method,
        is_finalized=True,
        finalized_at=FINALIZED_AT,
        declaring_runtime_or_adapter_id=EntityId.new(),
    )

    assert completion.method is method
    assert completion.is_finalized


def test_readiness_is_categorical_and_has_no_score_or_confidence() -> None:
    readiness = CompletedMediaAssetReadiness(
        id=EntityId.new(),
        status=CompletedMediaAssetReadinessStatus.NOT_SAFE_TO_READ,
        assessed_at=READINESS_ASSESSED_AT,
        limitations=("active writer may still exist",),
    )

    assert readiness.status is CompletedMediaAssetReadinessStatus.NOT_SAFE_TO_READ
    assert {status.value for status in CompletedMediaAssetReadinessStatus} == {
        "safe_to_read",
        "not_safe_to_read",
        "unknown",
    }
    assert not {"score", "confidence", "probability"} & {
        field.name for field in fields(CompletedMediaAssetReadiness)
    }


@pytest.mark.parametrize("status", tuple(CompletedMediaAssetIntegrityStatus))
def test_integrity_statuses_remain_categorical_declarations(
    status: CompletedMediaAssetIntegrityStatus,
) -> None:
    integrity = CompletedMediaAssetIntegrity(
        id=EntityId.new(),
        status=status,
        assessed_at=READINESS_ASSESSED_AT,
        assessor_id=EntityId.new(),
    )

    assert integrity.status is status
    assert integrity.checksum_algorithm is None
    assert integrity.checksum_value is None


@pytest.mark.parametrize(
    "status",
    (
        CompletedMediaAssetIntegrityStatus.FAILED,
        CompletedMediaAssetIntegrityStatus.NOT_ASSESSED,
        CompletedMediaAssetIntegrityStatus.UNKNOWN,
    ),
)
def test_nonconfirmed_integrity_does_not_replace_safe_readiness(
    status: CompletedMediaAssetIntegrityStatus,
) -> None:
    asset = make_completed_media_asset()
    assert asset.integrity is not None
    integrity = CompletedMediaAssetIntegrity(
        id=asset.integrity.id,
        status=status,
        assessed_at=asset.integrity.assessed_at,
        assessor_id=asset.integrity.assessor_id,
    )

    retained = replace(asset, integrity=integrity)

    assert retained.readiness.status is CompletedMediaAssetReadinessStatus.SAFE_TO_READ
    assert retained.integrity is not None
    assert retained.integrity.status is status
    assert retained.integrity.checksum_value is None


def test_technical_description_preserves_probe_compatible_facts() -> None:
    technical = make_completed_media_asset().technical_description

    assert technical is not None
    assert technical.container_format == "mp4"
    assert technical.video_codec == "h264"
    assert technical.audio_codec == "aac"
    assert technical.width == 1920
    assert technical.height == 1080
    assert technical.frame_rate == 29.97
    assert technical.audio_sample_rate == 48000
    assert technical.audio_channel_count == 2
    assert technical.media_stream_count == 2
    assert CompletedMediaAssetFrameRateMode.CONSTANT.value == "constant"


def test_technical_description_may_be_partial() -> None:
    technical = CompletedMediaAssetTechnicalDescription(audio_codec="pcm_s24le")

    assert technical.audio_codec == "pcm_s24le"
    assert technical.container_format is None
    assert technical.duration is None


def test_summary_is_complete_but_omits_sensitive_source_location() -> None:
    asset = make_completed_media_asset(
        source_location_value="/Users/synthetic/private/event/x7q9.mp4"
    )

    summary = CompletedMediaAssetSummary.from_asset(asset)

    assert summary.asset_id == asset.id
    assert summary.manifest_version == "1.0"
    assert summary.original_filename == "x7q9.mp4"
    assert summary.duration == timedelta(seconds=60)
    assert summary.segment_index == 7
    assert summary.finalized_at == FINALIZED_AT
    assert summary.integrity_status is CompletedMediaAssetIntegrityStatus.CONFIRMED
    summary_values = tuple(getattr(summary, field.name) for field in fields(summary))
    assert not any("/Users/synthetic" in str(value) for value in summary_values)
    assert "source_location" not in {field.name for field in fields(summary)}


def test_contracts_and_nested_metadata_are_immutable() -> None:
    source_metadata = {"nested": {"items": ["a", "b"]}}
    asset = make_completed_media_asset()
    source = replace(asset.source, metadata=source_metadata)
    source_metadata["nested"]["items"].append("caller-mutation")

    assert isinstance(source.metadata, MappingProxyType)
    nested = cast(MappingProxyType[str, Any], source.metadata["nested"])
    assert nested["items"] == ("a", "b")
    with pytest.raises(TypeError):
        cast(dict[str, Any], source.metadata)["new"] = True
    with pytest.raises(FrozenInstanceError):
        asset.kind = CompletedMediaAssetKind.MEDIA_CLIP  # pyright: ignore[reportAttributeAccessIssue]


def test_asset_metadata_is_supplementary_and_deep_frozen() -> None:
    asset = make_completed_media_asset()

    assert isinstance(asset.metadata, MappingProxyType)
    assert isinstance(asset.metadata["compatibility"], MappingProxyType)
    assert asset.metadata["tags"] == ("finalized",)
    assert asset.kind is CompletedMediaAssetKind.RECORDING_SEGMENT


def test_completion_readiness_integrity_and_time_fields_remain_separate() -> None:
    asset = make_completed_media_asset()

    assert asset.recorded_end_at < asset.finalized_at  # type: ignore[operator]
    assert asset.finalized_at < asset.readiness.assessed_at
    assert asset.integrity is not None
    assert asset.readiness.assessed_at < asset.integrity.assessed_at
    assert asset.integrity.assessed_at < asset.manifested_at
    assert len(
        {
            asset.recorded_end_at,
            asset.finalized_at,
            asset.readiness.assessed_at,
            asset.integrity.assessed_at,
            asset.manifested_at,
            asset.primary_resource.filesystem_modified_at,
        }
    ) >= 5


def test_completed_asset_has_no_session_or_downstream_status_fields() -> None:
    forbidden = {
        "session_id",
        "transfer_status",
        "queue_position",
        "ai_status",
        "editorial_status",
        "publication_status",
        "operational_state",
    }

    assert forbidden.isdisjoint(field.name for field in fields(CompletedMediaAsset))
