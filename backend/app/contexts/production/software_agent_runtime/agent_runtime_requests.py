from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.contexts.production.runtime import RuntimePressureState
from app.shared.ids import EntityId

from .agent_runtime_contract_validation import (
    freeze_runtime_metadata,
    normalize_entity_ids,
    normalize_limitations,
    normalize_strings,
    require_aware,
    require_non_empty,
    require_non_negative_revision,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


def _require_pressure_state(value: object, field_name: str) -> None:
    if not isinstance(value, RuntimePressureState):
        raise ValueError(f"{field_name} must be an approved RuntimePressureState.")


@dataclass(frozen=True, slots=True)
class AgentRuntimePressureDeclaration:
    pressure_state: RuntimePressureState
    assessed_at: datetime
    source_id: EntityId
    reason_codes: Sequence[str] = field(default_factory=tuple)
    limitations: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        _require_pressure_state(
            self.pressure_state,
            "AgentRuntimePressureDeclaration.pressure_state",
        )
        require_aware(
            self.assessed_at,
            "AgentRuntimePressureDeclaration.assessed_at",
        )
        object.__setattr__(
            self,
            "reason_codes",
            normalize_strings(
                self.reason_codes,
                "AgentRuntimePressureDeclaration.reason_codes",
            ),
        )
        object.__setattr__(
            self,
            "limitations",
            normalize_limitations(
                self.limitations,
                "AgentRuntimePressureDeclaration.limitations",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(
                self.metadata,
                "AgentRuntimePressureDeclaration.metadata",
            ),
        )


@dataclass(frozen=True, slots=True)
class AgentRuntimePrepareRequest:
    operation_id: EntityId
    runtime_id: EntityId
    configuration_id: EntityId
    expected_lifecycle_revision: int
    requested_at: datetime
    allow_development_profile: bool = False
    request_id: EntityId | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        _validate_operation(
            self.expected_lifecycle_revision,
            self.requested_at,
            self.metadata,
            "AgentRuntimePrepareRequest",
            self,
        )


@dataclass(frozen=True, slots=True)
class AgentRuntimeStartRequest:
    operation_id: EntityId
    runtime_id: EntityId
    configuration_id: EntityId
    expected_lifecycle_revision: int
    requested_at: datetime
    initial_pressure: AgentRuntimePressureDeclaration
    allow_development_profile: bool = False
    request_id: EntityId | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        _validate_operation(
            self.expected_lifecycle_revision,
            self.requested_at,
            self.metadata,
            "AgentRuntimeStartRequest",
            self,
        )


@dataclass(frozen=True, slots=True)
class AgentRuntimePressureUpdate:
    operation_id: EntityId
    runtime_id: EntityId
    expected_lifecycle_revision: int
    pressure_state: RuntimePressureState
    assessed_at: datetime
    source_id: EntityId
    reason_codes: Sequence[str] = field(default_factory=tuple)
    limitations: Sequence[str] = field(default_factory=tuple)
    request_id: EntityId | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        _require_pressure_state(
            self.pressure_state,
            "AgentRuntimePressureUpdate.pressure_state",
        )
        require_non_negative_revision(
            self.expected_lifecycle_revision,
            "AgentRuntimePressureUpdate.expected_lifecycle_revision",
        )
        require_aware(self.assessed_at, "AgentRuntimePressureUpdate.assessed_at")
        object.__setattr__(
            self,
            "reason_codes",
            normalize_strings(
                self.reason_codes,
                "AgentRuntimePressureUpdate.reason_codes",
            ),
        )
        object.__setattr__(
            self,
            "limitations",
            normalize_limitations(
                self.limitations,
                "AgentRuntimePressureUpdate.limitations",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(
                self.metadata,
                "AgentRuntimePressureUpdate.metadata",
            ),
        )

    def to_declaration(self) -> AgentRuntimePressureDeclaration:
        return AgentRuntimePressureDeclaration(
            pressure_state=self.pressure_state,
            assessed_at=self.assessed_at,
            source_id=self.source_id,
            reason_codes=self.reason_codes,
            limitations=self.limitations,
            metadata=self.metadata,
        )


@dataclass(frozen=True, slots=True)
class AgentRuntimeResumeRequest:
    operation_id: EntityId
    runtime_id: EntityId
    expected_lifecycle_revision: int
    requested_at: datetime
    current_pressure: AgentRuntimePressureDeclaration
    resume_reason: str
    requested_by_id: EntityId | None = None
    request_id: EntityId | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        _validate_operation(
            self.expected_lifecycle_revision,
            self.requested_at,
            self.metadata,
            "AgentRuntimeResumeRequest",
            self,
        )
        object.__setattr__(
            self,
            "resume_reason",
            require_non_empty(
                self.resume_reason,
                "AgentRuntimeResumeRequest.resume_reason",
            ),
        )


@dataclass(frozen=True, slots=True)
class AgentRuntimeCancellation:
    cancellation_id: EntityId
    operation_id: EntityId
    runtime_id: EntityId
    expected_lifecycle_revision: int
    requested_at: datetime
    cancellation_reason: str
    graceful_shutdown_required: bool
    requested_by_id: EntityId | None = None
    request_id: EntityId | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        _validate_operation(
            self.expected_lifecycle_revision,
            self.requested_at,
            self.metadata,
            "AgentRuntimeCancellation",
            self,
        )
        object.__setattr__(
            self,
            "cancellation_reason",
            require_non_empty(
                self.cancellation_reason,
                "AgentRuntimeCancellation.cancellation_reason",
            ),
        )


@dataclass(frozen=True, slots=True)
class AgentRuntimeStopRequest:
    operation_id: EntityId
    runtime_id: EntityId
    expected_lifecycle_revision: int
    requested_at: datetime
    stop_reason: str
    graceful: bool
    requested_by_id: EntityId | None = None
    request_id: EntityId | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        _validate_operation(
            self.expected_lifecycle_revision,
            self.requested_at,
            self.metadata,
            "AgentRuntimeStopRequest",
            self,
        )
        object.__setattr__(
            self,
            "stop_reason",
            require_non_empty(
                self.stop_reason,
                "AgentRuntimeStopRequest.stop_reason",
            ),
        )


@dataclass(frozen=True, slots=True)
class AgentRuntimeFailure:
    failure_id: EntityId
    operation_id: EntityId
    runtime_id: EntityId
    expected_lifecycle_revision: int
    occurred_at: datetime
    failure_code: str
    description: str
    limitation_ids: Sequence[EntityId] = field(default_factory=tuple)
    request_id: EntityId | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        _validate_operation(
            self.expected_lifecycle_revision,
            self.occurred_at,
            self.metadata,
            "AgentRuntimeFailure",
            self,
        )
        object.__setattr__(
            self,
            "failure_code",
            require_non_empty(
                self.failure_code,
                "AgentRuntimeFailure.failure_code",
            ),
        )
        object.__setattr__(
            self,
            "description",
            require_non_empty(
                self.description,
                "AgentRuntimeFailure.description",
            ),
        )
        object.__setattr__(
            self,
            "limitation_ids",
            normalize_entity_ids(
                self.limitation_ids,
                "AgentRuntimeFailure.limitation_ids",
            ),
        )


def _validate_operation(
    expected_revision: int,
    occurred_at: datetime,
    metadata: Mapping[str, Any],
    contract_name: str,
    instance: object,
) -> None:
    require_non_negative_revision(
        expected_revision,
        f"{contract_name}.expected_lifecycle_revision",
    )
    require_aware(occurred_at, f"{contract_name}.occurred_at")
    object.__setattr__(
        instance,
        "metadata",
        freeze_runtime_metadata(metadata, f"{contract_name}.metadata"),
    )


__all__ = [
    "AgentRuntimeCancellation",
    "AgentRuntimeFailure",
    "AgentRuntimePrepareRequest",
    "AgentRuntimePressureDeclaration",
    "AgentRuntimePressureUpdate",
    "AgentRuntimeResumeRequest",
    "AgentRuntimeStartRequest",
    "AgentRuntimeStopRequest",
]
