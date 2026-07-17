from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.shared.ids import EntityId

from .runtime_contract_validation import (
    freeze_runtime_metadata,
    normalize_limitations,
    require_optional_aware,
)
from .runtime_resource_policy import RuntimeOptionalActivityPolicy


class RuntimeEventModeKind(StrEnum):
    EVENT = "event"
    DEVELOPMENT = "development"
    MAINTENANCE = "maintenance"
    DISABLED = "disabled"


class RuntimeNetworkPolicy(StrEnum):
    OFFLINE_CAPABLE = "offline_capable"
    LOCAL_NETWORK_ONLY = "local_network_only"
    NETWORK_OPTIONAL = "network_optional"
    NETWORK_REQUIRED = "network_required"
    DISABLED = "disabled"


class RuntimeAssetRetentionExpectation(StrEnum):
    SOURCE_OWNED_NO_CHANGE = "source_owned_no_change"
    RETAIN_SOURCE_REFERENCE = "retain_source_reference"
    UNSPECIFIED = "unspecified"


class RuntimeManualOverrideStatus(StrEnum):
    NOT_ALLOWED = "not_allowed"
    INACTIVE = "inactive"
    DECLARED_ACTIVE = "declared_active"
    UNKNOWN = "unknown"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RuntimeEventMode:
    id: EntityId
    runtime_id: EntityId
    mode: RuntimeEventModeKind
    enabled: bool
    production_subordinate_requirement: bool
    optional_activity_behavior: RuntimeOptionalActivityPolicy
    network_policy: RuntimeNetworkPolicy
    asset_retention_expectation: RuntimeAssetRetentionExpectation
    manual_override_status: RuntimeManualOverrideStatus
    event_deployment_id: EntityId | None = None
    active_from: datetime | None = None
    active_until: datetime | None = None
    limitations: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_optional_aware(self.active_from, "RuntimeEventMode.active_from")
        require_optional_aware(self.active_until, "RuntimeEventMode.active_until")
        if (
            self.active_from is not None
            and self.active_until is not None
            and self.active_until <= self.active_from
        ):
            raise ValueError("Runtime event-mode active window must be positive.")
        object.__setattr__(
            self,
            "limitations",
            normalize_limitations(self.limitations, "RuntimeEventMode.limitations"),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(self.metadata, "RuntimeEventMode.metadata"),
        )
