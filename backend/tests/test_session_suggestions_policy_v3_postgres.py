"""The fixture rolls back all DDL and rows, including immutable history."""
from dataclasses import asdict, fields, replace

import psycopg
import pytest
from psycopg import sql
from psycopg.types.json import Jsonb

from app.contexts.production.event_mode_kernel.service import DurableEventModeKernel
from app.contexts.production.session_suggestions.contracts import (
    POLICY_V1,
    POLICY_V2,
    POLICY_V3,
    CandidateV3,
    ScheduleOffsetEntry,
    SuggestionConflictError,
)
from app.contexts.production.session_suggestions.service import SessionSuggestionService
from app.infrastructure.postgres.event_mode_kernel_repository import (
    PostgresEventModeKernelRepository,
)
from app.infrastructure.postgres.migrations import PostgresMigrationRunner
from app.infrastructure.postgres.session_suggestion_repository import PostgresSuggestionRepository
from app.shared.ids import EntityId
from app.shared.time import FixedClock
from tests.test_durable_event_mode_kernel import ACTOR_ID
from tests.test_render_work_execution import render_postgres_dsn as render_postgres_dsn
from tests.test_session_suggestion_policy import NOW, at
from tests.test_session_suggestions_postgres import seeded


def test_v3_forward_reverse_preserves_legacy_and_guards_v3_run(render_postgres_dsn: str) -> None:
    service, legacy = seeded(render_postgres_dsn)
    runner = PostgresMigrationRunner(render_postgres_dsn)
    runner.reverse_session_suggestions_policy_v3()
    assert service.read(legacy.event_id, legacy.id)[0] == legacy
    runner.apply_session_suggestions_policy_v3()
    runner.apply_session_suggestions_policy_v3()
    with service.repository.transaction(FixedClock(NOW)) as tx:
        original = tx.find_run("a" * 64)
        assert original is not None
        run = replace(original, id=EntityId.new(), input_digest="b" * 64, policy=POLICY_V3)
        candidate = CandidateV3(**{f.name: getattr(legacy.candidate, f.name)
                                   for f in fields(legacy.candidate)})
        suggestion = replace(legacy, id=EntityId.new(), run_id=run.id,
                             candidate=candidate, policy_version="3")
        tx.save_run(run, (suggestion,))
        assert tx.find_run(run.input_digest) == run
    restarted = SessionSuggestionService(PostgresSuggestionRepository(render_postgres_dsn),
                                          FixedClock(NOW))
    assert restarted.read(legacy.event_id, suggestion.id)[0] == suggestion
    assert restarted.read(legacy.event_id, legacy.id)[0] == legacy
    with pytest.raises(psycopg.Error, match="reverse_requires_empty_tables_for_v3_and_offsets"):
        runner.reverse_session_suggestions_policy_v3()


def test_override_roundtrip_replay_clear_blocks_and_immutable_membership(
    render_postgres_dsn: str,
) -> None:
    service, seed = seeded(render_postgres_dsn)
    event, stage = seed.event_id, seed.stage_id
    kernel = DurableEventModeKernel(
        repository=PostgresEventModeKernelRepository(render_postgres_dsn), clock=FixedClock(NOW))
    expectation = kernel.record_program_expectation(
        event_id=event, stage_id=stage, key="synthetic", title="Synthetic talk",
        planned_start=at(0), planned_end=at(3000))
    command = EntityId.new()
    entries = (ScheduleOffsetEntry(at(0), 1200), ScheduleOffsetEntry(at(6000), -300))
    setting = service.set_offset(event_id=event, stage_id=stage, command_id=command,
                                 actor_id=ACTOR_ID, entries=entries)
    # Even a setting without a v3 run protects reversal.
    with pytest.raises(psycopg.Error, match="reverse_requires_empty_tables_for_v3_and_offsets"):
        PostgresMigrationRunner(render_postgres_dsn).reverse_session_suggestions_policy_v3()
    run = service.run(event_id=event, stage_id=stage, actor_id=ACTOR_ID)
    assert run.blocks[0].schedule_offset_seconds == 1200
    assert run.blocks[0].override_setting_version == setting.version
    restarted = SessionSuggestionService(PostgresSuggestionRepository(render_postgres_dsn),
                                          FixedClock(NOW))
    assert restarted.run(event_id=event, stage_id=stage, actor_id=ACTOR_ID) == run
    clear = restarted.set_offset(event_id=event, stage_id=stage, command_id=EntityId.new(),
                                  actor_id=ACTOR_ID, entries=())
    assert restarted.current_offset(event, stage) == clear
    assert restarted.set_offset(event_id=event, stage_id=stage, command_id=command,
                                 actor_id=ACTOR_ID, entries=entries) == setting
    assert restarted.offset_history(event, stage, limit=1) == ((setting,), 1)
    assert restarted.offset_history(event, stage, after=1) == ((clear,), None)
    with pytest.raises(SuggestionConflictError):
        restarted.set_offset(event_id=event, stage_id=stage, command_id=command,
                              actor_id=ACTOR_ID, entries=())
    latest = restarted.run(event_id=event, stage_id=stage, actor_id=ACTOR_ID)
    assert latest.input_digest != run.input_digest
    assert latest.blocks[0].schedule_offset_source == "none"
    assert kernel.repository.get_program_expectation(expectation.id) == expectation
    assert not kernel.repository.list_sessions_for_stage(stage)
    for table in ("stage_schedule_offset_setting", "stage_schedule_offset_entry",
                  "session_suggestion_run_block"):
        for statement in ("DELETE FROM stageflow.{}", "UPDATE stageflow.{} SET stage_id=stage_id"):
            with pytest.raises(psycopg.Error, match="session_suggestion_immutable"):
                with psycopg.connect(render_postgres_dsn) as connection:
                    connection.execute(sql.SQL(statement).format(sql.Identifier(table)))
    with pytest.raises(psycopg.Error, match="entries_incomplete_or_unordered"):
        with psycopg.connect(render_postgres_dsn) as connection:
            connection.execute("""INSERT INTO stageflow.stage_schedule_offset_entry
                (event_id, stage_id, version, ordinal, effective_from, offset_seconds)
                VALUES (%s,%s,1,2,%s,0)""", (event.value, stage.value, at(7000)))
    with pytest.raises(psycopg.Error, match="blocks_incomplete_or_mismatched"):
        with psycopg.connect(render_postgres_dsn) as connection:
            connection.execute("""INSERT INTO stageflow.session_suggestion_run_block
                SELECT (jsonb_populate_record(NULL::stageflow.session_suggestion_run_block,
                    to_jsonb(b) || '{"ordinal":1}'::jsonb)).*
                FROM stageflow.session_suggestion_run_block b WHERE run_id=%s""", (run.id.value,))


