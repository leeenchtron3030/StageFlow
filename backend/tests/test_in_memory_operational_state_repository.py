from __future__ import annotations

from operational_state_repository_compliance import (
    OperationalStateRepositoryCompliance,
    make_accepted_state,
)

from app.contexts.production.operational_state_repository import (
    InMemoryOperationalStateRepository,
    OperationalStateRepository,
    OperationalStateRepositoryCommitOutcome,
)
from app.shared.ids import EntityId


class TestInMemoryOperationalStateRepositoryCompliance(
    OperationalStateRepositoryCompliance
):
    """Run the reusable ED-0046 suite against the ED-0047 implementation."""

    def repository_factory(self) -> OperationalStateRepository:
        return InMemoryOperationalStateRepository()


def test_commit_id_factory_is_deterministic_and_only_success_consumes_an_id() -> None:
    commit_ids = iter((EntityId.new(), EntityId.new()))
    first_expected = next(commit_ids)
    second_expected = next(commit_ids)
    injected_ids = iter((first_expected, second_expected))
    repository = InMemoryOperationalStateRepository(
        commit_id_factory=lambda: next(injected_ids)
    )
    initial = make_accepted_state(expected_revision=0)

    first = repository.commit_acceptance(initial.request)
    replay = repository.commit_acceptance(initial.request)
    isolated = make_accepted_state(expected_revision=0)
    second = repository.commit_acceptance(isolated.request)

    assert first.commit_id == first_expected
    assert replay.commit_id == first_expected
    assert second.commit_id == second_expected


def test_repository_instances_do_not_share_any_committed_state() -> None:
    first_repository = InMemoryOperationalStateRepository()
    second_repository = InMemoryOperationalStateRepository()
    fixture = make_accepted_state(expected_revision=0)

    first_repository.commit_acceptance(fixture.request)

    assert second_repository.get_state(fixture.successor.id).value is None
    assert second_repository.get_current_state(
        fixture.successor.subject,
        fixture.successor.kind,
    ).value is None
    assert second_repository.has_committed_evaluation(
        fixture.result.accepted_evaluation_id
    ).value is False


def test_deployment_provenance_neither_changes_the_key_nor_commit_semantics() -> None:
    repository = InMemoryOperationalStateRepository()
    subject = make_accepted_state().successor.subject
    agent = make_accepted_state(
        subject=subject,
        expected_revision=0,
        acceptance_metadata={"deployment_profile": "agent"},
    )
    node = make_accepted_state(
        subject=subject,
        expected_revision=1,
        acceptance_metadata={"deployment_profile": "node"},
    )

    first = repository.commit_acceptance(agent.request)
    second = repository.commit_acceptance(node.request)

    assert first.outcome is OperationalStateRepositoryCommitOutcome.COMMITTED
    assert second.outcome is OperationalStateRepositoryCommitOutcome.CURRENT_STATE_CONFLICT
    assert repository.get_current_state(subject, agent.successor.kind).value == (
        first.current_state_record
    )
