from enum import StrEnum


class FindingType(StrEnum):
    POSSIBLE_SESSION_BOUNDARY = "possible_session_boundary"
    EDITORIAL_MOMENT = "editorial_moment"
    TECHNICAL_INCIDENT = "technical_incident"
    SCHEDULE_CONFLICT = "schedule_conflict"
    METADATA_EVENT = "metadata_event"
    ALERT_CONDITION = "alert_condition"
    UNKNOWN = "unknown"
