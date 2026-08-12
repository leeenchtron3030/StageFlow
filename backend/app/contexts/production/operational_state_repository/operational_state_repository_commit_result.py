from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.contexts.production.operational_state import (
    OperationalStateKind,
    OperationalStateStatus,
    OperationalStateSubject,
)
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata

from .operational_state_repository_commit_outcome import (
    OperationalStateRepositoryCommitOutcome,
)
from .operational_state_repository_commit_reason import (
    OperationalStateRepositoryCommitReason,
    normalize_commit_reasons,
)
from .operational_state_repository_error import OperationalStateRepositoryError
from .operational_state_repository_record import OperationalStateRepositoryRecord


def _empty_metadata() -> Mapping[str, Any]:
    return {}


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware.")


@dataclass(frozen=True, slots=True)
class OperationalStateRepositoryCommitResult:
    """All-or-none outcome of one atomic repository commit attempt."""

    outcome: OperationalStateRepositoryCommitOutcome
    reasons: Sequence[OperationalStateRepositoryCommitReason]
    storage_changed: bool
    commit_id: EntityId | None = None
    acceptance_id: EntityId | None = None
    evaluation_id: EntityId | None = None
    predecessor_state_id: EntityId | None = None
    successor_state_id: EntityId | None = None
    subject: OperationalStateSubject | None = None
    state_kind: OperationalStateKind | None = None
    previous_revision: int | None = None
    committed_revision: int | None = None
    committed_at: datetime | None = None
    current_state_record: OperationalStateRepositoryRecord | None = None
    superseded_predecessor_record: OperationalStateRepositoryRecord | None = None
    error: OperationalStateRepositoryError | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        reasons = normalize_commit_reasons(self.reasons)
        if not reasons:
            raise ValueError("OperationalStateRepositoryCommitResult requires a reason.")
        for name, revision in (
            ("previous_revision", self.previous_revision),
            ("committed_revision", self.committed_revision),
        ):
            if revision is not None and revision < 0:
                raise ValueError(f"{name} must not be negative.")
        if self.committed_at is not None:
            _require_aware(
                self.committed_at,
                "OperationalStateRepositoryCommitResult.committed_at",
            )

        if self.outcome is OperationalStateRepositoryCommitOutcome.COMMITTED:
            self._validate_committed_shape()
        elif self.outcome is OperationalStateRepositoryCommitOutcome.ALREADY_COMMITTED:
            self._validate_already_committed_shape()
        else:
            self._validate_unchanged_shape()

        if (
            self.error is not None
            and self.outcome is not OperationalStateRepositoryCommitOutcome.UNKNOWN
        ):
            raise ValueError("Repository errors are represented only by the unknown outcome.")
        object.__setattr__(self, "reasons", reasons)
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def _validate_committed_shape(self) -> None:
        if not self.storage_changed:
            raise ValueError("A committed result must report one atomic storage change.")
        if any(
            value is None
            for value in (
                self.commit_id,
                self.acceptance_id,
                self.evaluation_id,
                self.successor_state_id,
                self.subject,
                self.state_kind,
                self.committed_revision,
                self.committed_at,
                self.current_state_record,
            )
        ):
            raise ValueError("A committed result requires complete commit identity and state.")
        current = self.current_state_record
        if current is None:  # Narrow the type after the complete-shape check.
            raise ValueError("A committed result requires its current record.")
        if current.status is not OperationalStateStatus.CURRENT:
            raise ValueError("A committed result current record must be current.")
        if current.state_id != self.successor_state_id:
            raise ValueError("Committed successor identity must match the current record.")
        if current.acceptance_id != self.acceptance_id:
            raise ValueError("Committed acceptance identity must match the current record.")
        if current.accepted_evaluation_id != self.evaluation_id:
            raise ValueError("Committed Evaluation identity must match the current record.")
        if current.subject != self.subject or current.kind is not self.state_kind:
            raise ValueError("Committed subject-kind key must match the current record.")
        if current.revision != self.committed_revision:
            raise ValueError("Committed revision must match the current record.")

        predecessor = self.superseded_predecessor_record
        if self.predecessor_state_id is None:
            if predecessor is not None:
                raise ValueError("An initial commit cannot expose a superseded predecessor.")
        elif (
            predecessor is None
            or predecessor.state_id != self.predecessor_state_id
            or predecessor.status is not OperationalStateStatus.SUPERSEDED
            or predecessor.successor_state_id != self.successor_state_id
        ):
            raise ValueError("A successor commit requires its persisted superseded predecessor.")

    def _validate_already_committed_shape(self) -> None:
        if self.storage_changed:
            raise ValueError("An already-committed result cannot report a storage change.")
        if self.current_state_record is not None or self.superseded_predecessor_record is not None:
            raise ValueError("An already-committed result cannot expose newly persisted records.")

    def _validate_unchanged_shape(self) -> None:
        if self.storage_changed:
            raise ValueError("A rejected commit result cannot report a storage change.")
        if any(
            value is not None
            for value in (
                self.commit_id,
                self.committed_revision,
                self.committed_at,
                self.current_state_record,
                self.superseded_predecessor_record,
            )
        ):
            raise ValueError("A rejected commit result cannot claim persisted commit output.")
