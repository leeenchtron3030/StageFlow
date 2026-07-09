from enum import StrEnum


class OperatorEventStatus(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    REMOVED = "removed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"
