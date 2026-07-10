from enum import StrEnum


class EvidenceRole(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CONTEXTUALIZES = "contextualizes"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"
