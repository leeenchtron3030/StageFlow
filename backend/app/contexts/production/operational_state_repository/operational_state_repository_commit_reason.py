from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.contexts.production.operational_state import (
    OperationalStateKind,
    OperationalStateSubject,
)
from app.shared.ids import EntityId
from app.shared.metadata import freeze_metadata


class OperationalStateRepositoryCommitReasonCode(StrEnum):
    """Categorical, non-Evidence reasoning for one repository commit outcome."""

    ACCEPTANCE_RESULT_NOT_ACCEPTED = "acceptance_result_not_accepted"
    MISSING_SUCCESSOR_STATE = "missing_successor_state"
    MISSING_ACCEPTANCE_IDENTITY = "missing_acceptance_identity"
    MISSING_EVALUATION_IDENTITY = "missing_evaluation_identity"
    MISSING_LINEAGE = "missing_lineage"
    SUCCESSOR_STATUS_NOT_CURRENT = "successor_status_not_current"
    SUCCESSOR_SUBJECT_MISMATCH = "successor_subject_mismatch"
    SUCCESSOR_KIND_MISMATCH = "successor_kind_mismatch"
    SUCCESSOR_FAMILY_MISMATCH = "successor_family_mismatch"
    SUCCESSOR_VALUE_MISMATCH = "successor_value_mismatch"
    SUCCESSOR_BASIS_MISMATCH = "successor_basis_mismatch"
    SUCCESSOR_CONTEXT_MISMATCH = "successor_context_mismatch"
    SUCCESSOR_TIMESTAMP_MISMATCH = "successor_timestamp_mismatch"
    EVALUATION_ALREADY_COMMITTED = "evaluation_already_committed"
    ACCEPTANCE_ALREADY_COMMITTED = "acceptance_already_committed"
    EXPECTED_PREDECESSOR_MISSING = "expected_predecessor_missing"
    EXPECTED_PREDECESSOR_NOT_CURRENT = "expected_predecessor_not_current"
    EXPECTED_PREDECESSOR_MISMATCH = "expected_predecessor_mismatch"
    UNEXPECTED_CURRENT_STATE = "unexpected_current_state"
    REPOSITORY_REVISION_MISMATCH = "repository_revision_mismatch"
    SUPERSESSION_MISSING = "supersession_missing"
    SUPERSESSION_MISMATCH = "supersession_mismatch"
    LINEAGE_CONFLICT = "lineage_conflict"
    COMMIT_COMPLETED = "commit_completed"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class OperationalStateRepositoryCommitReason:
    """One explainable structural, idempotency, or concurrency reason."""

    code: OperationalStateRepositoryCommitReasonCode
    message: str
    acceptance_id: EntityId | None = None
    evaluation_id: EntityId | None = None
    predecessor_state_id: EntityId | None = None
    successor_state_id: EntityId | None = None
    subject: OperationalStateSubject | None = None
    state_kind: OperationalStateKind | None = None
    expected_revision: int | None = None
    actual_revision: int | None = None
    related_ids: Sequence[EntityId] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.message.strip():
            raise ValueError(
                "OperationalStateRepositoryCommitReason message must not be empty."
            )
        if self.expected_revision is not None and self.expected_revision < 0:
            raise ValueError("Expected repository revision must not be negative.")
        if self.actual_revision is not None and self.actual_revision < 0:
            raise ValueError("Actual repository revision must not be negative.")
        object.__setattr__(self, "related_ids", tuple(dict.fromkeys(self.related_ids)))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))


def commit_reason_sort_key(
    reason: OperationalStateRepositoryCommitReason,
) -> tuple[str, str, str, str, str, str, int, int]:
    """Return a stable semantic key independent of enum declaration or input order."""

    return (
        reason.code.value,
        reason.message,
        reason.acceptance_id.to_json() if reason.acceptance_id else "",
        reason.evaluation_id.to_json() if reason.evaluation_id else "",
        reason.predecessor_state_id.to_json() if reason.predecessor_state_id else "",
        reason.successor_state_id.to_json() if reason.successor_state_id else "",
        reason.expected_revision if reason.expected_revision is not None else -1,
        reason.actual_revision if reason.actual_revision is not None else -1,
    )


def normalize_commit_reasons(
    reasons: Sequence[OperationalStateRepositoryCommitReason],
) -> tuple[OperationalStateRepositoryCommitReason, ...]:
    """Deduplicate and order commit reasons deterministically."""

    ordered = sorted(reasons, key=commit_reason_sort_key)
    normalized: list[OperationalStateRepositoryCommitReason] = []
    seen: set[tuple[str, str, str, str, str, str, int, int]] = set()
    for reason in ordered:
        key = commit_reason_sort_key(reason)
        if key not in seen:
            normalized.append(reason)
            seen.add(key)
    return tuple(normalized)