def test_every_policy_requires_exact_constants_and_versioned_components(
    render_postgres_dsn: str,
) -> None:
    _, seed = seeded(render_postgres_dsn)
    with psycopg.connect(render_postgres_dsn) as connection:
        insert = """INSERT INTO stageflow.session_suggestion_run
            (run_id, event_id, stage_id, input_digest, actor_id, created_at,
             expectation_references, asset_inputs, policy_id, policy_version, policy_constants,
             no_timing_evidence, no_segmentation, clock_implausible, no_coverage, no_planned_time)
            SELECT %s, event_id, stage_id, input_digest, actor_id, created_at,
                   expectation_references, asset_inputs, policy_id, %s, %s,
                   no_timing_evidence, no_segmentation, clock_implausible,
                   no_coverage, no_planned_time
            FROM stageflow.session_suggestion_run WHERE run_id=%s"""
        for policy in (POLICY_V1, POLICY_V2, POLICY_V3):
            constants = asdict(policy)
            run_id = EntityId.new().value
            connection.execute(insert, (run_id, policy.version,
                                        Jsonb(constants), seed.run_id.value))
            for key, value in constants.items():
                changed = {**constants, key: value + 1 if isinstance(value, (int, float))
                           else value + "-changed"}
                with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                    connection.execute(insert, (EntityId.new().value, policy.version,
                                                Jsonb(changed), seed.run_id.value))
            for other in {"1", "2", "3"} - {policy.version}:
                with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                    connection.execute(insert, (EntityId.new().value, other,
                                                Jsonb(constants), seed.run_id.value))
            suggestion_insert = """INSERT INTO stageflow.session_suggestion
                SELECT (jsonb_populate_record(NULL::stageflow.session_suggestion,
                    to_jsonb(s) || %s::jsonb)).*
                FROM stageflow.session_suggestion s WHERE suggestion_id=%s"""
            valid = {"suggestion_id": EntityId.new().value, "run_id": run_id,
                     "policy_version": policy.version,
                     "schedule_offset_seconds": 0 if policy.version == "3" else None,
                     "schedule_offset_source": "none" if policy.version == "3" else None}
            connection.execute(suggestion_insert, (Jsonb(valid), seed.id.value))
            invalids = ([{"schedule_offset_seconds": None}, {"schedule_offset_source": None},
                         {"schedule_offset_source": "invalid"}, {"schedule_offset_seconds": 7201},
                         {"schedule_offset_seconds": 1}, {"schedule_offset_source": "producer"}]
                        if policy.version == "3" else
                        [{"schedule_offset_seconds": 0}, {"schedule_offset_source": "none"}])
            for change in invalids:
                with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                    connection.execute(suggestion_insert, (Jsonb({**valid, **change,
                        "suggestion_id": EntityId.new().value}), seed.id.value))


@pytest.mark.parametrize("entries", [((0, 0), (0, 1)), ((1, 0), (0, 1)), ((0, 7201),)])
def test_database_rejects_bad_entry_bounds_and_order(
    render_postgres_dsn: str, entries: tuple[tuple[int, int], ...],
) -> None:
    _, seed = seeded(render_postgres_dsn)
    with pytest.raises(psycopg.Error):
        with psycopg.connect(render_postgres_dsn) as connection:
            connection.execute("""INSERT INTO stageflow.stage_schedule_offset_setting
                (event_id, stage_id, version, command_id, request_digest,
                 set_by, set_at, entry_count)
                VALUES (%s,%s,1,%s,%s,%s,%s,%s)""",
                (seed.event_id.value, seed.stage_id.value, EntityId.new().value,
                 "a" * 64, ACTOR_ID.value, NOW, len(entries)))
            for ordinal, (effective, offset) in enumerate(entries):
                connection.execute("""INSERT INTO stageflow.stage_schedule_offset_entry
                    (event_id, stage_id, version, ordinal, effective_from, offset_seconds)
                    VALUES (%s,%s,1,%s,%s,%s)""",
                    (seed.event_id.value, seed.stage_id.value, ordinal, at(effective), offset))
