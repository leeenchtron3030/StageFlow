from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class OperationalStateAcceptanceHistory:
    """Caller-supplied known acceptance history; not a persistence query."""

    accepted_evaluation_ids: Sequence[EntityId] = field(default_factory=tuple)
    prior_acceptance_ids: Sequence[EntityId] = field(default_factory=tuple)
    successor_state_ids: Sequence[EntityId] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        for name in (
            "accepted_evaluation_ids",
            "prior_acceptance_ids",
            "successor_state_ids",
        ):
            object.__setattr__(self, name, tuple(dict.fromkeys(getattr(self, name))))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def contains_evaluation(self, evaluation_id: EntityId) -> bool:
        return evaluation_id in self.accepted_evaluation_ids
