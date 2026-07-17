from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta

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
    OperationalStateAcceptanceOutcome,
    OperationalStateAcceptanceReason,
    OperationalStateAcceptanceReasonCode,
    OperationalStateAcceptanceResult,
    OperationalStateSupersession,
)
from app.contexts.production.operational_state_repository import (
    OperationalStateRepositoryCommitOutcome,
    OperationalStateRepositoryCommitReason,
    OperationalStateRepositoryCommitReasonCode,
    OperationalStateRepositoryCommitRequest,
    OperationalStateRepositoryCommitResult,
    OperationalStateRepositoryError,
    OperationalStateRepositoryErrorCode,
    OperationalStateRepositoryRecord,
)
from app.shared.ids import EntityId

NOW = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)


def _subject() -> OperationalStateSubject:
    return OperationalStateSubject(
        subject_type=OperationalStateSubjectType.RECORDING_BLOCK,
        subject_identifier="block-a",
    )


def _accepted_result(
    *,
    predecessor: OperationalState | None = None,
    proposed_value: OperationalStateValue = OperationalStateValue.ACTIVE,
    evaluation_at: datetime = NOW,
    accepted_at: datetime = NOW,
) -> OperationalStateAcceptanceResult:
    subject = predecessor.subject if predecessor is not None else _subject()
    evaluation_id = EntityId.new()
    policy_id = EntityId.new()
    transition_rule_id = EntityId.new()
    acceptance_rule_id = EntityId.new()
    lineage_id = EntityId.new()
    context = EvidenceContext(source_context_ids=(EntityId.new(),))
    lineage = OperationalStateAcceptanceLineage(
        evaluation_id=evaluation_id,
        policy_kind="recording_transition_policy",
        policy_id=policy_id,
        applied_rule_id=transition_rule_id,
        evaluated_state_kind=OperationalStateKind.RECORDING_STATE,
        current_state_id=predecessor.id if predecessor is not None else None,
        effective_current_value=(
            predecessor.value if predecessor is not None else OperationalStateValue.INACTIVE
        ),
        proposed_state_value=proposed_value,
        supporting_evidence_set_ids=(lineage_id,),
        contributing_evidence_item_ids=(lineage_id,),
        contributing_observation_ids=(lineage_id,),
        contributing_production_event_ids=(lineage_id,),
        contributing_signals=(EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,),
        interpreter_ids=(lineage_id,),
        interpretation_rule_ids=("recording_activity",),
        organizational_anchors=("2026-07-16T11:59:00+00:00",),
        evaluation_context=context,
    )
    successor = OperationalState(
        id=EntityId.new(),
        family=OperationalStateFamily.DIRECTLY_OBSERVABLE,
        kind=OperationalStateKind.RECORDING_STATE,
        subject=subject,
        value=proposed_value,
        status=OperationalStateStatus.CURRENT,
        basis=OperationalStateBasis(
            observation_ids=lineage.contributing_observation_ids,
            evidence_set_ids=lineage.supporting_evidence_set_ids,
            transition_evaluation_ids=(evaluation_id,),
            policy_ids=(policy_id,),
            transition_rule_ids=(transition_rule_id,),
            evidence_context=context,
        ),
        observed_or_derived_at=evaluation_at,
    )
    supersession = (
        OperationalStateSupersession(
            predecessor_state_id=predecessor.id,
            successor_state_id=successor.id,
            transition_evaluation_id=evaluation_id,
            accepted_at=accepted_at,
            predecessor_status_before_acceptance=OperationalStateStatus.CURRENT,
            successor_status=OperationalStateStatus.CURRENT,
            reason="Accepted successor will supersede the expected predecessor on commit.",
        )
        if predecessor is not None
        else None
    )
    return OperationalStateAcceptanceResult(
        id=EntityId.new(),
        outcome=OperationalStateAcceptanceOutcome.ACCEPTED,
        accepted_evaluation_id=evaluation_id,
        reasons=(
            OperationalStateAcceptanceReason(
                code=OperationalStateAcceptanceReasonCode.SUCCESSOR_CREATED,
                message="Acceptance created one immutable successor proposal.",
                evaluation_id=evaluation_id,
                current_state_id=predecessor.id if predecessor is not None else None,
                subject_identifier=subject.subject_identifier,
            ),
        ),
        current_state_id=predecessor.id if predecessor is not None else None,
        target_subject=subject,
        successor_state=successor,
        supersession=supersession,
        lineage=lineage,
        applied_acceptance_rule_id=acceptance_rule_id,
        accepted_at=accepted_at,
    )


