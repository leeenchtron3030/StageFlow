from enum import StrEnum


class RecordingSystemStatus(StrEnum):
    UNKNOWN = "unknown"
    CONFIGURED = "configured"
    READY = "ready"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPED = "stopped"
    DEGRADED = "degraded"
    FAILED = "failed"
    ARCHIVED = "archived"
