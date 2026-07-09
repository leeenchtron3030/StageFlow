from enum import StrEnum


class TranscriptSegmentStatus(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    FINALIZED = "finalized"
    FAILED = "failed"
    DELETED = "deleted"
    UNKNOWN = "unknown"