def _record_from_result(
    result: OperationalStateAcceptanceResult,
    *,
    persisted_status: OperationalStateStatus,
    persisted_at: datetime,
    revision: int,
    successor_state_id: EntityId | None = None,
) -> OperationalStateRepositoryRecord:
    state = result.successor_state
    acceptance_rule_id = result.applied_acceptance_rule_id
    if state is None or acceptance_rule_id is None:
        raise AssertionError("Test fixture requires one accepted successor.")
    return OperationalStateRepositoryRecord(
        state=state,
        persisted_status=persisted_status,
        acceptance_id=result.id,
        accepted_evaluation_id=result.accepted_evaluation_id,
        acceptance_rule_id=acceptance_rule_id,
        lineage=result.lineage,
        accepted_at=result.accepted_at,
        persisted_at=persisted_at,
        predecessor_state_id=result.current_state_id,
        successor_state_id=successor_state_id,
        revision=revision,
    )


def _reason(
    code: OperationalStateRepositoryCommitReasonCode,
    result: OperationalStateAcceptanceResult,
) -> OperationalStateRepositoryCommitReason:
    successor = result.successor_state
    return OperationalStateRepositoryCommitReason(
        code=code,
        message=f"Repository outcome: {code.value}.",
        acceptance_id=result.id,
        evaluation_id=result.accepted_evaluation_id,
        predecessor_state_id=result.current_state_id,
        successor_state_id=successor.id if successor is not None else None,
        subject=result.target_subject,
        state_kind=result.lineage.evaluated_state_kind,
    )


def test_commit_request_contains_one_acceptance_and_no_raw_domain_inputs() -> None:
    result = _accepted_result()
    metadata = {"trace": "request-a"}
    request = OperationalStateRepositoryCommitRequest(
        acceptance_result=result,
        commit_at=NOW,
        expected_current_state_id=None,
        expected_revision=0,
        request_id=EntityId.new(),
        metadata=metadata,
    )
    metadata["trace"] = "mutated"
    names = {field.name for field in fields(OperationalStateRepositoryCommitRequest)}

    assert request.acceptance_result is result
    assert request.acceptance_id == result.id
    assert request.evaluation_id == result.accepted_evaluation_id
    assert request.successor_state_id == result.successor_state.id  # type: ignore[union-attr]
    assert request.metadata["trace"] == "request-a"
    assert not {
        "production_events",
        "observations",
        "evidence_sets",
        "policy",
        "transition_evaluation",
        "session",
    } & names
    with pytest.raises(TypeError):
        request.metadata["trace"] = "forbidden"  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        request.expected_revision = 1  # type: ignore[misc]


def test_commit_request_requires_timezone_aware_commit_time_and_valid_revision() -> None:
    result = _accepted_result()
    with pytest.raises(ValueError, match="timezone-aware"):
        OperationalStateRepositoryCommitRequest(
            acceptance_result=result,
            commit_at=datetime(2026, 7, 16, 12, 0),
        )
    with pytest.raises(ValueError, match="must not be negative"):
        OperationalStateRepositoryCommitRequest(
            acceptance_result=result,
            commit_at=NOW,
            expected_revision=-1,
        )


