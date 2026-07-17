from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from app.contexts.production.asset_readiness import (
    AssetFinalizationObservation,
    AssetReadAccessObservation,
    AssetReadAccessStatus,
    AssetReadinessEvaluation,
    AssetReadinessEvaluationRequest,
    AssetReadinessObservationBundle,
    AssetReadinessPolicyParameters,
    AssetResourcePresenceObservation,
    AssetResourcePresenceStatus,
    AssetResourceSnapshot,
    AssetWriteStateObservation,
    AssetWriteStateStatus,
    ConservativeAssetReadinessPolicy,
    MediaAssetCandidate,
    MediaAssetCandidateResource,
)
from app.contexts.production.completed_media_asset import (
    CompletedMediaAssetCompletionMethod,
    CompletedMediaAssetContext,
    CompletedMediaAssetKind,
    CompletedMediaAssetLocationScheme,
    CompletedMediaAssetRuntimeProfile,
    CompletedMediaAssetSourceLocation,
)
from app.shared.ids import EntityId

BASE_TIME = datetime(2026, 7, 17, 10, 5, tzinfo=UTC)
EVALUATED_AT = BASE_TIME + timedelta(seconds=30)
FILESYSTEM_TIME = BASE_TIME - timedelta(seconds=2)
MINIMUM_INTERVAL = timedelta(seconds=5)


def entity_id(number: int) -> EntityId:
    return EntityId(f"00000000-0000-0000-0000-{number:012d}")


CANDIDATE_ID = entity_id(1)
PROPOSED_ASSET_ID = entity_id(2)
RESOURCE_ID = entity_id(3)
RUNTIME_ID = entity_id(4)
HOST_ID = entity_id(5)
VOLUME_ID = entity_id(6)
OBSERVER_ID = entity_id(7)
POLICY_ID = entity_id(8)
EVALUATION_ID = entity_id(9)
COMPLETION_ID = entity_id(10)
READINESS_ID = entity_id(11)
BUNDLE_ID = entity_id(12)
DECLARER_ID = entity_id(13)
MARKER_ID = entity_id(14)

STRONG_METHODS = (
    CompletedMediaAssetCompletionMethod.ATOMIC_RENAME_OBSERVED,
    CompletedMediaAssetCompletionMethod.CLOSED_SEGMENT_NOTIFICATION,
    CompletedMediaAssetCompletionMethod.EXPLICIT_RECORDER_FINALIZATION,
    CompletedMediaAssetCompletionMethod.SIDECAR_COMPLETION_MARKER,
)


def make_candidate(
    *,
    runtime_profile: CompletedMediaAssetRuntimeProfile = (
        CompletedMediaAssetRuntimeProfile.AGENT
    ),
    filename: str = "x7q9.mp4",
    metadata: Mapping[str, Any] | None = None,
) -> MediaAssetCandidate:
    location = CompletedMediaAssetSourceLocation(
        location_scheme=CompletedMediaAssetLocationScheme.LOCAL_FILESYSTEM,
        location_value="/synthetic/stage-a/x7q9.mp4",
        volume_id=VOLUME_ID,
        host_id=HOST_ID,
    )
    resource = MediaAssetCandidateResource(
        id=RESOURCE_ID,
        original_filename=filename,
        source_location=location,
        source_volume_id=VOLUME_ID,
        source_host_id=HOST_ID,
        media_type_hint="video/mp4",
        container_type_hint="mp4",
    )
    return MediaAssetCandidate(
        id=CANDIDATE_ID,
        proposed_asset_id=PROPOSED_ASSET_ID,
        primary_resource=resource,
        source_runtime_id=RUNTIME_ID,
        runtime_profile=runtime_profile,
        source_host_id=HOST_ID,
        recorder_application_id=entity_id(15),
        adapter_id=entity_id(16),
        first_observed_at=BASE_TIME - timedelta(minutes=1),
        context=CompletedMediaAssetContext(stage_id=entity_id(17)),
        intended_asset_kind=CompletedMediaAssetKind.RECORDING_SEGMENT,
        metadata={} if metadata is None else metadata,
    )


