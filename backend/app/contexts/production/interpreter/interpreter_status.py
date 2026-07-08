from enum import StrEnum


class InterpreterStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    DEGRADED = "degraded"
    EXPERIMENTAL = "experimental"
    ARCHIVED = "archived"
