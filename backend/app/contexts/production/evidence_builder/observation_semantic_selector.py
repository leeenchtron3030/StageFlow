from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.contexts.production.observation import Observation, ObservationType
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata

from .observation_semantic_selection import (
    ObservationSemanticSelection,
    ObservationSemanticSelectionStatus,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class ObservationSemanticSelector:
    """Selects structured semantic values from accepted Observation types."""

    accepted_observation_types: Sequence[ObservationType]
    semantic_keys: Sequence[str]
    selector_id: EntityId | None = None
    normalize_values: bool = True
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.accepted_observation_types:
            raise ValueError("ObservationSemanticSelector requires accepted types.")
        if not self.semantic_keys:
            raise ValueError("ObservationSemanticSelector requires semantic keys.")
        for key in self.semantic_keys:
            if not key.strip():
                raise ValueError("ObservationSemanticSelector semantic keys must be non-empty.")
        object.__setattr__(
            self,
            "accepted_observation_types",
            tuple(self.accepted_observation_types),
        )
        object.__setattr__(self, "semantic_keys", tuple(self.semantic_keys))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def select(
        self,
        observation: Observation,
        *,
        supported_values: Collection[str] | None = None,
        duplicate: bool = False,
    ) -> ObservationSemanticSelection:
        if duplicate:
            return ObservationSemanticSelection(
                observation_id=observation.id,
                status=ObservationSemanticSelectionStatus.DUPLICATE,
                matched_observation_type=observation.observation_type,
                rationale="Observation ID already processed in this build invocation.",
            )

        if observation.observation_type not in self.accepted_observation_types:
            return ObservationSemanticSelection(
                observation_id=observation.id,
                status=ObservationSemanticSelectionStatus.IGNORED_OBSERVATION_TYPE,
                matched_observation_type=observation.observation_type,
                rationale="Observation type is outside this builder domain.",
            )

        for semantic_key in self.semantic_keys:
            if semantic_key not in observation.metadata:
                continue
            raw_value = observation.metadata[semantic_key]
            normalized_value = self.normalize(raw_value)
            if normalized_value is None:
                continue
            if supported_values is not None and normalized_value not in supported_values:
                return ObservationSemanticSelection(
                    observation_id=observation.id,
                    status=ObservationSemanticSelectionStatus.UNSUPPORTED_SEMANTIC_VALUE,
                    matched_observation_type=observation.observation_type,
                    matched_semantic_key=semantic_key,
                    raw_semantic_value=raw_value,
                    normalized_semantic_value=normalized_value,
                    rationale="Structured semantic value is not supported by this builder.",
                )
            return ObservationSemanticSelection(
                observation_id=observation.id,
                status=ObservationSemanticSelectionStatus.SELECTED,
                matched_observation_type=observation.observation_type,
                matched_semantic_key=semantic_key,
                raw_semantic_value=raw_value,
                normalized_semantic_value=normalized_value,
                rationale="Structured semantic value selected.",
            )

        return ObservationSemanticSelection(
            observation_id=observation.id,
            status=ObservationSemanticSelectionStatus.MISSING_SEMANTIC_VALUE,
            matched_observation_type=observation.observation_type,
            rationale="No configured structured semantic key was present.",
        )

    def normalize(self, raw_value: Any) -> str | None:
        if raw_value is None:
            return None
        if isinstance(raw_value, str):
            value = raw_value.strip()
        else:
            value = str(raw_value).strip()
        if not value:
            return None
        if not self.normalize_values:
            return value
        return value.lower().replace("-", "_").replace(" ", "_")