def test_record_preserves_distinct_evaluation_acceptance_and_persistence_times() -> None:
    evaluation_at = NOW
    accepted_at = NOW + timedelta(seconds=2)
    persisted_at = NOW + timedelta(seconds=3)
    accepted = _accepted_result(
        evaluation_at=evaluation_at,
        accepted_at=accepted_at,
    )
    record = _record_from_result(
        accepted,
        persisted_status=OperationalStateStatus.CURRENT,
        persisted_at=persisted_at,
        revision=1,
    )

    assert record.evaluation_at == evaluation_at
    assert record.accepted_at == accepted_at
    assert record.persisted_at == persisted_at
    assert len({record.evaluation_at, record.accepted_at, record.persisted_at}) == 3


def test_successor_request_makes_expected_predecessor_explicit() -> None:
    initial = _accepted_result()
    predecessor = initial.successor_state
    assert predecessor is not None
    successor = _accepted_result(
        predecessor=predecessor,
        proposed_value=OperationalStateValue.PAUSED,
        accepted_at=datetime(2026, 7, 16, 12, 1, tzinfo=UTC),
    )
    request = OperationalStateRepositoryCommitRequest(
        acceptance_result=successor,
        commit_at=datetime(2026, 7, 16, 12, 2, tzinfo=UTC),
        expected_current_state_id=predecessor.id,
        expected_revision=1,
    )

    assert request.expected_current_state_id == successor.current_state_id
    assert successor.supersession is not None
    assert successor.supersession.predecessor_state_id == request.expected_current_state_id


def test_nonaccepted_result_can_only_reach_repository_as_invalid_commit_shape() -> None:
    accepted = _accepted_result()
    rejected = OperationalStateAcceptanceResult(
        id=EntityId.new(),
        outcome=OperationalStateAcceptanceOutcome.REJECTED_INVALID_LINEAGE,
        accepted_evaluation_id=accepted.accepted_evaluation_id,
        reasons=(
            OperationalStateAcceptanceReason(
                code=OperationalStateAcceptanceReasonCode.MISSING_EVENT_LINEAGE,
                message="Event lineage is missing.",
                evaluation_id=accepted.accepted_evaluation_id,
            ),
        ),
        current_state_id=None,
        target_subject=accepted.target_subject,
        successor_state=None,
        supersession=None,
        lineage=accepted.lineage,
        applied_acceptance_rule_id=None,
        accepted_at=NOW,
    )
    request = OperationalStateRepositoryCommitRequest(
        acceptance_result=rejected,
        commit_at=NOW,
    )
    no_change = OperationalStateRepositoryCommitResult(
        outcome=OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT,
        reasons=(
            _reason(
                OperationalStateRepositoryCommitReasonCode.ACCEPTANCE_RESULT_NOT_ACCEPTED,
                rejected,
            ),
        ),
        storage_changed=False,
        acceptance_id=rejected.id,
        evaluation_id=rejected.accepted_evaluation_id,
        subject=rejected.target_subject,
        state_kind=rejected.lineage.evaluated_state_kind,
    )

    assert not request.acceptance_result.is_accepted
    assert no_change.outcome is OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT
    assert not no_change.storage_changed


def test_reason_codes_cover_shape_idempotency_concurrency_and_completion() -> None:
    required = {
        "acceptance_result_not_accepted",
        "missing_successor_state",
        "missing_acceptance_identity",
        "missing_evaluation_identity",
        "missing_lineage",
        "successor_status_not_current",
        "successor_subject_mismatch",
        "successor_kind_mismatch",
        "successor_basis_mismatch",
        "evaluation_already_committed",
        "acceptance_already_committed",
        "expected_predecessor_missing",
        "expected_predecessor_not_current",
        "expected_predecessor_mismatch",
        "unexpected_current_state",
        "repository_revision_mismatch",
        "supersession_mismatch",
        "commit_completed",
        "not_found",
        "unknown",
    }

    assert required <= {code.value for code in OperationalStateRepositoryCommitReasonCode}


