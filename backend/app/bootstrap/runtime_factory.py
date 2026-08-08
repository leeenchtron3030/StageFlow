from __future__ import annotations

import platform
from datetime import timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from app.contexts.events import Stage
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
    validate_runtime,
)
from app.core.config.deployment import (
    EffectiveKernelConfiguration,
    EventModePolicy,
    NetworkPolicy,
    NodeRole,
)
from app.shared.ids import EntityId
from app.shared.time import Clock


def _namespace(configuration: EffectiveKernelConfiguration) -> UUID:
    deployment = configuration.deployment
    return uuid5(
        NAMESPACE_URL,
        f"stageflow:kernel:{deployment.deployment_id}:{deployment.node_id}",
    )


def _id(namespace: UUID, name: str) -> EntityId:
    return EntityId(str(uuid5(namespace, name)))


def _profile(role: NodeRole) -> RuntimeProfile:
    return {
        NodeRole.AGENT: RuntimeProfile.AGENT,
        NodeRole.NODE: RuntimeProfile.NODE,
        NodeRole.DEVELOPMENT: RuntimeProfile.DEVELOPMENT,
    }[role]


def _event_mode(mode: EventModePolicy) -> RuntimeEventModeKind:
    return {
        EventModePolicy.EVENT: RuntimeEventModeKind.EVENT,
        EventModePolicy.REHEARSAL: RuntimeEventModeKind.MAINTENANCE,
        EventModePolicy.DEVELOPMENT: RuntimeEventModeKind.DEVELOPMENT,
    }[mode]


def _network(policy: NetworkPolicy) -> RuntimeNetworkPolicy:
    return {
        NetworkPolicy.OFFLINE: RuntimeNetworkPolicy.OFFLINE_CAPABLE,
        NetworkPolicy.LOCAL_ONLY: RuntimeNetworkPolicy.LOCAL_NETWORK_ONLY,
        NetworkPolicy.OPTIONAL: RuntimeNetworkPolicy.NETWORK_OPTIONAL,
    }[policy]


