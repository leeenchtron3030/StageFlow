from enum import StrEnum


class OperatorAdapterCapability(StrEnum):
    REPORTS_ANNOTATIONS = "reports_annotations"
    REPORTS_MARKERS = "reports_markers"
    REPORTS_FLAGS = "reports_flags"
    REPORTS_NOTES = "reports_notes"
    REPORTS_REQUESTS = "reports_requests"
    UNKNOWN = "unknown"