def make_parameters(
    *,
    minimum_stable_interval: timedelta = MINIMUM_INTERVAL,
    require_read_access_for_stability: bool = True,
    require_post_finalization_presence: bool = True,
    accepted_strong_finalization_methods: Sequence[
        CompletedMediaAssetCompletionMethod
    ] = STRONG_METHODS,
    require_inactive_write_when_available: bool = True,
) -> AssetReadinessPolicyParameters:
    return AssetReadinessPolicyParameters(
        minimum_stable_interval=minimum_stable_interval,
        require_read_access_for_stability=require_read_access_for_stability,
        require_post_finalization_presence=require_post_finalization_presence,
        accepted_strong_finalization_methods=accepted_strong_finalization_methods,
        require_inactive_write_when_available=require_inactive_write_when_available,
        policy_version="1.0",
    )


def make_policy(
    parameters: AssetReadinessPolicyParameters | None = None,
) -> ConservativeAssetReadinessPolicy:
    return ConservativeAssetReadinessPolicy(
        policy_id=POLICY_ID,
        parameters=make_parameters() if parameters is None else parameters,
    )


def make_request(
    *,
    candidate_id: EntityId = CANDIDATE_ID,
    resource_id: EntityId = RESOURCE_ID,
    policy_id: EntityId = POLICY_ID,
    policy_version: str = "1.0",
    evaluated_at: datetime = EVALUATED_AT,
) -> AssetReadinessEvaluationRequest:
    return AssetReadinessEvaluationRequest(
        evaluation_id=EVALUATION_ID,
        policy_id=policy_id,
        policy_version=policy_version,
        candidate_id=candidate_id,
        resource_id=resource_id,
        evaluated_at=evaluated_at,
        completion_declaration_id=COMPLETION_ID,
        readiness_declaration_id=READINESS_ID,
        request_id=entity_id(18),
    )


def make_snapshot(
    number: int,
    observed_at: datetime,
    *,
    size_bytes: int = 1000,
    filesystem_modified_at: datetime | None = FILESYSTEM_TIME,
    identity_token: str | None = "resource-generation-a",
    source_host_id: EntityId | None = HOST_ID,
    source_volume_id: EntityId | None = VOLUME_ID,
    source_runtime_id: EntityId | None = RUNTIME_ID,
    limitations: Sequence[str] = (),
    metadata: Mapping[str, Any] | None = None,
) -> AssetResourceSnapshot:
    return AssetResourceSnapshot(
        id=entity_id(100 + number),
        candidate_id=CANDIDATE_ID,
        resource_id=RESOURCE_ID,
        observed_at=observed_at,
        size_bytes=size_bytes,
        observer_id=OBSERVER_ID,
        filesystem_modified_at=filesystem_modified_at,
        stable_resource_identity_token=identity_token,
        source_volume_id=source_volume_id,
        source_host_id=source_host_id,
        source_runtime_id=source_runtime_id,
        limitations=limitations,
        metadata={} if metadata is None else metadata,
    )


def make_finalization(
    number: int = 1,
    observed_at: datetime = BASE_TIME,
    *,
    method: CompletedMediaAssetCompletionMethod = (
        CompletedMediaAssetCompletionMethod.EXPLICIT_RECORDER_FINALIZATION
    ),
    source_runtime_id: EntityId | None = RUNTIME_ID,
    limitations: Sequence[str] = (),
) -> AssetFinalizationObservation:
    return AssetFinalizationObservation(
        id=entity_id(200 + number),
        candidate_id=CANDIDATE_ID,
        resource_id=RESOURCE_ID,
        observed_at=observed_at,
        completion_method=method,
        declaring_entity_id=DECLARER_ID,
        observer_id=OBSERVER_ID,
        source_runtime_id=source_runtime_id,
        completion_marker_resource_id=(
            MARKER_ID
            if method is CompletedMediaAssetCompletionMethod.SIDECAR_COMPLETION_MARKER
            else None
        ),
        source_event_id=entity_id(220 + number),
        limitations=limitations,
    )


