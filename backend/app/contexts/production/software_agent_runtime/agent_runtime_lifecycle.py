from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum


class AgentRuntimeLifecycleState(StrEnum):
    CREATED = "created"
    VALIDATED = "validated"
    READY = "ready"
    RUNNING = "running"
    YIELDING = "yielding"
    SUSPENDED = "suspended"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    DISABLED = "disabled"


class AgentRuntimeExecutionPermission(StrEnum):
    NONE = "none"
    ESSENTIAL_ONLY = "essential_only"
    REDUCED = "reduced"
    NORMAL = "normal"


class AgentRuntimeOperation(StrEnum):
    PREPARE = "prepare"
    START = "start"
    PRESSURE_UPDATE = "pressure_update"
    RESUME = "resume"
    CANCEL = "cancel"
    STOP = "stop"
    FAIL = "fail"


class AgentRuntimeOperationOutcome(StrEnum):
    APPLIED = "applied"
    ALREADY_APPLIED = "already_applied"
    DISABLED = "disabled"
    REJECTED = "rejected"
    STALE_REVISION = "stale_revision"
    OPERATION_CONFLICT = "operation_conflict"
    INVALID_RUNTIME = "invalid_runtime"
    INVALID_CONFIGURATION = "invalid_configuration"
    INVALID_TRANSITION = "invalid_transition"
    DEPENDENCY_FAILURE = "dependency_failure"
    APPLIED_WITH_NOTIFICATION_FAILURE = "applied_with_notification_failure"
    FAILED = "failed"
    UNKNOWN = "unknown"


class AgentRuntimeTransitionReasonCode(StrEnum):
    AGENT_CREATED = "agent_created"
    RUNTIME_VALIDATION_PASSED = "runtime_validation_passed"
    RUNTIME_VALIDATION_FAILED = "runtime_validation_failed"
    AGENT_PROFILE_ACCEPTED = "agent_profile_accepted"
    DEVELOPMENT_PROFILE_ACCEPTED = "development_profile_accepted"
    UNSUPPORTED_RUNTIME_PROFILE = "unsupported_runtime_profile"
    CONFIGURATION_DISABLED = "configuration_disabled"
    EVENT_MODE_DISABLED = "event_mode_disabled"
    REQUIRED_DEPENDENCY_MISSING = "required_dependency_missing"
    STARTUP_PREPARED = "startup_prepared"
    INITIAL_PRESSURE_NORMAL = "initial_pressure_normal"
    INITIAL_PRESSURE_ELEVATED = "initial_pressure_elevated"
    INITIAL_PRESSURE_CRITICAL = "initial_pressure_critical"
    RECORDING_SAFETY_UNCERTAIN = "recording_safety_uncertain"
    INITIAL_PRESSURE_UNKNOWN = "initial_pressure_unknown"
    PRESSURE_ELEVATED = "pressure_elevated"
    PRESSURE_CRITICAL = "pressure_critical"
    PRESSURE_NORMALIZED = "pressure_normalized"
    PRESSURE_UNKNOWN = "pressure_unknown"
    OPTIONAL_WORK_REDUCED = "optional_work_reduced"
    AGENT_WORK_SUSPENDED = "agent_work_suspended"
    EXPLICIT_RESUME_REQUIRED = "explicit_resume_required"
    RESUME_ACCEPTED = "resume_accepted"
    RESUME_BLOCKED_BY_PRESSURE = "resume_blocked_by_pressure"
    RESUME_BLOCKED_BY_CANCELLATION = "resume_blocked_by_cancellation"
    RESUME_BLOCKED_BY_FAILURE = "resume_blocked_by_failure"
    RESUME_BLOCKED_BY_INVALID_CONFIGURATION = "resume_blocked_by_invalid_configuration"
    STOP_REQUESTED = "stop_requested"
    CANCELLATION_REQUESTED = "cancellation_requested"
    GRACEFUL_SHUTDOWN_REQUESTED = "graceful_shutdown_requested"
    ALREADY_STOPPING = "already_stopping"
    ALREADY_STOPPED = "already_stopped"
    SHUTDOWN_COMPLETE = "shutdown_complete"
    FAILURE_REPORTED = "failure_reported"
    INVALID_LIFECYCLE_TRANSITION = "invalid_lifecycle_transition"
    STALE_LIFECYCLE_REVISION = "stale_lifecycle_revision"
    OPERATION_REPLAY = "operation_replay"
    OPERATION_IDENTITY_CONFLICT = "operation_identity_conflict"
    CANCELLATION_IDENTITY_CONFLICT = "cancellation_identity_conflict"
    RUNTIME_ID_MISMATCH = "runtime_id_mismatch"
    CONFIGURATION_ID_MISMATCH = "configuration_id_mismatch"
    TIMEZONE_NAIVE_TIMESTAMP = "timezone_naive_timestamp"
    DEPENDENCY_PUBLICATION_FAILURE = "dependency_publication_failure"
    AVAILABILITY_UNAVAILABLE = "availability_unavailable"
    UNKNOWN_LIFECYCLE_FAILURE = "unknown_lifecycle_failure"


class AgentRuntimeNotificationPortKind(StrEnum):
    LIFECYCLE = "lifecycle"
    HEALTH = "health"
    AVAILABILITY = "availability"


_REASON_ORDER = {reason: index for index, reason in enumerate(AgentRuntimeTransitionReasonCode)}


def normalize_reason_codes(
    values: Sequence[AgentRuntimeTransitionReasonCode],
) -> tuple[AgentRuntimeTransitionReasonCode, ...]:
    return tuple(sorted(set(values), key=_REASON_ORDER.__getitem__))


def permission_for_state(
    state: AgentRuntimeLifecycleState,
) -> AgentRuntimeExecutionPermission:
    if state is AgentRuntimeLifecycleState.RUNNING:
        return AgentRuntimeExecutionPermission.NORMAL
    if state is AgentRuntimeLifecycleState.YIELDING:
        return AgentRuntimeExecutionPermission.REDUCED
    return AgentRuntimeExecutionPermission.NONE


__all__ = [
    "AgentRuntimeExecutionPermission",
    "AgentRuntimeLifecycleState",
    "AgentRuntimeNotificationPortKind",
    "AgentRuntimeOperation",
    "AgentRuntimeOperationOutcome",
    "AgentRuntimeTransitionReasonCode",
    "normalize_reason_codes",
    "permission_for_state",
]
