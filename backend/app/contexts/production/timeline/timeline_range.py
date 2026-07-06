from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from app.contexts.production.timeline.timeline_position import TimelinePosition
from app.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class TimelineRange:
    """A span within one recording block timeline."""

    start: TimelinePosition
    end: TimelinePosition

    def __post_init__(self) -> None:
        if self.start.recording_block_id != self.end.recording_block_id:
            raise ValueError("TimelineRange positions must belong to the same RecordingBlock.")
        if self.end.offset <= self.start.offset:
            raise ValueError("TimelineRange end must be after start.")

    @property
    def recording_block_id(self) -> EntityId:
        return self.start.recording_block_id

    @property
    def duration(self) -> timedelta:
        return self.end.offset - self.start.offset
