from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from threading import Condition, RLock
from types import MappingProxyType

from app.contexts.production.runtime import (
    RuntimeAvailabilityStatus,
    RuntimeConfiguration,
    RuntimeEventModeKind,
    RuntimePressureState,
    RuntimeProfile,
    RuntimeValidationOutcome,
    RuntimeValidationResult,
    StageFlowRuntime,
    validate_runtime,
)
from app.shared.ids import EntityId

from .agent_runtime_contract_validation import canonical_value
from .agent_runtime_dependencies import AgentRuntimeDependencies
from .agent_runtime_derivation import (
    derive_availability,
    derive_health,
    deterministic_agent_id,
)
from .agent_runtime_lifecycle import (
    AgentRuntimeLifecycleState,
    AgentRuntimeNotificationPortKind,
    AgentRuntimeOperation,
    AgentRuntimeOperationOutcome,
    AgentRuntimeTransitionReasonCode,
    normalize_reason_codes,
    permission_for_state,
)
from .agent_runtime_requests import (
    AgentRuntimeCancellation,
    AgentRuntimeFailure,
    AgentRuntimePrepareRequest,
    AgentRuntimePressureDeclaration,
    AgentRuntimePressureUpdate,
    AgentRuntimeResumeRequest,
    AgentRuntimeStartRequest,
    AgentRuntimeStopRequest,
)
from .agent_runtime_snapshot import (
    AgentRuntimeNotificationFailure,
    AgentRuntimeOperationResult,
    AgentRuntimeSnapshot,
    AgentRuntimeSummary,
    AgentRuntimeTransition,
)


@dataclass(frozen=True, slots=True)
class _OperationRecord:
    fingerprint: str
    result: AgentRuntimeOperationResult
    notification_pending: bool


@dataclass(frozen=True, slots=True)
class _AgentRuntimeState:
    snapshot: AgentRuntimeSnapshot
    transitions: tuple[AgentRuntimeTransition, ...]
    operation_records: Mapping[str, _OperationRecord]
    cancellation_fingerprints: Mapping[str, str]
    validation_result: RuntimeValidationResult | None


@dataclass(frozen=True, slots=True)
class _TransitionSpec:
    next_state: AgentRuntimeLifecycleState
    reasons: tuple[AgentRuntimeTransitionReasonCode, ...]
    pressure: AgentRuntimePressureDeclaration | None = None
    cancellation: AgentRuntimeCancellation | None = None
    failure: AgentRuntimeFailure | None = None
    allow_same_state: bool = False


@dataclass(frozen=True, slots=True)
class _AppliedStep:
    snapshot: AgentRuntimeSnapshot
    transition: AgentRuntimeTransition


@dataclass(frozen=True, slots=True)
class _PendingPublication:
    fingerprint: str
    result: AgentRuntimeOperationResult
    steps: tuple[_AppliedStep, ...]


_ALLOWED_TRANSITIONS = frozenset(
    {
        (AgentRuntimeLifecycleState.CREATED, AgentRuntimeLifecycleState.VALIDATED),
        (AgentRuntimeLifecycleState.CREATED, AgentRuntimeLifecycleState.DISABLED),
        (AgentRuntimeLifecycleState.CREATED, AgentRuntimeLifecycleState.FAILED),
        (AgentRuntimeLifecycleState.CREATED, AgentRuntimeLifecycleState.STOPPED),
        (AgentRuntimeLifecycleState.VALIDATED, AgentRuntimeLifecycleState.READY),
        (AgentRuntimeLifecycleState.VALIDATED, AgentRuntimeLifecycleState.FAILED),
        (AgentRuntimeLifecycleState.VALIDATED, AgentRuntimeLifecycleState.STOPPING),
        (AgentRuntimeLifecycleState.READY, AgentRuntimeLifecycleState.RUNNING),
        (AgentRuntimeLifecycleState.READY, AgentRuntimeLifecycleState.YIELDING),
        (AgentRuntimeLifecycleState.READY, AgentRuntimeLifecycleState.SUSPENDED),
        (AgentRuntimeLifecycleState.READY, AgentRuntimeLifecycleState.STOPPING),
        (AgentRuntimeLifecycleState.RUNNING, AgentRuntimeLifecycleState.YIELDING),
        (AgentRuntimeLifecycleState.RUNNING, AgentRuntimeLifecycleState.SUSPENDED),
        (AgentRuntimeLifecycleState.RUNNING, AgentRuntimeLifecycleState.STOPPING),
        (AgentRuntimeLifecycleState.YIELDING, AgentRuntimeLifecycleState.RUNNING),
        (AgentRuntimeLifecycleState.YIELDING, AgentRuntimeLifecycleState.SUSPENDED),
        (AgentRuntimeLifecycleState.YIELDING, AgentRuntimeLifecycleState.STOPPING),
        (AgentRuntimeLifecycleState.SUSPENDED, AgentRuntimeLifecycleState.RUNNING),
        (AgentRuntimeLifecycleState.SUSPENDED, AgentRuntimeLifecycleState.YIELDING),
        (AgentRuntimeLifecycleState.SUSPENDED, AgentRuntimeLifecycleState.STOPPING),
        (AgentRuntimeLifecycleState.FAILED, AgentRuntimeLifecycleState.STOPPING),
        (AgentRuntimeLifecycleState.STOPPING, AgentRuntimeLifecycleState.STOPPED),
        (AgentRuntimeLifecycleState.DISABLED, AgentRuntimeLifecycleState.STOPPING),
    }
)


