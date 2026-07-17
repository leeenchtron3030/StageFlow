from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.shared.ids import EntityId

from .runtime_contract_validation import (
    freeze_runtime_metadata,
    normalize_entity_ids,
    require_non_empty,
)
from .runtime_profile import RuntimeProfile


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RuntimeIdentity:
    runtime_id: EntityId
    logical_name: str
    deployment_profile: RuntimeProfile
    host_id: EntityId
    installation_id: EntityId | None = None
    organization_id: EntityId | None = None
    event_deployment_id: EntityId | None = None
    configured_stage_ids: Sequence[EntityId] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "logical_name",
            require_non_empty(self.logical_name, "RuntimeIdentity.logical_name"),
        )
        object.__setattr__(
            self,
            "configured_stage_ids",
            normalize_entity_ids(
                self.configured_stage_ids,
                "RuntimeIdentity.configured_stage_ids",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(self.metadata, "RuntimeIdentity.metadata"),
        )
