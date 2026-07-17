from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.contexts.production.completed_media_asset import (
    CompletedMediaAssetCompletionMethod,
)
from app.shared.ids import EntityId

from .runtime_contract_validation import (
    freeze_runtime_metadata,
    normalize_entity_ids,
    normalize_enum_values,
    normalize_limitations,
    normalize_strings,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RuntimeReadinessCapability:
    id: EntityId
    runtime_id: EntityId
    supporting_capability_ids: Sequence[EntityId]
    supported_finalization_methods: Sequence[CompletedMediaAssetCompletionMethod]
    snapshot_support: bool
    write_state_support: bool
    read_access_support: bool
    presence_support: bool
    stable_identity_support: bool
    supported_policy_ids: Sequence[EntityId]
    supported_policy_versions: Sequence[str]
    limitations: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "supporting_capability_ids",
            normalize_entity_ids(
                self.supporting_capability_ids,
                "RuntimeReadinessCapability.supporting_capability_ids",
            ),
        )
        object.__setattr__(
            self,
            "supported_finalization_methods",
            normalize_enum_values(self.supported_finalization_methods),
        )
        policy_ids = normalize_entity_ids(
            self.supported_policy_ids,
            "RuntimeReadinessCapability.supported_policy_ids",
        )
        versions = normalize_strings(
            self.supported_policy_versions,
            "RuntimeReadinessCapability.supported_policy_versions",
        )
        if not policy_ids or not versions:
            raise ValueError("Readiness capability requires supported policy IDs and versions.")
        object.__setattr__(self, "supported_policy_ids", policy_ids)
        object.__setattr__(self, "supported_policy_versions", versions)
        object.__setattr__(
            self,
            "limitations",
            normalize_limitations(
                self.limitations,
                "RuntimeReadinessCapability.limitations",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(self.metadata, "RuntimeReadinessCapability.metadata"),
        )
