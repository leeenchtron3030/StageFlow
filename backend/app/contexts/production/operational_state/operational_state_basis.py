from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.contexts.production.evidence import EvidenceContext
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class OperationalStateBasis:
    """ID-only basis explaining why an OperationalState exists."""

    observation_ids: Sequence[EntityId] = field(default_factory=tuple)
    evidence_set_ids: Sequence[EntityId] = field(default_factory=tuple)
    transition_evaluation_ids: Sequence[EntityId] = field(default_factory=tuple)
    policy_ids: Sequence[EntityId] = field(default_factory=tuple)
    transition_rule_ids: Sequence[EntityId] = field(default_factory=tuple)
    evidence_context: EvidenceContext | None = None
    rationale: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        for name in (
            "observation_ids",
            "evidence_set_ids",
            "transition_evaluation_ids",
            "policy_ids",
            "transition_rule_ids",
        ):
            object.__setattr__(self, name, tuple(dict.fromkeys(getattr(self, name))))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
