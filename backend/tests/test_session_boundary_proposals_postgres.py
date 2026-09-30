"""All database DDL and immutable rows roll back through render_postgres_dsn."""
from dataclasses import replace
from typing import TypedDict
from unittest.mock import patch

import psycopg
import pytest

from app.contexts.production.event_mode_kernel.contracts import EpistemicKind, Session
from app.contexts.production.event_mode_kernel.service import DurableEventModeKernel
from app.contexts.production.session_suggestions.boundary_proposals import BoundaryProposalService
from app.contexts.production.session_suggestions.contracts import (
    InputSnapshot,
    SuggestionConflictError,
)
from app.contexts.production.session_suggestions.service import SessionSuggestionService
from app.infrastructure.postgres.event_mode_kernel_repository import (
    PostgresEventModeKernelRepository,
)
from app.infrastructure.postgres.migrations import PostgresMigrationRunner
from app.infrastructure.postgres.session_suggestion_repository import (
    PostgresSuggestionRepository,
    PostgresSuggestionTransaction,
)
from app.shared.ids import EntityId
from app.shared.time import FixedClock
from tests.test_durable_event_mode_kernel import ACTOR_ID
from tests.test_render_work_execution import render_postgres_dsn as render_postgres_dsn
from tests.test_session_suggestion_policy import NOW, asset, at
from tests.test_session_suggestions_postgres import seeded


class DecisionArgs(TypedDict):
    event_id: EntityId
    session_id: EntityId
    proposal_id: EntityId
    command_id: EntityId
    actor_id: EntityId


def linked(dsn: str) -> tuple[SessionSuggestionService, Session, InputSnapshot]:
    service, seed = seeded(dsn)
    kernel = DurableEventModeKernel(repository=PostgresEventModeKernelRepository(dsn),
                                    clock=FixedClock(NOW))
    talk = kernel.record_program_expectation(event_id=seed.event_id, stage_id=seed.stage_id,
                                             key="talk", title="Synthetic talk",
                                             planned_start=at(0), planned_end=at(1800))
    inputs = InputSnapshot((talk,), (asset(0, 1800),))
    with patch.object(PostgresSuggestionTransaction, "snapshot", return_value=inputs):
        service.run(event_id=seed.event_id, stage_id=seed.stage_id, actor_id=ACTOR_ID)
    suggestion, = service.page(seed.event_id, seed.stage_id)[0]
    decision = service.confirm(event_id=seed.event_id, suggestion_id=suggestion.id,
                                command_id=EntityId.new(), actor_id=ACTOR_ID,
                                start=at(60), end=at(1740))
    assert decision.session_id is not None
    session = kernel.repository.get_session(decision.session_id)
    assert session is not None
    service.clock = FixedClock(at(1))
    return service, session, inputs


def test_postgres_production_count_dedup_and_run_rollback(render_postgres_dsn: str) -> None:
    service, session, inputs = linked(render_postgres_dsn)
    boundaries = BoundaryProposalService(service.repository, service.clock)
    with patch.object(PostgresSuggestionTransaction, "snapshot", return_value=inputs):
        before = service.latest_run(session.event_id, session.stage_id)
        with patch.object(PostgresSuggestionTransaction, "save_run",
                          side_effect=RuntimeError("crash")):
            with pytest.raises(RuntimeError, match="crash"):
                service.run(event_id=session.event_id, stage_id=session.stage_id, actor_id=ACTOR_ID)
        assert service.latest_run(session.event_id, session.stage_id) == before
        assert not boundaries.open(session.event_id, session.id)
        run = service.run(event_id=session.event_id, stage_id=session.stage_id, actor_id=ACTOR_ID)
        assert run.boundary_proposals_created == 2
        assert service.run(event_id=session.event_id, stage_id=session.stage_id,
                            actor_id=ACTOR_ID) == run
    restarted = SessionSuggestionService(PostgresSuggestionRepository(render_postgres_dsn),
                                         FixedClock(at(2)))
    assert restarted.latest_run(session.event_id, session.stage_id) == run
    opened = boundaries.open(session.event_id, session.id)
    assert len(opened) == 2 and all(p.epistemic_kind == EpistemicKind.DERIVED for p in opened)
    changed = replace(inputs, assets=(replace(inputs.assets[0],
                                              segmentation_ids=(EntityId.new(),)),))
    with patch.object(PostgresSuggestionTransaction, "snapshot", return_value=changed):
        rerun = restarted.run(event_id=session.event_id, stage_id=session.stage_id,
                               actor_id=ACTOR_ID)
    assert rerun.id != run.id and rerun.boundary_proposals_created == 0
    assert boundaries.open(session.event_id, session.id) == opened


