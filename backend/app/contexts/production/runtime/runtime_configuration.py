from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.shared.ids import EntityId

from .runtime_asset_assembly_plan import RuntimeAssetAssemblyPlan
from .runtime_capability_set import RuntimeCapabilitySet
from .runtime_collection_plan import RuntimeCollectionPlan
from .runtime_contract_validation import (
    freeze_runtime_metadata,
    require_aware,
    require_non_empty,
)
from .runtime_event_mode import RuntimeEventMode
from .runtime_health import RuntimeHealthReportingPolicy
from .runtime_readiness_policy_selection import RuntimeReadinessPolicySelection
from .runtime_resource_policy import RuntimeResourcePolicy


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RuntimeConfiguration:
    id: EntityId
    runtime_id: EntityId
    configuration_schema_version: str
    enabled: bool
    event_mode: RuntimeEventMode
    capability_set: RuntimeCapabilitySet
    collection_plans: Sequence[RuntimeCollectionPlan]
    readiness_policy_selections: Sequence[RuntimeReadinessPolicySelection]
    asset_assembly_plans: Sequence[RuntimeAssetAssemblyPlan]
    resource_policy: RuntimeResourcePolicy
    health_reporting_policy: RuntimeHealthReportingPolicy
    configured_at: datetime
    configured_by_id: EntityId | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware(self.configured_at, "RuntimeConfiguration.configured_at")
        object.__setattr__(
            self,
            "configuration_schema_version",
            require_non_empty(
                self.configuration_schema_version,
                "RuntimeConfiguration.configuration_schema_version",
            ),
        )
        object.__setattr__(
            self,
            "collection_plans",
            tuple(sorted(self.collection_plans, key=lambda value: value.id.value)),
        )
        object.__setattr__(
            self,
            "readiness_policy_selections",
            tuple(
                sorted(
                    self.readiness_policy_selections,
                    key=lambda value: value.id.value,
                )
            ),
        )
        object.__setattr__(
            self,
            "asset_assembly_plans",
            tuple(sorted(self.asset_assembly_plans, key=lambda value: value.id.value)),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(self.metadata, "RuntimeConfiguration.metadata"),
        )
