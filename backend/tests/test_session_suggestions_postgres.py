"""Real PostgreSQL tests use the existing disposable, rolled-back schema fixture."""
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from app.contexts.events import EventStageBootstrapRequest, StageBootstrapDefinition
from app.contexts.production.event_mode_kernel.contracts import StartSessionRequest
from app.contexts.production.event_mode_kernel.service import DurableEventModeKernel
from app.contexts.production.session_suggestions.contracts import (
    InputSnapshot,
    Reference,
    SessionSuggestion,
    SuggestionRun,
    SuggestionStatus,
)
from app.contexts.production.session_suggestions.policy import evaluate
from app.contexts.production.session_suggestions.repository import SuggestionTransaction
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
from app.shared.time import Clock, FixedClock
from tests.test_durable_event_mode_kernel import ACTOR_ID, bootstrap_request
from tests.test_render_work_execution import (
    render_postgres_dsn as render_postgres_dsn,
)
from tests.test_session_assembly_foundation import postgres_dsn as postgres_dsn
from tests.test_session_suggestion_policy import NOW, asset


def seeded(dsn: str) -> tuple[SessionSuggestionService, SessionSuggestion]:
    kernel = DurableEventModeKernel(
        repository=PostgresEventModeKernelRepository(dsn), clock=FixedClock(NOW))
    bootstrap = kernel.bootstrap(bootstrap_request())
    assert bootstrap.event is not None
    stage, event = bootstrap.stages[0].id, bootstrap.event.id
    inputs = InputSnapshot((), (asset(0, 180),))
    result = evaluate(inputs)
    run = SuggestionRun(EntityId.new(), event, stage, "a" * 64, ACTOR_ID, NOW, (), inputs.assets,
                         None, None, result.skips)
    suggestion = SessionSuggestion(EntityId.new(), run.id, event, stage, result.candidates[0])
    repository = PostgresSuggestionRepository(dsn)
    with repository.transaction(FixedClock(NOW)) as tx:
        tx.scope(event, stage)
        tx.save_run(run, (suggestion,))
        assert tx.find_run(run.input_digest) == run
    return SessionSuggestionService(repository, FixedClock(NOW)), suggestion


def test_postgres_transactional_confirm_replay_and_immutable_history(
    render_postgres_dsn: str,
) -> None:
    service, suggestion = seeded(render_postgres_dsn)
    command = EntityId.new()
    with patch.object(PostgresSuggestionTransaction, "save_decision",
                      side_effect=RuntimeError("crash")):
        with pytest.raises(RuntimeError, match="crash"):
            service.confirm(event_id=suggestion.event_id, suggestion_id=suggestion.id,
                             command_id=command, actor_id=ACTOR_ID)
    kernel = PostgresEventModeKernelRepository(render_postgres_dsn)
    assert not kernel.list_sessions_for_stage(suggestion.stage_id)
    result = service.confirm(event_id=suggestion.event_id, suggestion_id=suggestion.id,
                              command_id=command, actor_id=ACTOR_ID)
    restarted = SessionSuggestionService(
        PostgresSuggestionRepository(render_postgres_dsn), FixedClock(NOW))
    assert restarted.confirm(event_id=suggestion.event_id, suggestion_id=suggestion.id,
                              command_id=command, actor_id=ACTOR_ID) == result
    assert len(kernel.list_sessions_for_stage(suggestion.stage_id)) == 1
    assert restarted.read(suggestion.event_id, suggestion.id) == (
        suggestion, SuggestionStatus.CONFIRMED)
    for table in ("session_suggestion_run", "session_suggestion", "session_suggestion_decision"):
        with pytest.raises(psycopg.Error, match="session_suggestion_immutable"):
            with psycopg.connect(render_postgres_dsn) as connection:
                statement = sql.SQL("DELETE FROM stageflow.{}").format(sql.Identifier(table))
                connection.execute(statement)
    with pytest.raises(psycopg.Error, match="requires_empty_tables"):
        PostgresMigrationRunner(render_postgres_dsn).reverse_session_suggestions_v1()


def test_postgres_empty_forward_reverse_and_run_input_digest(render_postgres_dsn: str) -> None:
    runner = PostgresMigrationRunner(render_postgres_dsn)
    runner.reverse_session_suggestions_v1()
    runner.apply_session_suggestions_v1()
    kernel = DurableEventModeKernel(
        repository=PostgresEventModeKernelRepository(render_postgres_dsn), clock=FixedClock(NOW))
    result = kernel.bootstrap(bootstrap_request())
    assert result.event is not None
    service = SessionSuggestionService(
        PostgresSuggestionRepository(render_postgres_dsn), FixedClock(NOW))
    first = service.run(event_id=result.event.id, stage_id=result.stages[0].id, actor_id=ACTOR_ID)
    replay = service.run(event_id=result.event.id, stage_id=result.stages[0].id, actor_id=ACTOR_ID)
    assert replay == first
    assert not service.page(result.event.id, result.stages[0].id)[0]
    with pytest.raises(psycopg.Error, match="requires_empty_tables"):
        runner.reverse_session_suggestions_v1()


