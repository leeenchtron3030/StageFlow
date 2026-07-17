from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, cast

import pytest
from completed_media_asset_fixtures import (
    FINALIZED_AT,
    MANIFESTED_AT,
    READINESS_ASSESSED_AT,
    make_completed_media_asset,
)

from app.contexts.production.completed_media_asset import (
    CompletedMediaAsset,
    CompletedMediaAssetContext,
    CompletedMediaAssetIntegrity,
    CompletedMediaAssetIntegrityStatus,
    CompletedMediaAssetKind,
    CompletedMediaAssetLocationScheme,
    CompletedMediaAssetReadinessStatus,
    CompletedMediaAssetRelationship,
    CompletedMediaAssetResource,
    CompletedMediaAssetResourceReference,
    CompletedMediaAssetSourceLocation,
    CompletedMediaAssetTechnicalDescription,
)
from app.contexts.production.timeline import TimelinePosition
from app.shared.ids import EntityId


def test_non_finalized_completion_cannot_form_completed_asset() -> None:
    asset = make_completed_media_asset()

    with pytest.raises(ValueError, match="requires finalized"):
        replace(asset, completion=replace(asset.completion, is_finalized=False))


@pytest.mark.parametrize(
    "status",
    (
        CompletedMediaAssetReadinessStatus.NOT_SAFE_TO_READ,
        CompletedMediaAssetReadinessStatus.UNKNOWN,
    ),
)
def test_unsafe_or_unknown_readiness_cannot_form_completed_asset(
    status: CompletedMediaAssetReadinessStatus,
) -> None:
    asset = make_completed_media_asset()

    with pytest.raises(ValueError, match="safe-to-read"):
        replace(asset, readiness=replace(asset.readiness, status=status))


def test_primary_resource_is_a_required_constructor_argument() -> None:
    asset = make_completed_media_asset()
    constructor = cast(Any, CompletedMediaAsset)

    with pytest.raises(TypeError, match="primary_resource"):
        constructor(
            id=asset.id,
            kind=asset.kind,
            manifest=asset.manifest,
            source=asset.source,
            provenance=asset.provenance,
            context=asset.context,
            completion=asset.completion,
            readiness=asset.readiness,
            finalized_at=asset.finalized_at,
            manifested_at=asset.manifested_at,
        )


def test_manifest_asset_and_primary_resource_ids_must_match() -> None:
    asset = make_completed_media_asset()

    with pytest.raises(ValueError, match="Manifest asset ID"):
        replace(asset, manifest=replace(asset.manifest, asset_id=EntityId.new()))
    with pytest.raises(ValueError, match="source resource"):
        replace(
            asset,
            manifest=replace(asset.manifest, source_resource_id=EntityId.new()),
        )


def test_manifest_related_resources_must_match_asset_references() -> None:
    asset = make_completed_media_asset()

    with pytest.raises(ValueError, match="related resources"):
        replace(asset, manifest=replace(asset.manifest, related_resource_ids=()))


def test_source_manifest_and_provenance_runtime_ids_cannot_conflict() -> None:
    asset = make_completed_media_asset()

    with pytest.raises(ValueError, match="Manifest producer Runtime"):
        replace(asset, source=replace(asset.source, runtime_id=EntityId.new()))
    with pytest.raises(ValueError, match="provenance Runtime"):
        replace(
            asset,
            provenance=replace(asset.provenance, source_runtime_id=EntityId.new()),
        )


def test_optional_source_and_provenance_id_conflicts_are_rejected() -> None:
    asset = make_completed_media_asset()

    with pytest.raises(ValueError, match="host IDs"):
        replace(asset, provenance=replace(asset.provenance, source_host_id=EntityId.new()))
    with pytest.raises(ValueError, match="Source Event ID"):
        replace(asset, provenance=replace(asset.provenance, source_event_ids=()))


def test_integrity_identity_and_checksum_size_must_match_asset() -> None:
    asset = make_completed_media_asset()
    assert asset.integrity is not None

    with pytest.raises(ValueError, match="integrity ID"):
        replace(asset, integrity=replace(asset.integrity, id=EntityId.new()))
    with pytest.raises(ValueError, match="Checksum byte size"):
        replace(
            asset,
            integrity=replace(asset.integrity, checksum_byte_size=1),
        )


def test_checksum_fields_are_all_or_none() -> None:
    with pytest.raises(ValueError, match="supplied together"):
        CompletedMediaAssetIntegrity(
            id=EntityId.new(),
            status=CompletedMediaAssetIntegrityStatus.CONFIRMED,
            assessed_at=READINESS_ASSESSED_AT,
            assessor_id=EntityId.new(),
            checksum_algorithm="sha256",
        )


def test_resource_size_filename_and_location_are_validated_without_io() -> None:
    location = CompletedMediaAssetSourceLocation(
        location_scheme=CompletedMediaAssetLocationScheme.LOCAL_FILESYSTEM,
        location_value="/synthetic/media.mp4",
    )

    with pytest.raises(ValueError, match="must not be negative"):
        CompletedMediaAssetResource(
            id=EntityId.new(),
            original_filename="media.mp4",
            source_location=location,
            file_size_bytes=-1,
        )
    with pytest.raises(ValueError, match="must not contain a source path"):
        CompletedMediaAssetResource(
            id=EntityId.new(),
            original_filename="/synthetic/media.mp4",
            source_location=location,
            file_size_bytes=0,
        )
    with pytest.raises(ValueError, match="must not embed credentials"):
        CompletedMediaAssetSourceLocation(
            location_scheme=CompletedMediaAssetLocationScheme.URI,
            location_value="smb://user:password@synthetic.invalid/media.mp4",
        )


