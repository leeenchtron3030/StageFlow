from enum import StrEnum


class ScheduleAdapterCapability(StrEnum):
    REPORTS_ACTIVITY_CREATED = "reports_activity_created"
    REPORTS_ACTIVITY_UPDATED = "reports_activity_updated"
    REPORTS_ACTIVITY_CANCELLED = "reports_activity_cancelled"
    REPORTS_ACTIVITY_COMPLETED = "reports_activity_completed"
    REPORTS_SCHEDULE_METADATA = "reports_schedule_metadata"
    UNKNOWN = "unknown"
