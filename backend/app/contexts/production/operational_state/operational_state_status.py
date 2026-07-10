from enum import StrEnum


class OperationalStateStatus(StrEnum):
    CURRENT = "current"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    ARCHIVED = "archived"
    UNKNOWN = "unknown"
