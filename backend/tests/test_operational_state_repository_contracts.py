from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass
from datetime import UTC, datetime, timedelta
from inspect import isabstract, signature
from typing import Any, cast

import pytest

from app.contexts.production.evidence import EvidenceContext, EvidenceSignal
from app.contexts.production.operational_state import (
    OperationalState,
    OperationalStateBasis,
    OperationalStateFamily,
    OperationalStateKind,
    OperationalStateStatus,
    OperationalStateSubject,
    OperationalStateSubjectType,
    OperationalStateValue,
)
from app.contexts.production.operational_state_acceptance import (
    OperationalStateAcceptanceLineage,
)
from app.contexts.production.operational_state_repository import (
    OPERATIONAL_STATE_REPOSITORY_SUPPORTED_KINDS,
    OperationalStateRepository,
    OperationalStateRepositoryCommitOutcome,
    OperationalStateRepositoryCommitReason,
    OperationalStateRepositoryCommitRequest,
    OperationalStateRepositoryCommitResult,
    OperationalStateRepositoryError,
    OperationalStateRepositoryHistory,
    OperationalStateRepositoryQueryOutcome,
    OperationalStateRepositoryQueryResult,
    OperationalStateRepositoryRecord,
)
from app.shared.ids import EntityId


def _subject(identifier: str = "block-a") -> OperationalStateSubject:
    return OperationalStateSubject(
        subject_type=OperationalStateSubjectType.RECORDING_BLOCK,
        subject_identifier=identifier,
    )


def _lineage(
    *,
    evaluation_id: EntityId,
    policy_id: EntityId,
    rule_id: EntityId,
    context: EvidenceContext,
    current_state_id: EntityId | None = None,
    current_value: OperationalStateValue = OperationalStateValue.INACTIVE,
    proposed_value: OperationalStateValue = OperationalStateValue.ACTIVE,
) -> OperationalStateAcceptanceLineage:
    lineage_id = EntityId.new()
    return OperationalStateAcceptanceLineage(
        evaluation_id=evaluation_id,
        policy_kind="recording_transition_policy",
        policy_id=policy_id,
        applied_rule_id=rule_id,
        evaluated_state_kind=OperationalStateKind.RECORDING_STATE,
        current_state_id=current_state_id,
        effective_current_value=current_value,
        proposed_state_value=proposed_value,
        supporting_evidence_set_ids=(lineage_id,),
        contributing_evidence_item_ids=(lineage_id,),
        contributing_observation_ids=(lineage_id,),
        contributing_production_event_ids=(lineage_id,),
        contributing_signals=(EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,),
        interpreter_ids=(lineage_id,),
        interpretation_rule_ids=("recording_activity_started",),
        evaluation_context=context,
    )


def _record(
    *,
    state_id: EntityId | None = None,
    subject: OperationalStateSubject | None = None,
    persisted_status: OperationalStateStatus = OperationalStateStatus.CURRENT,
    predecessor_state_id: EntityId | None = None,
    successor_state_id: EntityId | None = None,
    revision: int = 1,
    accepted_at: datetime | None = None,
    persisted_at: datetime | None = None,
    proposed_value: OperationalStateValue = OperationalStateValue.ACTIVE,
    family: OperationalStateFamily = OperationalStateFamily.DIRECTLY_OBSERVABLE,
) -> OperationalStateRepositoryRecord:
    resolved_state_id = state_id or EntityId.new()
    resolved_subject = subject or _subject()
    evaluation_id = EntityId.new()
    policy_id = EntityId.new()
    rule_id = EntityId.new()
    context = EvidenceContext(source_context_ids=(EntityId.new(),))
    current_value = (
        OperationalStateValue.INACTIVE
        if proposed_value is OperationalStateValue.ACTIVE
        else OperationalStateValue.ACTIVE
    )
    lineage = _lineage(
        evaluation_id=evaluation_id,
        policy_id=policy_id,
        rule_id=rule_id,
        context=context,
        current_state_id=predecessor_state_id,
        current_value=current_value,
        proposed_value=proposed_value,
    )
    state = OperationalState(
        id=resolved_state_id,
        family=family,
        kind=OperationalStateKind.RECORDING_STATE,
        subject=resolved_subject,
        value=proposed_value,
        status=OperationalStateStatus.CURRENT,
        basis=OperationalStateBasis(
            observation_ids=lineage.contributing_observation_ids,
            evidence_set_ids=lineage.supporting_evidence_set_ids,
            transition_evaluation_ids=(evaluation_id,),
            policy_ids=(policy_id,),
            transition_rule_ids=(rule_id,),
            evidence_context=context,
        ),
        observed_or_derived_at=datetime(2026, 7, 16, 12, 0, tzinfo=UTC),
    )
    return OperationalStateRepositoryRecord(
        state=state,
        persisted_status=persisted_status,
        acceptance_id=EntityId.new(),
        accepted_evaluation_id=evaluation_id,
        acceptance_rule_id=EntityId.new(),
        lineage=lineage,
        accepted_at=accepted_at or datetime(2026, 7, 16, 12, 0, tzinfo=UTC),
        persisted_at=persisted_at or datetime(2026, 7, 16, 12, revision, tzinfo=UTC),
        predecessor_state_id=predecessor_state_id,
        successor_state_id=successor_state_id,
        revision=revision,
    )


