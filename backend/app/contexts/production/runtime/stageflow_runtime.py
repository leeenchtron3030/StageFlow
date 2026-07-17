from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .runtime_asset_assembly_plan import RuntimeAssetAssemblyPlan
from .runtime_availability import RuntimeAvailability
from .runtime_capability_set import RuntimeCapabilitySet
from .runtime_collection_plan import RuntimeCollectionPlan
from .runtime_configuration import RuntimeConfiguration
from .runtime_contract_validation import freeze_runtime_metadata, require_aware
from .runtime_event_mode import RuntimeEventMode
from .runtime_health import RuntimeHealth
from .runtime_host import RuntimeHost
from .runtime_identity import RuntimeIdentity
from .runtime_limitation import RuntimeLimitation
from .runtime_profile import RuntimeProfile
from .runtime_readiness_policy_selection import RuntimeReadinessPolicySelection
from .runtime_resource_policy import RuntimeResourcePolicy
from .runtime_version import RuntimeVersion


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class StageFlowRuntime:
    identity: RuntimeIdentity
    profile: RuntimeProfile
    software_version: RuntimeVersion
    host: RuntimeHost
    configuration: RuntimeConfiguration
    capability_set: RuntimeCapabilitySet
    resource_policy: RuntimeResourcePolicy
    event_mode: RuntimeEventMode
    collection_plans: Sequence[RuntimeCollectionPlan]
    readiness_policy_selections: Sequence[RuntimeReadinessPolicySelection]
    asset_assembly_plans: Sequence[RuntimeAssetAssemblyPlan]
    health: RuntimeHealth
    availability: RuntimeAvailability
    limitations: Sequence[RuntimeLimitation]
    configured_at: datetime
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware(self.configured_at, "StageFlowRuntime.configured_at")
        for field_name in (
            "collection_plans",
            "readiness_policy_selections",
            "asset_assembly_plans",
            "limitations",
        ):
            object.__setattr__(
                self,
                field_name,
                tuple(
                    sorted(
                        getattr(self, field_name),
                        key=lambda value: value.id.value,
                    )
                ),
            )
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(self.metadata, "StageFlowRuntime.metadata"),
        )
