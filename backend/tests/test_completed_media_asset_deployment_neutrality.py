from __future__ import annotations

from dataclasses import fields, replace
from datetime import timedelta

import pytest
from completed_media_asset_fixtures import make_completed_media_asset

from app.contexts.production.completed_media_asset import (
    CompletedMediaAssetContext,
    CompletedMediaAssetKind,
    CompletedMediaAssetReadinessStatus,
    CompletedMediaAssetRelatedResourceKind,
    CompletedMediaAssetResourceReference,
    CompletedMediaAssetRuntimeProfile,
    CompletedMediaAssetSummary,
)
from app.shared.ids import CorrelationId, EntityId


@pytest.mark.parametrize(
    "profile",
    (
        CompletedMediaAssetRuntimeProfile.AGENT,
        CompletedMediaAssetRuntimeProfile.NODE,
        CompletedMediaAssetRuntimeProfile.EXTERNAL_COMPATIBLE_SOURCE,
        CompletedMediaAssetRuntimeProfile.DEVELOPMENT,
        CompletedMediaAssetRuntimeProfile.UNKNOWN,
    ),
)
def test_every_runtime_profile_uses_the_same_canonical_contract(
    profile: CompletedMediaAssetRuntimeProfile,
) -> None:
    asset = make_completed_media_asset(runtime_profile=profile)

    assert asset.source.runtime_profile is profile
    assert CompletedMediaAssetRuntimeProfile(profile.value) is profile
    assert asset.kind is CompletedMediaAssetKind.RECORDING_SEGMENT
    assert asset.readiness.status is CompletedMediaAssetReadinessStatus.SAFE_TO_READ
    assert asset.manifest.asset_id == asset.id


@pytest.mark.parametrize(
    "profile",
    (
        CompletedMediaAssetRuntimeProfile.AGENT,
        CompletedMediaAssetRuntimeProfile.NODE,
    ),
)
def test_agent_and_node_receive_identical_readiness_validation(
    profile: CompletedMediaAssetRuntimeProfile,
) -> None:
    asset = make_completed_media_asset(runtime_profile=profile)

    with pytest.raises(ValueError, match="safe-to-read"):
        replace(
            asset,
            readiness=replace(
                asset.readiness,
                status=CompletedMediaAssetReadinessStatus.NOT_SAFE_TO_READ,
            ),
        )


def test_deployment_profile_changes_provenance_not_asset_identity_semantics() -> None:
    asset_id = EntityId.new()
    agent = make_completed_media_asset(
        asset_id=asset_id,
        runtime_profile=CompletedMediaAssetRuntimeProfile.AGENT,
    )
    node = make_completed_media_asset(
        asset_id=asset_id,
        runtime_profile=CompletedMediaAssetRuntimeProfile.NODE,
    )
    development = make_completed_media_asset(
        asset_id=asset_id,
        runtime_profile=CompletedMediaAssetRuntimeProfile.DEVELOPMENT,
    )

    assert agent.id == node.id == development.id == asset_id
    assert agent.kind is node.kind is development.kind
    assert agent.readiness.status is node.readiness.status is development.readiness.status
    assert agent.integrity is not None
    assert node.integrity is not None
    assert development.integrity is not None
    assert agent.integrity.status is node.integrity.status is development.integrity.status
    assert {
        agent.source.runtime_profile,
        node.source.runtime_profile,
        development.source.runtime_profile,
    } == {
        CompletedMediaAssetRuntimeProfile.AGENT,
        CompletedMediaAssetRuntimeProfile.NODE,
        CompletedMediaAssetRuntimeProfile.DEVELOPMENT,
    }


def test_development_asset_provenance_is_first_class_without_metadata() -> None:
    asset = make_completed_media_asset(
        runtime_profile=CompletedMediaAssetRuntimeProfile.DEVELOPMENT,
    )
    source_without_metadata = replace(asset.source, metadata={})

    rebuilt = replace(asset, source=source_without_metadata)

    assert rebuilt.source.runtime_profile is CompletedMediaAssetRuntimeProfile.DEVELOPMENT
    assert rebuilt.source.metadata == {}


def test_optional_runtime_capabilities_do_not_create_asset_tiers() -> None:
    asset = make_completed_media_asset()
    sparse_source = replace(
        asset.source,
        host_id=None,
        recorder_application_id=None,
        recorder_application_version=None,
        adapter_id=None,
        producer_id=None,
        source_event_id=None,
        compatibility_identifiers=(),
    )
    sparse_provenance = replace(
        asset.provenance,
        source_host_id=None,
        recorder_application_id=None,
        producer_id=None,
        source_event_ids=(),
        adapter_id=None,
    )

    sparse = replace(asset, source=sparse_source, provenance=sparse_provenance)

    assert sparse.source.runtime_id == asset.source.runtime_id
    assert sparse.completion.is_finalized
    assert sparse.readiness.status is CompletedMediaAssetReadinessStatus.SAFE_TO_READ


def test_arbitrary_structured_and_misleading_filenames_are_equally_valid() -> None:
    stage_id = EntityId.new()
    block_id = EntityId.new()
    context = CompletedMediaAssetContext(stage_id=stage_id, recording_block_id=block_id)

    for filename in (
        "recording001.mp4",
        "MAINSTAGE_DAY1_SESSION4_0007.mkv",
        "STAGE_B_BUT_NOT_AUTHORITATIVE.mov",
        "abc123.mov",
    ):
        asset = make_completed_media_asset(filename=filename, context=context)
        assert asset.context.stage_id == stage_id
        assert asset.context.recording_block_id == block_id
        assert asset.primary_resource.original_filename == filename


