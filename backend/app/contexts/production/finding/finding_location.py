from __future__ import annotations

from dataclasses import dataclass

from app.contexts.production.timeline import TimelinePosition, TimelineRange
from app.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class FindingLocation:
    """A point or range on a production timeline where a finding applies."""

    point: TimelinePosition | None = None
    range: TimelineRange | None = None

    def __post_init__(self) -> None:
        has_point = self.point is not None
        has_range = self.range is not None
        if has_point == has_range:
            raise ValueError("FindingLocation requires exactly one of point or range.")

    @classmethod
    def at_point(cls, point: TimelinePosition) -> FindingLocation:
        return cls(point=point)

    @classmethod
    def over_range(cls, time_range: TimelineRange) -> FindingLocation:
        return cls(range=time_range)

    @property
    def is_point(self) -> bool:
        return self.point is not None

    @property
    def is_range(self) -> bool:
        return self.range is not None

    @property
    def recording_block_id(self) -> EntityId:
        if self.point is not None:
            return self.point.recording_block_id
        if self.range is not None:
            return self.range.recording_block_id
        raise RuntimeError("FindingLocation is invalid.")

    def summary(self) -> str:
        if self.point is not None:
            return f"point:{self.point.offset.total_seconds():.3f}s"
        if self.range is not None:
            start = self.range.start.offset.total_seconds()
            end = self.range.end.offset.total_seconds()
            return f"range:{start:.3f}s-{end:.3f}s"
        raise RuntimeError("FindingLocation is invalid.")
