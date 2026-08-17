from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from app.shared.ids import EntityId
from app.shared.time import require_aware_datetime

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_REASON = re.compile(r"^[a-z][a-z0-9_]{0,127}$")


def _identifier(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not _IDENTIFIER.fullmatch(normalized):
        raise ValueError(f"{field_name} must be a sanitized stable identifier.")
    return normalized


def _digest(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not _DIGEST.fullmatch(normalized):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest.")
    return normalized


def _reason(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not _REASON.fullmatch(normalized):
        raise ValueError(f"{field_name} must be a sanitized reason code.")
    return normalized


def _optional_identifier(value: str | None, field_name: str) -> str | None:
    return None if value is None else _identifier(value, field_name)


def _positive_duration(value: timedelta, field_name: str) -> timedelta:
    if value <= timedelta(0):
        raise ValueError(f"{field_name} must be positive.")
    if value > timedelta(hours=1):
        raise ValueError(f"{field_name} exceeds the bounded one-hour maximum.")
    return value


class OperationStatus(StrEnum):
    PENDING = "pending"
    ELIGIBLE = "eligible"
    LEASED = "leased"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    DEFERRED = "deferred"
    BLOCKED = "blocked"
    SUCCEEDED = "succeeded"
    TERMINAL_FAILED = "terminal_failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"


class AttemptStatus(StrEnum):
    LEASED = "leased"
    RUNNING = "running"
    FINALIZED = "finalized"


class AttemptOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    RETRYABLE_FAILURE = "retryable_failure"
    TERMINAL_FAILURE = "terminal_failure"
    LEASE_LOST = "lease_lost"
    RESULT_RECONCILED = "result_reconciled"
    CANCELLED = "cancelled"
    ORPHANED = "orphaned"


class WorkerHealth(StrEnum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class WorkerPressure(StrEnum):
    NORMAL = "normal"
    CONSTRAINED = "constrained"
    SATURATED = "saturated"
    UNKNOWN = "unknown"


class ExecutionLocality(StrEnum):
    LOCAL = "local"
    CLOUD = "cloud"


class EventNetworkPolicy(StrEnum):
    LOCAL_ONLY = "local_only"
    NETWORK_PERMITTED = "network_permitted"


@dataclass(frozen=True, slots=True)
class TranscriptionOperationInput:
    asset_id: EntityId
    manifest_id: EntityId
    manifest_version: str
    asset_format: str
    execution_profile_id: str
    execution_profile_version: str
    requested_language: str | None = None
    request_word_timing: bool = False
    request_speaker_labels: bool = False
    requires_cloud: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "manifest_version",
            "asset_format",
            "execution_profile_id",
            "execution_profile_version",
        ):
            object.__setattr__(
                self,
                field_name,
                _identifier(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self,
            "requested_language",
            _optional_identifier(self.requested_language, "requested_language"),
        )


@dataclass(frozen=True, slots=True)
class EnqueueTranscriptionOperation:
    operation_id: EntityId
    idempotency_key: str
    deployment_id: str
    event_id: EntityId | None
    input: TranscriptionOperationInput
    priority: int
    eligible_at: datetime
    max_attempts: int
    retry_delay: timedelta
    required_for_event: bool
    requested_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "idempotency_key",
            _identifier(self.idempotency_key, "idempotency_key"),
        )
        object.__setattr__(
            self,
            "deployment_id",
            _identifier(self.deployment_id, "deployment_id"),
        )
        if not -1000 <= self.priority <= 1000:
            raise ValueError("priority must be between -1000 and 1000.")
        if not 1 <= self.max_attempts <= 20:
            raise ValueError("max_attempts must be between 1 and 20.")
        object.__setattr__(
            self,
            "retry_delay",
            _positive_duration(self.retry_delay, "retry_delay"),
        )
        require_aware_datetime(self.eligible_at, "eligible_at")
        require_aware_datetime(self.requested_at, "requested_at")


@dataclass(frozen=True, slots=True)
class PendingOperation:
    request: EnqueueTranscriptionOperation
    request_digest: str
    work_key: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "request_digest",
            _digest(self.request_digest, "request_digest"),
        )
        object.__setattr__(self, "work_key", _digest(self.work_key, "work_key"))


@dataclass(frozen=True, slots=True)
class DurableOperation:
    id: EntityId
    kind: str
    schema_version: str
    deployment_id: str
    event_id: EntityId | None
    input: TranscriptionOperationInput
    idempotency_key: str
    request_digest: str
    work_key: str
    priority: int
    eligible_at: datetime
    status: OperationStatus
    max_attempts: int
    retry_delay: timedelta
    required_for_event: bool
    attempt_count: int
    fence_generation: int
    current_attempt_id: EntityId | None
    lease_owner_worker_id: EntityId | None
    lease_expires_at: datetime | None
    cancellation_requested_at: datetime | None
    terminal_result_type: str | None
    terminal_result_id: EntityId | None
    terminal_result_revision: int | None
    last_reason_code: str | None
    revision: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        for field_name in (
            "kind",
            "schema_version",
            "deployment_id",
            "idempotency_key",
        ):
            object.__setattr__(
                self,
                field_name,
                _identifier(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self,
            "request_digest",
            _digest(self.request_digest, "request_digest"),
        )
        object.__setattr__(self, "work_key", _digest(self.work_key, "work_key"))
        object.__setattr__(
            self,
            "terminal_result_type",
            _optional_identifier(self.terminal_result_type, "terminal_result_type"),
        )
        if self.last_reason_code is not None:
            object.__setattr__(
                self,
                "last_reason_code",
                _reason(self.last_reason_code, "last_reason_code"),
            )
        for field_name in ("eligible_at", "created_at", "updated_at"):
            require_aware_datetime(getattr(self, field_name), field_name)
        for field_name in ("lease_expires_at", "cancellation_requested_at"):
            value = getattr(self, field_name)
            if value is not None:
                require_aware_datetime(value, field_name)
        if self.attempt_count < 0 or self.fence_generation < 0:
            raise ValueError("attempt and fencing generations must not be negative.")
        if self.revision < 1:
            raise ValueError("operation revision must be positive.")


@dataclass(frozen=True, slots=True)
class OperationAttempt:
    id: EntityId
    operation_id: EntityId
    worker_id: EntityId
    attempt_number: int
    fence_generation: int
    status: AttemptStatus
    lease_started_at: datetime
    lease_expires_at: datetime
    execution_started_at: datetime | None
    finalized_at: datetime | None
    outcome: AttemptOutcome | None
    retryable: bool | None
    reason_code: str | None
    diagnostic_summary: str | None
    created_at: datetime

    def __post_init__(self) -> None:
        if self.attempt_number < 1 or self.fence_generation < 1:
            raise ValueError("attempt number and fencing generation must be positive.")
        for field_name in ("lease_started_at", "lease_expires_at", "created_at"):
            require_aware_datetime(getattr(self, field_name), field_name)
        for field_name in ("execution_started_at", "finalized_at"):
            value = getattr(self, field_name)
            if value is not None:
                require_aware_datetime(value, field_name)
        if self.lease_expires_at <= self.lease_started_at:
            raise ValueError("attempt lease expiry must follow lease start.")
        if self.reason_code is not None:
            object.__setattr__(
                self,
                "reason_code",
                _reason(self.reason_code, "reason_code"),
            )
        if self.diagnostic_summary is not None:
            diagnostic = self.diagnostic_summary.strip()
            if not diagnostic or len(diagnostic) > 256 or "\n" in diagnostic:
                raise ValueError("diagnostic_summary must be one bounded sanitized line.")
            object.__setattr__(self, "diagnostic_summary", diagnostic)


@dataclass(frozen=True, slots=True)
class Worker:
    id: EntityId
    node_id: str
    deployment_id: str
    event_id: EntityId | None
    enabled: bool
    draining: bool
    implementation_version: str
    revision: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        for field_name in ("node_id", "deployment_id", "implementation_version"):
            object.__setattr__(
                self,
                field_name,
                _identifier(getattr(self, field_name), field_name),
            )
        if self.revision < 1:
            raise ValueError("worker revision must be positive.")
        require_aware_datetime(self.created_at, "created_at")
        require_aware_datetime(self.updated_at, "updated_at")


@dataclass(frozen=True, slots=True)
class WorkerCapability:
    id: EntityId
    worker_id: EntityId
    operation_kind: str
    operation_schema_version: str
    execution_profile_id: str
    execution_profile_version: str
    locality: ExecutionLocality
    accepted_asset_formats: tuple[str, ...]
    supports_word_timing: bool
    supports_speaker_labels: bool
    provider_id: str | None
    provider_version: str | None
    model_id: str | None
    model_version: str | None
    runtime_id: str
    runtime_version: str
    configured_eligible: bool
    effective_from: datetime
    effective_until: datetime | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "operation_kind",
            "operation_schema_version",
            "execution_profile_id",
            "execution_profile_version",
            "runtime_id",
            "runtime_version",
        ):
            object.__setattr__(
                self,
                field_name,
                _identifier(getattr(self, field_name), field_name),
            )
        for field_name in (
            "provider_id",
            "provider_version",
            "model_id",
            "model_version",
        ):
            object.__setattr__(
                self,
                field_name,
                _optional_identifier(getattr(self, field_name), field_name),
            )
        formats = tuple(
            sorted(
                {
                    _identifier(value, "accepted_asset_format")
                    for value in self.accepted_asset_formats
                }
            )
        )
        if not formats:
            raise ValueError("A worker capability requires an accepted asset format.")
        object.__setattr__(self, "accepted_asset_formats", formats)
        require_aware_datetime(self.effective_from, "effective_from")
        if self.effective_until is not None:
            require_aware_datetime(self.effective_until, "effective_until")
            if self.effective_until <= self.effective_from:
                raise ValueError("effective_until must follow effective_from.")


@dataclass(frozen=True, slots=True)
class WorkerPresence:
    worker_id: EntityId
    observed_at: datetime
    expires_at: datetime
    maximum_concurrency: int
    health: WorkerHealth
    pressure: WorkerPressure

    def __post_init__(self) -> None:
        require_aware_datetime(self.observed_at, "observed_at")
        require_aware_datetime(self.expires_at, "expires_at")
        if self.expires_at <= self.observed_at:
            raise ValueError("presence expiry must follow observation time.")
        if not 1 <= self.maximum_concurrency <= 64:
            raise ValueError("maximum_concurrency must be between 1 and 64.")


@dataclass(frozen=True, slots=True)
class ClaimRequest:
    worker_id: EntityId
    network_policy: EventNetworkPolicy
    lease_duration: timedelta

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "lease_duration",
            _positive_duration(self.lease_duration, "lease_duration"),
        )


@dataclass(frozen=True, slots=True)
class OperationClaim:
    operation: DurableOperation
    attempt: OperationAttempt


@dataclass(frozen=True, slots=True)
class OperationFailure:
    reason_code: str
    retryable: bool
    diagnostic_summary: str
    retry_delay: timedelta | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reason_code",
            _reason(self.reason_code, "reason_code"),
        )
        diagnostic = self.diagnostic_summary.strip()
        if not diagnostic or len(diagnostic) > 256 or "\n" in diagnostic:
            raise ValueError("diagnostic_summary must be one bounded sanitized line.")
        object.__setattr__(self, "diagnostic_summary", diagnostic)
        if self.retry_delay is not None:
            object.__setattr__(
                self,
                "retry_delay",
                _positive_duration(self.retry_delay, "retry_delay"),
            )