def test_segment_indexes_and_durations_reject_invalid_values() -> None:
    with pytest.raises(ValueError, match="segment index"):
        CompletedMediaAssetRelationship(segment_index=-1)
    with pytest.raises(ValueError, match="sequence number"):
        CompletedMediaAssetRelationship(sequence_number=-1)
    with pytest.raises(ValueError, match="must not be negative"):
        CompletedMediaAssetRelationship(actual_duration=timedelta(seconds=-1))


def test_context_rejects_conflicting_or_duplicate_timeline_authority() -> None:
    block_id = EntityId.new()
    position = TimelinePosition(block_id, timedelta(seconds=1))

    with pytest.raises(ValueError, match="two timeline anchors"):
        CompletedMediaAssetContext(
            timeline_position=position,
            timeline_range=cast(Any, object()),
        )
    with pytest.raises(ValueError, match="must match"):
        CompletedMediaAssetContext(
            recording_block_id=EntityId.new(),
            timeline_position=position,
        )


def test_segment_relationship_fields_require_segment_kind() -> None:
    segment = make_completed_media_asset()
    clip = make_completed_media_asset(kind=CompletedMediaAssetKind.MEDIA_CLIP)
    assert segment.relationship is not None

    with pytest.raises(ValueError, match="recording_segment"):
        replace(clip, relationship=segment.relationship)


def test_related_resource_identity_cannot_conflict_or_include_primary() -> None:
    asset = make_completed_media_asset()
    original = asset.related_resources[0]
    conflicting = CompletedMediaAssetResourceReference(
        resource_id=original.resource_id,
        resource_kind=original.resource_kind,
        label="conflicting description",
    )

    with pytest.raises(ValueError, match="conflicting resources"):
        replace(asset, related_resources=(original, conflicting))
    primary_as_related = replace(original, resource_id=asset.primary_resource.id)
    with pytest.raises(ValueError, match="Primary resource"):
        replace(
            asset,
            manifest=replace(
                asset.manifest,
                related_resource_ids=(asset.primary_resource.id,),
            ),
            related_resources=(primary_as_related,),
        )


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    (
        ("width", 0),
        ("height", -1),
        ("frame_rate", 0.0),
        ("audio_sample_rate", 0),
        ("audio_channel_count", -1),
        ("media_stream_count", 0),
    ),
)
def test_technical_numeric_values_must_be_positive(
    field_name: str,
    invalid_value: int | float,
) -> None:
    kwargs = cast(dict[str, Any], {field_name: invalid_value})

    with pytest.raises(ValueError, match="positive"):
        CompletedMediaAssetTechnicalDescription(**kwargs)


def test_technical_and_resource_container_and_duration_must_agree() -> None:
    asset = make_completed_media_asset()
    assert asset.technical_description is not None

    with pytest.raises(ValueError, match="container"):
        replace(
            asset,
            technical_description=replace(
                asset.technical_description,
                container_format="matroska",
            ),
        )
    with pytest.raises(ValueError, match="durations"):
        replace(
            asset,
            technical_description=replace(
                asset.technical_description,
                duration=timedelta(seconds=59),
            ),
        )


def test_new_first_class_timestamps_must_be_timezone_aware() -> None:
    asset = make_completed_media_asset()
    naive = datetime(2026, 7, 16, 10, 5)

    with pytest.raises(ValueError, match="timezone-aware"):
        replace(asset.completion, finalized_at=naive)
    with pytest.raises(ValueError, match="timezone-aware"):
        replace(asset.readiness, assessed_at=naive)
    with pytest.raises(ValueError, match="timezone-aware"):
        replace(asset.manifest, created_at=naive)
    with pytest.raises(ValueError, match="timezone-aware"):
        replace(asset.primary_resource, filesystem_modified_at=naive)
    assert asset.integrity is not None
    with pytest.raises(ValueError, match="timezone-aware"):
        replace(asset.integrity, assessed_at=naive)


def test_directly_comparable_timestamp_ordering_is_enforced() -> None:
    asset = make_completed_media_asset()
    assert asset.recorded_end_at is not None

    with pytest.raises(ValueError, match="Recorded start"):
        replace(asset, recorded_start_at=asset.recorded_end_at + timedelta(seconds=1))
    with pytest.raises(ValueError, match="Finalization"):
        replace(asset, recorded_end_at=FINALIZED_AT + timedelta(seconds=1))
    with pytest.raises(ValueError, match="Readiness assessment"):
        replace(
            asset,
            readiness=replace(
                asset.readiness,
                assessed_at=FINALIZED_AT - timedelta(seconds=1),
            ),
        )
    with pytest.raises(ValueError, match="Manifest creation"):
        replace(
            asset,
            manifest=replace(
                asset.manifest,
                created_at=FINALIZED_AT - timedelta(seconds=1),
            ),
            manifested_at=FINALIZED_AT - timedelta(seconds=1),
        )
    assert MANIFESTED_AT > FINALIZED_AT


def test_metadata_rejects_credentials_and_non_serializable_objects() -> None:
    asset = make_completed_media_asset()

    with pytest.raises(ValueError, match="credential material"):
        replace(asset, metadata={"access_token": "synthetic-secret"})
    with pytest.raises(ValueError, match="serialization-friendly"):
        replace(asset, metadata={"active_object": object()})


def test_asset_relationships_cannot_reference_the_asset_itself() -> None:
    asset = make_completed_media_asset()
    assert asset.relationship is not None

    with pytest.raises(ValueError, match="must not reference itself"):
        replace(
            asset,
            relationship=replace(asset.relationship, previous_asset_id=asset.id),
        )


def test_integrity_is_optional_when_provenance_does_not_claim_it() -> None:
    asset = make_completed_media_asset(include_integrity=False)

    assert asset.integrity is None
    assert asset.provenance.integrity_declaration_id is None
