from enum import StrEnum


class ScheduledActivityStatus(StrEnum):
    SCHEDULED = "scheduled"
    UPDATED = "updated"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    UNKNOWN = "unknown"
