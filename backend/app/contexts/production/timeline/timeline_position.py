from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from functools import total_ordering

from app.shared.ids import EntityId


@total_ordering
@dataclass(frozen=True, slots=True)
class TimelinePosition:
    """A point within a recording block, measured as offset from block start."""

    recording_block_id: EntityId
    offset: timedelta

    def __post_init__(self) -> None:
        if self.offset < timedelta(0):
            raise ValueError("TimelinePosition offset must be non-negative.")

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, TimelinePosition):
            return NotImplemented
        return (self.recording_block_id.value, self.offset) < (
            other.recording_block_id.value,
            other.offset,
        )