def test_migration_has_first_class_components_and_no_stored_status() -> None:
    path = (Path(__file__).parents[1]
            / "app/infrastructure/postgres/sql/0022_session_suggestions_forward.sql")
    source = path.read_text(encoding="utf-8")
    assert "derived_status" not in source and "status text" not in source
    for component in ("start_edge_kind", "end_edge_kind", "start_plan_offset_seconds",
                      "end_plan_offset_seconds", "start_silence_support", "end_silence_support",
                      "start_cue_support", "end_cue_support", "overlap", "strength"):
        assert component in source


def test_postgres_populated_snapshot_latest_evidence_cues_and_no_upstream_writes(
    render_postgres_dsn: str,
) -> None:
    from app.contexts.production.media_segmentation_evidence.contracts import (
        MediaSegmentationEvidence,
        SegmentationInterval,
        SegmentationResult,
    )
    from app.contexts.production.media_segmentation_evidence.enqueue import (
        MediaSegmentationEnqueue,
        RegisteredSegmentationAsset,
    )
    from app.contexts.production.media_timing_evidence import MediaTimingEvidenceApplication
    from app.infrastructure.postgres.media_segmentation_repository import (
        PostgresMediaSegmentationRepository,
    )
    from app.infrastructure.postgres.media_timing_evidence_repository import (
        PostgresMediaTimingEvidenceRepository,
    )
    from tests.media_timing_evidence_fixtures import evidence_request
    from tests.test_derived_editorial_postgres import PostgresHarness, upstream_snapshot
    from tests.test_media_segmentation import setup

    h = PostgresHarness(render_postgres_dsn)
    now = h.session.authoritative_start
    clock = FixedClock(now)
    service = SessionSuggestionService(PostgresSuggestionRepository(h.dsn), clock)
    no_timing = service.run(event_id=h.event, stage_id=h.session.stage_id, actor_id=ACTOR_ID)
    assert no_timing.skips.no_timing_evidence == 1
    transcript = h.transcript()
    h.transcript(status="partial")
    h.timing()
    request = evidence_request(profile_id="synthetic-recorder", inspected_at=now)
    derived = replace(request.result.derivations[0], rule_id="creation_time_plus_duration",
                      candidate_started_at=now, candidate_ended_at=now + timedelta(seconds=600))
    timing = MediaTimingEvidenceApplication(PostgresMediaTimingEvidenceRepository(h.dsn)).apply(
        replace(request, operation_id=EntityId.new(), asset_id=h.asset, manifest_id=h.manifest,
                result=replace(request.result, derivations=(derived,))))
    segmentation = PostgresMediaSegmentationRepository(h.dsn)
    operation = MediaSegmentationEnqueue(segmentation, "test-deployment", clock).enqueue(
        h.event, RegisteredSegmentationAsset(h.asset, h.manifest, now))
    claim = segmentation.claim_next(setup(segmentation, h.event))
    assert claim is not None
    claim = segmentation.mark_running(claim)
    evidence = MediaSegmentationEvidence(
        EntityId.new(), operation.id, h.asset, h.manifest, "1.0", claim.attempt.id,
        SegmentationResult((SegmentationInterval("freeze", 300_000_000, 360_000_000),),
                           600_000_000, "8.1", "a" * 64, now), now,
    )
    segmentation.apply_result(claim, evidence)
    before = upstream_snapshot(h.dsn)
    run = service.run(event_id=h.event, stage_id=h.session.stage_id, actor_id=ACTOR_ID,
                       start_cue_list=Reference(h.phrases.id, 1))
    assert run.assets[0].timing == Reference(timing.id, timing.revision)
    assert run.assets[0].transcript == Reference(transcript, 1)
    assert run.assets[0].segmentation_ids == (evidence.id,)
    assert run.assets[0].intervals == evidence.result.intervals
    assert run.assets[0].start_cues[0] == now
    suggestions, _ = service.page(h.event, h.session.stage_id)
    assert len(suggestions) == 2
    assert any(s.candidate.start_cue_support for s in suggestions)
    assert upstream_snapshot(h.dsn) == before
    assert service.run(event_id=h.event, stage_id=h.session.stage_id, actor_id=ACTOR_ID,
                        start_cue_list=Reference(h.phrases.id, 1)) == run
    h.timing(matches=0)
    changed = service.run(event_id=h.event, stage_id=h.session.stage_id, actor_id=ACTOR_ID)
    assert changed.skips.no_timing_evidence == 1
    assert all(service.read(h.event, s.id)[1] == SuggestionStatus.SUPERSEDED for s in suggestions)


