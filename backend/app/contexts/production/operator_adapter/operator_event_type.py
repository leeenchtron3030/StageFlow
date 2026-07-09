from enum import StrEnum


class OperatorEventType(StrEnum):
    ANNOTATION_CREATED = "annotation_created"
    ANNOTATION_UPDATED = "annotation_updated"
    ANNOTATION_REMOVED = "annotation_removed"
    MARKER_CREATED = "marker_created"
    MARKER_REMOVED = "marker_removed"
    FLAG_CREATED = "flag_created"
    FLAG_REMOVED = "flag_removed"
    NOTE_CREATED = "note_created"
    NOTE_UPDATED = "note_updated"
    DECISION_REQUESTED = "decision_requested"
    CUSTOM = "custom"
    UNKNOWN = "unknown"