def test_repository_is_an_abstract_contract_with_exact_operations() -> None:
    expected = {
        "get_current_state",
        "get_state",
        "list_state_history",
        "has_committed_evaluation",
        "get_commit_by_evaluation",
        "commit_acceptance",
    }

    assert isabstract(OperationalStateRepository)
    assert OperationalStateRepository.__abstractmethods__ == expected
    assert tuple(signature(OperationalStateRepository.get_current_state).parameters) == (
        "self",
        "subject",
        "state_kind",
    )
    assert tuple(signature(OperationalStateRepository.get_state).parameters) == (
        "self",
        "state_id",
    )
    assert tuple(signature(OperationalStateRepository.commit_acceptance).parameters) == (
        "self",
        "request",
    )


def test_repository_contracts_are_frozen_and_supported_scope_is_narrow() -> None:
    contracts = (
        OperationalStateRepositoryCommitReason,
        OperationalStateRepositoryCommitRequest,
        OperationalStateRepositoryCommitResult,
        OperationalStateRepositoryError,
        OperationalStateRepositoryHistory,
        OperationalStateRepositoryQueryResult,
        OperationalStateRepositoryRecord,
    )

    assert all(is_dataclass(contract) for contract in contracts)
    assert all(cast(Any, contract).__dataclass_params__.frozen for contract in contracts)
    assert OPERATIONAL_STATE_REPOSITORY_SUPPORTED_KINDS == (
        OperationalStateKind.RECORDING_STATE,
        OperationalStateKind.SESSION_STATE,
    )


def test_commit_outcomes_are_exactly_the_approved_values() -> None:
    assert tuple(outcome.value for outcome in OperationalStateRepositoryCommitOutcome) == (
        "committed",
        "already_committed",
        "stale_predecessor",
        "current_state_conflict",
        "subject_kind_conflict",
        "invalid_acceptance_result",
        "invalid_successor_state",
        "lineage_conflict",
        "not_found",
        "unknown",
    )


def test_query_results_distinguish_found_not_found_conflict_and_failure() -> None:
    record = _record()
    found = OperationalStateRepositoryQueryResult(
        outcome=OperationalStateRepositoryQueryOutcome.FOUND,
        value=record,
        metadata={"source": "contract"},
    )
    missing = OperationalStateRepositoryQueryResult[OperationalStateRepositoryRecord](
        outcome=OperationalStateRepositoryQueryOutcome.NOT_FOUND,
    )
    conflict = OperationalStateRepositoryQueryResult[OperationalStateRepositoryRecord](
        outcome=OperationalStateRepositoryQueryOutcome.CURRENT_STATE_CONFLICT,
    )

    assert found.is_found
    assert found.value is record
    assert not missing.is_found and missing.value is None
    assert conflict.outcome is OperationalStateRepositoryQueryOutcome.CURRENT_STATE_CONFLICT
    with pytest.raises(ValueError, match="requires a value"):
        OperationalStateRepositoryQueryResult[OperationalStateRepositoryRecord](
            outcome=OperationalStateRepositoryQueryOutcome.FOUND
        )
    with pytest.raises(ValueError, match="cannot contain a value"):
        OperationalStateRepositoryQueryResult(
            outcome=OperationalStateRepositoryQueryOutcome.NOT_FOUND,
            value=record,
        )


