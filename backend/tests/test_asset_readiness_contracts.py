from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Any, cast

import pytest
from asset_readiness_fixtures import (
    BASE_TIME,
    CANDIDATE_ID,
    COMPLETION_ID,
    EVALUATED_AT,
    FILESYSTEM_TIME,
    HOST_ID,
    POLICY_ID,
    PROPOSED_ASSET_ID,
    READINESS_ID,
    RESOURCE_ID,
    RUNTIME_ID,
    VOLUME_ID,
    entity_id,
    make_bundle,
    make_candidate,
    make_parameters,
    make_request,
    make_snapshot,
    make_stability_bundle,
)

from app.contexts.production.asset_readiness import (
    AssetReadAccessStatus,
    AssetReadinessOutcome,
    AssetReadinessPolicyParameters,
    AssetReadinessReason,
    AssetReadinessReasonCode,
    AssetReadinessSummary,
    AssetResourcePresenceObservation,
    AssetResourcePresenceStatus,
    AssetWriteStateStatus,
    ConservativeAssetReadinessPolicy,
    MediaAssetCandidate,
    MediaAssetCandidateResource,
)
from app.contexts.production.completed_media_asset import (
    CompletedMediaAssetCompletion,
    CompletedMediaAssetCompletionMethod,
    CompletedMediaAssetKind,
    CompletedMediaAssetLocationScheme,
    CompletedMediaAssetRelationship,
    CompletedMediaAssetRuntimeProfile,
    CompletedMediaAssetSourceLocation,
)


def test_candidate_preserves_identity_provenance_context_and_intent() -> None:
    candidate = make_candidate()

    assert candidate.id == CANDIDATE_ID
    assert candidate.proposed_asset_id == PROPOSED_ASSET_ID
    assert candidate.primary_resource.id == RESOURCE_ID
    assert candidate.source_runtime_id == RUNTIME_ID
    assert candidate.source_host_id == HOST_ID
    assert candidate.intended_asset_kind is CompletedMediaAssetKind.RECORDING_SEGMENT
    assert candidate.context.stage_id is not None


def test_candidate_contains_no_completion_readiness_or_workflow_claims() -> None:
    candidate_fields = {field.name for field in fields(MediaAssetCandidate)}
    resource_fields = {field.name for field in fields(MediaAssetCandidateResource)}

    assert not {
        "completion",
        "is_finalized",
        "readiness",
        "session_id",
        "transfer_status",
        "queue_state",
        "operational_state",
    } & candidate_fields
    assert not {
        "checksum",
        "duration",
        "file_size_bytes",
        "filesystem_modified_at",
        "readiness",
    } & resource_fields


@pytest.mark.parametrize("filename", ("../x.mp4", "dir/x.mp4", "dir\\x.mp4", " "))
def test_candidate_filename_cannot_embed_a_path(filename: str) -> None:
    with pytest.raises(ValueError):
        make_candidate(filename=filename)


def test_candidate_resource_rejects_conflicting_host_or_volume_identity() -> None:
    location = CompletedMediaAssetSourceLocation(
        location_scheme=CompletedMediaAssetLocationScheme.MOUNTED_VOLUME,
        location_value="synthetic/x7q9.mp4",
        volume_id=VOLUME_ID,
        host_id=HOST_ID,
    )

    with pytest.raises(ValueError, match="volume"):
        MediaAssetCandidateResource(
            id=RESOURCE_ID,
            original_filename="x7q9.mp4",
            source_location=location,
            source_volume_id=entity_id(900),
        )
    with pytest.raises(ValueError, match="host"):
        MediaAssetCandidateResource(
            id=RESOURCE_ID,
            original_filename="x7q9.mp4",
            source_location=location,
            source_host_id=entity_id(901),
        )


def test_non_segment_candidate_rejects_segment_relationship_semantics() -> None:
    candidate = make_candidate()
    relationship = CompletedMediaAssetRelationship(segment_index=2)

    with pytest.raises(ValueError, match="Segment relationship"):
        replace(
            candidate,
            intended_asset_kind=CompletedMediaAssetKind.MEDIA_CLIP,
            relationship=relationship,
        )


def test_resource_snapshot_preserves_objective_descriptive_facts() -> None:
    snapshot = make_snapshot(1, BASE_TIME)

    assert snapshot.size_bytes == 1000
    assert snapshot.filesystem_modified_at == FILESYSTEM_TIME
    assert snapshot.stable_resource_identity_token == "resource-generation-a"
    assert snapshot.source_volume_id == VOLUME_ID
    assert snapshot.source_host_id == HOST_ID


