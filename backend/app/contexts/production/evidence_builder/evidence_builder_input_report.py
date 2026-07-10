from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.shared.ids import EntityId

from .observation_semantic_selection import (
    ObservationSemanticSelection,
    ObservationSemanticSelectionStatus,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class EvidenceBuilderInputReport:
    """Generic ID-only report for Evidence Builder input classification."""

    recognized_observation_ids: Sequence[EntityId]
    ignored_observation_ids: Sequence[EntityId]
    unsupported_observation_ids: Sequence[EntityId]
    duplicate_observation_ids: Sequence[EntityId]
    selections: Sequence[ObservationSemanticSelection] = field(default_factory=tuple)
    applied_rule_ids: Sequence[EntityId] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "recognized_observation_ids",
            tuple(self.recognized_observation_ids),
        )
        object.__setattr__(self, "ignored_observation_ids", tuple(self.ignored_observation_ids))
        object.__setattr__(
            self,
            "unsupported_observation_ids",
            tuple(self.unsupported_observation_ids),
        )
        object.__setattr__(
            self,
            "duplicate_observation_ids",
            tuple(self.duplicate_observation_ids),
        )
        object.__setattr__(self, "selections", tuple(self.selections))
        object.__setattr__(self, "applied_rule_ids", tuple(self.applied_rule_ids))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @classmethod
    def from_selections(
        cls,
        selections: Sequence[ObservationSemanticSelection],
        *,
        applied_rule_ids: Sequence[EntityId] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> EvidenceBuilderInputReport:
        selection_tuple = tuple(selections)
        return cls(
            recognized_observation_ids=tuple(
                selection.observation_id
                for selection in selection_tuple
                if selection.status is ObservationSemanticSelectionStatus.SELECTED
            ),
            ignored_observation_ids=tuple(
                selection.observation_id
                for selection in selection_tuple
                if selection.status
                is ObservationSemanticSelectionStatus.IGNORED_OBSERVATION_TYPE
            ),
            unsupported_observation_ids=tuple(
                selection.observation_id
                for selection in selection_tuple
                if selection.status
                in {
                    ObservationSemanticSelectionStatus.MISSING_SEMANTIC_VALUE,
                    ObservationSemanticSelectionStatus.UNSUPPORTED_SEMANTIC_VALUE,
                }
            ),
            duplicate_observation_ids=tuple(
                selection.observation_id
                for selection in selection_tuple
                if selection.status is ObservationSemanticSelectionStatus.DUPLICATE
            ),
            selections=selection_tuple,
            applied_rule_ids=tuple(applied_rule_ids),
            metadata=metadata or {},
        )
