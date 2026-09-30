"""Migration and v4 persistence; disposable schema fixture rolls back all DDL/data."""
from dataclasses import asdict, fields, replace
from typing import Any
from unittest.mock import patch

import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.contexts.production.event_mode_kernel.service import DurableEventModeKernel
from app.contexts.production.session_suggestions import service as service_module
from app.contexts.production.session_suggestions.contracts import (
    POLICY_V1,
    POLICY_V2,
    POLICY_V3,
    CandidateV4,
    InputSnapshot,
    ScheduleOffsetEntry,
)
from app.contexts.production.session_suggestions.policy_v4 import POLICY_V4
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


def constraints(dsn: str) -> list[dict[str, Any]]:
    with psycopg.Connection[dict[str, Any]].connect(dsn, row_factory=dict_row) as connection:
        return connection.execute("""SELECT conname, pg_get_constraintdef(oid) AS definition
            FROM pg_constraint WHERE conrelid IN ('stageflow.session_suggestion_run'::regclass,
                'stageflow.session_suggestion'::regclass) ORDER BY conname""").fetchall()


def test_v4_migration_forward_reverse_restores_prior_constraints_and_legacy(
    render_postgres_dsn: str,
) -> None:
    service, legacy = seeded(render_postgres_dsn)
    runner = PostgresMigrationRunner(render_postgres_dsn)
    runner.reverse_session_suggestions_policy_v4()
    prior = constraints(render_postgres_dsn)
    assert service.read(legacy.event_id, legacy.id)[0] == legacy
    runner.apply_session_suggestions_policy_v4()
    runner.apply_session_suggestions_policy_v4()
    assert constraints(render_postgres_dsn) != prior
    runner.reverse_session_suggestions_policy_v4()
    runner.reverse_session_suggestions_policy_v4()
    assert constraints(render_postgres_dsn) == prior
    assert service.read(legacy.event_id, legacy.id)[0] == legacy
    with psycopg.Connection[dict[str, Any]].connect(
        render_postgres_dsn, row_factory=dict_row,
    ) as connection:
        assert connection.execute("""SELECT 1 FROM stageflow.schema_migration
            WHERE version='0028_session_suggestions_policy_v4'""").fetchone() is None


@pytest.mark.parametrize('with_suggestion', [False, True])
def test_v4_zero_block_records_roundtrip_and_reverse_refuses(
    render_postgres_dsn: str, with_suggestion: bool,
) -> None:
    service, legacy = seeded(render_postgres_dsn)
    with service.repository.transaction(FixedClock(NOW)) as tx:
        original = tx.find_run('a' * 64)
        assert original is not None
        run = replace(original, id=EntityId.new(), input_digest='b' * 64, policy=POLICY_V4)
        candidate = CandidateV4(**{f.name: getattr(legacy.candidate, f.name)
                                   for f in fields(legacy.candidate)})
        suggestion = replace(legacy, id=EntityId.new(), run_id=run.id,
                             candidate=candidate, policy_version='4')
        tx.save_run(run, (suggestion,) if with_suggestion else ())
        assert tx.find_run(run.input_digest) == run
    restarted = SessionSuggestionService(PostgresSuggestionRepository(render_postgres_dsn),
                                          FixedClock(NOW))
    assert restarted.latest_run(run.event_id, run.stage_id) == run
    assert run.blocks == ()
    if with_suggestion:
        assert restarted.read(run.event_id, suggestion.id)[0] == suggestion
    runner = PostgresMigrationRunner(render_postgres_dsn)
    for reverse in (runner.reverse_session_suggestions_policy_v4,
                    runner.reverse_boundary_proposal_decisions):
        with pytest.raises(psycopg.Error, match='reverse_requires_empty_tables_for_v4'):
            reverse()
    with psycopg.Connection[dict[str, Any]].connect(
        render_postgres_dsn, row_factory=dict_row,
    ) as connection:
        row = connection.execute("""SELECT count(*) AS n FROM stageflow.schema_migration
            WHERE version IN ('0027_boundary_proposal_decisions',
                              '0028_session_suggestions_policy_v4')""").fetchone()
        assert row is not None and row['n'] == 2


