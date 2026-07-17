from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.shared.ids import EntityId

from .runtime_contract_validation import (
    freeze_runtime_metadata,
    normalize_entity_ids,
    normalize_strings,
    require_optional_non_empty,
    require_optional_positive_int,
)


class RuntimePowerSourceType(StrEnum):
    MAINS = "mains"
    BATTERY = "battery"
    UNINTERRUPTIBLE_POWER_SUPPLY = "uninterruptible_power_supply"
    MIXED = "mixed"
    UNKNOWN = "unknown"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RuntimeHost:
    host_id: EntityId
    host_name: str | None = None
    operating_system_family: str | None = None
    operating_system_version: str | None = None
    architecture: str | None = None
    cpu_logical_count: int | None = None
    memory_capacity_bytes: int | None = None
    gpu_identifiers: Sequence[str] = field(default_factory=tuple)
    local_volume_ids: Sequence[EntityId] = field(default_factory=tuple)
    network_interface_ids: Sequence[EntityId] = field(default_factory=tuple)
    power_source_type: RuntimePowerSourceType = RuntimePowerSourceType.UNKNOWN
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        for field_name in (
            "host_name",
            "operating_system_family",
            "operating_system_version",
            "architecture",
        ):
            object.__setattr__(
                self,
                field_name,
                require_optional_non_empty(
                    getattr(self, field_name),
                    f"RuntimeHost.{field_name}",
                ),
            )
        require_optional_positive_int(
            self.cpu_logical_count,
            "RuntimeHost.cpu_logical_count",
        )
        require_optional_positive_int(
            self.memory_capacity_bytes,
            "RuntimeHost.memory_capacity_bytes",
        )
        object.__setattr__(
            self,
            "gpu_identifiers",
            normalize_strings(self.gpu_identifiers, "RuntimeHost.gpu_identifiers"),
        )
        object.__setattr__(
            self,
            "local_volume_ids",
            normalize_entity_ids(self.local_volume_ids, "RuntimeHost.local_volume_ids"),
        )
        object.__setattr__(
            self,
            "network_interface_ids",
            normalize_entity_ids(
                self.network_interface_ids,
                "RuntimeHost.network_interface_ids",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(self.metadata, "RuntimeHost.metadata"),
        )
