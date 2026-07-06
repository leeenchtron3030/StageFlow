from enum import StrEnum


class ObservationType(StrEnum):
    SPEECH_DETECTED = "speech_detected"
    TITLE_DETECTED = "title_detected"
    GRAPHIC_CHANGED = "graphic_changed"
    APPLAUSE_DETECTED = "applause_detected"
    SILENCE_DETECTED = "silence_detected"
    MUSIC_DETECTED = "music_detected"
    OPERATOR_MARKER = "operator_marker"
    SCHEDULE_BOUNDARY = "schedule_boundary"
    TRANSCRIPT_TEXT_DETECTED = "transcript_text_detected"
    LIVESTREAM_STATUS_CHANGED = "livestream_status_changed"
    UNKNOWN = "unknown"
