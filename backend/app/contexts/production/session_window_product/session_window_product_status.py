from enum import StrEnum


class SessionWindowProductStatus(StrEnum):
    CREATED = "created"
    ACTIVE = "active"
    READY_FOR_PACKAGE = "ready_for_package"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"
