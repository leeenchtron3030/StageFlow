from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.shared.ids import EntityId

from .runtime_contract_validation import (
    freeze_runtime_metadata,
    normalize_entity_ids,
    require_non_empty,
    require_optional_aware,
)


class RuntimeLimitationSeverity(StrEnum):
    INFORMATIONAL = "informational"
    NON_BLOCKING = "non_blocking"
    BLOCKING = "blocking"
    UNKNOWN = "unknown"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RuntimeLimitation:
    id: EntityId
    runtime_id: EntityId
    code: str
    severity: RuntimeLimitationSeverity
    description: str
    affected_capability_ids: Sequence[EntityId] = field(default_factory=tuple)
    affected_collection_plan_ids: Sequence[EntityId] = field(default_factory=tuple)
    introduced_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "code",
            require_non_empty(self.code, "RuntimeLimitation.code"),
        )
        object.__setattr__(
            self,
            "description",
            require_non_empty(self.description, "RuntimeLimitation.description"),
        )
        require_optional_aware(self.introduced_at, "RuntimeLimitation.introduced_at")
        object.__setattr__(
            self,
            "affected_capability_ids",
            normalize_entity_ids(
                self.affected_capability_ids,
                "RuntimeLimitation.affected_capability_ids",
            ),
        )
        object.__setattr__(
            self,
            "affected_collection_plan_ids",
            normalize_entity_ids(
                self.affected_collection_plan_ids,
                "RuntimeLimitation.affected_collection_plan_ids",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(self.metadata, "RuntimeLimitation.metadata"),
        )
