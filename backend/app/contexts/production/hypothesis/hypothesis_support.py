from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class HypothesisSupport:
    """Evidence-set references related to a hypothesis."""

    supporting_evidence_set_ids: Sequence[EntityId] = field(default_factory=tuple)
    contradicting_evidence_set_ids: Sequence[EntityId] = field(default_factory=tuple)
    neutral_evidence_set_ids: Sequence[EntityId] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "supporting_evidence_set_ids",
            tuple(self.supporting_evidence_set_ids),
        )
        object.__setattr__(
            self,
            "contradicting_evidence_set_ids",
            tuple(self.contradicting_evidence_set_ids),
        )
        object.__setattr__(self, "neutral_evidence_set_ids", tuple(self.neutral_evidence_set_ids))

    @property
    def supporting_count(self) -> int:
        return len(self.supporting_evidence_set_ids)

    @property
    def contradicting_count(self) -> int:
        return len(self.contradicting_evidence_set_ids)

    @property
    def neutral_count(self) -> int:
        return len(self.neutral_evidence_set_ids)

    @property
    def total_count(self) -> int:
        return self.supporting_count + self.contradicting_count + self.neutral_count
