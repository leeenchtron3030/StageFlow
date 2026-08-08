from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.contexts.production.observation import ObservationType
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata


def _empty_metadata() -> Mapping[str, Any]:
    return {}


class ObservationSemanticSelectionStatus(StrEnum):
    """Outcome of structured semantic selection for one Observation."""

    SELECTED = "selected"
    IGNORED_OBSERVATION_TYPE = "ignored_observation_type"
    MISSING_SEMANTIC_VALUE = "missing_semantic_value"
    UNSUPPORTED_SEMANTIC_VALUE = "unsupported_semantic_value"
    DUPLICATE = "duplicate"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ObservationSemanticSelection:
    """Result of selecting structured semantic meaning from one Observation."""

    observation_id: EntityId
    status: ObservationSemanticSelectionStatus
    matched_observation_type: ObservationType | None = None
    matched_semantic_key: str | None = None
    raw_semantic_value: Any | None = None
    normalized_semantic_value: str | None = None
    rationale: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
