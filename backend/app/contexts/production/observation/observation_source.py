from enum import StrEnum


class ObservationSource(StrEnum):
    HUMAN = "human"
    OPERATOR = "operator"
    SCHEDULE = "schedule"
    TRANSCRIPT = "transcript"
    AUDIO = "audio"
    VISION = "vision"
    GRAPHICS = "graphics"
    LIVESTREAM = "livestream"
    SYSTEM = "system"
    UNKNOWN = "unknown"
