from enum import StrEnum


class OperationalStateKind(StrEnum):
    RECORDING_STATE = "recording_state"
    MEDIA_AVAILABILITY = "media_availability"
    TRANSCRIPT_STATE = "transcript_state"
    VISION_AVAILABILITY = "vision_availability"
    SESSION_STATE = "session_state"
    EDITORIAL_STATE = "editorial_state"
    PACKAGE_STATE = "package_state"
    OBSERVATION_READINESS = "observation_readiness"
    REASONING_READINESS = "reasoning_readiness"
    ENVIRONMENTAL_CONDITION = "environmental_condition"
    UNKNOWN = "unknown"