def make_write(
    number: int,
    observed_at: datetime,
    status: AssetWriteStateStatus,
    *,
    source_runtime_id: EntityId | None = RUNTIME_ID,
    limitations: Sequence[str] = (),
) -> AssetWriteStateObservation:
    return AssetWriteStateObservation(
        id=entity_id(300 + number),
        candidate_id=CANDIDATE_ID,
        resource_id=RESOURCE_ID,
        observed_at=observed_at,
        status=status,
        assessment_mechanism_id="synthetic-write-assessor",
        observer_id=OBSERVER_ID,
        source_runtime_id=source_runtime_id,
        writer_id=entity_id(320 + number) if status is AssetWriteStateStatus.ACTIVE else None,
        limitations=limitations,
    )


def make_access(
    number: int,
    observed_at: datetime,
    status: AssetReadAccessStatus,
    *,
    source_runtime_id: EntityId | None = RUNTIME_ID,
    limitations: Sequence[str] = (),
) -> AssetReadAccessObservation:
    return AssetReadAccessObservation(
        id=entity_id(400 + number),
        candidate_id=CANDIDATE_ID,
        resource_id=RESOURCE_ID,
        observed_at=observed_at,
        status=status,
        assessment_method_id="synthetic-read-assessor",
        access_scope="read-only file open",
        observer_id=OBSERVER_ID,
        source_runtime_id=source_runtime_id,
        limitations=limitations,
    )


def make_presence(
    number: int,
    observed_at: datetime,
    status: AssetResourcePresenceStatus = AssetResourcePresenceStatus.PRESENT,
    *,
    identity_token: str | None = "resource-generation-a",
    replacement_resource_id: EntityId | None = None,
    source_runtime_id: EntityId | None = RUNTIME_ID,
    limitations: Sequence[str] = (),
) -> AssetResourcePresenceObservation:
    replacement = replacement_resource_id
    if status is AssetResourcePresenceStatus.REPLACED and replacement is None:
        replacement = entity_id(999)
    return AssetResourcePresenceObservation(
        id=entity_id(500 + number),
        candidate_id=CANDIDATE_ID,
        resource_id=RESOURCE_ID,
        observed_at=observed_at,
        status=status,
        observer_id=OBSERVER_ID,
        source_runtime_id=source_runtime_id,
        observed_resource_identity_token=identity_token,
        replacement_resource_id=replacement,
        limitations=limitations,
    )


def make_bundle(
    *,
    snapshots: Sequence[AssetResourceSnapshot] = (),
    finalizations: Sequence[AssetFinalizationObservation] = (),
    writes: Sequence[AssetWriteStateObservation] = (),
    accesses: Sequence[AssetReadAccessObservation] = (),
    presences: Sequence[AssetResourcePresenceObservation] = (),
    candidate_id: EntityId = CANDIDATE_ID,
    resource_id: EntityId = RESOURCE_ID,
    created_at: datetime = EVALUATED_AT,
    metadata: Mapping[str, Any] | None = None,
) -> AssetReadinessObservationBundle:
    return AssetReadinessObservationBundle(
        id=BUNDLE_ID,
        candidate_id=candidate_id,
        resource_id=resource_id,
        created_at=created_at,
        resource_snapshots=snapshots,
        finalization_observations=finalizations,
        write_state_observations=writes,
        read_access_observations=accesses,
        presence_observations=presences,
        metadata={} if metadata is None else metadata,
    )


def make_stability_bundle() -> AssetReadinessObservationBundle:
    window_end = BASE_TIME + MINIMUM_INTERVAL
    return make_bundle(
        snapshots=(
            make_snapshot(1, BASE_TIME),
            make_snapshot(2, window_end),
        ),
        writes=(make_write(1, window_end, AssetWriteStateStatus.INACTIVE),),
        accesses=(make_access(1, window_end, AssetReadAccessStatus.READABLE),),
        presences=(make_presence(1, window_end),),
    )


def reason_codes(evaluation: AssetReadinessEvaluation) -> tuple[str, ...]:
    return tuple(reason.code.value for reason in evaluation.reasons)
