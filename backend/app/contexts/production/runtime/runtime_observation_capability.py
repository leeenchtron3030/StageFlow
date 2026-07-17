from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum
from typing import Any

from app.shared.ids import EntityId

from .runtime_contract_validation import (
    freeze_runtime_metadata,
    normalize_enum_values,
    normalize_limitations,
    require_optional_positive_duration,
)
from .runtime_source_capability import RuntimeSourceLocationScheme


class RuntimeObservationType(StrEnum):
    RESOURCE_SNAPSHOT = "resource_snapshot"
    FINALIZATION = "finalization"
    WRITE_STATE = "write_state"
    READ_ACCESS = "read_access"
    RESOURCE_PRESENCE = "resource_presence"


class RuntimeCollectionMode(StrEnum):
    EVENT_DRIVEN = "event_driven"
    SCHEDULED_SAMPLING = "scheduled_sampling"
    EXTERNAL_NOTIFICATION = "external_notification"
    MANUAL_INPUT = "manual_input"
    SUPPLIED_BY_ADAPTER = "supplied_by_adapter"
    UNKNOWN = "unknown"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RuntimeObservationCapability:
    id: EntityId
    runtime_id: EntityId
    runtime_capability_id: EntityId
    observation_type: RuntimeObservationType
    collector_or_adapter_id: EntityId
    supported_source_schemes: Sequence[RuntimeSourceLocationScheme]
    collection_mode: RuntimeCollectionMode
    timing_precision: timedelta | None = None
    stable_identity_support: bool = False
    limitations: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        schemes = normalize_enum_values(self.supported_source_schemes)
        if not schemes:
            raise ValueError("Observation capability requires a supported source scheme.")
        object.__setattr__(self, "supported_source_schemes", schemes)
        require_optional_positive_duration(
            self.timing_precision,
            "RuntimeObservationCapability.timing_precision",
        )
        object.__setattr__(
            self,
            "limitations",
            normalize_limitations(
                self.limitations,
                "RuntimeObservationCapability.limitations",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_runtime_metadata(
                self.metadata,
                "RuntimeObservationCapability.metadata",
            ),
        )