@dataclass(frozen=True, slots=True)
class OperationStatusCount:
    status: OperationStatus
    count: int

    def __post_init__(self) -> None:
        if self.count < 0:
            raise ValueError("status count must not be negative.")


@dataclass(frozen=True, slots=True)
class WorkExecutionProjection:
    generated_at: datetime
    counts: tuple[OperationStatusCount, ...]
    oldest_eligible_at: datetime | None
    active_lease_count: int
    attention_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        require_aware_datetime(self.generated_at, "generated_at")
        if self.oldest_eligible_at is not None:
            require_aware_datetime(self.oldest_eligible_at, "oldest_eligible_at")
        if self.active_lease_count < 0:
            raise ValueError("active_lease_count must not be negative.")
        object.__setattr__(
            self,
            "counts",
            tuple(sorted(self.counts, key=lambda item: item.status.value)),
        )
        object.__setattr__(
            self,
            "attention_codes",
            tuple(sorted({_reason(value, "attention_code") for value in self.attention_codes})),
        )


__all__ = [
    "AttemptOutcome",
    "AttemptStatus",
    "ClaimRequest",
    "DurableOperation",
    "EnqueueTranscriptionOperation",
    "EventNetworkPolicy",
    "ExecutionLocality",
    "OperationAttempt",
    "OperationClaim",
    "OperationFailure",
    "OperationStatus",
    "OperationStatusCount",
    "PendingOperation",
    "TranscriptionOperationInput",
    "Worker",
    "WorkerCapability",
    "WorkerHealth",
    "WorkerPresence",
    "WorkerPressure",
    "WorkExecutionProjection",
]