def test_commit_reasons_are_deduplicated_and_ordered_by_semantics() -> None:
    result = _accepted_result()
    second = _reason(
        OperationalStateRepositoryCommitReasonCode.SUCCESSOR_BASIS_MISMATCH,
        result,
    )
    first = _reason(
        OperationalStateRepositoryCommitReasonCode.ACCEPTANCE_RESULT_NOT_ACCEPTED,
        result,
    )
    commit_result = OperationalStateRepositoryCommitResult(
        outcome=OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT,
        reasons=(second, first, second),
        storage_changed=False,
        acceptance_id=result.id,
        evaluation_id=result.accepted_evaluation_id,
        successor_state_id=result.successor_state.id,  # type: ignore[union-attr]
        subject=result.target_subject,
        state_kind=result.lineage.evaluated_state_kind,
    )

    assert tuple(reason.code for reason in commit_result.reasons) == (
        OperationalStateRepositoryCommitReasonCode.ACCEPTANCE_RESULT_NOT_ACCEPTED,
        OperationalStateRepositoryCommitReasonCode.SUCCESSOR_BASIS_MISMATCH,
    )


def test_initial_commit_result_requires_complete_atomic_shape() -> None:
    accepted = _accepted_result()
    record = _record_from_result(
        accepted,
        persisted_status=OperationalStateStatus.CURRENT,
        persisted_at=NOW,
        revision=1,
    )
    result = OperationalStateRepositoryCommitResult(
        outcome=OperationalStateRepositoryCommitOutcome.COMMITTED,
        reasons=(
            _reason(OperationalStateRepositoryCommitReasonCode.COMMIT_COMPLETED, accepted),
        ),
        storage_changed=True,
        commit_id=EntityId.new(),
        acceptance_id=accepted.id,
        evaluation_id=accepted.accepted_evaluation_id,
        successor_state_id=record.state_id,
        subject=record.subject,
        state_kind=record.kind,
        previous_revision=0,
        committed_revision=1,
        committed_at=NOW,
        current_state_record=record,
    )

    assert result.storage_changed
    assert result.predecessor_state_id is None
    assert result.superseded_predecessor_record is None
    with pytest.raises(ValueError, match="complete commit identity"):
        OperationalStateRepositoryCommitResult(
            outcome=OperationalStateRepositoryCommitOutcome.COMMITTED,
            reasons=result.reasons,
            storage_changed=True,
        )


def test_successor_commit_result_requires_authoritative_supersession() -> None:
    initial = _accepted_result()
    predecessor = initial.successor_state
    assert predecessor is not None
    accepted = _accepted_result(
        predecessor=predecessor,
        proposed_value=OperationalStateValue.PAUSED,
        accepted_at=datetime(2026, 7, 16, 12, 1, tzinfo=UTC),
    )
    successor = accepted.successor_state
    assert successor is not None
    predecessor_record = _record_from_result(
        initial,
        persisted_status=OperationalStateStatus.SUPERSEDED,
        persisted_at=NOW,
        revision=1,
        successor_state_id=successor.id,
    )
    successor_record = _record_from_result(
        accepted,
        persisted_status=OperationalStateStatus.CURRENT,
        persisted_at=datetime(2026, 7, 16, 12, 2, tzinfo=UTC),
        revision=2,
    )
    result = OperationalStateRepositoryCommitResult(
        outcome=OperationalStateRepositoryCommitOutcome.COMMITTED,
        reasons=(
            _reason(OperationalStateRepositoryCommitReasonCode.COMMIT_COMPLETED, accepted),
        ),
        storage_changed=True,
        commit_id=EntityId.new(),
        acceptance_id=accepted.id,
        evaluation_id=accepted.accepted_evaluation_id,
        predecessor_state_id=predecessor.id,
        successor_state_id=successor.id,
        subject=successor.subject,
        state_kind=successor.kind,
        previous_revision=1,
        committed_revision=2,
        committed_at=datetime(2026, 7, 16, 12, 2, tzinfo=UTC),
        current_state_record=successor_record,
        superseded_predecessor_record=predecessor_record,
    )

    assert result.current_state_record is successor_record
    assert result.superseded_predecessor_record is predecessor_record
    assert predecessor.status is OperationalStateStatus.CURRENT
    assert predecessor_record.status is OperationalStateStatus.SUPERSEDED
    with pytest.raises(ValueError, match="persisted superseded predecessor"):
        OperationalStateRepositoryCommitResult(
            outcome=OperationalStateRepositoryCommitOutcome.COMMITTED,
            reasons=result.reasons,
            storage_changed=True,
            commit_id=result.commit_id,
            acceptance_id=result.acceptance_id,
            evaluation_id=result.evaluation_id,
            predecessor_state_id=result.predecessor_state_id,
            successor_state_id=result.successor_state_id,
            subject=result.subject,
            state_kind=result.state_kind,
            previous_revision=1,
            committed_revision=2,
            committed_at=result.committed_at,
            current_state_record=successor_record,
        )


