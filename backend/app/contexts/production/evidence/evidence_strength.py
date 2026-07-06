from enum import StrEnum


class EvidenceStrength(StrEnum):
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    CONTRADICTORY = "contradictory"
    UNKNOWN = "unknown"