class SoftwareAgentRuntime:
    """One synchronous process-local lifecycle for an ED-0050 Agent Runtime."""

    def __init__(
        self,
        runtime: StageFlowRuntime,
        dependencies: AgentRuntimeDependencies,
        *,
        agent_instance_id: EntityId,
        created_at: datetime,
    ) -> None:
        self._runtime = runtime
        self._dependencies = dependencies
        self._lock = RLock()
        self._publication_condition = Condition(self._lock)
        initial_reasons = (AgentRuntimeTransitionReasonCode.AGENT_CREATED,)
        initial_health = derive_health(
            runtime,
            agent_instance_id,
            AgentRuntimeLifecycleState.CREATED,
            0,
            created_at,
            None,
            initial_reasons,
        )
        initial_availability = derive_availability(
            runtime,
            agent_instance_id,
            AgentRuntimeLifecycleState.CREATED,
            0,
            created_at,
            None,
            initial_reasons,
        )
        snapshot = AgentRuntimeSnapshot(
            agent_instance_id=agent_instance_id,
            runtime_id=runtime.identity.runtime_id,
            configuration_id=runtime.configuration.id,
            deployment_profile=runtime.profile,
            lifecycle_state=AgentRuntimeLifecycleState.CREATED,
            previous_lifecycle_state=None,
            state_entered_at=created_at,
            lifecycle_revision=0,
            latest_operation_id=None,
            latest_transition_id=None,
            latest_pressure=None,
            execution_permission=permission_for_state(AgentRuntimeLifecycleState.CREATED),
            health=initial_health,
            availability=initial_availability,
            cancellation=None,
            active_limitations=runtime.limitations,
            failure=None,
            transition_lineage_ids=(),
        )
        self._state = _AgentRuntimeState(
            snapshot=snapshot,
            transitions=(),
            operation_records=MappingProxyType({}),
            cancellation_fingerprints=MappingProxyType({}),
            validation_result=None,
        )

    @property
    def runtime(self) -> StageFlowRuntime:
        return self._runtime

    @property
    def execution_configuration(self) -> RuntimeConfiguration:
        return self._runtime.configuration

    @property
    def snapshot(self) -> AgentRuntimeSnapshot:
        with self._lock:
            return self._state.snapshot

    @property
    def transition_history(self) -> tuple[AgentRuntimeTransition, ...]:
        with self._lock:
            return self._state.transitions

    @property
    def validation_result(self) -> RuntimeValidationResult | None:
        with self._lock:
            return self._state.validation_result

    def summary(self) -> AgentRuntimeSummary:
        with self._lock:
            return AgentRuntimeSummary.from_snapshot(
                self._state.snapshot,
                self._runtime.configuration.event_mode.mode,
                len(self._state.transitions),
            )

    def prepare(
        self,
        request: AgentRuntimePrepareRequest,
    ) -> AgentRuntimeOperationResult:
        return self._complete_operation(self._prepare_with_lock(request))

    def _prepare_with_lock(
        self,
        request: AgentRuntimePrepareRequest,
    ) -> AgentRuntimeOperationResult | _PendingPublication:
        operation = AgentRuntimeOperation.PREPARE
        fingerprint = self._fingerprint(operation, request)
        with self._lock:
            replay = self._replay_or_conflict(
                request.operation_id,
                request.runtime_id,
                request.requested_at,
                fingerprint,
            )
            if replay is not None:
                return replay
            rejection = self._common_rejection(
                request.operation_id,
                request.runtime_id,
                request.configuration_id,
                request.expected_lifecycle_revision,
                request.requested_at,
                fingerprint,
            )
            if rejection is not None:
                return rejection
            if self._state.snapshot.lifecycle_state is not (AgentRuntimeLifecycleState.CREATED):
                return self._reject(
                    request.operation_id,
                    request.runtime_id,
                    request.requested_at,
                    fingerprint,
                    AgentRuntimeOperationOutcome.INVALID_TRANSITION,
                    (AgentRuntimeTransitionReasonCode.INVALID_LIFECYCLE_TRANSITION,),
                )
            validation = validate_runtime(self._runtime)
            profile_reason = self._accepted_profile_reason(request.allow_development_profile)
            if profile_reason is None:
                return self._reject(
                    request.operation_id,
                    request.runtime_id,
                    request.requested_at,
                    fingerprint,
                    AgentRuntimeOperationOutcome.INVALID_RUNTIME,
                    (AgentRuntimeTransitionReasonCode.UNSUPPORTED_RUNTIME_PROFILE,),
                    validation,
                )
            if validation.outcome in (
                RuntimeValidationOutcome.INVALID,
                RuntimeValidationOutcome.UNKNOWN,
            ):
                return self._reject(
                    request.operation_id,
                    request.runtime_id,
                    request.requested_at,
                    fingerprint,
                    AgentRuntimeOperationOutcome.INVALID_CONFIGURATION,
                    (AgentRuntimeTransitionReasonCode.RUNTIME_VALIDATION_FAILED,),
                    validation,
                )
            configuration = self._runtime.configuration
            if (
                not configuration.enabled
                or configuration.event_mode.mode is RuntimeEventModeKind.DISABLED
            ):
                reason = (
                    AgentRuntimeTransitionReasonCode.CONFIGURATION_DISABLED
                    if not configuration.enabled
                    else AgentRuntimeTransitionReasonCode.EVENT_MODE_DISABLED
                )
                return self._apply(
                    request.operation_id,
                    request.runtime_id,
                    request.requested_at,
                    fingerprint,
                    (_TransitionSpec(AgentRuntimeLifecycleState.DISABLED, (reason,)),),
                    AgentRuntimeOperationOutcome.DISABLED,
                    validation,
                )
            if self._runtime.availability.status is (RuntimeAvailabilityStatus.UNAVAILABLE):
                return self._reject(
                    request.operation_id,
                    request.runtime_id,
                    request.requested_at,
                    fingerprint,
                    AgentRuntimeOperationOutcome.INVALID_CONFIGURATION,
                    (AgentRuntimeTransitionReasonCode.AVAILABILITY_UNAVAILABLE,),
                    validation,
                )
            if self._dependencies.missing_required_ports:
                return self._reject(
                    request.operation_id,
                    request.runtime_id,
                    request.requested_at,
                    fingerprint,
                    AgentRuntimeOperationOutcome.DEPENDENCY_FAILURE,
                    (AgentRuntimeTransitionReasonCode.REQUIRED_DEPENDENCY_MISSING,),
                    validation,
                )
            return self._apply(
                request.operation_id,
                request.runtime_id,
                request.requested_at,
                fingerprint,
                (
                    _TransitionSpec(
                        AgentRuntimeLifecycleState.VALIDATED,
                        (
                            AgentRuntimeTransitionReasonCode.RUNTIME_VALIDATION_PASSED,
                            profile_reason,
                        ),
                    ),
                    _TransitionSpec(
                        AgentRuntimeLifecycleState.READY,
                        (AgentRuntimeTransitionReasonCode.STARTUP_PREPARED,),
                    ),
                ),
                AgentRuntimeOperationOutcome.APPLIED,
                validation,
            )

    def start(self, request: AgentRuntimeStartRequest) -> AgentRuntimeOperationResult:
        return self._complete_operation(self._start_with_lock(request))

    def _start_with_lock(
        self,
        request: AgentRuntimeStartRequest,
    ) -> AgentRuntimeOperationResult | _PendingPublication:
        operation = AgentRuntimeOperation.START
        fingerprint = self._fingerprint(operation, request)
        with self._lock:
            replay = self._replay_or_conflict(
                request.operation_id,
                request.runtime_id,
                request.requested_at,
                fingerprint,
            )
            if replay is not None:
                return replay
            rejection = self._common_rejection(
                request.operation_id,
                request.runtime_id,
                request.configuration_id,
                request.expected_lifecycle_revision,
                request.requested_at,
                fingerprint,
            )
            if rejection is not None:
                return rejection
            if self._state.snapshot.lifecycle_state is not AgentRuntimeLifecycleState.READY:
                return self._reject(
                    request.operation_id,
                    request.runtime_id,
                    request.requested_at,
                    fingerprint,
                    AgentRuntimeOperationOutcome.INVALID_TRANSITION,
                    (AgentRuntimeTransitionReasonCode.INVALID_LIFECYCLE_TRANSITION,),
                )
            validation = validate_runtime(self._runtime)
            if validation.outcome in (
                RuntimeValidationOutcome.INVALID,
                RuntimeValidationOutcome.UNKNOWN,
            ):
                return self._reject(
                    request.operation_id,
                    request.runtime_id,
                    request.requested_at,
                    fingerprint,
                    AgentRuntimeOperationOutcome.INVALID_CONFIGURATION,
                    (AgentRuntimeTransitionReasonCode.RUNTIME_VALIDATION_FAILED,),
                    validation,
                )
            if self._accepted_profile_reason(request.allow_development_profile) is None:
                return self._reject(
                    request.operation_id,
                    request.runtime_id,
                    request.requested_at,
                    fingerprint,
                    AgentRuntimeOperationOutcome.INVALID_RUNTIME,
                    (AgentRuntimeTransitionReasonCode.UNSUPPORTED_RUNTIME_PROFILE,),
                    validation,
                )
            next_state, reasons = self._initial_pressure_mapping(
                request.initial_pressure.pressure_state
            )
            return self._apply(
                request.operation_id,
                request.runtime_id,
                request.requested_at,
                fingerprint,
                (
                    _TransitionSpec(
                        next_state,
                        reasons,
                        pressure=request.initial_pressure,
                    ),
                ),
                AgentRuntimeOperationOutcome.APPLIED,
                validation,
            )

    def update_pressure(
        self,
        update: AgentRuntimePressureUpdate,
    ) -> AgentRuntimeOperationResult:
        return self._complete_operation(self._update_pressure_with_lock(update))

    def _update_pressure_with_lock(
        self,
        update: AgentRuntimePressureUpdate,
    ) -> AgentRuntimeOperationResult | _PendingPublication:
        operation = AgentRuntimeOperation.PRESSURE_UPDATE
        fingerprint = self._fingerprint(operation, update)
        with self._lock:
            replay = self._replay_or_conflict(
                update.operation_id,
                update.runtime_id,
                update.assessed_at,
                fingerprint,
            )
            if replay is not None:
                return replay
            rejection = self._runtime_revision_rejection(
                update.operation_id,
                update.runtime_id,
                update.expected_lifecycle_revision,
                update.assessed_at,
                fingerprint,
            )
            if rejection is not None:
                return rejection
            current = self._state.snapshot.lifecycle_state
            if current not in (
                AgentRuntimeLifecycleState.RUNNING,
                AgentRuntimeLifecycleState.YIELDING,
                AgentRuntimeLifecycleState.SUSPENDED,
            ):
                return self._reject(
                    update.operation_id,
                    update.runtime_id,
                    update.assessed_at,
                    fingerprint,
                    AgentRuntimeOperationOutcome.INVALID_TRANSITION,
                    (AgentRuntimeTransitionReasonCode.INVALID_LIFECYCLE_TRANSITION,),
                )
            next_state = self._pressure_update_state(current, update.pressure_state)
            reasons = self._pressure_update_reasons(update.pressure_state, next_state)
            return self._apply(
                update.operation_id,
                update.runtime_id,
                update.assessed_at,
                fingerprint,
                (
                    _TransitionSpec(
                        next_state,
                        reasons,
                        pressure=update.to_declaration(),
                        allow_same_state=True,
                    ),
                ),
                AgentRuntimeOperationOutcome.APPLIED,
                self._state.validation_result,
            )

    def resume(
        self,
        request: AgentRuntimeResumeRequest,
    ) -> AgentRuntimeOperationResult:
        return self._complete_operation(self._resume_with_lock(request))

    def _resume_with_lock(
        self,
        request: AgentRuntimeResumeRequest,
    ) -> AgentRuntimeOperationResult | _PendingPublication:
        operation = AgentRuntimeOperation.RESUME
        fingerprint = self._fingerprint(operation, request)
        with self._lock:
            replay = self._replay_or_conflict(
                request.operation_id,
                request.runtime_id,
                request.requested_at,
                fingerprint,
            )
            if replay is not None:
                return replay
            rejection = self._runtime_revision_rejection(
                request.operation_id,
                request.runtime_id,
                request.expected_lifecycle_revision,
                request.requested_at,
                fingerprint,
            )
            if rejection is not None:
                return rejection
            current = self._state.snapshot
            if current.lifecycle_state not in (
                AgentRuntimeLifecycleState.YIELDING,
                AgentRuntimeLifecycleState.SUSPENDED,
            ):
                reason = (
                    AgentRuntimeTransitionReasonCode.RESUME_BLOCKED_BY_FAILURE
                    if current.lifecycle_state is AgentRuntimeLifecycleState.FAILED
                    else AgentRuntimeTransitionReasonCode.INVALID_LIFECYCLE_TRANSITION
                )
                return self._reject(
                    request.operation_id,
                    request.runtime_id,
                    request.requested_at,
                    fingerprint,
                    AgentRuntimeOperationOutcome.INVALID_TRANSITION,
                    (reason,),
                )
            if current.cancellation is not None:
                return self._reject(
                    request.operation_id,
                    request.runtime_id,
                    request.requested_at,
                    fingerprint,
                    AgentRuntimeOperationOutcome.REJECTED,
                    (AgentRuntimeTransitionReasonCode.RESUME_BLOCKED_BY_CANCELLATION,),
                )
            validation = validate_runtime(self._runtime)
            if validation.outcome in (
                RuntimeValidationOutcome.INVALID,
                RuntimeValidationOutcome.UNKNOWN,
            ):
                return self._reject(
                    request.operation_id,
                    request.runtime_id,
                    request.requested_at,
                    fingerprint,
                    AgentRuntimeOperationOutcome.INVALID_CONFIGURATION,
                    (AgentRuntimeTransitionReasonCode.RESUME_BLOCKED_BY_INVALID_CONFIGURATION,),
                    validation,
                )
            pressure = request.current_pressure.pressure_state
            if pressure not in (
                RuntimePressureState.NORMAL,
                RuntimePressureState.ELEVATED,
            ):
                return self._reject(
                    request.operation_id,
                    request.runtime_id,
                    request.requested_at,
                    fingerprint,
                    AgentRuntimeOperationOutcome.REJECTED,
                    (AgentRuntimeTransitionReasonCode.RESUME_BLOCKED_BY_PRESSURE,),
                    validation,
                )
            next_state = (
                AgentRuntimeLifecycleState.RUNNING
                if pressure is RuntimePressureState.NORMAL
                else AgentRuntimeLifecycleState.YIELDING
            )
            return self._apply(
                request.operation_id,
                request.runtime_id,
                request.requested_at,
                fingerprint,
                (
                    _TransitionSpec(
                        next_state,
                        (AgentRuntimeTransitionReasonCode.RESUME_ACCEPTED,),
                        pressure=request.current_pressure,
                        allow_same_state=True,
                    ),
                ),
                AgentRuntimeOperationOutcome.APPLIED,
                validation,
            )

    def cancel(
        self,
        request: AgentRuntimeCancellation,
    ) -> AgentRuntimeOperationResult:
        return self._complete_operation(self._cancel_with_lock(request))

    def _cancel_with_lock(
        self,
        request: AgentRuntimeCancellation,
    ) -> AgentRuntimeOperationResult | _PendingPublication:
        operation = AgentRuntimeOperation.CANCEL
        fingerprint = self._fingerprint(operation, request)
        with self._lock:
            replay = self._replay_or_conflict(
                request.operation_id,
                request.runtime_id,
                request.requested_at,
                fingerprint,
            )
            if replay is not None:
                return replay
            existing_cancellation = self._state.cancellation_fingerprints.get(
                request.cancellation_id.value
            )
            if existing_cancellation is not None and existing_cancellation != fingerprint:
                return self._reject(
                    request.operation_id,
                    request.runtime_id,
                    request.requested_at,
                    fingerprint,
                    AgentRuntimeOperationOutcome.OPERATION_CONFLICT,
                    (AgentRuntimeTransitionReasonCode.CANCELLATION_IDENTITY_CONFLICT,),
                )
            rejection = self._runtime_revision_rejection(
                request.operation_id,
                request.runtime_id,
                request.expected_lifecycle_revision,
                request.requested_at,
                fingerprint,
            )
            if rejection is not None:
                return rejection
            if self._state.snapshot.lifecycle_state is AgentRuntimeLifecycleState.STOPPED:
                return self._reject(
                    request.operation_id,
                    request.runtime_id,
                    request.requested_at,
                    fingerprint,
                    AgentRuntimeOperationOutcome.REJECTED,
                    (AgentRuntimeTransitionReasonCode.ALREADY_STOPPED,),
                )
            base_reasons = [AgentRuntimeTransitionReasonCode.CANCELLATION_REQUESTED]
            if request.graceful_shutdown_required:
                base_reasons.append(AgentRuntimeTransitionReasonCode.GRACEFUL_SHUTDOWN_REQUESTED)
            specs = self._shutdown_specs(tuple(base_reasons), request, None)
            return self._apply(
                request.operation_id,
                request.runtime_id,
                request.requested_at,
                fingerprint,
                specs,
                AgentRuntimeOperationOutcome.APPLIED,
                self._state.validation_result,
                cancellation_fingerprint=(request.cancellation_id, fingerprint),
            )

    def stop(
        self,
        request: AgentRuntimeStopRequest,
    ) -> AgentRuntimeOperationResult:
        return self._complete_operation(self._stop_with_lock(request))

    def _stop_with_lock(
        self,
        request: AgentRuntimeStopRequest,
    ) -> AgentRuntimeOperationResult | _PendingPublication:
        operation = AgentRuntimeOperation.STOP
        fingerprint = self._fingerprint(operation, request)
        with self._lock:
            replay = self._replay_or_conflict(
                request.operation_id,
                request.runtime_id,
                request.requested_at,
                fingerprint,
            )
            if replay is not None:
                return replay
            rejection = self._runtime_revision_rejection(
                request.operation_id,
                request.runtime_id,
                request.expected_lifecycle_revision,
                request.requested_at,
                fingerprint,
            )
            if rejection is not None:
                return rejection
            if self._state.snapshot.lifecycle_state is AgentRuntimeLifecycleState.STOPPED:
                return self._reject(
                    request.operation_id,
                    request.runtime_id,
                    request.requested_at,
                    fingerprint,
                    AgentRuntimeOperationOutcome.REJECTED,
                    (AgentRuntimeTransitionReasonCode.ALREADY_STOPPED,),
                )
            base_reasons = [AgentRuntimeTransitionReasonCode.STOP_REQUESTED]
            if request.graceful:
                base_reasons.append(AgentRuntimeTransitionReasonCode.GRACEFUL_SHUTDOWN_REQUESTED)
            specs = self._shutdown_specs(tuple(base_reasons), None, None)
            return self._apply(
                request.operation_id,
                request.runtime_id,
                request.requested_at,
                fingerprint,
                specs,
                AgentRuntimeOperationOutcome.APPLIED,
                self._state.validation_result,
            )

    def report_failure(
        self,
        failure: AgentRuntimeFailure,
    ) -> AgentRuntimeOperationResult:
        return self._complete_operation(self._report_failure_with_lock(failure))

    def _report_failure_with_lock(
        self,
        failure: AgentRuntimeFailure,
    ) -> AgentRuntimeOperationResult | _PendingPublication:
        operation = AgentRuntimeOperation.FAIL
        fingerprint = self._fingerprint(operation, failure)
        with self._lock:
            replay = self._replay_or_conflict(
                failure.operation_id,
                failure.runtime_id,
                failure.occurred_at,
                fingerprint,
            )
            if replay is not None:
                return replay
            rejection = self._runtime_revision_rejection(
                failure.operation_id,
                failure.runtime_id,
                failure.expected_lifecycle_revision,
                failure.occurred_at,
                fingerprint,
            )
            if rejection is not None:
                return rejection
            if self._state.snapshot.lifecycle_state not in (
                AgentRuntimeLifecycleState.CREATED,
                AgentRuntimeLifecycleState.VALIDATED,
            ):
                return self._reject(
                    failure.operation_id,
                    failure.runtime_id,
                    failure.occurred_at,
                    fingerprint,
                    AgentRuntimeOperationOutcome.INVALID_TRANSITION,
                    (AgentRuntimeTransitionReasonCode.INVALID_LIFECYCLE_TRANSITION,),
                )
            return self._apply(
                failure.operation_id,
                failure.runtime_id,
                failure.occurred_at,
                fingerprint,
                (
                    _TransitionSpec(
                        AgentRuntimeLifecycleState.FAILED,
                        (AgentRuntimeTransitionReasonCode.FAILURE_REPORTED,),
                        failure=failure,
                    ),
                ),
                AgentRuntimeOperationOutcome.FAILED,
                self._state.validation_result,
            )

    def _accepted_profile_reason(
        self,
        allow_development_profile: bool,
    ) -> AgentRuntimeTransitionReasonCode | None:
        if self._runtime.profile is RuntimeProfile.AGENT:
            return AgentRuntimeTransitionReasonCode.AGENT_PROFILE_ACCEPTED
        if self._runtime.profile is RuntimeProfile.DEVELOPMENT and allow_development_profile:
            return AgentRuntimeTransitionReasonCode.DEVELOPMENT_PROFILE_ACCEPTED
        return None

    def _common_rejection(
        self,
        operation_id: EntityId,
        runtime_id: EntityId,
        configuration_id: EntityId,
        expected_revision: int,
        occurred_at: datetime,
        fingerprint: str,
    ) -> AgentRuntimeOperationResult | None:
        if configuration_id != self._runtime.configuration.id:
            return self._reject(
                operation_id,
                runtime_id,
                occurred_at,
                fingerprint,
                AgentRuntimeOperationOutcome.INVALID_CONFIGURATION,
                (AgentRuntimeTransitionReasonCode.CONFIGURATION_ID_MISMATCH,),
            )
        return self._runtime_revision_rejection(
            operation_id,
            runtime_id,
            expected_revision,
            occurred_at,
            fingerprint,
        )

    def _runtime_revision_rejection(
        self,
        operation_id: EntityId,
        runtime_id: EntityId,
        expected_revision: int,
        occurred_at: datetime,
        fingerprint: str,
    ) -> AgentRuntimeOperationResult | None:
        if runtime_id != self._runtime.identity.runtime_id:
            return self._reject(
                operation_id,
                runtime_id,
                occurred_at,
                fingerprint,
                AgentRuntimeOperationOutcome.INVALID_RUNTIME,
                (AgentRuntimeTransitionReasonCode.RUNTIME_ID_MISMATCH,),
            )
        if expected_revision != self._state.snapshot.lifecycle_revision:
            return self._reject(
                operation_id,
                runtime_id,
                occurred_at,
                fingerprint,
                AgentRuntimeOperationOutcome.STALE_REVISION,
                (AgentRuntimeTransitionReasonCode.STALE_LIFECYCLE_REVISION,),
            )
        return None

    def _replay_or_conflict(
        self,
        operation_id: EntityId,
        runtime_id: EntityId,
        occurred_at: datetime,
        fingerprint: str,
    ) -> AgentRuntimeOperationResult | None:
        record = self._state.operation_records.get(operation_id.value)
        if record is None:
            return None
        if record.fingerprint != fingerprint:
            snapshot = self._state.snapshot
            return AgentRuntimeOperationResult(
                operation_id=operation_id,
                runtime_id=runtime_id,
                outcome=AgentRuntimeOperationOutcome.OPERATION_CONFLICT,
                reasons=(AgentRuntimeTransitionReasonCode.OPERATION_IDENTITY_CONFLICT,),
                previous_snapshot=snapshot,
                current_snapshot=snapshot,
                transitions=(),
                validation_result=self._state.validation_result,
                publication_failures=(),
                occurred_at=occurred_at,
            )
        while record.notification_pending:
            self._publication_condition.wait()
            resolved_record = self._state.operation_records.get(operation_id.value)
            if resolved_record is None:
                raise RuntimeError("Committed Agent operation record disappeared.")
            record = resolved_record
        original = record.result
        return replace(
            original,
            outcome=AgentRuntimeOperationOutcome.ALREADY_APPLIED,
            reasons=normalize_reason_codes(
                (
                    *original.reasons,
                    AgentRuntimeTransitionReasonCode.OPERATION_REPLAY,
                )
            ),
        )

    def _reject(
        self,
        operation_id: EntityId,
        runtime_id: EntityId,
        occurred_at: datetime,
        fingerprint: str,
        outcome: AgentRuntimeOperationOutcome,
        reasons: Sequence[AgentRuntimeTransitionReasonCode],
        validation: RuntimeValidationResult | None = None,
    ) -> AgentRuntimeOperationResult:
        snapshot = self._state.snapshot
        result = AgentRuntimeOperationResult(
            operation_id=operation_id,
            runtime_id=runtime_id,
            outcome=outcome,
            reasons=reasons,
            previous_snapshot=snapshot,
            current_snapshot=snapshot,
            transitions=(),
            validation_result=validation or self._state.validation_result,
            publication_failures=(),
            occurred_at=occurred_at,
        )
        self._record_operation(operation_id, fingerprint, result)
        return result

    def _apply(
        self,
        operation_id: EntityId,
        runtime_id: EntityId,
        occurred_at: datetime,
        fingerprint: str,
        specs: Sequence[_TransitionSpec],
        outcome: AgentRuntimeOperationOutcome,
        validation: RuntimeValidationResult | None,
        cancellation_fingerprint: tuple[EntityId, str] | None = None,
    ) -> _PendingPublication:
        previous = self._state.snapshot
        resolved_validation = validation or self._state.validation_result
        steps: list[_AppliedStep] = []
        current = previous
        for spec in specs:
            step = self._build_step(
                current,
                spec,
                operation_id,
                occurred_at,
                resolved_validation,
            )
            steps.append(step)
            current = step.snapshot
        transitions = tuple(step.transition for step in steps)
        reasons = normalize_reason_codes(tuple(reason for spec in specs for reason in spec.reasons))
        result = AgentRuntimeOperationResult(
            operation_id=operation_id,
            runtime_id=runtime_id,
            outcome=outcome,
            reasons=reasons,
            previous_snapshot=previous,
            current_snapshot=current,
            transitions=transitions,
            validation_result=resolved_validation,
            publication_failures=(),
            occurred_at=occurred_at,
        )
        records = dict(self._state.operation_records)
        records[operation_id.value] = _OperationRecord(
            fingerprint,
            result,
            notification_pending=True,
        )
        cancellation_fingerprints = dict(self._state.cancellation_fingerprints)
        if cancellation_fingerprint is not None:
            cancellation_id, cancellation_value = cancellation_fingerprint
            cancellation_fingerprints[cancellation_id.value] = cancellation_value
        self._state = _AgentRuntimeState(
            snapshot=current,
            transitions=(*self._state.transitions, *transitions),
            operation_records=MappingProxyType(records),
            cancellation_fingerprints=MappingProxyType(cancellation_fingerprints),
            validation_result=resolved_validation,
        )
        return _PendingPublication(fingerprint, result, tuple(steps))

    def _complete_operation(
        self,
        operation: AgentRuntimeOperationResult | _PendingPublication,
    ) -> AgentRuntimeOperationResult:
        if isinstance(operation, AgentRuntimeOperationResult):
            return operation
        result = operation.result
        publication_failures = self._publish_steps(operation.steps)
        if publication_failures:
            result = replace(
                result,
                outcome=(AgentRuntimeOperationOutcome.APPLIED_WITH_NOTIFICATION_FAILURE),
                reasons=normalize_reason_codes(
                    (
                        *result.reasons,
                        AgentRuntimeTransitionReasonCode.DEPENDENCY_PUBLICATION_FAILURE,
                    )
                ),
                publication_failures=publication_failures,
            )
        with self._publication_condition:
            records = dict(self._state.operation_records)
            record = records.get(result.operation_id.value)
            if record is None or record.fingerprint != operation.fingerprint:
                raise RuntimeError("Committed Agent operation record changed identity.")
            records[result.operation_id.value] = _OperationRecord(
                operation.fingerprint,
                result,
                notification_pending=False,
            )
            self._state = replace(
                self._state,
                operation_records=MappingProxyType(records),
            )
            self._publication_condition.notify_all()
        return result

    def _build_step(
        self,
        previous: AgentRuntimeSnapshot,
        spec: _TransitionSpec,
        operation_id: EntityId,
        occurred_at: datetime,
        validation: RuntimeValidationResult | None,
    ) -> _AppliedStep:
        if previous.lifecycle_state == spec.next_state:
            if not spec.allow_same_state:
                raise ValueError("Same-state Agent transition requires explicit permission.")
        elif (previous.lifecycle_state, spec.next_state) not in _ALLOWED_TRANSITIONS:
            raise ValueError("Software Agent attempted an unapproved lifecycle transition.")
        revision = previous.lifecycle_revision + 1
        transition_id = deterministic_agent_id(
            previous.agent_instance_id,
            (
                f"transition:{operation_id.value}:{revision}:"
                f"{previous.lifecycle_state.value}:{spec.next_state.value}"
            ),
        )
        reasons = normalize_reason_codes(spec.reasons)
        health = derive_health(
            self._runtime,
            previous.agent_instance_id,
            spec.next_state,
            revision,
            occurred_at,
            validation,
            reasons,
            previous.health,
        )
        availability = derive_availability(
            self._runtime,
            previous.agent_instance_id,
            spec.next_state,
            revision,
            occurred_at,
            validation,
            reasons,
        )
        pressure = spec.pressure or previous.latest_pressure
        cancellation = spec.cancellation or previous.cancellation
        failure = spec.failure or previous.failure
        snapshot = AgentRuntimeSnapshot(
            agent_instance_id=previous.agent_instance_id,
            runtime_id=self._runtime.configuration.runtime_id,
            configuration_id=self._runtime.configuration.id,
            deployment_profile=self._runtime.profile,
            lifecycle_state=spec.next_state,
            previous_lifecycle_state=previous.lifecycle_state,
            state_entered_at=occurred_at,
            lifecycle_revision=revision,
            latest_operation_id=operation_id,
            latest_transition_id=transition_id,
            latest_pressure=pressure,
            execution_permission=permission_for_state(spec.next_state),
            health=health,
            availability=availability,
            cancellation=cancellation,
            active_limitations=self._runtime.limitations,
            failure=failure,
            transition_lineage_ids=(
                *previous.transition_lineage_ids,
                transition_id,
            ),
        )
        transition = AgentRuntimeTransition(
            id=transition_id,
            operation_id=operation_id,
            runtime_id=self._runtime.configuration.runtime_id,
            configuration_id=self._runtime.configuration.id,
            lifecycle_revision=revision,
            previous_state=previous.lifecycle_state,
            next_state=spec.next_state,
            reason_codes=reasons,
            pressure_state=None if pressure is None else pressure.pressure_state,
            execution_permission_before=previous.execution_permission,
            execution_permission_after=snapshot.execution_permission,
            occurred_at=occurred_at,
            health_declaration_id=health.id,
            availability_declaration_id=availability.id,
            limitation_ids=tuple(value.id for value in self._runtime.limitations),
            failure_id=None if failure is None else failure.failure_id,
        )
        return _AppliedStep(snapshot, transition)

    def _publish_steps(
        self,
        steps: Sequence[_AppliedStep],
    ) -> tuple[AgentRuntimeNotificationFailure, ...]:
        failures: list[AgentRuntimeNotificationFailure] = []
        for step in steps:
            publications = (
                (
                    AgentRuntimeNotificationPortKind.LIFECYCLE,
                    self._dependencies.lifecycle_event_sink,
                    "publish_transition",
                    step.transition,
                ),
                (
                    AgentRuntimeNotificationPortKind.HEALTH,
                    self._dependencies.runtime_health_sink,
                    "publish_health",
                    step.snapshot.health,
                ),
                (
                    AgentRuntimeNotificationPortKind.AVAILABILITY,
                    self._dependencies.runtime_availability_sink,
                    "publish_availability",
                    step.snapshot.availability,
                ),
            )
            for kind, sink, method_name, value in publications:
                if sink is None:
                    continue
                try:
                    getattr(sink, method_name)(value)
                except Exception:
                    failures.append(
                        AgentRuntimeNotificationFailure(
                            port_kind=kind,
                            operation_id=step.transition.operation_id,
                            transition_id=step.transition.id,
                            failure_code="notification_publish_failed",
                            lifecycle_transition_committed=True,
                        )
                    )
        return tuple(failures)

    def _record_operation(
        self,
        operation_id: EntityId,
        fingerprint: str,
        result: AgentRuntimeOperationResult,
    ) -> None:
        records = dict(self._state.operation_records)
        records[operation_id.value] = _OperationRecord(
            fingerprint,
            result,
            notification_pending=False,
        )
        self._state = replace(
            self._state,
            operation_records=MappingProxyType(records),
        )

    def _shutdown_specs(
        self,
        reasons: tuple[AgentRuntimeTransitionReasonCode, ...],
        cancellation: AgentRuntimeCancellation | None,
        failure: AgentRuntimeFailure | None,
    ) -> tuple[_TransitionSpec, ...]:
        current = self._state.snapshot.lifecycle_state
        if current is AgentRuntimeLifecycleState.CREATED:
            return (
                _TransitionSpec(
                    AgentRuntimeLifecycleState.STOPPED,
                    (*reasons, AgentRuntimeTransitionReasonCode.SHUTDOWN_COMPLETE),
                    cancellation=cancellation,
                    failure=failure,
                ),
            )
        return (
            _TransitionSpec(
                AgentRuntimeLifecycleState.STOPPING,
                reasons,
                cancellation=cancellation,
                failure=failure,
            ),
            _TransitionSpec(
                AgentRuntimeLifecycleState.STOPPED,
                (AgentRuntimeTransitionReasonCode.SHUTDOWN_COMPLETE,),
                cancellation=cancellation,
                failure=failure,
            ),
        )

    def _initial_pressure_mapping(
        self,
        pressure: RuntimePressureState,
    ) -> tuple[
        AgentRuntimeLifecycleState,
        tuple[AgentRuntimeTransitionReasonCode, ...],
    ]:
        if pressure is RuntimePressureState.NORMAL:
            return (
                AgentRuntimeLifecycleState.RUNNING,
                (AgentRuntimeTransitionReasonCode.INITIAL_PRESSURE_NORMAL,),
            )
        if pressure is RuntimePressureState.ELEVATED:
            return (
                AgentRuntimeLifecycleState.YIELDING,
                (
                    AgentRuntimeTransitionReasonCode.INITIAL_PRESSURE_ELEVATED,
                    AgentRuntimeTransitionReasonCode.OPTIONAL_WORK_REDUCED,
                ),
            )
        if pressure is RuntimePressureState.CRITICAL:
            return (
                AgentRuntimeLifecycleState.SUSPENDED,
                (
                    AgentRuntimeTransitionReasonCode.INITIAL_PRESSURE_CRITICAL,
                    AgentRuntimeTransitionReasonCode.AGENT_WORK_SUSPENDED,
                ),
            )
        if pressure is RuntimePressureState.RECORDING_SAFETY_UNCERTAIN:
            return (
                AgentRuntimeLifecycleState.SUSPENDED,
                (
                    AgentRuntimeTransitionReasonCode.RECORDING_SAFETY_UNCERTAIN,
                    AgentRuntimeTransitionReasonCode.AGENT_WORK_SUSPENDED,
                ),
            )
        return (
            AgentRuntimeLifecycleState.SUSPENDED,
            (
                AgentRuntimeTransitionReasonCode.INITIAL_PRESSURE_UNKNOWN,
                AgentRuntimeTransitionReasonCode.AGENT_WORK_SUSPENDED,
            ),
        )

    @staticmethod
    def _pressure_update_state(
        current: AgentRuntimeLifecycleState,
        pressure: RuntimePressureState,
    ) -> AgentRuntimeLifecycleState:
        if pressure in (
            RuntimePressureState.CRITICAL,
            RuntimePressureState.RECORDING_SAFETY_UNCERTAIN,
            RuntimePressureState.UNKNOWN,
        ):
            return AgentRuntimeLifecycleState.SUSPENDED
        if current is AgentRuntimeLifecycleState.SUSPENDED:
            return current
        if pressure is RuntimePressureState.ELEVATED:
            return AgentRuntimeLifecycleState.YIELDING
        if current is AgentRuntimeLifecycleState.YIELDING:
            return current
        return AgentRuntimeLifecycleState.RUNNING

    @staticmethod
    def _pressure_update_reasons(
        pressure: RuntimePressureState,
        next_state: AgentRuntimeLifecycleState,
    ) -> tuple[AgentRuntimeTransitionReasonCode, ...]:
        if pressure is RuntimePressureState.NORMAL:
            reasons = [AgentRuntimeTransitionReasonCode.PRESSURE_NORMALIZED]
        elif pressure is RuntimePressureState.ELEVATED:
            reasons = [
                AgentRuntimeTransitionReasonCode.PRESSURE_ELEVATED,
                AgentRuntimeTransitionReasonCode.OPTIONAL_WORK_REDUCED,
            ]
        elif pressure is RuntimePressureState.CRITICAL:
            reasons = [AgentRuntimeTransitionReasonCode.PRESSURE_CRITICAL]
        elif pressure is RuntimePressureState.RECORDING_SAFETY_UNCERTAIN:
            reasons = [AgentRuntimeTransitionReasonCode.RECORDING_SAFETY_UNCERTAIN]
        else:
            reasons = [AgentRuntimeTransitionReasonCode.PRESSURE_UNKNOWN]
        if next_state is AgentRuntimeLifecycleState.SUSPENDED:
            reasons.extend(
                (
                    AgentRuntimeTransitionReasonCode.AGENT_WORK_SUSPENDED,
                    AgentRuntimeTransitionReasonCode.EXPLICIT_RESUME_REQUIRED,
                )
            )
        return normalize_reason_codes(reasons)

    @staticmethod
    def _fingerprint(operation: AgentRuntimeOperation, request: object) -> str:
        return f"{operation.value}:{canonical_value(request)}"


__all__ = ["SoftwareAgentRuntime"]
