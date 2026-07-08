from enum import StrEnum


class RecordingAdapterCapability(StrEnum):
    REPORTS_RECORDING_START = "reports_recording_start"
    REPORTS_RECORDING_STOP = "reports_recording_stop"
    REPORTS_RECORDING_PAUSE = "reports_recording_pause"
    REPORTS_RECORDING_STATUS = "reports_recording_status"
    REPORTS_LIVESTREAM_STATUS = "reports_livestream_status"
    REPORTS_HEALTH = "reports_health"
    UNKNOWN = "unknown"
