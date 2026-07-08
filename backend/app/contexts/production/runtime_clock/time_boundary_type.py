from enum import StrEnum


class TimeBoundaryType(StrEnum):
    SCHEDULED_ACTIVITY_START = "scheduled_activity_start"
    SCHEDULED_ACTIVITY_END = "scheduled_activity_end"
    RECORDING_EXPECTED_START = "recording_expected_start"
    RECORDING_EXPECTED_END = "recording_expected_end"
    TIMEOUT = "timeout"
    HEARTBEAT_DUE = "heartbeat_due"
    RETRY_DUE = "retry_due"
    MANUAL_DEADLINE = "manual_deadline"
    CUSTOM = "custom"
    UNKNOWN = "unknown"
