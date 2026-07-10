from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.contexts.production.evidence.evidence_signal import EvidenceSignal
from app.shared.ids import EntityId


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class EvidenceSignalReference:
    """ID-only reference describing a Signal's participation in Evidence."""

    signal: EvidenceSignal
    evidence_item_ids: Sequence[EntityId] = field(default_factory=tuple)
    observation_ids: Sequence[EntityId] = field(default_factory=tuple)
    rationale: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_item_ids", tuple(self.evidence_item_ids))
        object.__setattr__(self, "observation_ids", tuple(self.observation_ids))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
