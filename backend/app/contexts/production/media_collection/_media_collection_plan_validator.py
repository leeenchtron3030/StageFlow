from __future__ import annotations

import logging

from app.contexts.production.runtime import (
    RuntimeCapabilityKind,
    RuntimeCapabilitySupportStatus,
    RuntimeConfigurationValidity,
    RuntimeObservationCapability,
    RuntimeProfile,
    StageFlowRuntime,
    validate_runtime,
)
from app.contexts.production.software_agent_runtime import (
    AgentRuntimeExecutionPermission,
    AgentRuntimeLifecycleState,
    AgentRuntimeSnapshot,
)

from ._media_collection_ports import MediaCollectionPortGateway
from ._media_collection_state import OBSERVATION_ORDER, PlanContext
from .media_collection_contracts import MediaCollectionCycleRequest
from .media_collection_dependencies import MediaCollectionDependencies
from .media_collection_lifecycle import (
    MediaCollectionCycleOutcome,
    MediaCollectionCycleReasonCode,
)

_logger = logging.getLogger(__name__)


class MediaCollectionPlanValidator:
    """Validate runtime plans and process-local execution permission checkpoints."""

    def __init__(
        self,
        *,
        runtime: StageFlowRuntime,
        dependencies: MediaCollectionDependencies,
        ports: MediaCollectionPortGateway,
        allow_development_profile: bool,
    ) -> None:
        self._runtime = runtime
        self._dependencies = dependencies
        self._ports = ports
        self._allow_development_profile = allow_development_profile

    def validate_plan(
        self,
        request: MediaCollectionCycleRequest,
    ) -> tuple[
        PlanContext | None,
        MediaCollectionCycleOutcome,
        tuple[MediaCollectionCycleReasonCode, ...],
    ]:
        runtime = self._runtime
        configuration = runtime.configuration
        if request.runtime_id != runtime.identity.runtime_id:
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_RUNTIME,
                (MediaCollectionCycleReasonCode.RUNTIME_ID_MISMATCH,),
            )
        if request.configuration_id != configuration.id:
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_CONFIGURATION,
                (MediaCollectionCycleReasonCode.CONFIGURATION_ID_MISMATCH,),
            )
        if runtime.profile not in (RuntimeProfile.AGENT, RuntimeProfile.DEVELOPMENT):
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_RUNTIME,
                (MediaCollectionCycleReasonCode.RUNTIME_VALIDATION_FAILED,),
            )
        if runtime.profile is RuntimeProfile.DEVELOPMENT and not self._allow_development_profile:
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_RUNTIME,
                (MediaCollectionCycleReasonCode.RUNTIME_VALIDATION_FAILED,),
            )
        validation = validate_runtime(runtime)
        if validation.outcome not in (
            RuntimeConfigurationValidity.VALID,
            RuntimeConfigurationValidity.VALID_WITH_LIMITATIONS,
        ):
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_CONFIGURATION,
                (MediaCollectionCycleReasonCode.RUNTIME_VALIDATION_FAILED,),
            )
        if (
            runtime.capability_set != configuration.capability_set
            or runtime.resource_policy != configuration.resource_policy
            or runtime.event_mode != configuration.event_mode
            or runtime.collection_plans != configuration.collection_plans
            or runtime.readiness_policy_selections
            != configuration.readiness_policy_selections
            or runtime.asset_assembly_plans != configuration.asset_assembly_plans
        ):
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_CONFIGURATION,
                (MediaCollectionCycleReasonCode.RUNTIME_VALIDATION_FAILED,),
            )
        plan = next(
            (
                plan
                for plan in configuration.collection_plans
                if plan.id == request.collection_plan_id
            ),
            None,
        )
        if plan is None:
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_PLAN,
                (MediaCollectionCycleReasonCode.COLLECTION_PLAN_MISSING,),
            )
        if not plan.enabled:
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_PLAN,
                (MediaCollectionCycleReasonCode.COLLECTION_PLAN_DISABLED,),
            )
        selection = next(
            (
                value
                for value in configuration.readiness_policy_selections
                if value.id == plan.readiness_policy_selection_id
            ),
            None,
        )
        if selection is None:
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_PLAN,
                (MediaCollectionCycleReasonCode.READINESS_SELECTION_MISMATCH,),
            )
        discovery_capability = next(
            (
                capability
                for capability in configuration.capability_set.capabilities
                if capability.kind is RuntimeCapabilityKind.CANDIDATE_DISCOVERY
                and capability.support_status
                in (
                    RuntimeCapabilitySupportStatus.SUPPORTED,
                    RuntimeCapabilitySupportStatus.DEGRADED,
                )
            ),
            None,
        )
        if discovery_capability is None:
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_PLAN,
                (MediaCollectionCycleReasonCode.CAPABILITY_MISSING,),
            )
        observation_by_id = {
            capability.id: capability
            for capability in configuration.capability_set.observation_capabilities
        }
        selected: list[RuntimeObservationCapability] = []
        for capability_id in plan.observation_capability_ids:
            capability = observation_by_id.get(capability_id)
            if capability is None:
                return (
                    None,
                    MediaCollectionCycleOutcome.INVALID_PLAN,
                    (MediaCollectionCycleReasonCode.CAPABILITY_MISSING,),
                )
            selected.append(capability)
        target_types = {
            item for target in plan.targets for item in target.enabled_observation_types
        }
        if any(capability.observation_type not in target_types for capability in selected):
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_PLAN,
                (MediaCollectionCycleReasonCode.COLLECTION_TARGET_INVALID,),
            )
        source_ids = {
            source.id for source in configuration.capability_set.source_capabilities
        }
        if any(target.source_capability_id not in source_ids for target in plan.targets):
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_PLAN,
                (MediaCollectionCycleReasonCode.COLLECTION_TARGET_INVALID,),
            )
        if (
            plan.resource_policy_id != configuration.resource_policy.id
            or plan.event_mode_id != configuration.event_mode.id
        ):
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_PLAN,
                (MediaCollectionCycleReasonCode.EVENT_MODE_INCOMPATIBLE,),
            )
        required_ids = frozenset(
            capability.id
            for capability in selected
            if capability.runtime_capability_id in selection.required_capability_ids
        )
        if self._missing_ports(selected):
            return (
                None,
                MediaCollectionCycleOutcome.INVALID_DEPENDENCY,
                (MediaCollectionCycleReasonCode.REQUIRED_PORT_MISSING,),
            )
        return (
            PlanContext(
                plan=plan,
                selection=selection,
                discovery_capability_id=discovery_capability.id,
                observation_capabilities=tuple(
                    sorted(
                        selected,
                        key=lambda value: (
                            value.id not in required_ids,
                            OBSERVATION_ORDER[value.observation_type],
                            value.id.value,
                        ),
                    )
                ),
                required_observation_capability_ids=required_ids,
            ),
            MediaCollectionCycleOutcome.COMPLETED,
            (MediaCollectionCycleReasonCode.RUNTIME_VALIDATION_PASSED,),
        )

    def _missing_ports(
        self,
        capabilities: tuple[RuntimeObservationCapability, ...]
        | list[RuntimeObservationCapability],
    ) -> tuple[str, ...]:
        missing: list[str] = []
        if self._dependencies.agent_execution_state_port is None:
            missing.append("agent_execution_state_port")
        if self._dependencies.media_candidate_discovery_port is None:
            missing.append("media_candidate_discovery_port")
        for capability in capabilities:
            if self._ports.observation_port(capability.observation_type) is None:
                missing.append(capability.observation_type.value)
        return tuple(sorted(set(missing)))

    def read_agent_snapshot(
        self,
        request: MediaCollectionCycleRequest,
    ) -> AgentRuntimeSnapshot | None:
        port = self._dependencies.agent_execution_state_port
        if port is None:
            return None
        try:
            return port.get_current_snapshot(request.runtime_id)
        except Exception as error:
            _logger.error(
                (
                    "media_collection_agent_snapshot_failed cycle_id=%s "
                    "runtime_id=%s exception_type=%s"
                ),
                request.cycle_id.value,
                request.runtime_id.value,
                type(error).__name__,
            )
            return None

    def permission(
        self,
        snapshot: AgentRuntimeSnapshot,
        request: MediaCollectionCycleRequest,
    ) -> tuple[bool, tuple[MediaCollectionCycleReasonCode, ...]]:
        if snapshot.runtime_id != request.runtime_id:
            return False, (MediaCollectionCycleReasonCode.RUNTIME_ID_MISMATCH,)
        if snapshot.configuration_id != request.configuration_id:
            return False, (MediaCollectionCycleReasonCode.CONFIGURATION_ID_MISMATCH,)
        if snapshot.deployment_profile != self._runtime.profile:
            return False, (MediaCollectionCycleReasonCode.RUNTIME_ID_MISMATCH,)
        if snapshot.cancellation is not None:
            return False, (MediaCollectionCycleReasonCode.AGENT_CANCELLED,)
        if snapshot.lifecycle_state is AgentRuntimeLifecycleState.RUNNING:
            if snapshot.execution_permission is AgentRuntimeExecutionPermission.NORMAL:
                return True, (MediaCollectionCycleReasonCode.AGENT_RUNNING_NORMAL,)
        elif snapshot.lifecycle_state is AgentRuntimeLifecycleState.YIELDING:
            if snapshot.execution_permission is AgentRuntimeExecutionPermission.REDUCED:
                if request.permit_reduced_execution:
                    return True, (MediaCollectionCycleReasonCode.AGENT_YIELDING_REDUCED,)
                return False, (MediaCollectionCycleReasonCode.AGENT_PERMISSION_ABSENT,)
        elif snapshot.lifecycle_state is AgentRuntimeLifecycleState.STOPPING:
            return False, (MediaCollectionCycleReasonCode.AGENT_STOPPING,)
        elif snapshot.lifecycle_state is AgentRuntimeLifecycleState.STOPPED:
            return False, (MediaCollectionCycleReasonCode.AGENT_STOPPED,)
        elif snapshot.lifecycle_state is AgentRuntimeLifecycleState.FAILED:
            return False, (MediaCollectionCycleReasonCode.AGENT_FAILED,)
        elif snapshot.lifecycle_state is AgentRuntimeLifecycleState.DISABLED:
            return False, (MediaCollectionCycleReasonCode.AGENT_DISABLED,)
        if snapshot.execution_permission is AgentRuntimeExecutionPermission.ESSENTIAL_ONLY:
            return False, (MediaCollectionCycleReasonCode.ESSENTIAL_ONLY_UNDEFINED,)
        return False, (MediaCollectionCycleReasonCode.AGENT_PERMISSION_ABSENT,)

    def identity_or_permission_outcome(
        self,
        snapshot: AgentRuntimeSnapshot,
    ) -> MediaCollectionCycleOutcome:
        if (
            snapshot.runtime_id != self._runtime.identity.runtime_id
            or snapshot.configuration_id != self._runtime.configuration.id
            or snapshot.deployment_profile != self._runtime.profile
        ):
            return MediaCollectionCycleOutcome.INVALID_RUNTIME
        return MediaCollectionCycleOutcome.PERMISSION_DENIED

    def checkpoint(
        self,
        request: MediaCollectionCycleRequest,
    ) -> tuple[AgentRuntimeSnapshot | None, bool]:
        snapshot = self.read_agent_snapshot(request)
        if snapshot is None:
            return None, False
        permitted, _ = self.permission(snapshot, request)
        return snapshot, permitted

    def interruption_reasons(
        self,
        snapshot: AgentRuntimeSnapshot | None,
        request: MediaCollectionCycleRequest,
    ) -> tuple[MediaCollectionCycleReasonCode, ...]:
        permission_reasons = (
            () if snapshot is None else self.permission(snapshot, request)[1]
        )
        return (
            *permission_reasons,
            MediaCollectionCycleReasonCode.AGENT_LIFECYCLE_CHANGED,
            MediaCollectionCycleReasonCode.CYCLE_INTERRUPTED,
        )


__all__ = ["MediaCollectionPlanValidator"]
