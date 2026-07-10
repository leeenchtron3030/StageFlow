from enum import StrEnum


class EvidenceBuilderInputClassification(StrEnum):
    """Generic classification for one Observation in an Evidence Builder input."""

    RECOGNIZED = "recognized"
    IGNORED = "ignored"
    UNSUPPORTED = "unsupported"
    MISSING_SEMANTIC_VALUE = "missing_semantic_value"
    DUPLICATE = "duplicate"
    UNKNOWN = "unknown"
