from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any

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
    OperationalStateRepository,
    OperationalStateRepositoryCommitOutcome,
    OperationalStateRepositoryCommitRequest,
    OperationalStateRepositoryQueryOutcome,
)
from app.shared.ids import EntityId

EVALUATED_AT = datetime(2026, 7, 16, 10, 5, tzinfo=UTC)
ACCEPTED_AT = EVALUATED_AT + timedelta(seconds=2)
COMMITTED_AT = EVALUATED_AT + timedelta(seconds=3)
ORGANIZATIONAL_ANCHOR = EVALUATED_AT - timedelta(seconds=90)


@dataclass(frozen=True, slots=True)
class AcceptedStateFixture:
    result: OperationalStateAcceptanceResult
    request: OperationalStateRepositoryCommitRequest
    successor: OperationalState


def make_subject(
    *,
    state_kind: OperationalStateKind = OperationalStateKind.RECORDING_STATE,
    identifier: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> OperationalStateSubject:
    subject_type = (
        OperationalStateSubjectType.RECORDING_BLOCK
        if state_kind is OperationalStateKind.RECORDING_STATE
        else OperationalStateSubjectType.SESSION_CANDIDATE
    )
    return OperationalStateSubject(
        subject_type=subject_type,
        subject_identifier=identifier or EntityId.new().to_json(),
        metadata=metadata or {},
    )


def make_accepted_state(
    *,
    subject: OperationalStateSubject | None = None,
    state_kind: OperationalStateKind = OperationalStateKind.RECORDING_STATE,
    proposed_value: OperationalStateValue = OperationalStateValue.ACTIVE,
    predecessor: OperationalState | None = None,
    evaluation_id: EntityId | None = None,
    acceptance_id: EntityId | None = None,
    successor_id: EntityId | None = None,
    expected_revision: int | None = None,
    expected_current_state_id: EntityId | None | object = ...,
    family: OperationalStateFamily | None = None,
    status: OperationalStateStatus = OperationalStateStatus.CURRENT,
    lineage_context: EvidenceContext | None = None,
    basis_context: EvidenceContext | None | object = ...,
    accepted_at: datetime = ACCEPTED_AT,
    evaluated_at: datetime = EVALUATED_AT,
    committed_at: datetime = COMMITTED_AT,
    acceptance_metadata: Mapping[str, Any] | None = None,
) -> AcceptedStateFixture:
    resolved_subject = subject or (
        predecessor.subject if predecessor is not None else make_subject(state_kind=state_kind)
    )
    resolved_family = family or (
        OperationalStateFamily.DIRECTLY_OBSERVABLE
        if state_kind is OperationalStateKind.RECORDING_STATE
        else OperationalStateFamily.EVIDENCE_DERIVED
    )
    resolved_evaluation_id = evaluation_id or EntityId.new()
    policy_id = EntityId.new()
    transition_rule_id = EntityId.new()
    acceptance_rule_id = EntityId.new()
    evidence_set_id = EntityId.new()
    evidence_item_id = EntityId.new()
    observation_id = EntityId.new()
    event_id = EntityId.new()
    interpreter_id = EntityId.new()
    source_context_id = EntityId.new()
    resolved_context = lineage_context or EvidenceContext(
        organizational_anchor=ORGANIZATIONAL_ANCHOR,
        source_context_ids=(source_context_id,),
    )
    if basis_context is ...:
        resolved_basis_context: EvidenceContext | None = resolved_context
    elif isinstance(basis_context, EvidenceContext) or basis_context is None:
        resolved_basis_context = basis_context
    else:
        raise TypeError("basis_context must be an EvidenceContext or None.")
    signal = (
        EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED
        if state_kind is OperationalStateKind.RECORDING_STATE
        else EvidenceSignal.SESSION_CONTENT_INDICATED
    )
    lineage = OperationalStateAcceptanceLineage(
        evaluation_id=resolved_evaluation_id,
        policy_kind=(
            "recording_transition_policy"
            if state_kind is OperationalStateKind.RECORDING_STATE
            else "session_transition_policy"
        ),
        policy_id=policy_id,
        applied_rule_id=transition_rule_id,
        evaluated_state_kind=state_kind,
        current_state_id=predecessor.id if predecessor is not None else None,
        effective_current_value=(
            predecessor.value if predecessor is not None else OperationalStateValue.INACTIVE
        ),
        proposed_state_value=proposed_value,
        supporting_evidence_set_ids=(evidence_set_id,),
        contributing_evidence_item_ids=(evidence_item_id,),
        contributing_observation_ids=(observation_id,),
        contributing_production_event_ids=(event_id,),
        contributing_signals=(signal,),
        interpreter_ids=(interpreter_id,),
        interpretation_rule_ids=("compliance_interpretation_rule",),
        organizational_anchors=(ORGANIZATIONAL_ANCHOR.isoformat(),),
        evaluation_context=resolved_context,
        metadata={"deployment_provenance": "upstream_only"},
    )
    successor = OperationalState(
        id=successor_id or EntityId.new(),
        family=resolved_family,
        kind=state_kind,
        subject=resolved_subject,
        value=proposed_value,
        status=status,
        basis=OperationalStateBasis(
            observation_ids=lineage.contributing_observation_ids,
            evidence_set_ids=lineage.supporting_evidence_set_ids,
            transition_evaluation_ids=(resolved_evaluation_id,),
            policy_ids=(policy_id,),
            transition_rule_ids=(transition_rule_id,),
            evidence_context=resolved_basis_context,
            metadata={
                "evidence_item_ids": tuple(lineage.contributing_evidence_item_ids),
                "production_event_ids": tuple(lineage.contributing_production_event_ids),
            },
        ),
        observed_or_derived_at=evaluated_at,
    )
    supersession = (
        OperationalStateSupersession(
            predecessor_state_id=predecessor.id,
            successor_state_id=successor.id,
            transition_evaluation_id=resolved_evaluation_id,
            accepted_at=accepted_at,
            predecessor_status_before_acceptance=OperationalStateStatus.CURRENT,
            successor_status=status,
            reason="Compliance successor describes immutable predecessor supersession.",
        )
        if predecessor is not None
        else None
    )
    result = OperationalStateAcceptanceResult(
        id=acceptance_id or EntityId.new(),
        outcome=OperationalStateAcceptanceOutcome.ACCEPTED,
        accepted_evaluation_id=resolved_evaluation_id,
        reasons=(
            OperationalStateAcceptanceReason(
                code=OperationalStateAcceptanceReasonCode.SUCCESSOR_CREATED,
                message="Compliance fixture created one accepted successor.",
                evaluation_id=resolved_evaluation_id,
                current_state_id=predecessor.id if predecessor is not None else None,
                subject_identifier=resolved_subject.subject_identifier,
            ),
        ),
        current_state_id=predecessor.id if predecessor is not None else None,
        target_subject=resolved_subject,
        successor_state=successor,
        supersession=supersession,
        lineage=lineage,
        applied_acceptance_rule_id=acceptance_rule_id,
        accepted_at=accepted_at,
        metadata=acceptance_metadata or {},
    )
    expected_state_id = (
        predecessor.id
        if expected_current_state_id is ... and predecessor is not None
        else None
        if expected_current_state_id is ...
        else expected_current_state_id
    )
    if expected_state_id is not None and not isinstance(expected_state_id, EntityId):
        raise TypeError("expected_current_state_id must be an EntityId or None.")
    request = OperationalStateRepositoryCommitRequest(
        acceptance_result=result,
        commit_at=committed_at,
        expected_current_state_id=expected_state_id,
        expected_revision=expected_revision,
        request_id=EntityId.new(),
        metadata={"fixture": "repository_compliance"},
    )
    return AcceptedStateFixture(result=result, request=request, successor=successor)


def make_rejected_request(
    accepted: AcceptedStateFixture,
) -> OperationalStateRepositoryCommitRequest:
    result = OperationalStateAcceptanceResult(
        id=EntityId.new(),
        outcome=OperationalStateAcceptanceOutcome.REJECTED_INVALID_LINEAGE,
        accepted_evaluation_id=accepted.result.accepted_evaluation_id,
        reasons=(
            OperationalStateAcceptanceReason(
                code=OperationalStateAcceptanceReasonCode.MISSING_EVENT_LINEAGE,
                message="Compliance rejection lacks Event lineage.",
                evaluation_id=accepted.result.accepted_evaluation_id,
            ),
        ),
        current_state_id=None,
        target_subject=accepted.result.target_subject,
        successor_state=None,
        supersession=None,
        lineage=accepted.result.lineage,
        applied_acceptance_rule_id=None,
        accepted_at=ACCEPTED_AT,
    )
    return OperationalStateRepositoryCommitRequest(
        acceptance_result=result,
        commit_at=COMMITTED_AT,
    )


def public_repository_fingerprint(
    repository: OperationalStateRepository,
    *,
    subjects_and_kinds: tuple[tuple[OperationalStateSubject, OperationalStateKind], ...],
    state_ids: tuple[EntityId, ...],
    evaluation_ids: tuple[EntityId, ...],
) -> tuple[object, ...]:
    values: list[object] = []
    for subject, state_kind in subjects_and_kinds:
        values.append(repository.get_current_state(subject, state_kind))
        values.append(repository.list_state_history(subject, state_kind))
    for state_id in state_ids:
        values.append(repository.get_state(state_id))
    for evaluation_id in evaluation_ids:
        values.append(repository.has_committed_evaluation(evaluation_id))
        values.append(repository.get_commit_by_evaluation(evaluation_id))
    return tuple(values)


class OperationalStateRepositoryCompliance:
    """Reusable observable ED-0046 compliance suite driven by a repository factory."""

    def repository_factory(self) -> OperationalStateRepository:
        raise NotImplementedError

    def test_empty_repository_queries_are_typed_and_deterministic(self) -> None:
        repository = self.repository_factory()
        subject = make_subject()
        evaluation_id = EntityId.new()

        assert (
            repository.get_current_state(subject, OperationalStateKind.RECORDING_STATE).outcome
            is OperationalStateRepositoryQueryOutcome.NOT_FOUND
        )
        assert repository.get_state(EntityId.new()).outcome is (
            OperationalStateRepositoryQueryOutcome.NOT_FOUND
        )
        assert repository.list_state_history(
            subject,
            OperationalStateKind.RECORDING_STATE,
        ).outcome is OperationalStateRepositoryQueryOutcome.NOT_FOUND
        committed = repository.has_committed_evaluation(evaluation_id)
        assert committed.outcome is OperationalStateRepositoryQueryOutcome.FOUND
        assert committed.value is False
        assert repository.get_commit_by_evaluation(evaluation_id).outcome is (
            OperationalStateRepositoryQueryOutcome.NOT_FOUND
        )

    def test_initial_recording_commit_populates_all_public_indexes(self) -> None:
        repository = self.repository_factory()
        fixture = make_accepted_state(expected_revision=0)

        result = repository.commit_acceptance(fixture.request)

        assert result.outcome is OperationalStateRepositoryCommitOutcome.COMMITTED
        assert result.storage_changed
        assert result.previous_revision == 0
        assert result.committed_revision == 1
        assert result.predecessor_state_id is None
        assert result.superseded_predecessor_record is None
        current = repository.get_current_state(
            fixture.successor.subject,
            fixture.successor.kind,
        )
        assert current.value == result.current_state_record
        assert repository.get_state(fixture.successor.id).value == result.current_state_record
        history = repository.list_state_history(
            fixture.successor.subject,
            fixture.successor.kind,
        ).value
        assert history is not None
        assert history.state_ids == (fixture.successor.id,)
        assert history.revision == 1
        assert repository.has_committed_evaluation(
            fixture.result.accepted_evaluation_id
        ).value is True
        assert repository.get_commit_by_evaluation(
            fixture.result.accepted_evaluation_id
        ).value == result

    def test_initial_session_commit_uses_same_repository_contract(self) -> None:
        repository = self.repository_factory()
        fixture = make_accepted_state(
            state_kind=OperationalStateKind.SESSION_STATE,
            proposed_value=OperationalStateValue.ACTIVE,
            expected_revision=0,
        )

        result = repository.commit_acceptance(fixture.request)

        assert result.outcome is OperationalStateRepositoryCommitOutcome.COMMITTED
        record = result.current_state_record
        assert record is not None
        assert record.family is OperationalStateFamily.EVIDENCE_DERIVED
        assert record.kind is OperationalStateKind.SESSION_STATE
        assert record.subject.subject_type is OperationalStateSubjectType.SESSION_CANDIDATE

    def test_session_successors_use_ordered_state_history_without_session_aggregate(self) -> None:
        repository = self.repository_factory()
        active = make_accepted_state(
            state_kind=OperationalStateKind.SESSION_STATE,
            proposed_value=OperationalStateValue.ACTIVE,
            expected_revision=0,
        )
        repository.commit_acceptance(active.request)
        ending = make_accepted_state(
            state_kind=OperationalStateKind.SESSION_STATE,
            predecessor=active.successor,
            proposed_value=OperationalStateValue.ENDING,
            expected_revision=1,
            evaluated_at=EVALUATED_AT + timedelta(seconds=4),
            accepted_at=ACCEPTED_AT + timedelta(seconds=4),
            committed_at=COMMITTED_AT + timedelta(seconds=4),
        )
        repository.commit_acceptance(ending.request)
        ended = make_accepted_state(
            state_kind=OperationalStateKind.SESSION_STATE,
            predecessor=ending.successor,
            proposed_value=OperationalStateValue.ENDED,
            expected_revision=2,
            evaluated_at=EVALUATED_AT + timedelta(seconds=8),
            accepted_at=ACCEPTED_AT + timedelta(seconds=8),
            committed_at=COMMITTED_AT + timedelta(seconds=8),
        )

        result = repository.commit_acceptance(ended.request)

        assert result.outcome is OperationalStateRepositoryCommitOutcome.COMMITTED
        history = repository.list_state_history(
            active.successor.subject,
            OperationalStateKind.SESSION_STATE,
        ).value
        assert history is not None
        assert tuple(record.value for record in history.records) == (
            OperationalStateValue.ACTIVE,
            OperationalStateValue.ENDING,
            OperationalStateValue.ENDED,
        )
        assert tuple(record.revision for record in history.records) == (1, 2, 3)

    def test_successor_commit_supersedes_predecessor_and_appends_history(self) -> None:
        repository = self.repository_factory()
        initial = make_accepted_state(expected_revision=0)
        initial_result = repository.commit_acceptance(initial.request)
        assert initial_result.outcome is OperationalStateRepositoryCommitOutcome.COMMITTED
        successor = make_accepted_state(
            predecessor=initial.successor,
            proposed_value=OperationalStateValue.PAUSED,
            expected_revision=1,
            committed_at=COMMITTED_AT + timedelta(seconds=3),
            accepted_at=ACCEPTED_AT + timedelta(seconds=3),
            evaluated_at=EVALUATED_AT + timedelta(seconds=3),
        )

        result = repository.commit_acceptance(successor.request)

        assert result.outcome is OperationalStateRepositoryCommitOutcome.COMMITTED
        assert result.previous_revision == 1
        assert result.committed_revision == 2
        predecessor = repository.get_state(initial.successor.id).value
        current = repository.get_current_state(
            initial.successor.subject,
            initial.successor.kind,
        ).value
        assert predecessor is not None
        assert current is not None
        assert predecessor.status is OperationalStateStatus.SUPERSEDED
        assert predecessor.successor_state_id == successor.successor.id
        assert current.state_id == successor.successor.id
        history = repository.list_state_history(
            initial.successor.subject,
            initial.successor.kind,
        ).value
        assert history is not None
        assert history.state_ids == (initial.successor.id, successor.successor.id)
        assert tuple(record.revision for record in history.records) == (1, 2)
        assert initial.successor.status is OperationalStateStatus.CURRENT

    def test_exact_replay_returns_original_commit_without_mutation(self) -> None:
        repository = self.repository_factory()
        fixture = make_accepted_state(expected_revision=0)
        committed = repository.commit_acceptance(fixture.request)
        replay_request = replace(
            fixture.request,
            commit_at=COMMITTED_AT + timedelta(minutes=1),
        )
        before = public_repository_fingerprint(
            repository,
            subjects_and_kinds=((fixture.successor.subject, fixture.successor.kind),),
            state_ids=(fixture.successor.id,),
            evaluation_ids=(fixture.result.accepted_evaluation_id,),
        )

        replay = repository.commit_acceptance(replay_request)

        assert replay.outcome is OperationalStateRepositoryCommitOutcome.ALREADY_COMMITTED
        assert not replay.storage_changed
        assert replay.commit_id == committed.commit_id
        assert replay.committed_revision == committed.committed_revision
        assert committed.committed_at == COMMITTED_AT
        assert replay.committed_at == COMMITTED_AT
        assert replay.committed_at != replay_request.commit_at
        persisted = repository.get_state(fixture.successor.id).value
        assert persisted is not None
        assert persisted.persisted_at == COMMITTED_AT
        assert public_repository_fingerprint(
            repository,
            subjects_and_kinds=((fixture.successor.subject, fixture.successor.kind),),
            state_ids=(fixture.successor.id,),
            evaluation_ids=(fixture.result.accepted_evaluation_id,),
        ) == before

    def test_conflicting_evaluation_replay_is_lineage_conflict(self) -> None:
        repository = self.repository_factory()
        evaluation_id = EntityId.new()
        subject = make_subject()
        first = make_accepted_state(
            subject=subject,
            evaluation_id=evaluation_id,
            expected_revision=0,
        )
        conflicting = make_accepted_state(
            subject=subject,
            evaluation_id=evaluation_id,
            expected_revision=0,
        )
        repository.commit_acceptance(first.request)

        result = repository.commit_acceptance(conflicting.request)

        assert result.outcome is OperationalStateRepositoryCommitOutcome.LINEAGE_CONFLICT
        history = repository.list_state_history(subject, first.successor.kind).value
        assert history is not None
        assert history.state_ids == (first.successor.id,)

    def test_conflicting_acceptance_replay_is_lineage_conflict(self) -> None:
        repository = self.repository_factory()
        acceptance_id = EntityId.new()
        subject = make_subject()
        first = make_accepted_state(
            subject=subject,
            acceptance_id=acceptance_id,
            expected_revision=0,
        )
        conflicting = make_accepted_state(
            subject=subject,
            acceptance_id=acceptance_id,
            expected_revision=0,
        )
        repository.commit_acceptance(first.request)

        result = repository.commit_acceptance(conflicting.request)

        assert result.outcome is OperationalStateRepositoryCommitOutcome.LINEAGE_CONFLICT
        history = repository.list_state_history(subject, first.successor.kind).value
        assert history is not None
        assert history.state_ids == (first.successor.id,)

    def test_initial_commit_conflicts_with_existing_current_state(self) -> None:
        repository = self.repository_factory()
        subject = make_subject()
        first = make_accepted_state(subject=subject, expected_revision=0)
        second = make_accepted_state(subject=subject, expected_revision=1)
        repository.commit_acceptance(first.request)

        result = repository.commit_acceptance(second.request)

        assert result.outcome is OperationalStateRepositoryCommitOutcome.CURRENT_STATE_CONFLICT
        assert repository.get_current_state(subject, first.successor.kind).value == (
            repository.get_state(first.successor.id).value
        )

    def test_stale_predecessor_cannot_overwrite_newer_state(self) -> None:
        repository = self.repository_factory()
        initial = make_accepted_state(expected_revision=0)
        repository.commit_acceptance(initial.request)
        winner = make_accepted_state(
            predecessor=initial.successor,
            proposed_value=OperationalStateValue.PAUSED,
            expected_revision=1,
        )
        stale = make_accepted_state(
            predecessor=initial.successor,
            proposed_value=OperationalStateValue.STOPPED,
            expected_revision=1,
        )
        repository.commit_acceptance(winner.request)

        result = repository.commit_acceptance(stale.request)

        assert result.outcome is OperationalStateRepositoryCommitOutcome.STALE_PREDECESSOR
        current = repository.get_current_state(
            initial.successor.subject,
            initial.successor.kind,
        ).value
        assert current is not None
        assert current.state_id == winner.successor.id
        history = repository.list_state_history(
            initial.successor.subject,
            initial.successor.kind,
        ).value
        assert history is not None
        assert stale.successor.id not in history.state_ids

    def test_revision_mismatch_is_stale_and_does_not_increment_history(self) -> None:
        repository = self.repository_factory()
        initial = make_accepted_state(expected_revision=0)
        repository.commit_acceptance(initial.request)
        successor = make_accepted_state(
            predecessor=initial.successor,
            proposed_value=OperationalStateValue.PAUSED,
            expected_revision=0,
        )

        result = repository.commit_acceptance(successor.request)

        assert result.outcome is OperationalStateRepositoryCommitOutcome.STALE_PREDECESSOR
        history = repository.list_state_history(
            initial.successor.subject,
            initial.successor.kind,
        ).value
        assert history is not None
        assert history.revision == 1
        assert history.state_ids == (initial.successor.id,)

    def test_subject_kind_histories_are_isolated(self) -> None:
        repository = self.repository_factory()
        first = make_accepted_state(subject=make_subject(identifier="block-a"))
        second = make_accepted_state(subject=make_subject(identifier="block-b"))

        assert repository.commit_acceptance(first.request).outcome is (
            OperationalStateRepositoryCommitOutcome.COMMITTED
        )
        assert repository.commit_acceptance(second.request).outcome is (
            OperationalStateRepositoryCommitOutcome.COMMITTED
        )
        first_history = repository.list_state_history(
            first.successor.subject,
            first.successor.kind,
        ).value
        second_history = repository.list_state_history(
            second.successor.subject,
            second.successor.kind,
        ).value
        assert first_history is not None and second_history is not None
        assert first_history.state_ids == (first.successor.id,)
        assert second_history.state_ids == (second.successor.id,)
        assert first_history.revision == second_history.revision == 1

    def test_record_preserves_complete_lineage_context_and_timestamps(self) -> None:
        repository = self.repository_factory()
        fixture = make_accepted_state(expected_revision=0)

        result = repository.commit_acceptance(fixture.request)

        record = result.current_state_record
        assert record is not None
        assert record.acceptance_id == fixture.result.id
        assert record.accepted_evaluation_id == fixture.result.accepted_evaluation_id
        assert record.acceptance_rule_id == fixture.result.applied_acceptance_rule_id
        assert record.lineage.policy_id in record.basis.policy_ids
        assert record.lineage.applied_rule_id in record.basis.transition_rule_ids
        assert record.lineage.supporting_evidence_set_ids
        assert record.lineage.contributing_evidence_item_ids
        assert record.lineage.contributing_observation_ids
        assert record.lineage.contributing_production_event_ids
        assert record.lineage.interpreter_ids
        assert record.lineage.interpretation_rule_ids
        assert record.lineage.contributing_signals
        assert record.evidence_context == fixture.result.lineage.evaluation_context
        assert fixture.result.accepted_at == ACCEPTED_AT
        assert fixture.request.commit_at == COMMITTED_AT
        assert fixture.successor.observed_or_derived_at == EVALUATED_AT
        assert record.evaluation_at == EVALUATED_AT
        assert record.accepted_at == ACCEPTED_AT
        assert record.persisted_at == COMMITTED_AT
        assert result.committed_at == COMMITTED_AT
        assert record.evidence_context.organizational_anchor == ORGANIZATIONAL_ANCHOR
        assert len(
            {
                record.evaluation_at,
                record.accepted_at,
                record.persisted_at,
                record.evidence_context.organizational_anchor,
            }
        ) == 4

    def test_nonaccepted_result_is_rejected_without_observable_mutation(self) -> None:
        repository = self.repository_factory()
        accepted = make_accepted_state()
        request = make_rejected_request(accepted)
        before = public_repository_fingerprint(
            repository,
            subjects_and_kinds=((accepted.successor.subject, accepted.successor.kind),),
            state_ids=(accepted.successor.id,),
            evaluation_ids=(request.evaluation_id,),
        )

        result = repository.commit_acceptance(request)

        assert result.outcome is (
            OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT
        )
        assert not result.storage_changed
        assert public_repository_fingerprint(
            repository,
            subjects_and_kinds=((accepted.successor.subject, accepted.successor.kind),),
            state_ids=(accepted.successor.id,),
            evaluation_ids=(request.evaluation_id,),
        ) == before

    @pytest.mark.parametrize(
        ("family", "status", "expected"),
        (
            (
                OperationalStateFamily.EVIDENCE_DERIVED,
                OperationalStateStatus.CURRENT,
                OperationalStateRepositoryCommitOutcome.INVALID_SUCCESSOR_STATE,
            ),
            (
                OperationalStateFamily.DIRECTLY_OBSERVABLE,
                OperationalStateStatus.SUPERSEDED,
                OperationalStateRepositoryCommitOutcome.INVALID_SUCCESSOR_STATE,
            ),
        ),
    )
    def test_invalid_successor_shape_is_rejected(
        self,
        family: OperationalStateFamily,
        status: OperationalStateStatus,
        expected: OperationalStateRepositoryCommitOutcome,
    ) -> None:
        repository = self.repository_factory()
        fixture = make_accepted_state(family=family, status=status)

        result = repository.commit_acceptance(fixture.request)

        assert result.outcome is expected
        assert repository.get_state(fixture.successor.id).outcome is (
            OperationalStateRepositoryQueryOutcome.NOT_FOUND
        )

    def test_missing_expected_predecessor_is_invalid_not_stale(self) -> None:
        repository = self.repository_factory()
        initial = make_accepted_state(expected_revision=0)
        repository.commit_acceptance(initial.request)
        invalid = make_accepted_state(
            predecessor=initial.successor,
            proposed_value=OperationalStateValue.PAUSED,
            expected_current_state_id=None,
            expected_revision=1,
        )

        result = repository.commit_acceptance(invalid.request)

        assert result.outcome is (
            OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT
        )

    def test_subject_kind_and_context_contradictions_are_rejected(self) -> None:
        repository = self.repository_factory()
        subject_fixture = make_accepted_state()
        contradictory_subject_result = OperationalStateAcceptanceResult(
            id=subject_fixture.result.id,
            outcome=subject_fixture.result.outcome,
            accepted_evaluation_id=subject_fixture.result.accepted_evaluation_id,
            reasons=subject_fixture.result.reasons,
            current_state_id=subject_fixture.result.current_state_id,
            target_subject=make_subject(identifier="different-subject"),
            successor_state=subject_fixture.successor,
            supersession=subject_fixture.result.supersession,
            lineage=subject_fixture.result.lineage,
            applied_acceptance_rule_id=subject_fixture.result.applied_acceptance_rule_id,
            accepted_at=subject_fixture.result.accepted_at,
        )
        contradictory_subject_request = OperationalStateRepositoryCommitRequest(
            acceptance_result=contradictory_subject_result,
            commit_at=COMMITTED_AT,
        )
        context_fixture = make_accepted_state(
            basis_context=EvidenceContext(source_context_ids=(EntityId.new(),))
        )

        subject_result = repository.commit_acceptance(contradictory_subject_request)
        context_result = repository.commit_acceptance(context_fixture.request)

        assert subject_result.outcome is (
            OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT
        )
        assert context_result.outcome is (
            OperationalStateRepositoryCommitOutcome.INVALID_SUCCESSOR_STATE
        )

    def test_naive_acceptance_timestamp_is_rejected_without_storage(self) -> None:
        repository = self.repository_factory()
        fixture = make_accepted_state(accepted_at=datetime(2026, 7, 16, 10, 5))

        result = repository.commit_acceptance(fixture.request)

        assert result.outcome is (
            OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT
        )
        assert repository.get_state(fixture.successor.id).outcome is (
            OperationalStateRepositoryQueryOutcome.NOT_FOUND
        )

    def test_caller_contracts_remain_unchanged_after_commit(self) -> None:
        repository = self.repository_factory()
        initial = make_accepted_state(expected_revision=0)
        repository.commit_acceptance(initial.request)
        successor = make_accepted_state(
            predecessor=initial.successor,
            proposed_value=OperationalStateValue.PAUSED,
            expected_revision=1,
        )
        before = (
            initial.successor,
            successor.successor,
            successor.result,
            successor.result.lineage,
            successor.result.lineage.evaluation_context,
            successor.result.supersession,
            successor.request,
        )

        repository.commit_acceptance(successor.request)

        assert initial.successor.status is OperationalStateStatus.CURRENT
        assert before == (
            initial.successor,
            successor.successor,
            successor.result,
            successor.result.lineage,
            successor.result.lineage.evaluation_context,
            successor.result.supersession,
            successor.request,
        )
