from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.contexts.production.operational_state import (
    OperationalStateKind,
    OperationalStateStatus,
    OperationalStateSubject,
)
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata

from .operational_state_repository_record import OperationalStateRepositoryRecord


def _empty_metadata() -> Mapping[str, Any]:
    return {}


def _record_order_key(record: OperationalStateRepositoryRecord) -> tuple[int, str, str]:
    return (
        record.revision if record.revision is not None else 0,
        record.persisted_at.isoformat(),
        record.state_id.to_json(),
    )


@dataclass(frozen=True, slots=True)
class OperationalStateRepositoryHistory:
    """Oldest-to-newest immutable history for one subject-kind key."""

    subject: OperationalStateSubject
    state_kind: OperationalStateKind
    records: Sequence[OperationalStateRepositoryRecord] = field(default_factory=tuple)
    current_state_id: EntityId | None = None
    earliest_state_id: EntityId | None = None
    latest_committed_evaluation_id: EntityId | None = None
    revision: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        records = tuple(self.records)
        if self.revision is not None and self.revision < 0:
            raise ValueError("Repository history revision must not be negative.")
        if any(record.subject != self.subject for record in records):
            raise ValueError("Repository history cannot mix subjects.")
        if any(record.kind is not self.state_kind for record in records):
            raise ValueError("Repository history cannot mix state kinds.")
        if records != tuple(sorted(records, key=_record_order_key)):
            raise ValueError("Repository history must be ordered oldest to newest.")
        record_revisions = tuple(record.revision for record in records)
        revisions_are_present = tuple(revision is not None for revision in record_revisions)
        if any(revisions_are_present) and not all(revisions_are_present):
            raise ValueError("Repository history revisions must be present for every record.")
        if all(revisions_are_present) and records:
            revisions = tuple(
                revision for revision in record_revisions if revision is not None
            )
            if revisions != tuple(sorted(set(revisions))):
                raise ValueError("Repository history revisions must be strictly monotonic.")
            if self.revision != revisions[-1]:
                raise ValueError("Repository history revision must match the newest record.")
        elif self.revision is not None and records:
            raise ValueError("Unversioned repository records cannot claim a history revision.")
        if len({record.state_id for record in records}) != len(records):
            raise ValueError("Repository history cannot repeat a state ID.")

        if not records:
            if any(
                value is not None
                for value in (
                    self.current_state_id,
                    self.earliest_state_id,
                    self.latest_committed_evaluation_id,
                )
            ):
                raise ValueError("Empty repository history cannot reference a state or commit.")
        else:
            if self.earliest_state_id != records[0].state_id:
                raise ValueError("Repository history earliest state must be the first record.")
            if self.current_state_id != records[-1].state_id:
                raise ValueError("Repository history current state must be the newest record.")
            if self.latest_committed_evaluation_id != records[-1].accepted_evaluation_id:
                raise ValueError("Repository history latest Evaluation must match newest record.")
            if records[-1].status is not OperationalStateStatus.CURRENT:
                raise ValueError("Repository history newest record must be current.")
            if any(
                record.status is not OperationalStateStatus.SUPERSEDED
                for record in records[:-1]
            ):
                raise ValueError("Only the newest repository history record may be current.")
            for predecessor, successor in zip(records, records[1:], strict=False):
                if predecessor.successor_state_id != successor.state_id:
                    raise ValueError("Repository history successor chain is incomplete.")
                if successor.predecessor_state_id != predecessor.state_id:
                    raise ValueError("Repository history predecessor chain is incomplete.")

        object.__setattr__(self, "records", records)
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    @property
    def state_ids(self) -> tuple[EntityId, ...]:
        return tuple(record.state_id for record in self.records)
