"""Operational State Repository contracts and one process-local proof implementation."""

from .in_memory_operational_state_repository import InMemoryOperationalStateRepository
from .operational_state_repository import OperationalStateRepository
from .operational_state_repository_commit_outcome import (
    OperationalStateRepositoryCommitOutcome,
)
from .operational_state_repository_commit_reason import (
    OperationalStateRepositoryCommitReason,
    OperationalStateRepositoryCommitReasonCode,
    commit_reason_sort_key,
    normalize_commit_reasons,
)
from .operational_state_repository_commit_request import (
    OperationalStateRepositoryCommitRequest,
)
from .operational_state_repository_commit_result import (
    OperationalStateRepositoryCommitResult,
)
from .operational_state_repository_error import (
    OperationalStateRepositoryError,
    OperationalStateRepositoryErrorCode,
)
from .operational_state_repository_history import OperationalStateRepositoryHistory
from .operational_state_repository_query_result import (
    OperationalStateRepositoryQueryOutcome,
    OperationalStateRepositoryQueryResult,
)
from .operational_state_repository_record import (
    OPERATIONAL_STATE_REPOSITORY_SUPPORTED_KINDS,
    OperationalStateRepositoryRecord,
)

__all__ = [
    "OPERATIONAL_STATE_REPOSITORY_SUPPORTED_KINDS",
    "InMemoryOperationalStateRepository",
    "OperationalStateRepository",
    "OperationalStateRepositoryCommitOutcome",
    "OperationalStateRepositoryCommitReason",
    "OperationalStateRepositoryCommitReasonCode",
    "OperationalStateRepositoryCommitRequest",
    "OperationalStateRepositoryCommitResult",
    "OperationalStateRepositoryError",
    "OperationalStateRepositoryErrorCode",
    "OperationalStateRepositoryHistory",
    "OperationalStateRepositoryQueryOutcome",
    "OperationalStateRepositoryQueryResult",
    "OperationalStateRepositoryRecord",
    "commit_reason_sort_key",
    "normalize_commit_reasons",
]
