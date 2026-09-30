"""The shared fixture rolls back all DDL and immutable rows after each test."""
from dataclasses import replace
from unittest.mock import patch

import psycopg
import pytest

from app.contexts.production.event_mode_kernel.service import DurableEventModeKernel
from app.contexts.production.session_suggestions.contracts import InputSnapshot, SkipCounts
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


def test_0026_forward_reverse_old_rows_default_and_count_roundtrip(
    render_postgres_dsn: str,
) -> None:
    service, seed = seeded(render_postgres_dsn)
    runner = PostgresMigrationRunner(render_postgres_dsn)
    original = service.latest_run(seed.event_id, seed.stage_id)
    runner.reverse_session_suggestions_already_realized()
    with psycopg.connect(render_postgres_dsn) as connection:
        assert connection.execute("""SELECT 1 FROM information_schema.columns
            WHERE table_schema='stageflow' AND table_name='session_suggestion_run'
              AND column_name='already_realized'""").fetchone() is None
        assert connection.execute("""SELECT 1 FROM stageflow.schema_migration
            WHERE version='0026_session_suggestions_already_realized'""").fetchone() is None
    runner.apply_session_suggestions_already_realized()
    runner.apply_session_suggestions_already_realized()
    assert service.latest_run(seed.event_id, seed.stage_id) == original
    assert original.skips.already_realized == 0
    counted = replace(original, id=EntityId.new(), input_digest="c" * 64,
                      skips=SkipCounts(already_realized=2))
    with service.repository.transaction(FixedClock(NOW)) as tx:
        tx.save_run(counted, ())
    restarted = SessionSuggestionService(PostgresSuggestionRepository(render_postgres_dsn),
                                         FixedClock(NOW))
    assert restarted.latest_run(seed.event_id, seed.stage_id) == counted
    with psycopg.connect(render_postgres_dsn) as connection:
        insert = """INSERT INTO stageflow.session_suggestion_run
            (run_id, event_id, stage_id, input_digest, actor_id, created_at,
             expectation_references, asset_inputs, policy_id, policy_version, policy_constants,
             no_timing_evidence, no_segmentation, clock_implausible, no_coverage, no_planned_time,
             already_realized)
            SELECT %s, event_id, stage_id, input_digest, actor_id, created_at,
                   expectation_references, asset_inputs, policy_id, policy_version,
                   policy_constants,
                   no_timing_evidence, no_segmentation, clock_implausible, no_coverage,
                   no_planned_time, %s
            FROM stageflow.session_suggestion_run WHERE run_id=%s"""
        for value, error in ((-1, psycopg.errors.CheckViolation),
                             (None, psycopg.errors.NotNullViolation),
                             (2_147_483_648, psycopg.errors.NumericValueOutOfRange)):
            with pytest.raises(error), connection.transaction():
                connection.execute(insert, (EntityId.new().value, value, seed.run_id.value))
    # Reversal also works with nonzero counts, without changing suggestion identities.
    runner.reverse_session_suggestions_already_realized()
    runner.apply_session_suggestions_already_realized()
    assert restarted.latest_run(seed.event_id, seed.stage_id) == replace(
        counted, skips=SkipCounts())
    assert restarted.read(seed.event_id, seed.id)[0] == seed


def test_postgres_confirm_then_run_persists_filter_digest_and_queue(
    render_postgres_dsn: str,
) -> None:
    service, seed = seeded(render_postgres_dsn)
    event, stage = seed.event_id, seed.stage_id
    kernel = DurableEventModeKernel(
        repository=PostgresEventModeKernelRepository(render_postgres_dsn), clock=FixedClock(NOW))
    talks = tuple(kernel.record_program_expectation(
        event_id=event, stage_id=stage, key=f"talk-{i}", title=f"Talk {i}",
        planned_start=at(start), planned_end=at(end))
        for i, start, end in ((1, 0, 1800), (2, 1920, 3600)))
    inputs = InputSnapshot(talks, (asset(300, 3900, freezes=((1800, 1920),),
                                        silences=((1800, 1920),)),))
    with patch.object(PostgresSuggestionTransaction, "snapshot", return_value=inputs):
        first = service.run(event_id=event, stage_id=stage, actor_id=ACTOR_ID)
        before = {s.candidate.expectation.id: s for s in service.page(event, stage)[0]
                  if s.candidate.expectation is not None}
        service.confirm(event_id=event, suggestion_id=before[talks[0].id].id,
                        command_id=EntityId.new(), actor_id=ACTOR_ID)
        second = service.run(event_id=event, stage_id=stage, actor_id=ACTOR_ID)
    assert second.skips.already_realized == 1 and second.input_digest != first.input_digest
    assert second.blocks == first.blocks and second.expectations == first.expectations
    restarted = SessionSuggestionService(PostgresSuggestionRepository(render_postgres_dsn),
                                         FixedClock(NOW))
    assert restarted.latest_run(event, stage) == second
    remaining, = restarted.page(event, stage)[0]
    assert remaining.candidate == before[talks[1].id].candidate
    item, = restarted.list_pending_confirmations(event)
    assert "open_count:1" in item.reason_codes
