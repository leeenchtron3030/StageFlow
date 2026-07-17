from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from app.contexts.production.asset_readiness import AssetReadinessPolicyParameters
from app.contexts.production.completed_media_asset import (
    CompletedMediaAssetCompletionMethod,
    CompletedMediaAssetKind,
)
from app.contexts.production.runtime import (
    RuntimeAssetAssemblyPlan,
    RuntimeAssetRetentionExpectation,
    RuntimeAvailability,
    RuntimeAvailabilityStatus,
    RuntimeCapability,
    RuntimeCapabilityKind,
    RuntimeCapabilitySet,
    RuntimeCapabilitySupportStatus,
    RuntimeCollectionMode,
    RuntimeCollectionPlan,
    RuntimeCollectionTarget,
    RuntimeConfiguration,
    RuntimeConfigurationValidity,
    RuntimeContextSource,
    RuntimeDeclaredComponentStatus,
    RuntimeEventMode,
    RuntimeEventModeKind,
    RuntimeGpuUsePolicy,
    RuntimeHealth,
    RuntimeHealthReportingPolicy,
    RuntimeHealthStatus,
    RuntimeHost,
    RuntimeIdentity,
    RuntimeIntegritySource,
    RuntimeLimitation,
    RuntimeLimitationSeverity,
    RuntimeManualOverrideStatus,
    RuntimeNetworkPolicy,
    RuntimeObservationCapability,
    RuntimeObservationType,
    RuntimeOptionalActivityPolicy,
    RuntimePowerSourceType,
    RuntimePressureAction,
    RuntimePressureResponse,
    RuntimePressureState,
    RuntimeProfile,
    RuntimeReadinessCapability,
    RuntimeReadinessFallback,
    RuntimeReadinessPolicySelection,
    RuntimeReadinessRoute,
    RuntimeRecoveryPolicy,
    RuntimeResourceBudget,
    RuntimeResourcePolicy,
    RuntimeResourcePriorityClass,
    RuntimeSourceAccessMode,
    RuntimeSourceCapability,
    RuntimeSourceHostScope,
    RuntimeSourceLocationHandlingPolicy,
    RuntimeSourceLocationScheme,
    RuntimeSummaryPrivacyPolicy,
    RuntimeTechnicalDescriptionSource,
    RuntimeVersion,
    StageFlowRuntime,
)
from app.shared.ids import EntityId

CONFIGURED_AT = datetime(2026, 7, 17, 12, tzinfo=UTC)
DECLARED_AT = CONFIGURED_AT - timedelta(seconds=2)
HEALTH_AT = CONFIGURED_AT + timedelta(seconds=1)
AVAILABILITY_AT = CONFIGURED_AT + timedelta(seconds=2)
POLICY_ID = EntityId("10000000-0000-0000-0000-000000000001")


def entity_id(number: int) -> EntityId:
    return EntityId(f"10000000-0000-0000-0000-{number:012d}")


RUNTIME_ID = entity_id(1)
HOST_ID = entity_id(2)
CONFIGURATION_ID = entity_id(3)
CAPABILITY_SET_ID = entity_id(4)
RESOURCE_POLICY_ID = entity_id(5)
BUDGET_ID = entity_id(6)
EVENT_MODE_ID = entity_id(7)
SELECTION_ID = entity_id(8)
ASSEMBLY_ID = entity_id(9)
PLAN_ID = entity_id(10)
TARGET_ID = entity_id(11)
SOURCE_CAPABILITY_ID = entity_id(12)
READINESS_CAPABILITY_ID = entity_id(13)
HEALTH_ID = entity_id(14)
AVAILABILITY_ID = entity_id(15)
HEALTH_POLICY_ID = entity_id(16)
STAGE_ID = entity_id(17)
VOLUME_ID = entity_id(18)

_KIND_NUMBER = {kind: index for index, kind in enumerate(RuntimeCapabilityKind, 100)}
_OBSERVATION_NUMBER = {
    observation_type: index
    for index, observation_type in enumerate(RuntimeObservationType, 300)
}


