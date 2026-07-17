from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.shared.ids import EntityId

from .runtime_contract_validation import freeze_runtime_metadata, normalize_limitations
from .runtime_resource_budget import RuntimeResourceBudget


class RuntimeResourcePriorityClass(StrEnum):
    PRODUCTION_SUBORDINATE = "production_subordinate"
    DEVELOPMENT = "development"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class RuntimeGpuUsePolicy(StrEnum):
    FORBIDDEN = "forbidden"
    ALLOWED_WHEN_IDLE = "allowed_when_idle"
    ALLOWED = "allowed"
    UNKNOWN = "unknown"


class RuntimeOptionalActivityPolicy(StrEnum):
    CONTINUE = "continue"
    REDUCE = "reduce"
    SUSPEND = "suspend"
    DISABLED = "disabled"


class RuntimePressureState(StrEnum):
    NORMAL = "normal"
    ELEVATED = "elevated"
    CRITICAL = "critical"
    RECORDING_SAFETY_UNCERTAIN = "recording_safety_uncertain"
    UNKNOWN = "unknown"


class RuntimePressureAction(StrEnum):
    OPERATE_WITHIN_BUDGETS = "operate_within_budgets"
    REDUCE_OPTIONAL_ACTIVITY = "reduce_optional_activity"
    SUSPEND_OPTIONAL_ACTIVITY = "suspend_optional_activity"
    YIELD_NONESSENTIAL_WORK = "yield_nonessential_work"
    REMAIN_CONSERVATIVE = "remain_conservative"


class RuntimeRecoveryPolicy(StrEnum):
    RESUME_WHEN_NORMAL = "resume_when_normal"
    REQUIRE_EXPLICIT_DECLARATION = "require_explicit_declaration"
    REMAIN_SUSPENDED = "remain_suspended"
    UNKNOWN = "unknown"


_REQUIRED_PRESSURE_ACTIONS = {
    RuntimePressureState.NORMAL: RuntimePressureAction.OPERATE_WITHIN_BUDGETS,
    RuntimePressureState.ELEVATED: RuntimePressureAction.REDUCE_OPTIONAL_ACTIVITY,
    RuntimePressureState.CRITICAL: RuntimePressureAction.SUSPEND_OPTIONAL_ACTIVITY,
    RuntimePressureState.RECORDING_SAFETY_UNCERTAIN: (
        RuntimePressureAction.YIELD_NONESSENTIAL_WORK
    ),
}


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RuntimePressureResponse:
    pressure_state: RuntimePressureState
    action: RuntimePressureAction
    limitations: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        required = _REQUIRED_PRESSURE_ACTIONS.get(self.pressure_state)
        if required is not None and self.action is not required:
            raise ValueError("Runtime pressure response violates production priority.")
        object.__setattr__(
            self,
            "limitations",
            normalize_limitations(
                self.limitations,
                "RuntimePressureResponse.limitations",
            ),
        )


@dataclass(frozen=True, slots=True)
class RuntimeResourcePolicy:
    id: EntityId
    runtime_id: EntityId
    priority_class: RuntimeResourcePriorityClass
    event_mode_behavior: RuntimeOptionalActivityPolicy
    budget: RuntimeResourceBudget
    gpu_use_policy: RuntimeGpuUsePolicy
    optional_activity_policy: RuntimeOptionalActivityPolicy
    pressure_responses: Sequence[RuntimePressureResponse]
    recovery_policy: RuntimeRecoveryPolicy
    limitations: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        by_state = {response.pressure_state: response for response in self.pressure_responses}
        missing = set(_REQUIRED_PRESSURE_ACTIONS) - set(by_state)
        if missing:
            raise ValueError("Runtime resource policy requires all production pressure states.")
        if len(by_state) != len(self.pressure_responses):
            raise ValueError("Runtime resource policy pressure states must be unique.")
        object.__setattr__(
            self,
            "pressure_responses",
            tuple(by_state[state] for state in sorted(by_state, key=lambda value: value.value)),
        )
        object.__setattr__(
            self,
            "limitations",
            normalize_limitations(
                self.limitations,
                "RuntimeResourcePolicy.limitations",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(self.metadata, "RuntimeResourcePolicy.metadata"),
        )
