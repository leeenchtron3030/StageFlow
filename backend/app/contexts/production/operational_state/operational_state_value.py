from enum import StrEnum


class OperationalStateValue(StrEnum):
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"
    AVAILABLE = "available"
    INACTIVE = "inactive"
    READY = "ready"
    ACTIVE = "active"
    FLOWING = "flowing"
    PAUSED = "paused"
    DEGRADED = "degraded"
    INTERRUPTED = "interrupted"
    STOPPED = "stopped"
    ENDING = "ending"
    ENDED = "ended"
    COMPLETE = "complete"
    INSUFFICIENT = "insufficient"
    WAITING = "waiting"
    CANDIDATE = "candidate"
