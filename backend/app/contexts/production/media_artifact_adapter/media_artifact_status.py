from enum import StrEnum


class MediaArtifactStatus(StrEnum):
    CREATED = "created"
    UPDATING = "updating"
    FINALIZED = "finalized"
    FAILED = "failed"
    DELETED = "deleted"
    UNKNOWN = "unknown"
