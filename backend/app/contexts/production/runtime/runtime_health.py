from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from app.shared.ids import EntityId

from .runtime_contract_validation import (
    freeze_runtime_metadata,
    normalize_entity_ids,
    normalize_strings,
    require_aware,
    require_optional_positive_duration,
)


class RuntimeHealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class RuntimeConfigurationValidity(StrEnum):
    VALID = "valid"
    VALID_WITH_LIMITATIONS = "valid_with_limitations"
    INVALID = "invalid"
    UNKNOWN = "unknown"


class RuntimeDeclaredComponentStatus(StrEnum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RuntimeHealthReportingPolicy:
    id: EntityId
    runtime_id: EntityId
    enabled: bool
    expected_reporting_interval: timedelta | None = None
    include_capability_detail: bool = True
    include_resource_policy_detail: bool = True
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_optional_positive_duration(
            self.expected_reporting_interval,
            "RuntimeHealthReportingPolicy.expected_reporting_interval",
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(
                self.metadata,
                "RuntimeHealthReportingPolicy.metadata",
            ),
        )


@dataclass(frozen=True, slots=True)
class RuntimeHealth:
    id: EntityId
    runtime_id: EntityId
    status: RuntimeHealthStatus
    assessed_at: datetime
    configuration_validity: RuntimeConfigurationValidity
    capability_availability: RuntimeDeclaredComponentStatus
    resource_policy_availability: RuntimeDeclaredComponentStatus
    collection_plan_validity: RuntimeDeclaredComponentStatus
    limitation_ids: Sequence[EntityId] = field(default_factory=tuple)
    reason_codes: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware(self.assessed_at, "RuntimeHealth.assessed_at")
        object.__setattr__(
            self,
            "limitation_ids",
            normalize_entity_ids(self.limitation_ids, "RuntimeHealth.limitation_ids"),
        )
        object.__setattr__(
            self,
            "reason_codes",
            normalize_strings(self.reason_codes, "RuntimeHealth.reason_codes"),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(self.metadata, "RuntimeHealth.metadata"),
        )
