"""Every SQL test uses the disposable schema and rolled-back outer transaction."""
from dataclasses import replace
from typing import Any
from unittest.mock import patch

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.contexts.editorial.derivation_contracts import EditorialPhraseList
from app.contexts.production.session_suggestions.contracts import SuggestionConflictError
from app.contexts.production.session_suggestions.cue_catalog import CueRole
from app.contexts.production.session_suggestions.cue_composition import CustomPhrase, PhraseChoice
from app.contexts.production.session_suggestions.cue_service import BoundaryCueService
from app.contexts.production.session_suggestions.service import SessionSuggestionService
from app.infrastructure.postgres.boundary_cue_repository import PostgresBoundaryCueTransaction
from app.infrastructure.postgres.editorial_derivation_repository import (
    PostgresEditorialDerivationTransaction,
)
from app.infrastructure.postgres.migrations import PostgresMigrationRunner
from app.infrastructure.postgres.session_suggestion_repository import PostgresSuggestionRepository
from app.shared.ids import EntityId
from app.shared.time import FixedClock
from tests.test_boundary_cue_composition import CONFERENCE
from tests.test_durable_event_mode_kernel import ACTOR_ID
from tests.test_render_work_execution import render_postgres_dsn as render_postgres_dsn
from tests.test_session_suggestion_policy import NOW
from tests.test_session_suggestions_postgres import seeded

TABLES = ("boundary_cue_composition", "boundary_cue_group", "boundary_cue_choice",
          "boundary_cue_custom_phrase", "boundary_cue_segment_phrase")


def test_composition_restart_replay_run_defaults_history_and_reverse_guard(
    render_postgres_dsn: str,
) -> None:
    suggestions, seed = seeded(render_postgres_dsn)
    service = BoundaryCueService(suggestions.repository, FixedClock(NOW))
    request = replace(CONFERENCE, group_keys=CONFERENCE.group_keys + ("panels",),
                      include=(PhraseChoice("conference.mc-handoffs", "ladies and gentlemen"),),
                      exclude=(PhraseChoice("conference.mc-handoffs", "please welcome"),),
                      custom_phrases=(CustomPhrase("Synthetic closing", CueRole.END),))
    command = EntityId.new()
    first = service.publish(event_id=seed.event_id, actor_id=ACTOR_ID,
                            command_id=command, request=request)
    restarted_repo = PostgresSuggestionRepository(render_postgres_dsn)
    restarted = BoundaryCueService(restarted_repo, FixedClock(NOW))
    assert restarted.current(seed.event_id) == first
    second = restarted.publish(event_id=seed.event_id, actor_id=ACTOR_ID,
                                command_id=EntityId.new(), request=request)
    assert second.version == 2 and second.start_cue_list.id == first.start_cue_list.id
    assert restarted.publish(event_id=seed.event_id, actor_id=ACTOR_ID,
                             command_id=command, request=request) == first
    assert restarted.history(seed.event_id, limit=1) == ((first,), 1)
    assert restarted.history(seed.event_id, after=1) == ((second,), None)
    with pytest.raises(SuggestionConflictError):
        restarted.publish(event_id=seed.event_id, actor_id=ACTOR_ID,
                          command_id=command, request=CONFERENCE)
    run = SessionSuggestionService(restarted_repo, FixedClock(NOW)).run(
        event_id=seed.event_id, stage_id=seed.stage_id, actor_id=ACTOR_ID)
    assert run.start_cue_list == second.start_cue_list and run.end_cue_list == second.end_cue_list
    with suggestions.repository.transaction(FixedClock(NOW)) as tx:
        assert tx.find_run(run.input_digest) == run
    with pytest.raises(psycopg.Error, match="boundary_cue_reverse_requires_empty"):
        PostgresMigrationRunner(render_postgres_dsn).reverse_boundary_cue_composition_v1()

    for table in TABLES:
        for statement in ("DELETE FROM stageflow.{}", "UPDATE stageflow.{} SET version=version"):
            with pytest.raises(psycopg.Error, match="boundary_cue_composition_immutable"):
                with psycopg.Connection[dict[str, Any]].connect(
                    render_postgres_dsn, row_factory=dict_row) as connection:
                    connection.execute(sql.SQL(statement).format(sql.Identifier(table)))
    assert restarted.current(seed.event_id) == second

    for table, extra in (
        ("boundary_cue_group", {"group_key": "extra", "ordinal": 5}),
        ("boundary_cue_choice", {"phrase": "extra", "ordinal": 2}),
        ("boundary_cue_custom_phrase", {"phrase": "extra", "ordinal": 1}),
        ("boundary_cue_segment_phrase", {"phrase": "extra", "ordinal": 2}),
    ):
        with pytest.raises(psycopg.Error, match="boundary_cue_membership_incomplete"):
            with psycopg.Connection[dict[str, Any]].connect(
                    render_postgres_dsn, row_factory=dict_row) as connection:
                connection.execute(sql.SQL("""INSERT INTO stageflow.{table}
                    SELECT (jsonb_populate_record(NULL::stageflow.{table},
                        to_jsonb(c) || %s::jsonb)).* FROM stageflow.{table} c
                    WHERE event_id=%s AND version=1 ORDER BY ordinal LIMIT 1""").format(
                        table=sql.Identifier(table)), (Jsonb(extra), seed.event_id.value))