@pytest.mark.parametrize(
    "outcome, reason_code",
    (
        (
            OperationalStateRepositoryCommitOutcome.ALREADY_COMMITTED,
            OperationalStateRepositoryCommitReasonCode.EVALUATION_ALREADY_COMMITTED,
        ),
        (
            OperationalStateRepositoryCommitOutcome.STALE_PREDECESSOR,
            OperationalStateRepositoryCommitReasonCode.EXPECTED_PREDECESSOR_NOT_CURRENT,
        ),
        (
            OperationalStateRepositoryCommitOutcome.CURRENT_STATE_CONFLICT,
            OperationalStateRepositoryCommitReasonCode.UNEXPECTED_CURRENT_STATE,
        ),
    ),
)
def test_duplicate_stale_and_initial_conflict_results_never_claim_a_change(
    outcome: OperationalStateRepositoryCommitOutcome,
    reason_code: OperationalStateRepositoryCommitReasonCode,
) -> None:
    accepted = _accepted_result()
    result = OperationalStateRepositoryCommitResult(
        outcome=outcome,
        reasons=(_reason(reason_code, accepted),),
        storage_changed=False,
        commit_id=(
            EntityId.new()
            if outcome is OperationalStateRepositoryCommitOutcome.ALREADY_COMMITTED
            else None
        ),
        acceptance_id=accepted.id,
        evaluation_id=accepted.accepted_evaluation_id,
        successor_state_id=accepted.successor_state.id,  # type: ignore[union-attr]
        subject=accepted.target_subject,
        state_kind=accepted.lineage.evaluated_state_kind,
    )

    assert not result.storage_changed
    assert result.current_state_record is None
    assert result.superseded_predecessor_record is None


def test_domain_conflict_and_infrastructure_failure_remain_distinct() -> None:
    accepted = _accepted_result()
    stale = OperationalStateRepositoryCommitResult(
        outcome=OperationalStateRepositoryCommitOutcome.STALE_PREDECESSOR,
        reasons=(
            _reason(
                OperationalStateRepositoryCommitReasonCode.EXPECTED_PREDECESSOR_MISMATCH,
                accepted,
            ),
        ),
        storage_changed=False,
        acceptance_id=accepted.id,
        evaluation_id=accepted.accepted_evaluation_id,
        subject=accepted.target_subject,
        state_kind=accepted.lineage.evaluated_state_kind,
    )
    failure = OperationalStateRepositoryCommitResult(
        outcome=OperationalStateRepositoryCommitOutcome.UNKNOWN,
        reasons=(_reason(OperationalStateRepositoryCommitReasonCode.UNKNOWN, accepted),),
        storage_changed=False,
        acceptance_id=accepted.id,
        evaluation_id=accepted.accepted_evaluation_id,
        subject=accepted.target_subject,
        state_kind=accepted.lineage.evaluated_state_kind,
        error=OperationalStateRepositoryError(
            code=OperationalStateRepositoryErrorCode.TRANSACTION_FAILURE,
            message="The repository transaction failed unexpectedly.",
        ),
    )

    assert stale.error is None
    assert failure.error is not None
    with pytest.raises(ValueError, match="only by the unknown outcome"):
        OperationalStateRepositoryCommitResult(
            outcome=OperationalStateRepositoryCommitOutcome.NOT_FOUND,
            reasons=(_reason(OperationalStateRepositoryCommitReasonCode.NOT_FOUND, accepted),),
            storage_changed=False,
            error=failure.error,
        )
