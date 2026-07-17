from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from app.contexts.production.operational_state import (
    OperationalStateKind,
    OperationalStateSubject,
    OperationalStateSubjectType,
)
from app.shared.ids import EntityId

from .operational_state_repository_commit_result import (
    OperationalStateRepositoryCommitResult,
)
from .operational_state_repository_record import OperationalStateRepositoryRecord


@dataclass(frozen=True, slots=True)
class OperationalStateRepositoryKey:
    """Hashable repository identity derived from one OperationalStateSubject."""

    subject_type: OperationalStateSubjectType
    subject_identifier: str
    state_kind: OperationalStateKind

    @classmethod
    def from_subject(
        cls,
        subject: OperationalStateSubject,
        state_kind: OperationalStateKind,
    ) -> OperationalStateRepositoryKey:
        return cls(
            subject_type=subject.subject_type,
            subject_identifier=subject.subject_identifier,
            state_kind=state_kind,
        )


def _empty_record_mapping() -> Mapping[EntityId, OperationalStateRepositoryRecord]:
    return {}


def _empty_current_mapping() -> Mapping[OperationalStateRepositoryKey, EntityId]:
    return {}


def _empty_history_mapping() -> Mapping[OperationalStateRepositoryKey, tuple[EntityId, ...]]:
    return {}


def _empty_commit_mapping() -> Mapping[EntityId, OperationalStateRepositoryCommitResult]:
    return {}


def _empty_revision_mapping() -> Mapping[OperationalStateRepositoryKey, int]:
    return {}


@dataclass(frozen=True, slots=True)
class InMemoryOperationalStateRepositoryState:
    """Effectively immutable state replaced atomically after a complete commit."""

    records_by_state_id: Mapping[EntityId, OperationalStateRepositoryRecord] = field(
        default_factory=_empty_record_mapping
    )
    current_state_id_by_key: Mapping[OperationalStateRepositoryKey, EntityId] = field(
        default_factory=_empty_current_mapping
    )
    history_ids_by_key: Mapping[
        OperationalStateRepositoryKey,
        tuple[EntityId, ...],
    ] = field(default_factory=_empty_history_mapping)
    commits_by_evaluation_id: Mapping[
        EntityId,
        OperationalStateRepositoryCommitResult,
    ] = field(default_factory=_empty_commit_mapping)
    commits_by_acceptance_id: Mapping[
        EntityId,
        OperationalStateRepositoryCommitResult,
    ] = field(default_factory=_empty_commit_mapping)
    revisions_by_key: Mapping[OperationalStateRepositoryKey, int] = field(
        default_factory=_empty_revision_mapping
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "records_by_state_id",
            MappingProxyType(dict(self.records_by_state_id)),
        )
        object.__setattr__(
            self,
            "current_state_id_by_key",
            MappingProxyType(dict(self.current_state_id_by_key)),
        )
        object.__setattr__(
            self,
            "history_ids_by_key",
            MappingProxyType(
                {key: tuple(state_ids) for key, state_ids in self.history_ids_by_key.items()}
            ),
        )
        object.__setattr__(
            self,
            "commits_by_evaluation_id",
            MappingProxyType(dict(self.commits_by_evaluation_id)),
        )
        object.__setattr__(
            self,
            "commits_by_acceptance_id",
            MappingProxyType(dict(self.commits_by_acceptance_id)),
        )
        object.__setattr__(
            self,
            "revisions_by_key",
            MappingProxyType(dict(self.revisions_by_key)),
        )

    def with_commit(
        self,
        *,
        key: OperationalStateRepositoryKey,
        current_record: OperationalStateRepositoryRecord,
        superseded_record: OperationalStateRepositoryRecord | None,
        commit_result: OperationalStateRepositoryCommitResult,
    ) -> InMemoryOperationalStateRepositoryState:
        """Build a complete replacement snapshot without mutating this state."""

        records = dict(self.records_by_state_id)
        if superseded_record is not None:
            records[superseded_record.state_id] = superseded_record
        records[current_record.state_id] = current_record

        current = dict(self.current_state_id_by_key)
        current[key] = current_record.state_id

        histories = dict(self.history_ids_by_key)
        histories[key] = (*histories.get(key, ()), current_record.state_id)

        evaluations = dict(self.commits_by_evaluation_id)
        evaluations[current_record.accepted_evaluation_id] = commit_result

        acceptances = dict(self.commits_by_acceptance_id)
        acceptances[current_record.acceptance_id] = commit_result

        revisions = dict(self.revisions_by_key)
        revisions[key] = current_record.revision or 0

        return InMemoryOperationalStateRepositoryState(
            records_by_state_id=records,
            current_state_id_by_key=current,
            history_ids_by_key=histories,
            commits_by_evaluation_id=evaluations,
            commits_by_acceptance_id=acceptances,
            revisions_by_key=revisions,
        )
