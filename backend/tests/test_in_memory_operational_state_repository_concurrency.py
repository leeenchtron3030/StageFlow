from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

from operational_state_repository_compliance import make_accepted_state, make_subject

from app.contexts.production.operational_state import OperationalStateValue
from app.contexts.production.operational_state_repository import (
    InMemoryOperationalStateRepository,
    OperationalStateRepositoryCommitOutcome,
    OperationalStateRepositoryCommitRequest,
    OperationalStateRepositoryCommitResult,
    OperationalStateRepositoryQueryOutcome,
    OperationalStateRepositoryQueryResult,
    OperationalStateRepositoryRecord,
)
from app.shared.ids import EntityId


def _race_commits(
    repository: InMemoryOperationalStateRepository,
    first: OperationalStateRepositoryCommitRequest,
    second: OperationalStateRepositoryCommitRequest,
) -> tuple[OperationalStateRepositoryCommitResult, OperationalStateRepositoryCommitResult]:
    barrier = Barrier(2)

    def commit(request: OperationalStateRepositoryCommitRequest) -> (
        OperationalStateRepositoryCommitResult
    ):
        barrier.wait(timeout=5)
        return repository.commit_acceptance(request)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(commit, first)
        second_future = executor.submit(commit, second)
        return first_future.result(timeout=5), second_future.result(timeout=5)


def test_competing_initial_commits_have_exactly_one_winner() -> None:
    repository = InMemoryOperationalStateRepository()
    subject = make_subject()
    first = make_accepted_state(subject=subject, expected_revision=0)
    second = make_accepted_state(subject=subject, expected_revision=0)

    results = _race_commits(repository, first.request, second.request)

    assert {result.outcome for result in results} == {
        OperationalStateRepositoryCommitOutcome.COMMITTED,
        OperationalStateRepositoryCommitOutcome.CURRENT_STATE_CONFLICT,
    }
    history = repository.list_state_history(subject, first.successor.kind).value
    assert history is not None
    assert len(history.records) == 1
    winner = next(result for result in results if result.storage_changed)
    assert history.current_state_id == winner.successor_state_id
    committed_count = sum(
        repository.has_committed_evaluation(fixture.result.accepted_evaluation_id).value
        is True
        for fixture in (first, second)
    )
    assert committed_count == 1


def test_competing_successors_from_one_predecessor_have_exactly_one_winner() -> None:
    repository = InMemoryOperationalStateRepository()
    initial = make_accepted_state(expected_revision=0)
    repository.commit_acceptance(initial.request)
    first = make_accepted_state(
        predecessor=initial.successor,
        proposed_value=OperationalStateValue.PAUSED,
        expected_revision=1,
    )
    second = make_accepted_state(
        predecessor=initial.successor,
        proposed_value=OperationalStateValue.STOPPED,
        expected_revision=1,
    )

    results = _race_commits(repository, first.request, second.request)

    assert {result.outcome for result in results} == {
        OperationalStateRepositoryCommitOutcome.COMMITTED,
        OperationalStateRepositoryCommitOutcome.STALE_PREDECESSOR,
    }
    history = repository.list_state_history(
        initial.successor.subject,
        initial.successor.kind,
    ).value
    assert history is not None
    assert len(history.records) == 2
    winner = next(result for result in results if result.storage_changed)
    assert history.current_state_id == winner.successor_state_id
    predecessor = repository.get_state(initial.successor.id).value
    assert predecessor is not None
    assert predecessor.successor_state_id == winner.successor_state_id


def test_duplicate_evaluation_race_commits_once_and_replays_once() -> None:
    repository = InMemoryOperationalStateRepository()
    fixture = make_accepted_state(expected_revision=0)

    results = _race_commits(repository, fixture.request, fixture.request)

    assert {result.outcome for result in results} == {
        OperationalStateRepositoryCommitOutcome.COMMITTED,
        OperationalStateRepositoryCommitOutcome.ALREADY_COMMITTED,
    }
    assert results[0].commit_id == results[1].commit_id
    history = repository.list_state_history(
        fixture.successor.subject,
        fixture.successor.kind,
    ).value
    assert history is not None
    assert history.state_ids == (fixture.successor.id,)


def test_conflicting_evaluation_race_commits_once_and_conflicts_once() -> None:
    repository = InMemoryOperationalStateRepository()
    subject = make_subject()
    evaluation_id = EntityId.new()
    first = make_accepted_state(
        subject=subject,
        evaluation_id=evaluation_id,
        expected_revision=0,
    )
    second = make_accepted_state(
        subject=subject,
        evaluation_id=evaluation_id,
        expected_revision=0,
    )

    results = _race_commits(repository, first.request, second.request)

    assert {result.outcome for result in results} == {
        OperationalStateRepositoryCommitOutcome.COMMITTED,
        OperationalStateRepositoryCommitOutcome.LINEAGE_CONFLICT,
    }
    history = repository.list_state_history(subject, first.successor.kind).value
    assert history is not None
    assert len(history.records) == 1
    assert repository.has_committed_evaluation(evaluation_id).value is True


def test_conflicting_acceptance_race_commits_once_and_conflicts_once() -> None:
    repository = InMemoryOperationalStateRepository()
    subject = make_subject()
    acceptance_id = EntityId.new()
    first = make_accepted_state(
        subject=subject,
        acceptance_id=acceptance_id,
        expected_revision=0,
    )
    second = make_accepted_state(
        subject=subject,
        acceptance_id=acceptance_id,
        expected_revision=0,
    )

    results = _race_commits(repository, first.request, second.request)

    assert {result.outcome for result in results} == {
        OperationalStateRepositoryCommitOutcome.COMMITTED,
        OperationalStateRepositoryCommitOutcome.LINEAGE_CONFLICT,
    }
    history = repository.list_state_history(subject, first.successor.kind).value
    assert history is not None
    assert len(history.records) == 1


def test_query_waits_for_commit_and_observes_only_complete_replacement_state() -> None:
    commit_id_requested = Event()
    release_commit_id = Event()
    query_started = Event()
    commit_id = EntityId.new()

    def controlled_commit_id() -> EntityId:
        commit_id_requested.set()
        assert release_commit_id.wait(timeout=5)
        return commit_id

    repository = InMemoryOperationalStateRepository(
        commit_id_factory=controlled_commit_id
    )
    fixture = make_accepted_state(expected_revision=0)

    with ThreadPoolExecutor(max_workers=2) as executor:
        commit_future = executor.submit(repository.commit_acceptance, fixture.request)
        assert commit_id_requested.wait(timeout=5)

        def query_current() -> OperationalStateRepositoryQueryResult[
            OperationalStateRepositoryRecord
        ]:
            query_started.set()
            return repository.get_current_state(
                fixture.successor.subject,
                fixture.successor.kind,
            )

        query_future = executor.submit(query_current)
        assert query_started.wait(timeout=5)
        assert not query_future.done()
        release_commit_id.set()
        committed = commit_future.result(timeout=5)
        query = query_future.result(timeout=5)

    assert committed.outcome is OperationalStateRepositoryCommitOutcome.COMMITTED
    assert committed.commit_id == commit_id
    assert query.outcome is OperationalStateRepositoryQueryOutcome.FOUND
    record = query.value
    assert record is not None
    assert record.state_id == fixture.successor.id
