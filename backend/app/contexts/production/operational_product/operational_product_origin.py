from enum import StrEnum


class OperationalProductOrigin(StrEnum):
    VERIFIED_FINDING = "verified_finding"
    HUMAN_CREATED = "human_created"
    SYSTEM_CREATED = "system_created"
    IMPORTED = "imported"
    UNKNOWN = "unknown"
