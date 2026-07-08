from enum import StrEnum


class MediaArtifactCapability(StrEnum):
    REPORTS_ARTIFACT_CREATED = "reports_artifact_created"
    REPORTS_ARTIFACT_UPDATED = "reports_artifact_updated"
    REPORTS_ARTIFACT_FINALIZED = "reports_artifact_finalized"
    REPORTS_ARTIFACT_FAILED = "reports_artifact_failed"
    REPORTS_ARTIFACT_DELETED = "reports_artifact_deleted"
    REPORTS_ARTIFACT_SIZE = "reports_artifact_size"
    REPORTS_ARTIFACT_LOCATION = "reports_artifact_location"
    UNKNOWN = "unknown"
