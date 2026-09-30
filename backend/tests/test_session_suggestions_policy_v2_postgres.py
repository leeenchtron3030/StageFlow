"""All DDL and immutable rows live in the rolled-back PostgreSQL fixture."""
from dataclasses import asdict, fields, replace
from pathlib import Path

import psycopg
import pytest
from psycopg.types.json import Jsonb

from app.contexts.production.session_suggestions.contracts import (
    POLICY_V1,
    POLICY_V2,
    CandidateV2,
    Span,
)
from app.infrastructure.postgres.migrations import PostgresMigrationRunner
from app.shared.ids import EntityId
from app.shared.time import FixedClock
from tests.test_render_work_execution import render_postgres_dsn as render_postgres_dsn
from tests.test_session_suggestion_policy import NOW, at
from tests.test_session_suggestions_postgres import seeded


def test_forward_reverse_preserves_v1_and_v2_roundtrip_refuses_reverse(
    render_postgres_dsn: str,
) -> None:
    service, suggestion = seeded(render_postgres_dsn)
    runner = PostgresMigrationRunner(render_postgres_dsn)
    runner.reverse_session_suggestions_policy_v2()
    assert service.read(suggestion.event_id, suggestion.id)[0] == suggestion
    runner.apply_session_suggestions_policy_v2()
    runner.apply_session_suggestions_policy_v2()  # idempotent registry
    with service.repository.transaction(FixedClock(NOW)) as tx:
        original = tx.find_run("a" * 64)
        assert original is not None and original.policy == POLICY_V1
        run = replace(original, id=EntityId.new(), input_digest="b" * 64, policy=POLICY_V2)
        candidate = CandidateV2(**{f.name: getattr(suggestion.candidate, f.name)
                                   for f in fields(suggestion.candidate)})
        candidate = replace(candidate, span=Span(at(0), at(60)))
        current = replace(suggestion, id=EntityId.new(), run_id=run.id,
                          candidate=candidate, policy_version="2")
        tx.save_run(run, (current,))
        assert tx.find_run(run.input_digest) == run
    assert service.read(current.event_id, current.id)[0] == current
    assert service.read(suggestion.event_id, suggestion.id)[0] == suggestion
    with pytest.raises(psycopg.Error, match="reverse_requires_empty_tables_for_v2"):
        runner.reverse_session_suggestions_policy_v2()


def test_each_version_requires_its_exact_constants_and_suggestion_duration(
    render_postgres_dsn: str,
) -> None:
    _, seed = seeded(render_postgres_dsn)
    with psycopg.connect(render_postgres_dsn) as connection:
        # Clone only a run with new identity; FK scope and immutable history stay real.
        insert = """INSERT INTO stageflow.session_suggestion_run
            (run_id, event_id, stage_id, input_digest, actor_id, created_at,
             expectation_references, asset_inputs, policy_id, policy_version, policy_constants,
             no_timing_evidence, no_segmentation, clock_implausible, no_coverage, no_planned_time)
            SELECT %s, event_id, stage_id, input_digest, actor_id, created_at,
                   expectation_references, asset_inputs, policy_id, %s, %s,
                   no_timing_evidence, no_segmentation, clock_implausible,
                   no_coverage, no_planned_time
            FROM stageflow.session_suggestion_run WHERE run_id=%s"""
        for policy in (POLICY_V1, POLICY_V2):
            constants = asdict(policy)
            connection.execute(insert, (EntityId.new().value, policy.version,
                                        Jsonb(constants), seed.run_id.value))
            for key, value in constants.items():
                changed = dict(constants)
                changed[key] = value + 1 if isinstance(value, (int, float)) else value + "-changed"
                with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                    connection.execute(insert, (EntityId.new().value, policy.version,
                                                Jsonb(changed), seed.run_id.value))
            for version in ("2" if policy.version == "1" else "1", "3"):
                with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                    connection.execute(insert, (EntityId.new().value, version,
                                                Jsonb(constants), seed.run_id.value))
        # v1 retains >60 s, although v2 accepts exactly 60 s.
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            connection.execute("""INSERT INTO stageflow.session_suggestion
                SELECT (jsonb_populate_record(NULL::stageflow.session_suggestion,
                    to_jsonb(s) || jsonb_build_object('suggestion_id', %s::text,
                        'suggested_end', suggested_start + interval '60 seconds'))).*
                FROM stageflow.session_suggestion s WHERE suggestion_id=%s""",
                (EntityId.new().value, seed.id.value))
        # A suggestion cannot claim a different policy than its immutable run.
        with pytest.raises(psycopg.errors.ForeignKeyViolation), connection.transaction():
            connection.execute("""INSERT INTO stageflow.session_suggestion
                SELECT (jsonb_populate_record(NULL::stageflow.session_suggestion,
                    to_jsonb(s) || jsonb_build_object('suggestion_id', %s::text,
                        'policy_version', '2'))).*
                FROM stageflow.session_suggestion s WHERE suggestion_id=%s""",
                (EntityId.new().value, seed.id.value))


def test_registry_forward_reverse_order_and_sql_are_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    applied: list[str] = []

    def record(self: PostgresMigrationRunner, filename: str, *, version: str) -> None:
        path = Path(__file__).parents[1] / "app/infrastructure/postgres/sql" / filename
        assert path.is_file()
        applied.append(version)

    monkeypatch.setattr(PostgresMigrationRunner, "_execute_if_missing", record)
    monkeypatch.setattr(PostgresMigrationRunner, "_execute_if_present", record)
    runner = PostgresMigrationRunner("unused")
    runner.apply_session_suggestions_v1()
    assert applied == ["0022_session_suggestions", "0023_session_suggestions_policy_v2",
                       "0024_session_suggestions_policy_v3", "0025_boundary_cue_composition",
                       "0026_session_suggestions_already_realized"]
    applied.clear()
    runner.reverse_session_suggestions_v1()
    assert applied == ["0026_session_suggestions_already_realized",
                       "0025_boundary_cue_composition", "0024_session_suggestions_policy_v3",
                       "0023_session_suggestions_policy_v2",
                        "0022_session_suggestions"]
