from enum import StrEnum


class OperationalProductType(StrEnum):
    SESSION_WINDOW = "session_window"
    EDITORIAL_MOMENT = "editorial_moment"
    TECHNICAL_INCIDENT = "technical_incident"
    METADATA_RECORD = "metadata_record"
    ALERT = "alert"
    PACKAGE_TASK = "package_task"
    UNKNOWN = "unknown"
