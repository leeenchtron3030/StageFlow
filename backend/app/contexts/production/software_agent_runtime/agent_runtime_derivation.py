from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID, uuid5

from app.contexts.production.runtime import (
    RuntimeAvailability,
    RuntimeAvailabilityStatus,
    RuntimeConfigurationValidity,
    RuntimeDeclaredComponentStatus,
    RuntimeHealth,
    RuntimeHealthStatus,
    RuntimeValidationOutcome,
    RuntimeValidationResult,
    StageFlowRuntime,
)
from app.shared.ids import EntityId

from .agent_runtime_lifecycle import (
    AgentRuntimeLifecycleState,
    AgentRuntimeTransitionReasonCode,
)


def deterministic_agent_id(namespace_id: EntityId, token: str) -> EntityId:
    return EntityId(str(uuid5(UUID(namespace_id.value), token)))


def derive_health(
    runtime: StageFlowRuntime,
    agent_instance_id: EntityId,
    state: AgentRuntimeLifecycleState,
    revision: int,
    assessed_at: datetime,
    validation: RuntimeValidationResult | None,
    reasons: Sequence[AgentRuntimeTransitionReasonCode],
    previous: RuntimeHealth | None = None,
) -> RuntimeHealth:
    declaration_id = deterministic_agent_id(
        agent_instance_id,
        f"health:{revision}:{state.value}",
    )
    if state is AgentRuntimeLifecycleState.CREATED:
        status = RuntimeHealthStatus.UNKNOWN
        validity = RuntimeConfigurationValidity.UNKNOWN
        component = RuntimeDeclaredComponentStatus.UNKNOWN
        resource = RuntimeDeclaredComponentStatus.UNKNOWN
        collection = RuntimeDeclaredComponentStatus.UNKNOWN
    elif state is AgentRuntimeLifecycleState.FAILED:
        status = RuntimeHealthStatus.UNHEALTHY
        validity = _validation_validity(validation)
        component = RuntimeDeclaredComponentStatus.UNAVAILABLE
        resource = RuntimeDeclaredComponentStatus.UNAVAILABLE
        collection = RuntimeDeclaredComponentStatus.UNAVAILABLE
    elif state in (
        AgentRuntimeLifecycleState.YIELDING,
        AgentRuntimeLifecycleState.SUSPENDED,
    ):
        status = RuntimeHealthStatus.DEGRADED
        validity = _validation_validity(validation)
        component = _component_status(validation)
        resource = RuntimeDeclaredComponentStatus.DEGRADED
        collection = (
            RuntimeDeclaredComponentStatus.DEGRADED
            if state is AgentRuntimeLifecycleState.YIELDING
            else RuntimeDeclaredComponentStatus.UNAVAILABLE
        )
    elif (
        state
        in (
            AgentRuntimeLifecycleState.STOPPING,
            AgentRuntimeLifecycleState.STOPPED,
        )
        and previous is not None
    ):
        status = previous.status
        validity = previous.configuration_validity
        component = previous.capability_availability
        resource = previous.resource_policy_availability
        collection = previous.collection_plan_validity
    else:
        validity = _validation_validity(validation)
        component = _component_status(validation)
        resource = component
        collection = component
        status = (
            RuntimeHealthStatus.HEALTHY
            if validity is RuntimeConfigurationValidity.VALID
            else RuntimeHealthStatus.DEGRADED
        )
    return RuntimeHealth(
        id=declaration_id,
        runtime_id=runtime.configuration.runtime_id,
        status=status,
        assessed_at=assessed_at,
        configuration_validity=validity,
        capability_availability=component,
        resource_policy_availability=resource,
        collection_plan_validity=collection,
        limitation_ids=tuple(value.id for value in runtime.limitations),
        reason_codes=tuple(reason.value for reason in reasons),
    )


def derive_availability(
    runtime: StageFlowRuntime,
    agent_instance_id: EntityId,
    state: AgentRuntimeLifecycleState,
    revision: int,
    declared_at: datetime,
    validation: RuntimeValidationResult | None,
    reasons: Sequence[AgentRuntimeTransitionReasonCode],
) -> RuntimeAvailability:
    declaration_id = deterministic_agent_id(
        agent_instance_id,
        f"availability:{revision}:{state.value}",
    )
    status = {
        AgentRuntimeLifecycleState.CREATED: RuntimeAvailabilityStatus.UNAVAILABLE,
        AgentRuntimeLifecycleState.VALIDATED: RuntimeAvailabilityStatus.UNAVAILABLE,
        AgentRuntimeLifecycleState.READY: RuntimeAvailabilityStatus.AVAILABLE,
        AgentRuntimeLifecycleState.RUNNING: RuntimeAvailabilityStatus.AVAILABLE,
        AgentRuntimeLifecycleState.YIELDING: RuntimeAvailabilityStatus.LIMITED,
        AgentRuntimeLifecycleState.SUSPENDED: RuntimeAvailabilityStatus.UNAVAILABLE,
        AgentRuntimeLifecycleState.STOPPING: RuntimeAvailabilityStatus.UNAVAILABLE,
        AgentRuntimeLifecycleState.STOPPED: RuntimeAvailabilityStatus.UNAVAILABLE,
        AgentRuntimeLifecycleState.FAILED: RuntimeAvailabilityStatus.UNAVAILABLE,
        AgentRuntimeLifecycleState.DISABLED: RuntimeAvailabilityStatus.DISABLED,
    }[state]
    return RuntimeAvailability(
        id=declaration_id,
        runtime_id=runtime.configuration.runtime_id,
        status=status,
        declared_at=declared_at,
        reason_codes=tuple(reason.value for reason in reasons),
        expected_capability_availability=_component_status(validation),
        event_mode_compatible=runtime.availability.event_mode_compatible,
        limitation_ids=tuple(value.id for value in runtime.limitations),
        limitations=tuple(value.description for value in runtime.limitations),
    )


def _validation_validity(
    validation: RuntimeValidationResult | None,
) -> RuntimeConfigurationValidity:
    if validation is None:
        return RuntimeConfigurationValidity.UNKNOWN
    return RuntimeConfigurationValidity(validation.outcome.value)


def _component_status(
    validation: RuntimeValidationResult | None,
) -> RuntimeDeclaredComponentStatus:
    if validation is None or validation.outcome is RuntimeValidationOutcome.UNKNOWN:
        return RuntimeDeclaredComponentStatus.UNKNOWN
    if validation.outcome is RuntimeValidationOutcome.VALID:
        return RuntimeDeclaredComponentStatus.AVAILABLE
    if validation.outcome is RuntimeValidationOutcome.VALID_WITH_LIMITATIONS:
        return RuntimeDeclaredComponentStatus.DEGRADED
    return RuntimeDeclaredComponentStatus.UNAVAILABLE


__all__ = [
    "derive_availability",
    "derive_health",
    "deterministic_agent_id",
]
