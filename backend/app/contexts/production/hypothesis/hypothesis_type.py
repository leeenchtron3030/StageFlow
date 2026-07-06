from enum import StrEnum


class HypothesisType(StrEnum):
    POSSIBLE_SESSION_START = "possible_session_start"
    POSSIBLE_SESSION_END = "possible_session_end"
    POSSIBLE_TRANSITION = "possible_transition"
    POSSIBLE_SCHEDULE_CONFLICT = "possible_schedule_conflict"
    POSSIBLE_RECORDING_ANOMALY = "possible_recording_anomaly"
    GENERAL_CONTEXT = "general_context"
    UNKNOWN = "unknown"
