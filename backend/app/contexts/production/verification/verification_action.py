from enum import StrEnum


class VerificationAction(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    ADJUST = "adjust"
    MERGE = "merge"
    SPLIT = "split"
    DEFER = "defer"
    ESCALATE = "escalate"
    ANNOTATE = "annotate"
    SUPERSEDE = "supersede"
