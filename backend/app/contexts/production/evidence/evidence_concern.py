from enum import StrEnum


class EvidenceConcern(StrEnum):
    RECORDING_COVERAGE = "recording_coverage"
    MEDIA_AVAILABILITY = "media_availability"
    POSSIBLE_SESSION_START = "possible_session_start"
    POSSIBLE_SESSION_END = "possible_session_end"
    TRANSCRIPT_CONTINUITY = "transcript_continuity"
    SCHEDULE_ALIGNMENT = "schedule_alignment"
    VISUAL_TRANSITION_CONTEXT = "visual_transition_context"
    EDITORIAL_MOMENT = "editorial_moment"
    PACKAGE_PREPARATION = "package_preparation"
    UNKNOWN = "unknown"