@pytest.mark.parametrize("failure", ["second_list", "composition"])
def test_sql_fault_rolls_back_lists_and_composition(render_postgres_dsn: str, failure: str) -> None:
    suggestions, seed = seeded(render_postgres_dsn)
    service = BoundaryCueService(suggestions.repository, FixedClock(NOW))
    original = PostgresBoundaryCueTransaction.publish_cue_list
    calls = 0

    def fail_second(tx: PostgresBoundaryCueTransaction,
                    value: EditorialPhraseList) -> EditorialPhraseList:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected fault")
        return original(tx, value)

    target = "publish_cue_list" if failure == "second_list" else "save_composition"
    effect = fail_second if failure == "second_list" else RuntimeError("injected fault")
    with patch.object(PostgresBoundaryCueTransaction, target, autospec=True, side_effect=effect):
        with pytest.raises(RuntimeError, match="injected fault"):
            service.publish(event_id=seed.event_id, actor_id=ACTOR_ID,
                            command_id=EntityId.new(), request=CONFERENCE)
    with psycopg.Connection[dict[str, Any]].connect(
                    render_postgres_dsn, row_factory=dict_row) as connection:
        assert not connection.execute("SELECT 1 FROM stageflow.boundary_cue_composition").fetchall()
        assert not connection.execute("""SELECT 1 FROM stageflow.editorial_phrase_list
            WHERE phrase_key IN ('boundary-cues-start', 'boundary-cues-end')""").fetchall()


@pytest.mark.parametrize("reserved", ["boundary-cues-start", "boundary-cues-end"])
def test_forward_reserved_key_guard_and_exact_empty_reverse(
    render_postgres_dsn: str, reserved: str,
) -> None:
    _, seed = seeded(render_postgres_dsn)
    runner = PostgresMigrationRunner(render_postgres_dsn)
    with psycopg.Connection[dict[str, Any]].connect(
                    render_postgres_dsn, row_factory=dict_row) as connection:
        before = {r["tablename"] for r in connection.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='stageflow'").fetchall()}
    runner.reverse_boundary_cue_composition_v1()
    runner.reverse_boundary_cue_composition_v1()
    with psycopg.Connection[dict[str, Any]].connect(
                    render_postgres_dsn, row_factory=dict_row) as connection:
        after = {r["tablename"] for r in connection.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='stageflow'").fetchall()}
    assert before - after == set(TABLES) and not after - before
    runner.apply_boundary_cue_composition_v1()
    runner.apply_boundary_cue_composition_v1()
    runner.reverse_boundary_cue_composition_v1()
    # Model a pre-migration manual publication through the unmodified storage adapter.
    with psycopg.Connection[dict[str, Any]].connect(
                    render_postgres_dsn, row_factory=dict_row) as connection:
        PostgresEditorialDerivationTransaction(connection).publish(EditorialPhraseList(
            EntityId.new(), seed.event_id, reserved, 1, "Legacy synthetic cues",
            ("synthetic cue",), ACTOR_ID, NOW))
    with pytest.raises(psycopg.Error, match="boundary_cue_reserved_key_exists"):
        runner.apply_boundary_cue_composition_v1()
    with psycopg.Connection[dict[str, Any]].connect(
                    render_postgres_dsn, row_factory=dict_row) as connection:
        assert connection.execute("""SELECT 1 FROM stageflow.schema_migration
            WHERE version='0025_boundary_cue_composition'""").fetchone() is None
        assert connection.execute("""SELECT 1 FROM pg_tables WHERE schemaname='stageflow'
            AND tablename='boundary_cue_composition'""").fetchone() is None
