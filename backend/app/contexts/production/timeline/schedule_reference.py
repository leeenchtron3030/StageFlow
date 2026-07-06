from __future__ import annotations

from dataclasses import dataclass

from app.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class ScheduleReference:
    """Generic reference to externally scheduled session information."""

    external_system_id: EntityId
    external_schedule_id: str
    external_version: str | None = None
    source_label: str | None = None

    def __post_init__(self) -> None:
        if not self.external_schedule_id.strip():
            raise ValueError("ScheduleReference external_schedule_id must not be empty.")
