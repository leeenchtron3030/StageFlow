from enum import StrEnum


class EvidencePurpose(StrEnum):
    POTENTIAL_SESSION_START = "potential_session_start"
    POTENTIAL_SESSION_END = "potential_session_end"
    POTENTIAL_SESSION_CONTINUATION = "potential_session_continuation"
    POTENTIAL_TRANSITION = "potential_transition"
    POTENTIAL_SCHEDULE_CONFLICT = "potential_schedule_conflict"
    GENERAL_CONTEXT = "general_context"
    UNKNOWN = "unknown"