def test_resource_snapshot_rejects_negative_size_and_naive_timestamps() -> None:
    with pytest.raises(ValueError, match="negative"):
        make_snapshot(1, BASE_TIME, size_bytes=-1)
    with pytest.raises(ValueError, match="timezone-aware"):
        make_snapshot(1, datetime(2026, 7, 17, 10, 5))
    with pytest.raises(ValueError, match="timezone-aware"):
        make_snapshot(
            1,
            BASE_TIME,
            filesystem_modified_at=datetime(2026, 7, 17, 10, 4),
        )


def test_resource_observation_status_vocabularies_are_exact() -> None:
    assert {status.value for status in AssetWriteStateStatus} == {
        "active",
        "inactive",
        "unknown",
        "unsupported",
    }
    assert {status.value for status in AssetReadAccessStatus} == {
        "readable",
        "unreadable",
        "unknown",
        "unsupported",
    }
    assert {status.value for status in AssetResourcePresenceStatus} == {
        "present",
        "missing",
        "replaced",
        "unknown",
    }


def test_presence_replacement_requires_a_distinct_resource_identity() -> None:
    common: dict[str, Any] = {
        "id": entity_id(1),
        "candidate_id": CANDIDATE_ID,
        "resource_id": RESOURCE_ID,
        "observed_at": BASE_TIME,
        "observer_id": entity_id(2),
    }

    with pytest.raises(ValueError, match="requires"):
        AssetResourcePresenceObservation(
            **common,
            status=AssetResourcePresenceStatus.REPLACED,
        )
    with pytest.raises(ValueError, match="Only"):
        AssetResourcePresenceObservation(
            **common,
            status=AssetResourcePresenceStatus.PRESENT,
            replacement_resource_id=entity_id(3),
        )
    with pytest.raises(ValueError, match="differ"):
        AssetResourcePresenceObservation(
            **common,
            status=AssetResourcePresenceStatus.REPLACED,
            replacement_resource_id=RESOURCE_ID,
        )


def test_observation_bundle_normalizes_order_and_exact_duplicate_ids() -> None:
    first = make_snapshot(1, BASE_TIME)
    second = make_snapshot(2, BASE_TIME + timedelta(seconds=5))
    bundle = make_bundle(snapshots=(second, first, first))

    assert bundle.resource_snapshots == (first, second)
    assert bundle.observation_ids == (first.id, second.id)
    assert bundle.conflicting_observation_ids == ()


def test_observation_bundle_rejects_child_identity_and_time_mismatches() -> None:
    snapshot = make_snapshot(1, BASE_TIME)

    with pytest.raises(ValueError, match="candidate ID"):
        make_bundle(snapshots=(snapshot,), candidate_id=entity_id(777))
    with pytest.raises(ValueError, match="resource ID"):
        make_bundle(snapshots=(snapshot,), resource_id=entity_id(778))
    with pytest.raises(ValueError, match="after bundle creation"):
        make_bundle(snapshots=(snapshot,), created_at=BASE_TIME - timedelta(seconds=1))


def test_empty_observation_bundle_is_valid_and_immutable() -> None:
    bundle = make_bundle(metadata={"nested": {"values": [1, 2]}})

    assert bundle.all_observations == ()
    assert isinstance(bundle.metadata, MappingProxyType)
    assert isinstance(bundle.metadata["nested"], MappingProxyType)
    with pytest.raises(FrozenInstanceError):
        bundle.created_at = BASE_TIME  # type: ignore[misc]


def test_policy_parameters_are_explicit_normalized_and_immutable() -> None:
    parameters = make_parameters(
        accepted_strong_finalization_methods=(
            CompletedMediaAssetCompletionMethod.EXPLICIT_RECORDER_FINALIZATION,
            CompletedMediaAssetCompletionMethod.ATOMIC_RENAME_OBSERVED,
            CompletedMediaAssetCompletionMethod.EXPLICIT_RECORDER_FINALIZATION,
        )
    )

    assert parameters.accepted_strong_finalization_methods == (
        CompletedMediaAssetCompletionMethod.ATOMIC_RENAME_OBSERVED,
        CompletedMediaAssetCompletionMethod.EXPLICIT_RECORDER_FINALIZATION,
    )
    assert parameters.minimum_stable_interval == timedelta(seconds=5)
    assert parameters.require_read_access_for_stability is True
    assert parameters.require_post_finalization_presence is True
    assert parameters.require_inactive_write_when_available is True
    with pytest.raises(FrozenInstanceError):
        parameters.policy_version = "2.0"  # type: ignore[misc]


