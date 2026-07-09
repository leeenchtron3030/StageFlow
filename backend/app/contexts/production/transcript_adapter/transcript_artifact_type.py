from enum import StrEnum


class TranscriptArtifactType(StrEnum):
    PARTIAL_TRANSCRIPT = "partial_transcript"
    FINAL_TRANSCRIPT = "final_transcript"
    CAPTION = "caption"
    SUBTITLE = "subtitle"
    WORD_TIMESTAMPS = "word_timestamps"
    SPEAKER_LABELS = "speaker_labels"
    TRANSLATION = "translation"
    METADATA = "metadata"
    UNKNOWN = "unknown"
