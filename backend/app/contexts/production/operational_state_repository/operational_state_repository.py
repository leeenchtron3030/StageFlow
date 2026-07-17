from __future__ import annotations

from abc import ABC, abstractmethod

from app.contexts.production.operational_state import (
    OperationalStateKind,
    OperationalStateSubject,
)
from app.shared.ids import EntityId

from .operational_state_repository_commit_request import (
    OperationalStateRepositoryCommitRequest,
)
from .operational_state_repository_commit_result import (
    OperationalStateRepositoryCommitResult,
)
from .operational_state_repository_history import OperationalStateRepositoryHistory
from .operational_state_repository_query_result import OperationalStateRepositoryQueryResult
from .operational_state_repository_record import OperationalStateRepositoryRecord


class OperationalStateRepository(ABC):
    """Infrastructure-neutral atomic persistence boundary for accepted state.

    Implementations must use subject plus state kind as the current-state key and expose
    at most one current record for that key. ``commit_acceptance`` must atomically record
    Evaluation and acceptance idempotency, persist the successor, supersede the expected
    predecessor when present, append ordered history, and move the current pointer. No
    subset may be observable. The repository validates accepted shape and lineage but
    never invokes policy, acceptance, Evidence interpretation, or external execution.
    """

    @abstractmethod
    def get_current_state(
        self,
        subject: OperationalStateSubject,
        state_kind: OperationalStateKind,
    ) -> OperationalStateRepositoryQueryResult[OperationalStateRepositoryRecord]:
        """Return the sole current record or an explicit typed query outcome."""

    @abstractmethod
    def get_state(
        self,
        state_id: EntityId,
    ) -> OperationalStateRepositoryQueryResult[OperationalStateRepositoryRecord]:
        """Return a current or superseded record by globally unique state ID."""

    @abstractmethod
    def list_state_history(
        self,
        subject: OperationalStateSubject,
        state_kind: OperationalStateKind,
    ) -> OperationalStateRepositoryQueryResult[OperationalStateRepositoryHistory]:
        """Return immutable oldest-to-newest history isolated to one key."""

    @abstractmethod
    def has_committed_evaluation(
        self,
        evaluation_id: EntityId,
    ) -> OperationalStateRepositoryQueryResult[bool]:
        """Report repository-scoped Evaluation commit identity or a typed failure."""

    @abstractmethod
    def get_commit_by_evaluation(
        self,
        evaluation_id: EntityId,
    ) -> OperationalStateRepositoryQueryResult[OperationalStateRepositoryCommitResult]:
        """Return the original committed acceptance and successor lineage."""

    @abstractmethod
    def commit_acceptance(
        self,
        request: OperationalStateRepositoryCommitRequest,
    ) -> OperationalStateRepositoryCommitResult:
        """Atomically commit one accepted result or return a no-change outcome."""
