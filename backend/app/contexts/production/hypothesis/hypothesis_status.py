from enum import StrEnum


class HypothesisStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    DISMISSED = "dismissed"
    ARCHIVED = "archived"