@pytest.mark.parametrize("change,expected", [("other_edge", 0), ("candidate", 1), ("boundary", 1)])
def test_postgres_dismissal_dedup_after_restart_and_fresh_run(
    render_postgres_dsn: str, change: str, expected: int,
) -> None:
    service, session, inputs = linked(render_postgres_dsn)
    with patch.object(PostgresSuggestionTransaction, "snapshot", return_value=inputs):
        first = service.run(event_id=session.event_id, stage_id=session.stage_id, actor_id=ACTOR_ID)
    boundaries = BoundaryProposalService(service.repository, FixedClock(at(2)))
    opened = boundaries.open(session.event_id, session.id)
    start = next(p for p in opened if p.boundary_kind == "start")
    end = next(p for p in opened if p.boundary_kind == "end")
    boundaries.dismiss(event_id=session.event_id, session_id=session.id, proposal_id=start.id,
                       command_id=EntityId.new(), actor_id=ACTOR_ID)
    boundaries.apply(event_id=session.event_id, session_id=session.id, proposal_id=end.id,
                     command_id=EntityId.new(), actor_id=ACTOR_ID)
    kernel = DurableEventModeKernel(
        repository=PostgresEventModeKernelRepository(render_postgres_dsn), clock=FixedClock(at(3)))
    updated = kernel.repository.get_session(session.id)
    assert updated is not None and updated.authoritative_end == end.boundary_at
    if change == "candidate":
        original = inputs.assets[0]
        assert original.coverage is not None and original.timing is not None
        inputs = replace(inputs, assets=(replace(
            original, coverage=replace(original.coverage, start=at(-60)),
            timing=replace(original.timing, revision=original.timing.revision + 1)),))
    elif change == "boundary":
        # Same boundary value, but a later same-edge correction permits re-proposal.
        kernel.correct_session_boundary(operation_id=EntityId.new(), session_id=session.id,
                                         boundary_kind="start",
                                         boundary_at=session.authoritative_start,
                                         actor_id=ACTOR_ID, reason="Human review")
    before = kernel.repository.list_boundary_proposals(session.id)
    restarted = SessionSuggestionService(PostgresSuggestionRepository(render_postgres_dsn),
                                         FixedClock(at(4)))
    with patch.object(PostgresSuggestionTransaction, "snapshot", return_value=inputs):
        second = restarted.run(event_id=session.event_id, stage_id=session.stage_id,
                                actor_id=ACTOR_ID)
    assert second.id != first.id and second.boundary_proposals_created == expected
    after = kernel.repository.list_boundary_proposals(session.id)
    assert len(after) == len(before) + expected
    assert tuple(p for p in after if p.boundary_kind == "end") == (end,)
    current = boundaries.open(session.event_id, session.id)
    assert len(current) == expected
    if expected:
        assert current[0].id != start.id and current[0].boundary_kind == "start"
        assert current[0].boundary_at == (at(-60) if change == "candidate" else start.boundary_at)
    else:
        assert after == before


def test_postgres_apply_atomic_retry_dismiss_history_and_immutable_guard(
    render_postgres_dsn: str,
) -> None:
    service, session, inputs = linked(render_postgres_dsn)
    with patch.object(PostgresSuggestionTransaction, "snapshot", return_value=inputs):
        service.run(event_id=session.event_id, stage_id=session.stage_id, actor_id=ACTOR_ID)
    boundaries = BoundaryProposalService(service.repository, FixedClock(at(2)))
    opened = boundaries.open(session.event_id, session.id)
    start = next(p for p in opened if p.boundary_kind == "start")
    end = next(p for p in opened if p.boundary_kind == "end")
    command = EntityId.new()
    args = DecisionArgs(event_id=session.event_id, session_id=session.id, proposal_id=start.id,
                        command_id=command, actor_id=ACTOR_ID)
    with patch.object(PostgresSuggestionTransaction, "save_boundary_decision",
                      side_effect=RuntimeError("crash")):
        with pytest.raises(RuntimeError, match="crash"):
            boundaries.apply(**args)
    kernel = PostgresEventModeKernelRepository(render_postgres_dsn)
    assert kernel.get_session(session.id) == session
    assert boundaries.open(session.event_id, session.id) == opened
    decision = boundaries.apply(**args)
    restarted = BoundaryProposalService(PostgresSuggestionRepository(render_postgres_dsn),
                                         FixedClock(at(3)))
    assert restarted.apply(**args) == decision
    updated = kernel.get_session(session.id)
    assert updated is not None and updated.revision == session.revision + 1
    assert updated.authoritative_start == start.boundary_at
    with pytest.raises(SuggestionConflictError, match="command_id_conflict"):
        restarted.dismiss(**args)
    with pytest.raises(SuggestionConflictError, match="boundary_proposal_decided"):
        different = args.copy()
        different["command_id"] = EntityId.new()
        restarted.apply(**different)
    dismissed = restarted.dismiss(event_id=session.event_id, session_id=session.id,
                                   proposal_id=end.id, command_id=EntityId.new(), actor_id=ACTOR_ID)
    assert not restarted.open(session.event_id, session.id)
    history, _ = restarted.history(session.event_id, session.id)
    assert set(history) == {decision, dismissed}
    page, cursor = restarted.history(session.event_id, session.id, limit=1)
    tail, cursor2 = restarted.history(session.event_id, session.id, limit=1, after=cursor)
    assert page + tail == history and cursor is not None and cursor2 is None
    with psycopg.connect(render_postgres_dsn) as connection:
        for statement in ("UPDATE stageflow.boundary_proposal_decision SET reason='changed'",
                          "DELETE FROM stageflow.boundary_proposal_decision"):
            with pytest.raises(psycopg.Error, match="boundary_proposal_decision_immutable"):
                with connection.transaction():
                    connection.execute(statement)
        with pytest.raises(psycopg.errors.UniqueViolation), connection.transaction():
            connection.execute("""INSERT INTO stageflow.boundary_proposal_decision
                SELECT * FROM stageflow.boundary_proposal_decision LIMIT 1""")
    runner = PostgresMigrationRunner(render_postgres_dsn)
    with pytest.raises(psycopg.Error, match="boundary_proposal_reverse_requires_empty_decisions"):
        runner.reverse_session_suggestions_already_realized()
    assert service.latest_run(session.event_id, session.stage_id).boundary_proposals_created == 2
    assert restarted.history(session.event_id, session.id)[0] == history