def capability_id(kind: RuntimeCapabilityKind) -> EntityId:
    return entity_id(_KIND_NUMBER[kind])


def observation_capability_id(
    observation_type: RuntimeObservationType,
) -> EntityId:
    return entity_id(_OBSERVATION_NUMBER[observation_type])


def make_parameters() -> AssetReadinessPolicyParameters:
    return AssetReadinessPolicyParameters(
        minimum_stable_interval=timedelta(seconds=5),
        require_read_access_for_stability=True,
        require_post_finalization_presence=True,
        accepted_strong_finalization_methods=(
            CompletedMediaAssetCompletionMethod.CLOSED_SEGMENT_NOTIFICATION,
            CompletedMediaAssetCompletionMethod.EXPLICIT_RECORDER_FINALIZATION,
        ),
        require_inactive_write_when_available=True,
        policy_version="1.0",
    )


def _general_capability(
    kind: RuntimeCapabilityKind,
    *,
    runtime_id: EntityId,
    supported: bool = True,
) -> RuntimeCapability:
    return RuntimeCapability(
        id=capability_id(kind),
        runtime_id=runtime_id,
        kind=kind,
        support_status=(
            RuntimeCapabilitySupportStatus.SUPPORTED
            if supported
            else RuntimeCapabilitySupportStatus.UNSUPPORTED
        ),
        capability_version="1.0",
        scope="runtime",
    )


