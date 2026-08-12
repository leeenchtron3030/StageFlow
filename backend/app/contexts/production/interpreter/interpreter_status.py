from enum import StrEnum


class InterpreterStatus(StrEnum):
    UNKNOWN = "unknown"
    CONFIGURED = "configured"
    READY = "ready"
    ACTIVE = "active"
    DISABLED = "disabled"
    DEGRADED = "degraded"
    EXPERIMENTAL = "experimental"
    ARCHIVED = "archived"
    FAILED = "failed"
