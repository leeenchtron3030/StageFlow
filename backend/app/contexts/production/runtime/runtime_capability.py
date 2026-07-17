from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.shared.ids import EntityId

from .runtime_contract_validation import (
    freeze_runtime_metadata,
    normalize_limitations,
    require_non_empty,
)


class RuntimeCapabilitySupportStatus(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class RuntimeCapabilityKind(StrEnum):
    CANDIDATE_DISCOVERY = "candidate_discovery"
    RESOURCE_SNAPSHOT_COLLECTION = "resource_snapshot_collection"
    FINALIZATION_OBSERVATION_COLLECTION = "finalization_observation_collection"
    WRITE_STATE_OBSERVATION_COLLECTION = "write_state_observation_collection"
    READ_ACCESS_OBSERVATION_COLLECTION = "read_access_observation_collection"
    RESOURCE_PRESENCE_OBSERVATION_COLLECTION = "resource_presence_observation_collection"
    STABLE_RESOURCE_IDENTITY = "stable_resource_identity"
    RECORDER_FINALIZATION_INTEGRATION = "recorder_finalization_integration"
    ATOMIC_RENAME_OBSERVATION = "atomic_rename_observation"
    COMPLETION_MARKER_OBSERVATION = "completion_marker_observation"
    MANUAL_DECLARATION_INPUT = "manual_declaration_input"
    COMPLETED_ASSET_ASSEMBLY = "completed_asset_assembly"
    LOCAL_FILESYSTEM_ACCESS = "local_filesystem_access"
    MOUNTED_VOLUME_ACCESS = "mounted_volume_access"
    NETWORK_SHARE_ACCESS = "network_share_access"
    MEDIA_HEADER_ACCESS = "media_header_access"
    CHECKSUM_SUPPLY = "checksum_supply"
    RESOURCE_PRESSURE_AWARENESS = "resource_pressure_awareness"
    EVENT_MODE_SUPPORT = "event_mode_support"
    OPTIONAL_ACTIVITY_SUSPENSION = "optional_activity_suspension"
    HEALTH_REPORTING = "health_reporting"


def _empty_mapping() -> Mapping[str, Any]:
    return {}


def _require_approved_kind(value: object) -> None:
    if not isinstance(value, RuntimeCapabilityKind):
        raise ValueError("Runtime capability kind is not approved by ED-0050.")


def _require_approved_status(value: object) -> None:
    if not isinstance(value, RuntimeCapabilitySupportStatus):
        raise ValueError("Runtime capability support status is not approved.")


@dataclass(frozen=True, slots=True)
class RuntimeCapability:
    id: EntityId
    runtime_id: EntityId
    kind: RuntimeCapabilityKind
    support_status: RuntimeCapabilitySupportStatus
    capability_version: str
    scope: str
    provider_or_adapter_id: EntityId | None = None
    limitations: Sequence[str] = field(default_factory=tuple)
    parameters: Mapping[str, Any] = field(default_factory=_empty_mapping)
    metadata: Mapping[str, Any] = field(default_factory=_empty_mapping)

    def __post_init__(self) -> None:
        _require_approved_kind(self.kind)
        _require_approved_status(self.support_status)
        object.__setattr__(
            self,
            "capability_version",
            require_non_empty(
                self.capability_version,
                "RuntimeCapability.capability_version",
            ),
        )
        object.__setattr__(
            self,
            "scope",
            require_non_empty(self.scope, "RuntimeCapability.scope"),
        )
        limitations = normalize_limitations(
            self.limitations,
            "RuntimeCapability.limitations",
        )
        if (
            self.support_status is RuntimeCapabilitySupportStatus.DEGRADED
            and not limitations
        ):
            raise ValueError("A degraded Runtime capability requires a limitation.")
        object.__setattr__(self, "limitations", limitations)
        object.__setattr__(
            self,
            "parameters",
            freeze_runtime_metadata(self.parameters, "RuntimeCapability.parameters"),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(self.metadata, "RuntimeCapability.metadata"),
        )
