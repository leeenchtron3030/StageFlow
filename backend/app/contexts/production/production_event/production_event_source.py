from enum import StrEnum


class ProductionEventSource(StrEnum):
    RECORDING_SYSTEM = "recording_system"
    FILESYSTEM = "filesystem"
    SCHEDULE_SYSTEM = "schedule_system"
    TRANSCRIPT_SYSTEM = "transcript_system"
    VISION_SYSTEM = "vision_system"
    AUDIO_SYSTEM = "audio_system"
    LIVESTREAM_SYSTEM = "livestream_system"
    OPERATOR = "operator"
    TIMER = "timer"
    WEBHOOK = "webhook"
    INTERNAL_SYSTEM = "internal_system"
    UNKNOWN = "unknown"