def make_runtime(
    *,
    runtime_id: EntityId = RUNTIME_ID,
    profile: RuntimeProfile = RuntimeProfile.NODE,
    route: RuntimeReadinessRoute = RuntimeReadinessRoute.STRONG_THEN_STABILITY,
    fallback: RuntimeReadinessFallback = RuntimeReadinessFallback.REMAIN_INSUFFICIENT,
    include_strong: bool = True,
    include_read: bool = True,
    include_write: bool = True,
    include_stable_identity: bool = True,
    mode: RuntimeEventModeKind = RuntimeEventModeKind.EVENT,
    priority: RuntimeResourcePriorityClass | None = None,
    network_policy: RuntimeNetworkPolicy | None = None,
    disk_write_budget: int | None = 0,
    gpu_policy: RuntimeGpuUsePolicy = RuntimeGpuUsePolicy.FORBIDDEN,
    optional_activity: RuntimeOptionalActivityPolicy | None = None,
    limitation_severity: RuntimeLimitationSeverity | None = None,
    context_sources: Sequence[RuntimeContextSource] = (
        RuntimeContextSource.EXPLICIT_RUNTIME_CONFIGURATION,
    ),
    expected_invalid: bool = False,
) -> StageFlowRuntime:
    enabled = mode is not RuntimeEventModeKind.DISABLED
    resolved_priority = priority or (
        RuntimeResourcePriorityClass.DISABLED
        if not enabled
        else RuntimeResourcePriorityClass.PRODUCTION_SUBORDINATE
    )
    resolved_network = network_policy or (
        RuntimeNetworkPolicy.DISABLED
        if not enabled
        else RuntimeNetworkPolicy.NETWORK_OPTIONAL
    )
    resolved_optional = optional_activity or (
        RuntimeOptionalActivityPolicy.DISABLED
        if not enabled
        else RuntimeOptionalActivityPolicy.SUSPEND
    )
    identity = RuntimeIdentity(
        runtime_id=runtime_id,
        logical_name="Synthetic Stage Runtime",
        deployment_profile=profile,
        host_id=HOST_ID,
        installation_id=entity_id(19),
        organization_id=entity_id(20),
        event_deployment_id=entity_id(21),
        configured_stage_ids=(STAGE_ID,),
    )
    version = RuntimeVersion(
        product_name="StageFlow Runtime",
        semantic_version="1.0.0",
        build_identifier="synthetic-build",
        contract_compatibility_version="1.0",
        configuration_schema_version="1.0",
        capability_schema_version="1.0",
        build_timestamp=CONFIGURED_AT - timedelta(days=1),
    )
    host = RuntimeHost(
        host_id=HOST_ID,
        host_name="synthetic-runtime-host",
        operating_system_family="synthetic-os",
        operating_system_version="1",
        architecture="arm64",
        cpu_logical_count=8,
        memory_capacity_bytes=16_000_000_000,
        gpu_identifiers=("synthetic-gpu",),
        local_volume_ids=(VOLUME_ID,),
        network_interface_ids=(entity_id(22),),
        power_source_type=RuntimePowerSourceType.MAINS,
    )
    supported_by_kind = {
        RuntimeCapabilityKind.READ_ACCESS_OBSERVATION_COLLECTION: include_read,
        RuntimeCapabilityKind.WRITE_STATE_OBSERVATION_COLLECTION: include_write,
        RuntimeCapabilityKind.STABLE_RESOURCE_IDENTITY: include_stable_identity,
        RuntimeCapabilityKind.RECORDER_FINALIZATION_INTEGRATION: include_strong,
        RuntimeCapabilityKind.FINALIZATION_OBSERVATION_COLLECTION: include_strong,
    }
    kinds = (
        RuntimeCapabilityKind.CANDIDATE_DISCOVERY,
        RuntimeCapabilityKind.RESOURCE_SNAPSHOT_COLLECTION,
        RuntimeCapabilityKind.FINALIZATION_OBSERVATION_COLLECTION,
        RuntimeCapabilityKind.WRITE_STATE_OBSERVATION_COLLECTION,
        RuntimeCapabilityKind.READ_ACCESS_OBSERVATION_COLLECTION,
        RuntimeCapabilityKind.RESOURCE_PRESENCE_OBSERVATION_COLLECTION,
        RuntimeCapabilityKind.STABLE_RESOURCE_IDENTITY,
        RuntimeCapabilityKind.RECORDER_FINALIZATION_INTEGRATION,
        RuntimeCapabilityKind.COMPLETED_ASSET_ASSEMBLY,
        RuntimeCapabilityKind.LOCAL_FILESYSTEM_ACCESS,
        RuntimeCapabilityKind.RESOURCE_PRESSURE_AWARENESS,
        RuntimeCapabilityKind.EVENT_MODE_SUPPORT,
        RuntimeCapabilityKind.OPTIONAL_ACTIVITY_SUSPENSION,
        RuntimeCapabilityKind.HEALTH_REPORTING,
    )
    general = tuple(
        _general_capability(
            kind,
            runtime_id=runtime_id,
            supported=supported_by_kind.get(kind, True),
        )
        for kind in kinds
    )
    source = RuntimeSourceCapability(
        id=SOURCE_CAPABILITY_ID,
        runtime_id=runtime_id,
        runtime_capability_id=capability_id(
            RuntimeCapabilityKind.LOCAL_FILESYSTEM_ACCESS
        ),
        supported_location_schemes=(RuntimeSourceLocationScheme.LOCAL_FILE,),
        supported_host_scope=RuntimeSourceHostScope.CONFIGURED_HOSTS,
        supported_host_ids=(HOST_ID,),
        supported_volume_ids=(VOLUME_ID,),
        access_mode=RuntimeSourceAccessMode.READ_ONLY,
        source_adapter_id=entity_id(23),
        recorder_application_ids=(entity_id(24),),
    )
    type_to_kind = {
        RuntimeObservationType.RESOURCE_SNAPSHOT: (
            RuntimeCapabilityKind.RESOURCE_SNAPSHOT_COLLECTION
        ),
        RuntimeObservationType.FINALIZATION: (
            RuntimeCapabilityKind.FINALIZATION_OBSERVATION_COLLECTION
        ),
        RuntimeObservationType.WRITE_STATE: (
            RuntimeCapabilityKind.WRITE_STATE_OBSERVATION_COLLECTION
        ),
        RuntimeObservationType.READ_ACCESS: (
            RuntimeCapabilityKind.READ_ACCESS_OBSERVATION_COLLECTION
        ),
        RuntimeObservationType.RESOURCE_PRESENCE: (
            RuntimeCapabilityKind.RESOURCE_PRESENCE_OBSERVATION_COLLECTION
        ),
    }
    selected_types = [
        RuntimeObservationType.RESOURCE_SNAPSHOT,
        RuntimeObservationType.RESOURCE_PRESENCE,
    ]
    if include_strong:
        selected_types.append(RuntimeObservationType.FINALIZATION)
    if include_write:
        selected_types.append(RuntimeObservationType.WRITE_STATE)
    if include_read:
        selected_types.append(RuntimeObservationType.READ_ACCESS)
    observations = tuple(
        RuntimeObservationCapability(
            id=observation_capability_id(observation_type),
            runtime_id=runtime_id,
            runtime_capability_id=capability_id(type_to_kind[observation_type]),
            observation_type=observation_type,
            collector_or_adapter_id=entity_id(400 + index),
            supported_source_schemes=(RuntimeSourceLocationScheme.LOCAL_FILE,),
            collection_mode=RuntimeCollectionMode.SUPPLIED_BY_ADAPTER,
            timing_precision=timedelta(milliseconds=100),
            stable_identity_support=include_stable_identity,
        )
        for index, observation_type in enumerate(RuntimeObservationType)
    )
    readiness = RuntimeReadinessCapability(
        id=READINESS_CAPABILITY_ID,
        runtime_id=runtime_id,
        supporting_capability_ids=tuple(capability.id for capability in general),
        supported_finalization_methods=(
            (
                CompletedMediaAssetCompletionMethod.CLOSED_SEGMENT_NOTIFICATION,
                CompletedMediaAssetCompletionMethod.EXPLICIT_RECORDER_FINALIZATION,
            )
            if include_strong
            else ()
        ),
        snapshot_support=True,
        write_state_support=include_write,
        read_access_support=include_read,
        presence_support=True,
        stable_identity_support=include_stable_identity,
        supported_policy_ids=(POLICY_ID,),
        supported_policy_versions=("1.0",),
    )
    capability_set = RuntimeCapabilitySet(
        id=CAPABILITY_SET_ID,
        runtime_id=runtime_id,
        capability_schema_version="1.0",
        capabilities=general,
        source_capabilities=(source,),
        observation_capabilities=observations,
        readiness_capabilities=(readiness,),
        declared_at=DECLARED_AT,
    )
    required_kinds = {
        RuntimeCapabilityKind.RESOURCE_PRESENCE_OBSERVATION_COLLECTION,
    }
    if route in (
        RuntimeReadinessRoute.STABILITY_DERIVED,
        RuntimeReadinessRoute.STRONG_THEN_STABILITY,
    ) or fallback is RuntimeReadinessFallback.USE_STABILITY_ROUTE:
        required_kinds.update(
            {
                RuntimeCapabilityKind.RESOURCE_SNAPSHOT_COLLECTION,
                RuntimeCapabilityKind.READ_ACCESS_OBSERVATION_COLLECTION,
                RuntimeCapabilityKind.WRITE_STATE_OBSERVATION_COLLECTION,
                RuntimeCapabilityKind.STABLE_RESOURCE_IDENTITY,
            }
        )
    if route in (
        RuntimeReadinessRoute.STRONG_FINALIZATION,
        RuntimeReadinessRoute.STRONG_THEN_STABILITY,
    ) and fallback is not RuntimeReadinessFallback.USE_STABILITY_ROUTE:
        required_kinds.add(RuntimeCapabilityKind.FINALIZATION_OBSERVATION_COLLECTION)
    optional_ids = ()
    if (
        route is RuntimeReadinessRoute.STRONG_FINALIZATION
        and fallback is not RuntimeReadinessFallback.USE_STABILITY_ROUTE
    ):
        optional_ids = (
            capability_id(RuntimeCapabilityKind.READ_ACCESS_OBSERVATION_COLLECTION),
            capability_id(RuntimeCapabilityKind.WRITE_STATE_OBSERVATION_COLLECTION),
        )
    selection = RuntimeReadinessPolicySelection(
        id=SELECTION_ID,
        runtime_id=runtime_id,
        readiness_capability_id=READINESS_CAPABILITY_ID,
        policy_id=POLICY_ID,
        policy_version="1.0",
        policy_parameters=make_parameters(),
        selected_route=route,
        required_capability_ids=tuple(capability_id(kind) for kind in required_kinds),
        optional_capability_ids=optional_ids,
        fallback_behavior=fallback,
    )
    target = RuntimeCollectionTarget(
        id=TARGET_ID,
        runtime_id=runtime_id,
        source_capability_id=SOURCE_CAPABILITY_ID,
        source_location_scheme=RuntimeSourceLocationScheme.LOCAL_FILE,
        opaque_location_reference="/synthetic/event/recordings",
        source_host_id=HOST_ID,
        source_volume_id=VOLUME_ID,
        expected_recorder_application_id=entity_id(24),
        configured_stage_id=STAGE_ID,
        configured_recording_block_id=entity_id(25),
        candidate_asset_kind_hint=CompletedMediaAssetKind.RECORDING_SEGMENT,
        enabled_observation_types=tuple(selected_types),
    )
    plan = RuntimeCollectionPlan(
        id=PLAN_ID,
        runtime_id=runtime_id,
        plan_version="1.0",
        enabled=enabled,
        targets=(target,),
        observation_capability_ids=tuple(
            observation_capability_id(observation_type)
            for observation_type in selected_types
        ),
        collection_modes=(RuntimeCollectionMode.SUPPLIED_BY_ADAPTER,),
        readiness_policy_selection_id=SELECTION_ID,
        resource_policy_id=RESOURCE_POLICY_ID,
        event_mode_id=EVENT_MODE_ID,
    )
    budget = RuntimeResourceBudget(
        id=BUDGET_ID,
        runtime_id=runtime_id,
        maximum_cpu_utilization_percentage=20,
        maximum_memory_allocation_bytes=512_000_000,
        maximum_disk_read_bytes_per_second=20_000_000,
        maximum_disk_write_bytes_per_second=disk_write_budget,
        maximum_network_bytes_per_second=5_000_000,
        maximum_concurrent_candidate_assessments=2,
        maximum_concurrent_read_access_checks=1,
        maximum_collections_per_minute=60,
        burst_allowance=2,
    )
    pressure_responses = (
        RuntimePressureResponse(
            RuntimePressureState.NORMAL,
            RuntimePressureAction.OPERATE_WITHIN_BUDGETS,
        ),
        RuntimePressureResponse(
            RuntimePressureState.ELEVATED,
            RuntimePressureAction.REDUCE_OPTIONAL_ACTIVITY,
        ),
        RuntimePressureResponse(
            RuntimePressureState.CRITICAL,
            RuntimePressureAction.SUSPEND_OPTIONAL_ACTIVITY,
        ),
        RuntimePressureResponse(
            RuntimePressureState.RECORDING_SAFETY_UNCERTAIN,
            RuntimePressureAction.YIELD_NONESSENTIAL_WORK,
        ),
    )
    resource_policy = RuntimeResourcePolicy(
        id=RESOURCE_POLICY_ID,
        runtime_id=runtime_id,
        priority_class=resolved_priority,
        event_mode_behavior=resolved_optional,
        budget=budget,
        gpu_use_policy=gpu_policy,
        optional_activity_policy=resolved_optional,
        pressure_responses=pressure_responses,
        recovery_policy=RuntimeRecoveryPolicy.REQUIRE_EXPLICIT_DECLARATION,
    )
    event_mode = RuntimeEventMode(
        id=EVENT_MODE_ID,
        runtime_id=runtime_id,
        mode=mode,
        enabled=enabled,
        event_deployment_id=identity.event_deployment_id,
        active_from=CONFIGURED_AT,
        active_until=CONFIGURED_AT + timedelta(hours=12),
        production_subordinate_requirement=(
            resolved_priority is RuntimeResourcePriorityClass.PRODUCTION_SUBORDINATE
        ),
        optional_activity_behavior=resolved_optional,
        network_policy=resolved_network,
        asset_retention_expectation=(
            RuntimeAssetRetentionExpectation.SOURCE_OWNED_NO_CHANGE
        ),
        manual_override_status=RuntimeManualOverrideStatus.NOT_ALLOWED,
    )
    assembly = RuntimeAssetAssemblyPlan(
        id=ASSEMBLY_ID,
        runtime_id=runtime_id,
        manifest_schema_name="stageflow.completed_media_asset",
        manifest_schema_version="1.0",
        supported_asset_kinds=(CompletedMediaAssetKind.RECORDING_SEGMENT,),
        context_sources=context_sources,
        technical_description_sources=(
            RuntimeTechnicalDescriptionSource.RECORDER_STRUCTURED_METADATA,
        ),
        integrity_sources=(RuntimeIntegritySource.NONE,),
        source_location_handling_policy=(
            RuntimeSourceLocationHandlingPolicy.READ_ONLY_REFERENCE
        ),
        summary_privacy_policy=RuntimeSummaryPrivacyPolicy.OMIT_FULL_SOURCE_PATHS,
    )
    limitation = (
        RuntimeLimitation(
            id=entity_id(500),
            runtime_id=runtime_id,
            code="optional_capability_unavailable",
            severity=limitation_severity,
            description="An optional Runtime capability is unavailable.",
            affected_capability_ids=optional_ids,
            introduced_at=CONFIGURED_AT,
        )
        if limitation_severity is not None
        else None
    )
    limitations = () if limitation is None else (limitation,)
    health_status = (
        RuntimeHealthStatus.UNHEALTHY
        if expected_invalid
        else RuntimeHealthStatus.DEGRADED
        if limitations
        else RuntimeHealthStatus.HEALTHY
    )
    configuration_validity = (
        RuntimeConfigurationValidity.INVALID
        if expected_invalid
        else RuntimeConfigurationValidity.VALID_WITH_LIMITATIONS
        if limitations
        else RuntimeConfigurationValidity.VALID
    )
    component_status = (
        RuntimeDeclaredComponentStatus.UNAVAILABLE
        if expected_invalid
        else RuntimeDeclaredComponentStatus.DEGRADED
        if limitations
        else RuntimeDeclaredComponentStatus.AVAILABLE
    )
    health = RuntimeHealth(
        id=HEALTH_ID,
        runtime_id=runtime_id,
        status=health_status,
        assessed_at=HEALTH_AT,
        configuration_validity=configuration_validity,
        capability_availability=component_status,
        resource_policy_availability=(
            RuntimeDeclaredComponentStatus.AVAILABLE
        ),
        collection_plan_validity=component_status,
        limitation_ids=tuple(value.id for value in limitations),
        reason_codes=("synthetic_declaration",),
    )
    availability_status = (
        RuntimeAvailabilityStatus.DISABLED
        if not enabled
        else RuntimeAvailabilityStatus.UNAVAILABLE
        if expected_invalid
        else RuntimeAvailabilityStatus.LIMITED
        if limitations or mode is RuntimeEventModeKind.MAINTENANCE
        else RuntimeAvailabilityStatus.AVAILABLE
    )
    availability = RuntimeAvailability(
        id=AVAILABILITY_ID,
        runtime_id=runtime_id,
        status=availability_status,
        declared_at=AVAILABILITY_AT,
        reason_codes=("synthetic_declaration",),
        expected_capability_availability=component_status,
        event_mode_compatible=(mode is not RuntimeEventModeKind.EVENT or not expected_invalid),
        limitation_ids=tuple(value.id for value in limitations),
    )
    health_policy = RuntimeHealthReportingPolicy(
        id=HEALTH_POLICY_ID,
        runtime_id=runtime_id,
        enabled=True,
        expected_reporting_interval=timedelta(seconds=30),
    )
    configuration = RuntimeConfiguration(
        id=CONFIGURATION_ID,
        runtime_id=runtime_id,
        configuration_schema_version="1.0",
        enabled=enabled,
        event_mode=event_mode,
        capability_set=capability_set,
        collection_plans=(plan,),
        readiness_policy_selections=(selection,),
        asset_assembly_plans=(assembly,),
        resource_policy=resource_policy,
        health_reporting_policy=health_policy,
        configured_at=CONFIGURED_AT,
        configured_by_id=entity_id(26),
    )
    return StageFlowRuntime(
        identity=identity,
        profile=profile,
        software_version=version,
        host=host,
        configuration=configuration,
        capability_set=capability_set,
        resource_policy=resource_policy,
        event_mode=event_mode,
        collection_plans=(plan,),
        readiness_policy_selections=(selection,),
        asset_assembly_plans=(assembly,),
        health=health,
        availability=availability,
        limitations=limitations,
        configured_at=CONFIGURED_AT,
    )