def test_policy_parameters_reject_invalid_interval_or_strong_method() -> None:
    with pytest.raises(ValueError, match="positive"):
        make_parameters(minimum_stable_interval=timedelta(0))
    with pytest.raises(ValueError, match="At least one"):
        make_parameters(accepted_strong_finalization_methods=())
    with pytest.raises(ValueError, match="approved strong"):
        make_parameters(
            accepted_strong_finalization_methods=(
                CompletedMediaAssetCompletionMethod.MANUAL_DECLARATION,
            )
        )


def test_evaluation_request_rejects_naive_time_and_blank_version() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        make_request(evaluated_at=datetime(2026, 7, 17, 10, 5))
    with pytest.raises(ValueError, match="must not be empty"):
        make_request(policy_version=" ")


def test_reason_is_deduplicated_id_oriented_and_recursively_immutable() -> None:
    values = [entity_id(2), entity_id(1), entity_id(2)]
    metadata: dict[str, Any] = {"nested": ["supplied"]}
    reason = AssetReadinessReason(
        code=AssetReadinessReasonCode.READ_ACCESS_FAILED,
        message=" read failed ",
        observation_ids=values,
        metadata=metadata,
    )
    values.append(entity_id(3))
    cast(list[str], metadata["nested"]).append("changed")

    assert reason.message == "read failed"
    assert reason.observation_ids == (entity_id(1), entity_id(2))
    assert reason.metadata["nested"] == ("supplied",)


def test_metadata_rejects_credential_shaped_keys() -> None:
    with pytest.raises(ValueError, match="credential"):
        make_candidate(metadata={"access_token": "synthetic-secret"})
    with pytest.raises(ValueError, match="credential"):
        make_snapshot(1, BASE_TIME, metadata={"password": "synthetic-secret"})


def test_outcome_vocabulary_is_exact_and_categorical() -> None:
    assert {outcome.value for outcome in AssetReadinessOutcome} == {
        "safe_to_read",
        "not_safe_to_read",
        "insufficient_observation",
        "conflicting_observation",
        "unsupported_source",
        "invalid_request",
        "unknown",
    }


def test_summary_is_privacy_safe_and_retains_explicit_parameters_in_lineage() -> None:
    candidate = make_candidate()
    evaluation = make_stability_bundle()
    result = ConservativeAssetReadinessPolicy(
        policy_id=POLICY_ID,
        parameters=make_parameters(),
    ).evaluate(candidate, evaluation, make_request())
    summary = AssetReadinessSummary.from_evaluation(result, candidate)

    assert summary.candidate_id == CANDIDATE_ID
    assert summary.resource_id == RESOURCE_ID
    assert summary.stable_interval == timedelta(seconds=5)
    assert summary.source_runtime_id == RUNTIME_ID
    assert summary.runtime_profile is CompletedMediaAssetRuntimeProfile.AGENT
    assert not any(
        "synthetic/stage" in str(getattr(summary, field.name))
        for field in fields(summary)
    )
    assert result.policy_parameters == make_parameters()


def test_summary_rejects_mismatched_candidate() -> None:
    candidate = make_candidate()
    result = ConservativeAssetReadinessPolicy(
        policy_id=POLICY_ID,
        parameters=make_parameters(),
    ).evaluate(candidate, make_stability_bundle(), make_request())
    other = replace(candidate, id=entity_id(800))

    with pytest.raises(ValueError, match="must match"):
        AssetReadinessSummary.from_evaluation(result, other)


def test_ed0048_completion_preserves_first_class_limitations() -> None:
    completion = CompletedMediaAssetCompletion(
        id=COMPLETION_ID,
        method=CompletedMediaAssetCompletionMethod.EXPLICIT_RECORDER_FINALIZATION,
        is_finalized=True,
        finalized_at=EVALUATED_AT,
        declaring_runtime_or_adapter_id=RUNTIME_ID,
        limitations=("clock precision limited", "clock precision limited"),
    )

    assert completion.limitations == ("clock precision limited",)
    assert READINESS_ID != completion.id


def test_contracts_are_frozen_and_caller_owned_collections_do_not_leak() -> None:
    limitations = ["network semantics uncertain"]
    snapshot = make_snapshot(1, BASE_TIME, limitations=limitations)
    limitations.append("mutated")

    assert snapshot.limitations == ("network semantics uncertain",)
    with pytest.raises(FrozenInstanceError):
        snapshot.size_bytes = 2  # type: ignore[misc]


def test_public_policy_parameter_shape_has_no_hidden_deployment_selector() -> None:
    parameter_fields = {field.name for field in fields(AssetReadinessPolicyParameters)}

    assert "runtime_profile" not in parameter_fields
    assert "agent_threshold" not in parameter_fields
    assert "node_threshold" not in parameter_fields
    assert "policy_version" in parameter_fields
