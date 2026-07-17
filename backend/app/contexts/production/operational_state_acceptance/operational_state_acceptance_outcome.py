from enum import StrEnum


class OperationalStateAcceptanceOutcome(StrEnum):
    ACCEPTED = "accepted"
    REJECTED_INELIGIBLE_EVALUATION = "rejected_ineligible_evaluation"
    REJECTED_INVALID_LINEAGE = "rejected_invalid_lineage"
    REJECTED_INVALID_CURRENT_STATE = "rejected_invalid_current_state"
    REJECTED_INVALID_SUBJECT = "rejected_invalid_subject"
    REJECTED_CONTEXT_MISMATCH = "rejected_context_mismatch"
    REJECTED_INVALID_TRANSITION = "rejected_invalid_transition"
    ALREADY_ACCEPTED = "already_accepted"
    UNKNOWN = "unknown"
