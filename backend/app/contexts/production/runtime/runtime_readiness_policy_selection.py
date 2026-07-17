from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.contexts.production.asset_readiness import AssetReadinessPolicyParameters
from app.shared.ids import EntityId

from .runtime_contract_validation import (
    freeze_runtime_metadata,
    normalize_entity_ids,
    normalize_limitations,
    require_non_empty,
)


class RuntimeReadinessRoute(StrEnum):
    STRONG_FINALIZATION = "strong_finalization"
    STABILITY_DERIVED = "stability_derived"
    STRONG_THEN_STABILITY = "strong_then_stability"
    DISABLED = "disabled"


class RuntimeReadinessFallback(StrEnum):
    NO_FALLBACK = "no_fallback"
    USE_STABILITY_ROUTE = "use_stability_route"
    REMAIN_INSUFFICIENT = "remain_insufficient"
    DISABLE_CANDIDATE = "disable_candidate"
    UNKNOWN = "unknown"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RuntimeReadinessPolicySelection:
    id: EntityId
    runtime_id: EntityId
    readiness_capability_id: EntityId
    policy_id: EntityId
    policy_version: str
    policy_parameters: AssetReadinessPolicyParameters
    selected_route: RuntimeReadinessRoute
    required_capability_ids: Sequence[EntityId]
    optional_capability_ids: Sequence[EntityId]
    fallback_behavior: RuntimeReadinessFallback
    limitations: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        version = require_non_empty(
            self.policy_version,
            "RuntimeReadinessPolicySelection.policy_version",
        )
        if version != self.policy_parameters.policy_version:
            raise ValueError("Readiness selection and ED-0049 parameter versions must match.")
        object.__setattr__(self, "policy_version", version)
        object.__setattr__(
            self,
            "required_capability_ids",
            normalize_entity_ids(
                self.required_capability_ids,
                "RuntimeReadinessPolicySelection.required_capability_ids",
            ),
        )
        object.__setattr__(
            self,
            "optional_capability_ids",
            normalize_entity_ids(
                self.optional_capability_ids,
                "RuntimeReadinessPolicySelection.optional_capability_ids",
            ),
        )
        if set(self.required_capability_ids) & set(self.optional_capability_ids):
            raise ValueError("Readiness capability IDs cannot be required and optional.")
        object.__setattr__(
            self,
            "limitations",
            normalize_limitations(
                self.limitations,
                "RuntimeReadinessPolicySelection.limitations",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(
                self.metadata,
                "RuntimeReadinessPolicySelection.metadata",
            ),
        )
