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
    normalize_limitations,
    normalize_strings,
    require_aware,
)
from .runtime_health import RuntimeDeclaredComponentStatus


class RuntimeAvailabilityStatus(StrEnum):
    AVAILABLE = "available"
    LIMITED = "limited"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RuntimeAvailability:
    id: EntityId
    runtime_id: EntityId
    status: RuntimeAvailabilityStatus
    declared_at: datetime
    reason_codes: Sequence[str]
    expected_capability_availability: RuntimeDeclaredComponentStatus
    event_mode_compatible: bool
    limitation_ids: Sequence[EntityId] = field(default_factory=tuple)
    limitations: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware(self.declared_at, "RuntimeAvailability.declared_at")
        object.__setattr__(
            self,
            "reason_codes",
            normalize_strings(self.reason_codes, "RuntimeAvailability.reason_codes"),
        )
        object.__setattr__(
            self,
            "limitation_ids",
            normalize_entity_ids(
                self.limitation_ids,
                "RuntimeAvailability.limitation_ids",
            ),
        )
        object.__setattr__(
            self,
            "limitations",
            normalize_limitations(
                self.limitations,
                "RuntimeAvailability.limitations",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(self.metadata, "RuntimeAvailability.metadata"),
        )
