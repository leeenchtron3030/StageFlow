from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.shared.time import require_aware_datetime


@dataclass(frozen=True, slots=True)
class ExternalProgramItem:
    event_id: str
    session_id: str
    room_id: str
    room_name: str
    title: str
    speakers: tuple[str, ...]
    planned_start: datetime
    planned_end: datetime

    def __post_init__(self) -> None:
        for name in ("event_id", "session_id", "room_id", "room_name", "title"):
            value = str(getattr(self, name)).strip()
            if not value:
                raise ValueError(f"{name} must not be empty")
            object.__setattr__(self, name, value)
        object.__setattr__(
            self,
            "speakers",
            tuple(sorted({speaker.strip() for speaker in self.speakers if speaker.strip()})),
        )
        require_aware_datetime(self.planned_start, "planned_start")
        require_aware_datetime(self.planned_end, "planned_end")
        if self.planned_end < self.planned_start:
            raise ValueError("planned_end cannot precede planned_start")


class ExternalProgramSource(Protocol):
    def fetch_program(self) -> tuple[ExternalProgramItem, ...]: ...


__all__ = ["ExternalProgramItem", "ExternalProgramSource"]
