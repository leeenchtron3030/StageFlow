from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from app.shared.ids import EntityId

from .runtime_contract_validation import (
    freeze_runtime_metadata,
    require_optional_non_negative_int,
    require_optional_percentage,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RuntimeResourceBudget:
    id: EntityId
    runtime_id: EntityId
    maximum_cpu_utilization_percentage: float | None = None
    maximum_memory_allocation_bytes: int | None = None
    maximum_disk_read_bytes_per_second: int | None = None
    maximum_disk_write_bytes_per_second: int | None = None
    maximum_network_bytes_per_second: int | None = None
    maximum_concurrent_candidate_assessments: int | None = None
    maximum_concurrent_read_access_checks: int | None = None
    maximum_collections_per_minute: int | None = None
    burst_allowance: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_optional_percentage(
            self.maximum_cpu_utilization_percentage,
            "RuntimeResourceBudget.maximum_cpu_utilization_percentage",
        )
        for field_name in (
            "maximum_memory_allocation_bytes",
            "maximum_disk_read_bytes_per_second",
            "maximum_disk_write_bytes_per_second",
            "maximum_network_bytes_per_second",
            "maximum_concurrent_candidate_assessments",
            "maximum_concurrent_read_access_checks",
            "maximum_collections_per_minute",
            "burst_allowance",
        ):
            require_optional_non_negative_int(
                getattr(self, field_name),
                f"RuntimeResourceBudget.{field_name}",
            )
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(self.metadata, "RuntimeResourceBudget.metadata"),
        )
