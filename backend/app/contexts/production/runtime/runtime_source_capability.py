from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.shared.ids import EntityId

from .runtime_contract_validation import (
    freeze_runtime_metadata,
    normalize_entity_ids,
    normalize_enum_values,
    normalize_limitations,
)


class RuntimeSourceLocationScheme(StrEnum):
    LOCAL_FILE = "local_file"
    MOUNTED_VOLUME = "mounted_volume"
    NETWORK_SHARE = "network_share"
    EXTERNAL_REFERENCE = "external_reference"
    UNKNOWN = "unknown"


class RuntimeSourceHostScope(StrEnum):
    LOCAL_HOST = "local_host"
    CONFIGURED_HOSTS = "configured_hosts"
    ANY_DECLARED_HOST = "any_declared_host"
    UNKNOWN = "unknown"


class RuntimeSourceAccessMode(StrEnum):
    READ_ONLY = "read_only"
    READ_WRITE_DECLARED = "read_write_declared"
    UNKNOWN = "unknown"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RuntimeSourceCapability:
    id: EntityId
    runtime_id: EntityId
    runtime_capability_id: EntityId
    supported_location_schemes: Sequence[RuntimeSourceLocationScheme]
    supported_host_scope: RuntimeSourceHostScope
    access_mode: RuntimeSourceAccessMode
    supported_host_ids: Sequence[EntityId] = field(default_factory=tuple)
    supported_volume_ids: Sequence[EntityId] = field(default_factory=tuple)
    source_adapter_id: EntityId | None = None
    recorder_application_ids: Sequence[EntityId] = field(default_factory=tuple)
    limitations: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        schemes = normalize_enum_values(self.supported_location_schemes)
        if not schemes:
            raise ValueError("Runtime source capability requires a location scheme.")
        object.__setattr__(self, "supported_location_schemes", schemes)
        object.__setattr__(
            self,
            "supported_host_ids",
            normalize_entity_ids(
                self.supported_host_ids,
                "RuntimeSourceCapability.supported_host_ids",
            ),
        )
        if (
            self.supported_host_scope is RuntimeSourceHostScope.CONFIGURED_HOSTS
            and not self.supported_host_ids
        ):
            raise ValueError("Configured-host scope requires at least one host ID.")
        object.__setattr__(
            self,
            "supported_volume_ids",
            normalize_entity_ids(
                self.supported_volume_ids,
                "RuntimeSourceCapability.supported_volume_ids",
            ),
        )
        object.__setattr__(
            self,
            "recorder_application_ids",
            normalize_entity_ids(
                self.recorder_application_ids,
                "RuntimeSourceCapability.recorder_application_ids",
            ),
        )
        object.__setattr__(
            self,
            "limitations",
            normalize_limitations(
                self.limitations,
                "RuntimeSourceCapability.limitations",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(self.metadata, "RuntimeSourceCapability.metadata"),
        )
