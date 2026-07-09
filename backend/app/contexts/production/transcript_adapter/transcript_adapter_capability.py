from enum import StrEnum


class TranscriptAdapterCapability(StrEnum):
    REPORTS_PARTIAL_TRANSCRIPTS = "reports_partial_transcripts"
    REPORTS_FINAL_TRANSCRIPTS = "reports_final_transcripts"
    REPORTS_WORD_TIMESTAMPS = "reports_word_timestamps"
    REPORTS_SPEAKER_LABELS = "reports_speaker_labels"
    REPORTS_LANGUAGE = "reports_language"
    REPORTS_CONFIDENCE = "reports_confidence"
    REPORTS_TRANSLATIONS = "reports_translations"
    UNKNOWN = "unknown"
