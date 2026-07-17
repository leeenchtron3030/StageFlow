from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.shared.ids import EntityId

from .runtime_availability import RuntimeAvailabilityStatus
from .runtime_capability import (
    RuntimeCapability,
    RuntimeCapabilityKind,
    RuntimeCapabilitySupportStatus,
)
from .runtime_contract_validation import (
    freeze_runtime_metadata,
    normalize_entity_ids,
    require_non_empty,
)
from .runtime_event_mode import (
    RuntimeAssetRetentionExpectation,
    RuntimeEventModeKind,
    RuntimeNetworkPolicy,
)
from .runtime_health import (
    RuntimeConfigurationValidity,
    RuntimeDeclaredComponentStatus,
    RuntimeHealthStatus,
)
from .runtime_limitation import RuntimeLimitationSeverity
from .runtime_observation_capability import RuntimeObservationType
from .runtime_profile import RuntimeProfile
from .runtime_readiness_capability import RuntimeReadinessCapability
from .runtime_readiness_policy_selection import (
    RuntimeReadinessFallback,
    RuntimeReadinessPolicySelection,
    RuntimeReadinessRoute,
)
from .runtime_resource_policy import (
    RuntimeGpuUsePolicy,
    RuntimeOptionalActivityPolicy,
    RuntimeResourcePriorityClass,
)
from .runtime_source_capability import RuntimeSourceAccessMode, RuntimeSourceHostScope
from .stageflow_runtime import StageFlowRuntime

RuntimeValidationOutcome = RuntimeConfigurationValidity


class RuntimeValidationReasonCode(StrEnum):
    RUNTIME_ID_MISMATCH = "runtime_id_mismatch"
    PROFILE_MISMATCH = "profile_mismatch"
    HOST_ID_MISMATCH = "host_id_mismatch"
    CONFIGURATION_GRAPH_MISMATCH = "configuration_graph_mismatch"
    CONFIGURATION_SCHEMA_MISMATCH = "configuration_schema_mismatch"
    CAPABILITY_SCHEMA_MISMATCH = "capability_schema_mismatch"
    POLICY_VERSION_MISMATCH = "policy_version_mismatch"
    DUPLICATE_CAPABILITY_ID = "duplicate_capability_id"
    CONFLICTING_CAPABILITY_KIND = "conflicting_capability_kind"
    CAPABILITY_REFERENCE_MISSING = "capability_reference_missing"
    CAPABILITY_UNAVAILABLE = "capability_unavailable"
    SPECIALIZED_CAPABILITY_MISMATCH = "specialized_capability_mismatch"
    EVENT_MODE_PRIORITY_MISMATCH = "event_mode_priority_mismatch"
    EVENT_MODE_DISK_WRITE_FORBIDDEN = "event_mode_disk_write_forbidden"
    EVENT_MODE_NETWORK_REQUIRED = "event_mode_network_required"
    EVENT_MODE_GPU_UNCONSTRAINED = "event_mode_gpu_unconstrained"
    EVENT_MODE_OPTIONAL_ACTIVITY_UNSAFE = "event_mode_optional_activity_unsafe"
    EVENT_MODE_RETENTION_UNSAFE = "event_mode_retention_unsafe"
    EVENT_MODE_SOURCE_WRITE_ACCESS = "event_mode_source_write_access"
    DISABLED_RUNTIME_HAS_ACTIVE_PLAN = "disabled_runtime_has_active_plan"
    DISABLED_RUNTIME_AVAILABILITY_MISMATCH = (
        "disabled_runtime_availability_mismatch"
    )
    COLLECTION_REFERENCE_MISMATCH = "collection_reference_mismatch"
    SOURCE_CAPABILITY_MISSING = "source_capability_missing"
    SOURCE_SCHEME_UNSUPPORTED = "source_scheme_unsupported"
    SOURCE_HOST_UNSUPPORTED = "source_host_unsupported"
    SOURCE_VOLUME_UNSUPPORTED = "source_volume_unsupported"
    OBSERVATION_CAPABILITY_MISSING = "observation_capability_missing"
    OBSERVATION_TYPE_UNSUPPORTED = "observation_type_unsupported"
    COLLECTION_MODE_UNSUPPORTED = "collection_mode_unsupported"
    READINESS_CAPABILITY_MISSING = "readiness_capability_missing"
    READINESS_POLICY_UNSUPPORTED = "readiness_policy_unsupported"
    READINESS_ROUTE_UNSUPPORTED = "readiness_route_unsupported"
    STABILITY_SNAPSHOT_CAPABILITY_MISSING = "stability_snapshot_capability_missing"
    STABILITY_PRESENCE_CAPABILITY_MISSING = "stability_presence_capability_missing"
    STABILITY_READ_ACCESS_CAPABILITY_MISSING = (
        "stability_read_access_capability_missing"
    )
    STABILITY_WRITE_STATE_CAPABILITY_MISSING = (
        "stability_write_state_capability_missing"
    )
    STABILITY_IDENTITY_CAPABILITY_MISSING = (
        "stability_identity_capability_missing"
    )
    STRONG_FINALIZATION_CAPABILITY_MISSING = (
        "strong_finalization_capability_missing"
    )
    STRONG_PRESENCE_CAPABILITY_MISSING = "strong_presence_capability_missing"
    INVALID_READINESS_FALLBACK = "invalid_readiness_fallback"
    ASSET_ASSEMBLY_CAPABILITY_MISSING = "asset_assembly_capability_missing"
    ASSET_MANIFEST_SCHEMA_MISMATCH = "asset_manifest_schema_mismatch"
    ASSET_PRIVACY_POLICY_UNKNOWN = "asset_privacy_policy_unknown"
    NON_AUTHORITATIVE_CONTEXT_HINT = "non_authoritative_context_hint"
    HEALTH_DECLARATION_INCONSISTENT = "health_declaration_inconsistent"
    AVAILABILITY_DECLARATION_INCONSISTENT = (
        "availability_declaration_inconsistent"
    )
    LIMITATION_REFERENCE_MISSING = "limitation_reference_missing"
    BLOCKING_LIMITATION = "blocking_limitation"
    NON_BLOCKING_LIMITATION = "non_blocking_limitation"
    OPTIONAL_CAPABILITY_UNAVAILABLE = "optional_capability_unavailable"
    UNKNOWN_RUNTIME_PROFILE = "unknown_runtime_profile"
    CONFIGURATION_VALID = "configuration_valid"
    UNKNOWN_VALIDATION_CONDITION = "unknown_validation_condition"


