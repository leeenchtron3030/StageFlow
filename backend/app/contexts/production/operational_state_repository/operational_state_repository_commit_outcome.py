from enum import StrEnum


class OperationalStateRepositoryCommitOutcome(StrEnum):
    """Complete outcomes for one atomic acceptance commit attempt."""

    COMMITTED = "committed"
    ALREADY_COMMITTED = "already_committed"
    STALE_PREDECESSOR = "stale_predecessor"
    CURRENT_STATE_CONFLICT = "current_state_conflict"
    SUBJECT_KIND_CONFLICT = "subject_kind_conflict"
    INVALID_ACCEPTANCE_RESULT = "invalid_acceptance_result"
    INVALID_SUCCESSOR_STATE = "invalid_successor_state"
    LINEAGE_CONFLICT = "lineage_conflict"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"
