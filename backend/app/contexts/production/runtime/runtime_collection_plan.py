from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.shared.ids import EntityId

from .runtime_collection_target import RuntimeCollectionTarget
from .runtime_contract_validation import (
    freeze_runtime_metadata,
    normalize_entity_ids,
    normalize_enum_values,
    normalize_limitations,
    require_non_empty,
    require_optional_aware,
)
from .runtime_observation_capability import RuntimeCollectionMode


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RuntimeCollectionPlan:
    id: EntityId
    runtime_id: EntityId
    plan_version: str
    enabled: bool
    targets: Sequence[RuntimeCollectionTarget]
    observation_capability_ids: Sequence[EntityId]
    collection_modes: Sequence[RuntimeCollectionMode]
    readiness_policy_selection_id: EntityId
    resource_policy_id: EntityId
    event_mode_id: EntityId
    starts_at: datetime | None = None
    stops_at: datetime | None = None
    limitations: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "plan_version",
            require_non_empty(self.plan_version, "RuntimeCollectionPlan.plan_version"),
        )
        require_optional_aware(self.starts_at, "RuntimeCollectionPlan.starts_at")
        require_optional_aware(self.stops_at, "RuntimeCollectionPlan.stops_at")
        if (
            self.starts_at is not None
            and self.stops_at is not None
            and self.stops_at <= self.starts_at
        ):
            raise ValueError("Runtime collection-plan boundary must be positive.")
        object.__setattr__(
            self,
            "targets",
            tuple(sorted(self.targets, key=lambda target: target.id.value)),
        )
        object.__setattr__(
            self,
            "observation_capability_ids",
            normalize_entity_ids(
                self.observation_capability_ids,
                "RuntimeCollectionPlan.observation_capability_ids",
            ),
        )
        object.__setattr__(
            self,
            "collection_modes",
            normalize_enum_values(self.collection_modes),
        )
        if self.enabled and (not self.targets or not self.observation_capability_ids):
            raise ValueError("Enabled collection plan requires targets and capabilities.")
        object.__setattr__(
            self,
            "limitations",
            normalize_limitations(
                self.limitations,
                "RuntimeCollectionPlan.limitations",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(self.metadata, "RuntimeCollectionPlan.metadata"),
        )
