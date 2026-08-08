from enum import StrEnum


class DispatchStatus(StrEnum):
    """Fail-closed aggregate classification for one dispatch."""

    NO_MATCH = "no_match"
    SUCCESS = "success"
    SUCCESS_WITH_WARNINGS = "success_with_warnings"
    PARTIAL_FAILURE = "partial_failure"
    TOTAL_FAILURE = "total_failure"
