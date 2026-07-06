from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from app.contexts.production.timeline import TimelinePosition, TimelineRange
from app.shared.ids import EntityId


class VerificationAdjustmentType(StrEnum):
    ADJUST_START = "adjust_start"
    ADJUST_END = "adjust_end"
    ADJUST_RANGE = "adjust_range"
    MERGE_FINDINGS = "merge_findings"
    SPLIT_FINDING = "split_finding"
    REVISE_LOCATION = "revise_location"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class VerificationAdjustment:
    """A described adjustment attached to a verification decision."""

    adjustment_type: VerificationAdjustmentType
    target_finding_ids: Sequence[EntityId] = field(default_factory=tuple)
    adjusted_position: TimelinePosition | None = None
    adjusted_range: TimelineRange | None = None
    rationale: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_finding_ids", tuple(self.target_finding_ids))