def build_stageflow_runtime(
    configuration: EffectiveKernelConfiguration,
    *,
    stages: tuple[Stage, ...],
    clock: Clock,
) -> StageFlowRuntime:
    deployment = configuration.deployment
    configured_at = clock.now()
    namespace = _namespace(configuration)
    runtime_id = _id(namespace, "runtime")
    host_id = _id(namespace, "host")
    configuration_id = _id(namespace, "configuration")
    capability_set_id = _id(namespace, "capability-set")
    resource_policy_id = _id(namespace, "resource-policy")
    budget_id = _id(namespace, "resource-budget")
    event_mode_id = _id(namespace, "event-mode")
    selection_id = _id(namespace, "readiness-selection")
    policy_id = _id(namespace, "readiness-policy")
    readiness_capability_id = _id(namespace, "readiness-capability")
    assembly_id = _id(namespace, "asset-assembly")
    plan_id = _id(namespace, "collection-plan")
    source_capability_id = _id(namespace, "source-capability")
    adapter_id = _id(namespace, "local-filesystem-adapter")
    recorder_id = _id(namespace, "configured-recorder")
    health_id = _id(namespace, "health")
    availability_id = _id(namespace, "availability")
    health_policy_id = _id(namespace, "health-policy")
    event_deployment_id = _id(namespace, f"event:{deployment.event.key}")
    stage_by_key = {stage.key: stage for stage in stages}
    configured_stage_keys = {stage.key for stage in deployment.event.stages}
    if set(stage_by_key) != configured_stage_keys:
        raise ValueError("runtime_stage_resolution_mismatch")

    identity = RuntimeIdentity(
        runtime_id=runtime_id,
        logical_name=f"StageFlow {deployment.node_id}",
        deployment_profile=_profile(deployment.node_role),
        host_id=host_id,
        installation_id=_id(namespace, "installation"),
        event_deployment_id=event_deployment_id,
        configured_stage_ids=tuple(stage.id for stage in stages),
    )
    version = RuntimeVersion(
        product_name="StageFlow Runtime",
        semantic_version="1.0.0",
        build_identifier="durable-kernel-v1",
        contract_compatibility_version="1.0",
        configuration_schema_version=deployment.schema_version,
        capability_schema_version="1.0",
    )
    volume_ids = tuple(
        _id(namespace, f"volume:{source.key}")
        for stage in deployment.event.stages
        for source in stage.sources
    )
    host = RuntimeHost(
        host_id=host_id,
        host_name=platform.node() or deployment.node_id,
        operating_system_family=platform.system() or "unknown",
        operating_system_version=platform.version() or "unknown",
        architecture=platform.machine() or "unknown",
        local_volume_ids=volume_ids,
        power_source_type=RuntimePowerSourceType.UNKNOWN,
    )
    capability_kinds = (
        RuntimeCapabilityKind.CANDIDATE_DISCOVERY,
        RuntimeCapabilityKind.RESOURCE_SNAPSHOT_COLLECTION,
        RuntimeCapabilityKind.WRITE_STATE_OBSERVATION_COLLECTION,
        RuntimeCapabilityKind.READ_ACCESS_OBSERVATION_COLLECTION,
        RuntimeCapabilityKind.RESOURCE_PRESENCE_OBSERVATION_COLLECTION,
        RuntimeCapabilityKind.STABLE_RESOURCE_IDENTITY,
        RuntimeCapabilityKind.COMPLETED_ASSET_ASSEMBLY,
        RuntimeCapabilityKind.LOCAL_FILESYSTEM_ACCESS,
        RuntimeCapabilityKind.RESOURCE_PRESSURE_AWARENESS,
        RuntimeCapabilityKind.EVENT_MODE_SUPPORT,
        RuntimeCapabilityKind.OPTIONAL_ACTIVITY_SUSPENSION,
        RuntimeCapabilityKind.HEALTH_REPORTING,
    )
    capability_ids = {
        kind: _id(namespace, f"capability:{kind.value}") for kind in capability_kinds
    }
    general = tuple(
        RuntimeCapability(
            id=capability_ids[kind],
            runtime_id=runtime_id,
            kind=kind,
            support_status=RuntimeCapabilitySupportStatus.SUPPORTED,
            capability_version="1.0",
            scope="runtime",
        )
        for kind in capability_kinds
    )
    source_capability = RuntimeSourceCapability(
        id=source_capability_id,
        runtime_id=runtime_id,
        runtime_capability_id=capability_ids[
            RuntimeCapabilityKind.LOCAL_FILESYSTEM_ACCESS
        ],
        supported_location_schemes=(
            RuntimeSourceLocationScheme.LOCAL_FILE,
            RuntimeSourceLocationScheme.MOUNTED_VOLUME,
        ),
        supported_host_scope=RuntimeSourceHostScope.CONFIGURED_HOSTS,
        supported_host_ids=(host_id,),
        supported_volume_ids=volume_ids,
        access_mode=RuntimeSourceAccessMode.READ_ONLY,
        source_adapter_id=adapter_id,
        recorder_application_ids=(recorder_id,),
    )
    observation_kinds = {
        RuntimeObservationType.RESOURCE_SNAPSHOT: (
            RuntimeCapabilityKind.RESOURCE_SNAPSHOT_COLLECTION
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
    observation_capabilities = tuple(
        RuntimeObservationCapability(
            id=_id(namespace, f"observation:{observation_type.value}"),
            runtime_id=runtime_id,
            runtime_capability_id=capability_ids[kind],
            observation_type=observation_type,
            collector_or_adapter_id=adapter_id,
            supported_source_schemes=(
                RuntimeSourceLocationScheme.LOCAL_FILE,
                RuntimeSourceLocationScheme.MOUNTED_VOLUME,
            ),
            collection_mode=RuntimeCollectionMode.SCHEDULED_SAMPLING,
            timing_precision=timedelta(milliseconds=100),
            stable_identity_support=True,
        )
        for observation_type, kind in observation_kinds.items()
    )
    readiness_capability = RuntimeReadinessCapability(
        id=readiness_capability_id,
        runtime_id=runtime_id,
        supporting_capability_ids=tuple(capability.id for capability in general),
        supported_finalization_methods=(),
        snapshot_support=True,
        write_state_support=True,
        read_access_support=True,
        presence_support=True,
        stable_identity_support=True,
        supported_policy_ids=(policy_id,),
        supported_policy_versions=("1.0",),
    )
    capability_set = RuntimeCapabilitySet(
        id=capability_set_id,
        runtime_id=runtime_id,
        capability_schema_version="1.0",
        capabilities=general,
        source_capabilities=(source_capability,),
        observation_capabilities=observation_capabilities,
        readiness_capabilities=(readiness_capability,),
        declared_at=configured_at,
    )
    parameters = AssetReadinessPolicyParameters(
        minimum_stable_interval=timedelta(seconds=5),
        require_read_access_for_stability=True,
        require_post_finalization_presence=True,
        accepted_strong_finalization_methods=(
            CompletedMediaAssetCompletionMethod.ATOMIC_RENAME_OBSERVED,
        ),
        require_inactive_write_when_available=True,
        policy_version="1.0",
    )
    required_kinds = (
        RuntimeCapabilityKind.RESOURCE_SNAPSHOT_COLLECTION,
        RuntimeCapabilityKind.WRITE_STATE_OBSERVATION_COLLECTION,
        RuntimeCapabilityKind.READ_ACCESS_OBSERVATION_COLLECTION,
        RuntimeCapabilityKind.RESOURCE_PRESENCE_OBSERVATION_COLLECTION,
        RuntimeCapabilityKind.STABLE_RESOURCE_IDENTITY,
    )
    selection = RuntimeReadinessPolicySelection(
        id=selection_id,
        runtime_id=runtime_id,
        readiness_capability_id=readiness_capability_id,
        policy_id=policy_id,
        policy_version="1.0",
        policy_parameters=parameters,
        selected_route=RuntimeReadinessRoute.STABILITY_DERIVED,
        required_capability_ids=tuple(capability_ids[kind] for kind in required_kinds),
        optional_capability_ids=(),
        fallback_behavior=RuntimeReadinessFallback.REMAIN_INSUFFICIENT,
    )
    observation_types = tuple(observation_kinds)
    targets = tuple(
        RuntimeCollectionTarget(
            id=_id(namespace, f"target:{source.key}"),
            runtime_id=runtime_id,
            source_capability_id=source_capability_id,
            source_location_scheme=RuntimeSourceLocationScheme.LOCAL_FILE,
            opaque_location_reference=source.path,
            source_host_id=host_id,
            source_volume_id=_id(namespace, f"volume:{source.key}"),
            expected_recorder_application_id=recorder_id,
            configured_stage_id=stage_by_key[stage.key].id,
            candidate_asset_kind_hint=CompletedMediaAssetKind.RECORDING_SEGMENT,
            enabled_observation_types=observation_types,
            metadata={"source_binding_key": source.key},
        )
        for stage in deployment.event.stages
        for source in stage.sources
    )
    plan = RuntimeCollectionPlan(
        id=plan_id,
        runtime_id=runtime_id,
        plan_version="1.0",
        enabled=True,
        targets=targets,
        observation_capability_ids=tuple(
            capability.id for capability in observation_capabilities
        ),
        collection_modes=(RuntimeCollectionMode.SCHEDULED_SAMPLING,),
        readiness_policy_selection_id=selection_id,
        resource_policy_id=resource_policy_id,
        event_mode_id=event_mode_id,
    )
    limits = deployment.resources
    budget = RuntimeResourceBudget(
        id=budget_id,
        runtime_id=runtime_id,
        maximum_cpu_utilization_percentage=limits.maximum_cpu_percentage,
        maximum_memory_allocation_bytes=limits.maximum_memory_bytes,
        maximum_disk_write_bytes_per_second=0,
        maximum_concurrent_candidate_assessments=(
            limits.maximum_concurrent_assessments
        ),
        maximum_concurrent_read_access_checks=1,
        maximum_collections_per_minute=12,
        burst_allowance=1,
    )
    pressure_responses = tuple(
        RuntimePressureResponse(state, action)
        for state, action in (
            (
                RuntimePressureState.NORMAL,
                RuntimePressureAction.OPERATE_WITHIN_BUDGETS,
            ),
            (
                RuntimePressureState.ELEVATED,
                RuntimePressureAction.REDUCE_OPTIONAL_ACTIVITY,
            ),
            (
                RuntimePressureState.CRITICAL,
                RuntimePressureAction.SUSPEND_OPTIONAL_ACTIVITY,
            ),
            (
                RuntimePressureState.RECORDING_SAFETY_UNCERTAIN,
                RuntimePressureAction.YIELD_NONESSENTIAL_WORK,
            ),
        )
    )
    resource_policy = RuntimeResourcePolicy(
        id=resource_policy_id,
        runtime_id=runtime_id,
        priority_class=RuntimeResourcePriorityClass.PRODUCTION_SUBORDINATE,
        event_mode_behavior=RuntimeOptionalActivityPolicy.SUSPEND,
        budget=budget,
        gpu_use_policy=RuntimeGpuUsePolicy.FORBIDDEN,
        optional_activity_policy=RuntimeOptionalActivityPolicy.SUSPEND,
        pressure_responses=pressure_responses,
        recovery_policy=RuntimeRecoveryPolicy.REQUIRE_EXPLICIT_DECLARATION,
    )
    mode = _event_mode(deployment.event_mode)
    event_mode = RuntimeEventMode(
        id=event_mode_id,
        runtime_id=runtime_id,
        mode=mode,
        enabled=True,
        event_deployment_id=event_deployment_id,
        active_from=configured_at,
        production_subordinate_requirement=True,
        optional_activity_behavior=RuntimeOptionalActivityPolicy.SUSPEND,
        network_policy=_network(deployment.network_policy),
        asset_retention_expectation=(
            RuntimeAssetRetentionExpectation.SOURCE_OWNED_NO_CHANGE
        ),
        manual_override_status=RuntimeManualOverrideStatus.NOT_ALLOWED,
    )
    assembly = RuntimeAssetAssemblyPlan(
        id=assembly_id,
        runtime_id=runtime_id,
        manifest_schema_name="stageflow.completed_media_asset",
        manifest_schema_version="1.0",
        supported_asset_kinds=(CompletedMediaAssetKind.RECORDING_SEGMENT,),
        context_sources=(RuntimeContextSource.EXPLICIT_RUNTIME_CONFIGURATION,),
        technical_description_sources=(RuntimeTechnicalDescriptionSource.NONE,),
        integrity_sources=(RuntimeIntegritySource.NONE,),
        source_location_handling_policy=(
            RuntimeSourceLocationHandlingPolicy.READ_ONLY_REFERENCE
        ),
        summary_privacy_policy=RuntimeSummaryPrivacyPolicy.OMIT_FULL_SOURCE_PATHS,
    )
    health_policy = RuntimeHealthReportingPolicy(
        id=health_policy_id,
        runtime_id=runtime_id,
        enabled=True,
        expected_reporting_interval=timedelta(seconds=30),
    )
    configuration_contract = RuntimeConfiguration(
        id=configuration_id,
        runtime_id=runtime_id,
        configuration_schema_version=deployment.schema_version,
        enabled=True,
        event_mode=event_mode,
        capability_set=capability_set,
        collection_plans=(plan,),
        readiness_policy_selections=(selection,),
        asset_assembly_plans=(assembly,),
        resource_policy=resource_policy,
        health_reporting_policy=health_policy,
        configured_at=configured_at,
    )
    health = RuntimeHealth(
        id=health_id,
        runtime_id=runtime_id,
        status=RuntimeHealthStatus.HEALTHY,
        assessed_at=configured_at,
        configuration_validity=RuntimeConfigurationValidity.VALID,
        capability_availability=RuntimeDeclaredComponentStatus.AVAILABLE,
        resource_policy_availability=RuntimeDeclaredComponentStatus.AVAILABLE,
        collection_plan_validity=RuntimeDeclaredComponentStatus.AVAILABLE,
        reason_codes=("validated_kernel_configuration",),
    )
    availability = RuntimeAvailability(
        id=availability_id,
        runtime_id=runtime_id,
        status=RuntimeAvailabilityStatus.AVAILABLE,
        declared_at=configured_at,
        reason_codes=("validated_kernel_configuration",),
        expected_capability_availability=RuntimeDeclaredComponentStatus.AVAILABLE,
        event_mode_compatible=True,
    )
    runtime = StageFlowRuntime(
        identity=identity,
        profile=identity.deployment_profile,
        software_version=version,
        host=host,
        configuration=configuration_contract,
        capability_set=capability_set,
        resource_policy=resource_policy,
        event_mode=event_mode,
        collection_plans=(plan,),
        readiness_policy_selections=(selection,),
        asset_assembly_plans=(assembly,),
        health=health,
        availability=availability,
        limitations=(),
        configured_at=configured_at,
    )
    validation = validate_runtime(runtime)
    if validation.outcome is RuntimeConfigurationValidity.INVALID:
        codes = ",".join(reason.code.value for reason in validation.reasons)
        raise ValueError(f"runtime_configuration_invalid:{codes}")
    return runtime


__all__ = ["build_stageflow_runtime"]
