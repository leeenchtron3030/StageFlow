from enum import StrEnum


class VisualDetectionStatus(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    FINALIZED = "finalized"
    FAILED = "failed"
    DELETED = "deleted"
    UNKNOWN = "unknown"