def test_record_preserves_identity_lineage_context_and_persisted_status() -> None:
    successor_id = EntityId.new()
    record = _record(
        persisted_status=OperationalStateStatus.SUPERSEDED,
        successor_state_id=successor_id,
    )

    assert record.state_id == record.state.id
    assert record.subject == record.state.subject
    assert record.kind is OperationalStateKind.RECORDING_STATE
    assert record.family is OperationalStateFamily.DIRECTLY_OBSERVABLE
    assert record.status is OperationalStateStatus.SUPERSEDED
    assert record.state.status is OperationalStateStatus.CURRENT
    assert record.accepted_evaluation_id == record.lineage.evaluation_id
    assert record.evidence_context == record.lineage.evaluation_context
    assert record.lineage.contributing_production_event_ids
    assert record.lineage.contributing_observation_ids
    assert record.lineage.supporting_evidence_set_ids
    with pytest.raises(FrozenInstanceError):
        record.persisted_status = OperationalStateStatus.CURRENT  # type: ignore[misc]


def test_record_rejects_naive_persisted_time_and_incomplete_supersession() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _record(accepted_at=datetime(2026, 7, 16, 12, 0))
    with pytest.raises(ValueError, match="timezone-aware"):
        _record(persisted_at=datetime(2026, 7, 16, 12, 0))
    with pytest.raises(ValueError, match="requires a successor"):
        _record(persisted_status=OperationalStateStatus.SUPERSEDED)
    with pytest.raises(ValueError, match="family must match"):
        _record(family=OperationalStateFamily.EVIDENCE_DERIVED)


def test_history_is_subject_kind_isolated_immutable_and_oldest_to_newest() -> None:
    subject = _subject()
    first_id = EntityId.new()
    second_id = EntityId.new()
    first = _record(
        state_id=first_id,
        subject=subject,
        persisted_status=OperationalStateStatus.SUPERSEDED,
        successor_state_id=second_id,
        revision=1,
        persisted_at=datetime(2026, 7, 16, 12, 0, tzinfo=UTC),
    )
    second = _record(
        state_id=second_id,
        subject=subject,
        predecessor_state_id=first_id,
        revision=2,
        persisted_at=datetime(2026, 7, 16, 12, 1, tzinfo=UTC),
        proposed_value=OperationalStateValue.PAUSED,
    )
    history = OperationalStateRepositoryHistory(
        subject=subject,
        state_kind=OperationalStateKind.RECORDING_STATE,
        records=(first, second),
        current_state_id=second_id,
        earliest_state_id=first_id,
        latest_committed_evaluation_id=second.accepted_evaluation_id,
        revision=2,
    )

    assert history.state_ids == (first_id, second_id)
    assert history.records == (first, second)
    with pytest.raises(ValueError, match="oldest to newest"):
        OperationalStateRepositoryHistory(
            subject=subject,
            state_kind=OperationalStateKind.RECORDING_STATE,
            records=(second, first),
            current_state_id=first_id,
            earliest_state_id=second_id,
            latest_committed_evaluation_id=first.accepted_evaluation_id,
        )
    with pytest.raises(ValueError, match="cannot mix subjects"):
        OperationalStateRepositoryHistory(
            subject=_subject("different-block"),
            state_kind=OperationalStateKind.RECORDING_STATE,
            records=(first,),
            current_state_id=first_id,
            earliest_state_id=first_id,
            latest_committed_evaluation_id=first.accepted_evaluation_id,
        )
    with pytest.raises(ValueError, match="strictly monotonic"):
        duplicate_revision = _record(
            state_id=second_id,
            subject=subject,
            predecessor_state_id=first_id,
            revision=1,
            persisted_at=datetime(2026, 7, 16, 12, 1, tzinfo=UTC),
            proposed_value=OperationalStateValue.PAUSED,
        )
        OperationalStateRepositoryHistory(
            subject=subject,
            state_kind=OperationalStateKind.RECORDING_STATE,
            records=(first, duplicate_revision),
            current_state_id=second_id,
            earliest_state_id=first_id,
            latest_committed_evaluation_id=duplicate_revision.accepted_evaluation_id,
            revision=1,
        )


def test_history_order_uses_revision_time_and_state_identity_deterministically() -> None:
    subject = _subject()
    now = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    first_id = EntityId.new()
    second_id = EntityId.new()
    first = _record(
        state_id=first_id,
        subject=subject,
        persisted_status=OperationalStateStatus.SUPERSEDED,
        successor_state_id=second_id,
        revision=1,
        persisted_at=now,
    )
    second = _record(
        state_id=second_id,
        subject=subject,
        predecessor_state_id=first_id,
        revision=2,
        persisted_at=now + timedelta(seconds=1),
        proposed_value=OperationalStateValue.PAUSED,
    )

    assert first.revision < second.revision  # type: ignore[operator]
    assert first.persisted_at < second.persisted_at