def test_filename_and_transfer_destination_changes_do_not_force_asset_identity_change() -> None:
    asset_id = EntityId.new()
    first = make_completed_media_asset(
        asset_id=asset_id,
        filename="before.mov",
        source_location_value="/synthetic/source/before.mov",
    )
    relocated = make_completed_media_asset(
        asset_id=asset_id,
        filename="after.mov",
        source_location_value="smb://synthetic.invalid/transfer/after.mov",
    )

    assert first.id == relocated.id == asset_id
    assert first.primary_resource.original_filename != relocated.primary_resource.original_filename
    assert first.primary_resource.source_location != relocated.primary_resource.source_location


def test_duplicate_filenames_do_not_collapse_distinct_asset_identity() -> None:
    first = make_completed_media_asset(filename="duplicate.mp4")
    second = make_completed_media_asset(filename="duplicate.mp4")

    assert first.id != second.id
    assert first.primary_resource.original_filename == second.primary_resource.original_filename


def test_segments_allow_non_sixty_second_duration_missing_neighbors_and_gaps() -> None:
    segment = make_completed_media_asset(
        duration=timedelta(seconds=37, milliseconds=250),
        segment_index=19,
    )

    assert segment.relationship is not None
    assert segment.relationship.segment_index == 19
    assert segment.relationship.previous_asset_id is None
    assert segment.relationship.next_asset_id is None
    assert segment.relationship.actual_duration == timedelta(seconds=37, milliseconds=250)


def test_complete_recording_does_not_require_segments_or_claim_session_completion() -> None:
    recording = make_completed_media_asset(
        kind=CompletedMediaAssetKind.COMPLETE_RECORDING,
        duration=timedelta(hours=2),
    )

    assert recording.relationship is not None
    assert recording.relationship.segment_index is None
    assert recording.technical_description is not None
    assert recording.technical_description.duration == timedelta(hours=2)
    assert "session_id" not in {field.name for field in fields(recording)}


def test_id_and_string_collections_normalize_independently_of_input_order() -> None:
    asset = make_completed_media_asset()
    correlation_a = CorrelationId.new()
    correlation_b = CorrelationId.new()
    event_a = EntityId.new()
    event_b = EntityId.new()
    check_a = EntityId.new()
    check_b = EntityId.new()
    context_forward = replace(
        asset.context,
        correlation_ids=(correlation_b, correlation_a, correlation_b),
        transcript_stream_ids=("z", "a", "z"),
    )
    context_reverse = replace(
        asset.context,
        correlation_ids=(correlation_a, correlation_b),
        transcript_stream_ids=("a", "z"),
    )
    provenance_forward = replace(asset.provenance, source_event_ids=(event_b, event_a))
    provenance_reverse = replace(asset.provenance, source_event_ids=(event_a, event_b))
    readiness_forward = replace(
        asset.readiness,
        assessment_method_identifiers=("z", "a", "z"),
        supporting_check_ids=(check_b, check_a),
        limitations=("z", "a"),
    )
    readiness_reverse = replace(
        asset.readiness,
        assessment_method_identifiers=("a", "z"),
        supporting_check_ids=(check_a, check_b),
        limitations=("a", "z"),
    )

    assert context_forward == context_reverse
    assert provenance_forward == provenance_reverse
    assert readiness_forward == readiness_reverse


def test_related_resource_and_manifest_order_are_deterministic() -> None:
    asset = make_completed_media_asset()
    first = asset.related_resources[0]
    second = CompletedMediaAssetResourceReference(
        resource_id=EntityId.new(),
        resource_kind=CompletedMediaAssetRelatedResourceKind.CHECKSUM_SIDECAR,
    )
    ids = (first.resource_id, second.resource_id)
    manifest = replace(asset.manifest, related_resource_ids=tuple(reversed(ids)))

    ordered = replace(
        asset,
        manifest=manifest,
        related_resources=(second, first),
    )

    assert tuple(reference.resource_id for reference in ordered.related_resources) == (
        ordered.manifest.related_resource_ids
    )
    assert ordered.manifest.related_resource_ids == tuple(
        sorted(ids, key=lambda value: value.value)
    )


def test_metadata_order_does_not_change_contract_or_summary_values() -> None:
    asset = make_completed_media_asset(include_integrity=False)
    forward = replace(asset, metadata={"a": 1, "b": 2})
    reverse = replace(asset, metadata={"b": 2, "a": 1})

    assert forward == reverse
    assert CompletedMediaAssetSummary.from_asset(forward) == (
        CompletedMediaAssetSummary.from_asset(reverse)
    )


def test_summary_warning_order_is_deterministic_and_profile_neutral() -> None:
    asset = make_completed_media_asset(
        kind=CompletedMediaAssetKind.UNKNOWN,
        runtime_profile=CompletedMediaAssetRuntimeProfile.UNKNOWN,
        include_integrity=False,
    )

    summary = CompletedMediaAssetSummary.from_asset(asset)

    assert summary.warning_codes == tuple(sorted(summary.warning_codes))
    assert summary.warning_codes == (
        "asset_kind_unknown",
        "integrity_not_provided",
        "runtime_profile_unknown",
    )


def test_runtime_profile_is_not_part_of_asset_kind_or_context_contracts() -> None:
    assert "runtime_profile" not in {field.name for field in fields(CompletedMediaAssetContext)}
    assert CompletedMediaAssetKind.RECORDING_SEGMENT.value == "recording_segment"