@pytest.mark.parametrize("cause", ["boundary", "newer"])
def test_postgres_stale_proposals_excluded_and_refused(
    render_postgres_dsn: str, cause: str,
) -> None:
    service, session, inputs = linked(render_postgres_dsn)
    with patch.object(PostgresSuggestionTransaction, "snapshot", return_value=inputs):
        service.run(event_id=session.event_id, stage_id=session.stage_id, actor_id=ACTOR_ID)
    boundaries = BoundaryProposalService(service.repository, FixedClock(at(3)))
    p = next(p for p in boundaries.open(session.event_id, session.id) if p.boundary_kind == "start")
    kernel = DurableEventModeKernel(
        repository=PostgresEventModeKernelRepository(render_postgres_dsn), clock=FixedClock(at(2)))
    if cause == "newer":
        kernel.propose_session_boundary(session_id=session.id, boundary_kind="start",
                                         boundary_at=at(10), epistemic_kind=p.epistemic_kind,
                                         proposer_id=p.proposer_id, evidence_ids=p.evidence_ids,
                                         policy_id=p.policy_id, policy_version=p.policy_version,
                                         reason=p.reason)
    else:
        kernel.correct_session_boundary(operation_id=EntityId.new(), session_id=session.id,
                                         boundary_kind="start", boundary_at=at(70),
                                         actor_id=ACTOR_ID, reason="Human correction")
    assert p not in boundaries.open(session.event_id, session.id)
    with pytest.raises(SuggestionConflictError, match="boundary_proposal_stale"):
        boundaries.apply(event_id=session.event_id, session_id=session.id, proposal_id=p.id,
                           command_id=EntityId.new(), actor_id=ACTOR_ID)


def test_0027_forward_reverse_defaults_constraints_and_retained_proposals(
    render_postgres_dsn: str,
) -> None:
    service, session, inputs = linked(render_postgres_dsn)
    runner = PostgresMigrationRunner(render_postgres_dsn)
    original = service.latest_run(session.event_id, session.stage_id)
    runner.reverse_boundary_proposal_decisions()
    with psycopg.connect(render_postgres_dsn) as connection:
        assert connection.execute("""SELECT 1 WHERE
            to_regclass('stageflow.boundary_proposal_decision') IS NOT NULL""").fetchone() is None
        assert connection.execute("""SELECT 1 FROM stageflow.schema_migration
            WHERE version='0027_boundary_proposal_decisions'""").fetchone() is None
    runner.apply_boundary_proposal_decisions()
    runner.apply_boundary_proposal_decisions()
    assert service.latest_run(session.event_id, session.stage_id) == original
    assert original.boundary_proposals_created == 0
    with patch.object(PostgresSuggestionTransaction, "snapshot", return_value=inputs):
        run = service.run(event_id=session.event_id, stage_id=session.stage_id, actor_id=ACTOR_ID)
    assert run.boundary_proposals_created == 2
    with psycopg.connect(render_postgres_dsn) as connection:
        for count, error in ((-1, psycopg.errors.CheckViolation),
                             (None, psycopg.errors.NotNullViolation),
                             (2_147_483_648, psycopg.errors.NumericValueOutOfRange)):
            with pytest.raises(error), connection.transaction():
                connection.execute("""INSERT INTO stageflow.session_suggestion_run
                    OVERRIDING SYSTEM VALUE
                    SELECT (jsonb_populate_record(NULL::stageflow.session_suggestion_run,
                      to_jsonb(r) || jsonb_build_object('run_id', %s::text,
                        'run_sequence', -1, 'boundary_proposals_created', %s::bigint))).*
                    FROM stageflow.session_suggestion_run r WHERE run_id=%s""",
                    (EntityId.new().value, count, run.id.value))
    kernel = PostgresEventModeKernelRepository(render_postgres_dsn)
    proposals = kernel.list_boundary_proposals(session.id)
    runner.reverse_boundary_proposal_decisions()
    assert kernel.list_boundary_proposals(session.id) == proposals
    runner.apply_boundary_proposal_decisions()
    assert service.latest_run(session.event_id, session.stage_id) == replace(
        run, boundary_proposals_created=0)
