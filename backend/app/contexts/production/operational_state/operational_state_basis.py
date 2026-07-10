from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.shared.ids import EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class OperationalStateBasis:
    """ID-only basis explaining why an OperationalState exists."""

    observation_ids: Sequence[EntityId] = field(default_factory=tuple)
    evidence_set_ids: Sequence[EntityId] = field(default_factory=tuple)
    rationale: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "observation_ids", tuple(self.observation_ids))
        object.__setattr__(self, "evidence_set_ids", tuple(self.evidence_set_ids))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