def test_postgres_return_to_earlier_inputs_creates_fresh_latest_run(
    render_postgres_dsn: str,
) -> None:
    service, seed = seeded(render_postgres_dsn)
    initial = InputSnapshot((), (asset(0, 180),))
    changed = replace(initial, assets=(replace(initial.assets[0], segmentation_ids=()),))
    with patch.object(PostgresSuggestionTransaction, "snapshot", return_value=initial):
        first = service.run(event_id=seed.event_id, stage_id=seed.stage_id, actor_id=ACTOR_ID)
    first_suggestion = service.page(seed.event_id, seed.stage_id)[0][0]
    with patch.object(PostgresSuggestionTransaction, "snapshot", return_value=changed):
        second = service.run(event_id=seed.event_id, stage_id=seed.stage_id, actor_id=ACTOR_ID)
    second_suggestion = service.page(seed.event_id, seed.stage_id)[0][0]
    with patch.object(PostgresSuggestionTransaction, "snapshot", return_value=initial):
        third = service.run(event_id=seed.event_id, stage_id=seed.stage_id, actor_id=ACTOR_ID)
        assert service.run(
            event_id=seed.event_id, stage_id=seed.stage_id, actor_id=ACTOR_ID) == third
    assert third.id not in (first.id, second.id)
    assert third.input_digest == first.input_digest
    assert service.read(seed.event_id, first_suggestion.id)[1] == SuggestionStatus.SUPERSEDED
    assert service.read(seed.event_id, second_suggestion.id)[1] == SuggestionStatus.SUPERSEDED
    opened, _ = service.page(seed.event_id, seed.stage_id)
    assert opened and all(s.run_id == third.id for s in opened)
    with service.repository.transaction(FixedClock(NOW)) as tx:
        assert isinstance(tx, PostgresSuggestionTransaction)
        rows = tx.connection.execute(
            """SELECT run_id FROM stageflow.session_suggestion_run WHERE stage_id=%s
               AND input_digest=%s ORDER BY run_sequence""",
            (seed.stage_id.value, first.input_digest),
        ).fetchall()
    assert [str(row["run_id"]) for row in rows] == [first.id.value, third.id.value]


@pytest.mark.parametrize("action", ["page", "run"])
def test_postgres_suggestion_transaction_does_not_block_other_stage_start(
    postgres_dsn: str, action: str,
) -> None:
    # This needs genuinely separate connections and committed bootstrap rows;
    # render_postgres_dsn deliberately borrows one connection and cannot prove it.
    PostgresMigrationRunner(postgres_dsn).apply_event_mode_kernel_v1()
    clock = FixedClock(NOW)
    kernel = DurableEventModeKernel(
        repository=PostgresEventModeKernelRepository(
            make_conninfo(postgres_dsn, options="-c lock_timeout=500ms")), clock=clock)
    suffix = EntityId.new().value
    boot = kernel.bootstrap(EventStageBootstrapRequest(
        EntityId.new(), "suggestion-lock-" + suffix, "Synthetic Event",
        tuple(StageBootstrapDefinition(f"stage-{i}", f"Stage {i}", {
            f"source-{suffix}-{i}": "synthetic-source"}) for i in range(2)), ACTOR_ID, NOW,
    ))
    assert boot.event is not None
    event, stage, other_stage = boot.event.id, boot.stages[0].id, boot.stages[1].id
    repository = PostgresSuggestionRepository(postgres_dsn)
    service = SessionSuggestionService(repository, clock)
    transaction = repository.transaction
    started: list[EntityId] = []

    class RollbackSuggestionTransaction(Exception):
        pass

    @contextmanager
    def while_open(clock: Clock) -> Generator[SuggestionTransaction]:
        try:
            with transaction(clock) as tx:
                yield tx
                # The page/run has executed, but its transaction still holds any locks.
                session = kernel.start_session(StartSessionRequest(
                    EntityId.new(), event, other_stage, ACTOR_ID, NOW, NOW))
                started.append(session.id)
                # Keep the shared test database eligible for guarded reversals.
                raise RollbackSuggestionTransaction
        except RollbackSuggestionTransaction:
            pass

    with patch.object(repository, "transaction", side_effect=while_open):
        if action == "page":
            service.page(event, stage)
        else:
            service.run(event_id=event, stage_id=stage, actor_id=ACTOR_ID)
    sessions = kernel.repository.list_sessions_for_stage(other_stage)
    assert len(sessions) == 1 and started == [sessions[0].id]
    assert not service.page(event, stage)[0]
    with repository.transaction(clock) as tx:
        assert isinstance(tx, PostgresSuggestionTransaction)
        assert tx.connection.execute(
            "SELECT 1 FROM stageflow.session_suggestion_run WHERE event_id=%s", (event.value,),
        ).fetchone() is None