def validation_codes(runtime: StageFlowRuntime) -> tuple[str, ...]:
    from app.contexts.production.runtime import validate_runtime

    return tuple(reason.code.value for reason in validate_runtime(runtime).reasons)


def synchronize_runtime(
    runtime: StageFlowRuntime,
    *,
    identity: RuntimeIdentity | None = None,
    profile: RuntimeProfile | None = None,
    version: RuntimeVersion | None = None,
    host: RuntimeHost | None = None,
    capability_set: RuntimeCapabilitySet | None = None,
    resource_policy: RuntimeResourcePolicy | None = None,
    event_mode: RuntimeEventMode | None = None,
    collection_plans: Sequence[RuntimeCollectionPlan] | None = None,
    readiness_selections: Sequence[RuntimeReadinessPolicySelection] | None = None,
    assembly_plans: Sequence[RuntimeAssetAssemblyPlan] | None = None,
    health: RuntimeHealth | None = None,
    availability: RuntimeAvailability | None = None,
    limitations: Sequence[RuntimeLimitation] | None = None,
) -> StageFlowRuntime:
    resolved_identity = runtime.identity if identity is None else identity
    resolved_profile = runtime.profile if profile is None else profile
    resolved_version = runtime.software_version if version is None else version
    resolved_host = runtime.host if host is None else host
    resolved_capabilities = (
        runtime.capability_set if capability_set is None else capability_set
    )
    resolved_policy = runtime.resource_policy if resource_policy is None else resource_policy
    resolved_mode = runtime.event_mode if event_mode is None else event_mode
    resolved_plans = (
        runtime.collection_plans
        if collection_plans is None
        else tuple(collection_plans)
    )
    resolved_selections = (
        runtime.readiness_policy_selections
        if readiness_selections is None
        else tuple(readiness_selections)
    )
    resolved_assembly = (
        runtime.asset_assembly_plans
        if assembly_plans is None
        else tuple(assembly_plans)
    )
    resolved_health = runtime.health if health is None else health
    resolved_availability = (
        runtime.availability if availability is None else availability
    )
    resolved_limitations = (
        runtime.limitations if limitations is None else tuple(limitations)
    )
    configuration = replace(
        runtime.configuration,
        event_mode=resolved_mode,
        capability_set=resolved_capabilities,
        collection_plans=resolved_plans,
        readiness_policy_selections=resolved_selections,
        asset_assembly_plans=resolved_assembly,
        resource_policy=resolved_policy,
    )
    return replace(
        runtime,
        identity=resolved_identity,
        profile=resolved_profile,
        software_version=resolved_version,
        host=resolved_host,
        configuration=configuration,
        capability_set=resolved_capabilities,
        resource_policy=resolved_policy,
        event_mode=resolved_mode,
        collection_plans=resolved_plans,
        readiness_policy_selections=resolved_selections,
        asset_assembly_plans=resolved_assembly,
        health=resolved_health,
        availability=resolved_availability,
        limitations=resolved_limitations,
    )
