from enum import StrEnum


class ClockCapability(StrEnum):
    EVALUATES_TIME_BOUNDARIES = "evaluates_time_boundaries"
    REPORTS_BOUNDARY_CROSSED = "reports_boundary_crossed"
    REPORTS_HEARTBEAT_DUE = "reports_heartbeat_due"
    REPORTS_TIMEOUT = "reports_timeout"
    REPORTS_RETRY_DUE = "reports_retry_due"
    UNKNOWN = "unknown"