def test_v4_service_persistence_override_and_restart_replay(
    render_postgres_dsn: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, legacy = seeded(render_postgres_dsn)
    kernel = DurableEventModeKernel(
        repository=PostgresEventModeKernelRepository(render_postgres_dsn), clock=FixedClock(NOW))
    talk = kernel.record_program_expectation(event_id=legacy.event_id, stage_id=legacy.stage_id,
                                             key='synthetic', title='Synthetic talk',
                                             planned_start=at(0), planned_end=at(1800))
    setting = service.set_offset(event_id=legacy.event_id, stage_id=legacy.stage_id,
                                 command_id=EntityId.new(), actor_id=ACTOR_ID,
                                 entries=(ScheduleOffsetEntry(at(0), 0),))
    monkeypatch.setattr(service_module, 'POLICY_VERSION', 4)
    with patch.object(PostgresSuggestionTransaction, 'snapshot',
                      return_value=InputSnapshot((talk,), (asset(0, 1800),))):
        run = service.run(event_id=legacy.event_id, stage_id=legacy.stage_id, actor_id=ACTOR_ID)
        restarted = SessionSuggestionService(PostgresSuggestionRepository(render_postgres_dsn),
                                              FixedClock(NOW))
        assert restarted.run(event_id=run.event_id, stage_id=run.stage_id, actor_id=ACTOR_ID) == run
    assert run.policy == POLICY_V4 and run.blocks == ()
    assert run.override_setting_version == setting.version
    suggestion = restarted.page(run.event_id, run.stage_id)[0][0]
    assert suggestion.policy_version == '4' and isinstance(suggestion.candidate, CandidateV4)
    assert suggestion.candidate.expectation is not None
    assert suggestion.candidate.expectation.id == talk.id
    assert suggestion.candidate.schedule_offset_source == 'producer'
    assert restarted.read(run.event_id, suggestion.id)[0] == suggestion
    assert restarted.read(legacy.event_id, legacy.id)[0] == legacy


def test_v4_migration_exact_constants_all_versions_and_offset_components(
    render_postgres_dsn: str,
) -> None:
    _, seed = seeded(render_postgres_dsn)
    with psycopg.Connection[dict[str, Any]].connect(
        render_postgres_dsn, row_factory=dict_row,
    ) as connection:
        insert = """INSERT INTO stageflow.session_suggestion_run
            (run_id, event_id, stage_id, input_digest, actor_id, created_at,
             expectation_references, asset_inputs, policy_id, policy_version, policy_constants,
             no_timing_evidence, no_segmentation, clock_implausible, no_coverage, no_planned_time)
            SELECT %s, event_id, stage_id, input_digest, actor_id, created_at,
                   expectation_references, asset_inputs, policy_id, %s, %s,
                   no_timing_evidence, no_segmentation, clock_implausible,
                   no_coverage, no_planned_time
            FROM stageflow.session_suggestion_run WHERE run_id=%s"""
        for policy in (POLICY_V1, POLICY_V2, POLICY_V3, POLICY_V4):
            constants = asdict(policy)
            run_id = EntityId.new().value
            connection.execute(insert, (run_id, policy.version,
                                        Jsonb(constants), seed.run_id.value))
            for key, value in constants.items():
                changed = {**constants, key: value + 1 if isinstance(value, (int, float))
                           else value + '-changed'}
                with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                    connection.execute(insert, (EntityId.new().value, policy.version,
                                                Jsonb(changed), seed.run_id.value))
            for other in {'1', '2', '3', '4'} - {policy.version}:
                with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                    connection.execute(insert, (EntityId.new().value, other,
                                                Jsonb(constants), seed.run_id.value))
            valid = {'suggestion_id': EntityId.new().value, 'run_id': run_id,
                     'policy_version': policy.version,
                     'schedule_offset_seconds': 0 if policy.version in ('3', '4') else None,
                     'schedule_offset_source': 'none' if policy.version in ('3', '4') else None}
            suggestion_insert = """INSERT INTO stageflow.session_suggestion
                SELECT (jsonb_populate_record(NULL::stageflow.session_suggestion,
                    to_jsonb(s) || %s::jsonb)).*
                FROM stageflow.session_suggestion s WHERE suggestion_id=%s"""
            connection.execute(suggestion_insert, (Jsonb(valid), seed.id.value))
            invalids = ([{'schedule_offset_seconds': None}, {'schedule_offset_source': None},
                         {'schedule_offset_source': 'invalid'}, {'schedule_offset_seconds': 7201},
                         {'schedule_offset_seconds': 1}, {'schedule_offset_source': 'producer'}]
                        if policy.version in ('3', '4') else
                        [{'schedule_offset_seconds': 0}, {'schedule_offset_source': 'none'}])
            for change in invalids:
                with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                    connection.execute(suggestion_insert, (Jsonb({**valid, **change,
                        'suggestion_id': EntityId.new().value}), seed.id.value))


@pytest.mark.parametrize('version', ['3', '4'])
@pytest.mark.parametrize('sign', [-1, 1])
def test_scheduled_estimated_offset_database_bound_is_version_specific(
    render_postgres_dsn: str, version: str, sign: int,
) -> None:
    service, seed = seeded(render_postgres_dsn)
    kernel = DurableEventModeKernel(
        repository=PostgresEventModeKernelRepository(render_postgres_dsn), clock=FixedClock(NOW))
    talk = kernel.record_program_expectation(event_id=seed.event_id, stage_id=seed.stage_id,
                                             key='synthetic', title='Synthetic talk',
                                             planned_start=at(0), planned_end=at(1800))
    with service.repository.transaction(FixedClock(NOW)) as tx:
        original = tx.find_run('a' * 64)
        assert original is not None
        run = replace(original, id=EntityId.new(), input_digest='b' * 64,
                      policy=POLICY_V4 if version == '4' else POLICY_V3)
        tx.save_run(run, ())
    limit = 5400 if version == '4' else 3600
    with psycopg.connect(render_postgres_dsn) as connection:
        insert = """INSERT INTO stageflow.session_suggestion
            SELECT (jsonb_populate_record(NULL::stageflow.session_suggestion,
                to_jsonb(s) || %s::jsonb)).*
            FROM stageflow.session_suggestion s WHERE suggestion_id=%s"""
        valid = {'suggestion_id': EntityId.new().value, 'run_id': run.id.value,
                 'policy_version': version, 'expectation_id': talk.id.value,
                 'expectation_revision': talk.revision,
                 'start_plan_offset_seconds': 0, 'end_plan_offset_seconds': 0, 'strength': 'medium',
                 'schedule_offset_seconds': sign * limit, 'schedule_offset_source': 'estimated'}
        connection.execute(insert, (Jsonb(valid), seed.id.value))
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            connection.execute(insert, (Jsonb({**valid, 'suggestion_id': EntityId.new().value,
                'schedule_offset_seconds': sign * (limit + 1)}), seed.id.value))
