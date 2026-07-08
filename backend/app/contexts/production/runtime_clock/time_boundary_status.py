from enum import StrEnum


class TimeBoundaryStatus(StrEnum):
    PENDING = "pending"
    CROSSED = "crossed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    ARCHIVED = "archived"
    UNKNOWN = "unknown"
