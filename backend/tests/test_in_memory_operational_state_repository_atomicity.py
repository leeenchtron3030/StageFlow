from __future__ import annotations

from datetime import datetime
from types import MappingProxyType

import pytest
from operational_state_repository_compliance import (
    make_accepted_state,
    make_rejected_request,
    make_subject,
)

from app.contexts.production.operational_state import (
    OperationalStateFamily,
    OperationalStateStatus,
    OperationalStateValue,
)
from app.contexts.production.operational_state_repository import (
    InMemoryOperationalStateRepository,
    OperationalStateRepositoryCommitOutcome,
    OperationalStateRepositoryCommitRequest,
)
from app.contexts.production.operational_state_repository.in_memory_repository_state import (
    InMemoryOperationalStateRepositoryState,
)
from app.shared.ids import EntityId


def _state_reference(
    repository: InMemoryOperationalStateRepository,
) -> InMemoryOperationalStateRepositoryState:
    return repository._state  # pyright: ignore[reportPrivateUsage]


def _assert_rejected_without_state_replacement(
    repository: InMemoryOperationalStateRepository,
    request: OperationalStateRepositoryCommitRequest,
    expected: OperationalStateRepositoryCommitOutcome,
) -> None:
    before = _state_reference(repository)

    result = repository.commit_acceptance(request)

    assert result.outcome is expected
    assert not result.storage_changed
    assert _state_reference(repository) is before


def test_success_uses_one_state_replacement_and_rejections_use_none() -> None:
    repository = InMemoryOperationalStateRepository()
    fixture = make_accepted_state(expected_revision=0)
    empty_state = _state_reference(repository)

    committed = repository.commit_acceptance(fixture.request)

    committed_state = _state_reference(repository)
    assert committed.outcome is OperationalStateRepositoryCommitOutcome.COMMITTED
    assert committed_state is not empty_state
    replayed = repository.commit_acceptance(fixture.request)
    assert replayed.outcome is OperationalStateRepositoryCommitOutcome.ALREADY_COMMITTED
    assert _state_reference(repository) is committed_state


def test_invalid_acceptance_and_successor_leave_every_private_index_unchanged() -> None:
    accepted = make_accepted_state()
    repository = InMemoryOperationalStateRepository()
    _assert_rejected_without_state_replacement(
        repository,
        make_rejected_request(accepted),
        OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT,
    )
    invalid_family = make_accepted_state(
        family=OperationalStateFamily.EVIDENCE_DERIVED
    )
    _assert_rejected_without_state_replacement(
        repository,
        invalid_family.request,
        OperationalStateRepositoryCommitOutcome.INVALID_SUCCESSOR_STATE,
    )
    invalid_status = make_accepted_state(status=OperationalStateStatus.SUPERSEDED)
    _assert_rejected_without_state_replacement(
        repository,
        invalid_status.request,
        OperationalStateRepositoryCommitOutcome.INVALID_SUCCESSOR_STATE,
    )


def test_duplicate_and_conflicting_replays_leave_state_snapshot_unchanged() -> None:
    repository = InMemoryOperationalStateRepository()
    evaluation_id = EntityId.new()
    acceptance_id = EntityId.new()
    subject = make_subject()
    committed = make_accepted_state(
        subject=subject,
        evaluation_id=evaluation_id,
        acceptance_id=acceptance_id,
        expected_revision=0,
    )
    repository.commit_acceptance(committed.request)
    _assert_rejected_without_state_replacement(
        repository,
        committed.request,
        OperationalStateRepositoryCommitOutcome.ALREADY_COMMITTED,
    )
    evaluation_conflict = make_accepted_state(
        subject=subject,
        evaluation_id=evaluation_id,
        expected_revision=1,
    )
    _assert_rejected_without_state_replacement(
        repository,
        evaluation_conflict.request,
        OperationalStateRepositoryCommitOutcome.LINEAGE_CONFLICT,
    )
    acceptance_conflict = make_accepted_state(
        subject=subject,
        acceptance_id=acceptance_id,
        expected_revision=1,
    )
    _assert_rejected_without_state_replacement(
        repository,
        acceptance_conflict.request,
        OperationalStateRepositoryCommitOutcome.LINEAGE_CONFLICT,
    )


def test_current_stale_revision_and_request_conflicts_do_not_replace_state() -> None:
    repository = InMemoryOperationalStateRepository()
    subject = make_subject()
    initial = make_accepted_state(subject=subject, expected_revision=0)
    repository.commit_acceptance(initial.request)
    initial_conflict = make_accepted_state(subject=subject, expected_revision=1)
    _assert_rejected_without_state_replacement(
        repository,
        initial_conflict.request,
        OperationalStateRepositoryCommitOutcome.CURRENT_STATE_CONFLICT,
    )
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
    _assert_rejected_without_state_replacement(
        repository,
        stale.request,
        OperationalStateRepositoryCommitOutcome.STALE_PREDECESSOR,
    )
    revision_conflict = make_accepted_state(
        predecessor=winner.successor,
        proposed_value=OperationalStateValue.STOPPED,
        expected_revision=1,
    )
    _assert_rejected_without_state_replacement(
        repository,
        revision_conflict.request,
        OperationalStateRepositoryCommitOutcome.STALE_PREDECESSOR,
    )
    missing_expected = make_accepted_state(
        predecessor=winner.successor,
        proposed_value=OperationalStateValue.STOPPED,
        expected_current_state_id=None,
        expected_revision=2,
    )
    _assert_rejected_without_state_replacement(
        repository,
        missing_expected.request,
        OperationalStateRepositoryCommitOutcome.INVALID_ACCEPTANCE_RESULT,
    )


def test_naive_commit_timestamp_is_rejected_before_repository_mutation() -> None:
    repository = InMemoryOperationalStateRepository()
    fixture = make_accepted_state()
    before = _state_reference(repository)

    with pytest.raises(ValueError, match="timezone-aware"):
        OperationalStateRepositoryCommitRequest(
            acceptance_result=fixture.result,
            commit_at=datetime(2026, 7, 16, 10, 5),
        )

    assert _state_reference(repository) is before


def test_unexpected_commit_id_failure_propagates_without_state_assignment() -> None:
    def fail_commit_id() -> EntityId:
        raise RuntimeError("controlled commit ID failure")

    repository = InMemoryOperationalStateRepository(commit_id_factory=fail_commit_id)
    fixture = make_accepted_state(expected_revision=0)
    before = _state_reference(repository)

    with pytest.raises(RuntimeError, match="controlled commit ID failure"):
        repository.commit_acceptance(fixture.request)

    assert _state_reference(repository) is before


def test_internal_state_collections_are_read_only_and_not_shared_between_snapshots() -> None:
    repository = InMemoryOperationalStateRepository()
    fixture = make_accepted_state(expected_revision=0)
    repository.commit_acceptance(fixture.request)
    state = _state_reference(repository)
    records = state.records_by_state_id
    histories = state.history_ids_by_key

    assert isinstance(records, MappingProxyType)
    assert isinstance(histories, MappingProxyType)
    assert len(state.commits_by_evaluation_id) == 1
    assert len(state.commits_by_acceptance_id) == 1
    assert tuple(state.revisions_by_key.values()) == (1,)
    with pytest.raises(TypeError):
        records[EntityId.new()] = object()  # pyright: ignore[reportIndexIssue]