_REASON_ORDER = {
    code: index for index, code in enumerate(RuntimeValidationReasonCode)
}

_OBSERVATION_KINDS = {
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

_SOURCE_KINDS = frozenset(
    {
        RuntimeCapabilityKind.LOCAL_FILESYSTEM_ACCESS,
        RuntimeCapabilityKind.MOUNTED_VOLUME_ACCESS,
        RuntimeCapabilityKind.NETWORK_SHARE_ACCESS,
    }
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RuntimeValidationReason:
    code: RuntimeValidationReasonCode
    message: str
    related_ids: Sequence[EntityId] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "message",
            require_non_empty(self.message, "RuntimeValidationReason.message"),
        )
        object.__setattr__(
            self,
            "related_ids",
            normalize_entity_ids(
                self.related_ids,
                "RuntimeValidationReason.related_ids",
            ),
        )


@dataclass(frozen=True, slots=True)
class RuntimeValidationResult:
    runtime_id: EntityId
    configuration_id: EntityId
    outcome: RuntimeValidationOutcome
    reasons: Sequence[RuntimeValidationReason]
    limitation_ids: Sequence[EntityId] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        reasons = _normalize_reasons(self.reasons)
        if not reasons:
            raise ValueError("Runtime validation result requires at least one reason.")
        object.__setattr__(self, "reasons", reasons)
        object.__setattr__(
            self,
            "limitation_ids",
            normalize_entity_ids(
                self.limitation_ids,
                "RuntimeValidationResult.limitation_ids",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(self.metadata, "RuntimeValidationResult.metadata"),
        )


def validate_runtime(runtime: StageFlowRuntime) -> RuntimeValidationResult:
    reasons: list[RuntimeValidationReason] = []
    reasons.extend(_identity_reasons(runtime))
    reasons.extend(_schema_reasons(runtime))
    reasons.extend(_capability_reasons(runtime))
    reasons.extend(_event_mode_reasons(runtime))
    reasons.extend(_collection_reasons(runtime))
    reasons.extend(_readiness_reasons(runtime))
    reasons.extend(_assembly_reasons(runtime))
    reasons.extend(_health_availability_reasons(runtime))

    blocking_limitations = tuple(
        limitation
        for limitation in runtime.limitations
        if limitation.severity is RuntimeLimitationSeverity.BLOCKING
    )
    if blocking_limitations:
        reasons.append(
            _reason(
                RuntimeValidationReasonCode.BLOCKING_LIMITATION,
                "A first-class blocking Runtime limitation is present.",
                tuple(limitation.id for limitation in blocking_limitations),
            )
        )

    invalid = any(reason.code in _INVALID_REASON_CODES for reason in reasons)
    has_limitations = _has_non_blocking_limitations(runtime, reasons)
    if invalid:
        outcome = RuntimeValidationOutcome.INVALID
    elif has_limitations:
        outcome = RuntimeValidationOutcome.VALID_WITH_LIMITATIONS
        reasons.append(
            _reason(
                RuntimeValidationReasonCode.NON_BLOCKING_LIMITATION,
                "Configuration remains feasible with explicit non-blocking limitations.",
                tuple(
                    limitation.id
                    for limitation in runtime.limitations
                    if limitation.severity
                    in (
                        RuntimeLimitationSeverity.INFORMATIONAL,
                        RuntimeLimitationSeverity.NON_BLOCKING,
                        RuntimeLimitationSeverity.UNKNOWN,
                    )
                ),
            )
        )
    elif runtime.profile is RuntimeProfile.UNKNOWN:
        outcome = RuntimeValidationOutcome.UNKNOWN
        reasons.append(
            _reason(
                RuntimeValidationReasonCode.UNKNOWN_RUNTIME_PROFILE,
                "Runtime profile remains explicitly unknown.",
            )
        )
    else:
        outcome = RuntimeValidationOutcome.VALID
        reasons.append(
            _reason(
                RuntimeValidationReasonCode.CONFIGURATION_VALID,
                "Runtime declarations are internally coherent.",
            )
        )

    return RuntimeValidationResult(
        runtime_id=runtime.identity.runtime_id,
        configuration_id=runtime.configuration.id,
        outcome=outcome,
        reasons=reasons,
        limitation_ids=tuple(limitation.id for limitation in runtime.limitations),
    )


def _identity_reasons(runtime: StageFlowRuntime) -> tuple[RuntimeValidationReason, ...]:
    expected = runtime.identity.runtime_id
    runtime_ids = (
        runtime.configuration.runtime_id,
        runtime.capability_set.runtime_id,
        runtime.resource_policy.runtime_id,
        runtime.resource_policy.budget.runtime_id,
        runtime.event_mode.runtime_id,
        runtime.health.runtime_id,
        runtime.availability.runtime_id,
        runtime.configuration.health_reporting_policy.runtime_id,
        *(value.runtime_id for value in runtime.collection_plans),
        *(value.runtime_id for value in runtime.readiness_policy_selections),
        *(value.runtime_id for value in runtime.asset_assembly_plans),
        *(value.runtime_id for value in runtime.limitations),
        *(value.runtime_id for value in runtime.capability_set.capabilities),
        *(value.runtime_id for value in runtime.capability_set.source_capabilities),
        *(value.runtime_id for value in runtime.capability_set.observation_capabilities),
        *(value.runtime_id for value in runtime.capability_set.readiness_capabilities),
    )
    reasons: list[RuntimeValidationReason] = []
    if any(runtime_id != expected for runtime_id in runtime_ids):
        reasons.append(
            _reason(
                RuntimeValidationReasonCode.RUNTIME_ID_MISMATCH,
                "All Runtime-owned declarations must use one Runtime ID.",
            )
        )
    if runtime.profile is not runtime.identity.deployment_profile:
        reasons.append(
            _reason(
                RuntimeValidationReasonCode.PROFILE_MISMATCH,
                "Top-level and identity Runtime profiles must match.",
            )
        )
    if runtime.host.host_id != runtime.identity.host_id:
        reasons.append(
            _reason(
                RuntimeValidationReasonCode.HOST_ID_MISMATCH,
                "Runtime identity and host declaration must use one host ID.",
            )
        )
    configuration = runtime.configuration
    if (
        configuration.event_mode != runtime.event_mode
        or configuration.capability_set != runtime.capability_set
        or configuration.resource_policy != runtime.resource_policy
        or configuration.collection_plans != runtime.collection_plans
        or configuration.readiness_policy_selections
        != runtime.readiness_policy_selections
        or configuration.asset_assembly_plans != runtime.asset_assembly_plans
        or configuration.configured_at != runtime.configured_at
    ):
        reasons.append(
            _reason(
                RuntimeValidationReasonCode.CONFIGURATION_GRAPH_MISMATCH,
                "Top-level Runtime declarations must match the immutable configuration.",
                (configuration.id,),
            )
        )
    return tuple(reasons)


def _schema_reasons(runtime: StageFlowRuntime) -> tuple[RuntimeValidationReason, ...]:
    reasons: list[RuntimeValidationReason] = []
    if (
        runtime.configuration.configuration_schema_version
        != runtime.software_version.configuration_schema_version
    ):
        reasons.append(
            _reason(
                RuntimeValidationReasonCode.CONFIGURATION_SCHEMA_MISMATCH,
                "Runtime and configuration schema versions must match explicitly.",
            )
        )
    if (
        runtime.capability_set.capability_schema_version
        != runtime.software_version.capability_schema_version
    ):
        reasons.append(
            _reason(
                RuntimeValidationReasonCode.CAPABILITY_SCHEMA_MISMATCH,
                "Runtime and capability schema versions must match explicitly.",
            )
        )
    return tuple(reasons)


def _capability_reasons(runtime: StageFlowRuntime) -> tuple[RuntimeValidationReason, ...]:
    capability_set = runtime.capability_set
    reasons: list[RuntimeValidationReason] = []
    if capability_set.conflicting_capability_ids:
        reasons.append(
            _reason(
                RuntimeValidationReasonCode.DUPLICATE_CAPABILITY_ID,
                "One capability ID contains conflicting declarations.",
                capability_set.conflicting_capability_ids,
            )
        )
    if capability_set.conflicting_capability_keys:
        reasons.append(
            _reason(
                RuntimeValidationReasonCode.CONFLICTING_CAPABILITY_KIND,
                "One capability kind and scope has conflicting support states.",
            )
        )
    by_id = {capability.id: capability for capability in capability_set.capabilities}
    for source in capability_set.source_capabilities:
        capability = by_id.get(source.runtime_capability_id)
        if capability is None:
            reasons.append(
                _reason(
                    RuntimeValidationReasonCode.CAPABILITY_REFERENCE_MISSING,
                    "Source declaration references an unknown Runtime capability.",
                    (source.id, source.runtime_capability_id),
                )
            )
        elif capability.kind not in _SOURCE_KINDS:
            reasons.append(
                _reason(
                    RuntimeValidationReasonCode.SPECIALIZED_CAPABILITY_MISMATCH,
                    "Source declaration references an incompatible capability kind.",
                    (source.id, capability.id),
                )
            )
    for observation in capability_set.observation_capabilities:
        capability = by_id.get(observation.runtime_capability_id)
        if capability is None:
            reasons.append(
                _reason(
                    RuntimeValidationReasonCode.CAPABILITY_REFERENCE_MISSING,
                    "Observation declaration references an unknown Runtime capability.",
                    (observation.id, observation.runtime_capability_id),
                )
            )
        elif capability.kind is not _OBSERVATION_KINDS[observation.observation_type]:
            reasons.append(
                _reason(
                    RuntimeValidationReasonCode.SPECIALIZED_CAPABILITY_MISMATCH,
                    "Observation type and general capability kind must match.",
                    (observation.id, capability.id),
                )
            )
    for readiness in capability_set.readiness_capabilities:
        missing = tuple(
            capability_id
            for capability_id in readiness.supporting_capability_ids
            if capability_id not in by_id
        )
        if missing:
            reasons.append(
                _reason(
                    RuntimeValidationReasonCode.CAPABILITY_REFERENCE_MISSING,
                    "Readiness capability references unknown supporting capabilities.",
                    (readiness.id, *missing),
                )
            )
    return tuple(reasons)


def _event_mode_reasons(runtime: StageFlowRuntime) -> tuple[RuntimeValidationReason, ...]:
    mode = runtime.event_mode
    policy = runtime.resource_policy
    reasons: list[RuntimeValidationReason] = []
    if mode.mode is RuntimeEventModeKind.EVENT:
        if (
            not mode.enabled
            or not mode.production_subordinate_requirement
            or policy.priority_class
            is not RuntimeResourcePriorityClass.PRODUCTION_SUBORDINATE
        ):
            reasons.append(
                _reason(
                    RuntimeValidationReasonCode.EVENT_MODE_PRIORITY_MISMATCH,
                    "Event mode must be enabled and production-subordinate.",
                )
            )
        if (policy.budget.maximum_disk_write_bytes_per_second or 0) > 0:
            reasons.append(
                _reason(
                    RuntimeValidationReasonCode.EVENT_MODE_DISK_WRITE_FORBIDDEN,
                    "Event-mode source observation must not require disk writes.",
                    (policy.budget.id,),
                )
            )
        if mode.network_policy is RuntimeNetworkPolicy.NETWORK_REQUIRED:
            reasons.append(
                _reason(
                    RuntimeValidationReasonCode.EVENT_MODE_NETWORK_REQUIRED,
                    "Event-mode candidate readiness cannot require internet access.",
                    (mode.id,),
                )
            )
        if policy.gpu_use_policy is RuntimeGpuUsePolicy.ALLOWED:
            reasons.append(
                _reason(
                    RuntimeValidationReasonCode.EVENT_MODE_GPU_UNCONSTRAINED,
                    "Event mode requires forbidden or idle-constrained GPU use.",
                    (policy.id,),
                )
            )
        safe_optional = {
            RuntimeOptionalActivityPolicy.REDUCE,
            RuntimeOptionalActivityPolicy.SUSPEND,
            RuntimeOptionalActivityPolicy.DISABLED,
        }
        if (
            mode.optional_activity_behavior not in safe_optional
            or policy.optional_activity_policy not in safe_optional
        ):
            reasons.append(
                _reason(
                    RuntimeValidationReasonCode.EVENT_MODE_OPTIONAL_ACTIVITY_UNSAFE,
                    "Event-mode optional activity must be reducible or suspendable.",
                )
            )
        if mode.asset_retention_expectation is not (
            RuntimeAssetRetentionExpectation.SOURCE_OWNED_NO_CHANGE
        ):
            reasons.append(
                _reason(
                    RuntimeValidationReasonCode.EVENT_MODE_RETENTION_UNSAFE,
                    "Event mode must preserve source ownership without modification.",
                )
            )
        active_source_ids = {
            target.source_capability_id
            for plan in runtime.collection_plans
            if plan.enabled
            for target in plan.targets
        }
        writable_sources = tuple(
            source.id
            for source in runtime.capability_set.source_capabilities
            if source.id in active_source_ids
            and source.access_mode is not RuntimeSourceAccessMode.READ_ONLY
        )
        if writable_sources:
            reasons.append(
                _reason(
                    RuntimeValidationReasonCode.EVENT_MODE_SOURCE_WRITE_ACCESS,
                    "Event-mode collection sources must be declared read-only.",
                    writable_sources,
                )
            )
    if mode.mode is RuntimeEventModeKind.DISABLED or not runtime.configuration.enabled:
        active = tuple(plan.id for plan in runtime.collection_plans if plan.enabled)
        if active:
            reasons.append(
                _reason(
                    RuntimeValidationReasonCode.DISABLED_RUNTIME_HAS_ACTIVE_PLAN,
                    "A disabled Runtime cannot contain an enabled collection plan.",
                    active,
                )
            )
        if runtime.availability.status is not RuntimeAvailabilityStatus.DISABLED:
            reasons.append(
                _reason(
                    RuntimeValidationReasonCode.DISABLED_RUNTIME_AVAILABILITY_MISMATCH,
                    "A disabled Runtime must declare disabled availability.",
                )
            )
    return tuple(reasons)


def _collection_reasons(runtime: StageFlowRuntime) -> tuple[RuntimeValidationReason, ...]:
    source_by_id = {
        capability.id: capability
        for capability in runtime.capability_set.source_capabilities
    }
    observation_by_id = {
        capability.id: capability
        for capability in runtime.capability_set.observation_capabilities
    }
    general_by_id = {
        capability.id: capability for capability in runtime.capability_set.capabilities
    }
    selection_ids = {selection.id for selection in runtime.readiness_policy_selections}
    reasons: list[RuntimeValidationReason] = []
    for plan in runtime.collection_plans:
        if (
            plan.resource_policy_id != runtime.resource_policy.id
            or plan.event_mode_id != runtime.event_mode.id
            or plan.readiness_policy_selection_id not in selection_ids
        ):
            reasons.append(
                _reason(
                    RuntimeValidationReasonCode.COLLECTION_REFERENCE_MISMATCH,
                    "Collection plan references must match configured policy declarations.",
                    (plan.id,),
                )
            )
        selected_observations = tuple(
            observation_by_id.get(capability_id)
            for capability_id in plan.observation_capability_ids
        )
        missing_observations = tuple(
            capability_id
            for capability_id, capability in zip(
                plan.observation_capability_ids,
                selected_observations,
                strict=True,
            )
            if capability is None
        )
        if missing_observations:
            reasons.append(
                _reason(
                    RuntimeValidationReasonCode.OBSERVATION_CAPABILITY_MISSING,
                    "Collection plan references unknown observation capabilities.",
                    (plan.id, *missing_observations),
                )
            )
        for observation in (value for value in selected_observations if value is not None):
            general = general_by_id.get(observation.runtime_capability_id)
            if general is None or not _capability_available(general):
                reasons.append(
                    _reason(
                        RuntimeValidationReasonCode.CAPABILITY_UNAVAILABLE,
                        "Selected observation capability is not declared available.",
                        (plan.id, observation.id),
                    )
                )
            if plan.collection_modes and observation.collection_mode not in plan.collection_modes:
                reasons.append(
                    _reason(
                        RuntimeValidationReasonCode.COLLECTION_MODE_UNSUPPORTED,
                        "Collection plan mode does not include the observation mode.",
                        (plan.id, observation.id),
                    )
                )
        for target in plan.targets:
            source = source_by_id.get(target.source_capability_id)
            if source is None:
                reasons.append(
                    _reason(
                        RuntimeValidationReasonCode.SOURCE_CAPABILITY_MISSING,
                        "Collection target references an unknown source capability.",
                        (plan.id, target.id, target.source_capability_id),
                    )
                )
                continue
            general_source = general_by_id.get(source.runtime_capability_id)
            if general_source is None or not _capability_available(general_source):
                reasons.append(
                    _reason(
                        RuntimeValidationReasonCode.CAPABILITY_UNAVAILABLE,
                        "Selected source capability is not declared available.",
                        (plan.id, source.id),
                    )
                )
            if target.source_location_scheme not in source.supported_location_schemes:
                reasons.append(
                    _reason(
                        RuntimeValidationReasonCode.SOURCE_SCHEME_UNSUPPORTED,
                        "Collection target source scheme is not declared supported.",
                        (target.id, source.id),
                    )
                )
            if (
                source.supported_host_scope is RuntimeSourceHostScope.CONFIGURED_HOSTS
                and target.source_host_id not in source.supported_host_ids
            ):
                reasons.append(
                    _reason(
                        RuntimeValidationReasonCode.SOURCE_HOST_UNSUPPORTED,
                        "Collection target host is outside configured source scope.",
                        (target.id, source.id),
                    )
                )
            if (
                target.source_volume_id is not None
                and source.supported_volume_ids
                and target.source_volume_id not in source.supported_volume_ids
            ):
                reasons.append(
                    _reason(
                        RuntimeValidationReasonCode.SOURCE_VOLUME_UNSUPPORTED,
                        "Collection target volume is outside configured source scope.",
                        (target.id, source.id),
                    )
                )
            supported_types = {
                observation.observation_type
                for observation in selected_observations
                if observation is not None
                and target.source_location_scheme in observation.supported_source_schemes
            }
            if not set(target.enabled_observation_types) <= supported_types:
                reasons.append(
                    _reason(
                        RuntimeValidationReasonCode.OBSERVATION_TYPE_UNSUPPORTED,
                        "Collection target requests an unsupported observation type.",
                        (target.id,),
                    )
                )
    return tuple(reasons)


def _readiness_reasons(runtime: StageFlowRuntime) -> tuple[RuntimeValidationReason, ...]:
    readiness_by_id = {
        capability.id: capability
        for capability in runtime.capability_set.readiness_capabilities
    }
    general_by_id = {
        capability.id: capability for capability in runtime.capability_set.capabilities
    }
    reasons: list[RuntimeValidationReason] = []
    for selection in runtime.readiness_policy_selections:
        capability = readiness_by_id.get(selection.readiness_capability_id)
        if capability is None:
            reasons.append(
                _reason(
                    RuntimeValidationReasonCode.READINESS_CAPABILITY_MISSING,
                    "Readiness selection references an unknown readiness capability.",
                    (selection.id, selection.readiness_capability_id),
                )
            )
            continue
        if (
            selection.policy_id not in capability.supported_policy_ids
            or selection.policy_version not in capability.supported_policy_versions
        ):
            reasons.append(
                _reason(
                    RuntimeValidationReasonCode.READINESS_POLICY_UNSUPPORTED,
                    "Selected ED-0049 policy ID or version is not declared supported.",
                    (selection.id, capability.id),
                )
            )
        for capability_id in selection.required_capability_ids:
            general = general_by_id.get(capability_id)
            if general is None:
                reasons.append(
                    _reason(
                        RuntimeValidationReasonCode.CAPABILITY_REFERENCE_MISSING,
                        "Readiness selection requires an unknown capability.",
                        (selection.id, capability_id),
                    )
                )
            elif not _capability_available(general):
                reasons.append(
                    _reason(
                        RuntimeValidationReasonCode.CAPABILITY_UNAVAILABLE,
                        "Readiness selection requires an unavailable capability.",
                        (selection.id, capability_id),
                    )
                )
        optional_unavailable = tuple(
            capability_id
            for capability_id in selection.optional_capability_ids
            if capability_id not in general_by_id
            or not _capability_available(general_by_id[capability_id])
        )
        if optional_unavailable:
            reasons.append(
                _reason(
                    RuntimeValidationReasonCode.OPTIONAL_CAPABILITY_UNAVAILABLE,
                    "Optional readiness capability is explicitly unavailable.",
                    (selection.id, *optional_unavailable),
                )
            )
        reasons.extend(_route_reasons(selection, capability))
    return tuple(reasons)


def _route_reasons(
    selection: RuntimeReadinessPolicySelection,
    capability: RuntimeReadinessCapability,
) -> tuple[RuntimeValidationReason, ...]:
    reasons: list[RuntimeValidationReason] = []
    needs_strong = selection.selected_route in (
        RuntimeReadinessRoute.STRONG_FINALIZATION,
        RuntimeReadinessRoute.STRONG_THEN_STABILITY,
    )
    needs_stability = selection.selected_route in (
        RuntimeReadinessRoute.STABILITY_DERIVED,
        RuntimeReadinessRoute.STRONG_THEN_STABILITY,
    ) or selection.fallback_behavior is RuntimeReadinessFallback.USE_STABILITY_ROUTE
    strong_is_optional = (
        selection.selected_route is RuntimeReadinessRoute.STRONG_FINALIZATION
        and selection.fallback_behavior
        is RuntimeReadinessFallback.USE_STABILITY_ROUTE
    )
    if needs_strong and not strong_is_optional:
        accepted = set(selection.policy_parameters.accepted_strong_finalization_methods)
        if not accepted & set(capability.supported_finalization_methods):
            reasons.append(
                _reason(
                    RuntimeValidationReasonCode.STRONG_FINALIZATION_CAPABILITY_MISSING,
                    "No accepted strong finalization method is declared supported.",
                    (selection.id, capability.id),
                )
            )
        if (
            selection.policy_parameters.require_post_finalization_presence
            and not capability.presence_support
        ):
            reasons.append(
                _reason(
                    RuntimeValidationReasonCode.STRONG_PRESENCE_CAPABILITY_MISSING,
                    "Strong route requires post-finalization presence capability.",
                    (selection.id, capability.id),
                )
            )
    if needs_stability:
        checks = (
            (
                not capability.snapshot_support,
                RuntimeValidationReasonCode.STABILITY_SNAPSHOT_CAPABILITY_MISSING,
                "Stability route requires snapshot capability.",
            ),
            (
                not capability.presence_support,
                RuntimeValidationReasonCode.STABILITY_PRESENCE_CAPABILITY_MISSING,
                "Stability route requires presence capability.",
            ),
            (
                selection.policy_parameters.require_read_access_for_stability
                and not capability.read_access_support,
                RuntimeValidationReasonCode.STABILITY_READ_ACCESS_CAPABILITY_MISSING,
                "Explicit ED-0049 parameters require read-access capability.",
            ),
            (
                selection.policy_parameters.require_inactive_write_when_available
                and not capability.write_state_support,
                RuntimeValidationReasonCode.STABILITY_WRITE_STATE_CAPABILITY_MISSING,
                "Explicit ED-0049 parameters require inactive-write capability.",
            ),
            (
                not capability.stable_identity_support,
                RuntimeValidationReasonCode.STABILITY_IDENTITY_CAPABILITY_MISSING,
                "Stability route requires stable resource identity capability.",
            ),
        )
        reasons.extend(
            _reason(code, message, (selection.id, capability.id))
            for failed, code, message in checks
            if failed
        )
    if (
        selection.fallback_behavior is RuntimeReadinessFallback.USE_STABILITY_ROUTE
        and selection.selected_route
        not in (
            RuntimeReadinessRoute.STRONG_FINALIZATION,
            RuntimeReadinessRoute.STRONG_THEN_STABILITY,
        )
    ):
        reasons.append(
            _reason(
                RuntimeValidationReasonCode.INVALID_READINESS_FALLBACK,
                "Stability fallback requires a strong-first route selection.",
                (selection.id,),
            )
        )
    if (
        selection.selected_route is RuntimeReadinessRoute.DISABLED
        and selection.fallback_behavior is not RuntimeReadinessFallback.NO_FALLBACK
    ):
        reasons.append(
            _reason(
                RuntimeValidationReasonCode.INVALID_READINESS_FALLBACK,
                "Disabled readiness selection cannot define a fallback route.",
                (selection.id,),
            )
        )
    return tuple(reasons)


def _assembly_reasons(runtime: StageFlowRuntime) -> tuple[RuntimeValidationReason, ...]:
    assembly_capabilities = tuple(
        capability
        for capability in runtime.capability_set.capabilities
        if capability.kind is RuntimeCapabilityKind.COMPLETED_ASSET_ASSEMBLY
        and _capability_available(capability)
    )
    reasons: list[RuntimeValidationReason] = []
    for plan in runtime.asset_assembly_plans:
        if not assembly_capabilities:
            reasons.append(
                _reason(
                    RuntimeValidationReasonCode.ASSET_ASSEMBLY_CAPABILITY_MISSING,
                    "Asset assembly plan requires a declared assembly capability.",
                    (plan.id,),
                )
            )
        if (
            plan.manifest_schema_name != "stageflow.completed_media_asset"
            or plan.manifest_schema_version != "1.0"
        ):
            reasons.append(
                _reason(
                    RuntimeValidationReasonCode.ASSET_MANIFEST_SCHEMA_MISMATCH,
                    "Assembly plan must use the ED-0048 manifest schema and version.",
                    (plan.id,),
                )
            )
        if "unknown" in (
            plan.source_location_handling_policy.value,
            plan.summary_privacy_policy.value,
        ):
            reasons.append(
                _reason(
                    RuntimeValidationReasonCode.ASSET_PRIVACY_POLICY_UNKNOWN,
                    "Assembly plan source-location privacy must be explicit.",
                    (plan.id,),
                )
            )
        if any(
            source.value in {"filename_hint_only", "path_hint_only"}
            for source in plan.context_sources
        ):
            reasons.append(
                _reason(
                    RuntimeValidationReasonCode.NON_AUTHORITATIVE_CONTEXT_HINT,
                    "Filename and path context sources remain non-authoritative hints.",
                    (plan.id,),
                )
            )
    return tuple(reasons)


def _health_availability_reasons(
    runtime: StageFlowRuntime,
) -> tuple[RuntimeValidationReason, ...]:
    reasons: list[RuntimeValidationReason] = []
    limitation_ids = {limitation.id for limitation in runtime.limitations}
    missing_health = tuple(
        limitation_id
        for limitation_id in runtime.health.limitation_ids
        if limitation_id not in limitation_ids
    )
    missing_availability = tuple(
        limitation_id
        for limitation_id in runtime.availability.limitation_ids
        if limitation_id not in limitation_ids
    )
    if missing_health or missing_availability:
        reasons.append(
            _reason(
                RuntimeValidationReasonCode.LIMITATION_REFERENCE_MISSING,
                "Health or availability references an unknown Runtime limitation.",
                (*missing_health, *missing_availability),
            )
        )
    health = runtime.health
    if health.status is RuntimeHealthStatus.HEALTHY and (
        health.configuration_validity is not RuntimeConfigurationValidity.VALID
        or health.capability_availability
        is not RuntimeDeclaredComponentStatus.AVAILABLE
        or health.resource_policy_availability
        is not RuntimeDeclaredComponentStatus.AVAILABLE
        or health.collection_plan_validity
        is not RuntimeDeclaredComponentStatus.AVAILABLE
    ):
        reasons.append(
            _reason(
                RuntimeValidationReasonCode.HEALTH_DECLARATION_INCONSISTENT,
                "Healthy status requires valid and available declared components.",
                (health.id,),
            )
        )
    if (
        health.status is RuntimeHealthStatus.UNHEALTHY
        and runtime.availability.status
        in (RuntimeAvailabilityStatus.AVAILABLE, RuntimeAvailabilityStatus.LIMITED)
    ):
        reasons.append(
            _reason(
                RuntimeValidationReasonCode.AVAILABILITY_DECLARATION_INCONSISTENT,
                "An unhealthy Runtime cannot declare available StageFlow work.",
                (health.id, runtime.availability.id),
            )
        )
    if (
        runtime.event_mode.mode is RuntimeEventModeKind.EVENT
        and not runtime.availability.event_mode_compatible
    ):
        reasons.append(
            _reason(
                RuntimeValidationReasonCode.AVAILABILITY_DECLARATION_INCONSISTENT,
                "Event-mode Runtime must declare event-mode-compatible availability.",
                (runtime.availability.id,),
            )
        )
    return tuple(reasons)


def _capability_available(capability: RuntimeCapability) -> bool:
    return capability.support_status in (
        RuntimeCapabilitySupportStatus.SUPPORTED,
        RuntimeCapabilitySupportStatus.DEGRADED,
    )


def _has_non_blocking_limitations(
    runtime: StageFlowRuntime,
    reasons: Sequence[RuntimeValidationReason],
) -> bool:
    if any(
        limitation.severity is not RuntimeLimitationSeverity.BLOCKING
        for limitation in runtime.limitations
    ):
        return True
    if any(
        capability.support_status is RuntimeCapabilitySupportStatus.DEGRADED
        for capability in runtime.capability_set.capabilities
    ):
        return True
    if any(reason.code in _LIMITATION_REASON_CODES for reason in reasons):
        return True
    return any(
        values
        for values in (
            runtime.capability_set.limitations,
            runtime.event_mode.limitations,
            runtime.resource_policy.limitations,
        )
    )


def _reason(
    code: RuntimeValidationReasonCode,
    message: str,
    related_ids: Sequence[EntityId] = (),
) -> RuntimeValidationReason:
    return RuntimeValidationReason(code=code, message=message, related_ids=related_ids)


def _normalize_reasons(
    reasons: Sequence[RuntimeValidationReason],
) -> tuple[RuntimeValidationReason, ...]:
    by_key: dict[tuple[int, str, str, tuple[str, ...]], RuntimeValidationReason] = {}
    for reason in reasons:
        key = (
            _REASON_ORDER[reason.code],
            reason.code.value,
            reason.message,
            tuple(value.value for value in reason.related_ids),
        )
        by_key[key] = reason
    return tuple(by_key[key] for key in sorted(by_key))


_LIMITATION_REASON_CODES = frozenset(
    {
        RuntimeValidationReasonCode.NON_AUTHORITATIVE_CONTEXT_HINT,
        RuntimeValidationReasonCode.OPTIONAL_CAPABILITY_UNAVAILABLE,
        RuntimeValidationReasonCode.NON_BLOCKING_LIMITATION,
    }
)

_INVALID_REASON_CODES = frozenset(
    set(RuntimeValidationReasonCode)
    - _LIMITATION_REASON_CODES
    - {
        RuntimeValidationReasonCode.UNKNOWN_RUNTIME_PROFILE,
        RuntimeValidationReasonCode.CONFIGURATION_VALID,
        RuntimeValidationReasonCode.UNKNOWN_VALIDATION_CONDITION,
    }
)
