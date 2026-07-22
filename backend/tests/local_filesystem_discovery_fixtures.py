from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

from runtime_fixtures import (
    CONFIGURATION_ID,
    CONFIGURED_AT,
    PLAN_ID,
    RUNTIME_ID,
    capability_id,
    entity_id,
    make_runtime,
    synchronize_runtime,
)

from app.contexts.production.completed_media_asset import CompletedMediaAssetKind
from app.contexts.production.local_filesystem_discovery import (
    LocalFilesystemCandidateDiscoveryAdapter,
    LocalFilesystemDiscoveryConfiguration,
    LocalFilesystemEligibilityPolicy,
    LocalFilesystemExtensionMatchingMode,
    LocalFilesystemHiddenEntryPolicy,
    LocalFilesystemSymlinkPolicy,
    LocalFilesystemTargetBinding,
    LocalFilesystemTargetScope,
)
from app.contexts.production.media_collection import MediaCandidateDiscoveryRequest
from app.contexts.production.runtime import (
    RuntimeCapabilityKind,
    RuntimeProfile,
    RuntimeSourceLocationScheme,
    StageFlowRuntime,
)
from app.contexts.production.software_agent_runtime import AgentRuntimeExecutionPermission

ADAPTER_ID = entity_id(23)
BINDING_ID = entity_id(9000)
IDENTITY_NAMESPACE_ID = entity_id(9001)
DISCOVERY_CAPABILITY_ID = capability_id(RuntimeCapabilityKind.CANDIDATE_DISCOVERY)
REQUESTED_AT = datetime.fromisoformat("2026-07-17T10:05:00+00:00")


def make_policy(
    *,
    allowed: tuple[str, ...] = (".mov", ".mp4"),
    case_insensitive: bool = True,
    include_hidden: bool = False,
    permit_all: bool = False,
    excluded: tuple[str, ...] = (".partial",),
) -> LocalFilesystemEligibilityPolicy:
    return LocalFilesystemEligibilityPolicy(
        allowed_filename_extensions=allowed,
        extension_matching_mode=(
            LocalFilesystemExtensionMatchingMode.CASE_INSENSITIVE
            if case_insensitive
            else LocalFilesystemExtensionMatchingMode.CASE_SENSITIVE
        ),
        hidden_entry_policy=(
            LocalFilesystemHiddenEntryPolicy.INCLUDE
            if include_hidden
            else LocalFilesystemHiddenEntryPolicy.EXCLUDE
        ),
        regular_file_required=True,
        symlink_policy=LocalFilesystemSymlinkPolicy.REJECT_OR_SKIP,
        permit_all_regular_files=permit_all,
        excluded_suffixes=excluded,
        extension_to_media_type_hints={".mov": "video/quicktime", ".mp4": "video/mp4"},
        extension_to_container_hints={".mov": "quicktime", ".mp4": "mp4"},
        extension_to_asset_kind_hints={
            ".mov": CompletedMediaAssetKind.RECORDING_SEGMENT,
            ".mp4": CompletedMediaAssetKind.RECORDING_SEGMENT,
        },
    )


def make_adapter(
    target_path: Path,
    *,
    scope: LocalFilesystemTargetScope = LocalFilesystemTargetScope.SHALLOW_DIRECTORY,
    entry_limit: int = 20,
    policy: LocalFilesystemEligibilityPolicy | None = None,
    profile: RuntimeProfile = RuntimeProfile.AGENT,
    scheme: RuntimeSourceLocationScheme = RuntimeSourceLocationScheme.LOCAL_FILE,
) -> tuple[LocalFilesystemCandidateDiscoveryAdapter, MediaCandidateDiscoveryRequest]:
    runtime = make_discovery_runtime(target_path, profile=profile, scheme=scheme)
    target = runtime.configuration.collection_plans[0].targets[0]
    binding = LocalFilesystemTargetBinding(
        binding_id=BINDING_ID,
        runtime_id=runtime.identity.runtime_id,
        configuration_id=runtime.configuration.id,
        collection_plan_id=runtime.configuration.collection_plans[0].id,
        collection_target_id=target.id,
        source_capability_id=target.source_capability_id,
        discovery_capability_id=DISCOVERY_CAPABILITY_ID,
        source_location_scheme=scheme,
        configured_absolute_target_location=str(target_path),
        target_scope=scope,
        maximum_directory_entries_examined=entry_limit,
        eligibility_policy=policy or make_policy(),
        source_host_id=target.source_host_id,
        source_volume_id=target.source_volume_id,
        configured_stage_id=target.configured_stage_id,
        configured_recording_block_id=target.configured_recording_block_id,
        recorder_application_id=target.expected_recorder_application_id,
        explicit_asset_kind_hint=target.candidate_asset_kind_hint,
    )
    configuration = LocalFilesystemDiscoveryConfiguration(
        adapter_id=ADAPTER_ID,
        adapter_version="1.0.0",
        runtime_id=runtime.identity.runtime_id,
        configuration_id=runtime.configuration.id,
        supported_source_schemes=(
            RuntimeSourceLocationScheme.LOCAL_FILE,
            RuntimeSourceLocationScheme.MOUNTED_VOLUME,
        ),
        target_bindings=(binding,),
        identity_namespace_id=IDENTITY_NAMESPACE_ID,
        configured_at=CONFIGURED_AT,
    )
    adapter = LocalFilesystemCandidateDiscoveryAdapter(runtime, configuration)
    request = make_request(runtime)
    return adapter, request


def make_discovery_runtime(
    target_path: Path,
    *,
    profile: RuntimeProfile = RuntimeProfile.AGENT,
    scheme: RuntimeSourceLocationScheme = RuntimeSourceLocationScheme.LOCAL_FILE,
) -> StageFlowRuntime:
    runtime = make_runtime(profile=profile)
    source = runtime.capability_set.source_capabilities[0]
    source = replace(
        source,
        supported_location_schemes=(
            RuntimeSourceLocationScheme.LOCAL_FILE,
            RuntimeSourceLocationScheme.MOUNTED_VOLUME,
            RuntimeSourceLocationScheme.NETWORK_SHARE,
        ),
    )
    capability_set = replace(runtime.capability_set, source_capabilities=(source,))
    target = replace(
        runtime.configuration.collection_plans[0].targets[0],
        source_location_scheme=scheme,
        opaque_location_reference=str(target_path),
    )
    plan = replace(runtime.configuration.collection_plans[0], targets=(target,))
    return synchronize_runtime(
        runtime,
        capability_set=capability_set,
        collection_plans=(plan,),
    )


def make_request(
    runtime: StageFlowRuntime,
    *,
    maximum_candidates: int = 10,
    requested_at: datetime = REQUESTED_AT,
    permission: AgentRuntimeExecutionPermission = AgentRuntimeExecutionPermission.NORMAL,
) -> MediaCandidateDiscoveryRequest:
    plan = runtime.configuration.collection_plans[0]
    target = plan.targets[0]
    return MediaCandidateDiscoveryRequest(
        discovery_request_id=entity_id(9010),
        collection_cycle_id=entity_id(9011),
        runtime_id=RUNTIME_ID,
        configuration_id=CONFIGURATION_ID,
        collection_plan_id=PLAN_ID,
        collection_target_id=target.id,
        source_capability_id=target.source_capability_id,
        discovery_capability_id=DISCOVERY_CAPABILITY_ID,
        maximum_candidate_count=maximum_candidates,
        requested_at=requested_at,
        execution_permission=permission,
        event_mode_id=plan.event_mode_id,
        resource_policy_id=plan.resource_policy_id,
        target_reference=target.opaque_location_reference,
    )
