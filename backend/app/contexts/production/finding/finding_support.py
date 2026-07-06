from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class FindingSupport:
    """Hypothesis ID references related to a finding."""

    supporting_hypothesis_ids: Sequence[EntityId] = field(default_factory=tuple)
    contradicting_hypothesis_ids: Sequence[EntityId] = field(default_factory=tuple)
    neutral_hypothesis_ids: Sequence[EntityId] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "supporting_hypothesis_ids",
            tuple(self.supporting_hypothesis_ids),
        )
        object.__setattr__(
            self,
            "contradicting_hypothesis_ids",
            tuple(self.contradicting_hypothesis_ids),
        )
        object.__setattr__(self, "neutral_hypothesis_ids", tuple(self.neutral_hypothesis_ids))

    @property
    def supporting_count(self) -> int:
        return len(self.supporting_hypothesis_ids)

    @property
    def contradicting_count(self) -> int:
        return len(self.contradicting_hypothesis_ids)

    @property
    def neutral_count(self) -> int:
        return len(self.neutral_hypothesis_ids)

    @property
    def total_count(self) -> int:
        return self.supporting_count + self.contradicting_count + self.neutral_count
