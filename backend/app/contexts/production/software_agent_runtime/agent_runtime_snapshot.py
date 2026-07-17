from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.contexts.production.runtime import (
    RuntimeAvailability,
    RuntimeAvailabilityStatus,
    RuntimeEventModeKind,
    RuntimeHealth,
    RuntimeHealthStatus,
    RuntimeLimitation,
    RuntimeLimitationSeverity,
    RuntimePressureState,
    RuntimeProfile,
    RuntimeValidationResult,
)
from app.shared.ids import EntityId

from .agent_runtime_contract_validation import (
    freeze_runtime_metadata,
    normalize_entity_ids,
    normalize_ordered_entity_ids,
    normalize_strings,
    require_aware,
    require_non_empty,
    require_non_negative_revision,
)
from .agent_runtime_lifecycle import (
    AgentRuntimeExecutionPermission,
    AgentRuntimeLifecycleState,
    AgentRuntimeNotificationPortKind,
    AgentRuntimeOperationOutcome,
    AgentRuntimeTransitionReasonCode,
    normalize_reason_codes,
)
from .agent_runtime_requests import (
    AgentRuntimeCancellation,
    AgentRuntimeFailure,
    AgentRuntimePressureDeclaration,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class AgentRuntimeSnapshot:
    agent_instance_id: EntityId
    runtime_id: EntityId
    configuration_id: EntityId
    deployment_profile: RuntimeProfile
    lifecycle_state: AgentRuntimeLifecycleState
    previous_lifecycle_state: AgentRuntimeLifecycleState | None
    state_entered_at: datetime
    lifecycle_revision: int
    latest_operation_id: EntityId | None
    latest_transition_id: EntityId | None
    latest_pressure: AgentRuntimePressureDeclaration | None
    execution_permission: AgentRuntimeExecutionPermission
    health: RuntimeHealth
    availability: RuntimeAvailability
    cancellation: AgentRuntimeCancellation | None
    active_limitations: Sequence[RuntimeLimitation]
    failure: AgentRuntimeFailure | None
    transition_lineage_ids: Sequence[EntityId]
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware(
            self.state_entered_at,
            "AgentRuntimeSnapshot.state_entered_at",
        )
        require_non_negative_revision(
            self.lifecycle_revision,
            "AgentRuntimeSnapshot.lifecycle_revision",
        )
        object.__setattr__(
            self,
            "active_limitations",
            tuple(
                sorted(
                    self.active_limitations,
                    key=lambda limitation: limitation.id.value,
                )
            ),
        )
        object.__setattr__(
            self,
            "transition_lineage_ids",
            normalize_ordered_entity_ids(
                self.transition_lineage_ids,
                "AgentRuntimeSnapshot.transition_lineage_ids",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(
                self.metadata,
                "AgentRuntimeSnapshot.metadata",
            ),
        )


@dataclass(frozen=True, slots=True)
class AgentRuntimeTransition:
    id: EntityId
    operation_id: EntityId
    runtime_id: EntityId
    configuration_id: EntityId
    lifecycle_revision: int
    previous_state: AgentRuntimeLifecycleState
    next_state: AgentRuntimeLifecycleState
    reason_codes: Sequence[AgentRuntimeTransitionReasonCode]
    pressure_state: RuntimePressureState | None
    execution_permission_before: AgentRuntimeExecutionPermission
    execution_permission_after: AgentRuntimeExecutionPermission
    occurred_at: datetime
    health_declaration_id: EntityId
    availability_declaration_id: EntityId
    limitation_ids: Sequence[EntityId] = field(default_factory=tuple)
    failure_id: EntityId | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if self.lifecycle_revision <= 0:
            raise ValueError("Agent Runtime transition revision must be positive.")
        require_aware(self.occurred_at, "AgentRuntimeTransition.occurred_at")
        reasons = normalize_reason_codes(self.reason_codes)
        if not reasons:
            raise ValueError("Agent Runtime transition requires a reason code.")
        object.__setattr__(self, "reason_codes", reasons)
        object.__setattr__(
            self,
            "limitation_ids",
            normalize_entity_ids(
                self.limitation_ids,
                "AgentRuntimeTransition.limitation_ids",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(
                self.metadata,
                "AgentRuntimeTransition.metadata",
            ),
        )


@dataclass(frozen=True, slots=True)
class AgentRuntimeNotificationFailure:
    port_kind: AgentRuntimeNotificationPortKind
    operation_id: EntityId
    transition_id: EntityId
    failure_code: str
    lifecycle_transition_committed: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "failure_code",
            require_non_empty(
                self.failure_code,
                "AgentRuntimeNotificationFailure.failure_code",
            ),
        )


_NON_MUTATING_OUTCOMES = {
    AgentRuntimeOperationOutcome.REJECTED,
    AgentRuntimeOperationOutcome.STALE_REVISION,
    AgentRuntimeOperationOutcome.OPERATION_CONFLICT,
    AgentRuntimeOperationOutcome.INVALID_RUNTIME,
    AgentRuntimeOperationOutcome.INVALID_CONFIGURATION,
    AgentRuntimeOperationOutcome.INVALID_TRANSITION,
    AgentRuntimeOperationOutcome.DEPENDENCY_FAILURE,
    AgentRuntimeOperationOutcome.UNKNOWN,
}


@dataclass(frozen=True, slots=True)
class AgentRuntimeOperationResult:
    operation_id: EntityId
    runtime_id: EntityId
    outcome: AgentRuntimeOperationOutcome
    reasons: Sequence[AgentRuntimeTransitionReasonCode]
    previous_snapshot: AgentRuntimeSnapshot
    current_snapshot: AgentRuntimeSnapshot
    transitions: Sequence[AgentRuntimeTransition]
    validation_result: RuntimeValidationResult | None
    publication_failures: Sequence[AgentRuntimeNotificationFailure]
    occurred_at: datetime
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware(
            self.occurred_at,
            "AgentRuntimeOperationResult.occurred_at",
        )
        reasons = normalize_reason_codes(self.reasons)
        if not reasons:
            raise ValueError("Agent Runtime operation result requires a reason.")
        object.__setattr__(self, "reasons", reasons)
        object.__setattr__(self, "transitions", tuple(self.transitions))
        object.__setattr__(
            self,
            "publication_failures",
            tuple(self.publication_failures),
        )
        if (
            self.outcome in _NON_MUTATING_OUTCOMES
            and self.previous_snapshot != self.current_snapshot
        ):
            raise ValueError("Rejected Agent operation must not mutate its snapshot.")
        if self.outcome in _NON_MUTATING_OUTCOMES and self.transitions:
            raise ValueError("Rejected Agent operation must not create transitions.")
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(
                self.metadata,
                "AgentRuntimeOperationResult.metadata",
            ),
        )

    @property
    def transition(self) -> AgentRuntimeTransition | None:
        return None if not self.transitions else self.transitions[-1]


@dataclass(frozen=True, slots=True)
class AgentRuntimeSummary:
    agent_instance_id: EntityId
    runtime_id: EntityId
    configuration_id: EntityId
    runtime_profile: RuntimeProfile
    lifecycle_state: AgentRuntimeLifecycleState
    lifecycle_revision: int
    execution_permission: AgentRuntimeExecutionPermission
    event_mode: RuntimeEventModeKind
    latest_pressure_state: RuntimePressureState | None
    health_status: RuntimeHealthStatus
    availability_status: RuntimeAvailabilityStatus
    active_limitation_count: int
    blocking_limitation_count: int
    cancellation_active: bool
    transition_count: int
    failure_code: str | None
    warning_codes: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        require_non_negative_revision(
            self.lifecycle_revision,
            "AgentRuntimeSummary.lifecycle_revision",
        )
        object.__setattr__(
            self,
            "warning_codes",
            normalize_strings(
                self.warning_codes,
                "AgentRuntimeSummary.warning_codes",
            ),
        )

    @classmethod
    def from_snapshot(
        cls,
        snapshot: AgentRuntimeSnapshot,
        event_mode: RuntimeEventModeKind,
        transition_count: int,
    ) -> AgentRuntimeSummary:
        warnings = tuple(
            limitation.code
            for limitation in snapshot.active_limitations
            if limitation.severity is not RuntimeLimitationSeverity.INFORMATIONAL
        )
        return cls(
            agent_instance_id=snapshot.agent_instance_id,
            runtime_id=snapshot.runtime_id,
            configuration_id=snapshot.configuration_id,
            runtime_profile=snapshot.deployment_profile,
            lifecycle_state=snapshot.lifecycle_state,
            lifecycle_revision=snapshot.lifecycle_revision,
            execution_permission=snapshot.execution_permission,
            event_mode=event_mode,
            latest_pressure_state=(
                None
                if snapshot.latest_pressure is None
                else snapshot.latest_pressure.pressure_state
            ),
            health_status=snapshot.health.status,
            availability_status=snapshot.availability.status,
            active_limitation_count=len(snapshot.active_limitations),
            blocking_limitation_count=sum(
                limitation.severity is RuntimeLimitationSeverity.BLOCKING
                for limitation in snapshot.active_limitations
            ),
            cancellation_active=snapshot.cancellation is not None,
            transition_count=transition_count,
            failure_code=(None if snapshot.failure is None else snapshot.failure.failure_code),
            warning_codes=warnings,
        )


__all__ = [
    "AgentRuntimeNotificationFailure",
    "AgentRuntimeOperationResult",
    "AgentRuntimeSnapshot",
    "AgentRuntimeSummary",
    "AgentRuntimeTransition",
]
