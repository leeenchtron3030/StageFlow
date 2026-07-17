from enum import StrEnum


class AssetReadinessOutcome(StrEnum):
    SAFE_TO_READ = "safe_to_read"
    NOT_SAFE_TO_READ = "not_safe_to_read"
    INSUFFICIENT_OBSERVATION = "insufficient_observation"
    CONFLICTING_OBSERVATION = "conflicting_observation"
    UNSUPPORTED_SOURCE = "unsupported_source"
    INVALID_REQUEST = "invalid_request"
    UNKNOWN = "unknown"
