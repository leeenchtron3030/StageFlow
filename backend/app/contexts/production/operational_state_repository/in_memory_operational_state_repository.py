from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from threading import RLock

from app.contexts.production.operational_state import (
    OperationalStateFamily,
    OperationalStateKind,
    OperationalStateStatus,
    OperationalStateSubject,
)
from app.shared.ids import EntityId

from ..operational_state_acceptance.operational_state_acceptance_outcome import (
    OperationalStateAcceptanceOutcome,
)
from .in_memory_repository_state import (
    InMemoryOperationalStateRepositoryState,
    OperationalStateRepositoryKey,
)
from .operational_state_repository import OperationalStateRepository
from .operational_state_repository_commit_outcome import (
    OperationalStateRepositoryCommitOutcome,
)
from .operational_state_repository_commit_reason import (
    OperationalStateRepositoryCommitReason,
    OperationalStateRepositoryCommitReasonCode,
)
from .operational_state_repository_commit_request import (
    OperationalStateRepositoryCommitRequest,
)
from .operational_state_repository_commit_result import (
    OperationalStateRepositoryCommitResult,
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

_SUPPORTED_FAMILY_BY_KIND = {
    OperationalStateKind.RECORDING_STATE: OperationalStateFamily.DIRECTLY_OBSERVABLE,
    OperationalStateKind.SESSION_STATE: OperationalStateFamily.EVIDENCE_DERIVED,
}


def _is_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


class InMemoryOperationalStateRepository(OperationalStateRepository):
    """Thread-safe development and contract-validation repository.

    The implementation owns one process-local immutable state snapshot. Commits validate
    against one captured snapshot, build every replacement record and index locally, and
    replace the snapshot once while holding a private reentrant lock. It is intentionally
    disposable and provides no production persistence or cross-process coordination.
    """

    def __init__(
        self,
        *,
        commit_id_factory: Callable[[], EntityId] = EntityId.new,
    ) -> None:
        self._commit_id_factory = commit_id_factory
        self._lock = RLock()
        self._state = InMemoryOperationalStateRepositoryState()

    def get_current_state(
        self,
        subject: OperationalStateSubject,
        state_kind: OperationalStateKind,
    ) -> OperationalStateRepositoryQueryResult[OperationalStateRepositoryRecord]:
        if state_kind not in OPERATIONAL_STATE_REPOSITORY_SUPPORTED_KINDS:
            return OperationalStateRepositoryQueryResult(
                outcome=OperationalStateRepositoryQueryOutcome.INVALID_QUERY,
                metadata={"reason": "unsupported_state_kind"},
            )
        key = OperationalStateRepositoryKey.from_subject(subject, state_kind)
        with self._lock:
            state = self._state
            state_id = state.current_state_id_by_key.get(key)
            if state_id is None:
                return OperationalStateRepositoryQueryResult(
                    outcome=OperationalStateRepositoryQueryOutcome.NOT_FOUND
                )
            record = state.records_by_state_id.get(state_id)
            if (
                record is None
                or record.status is not OperationalStateStatus.CURRENT
                or record.kind is not state_kind
                or OperationalStateRepositoryKey.from_subject(record.subject, record.kind)
                != key
            ):
                return OperationalStateRepositoryQueryResult(
                    outcome=OperationalStateRepositoryQueryOutcome.CURRENT_STATE_CONFLICT,
                    metadata={"reason": "current_index_integrity_conflict"},
                )
            return OperationalStateRepositoryQueryResult(
                outcome=OperationalStateRepositoryQueryOutcome.FOUND,
                value=record,
            )

    def get_state(
        self,
        state_id: EntityId,
    ) -> OperationalStateRepositoryQueryResult[OperationalStateRepositoryRecord]:
        with self._lock:
            record = self._state.records_by_state_id.get(state_id)
            if record is None:
                return OperationalStateRepositoryQueryResult(
                    outcome=OperationalStateRepositoryQueryOutcome.NOT_FOUND
                )
            return OperationalStateRepositoryQueryResult(
                outcome=OperationalStateRepositoryQueryOutcome.FOUND,
                value=record,
            )

    def list_state_history(
        self,
        subject: OperationalStateSubject,
        state_kind: OperationalStateKind,
    ) -> OperationalStateRepositoryQueryResult[OperationalStateRepositoryHistory]:
        if state_kind not in OPERATIONAL_STATE_REPOSITORY_SUPPORTED_KINDS:
            return OperationalStateRepositoryQueryResult(
                outcome=OperationalStateRepositoryQueryOutcome.INVALID_QUERY,
                metadata={"reason": "unsupported_state_kind"},
            )
        key = OperationalStateRepositoryKey.from_subject(subject, state_kind)
        with self._lock:
            state = self._state
            state_ids = state.history_ids_by_key.get(key)
            if not state_ids:
                return OperationalStateRepositoryQueryResult(
                    outcome=OperationalStateRepositoryQueryOutcome.NOT_FOUND
                )
            records = tuple(state.records_by_state_id[state_id] for state_id in state_ids)
            current_state_id = state.current_state_id_by_key[key]
            history = OperationalStateRepositoryHistory(
                subject=records[0].subject,
                state_kind=state_kind,
                records=records,
                current_state_id=current_state_id,
                earliest_state_id=state_ids[0],
                latest_committed_evaluation_id=records[-1].accepted_evaluation_id,
                revision=state.revisions_by_key[key],
            )
            return OperationalStateRepositoryQueryResult(
                outcome=OperationalStateRepositoryQueryOutcome.FOUND,
                value=history,
            )

    def has_committed_evaluation(
        self,
        evaluation_id: EntityId,
    ) -> OperationalStateRepositoryQueryResult[bool]:
        with self._lock:
            committed = evaluation_id in self._state.commits_by_evaluation_id
            return OperationalStateRepositoryQueryResult(
                outcome=OperationalStateRepositoryQueryOutcome.FOUND,
                value=committed,
            )

    def get_commit_by_evaluation(
        self,
        evaluation_id: EntityId,
    ) -> OperationalStateRepositoryQueryResult[OperationalStateRepositoryCommitResult]:
        with self._lock:
            commit = self._state.commits_by_evaluation_id.get(evaluation_id)
            if commit is None:
                return OperationalStateRepositoryQueryResult(
                    outcome=OperationalStateRepositoryQueryOutcome.NOT_FOUND
                )
            return OperationalStateRepositoryQueryResult(
                outcome=OperationalStateRepositoryQueryOutcome.FOUND,
                value=commit,
            )

    def commit_acceptance(
        self,
        request: OperationalStateRepositoryCommitRequest,
    ) -> OperationalStateRepositoryCommitResult:
        with self._lock:
            state = self._state
            rejection = self._validate_request_shape(request, state)
            if rejection is not None:
                return rejection

            acceptance = request.acceptance_result
            successor = acceptance.successor_state
            acceptance_rule_id = acceptance.applied_acceptance_rule_id
            if successor is None or acceptance_rule_id is None:
                return self._reject(
                    request,
                    OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT,
                    OperationalStateRepositoryCommitReasonCode.MISSING_SUCCESSOR_STATE,
                    "Accepted result does not contain a complete successor proposal.",
                )

            key = OperationalStateRepositoryKey.from_subject(
                successor.subject,
                successor.kind,
            )
            actual_revision = state.revisions_by_key.get(key, 0)
            predecessor_record_or_rejection = self._validate_predecessor(
                request,
                state,
                key,
                actual_revision,
            )
            if isinstance(
                predecessor_record_or_rejection,
                OperationalStateRepositoryCommitResult,
            ):
                return predecessor_record_or_rejection
            predecessor_record = predecessor_record_or_rejection

            revision = actual_revision + 1
            try:
                current_record = OperationalStateRepositoryRecord(
                    state=successor,
                    persisted_status=OperationalStateStatus.CURRENT,
                    acceptance_id=acceptance.id,
                    accepted_evaluation_id=acceptance.accepted_evaluation_id,
                    acceptance_rule_id=acceptance_rule_id,
                    lineage=acceptance.lineage,
                    accepted_at=acceptance.accepted_at,
                    persisted_at=request.commit_at,
                    predecessor_state_id=acceptance.current_state_id,
                    revision=revision,
                    metadata={"repository": "in_memory_contract_validation"},
                )
                superseded_record = self._supersede_predecessor(
                    predecessor_record,
                    successor.id,
                )
            except ValueError as error:
                return self._reject(
                    request,
                    OperationalStateRepositoryCommitOutcome.INVALID_SUCCESSOR_STATE,
                    OperationalStateRepositoryCommitReasonCode.SUCCESSOR_BASIS_MISMATCH,
                    f"Successor cannot form a valid repository record: {error}",
                    actual_revision=actual_revision,
                )

            commit_id = self._commit_id_factory()
            commit_result = OperationalStateRepositoryCommitResult(
                outcome=OperationalStateRepositoryCommitOutcome.COMMITTED,
                reasons=(
                    self._reason(
                        request,
                        OperationalStateRepositoryCommitReasonCode.COMMIT_COMPLETED,
                        "Accepted Operational State was atomically committed.",
                        actual_revision=actual_revision,
                    ),
                ),
                storage_changed=True,
                commit_id=commit_id,
                acceptance_id=acceptance.id,
                evaluation_id=acceptance.accepted_evaluation_id,
                predecessor_state_id=acceptance.current_state_id,
                successor_state_id=successor.id,
                subject=successor.subject,
                state_kind=successor.kind,
                previous_revision=actual_revision,
                committed_revision=revision,
                committed_at=request.commit_at,
                current_state_record=current_record,
                superseded_predecessor_record=superseded_record,
                metadata={"repository": "in_memory_contract_validation"},
            )
            replacement = state.with_commit(
                key=key,
                current_record=current_record,
                superseded_record=superseded_record,
                commit_result=commit_result,
            )
            self._state = replacement
            return commit_result

    def _validate_request_shape(
        self,
        request: OperationalStateRepositoryCommitRequest,
        state: InMemoryOperationalStateRepositoryState,
    ) -> OperationalStateRepositoryCommitResult | None:
        acceptance = request.acceptance_result
        successor = acceptance.successor_state
        if not _is_aware(request.commit_at):
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT,
                OperationalStateRepositoryCommitReasonCode.SUCCESSOR_TIMESTAMP_MISMATCH,
                "Repository commit timestamp must be timezone-aware.",
            )
        if acceptance.outcome is not OperationalStateAcceptanceOutcome.ACCEPTED:
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT,
                OperationalStateRepositoryCommitReasonCode.ACCEPTANCE_RESULT_NOT_ACCEPTED,
                "Repository commit requires an accepted result.",
            )
        if successor is None:
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT,
                OperationalStateRepositoryCommitReasonCode.MISSING_SUCCESSOR_STATE,
                "Accepted result requires one successor state.",
            )
        if acceptance.applied_acceptance_rule_id is None:
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT,
                OperationalStateRepositoryCommitReasonCode.MISSING_LINEAGE,
                "Accepted result requires an acceptance rule identity.",
            )
        if not _is_aware(acceptance.accepted_at):
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT,
                OperationalStateRepositoryCommitReasonCode.SUCCESSOR_TIMESTAMP_MISMATCH,
                "Acceptance timestamp must be timezone-aware for repository storage.",
            )
        if successor.status is not OperationalStateStatus.CURRENT:
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.INVALID_SUCCESSOR_STATE,
                OperationalStateRepositoryCommitReasonCode.SUCCESSOR_STATUS_NOT_CURRENT,
                "Accepted successor must have status current.",
            )
        if successor.kind not in OPERATIONAL_STATE_REPOSITORY_SUPPORTED_KINDS:
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.INVALID_SUCCESSOR_STATE,
                OperationalStateRepositoryCommitReasonCode.SUCCESSOR_KIND_MISMATCH,
                "Accepted successor state kind is outside repository scope.",
            )
        if successor.family is not _SUPPORTED_FAMILY_BY_KIND[successor.kind]:
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.INVALID_SUCCESSOR_STATE,
                OperationalStateRepositoryCommitReasonCode.SUCCESSOR_FAMILY_MISMATCH,
                "Accepted successor family does not match its state kind.",
            )
        if successor.subject != acceptance.target_subject:
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT,
                OperationalStateRepositoryCommitReasonCode.SUCCESSOR_SUBJECT_MISMATCH,
                "Accepted target subject does not match the successor subject.",
            )
        lineage = acceptance.lineage
        if lineage.evaluation_id != acceptance.accepted_evaluation_id:
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT,
                OperationalStateRepositoryCommitReasonCode.MISSING_EVALUATION_IDENTITY,
                "Acceptance and lineage Evaluation identities do not match.",
            )
        if lineage.evaluated_state_kind is not successor.kind:
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT,
                OperationalStateRepositoryCommitReasonCode.SUCCESSOR_KIND_MISMATCH,
                "Accepted lineage state kind does not match the successor.",
            )
        if lineage.proposed_state_value is not successor.value:
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT,
                OperationalStateRepositoryCommitReasonCode.SUCCESSOR_VALUE_MISMATCH,
                "Accepted lineage value does not match the successor value.",
            )
        if lineage.policy_id is None or lineage.applied_rule_id is None:
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT,
                OperationalStateRepositoryCommitReasonCode.MISSING_LINEAGE,
                "Accepted lineage requires policy and transition-rule identities.",
            )
        basis = successor.basis
        if (
            acceptance.accepted_evaluation_id not in basis.transition_evaluation_ids
            or lineage.policy_id not in basis.policy_ids
            or lineage.applied_rule_id not in basis.transition_rule_ids
        ):
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.INVALID_SUCCESSOR_STATE,
                OperationalStateRepositoryCommitReasonCode.SUCCESSOR_BASIS_MISMATCH,
                "Successor basis does not retain Evaluation, policy, and rule identities.",
            )
        if basis.evidence_context is None or basis.evidence_context != lineage.evaluation_context:
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.INVALID_SUCCESSOR_STATE,
                OperationalStateRepositoryCommitReasonCode.SUCCESSOR_CONTEXT_MISMATCH,
                "Successor basis does not retain authoritative accepted Evidence context.",
            )
        if lineage.current_state_id != acceptance.current_state_id:
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT,
                OperationalStateRepositoryCommitReasonCode.EXPECTED_PREDECESSOR_MISMATCH,
                "Acceptance and lineage predecessor identities do not match.",
            )

        evaluation_commit = state.commits_by_evaluation_id.get(
            acceptance.accepted_evaluation_id
        )
        if evaluation_commit is not None:
            if self._is_exact_replay(evaluation_commit, request):
                return self._already_committed(
                    request,
                    evaluation_commit,
                    OperationalStateRepositoryCommitReasonCode.EVALUATION_ALREADY_COMMITTED,
                )
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.LINEAGE_CONFLICT,
                OperationalStateRepositoryCommitReasonCode.LINEAGE_CONFLICT,
                "Evaluation ID is already committed with different accepted lineage.",
            )

        acceptance_commit = state.commits_by_acceptance_id.get(acceptance.id)
        if acceptance_commit is not None:
            if self._is_exact_replay(acceptance_commit, request):
                return self._already_committed(
                    request,
                    acceptance_commit,
                    OperationalStateRepositoryCommitReasonCode.ACCEPTANCE_ALREADY_COMMITTED,
                )
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.LINEAGE_CONFLICT,
                OperationalStateRepositoryCommitReasonCode.LINEAGE_CONFLICT,
                "Acceptance ID is already committed with different accepted lineage.",
            )

        existing_state = state.records_by_state_id.get(successor.id)
        if existing_state is not None:
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.LINEAGE_CONFLICT,
                OperationalStateRepositoryCommitReasonCode.LINEAGE_CONFLICT,
                "Successor state ID already belongs to another committed lineage.",
            )
        return self._validate_supersession_shape(request)

    def _validate_supersession_shape(
        self,
        request: OperationalStateRepositoryCommitRequest,
    ) -> OperationalStateRepositoryCommitResult | None:
        acceptance = request.acceptance_result
        successor = acceptance.successor_state
        predecessor_id = acceptance.current_state_id
        supersession = acceptance.supersession
        if successor is None:
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT,
                OperationalStateRepositoryCommitReasonCode.MISSING_SUCCESSOR_STATE,
                "Accepted result requires one successor state.",
            )
        if predecessor_id is None:
            if supersession is not None:
                return self._reject(
                    request,
                    OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT,
                    OperationalStateRepositoryCommitReasonCode.SUPERSESSION_MISMATCH,
                    "Initial acceptance must not contain supersession.",
                )
            if request.expected_current_state_id is not None:
                return self._reject(
                    request,
                    OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT,
                    OperationalStateRepositoryCommitReasonCode.EXPECTED_PREDECESSOR_MISMATCH,
                    "Initial acceptance cannot expect a predecessor.",
                )
            return None

        if request.expected_current_state_id is None:
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT,
                OperationalStateRepositoryCommitReasonCode.EXPECTED_PREDECESSOR_MISSING,
                "Successor commit request must explicitly identify its predecessor.",
            )
        if request.expected_current_state_id != predecessor_id:
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT,
                OperationalStateRepositoryCommitReasonCode.EXPECTED_PREDECESSOR_MISMATCH,
                "Commit request predecessor contradicts the accepted result.",
            )
        if supersession is None:
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT,
                OperationalStateRepositoryCommitReasonCode.SUPERSESSION_MISSING,
                "Successor acceptance requires a supersession description.",
            )
        if (
            supersession.predecessor_state_id != predecessor_id
            or supersession.successor_state_id != successor.id
            or supersession.transition_evaluation_id != acceptance.accepted_evaluation_id
            or supersession.accepted_at != acceptance.accepted_at
            or supersession.predecessor_status_before_acceptance
            is not OperationalStateStatus.CURRENT
            or supersession.successor_status is not OperationalStateStatus.CURRENT
        ):
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT,
                OperationalStateRepositoryCommitReasonCode.SUPERSESSION_MISMATCH,
                "Supersession description contradicts accepted predecessor or successor.",
            )
        if predecessor_id == successor.id:
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.INVALID_SUCCESSOR_STATE,
                OperationalStateRepositoryCommitReasonCode.SUPERSESSION_MISMATCH,
                "Successor state ID must differ from its predecessor.",
            )
        return None

    def _validate_predecessor(
        self,
        request: OperationalStateRepositoryCommitRequest,
        state: InMemoryOperationalStateRepositoryState,
        key: OperationalStateRepositoryKey,
        actual_revision: int,
    ) -> OperationalStateRepositoryRecord | OperationalStateRepositoryCommitResult | None:
        acceptance = request.acceptance_result
        successor = acceptance.successor_state
        predecessor_id = acceptance.current_state_id
        current_state_id = state.current_state_id_by_key.get(key)
        if successor is None:
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT,
                OperationalStateRepositoryCommitReasonCode.MISSING_SUCCESSOR_STATE,
                "Accepted result requires one successor state.",
            )

        if predecessor_id is None:
            if current_state_id is not None:
                return self._reject(
                    request,
                    OperationalStateRepositoryCommitOutcome.CURRENT_STATE_CONFLICT,
                    OperationalStateRepositoryCommitReasonCode.UNEXPECTED_CURRENT_STATE,
                    "Initial commit cannot replace an existing current state.",
                    actual_revision=actual_revision,
                )
            if request.expected_revision is not None and request.expected_revision != 0:
                return self._reject(
                    request,
                    OperationalStateRepositoryCommitOutcome.STALE_PREDECESSOR,
                    OperationalStateRepositoryCommitReasonCode.REPOSITORY_REVISION_MISMATCH,
                    "Expected repository revision does not match the empty history.",
                    actual_revision=actual_revision,
                )
            return None

        if current_state_id != predecessor_id:
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.STALE_PREDECESSOR,
                OperationalStateRepositoryCommitReasonCode.EXPECTED_PREDECESSOR_NOT_CURRENT,
                "Accepted predecessor is no longer the repository current state.",
                actual_revision=actual_revision,
            )
        predecessor = state.records_by_state_id.get(predecessor_id)
        if predecessor is None or predecessor.status is not OperationalStateStatus.CURRENT:
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.STALE_PREDECESSOR,
                OperationalStateRepositoryCommitReasonCode.EXPECTED_PREDECESSOR_NOT_CURRENT,
                "Accepted predecessor is missing or no longer persisted as current.",
                actual_revision=actual_revision,
            )
        if predecessor.subject != successor.subject or predecessor.kind is not successor.kind:
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.SUBJECT_KIND_CONFLICT,
                OperationalStateRepositoryCommitReasonCode.LINEAGE_CONFLICT,
                "Persisted predecessor and accepted successor do not share a subject-kind key.",
                actual_revision=actual_revision,
            )
        if (
            request.expected_revision is not None
            and request.expected_revision != actual_revision
        ):
            return self._reject(
                request,
                OperationalStateRepositoryCommitOutcome.STALE_PREDECESSOR,
                OperationalStateRepositoryCommitReasonCode.REPOSITORY_REVISION_MISMATCH,
                "Expected repository revision does not match current history.",
                actual_revision=actual_revision,
            )
        return predecessor

    @staticmethod
    def _supersede_predecessor(
        predecessor: OperationalStateRepositoryRecord | None,
        successor_state_id: EntityId,
    ) -> OperationalStateRepositoryRecord | None:
        if predecessor is None:
            return None
        return OperationalStateRepositoryRecord(
            state=predecessor.state,
            persisted_status=OperationalStateStatus.SUPERSEDED,
            acceptance_id=predecessor.acceptance_id,
            accepted_evaluation_id=predecessor.accepted_evaluation_id,
            acceptance_rule_id=predecessor.acceptance_rule_id,
            lineage=predecessor.lineage,
            accepted_at=predecessor.accepted_at,
            persisted_at=predecessor.persisted_at,
            predecessor_state_id=predecessor.predecessor_state_id,
            successor_state_id=successor_state_id,
            revision=predecessor.revision,
            metadata=predecessor.metadata,
        )

    @staticmethod
    def _is_exact_replay(
        original: OperationalStateRepositoryCommitResult,
        request: OperationalStateRepositoryCommitRequest,
    ) -> bool:
        acceptance = request.acceptance_result
        successor = acceptance.successor_state
        record = original.current_state_record
        return bool(
            successor is not None
            and record is not None
            and original.acceptance_id == acceptance.id
            and original.evaluation_id == acceptance.accepted_evaluation_id
            and original.predecessor_state_id == acceptance.current_state_id
            and original.successor_state_id == successor.id
            and original.subject == successor.subject
            and original.state_kind is successor.kind
            and record.state == successor
            and record.lineage == acceptance.lineage
            and record.acceptance_rule_id == acceptance.applied_acceptance_rule_id
            and record.accepted_at == acceptance.accepted_at
        )

    def _already_committed(
        self,
        request: OperationalStateRepositoryCommitRequest,
        original: OperationalStateRepositoryCommitResult,
        reason_code: OperationalStateRepositoryCommitReasonCode,
    ) -> OperationalStateRepositoryCommitResult:
        return OperationalStateRepositoryCommitResult(
            outcome=OperationalStateRepositoryCommitOutcome.ALREADY_COMMITTED,
            reasons=(
                self._reason(
                    request,
                    reason_code,
                    "Exact accepted lineage already belongs to the original commit.",
                    actual_revision=original.committed_revision,
                ),
            ),
            storage_changed=False,
            commit_id=original.commit_id,
            acceptance_id=original.acceptance_id,
            evaluation_id=original.evaluation_id,
            predecessor_state_id=original.predecessor_state_id,
            successor_state_id=original.successor_state_id,
            subject=original.subject,
            state_kind=original.state_kind,
            previous_revision=original.previous_revision,
            committed_revision=original.committed_revision,
            committed_at=original.committed_at,
            metadata={"replayed_original_commit": True},
        )

    def _reject(
        self,
        request: OperationalStateRepositoryCommitRequest,
        outcome: OperationalStateRepositoryCommitOutcome,
        reason_code: OperationalStateRepositoryCommitReasonCode,
        message: str,
        *,
        actual_revision: int | None = None,
    ) -> OperationalStateRepositoryCommitResult:
        acceptance = request.acceptance_result
        successor = acceptance.successor_state
        return OperationalStateRepositoryCommitResult(
            outcome=outcome,
            reasons=(
                self._reason(
                    request,
                    reason_code,
                    message,
                    actual_revision=actual_revision,
                ),
            ),
            storage_changed=False,
            acceptance_id=acceptance.id,
            evaluation_id=acceptance.accepted_evaluation_id,
            predecessor_state_id=acceptance.current_state_id,
            successor_state_id=successor.id if successor is not None else None,
            subject=acceptance.target_subject,
            state_kind=acceptance.lineage.evaluated_state_kind,
            previous_revision=actual_revision,
        )

    @staticmethod
    def _reason(
        request: OperationalStateRepositoryCommitRequest,
        code: OperationalStateRepositoryCommitReasonCode,
        message: str,
        *,
        actual_revision: int | None = None,
    ) -> OperationalStateRepositoryCommitReason:
        acceptance = request.acceptance_result
        successor = acceptance.successor_state
        return OperationalStateRepositoryCommitReason(
            code=code,
            message=message,
            acceptance_id=acceptance.id,
            evaluation_id=acceptance.accepted_evaluation_id,
            predecessor_state_id=acceptance.current_state_id,
            successor_state_id=successor.id if successor is not None else None,
            subject=acceptance.target_subject,
            state_kind=acceptance.lineage.evaluated_state_kind,
            expected_revision=request.expected_revision,
            actual_revision=actual_revision,
        )
