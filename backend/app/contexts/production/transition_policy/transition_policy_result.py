from enum import StrEnum


class TransitionPolicyResult(StrEnum):
    TRANSITION_SUPPORTED = "transition_supported"
    TRANSITION_NOT_SUPPORTED = "transition_not_supported"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    ALREADY_CURRENT = "already_current"
    UNKNOWN = "unknown"
