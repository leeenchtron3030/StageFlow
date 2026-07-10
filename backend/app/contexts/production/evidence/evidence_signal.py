from enum import StrEnum


class EvidenceSignal(StrEnum):
    """Operational indication contributed by structured Evidence."""

    RECORDING_CONTINUITY_ESTABLISHED = "recording_continuity_established"
    RECORDING_PAUSE_INDICATED = "recording_pause_indicated"
    RECORDING_CONTINUITY_RESTORED = "recording_continuity_restored"
    RECORDING_END_INDICATED = "recording_end_indicated"
    MEDIA_AVAILABILITY_INDICATED = "media_availability_indicated"
    MEDIA_FINALIZATION_INDICATED = "media_finalization_indicated"
    MEDIA_FAILURE_INDICATED = "media_failure_indicated"
    SCHEDULED_WINDOW_ACTIVE = "scheduled_window_active"
    SCHEDULED_ACTIVITY_CHANGED = "scheduled_activity_changed"
    SCHEDULED_ACTIVITY_CANCELLED = "scheduled_activity_cancelled"
    SPEECH_ACTIVITY_AVAILABLE = "speech_activity_available"
    TRANSCRIPT_CONTINUITY_INDICATED = "transcript_continuity_indicated"
    VISUAL_ACTIVITY_AVAILABLE = "visual_activity_available"
    PRESENTATION_TRANSITION_INDICATED = "presentation_transition_indicated"
    VISUAL_OBSTRUCTION_INDICATED = "visual_obstruction_indicated"
    OPERATOR_ATTENTION_INDICATED = "operator_attention_indicated"
    SPEAKER_INTRODUCTION_INDICATED = "speaker_introduction_indicated"
    SESSION_CONTENT_INDICATED = "session_content_indicated"
    SESSION_END_INDICATED = "session_end_indicated"
    EDITORIAL_INTEREST_INDICATED = "editorial_interest_indicated"
    PACKAGE_INPUTS_AVAILABLE = "package_inputs_available"
    UNKNOWN = "unknown"
