from enum import StrEnum


class FindingOrigin(StrEnum):
    HUMAN_REVIEW = "human_review"
    SCHEDULE_REASONING = "schedule_reasoning"
    TRANSCRIPT_REASONING = "transcript_reasoning"
    GRAPHICS_REASONING = "graphics_reasoning"
    AUDIO_REASONING = "audio_reasoning"
    MULTI_SOURCE_REASONING = "multi_source_reasoning"
    UNKNOWN = "unknown"
