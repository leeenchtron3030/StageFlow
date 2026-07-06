from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class TimeRange:
    """Immutable time range with duration validation."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError("TimeRange end must be after start.")

    @property
    def duration(self) -> timedelta:
        return self.end - self.start
