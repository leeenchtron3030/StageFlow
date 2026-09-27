"""Real PostgreSQL qualification in a disposable, rolled-back schema."""
from dataclasses import replace
from datetime import timedelta
from typing import Any

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.contexts.editorial import (
    EditorialCandidateMoment,
    EditorialMomentReviewAction,
    EditorialMomentService,
)
from app.contexts.editorial.derivation_contracts import EditorialDerivationRun
from app.contexts.editorial.derivation_service import EditorialDerivationService
from app.contexts.production.event_mode_kernel import DurableEventModeKernel, StartSessionRequest
from app.contexts.production.media_timing_evidence import MediaTimingEvidenceApplication
from app.contexts.work_execution import TranscriptionOperationApplication
from app.infrastructure.postgres import (
    PostgresEditorialMomentRepository,
    PostgresEventModeKernelRepository,
    PostgresMediaTimingEvidenceRepository,
    PostgresMigrationRunner,
    PostgresWorkExecutionRepository,
)
from app.infrastructure.postgres.editorial_derivation_repository import (
    PostgresEditorialDerivationRepository,
    PostgresEditorialDerivationTransaction,
)
from app.shared.ids import EntityId
from app.shared.time import FixedClock
from tests.media_timing_evidence_fixtures import evidence_request
from tests.test_derived_editorial_candidates import ACTOR, NOW
from tests.test_render_work_execution import (
    render_postgres_dsn as render_postgres_dsn,
)
from tests.test_render_work_execution import (
    seed_asset,
)
from tests.test_transcription_worker_substrate import enqueue_request, operation_input


class PostgresHarness:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.event, self.asset, self.manifest = seed_asset(dsn, observed_at=NOW)
        with psycopg.Connection[dict[str, Any]].connect(dsn, row_factory=dict_row) as connection:
            row = connection.execute(
                "SELECT stage_id FROM stageflow.completed_media_asset_registry WHERE asset_id=%s",
                (self.asset.value,),
            ).fetchone()
            assert row is not None
            stage_id = EntityId(str(row["stage_id"]))
        self.session = PostgresEventModeKernelRepository(dsn).start_session(StartSessionRequest(
            operation_id=EntityId.new(), event_id=self.event, stage_id=stage_id, actor_id=ACTOR,
            authoritative_start=NOW, requested_at=NOW,
        ))
        with psycopg.Connection[dict[str, Any]].connect(dsn, row_factory=dict_row) as connection:
            connection.execute(
                """INSERT INTO stageflow.media_association
                   (asset_id, association_status, session_id, authority, reason_codes,
                    evidence_ids, actor_id, revision, decided_at, input_references,
                    policy_id, policy_version)
                   VALUES (%s, 'associated', %s, 'deterministic', '["synthetic_assignment"]',
                           '[]', %s, 1, %s, '[{"record_type":"synthetic"}]', 'synthetic', '1')""",
                (self.asset.value, self.session.id.value, ACTOR.value, NOW),
            )
        self.service = EditorialDerivationService(
            PostgresEditorialDerivationRepository(dsn), FixedClock(NOW),
        )
        self.phrase_command = EntityId.new()
        self.phrases = self.service.publish_phrase_list(
            event_id=self.event, key="test", version=1, name="Synthetic phrases",
            phrases=("silver lantern",), actor_id=ACTOR, command_id=self.phrase_command,
        )

    def transcript(self, *, status: str = "complete", count: int = 2) -> EntityId:
        evidence = EntityId.new()
        operation = replace(operation_input(), asset_id=self.asset, manifest_id=self.manifest,
                            execution_profile_version=evidence.value)
        request = replace(enqueue_request(operation), idempotency_key=evidence.value,
                          event_id=self.event)
        application = TranscriptionOperationApplication(PostgresWorkExecutionRepository(self.dsn))
        durable = application.enqueue(request)
        with psycopg.Connection[dict[str, Any]].connect(
            self.dsn, row_factory=dict_row,
        ) as connection:
            previous = connection.execute(
                """SELECT evidence_id, evidence_revision FROM stageflow.transcript_evidence_revision
                   WHERE asset_id=%s ORDER BY evidence_revision DESC LIMIT 1""",
                (self.asset.value,),
            ).fetchone()
            revision = 1 if previous is None else previous["evidence_revision"] + 1
            connection.execute(
                """INSERT INTO stageflow.transcript_evidence_revision
                   (evidence_id, operation_id, work_key, result_digest, asset_id, manifest_id,
                    manifest_version, evidence_revision, predecessor_evidence_id, evidence_status,
                    provider_id, provider_version, model_id, model_version, execution_tool_id,
                    execution_tool_version, execution_revision, produced_at, applied_at,
                    partial_reason)
                   VALUES (%s, %s, %s, %s, %s, %s, 'manifest-v1', %s, %s, %s,
                           'synthetic', '1', 'synthetic', '1', 'synthetic', '1', '1', %s, %s, %s)
                """,
                (evidence.value, durable.id.value, durable.work_key, "a" * 64, self.asset.value,
                 self.manifest.value, revision,
                 None if previous is None else previous["evidence_id"],
                 status, NOW, NOW, "synthetic_partial" if status == "partial" else None),
            )
            segment_id = EntityId.new()
            connection.execute(
                """INSERT INTO stageflow.transcript_evidence_segment
                   (evidence_id, segment_id, segment_ordinal, transcript_text,
                    asset_start_microseconds, asset_end_microseconds)
                   VALUES (%s, %s, 0, 'synthetic segment', 0, %s)""",
                (evidence.value, segment_id.value, count * 2_000_000),
            )
            for index in range(count * 2):
                connection.execute(
                    """INSERT INTO stageflow.transcript_evidence_word
                       (evidence_id, segment_id, word_id, word_ordinal, word_text,
                        asset_start_microseconds, asset_end_microseconds)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (evidence.value, segment_id.value, EntityId.new().value, index,
                     "silver" if index % 2 == 0 else "lantern", index * 1_000_000,
                     (index + 1) * 1_000_000),
                )
        return evidence

    def timing(self, *, matches: int = 1) -> EntityId:
        request = evidence_request(profile_id="synthetic-recorder", inspected_at=NOW)
        derivation = replace(request.result.derivations[0], rule_id="creation_time_plus_duration",
                             candidate_started_at=NOW + timedelta(seconds=1),
                             candidate_ended_at=NOW + timedelta(seconds=60))
        request = replace(
            request, operation_id=EntityId.new(), asset_id=self.asset, manifest_id=self.manifest,
            manifest_version="manifest-v1", result=replace(
                request.result, derivations=tuple(replace(derivation, id=EntityId.new())
                                                 for _ in range(matches)),
            ),
        )
        application = MediaTimingEvidenceApplication(
            PostgresMediaTimingEvidenceRepository(self.dsn),
        )
        return application.apply(request).id

    def derive(self, command_id: EntityId | None = None) -> EditorialDerivationRun:
        return self.service.derive_candidates(
            session_id=self.session.id, phrase_list_id=self.phrases.id, version=1,
            actor_id=ACTOR, command_id=command_id or EntityId.new(),
        )


def upstream_snapshot(dsn: str) -> dict[str, object]:
    with psycopg.Connection[dict[str, Any]].connect(dsn, row_factory=dict_row) as connection:
        return {table: connection.execute(sql.SQL(
            "SELECT to_jsonb(t) AS row FROM stageflow.{} t ORDER BY to_jsonb(t)::text",
        ).format(sql.Identifier(table))).fetchall() for table in (
            "session", "media_association", "transcript_evidence_revision",
            "transcript_evidence_segment", "transcript_evidence_word", "media_timing_evidence",
            "media_timing_observation", "media_timing_derivation", "session_completion_history",
            "session_completion_asset", "completed_media_asset_registry",
        )}


def test_postgres_reader_selection_restart_replay_review_and_no_upstream_writes(
    render_postgres_dsn: str,
) -> None:
    h = PostgresHarness(render_postgres_dsn)
    transcript = h.transcript()
    h.transcript(status="partial")
    timing = h.timing()
    before = upstream_snapshot(h.dsn)
    command = EntityId.new()
    run = h.derive(command)
    assert len(run.candidate_ids) == 2
    assert run.inputs[0].transcript_evidence_id == transcript
    assert run.inputs[0].timing is not None and run.inputs[0].timing.evidence_id == timing
    h.service = EditorialDerivationService(
        PostgresEditorialDerivationRepository(h.dsn), FixedClock(NOW),
    )
    assert h.derive(command) == h.derive() == run
    assert h.service.publish_phrase_list(
        event_id=h.event, key="test", version=1, name="Synthetic phrases",
        phrases=("silver lantern",), actor_id=ACTOR, command_id=h.phrase_command,
    ) == h.phrases
    moments = EditorialMomentService(PostgresEditorialMomentRepository(h.dsn), FixedClock(NOW))
    candidate = moments.list_for_session(h.session.id)[0]
    assert candidate.timeline_start_microseconds == 1_000_000
    assert candidate.timeline_end_microseconds == 3_000_000
    assert candidate.provenance is not None
    assert candidate.provenance.transcript_revision == 1
    assert candidate.provenance.timing_qualification == "unqualified"
    for action in EditorialMomentReviewAction:
        result = moments.review_moment(
            operation_id=EntityId.new(), actor_id=ACTOR, candidate_moment_id=candidate.id,
            expected_candidate_revision=1, action=action, reason="Synthetic human review",
            adjusted_timeline_start_microseconds=1 if action.value == "revise_range" else None,
            adjusted_timeline_end_microseconds=2 if action.value == "revise_range" else None,
        )
        assert (result.clip is not None) == (action.value == "approve_and_create_clip")
    queue = moments.list_review_queue(h.event)
    reviewed = next(item for item in queue.items if item.candidate.id == candidate.id)
    assert reviewed.candidate.provenance == candidate.provenance
    assert len(reviewed.decisions) == 4 and len(reviewed.clips) == 1
    assert upstream_snapshot(h.dsn) == before
    new_transcript = h.transcript()
    changed = h.derive()
    assert changed.id != run.id and changed.inputs[0].transcript_evidence_id == new_transcript
    assert h.derive(command) == run


def test_postgres_missing_and_ambiguous_evidence_skips_and_candidate_limit(
    render_postgres_dsn: str,
) -> None:
    h = PostgresHarness(render_postgres_dsn)
    assert h.derive().skips.no_transcript == 1
    h.transcript(count=503)
    assert h.derive().skips.no_timing_evidence == 1
    h.timing(matches=2)
    assert h.derive().skips.no_timing_evidence == 1
    h.timing()
    run = h.derive()
    assert len(run.candidate_ids) == 500 and run.skips.limit_reached == 3
    h.timing(matches=0)
    # The latest active revision does not fall back to an older usable derivation.
    assert h.derive().skips.no_timing_evidence == 1


def test_postgres_derivation_persists_and_rereads_session_end_conflicts(
    render_postgres_dsn: str,
) -> None:
    h = PostgresHarness(render_postgres_dsn)
    kernel = DurableEventModeKernel(
        repository=PostgresEventModeKernelRepository(h.dsn), clock=FixedClock(NOW),
    )
    session = kernel.correct_session_boundary(
        operation_id=EntityId.new(), session_id=h.session.id, boundary_kind="end",
        boundary_at=NOW + timedelta(seconds=2), actor_id=ACTOR, reason="Synthetic end",
    )
    h.transcript(count=2)
    h.timing()
    run = h.derive()
    assert len(run.candidate_ids) == 2
    expected = [
        (1_000_000, 3_000_000, "partially_excluded_by_session_boundary"),
        (3_000_000, 5_000_000, "excluded_by_session_boundary"),
    ]
    with psycopg.Connection[dict[str, Any]].connect(h.dsn, row_factory=dict_row) as connection:
        rows = connection.execute(
            """SELECT c.timeline_start_microseconds, c.timeline_end_microseconds,
                      h.location_conflict_reason, h.evaluated_session_revision,
                      h.session_authoritative_end
               FROM stageflow.editorial_candidate_moment c
               JOIN stageflow.editorial_candidate_moment_location_history h
                 USING (candidate_moment_id)
               WHERE c.session_id = %s ORDER BY c.timeline_start_microseconds""",
            (h.session.id.value,),
        ).fetchall()
    assert [(row["timeline_start_microseconds"], row["timeline_end_microseconds"],
             row["location_conflict_reason"]) for row in rows] == expected
    assert all(row["evaluated_session_revision"] == session.revision
               and row["session_authoritative_end"] == NOW + timedelta(seconds=2) for row in rows)
    restarted = EditorialMomentService(PostgresEditorialMomentRepository(h.dsn), FixedClock(NOW))
    candidates = restarted.list_for_session(h.session.id)
    assert {candidate.id for candidate in candidates} == set(run.candidate_ids)
    assert [(candidate.timeline_start_microseconds, candidate.timeline_end_microseconds,
             candidate.location_conflict_reason) for candidate in candidates] == expected


def test_postgres_run_rolls_back_all_editorial_writes_on_failure(
    render_postgres_dsn: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    h = PostgresHarness(render_postgres_dsn)
    h.transcript()
    h.timing()
    original = PostgresEditorialDerivationTransaction.record_command

    def fail(self: PostgresEditorialDerivationTransaction, *args: Any, **kwargs: Any) -> None:
        original(self, *args, **kwargs)
        raise RuntimeError("synthetic commit-boundary failure")

    monkeypatch.setattr(PostgresEditorialDerivationTransaction, "record_command", fail)
    with pytest.raises(RuntimeError):
        h.derive()
    with psycopg.Connection[dict[str, Any]].connect(h.dsn, row_factory=dict_row) as connection:
        for table in ("editorial_derivation_run", "editorial_candidate_moment",
                      "editorial_candidate_provenance",
                      "editorial_candidate_moment_location_history"):
            row = connection.execute(sql.SQL("SELECT count(*) AS n FROM stageflow.{}").format(
                sql.Identifier(table),
            )).fetchone()
            assert row is not None and row["n"] == 0


def test_0019_forward_reverse_reapply_preserves_declared_constraints(
    render_postgres_dsn: str,
) -> None:
    runner = PostgresMigrationRunner(render_postgres_dsn)
    runner.reverse_derived_editorial_candidates_v1()
    with psycopg.Connection[dict[str, Any]].connect(
        render_postgres_dsn, row_factory=dict_row,
    ) as connection:
        original = connection.execute("""SELECT conname, pg_get_constraintdef(oid) AS definition
            FROM pg_constraint WHERE conrelid='stageflow.editorial_candidate_moment'::regclass
            ORDER BY conname""").fetchall()
    runner.apply_derived_editorial_candidates_v1()
    runner.reverse_derived_editorial_candidates_v1()
    with psycopg.Connection[dict[str, Any]].connect(
        render_postgres_dsn, row_factory=dict_row,
    ) as connection:
        assert connection.execute("""SELECT conname, pg_get_constraintdef(oid) AS definition
            FROM pg_constraint WHERE conrelid='stageflow.editorial_candidate_moment'::regclass
            ORDER BY conname""").fetchall() == original
        # Literal 0008 expectations also catch a consistently incorrect reverse/reapply.
        checks = connection.execute("""SELECT conname, pg_get_constraintdef(oid) AS definition
            FROM pg_constraint WHERE conrelid='stageflow.editorial_candidate_moment'::regclass
            AND contype = 'c'""").fetchall()
        assert {row["conname"]: row["definition"] for row in checks} == {
            "editorial_candidate_moment_expected_session_revision_check":
                "CHECK ((expected_session_revision > 0))",
            "editorial_candidate_moment_timeline_start_microseconds_check":
                "CHECK ((timeline_start_microseconds >= 0))",
            "editorial_candidate_moment_origin_check": "CHECK ((origin = 'declared'::text))",
            "editorial_candidate_moment_epistemic_kind_check":
                "CHECK ((epistemic_kind = 'declared'::text))",
            "editorial_candidate_moment_reason_code_check":
                "CHECK ((reason_code = 'human_mark_moment'::text))",
            "editorial_candidate_moment_revision_check": "CHECK ((revision = 1))",
            "editorial_candidate_moment_check":
                "CHECK (((timeline_end_microseconds IS NULL) OR "
                "(timeline_end_microseconds >= timeline_start_microseconds)))",
            "editorial_candidate_moment_note_check":
                "CHECK (((note IS NULL) OR (btrim(note) <> ''::text)))",
            "editorial_candidate_moment_check1":
                "CHECK (((session_authoritative_end IS NULL) OR "
                "(session_authoritative_end >= session_authoritative_start)))",
        }
        columns = connection.execute("""SELECT column_name, is_nullable
            FROM information_schema.columns WHERE table_schema = 'stageflow'
            AND table_name = 'editorial_candidate_moment'""").fetchall()
        assert {row["column_name"]: row["is_nullable"] for row in columns} == {
            "candidate_moment_id": "NO", "session_id": "NO", "expected_session_revision": "NO",
            "timeline_start_microseconds": "NO", "timeline_end_microseconds": "YES",
            "session_authoritative_start": "NO", "session_authoritative_end": "YES",
            "origin": "NO", "epistemic_kind": "NO", "reason_code": "NO", "actor_id": "NO",
            "operation_id": "NO", "note": "YES", "declared_at": "NO", "revision": "NO",
        }
    runner.apply_derived_editorial_candidates_v1()
    # A phrase list alone is enough to refuse reversal, even before a run exists.
    h = PostgresHarness(render_postgres_dsn)
    with pytest.raises(psycopg.errors.RaiseException, match="cannot reverse 0019"):
        runner.reverse_derived_editorial_candidates_v1()
    h.transcript()
    h.timing()
    h.derive()
    with pytest.raises(psycopg.errors.RaiseException, match="cannot reverse 0019"):
        runner.reverse_derived_editorial_candidates_v1()


@pytest.mark.parametrize("table", [
    "editorial_phrase_list", "editorial_derivation_run", "editorial_derivation_command",
    "editorial_candidate_provenance", "editorial_candidate_moment",
])
@pytest.mark.parametrize("verb", ["UPDATE", "DELETE"])
def test_0019_records_are_immutable(render_postgres_dsn: str, table: str, verb: str) -> None:
    h = PostgresHarness(render_postgres_dsn)
    h.transcript()
    h.timing()
    h.derive()
    with pytest.raises(psycopg.errors.CheckViolation, match="immutable"):
        with psycopg.Connection[dict[str, Any]].connect(h.dsn, row_factory=dict_row) as connection:
            if verb == "DELETE":
                connection.execute(sql.SQL("DELETE FROM stageflow.{}").format(
                    sql.Identifier(table),
                ))
            else:
                column = {"editorial_phrase_list": "name",
                          "editorial_derivation_run": "input_digest",
                          "editorial_derivation_command": "request_digest",
                          "editorial_candidate_provenance": "normalized_phrase",
                          "editorial_candidate_moment": "note"}[table]
                connection.execute(sql.SQL("UPDATE stageflow.{} SET {} = {}").format(
                    sql.Identifier(table), sql.Identifier(column), sql.Identifier(column),
                ))


@pytest.mark.parametrize("invalid_provenance", [False, True])
def test_0019_declared_candidate_requires_operation_and_forbids_provenance(
    render_postgres_dsn: str, invalid_provenance: bool,
) -> None:
    h = PostgresHarness(render_postgres_dsn)
    moments = EditorialMomentService(PostgresEditorialMomentRepository(h.dsn), FixedClock(NOW))
    declared = moments.mark_moment(
        operation_id=EntityId.new(), session_id=h.session.id,
        expected_session_revision=h.session.revision, timeline_start_microseconds=0,
        actor_id=ACTOR,
    )
    if invalid_provenance:
        h.transcript()
        h.timing()
        h.derive()
        table = "editorial_candidate_provenance"
    else:
        table = "editorial_candidate_moment"
    with psycopg.Connection[dict[str, Any]].connect(h.dsn, row_factory=dict_row) as connection:
        row = connection.execute(sql.SQL("SELECT * FROM stageflow.{} LIMIT 1").format(
            sql.Identifier(table),
        )).fetchone()
        assert row is not None
    if invalid_provenance:
        row["candidate_moment_id"] = declared.id.value
    else:
        row["candidate_moment_id"] = EntityId.new().value
        row["operation_id"] = None
    with pytest.raises(psycopg.errors.CheckViolation) as error:
        with psycopg.connect(h.dsn) as connection:
            connection.execute(sql.SQL("INSERT INTO stageflow.{} ({}) VALUES ({})").format(
                sql.Identifier(table), sql.SQL(",").join(map(sql.Identifier, row)),
                sql.SQL(",").join(sql.Placeholder() for _ in row),
            ), tuple(row.values()))
    if invalid_provenance:
        assert "cannot carry derived provenance" in str(error.value)
    else:
        assert error.value.diag.constraint_name == "editorial_candidate_moment_kind_check"


@pytest.mark.parametrize("changes", [
    {"origin": "declared"}, {"epistemic_kind": "declared"}, {"reason_code": "human_mark_moment"},
    {"source_kind": "producer_declaration"}, {"operation_id": "random"}, {"revision": 2},
    {"timeline_end_microseconds": None}, {"timeline_start_microseconds": -1},
    {"timeline_end_microseconds": -1}, {},
])
def test_0019_rejects_invalid_derived_candidates_and_missing_provenance(
    render_postgres_dsn: str, changes: dict[str, object],
) -> None:
    h = PostgresHarness(render_postgres_dsn)
    h.transcript()
    h.timing()
    run = h.derive()
    with psycopg.Connection[dict[str, Any]].connect(h.dsn, row_factory=dict_row) as connection:
        row = connection.execute(
            "SELECT * FROM stageflow.editorial_candidate_moment LIMIT 1",
        ).fetchone()
        assert row is not None
    row["candidate_moment_id"] = EntityId.new().value
    row.update(changes)
    if row["operation_id"] == "random":
        row["operation_id"] = EntityId.new().value
    with pytest.raises(psycopg.errors.CheckViolation) as error:
        with psycopg.Connection[dict[str, Any]].connect(h.dsn, row_factory=dict_row) as connection:
            connection.execute(sql.SQL(
                "INSERT INTO stageflow.editorial_candidate_moment ({}) VALUES ({})",
            ).format(sql.SQL(",").join(map(sql.Identifier, row)),
                                       sql.SQL(",").join(sql.Placeholder() for _ in row)),
                               tuple(row.values()))
    if not changes:
        assert "requires matching provenance" in str(error.value)
    elif "revision" in changes:
        assert error.value.diag.constraint_name == "editorial_candidate_moment_revision_check"
    elif "timeline_start_microseconds" in changes:
        assert error.value.diag.constraint_name == (
            "editorial_candidate_moment_timeline_start_microseconds_check"
        )
    elif changes.get("timeline_end_microseconds") == -1:
        assert error.value.diag.constraint_name == "editorial_candidate_moment_check"
    else:
        assert error.value.diag.constraint_name == "editorial_candidate_moment_kind_check"
    assert h.derive() == run


@pytest.mark.parametrize(("field", "value", "constraint"), [
    ("asset_id", "new_id", "editorial_candidate_provenance_asset_id_transcript_evidence_i_fkey"),
    ("transcript_evidence_id", "new_id", None),
    ("timing_evidence_id", "new_id", None),
    ("segment_id", "new_id", None),
    ("first_word_id", "new_id", None),
    ("last_word_id", "new_id", None),
    ("run_id", "new_id", None),
    ("phrase_list_version", 2, None),
    ("transcript_revision", 2, "provenance"),
    ("timing_revision", 2, "provenance"),
    ("timing_qualification", "qualified", "provenance"),
])
def test_0019_provenance_foreign_keys_and_frozen_revisions(
    render_postgres_dsn: str, field: str, value: object, constraint: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    h = PostgresHarness(render_postgres_dsn)
    h.transcript()
    h.timing()
    original = PostgresEditorialDerivationTransaction.save_run

    def malformed(
        self: PostgresEditorialDerivationTransaction, run: EditorialDerivationRun,
        candidates: tuple[EditorialCandidateMoment, ...],
    ) -> None:
        candidate = candidates[0]
        assert candidate.provenance is not None
        changed = replace(candidate.provenance, **{
            field: EntityId.new() if value == "new_id" else value,
        })
        original(self, run, (replace(candidate, provenance=changed), *candidates[1:]))

    monkeypatch.setattr(PostgresEditorialDerivationTransaction, "save_run", malformed)
    if constraint == "provenance":
        with pytest.raises(psycopg.errors.CheckViolation, match="requires matching provenance"):
            h.derive()
    else:
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            h.derive()


@pytest.mark.parametrize(("table", "field", "value"), [
    ("editorial_phrase_list", "phrase_key", ""),
    ("editorial_phrase_list", "version", 0),
    ("editorial_phrase_list", "name", ""),
    ("editorial_phrase_list", "phrases", []),
    ("editorial_phrase_list", "phrases", ["synthetic"] * 201),
    ("editorial_derivation_run", "input_set", {}),
    ("editorial_derivation_run", "input_digest", "invalid"),
    ("editorial_derivation_run", "candidate_ids", [ACTOR.value] * 501),
    ("editorial_derivation_run", "no_transcript", -1),
    ("editorial_derivation_run", "no_timing_evidence", -1),
    ("editorial_derivation_run", "no_session_start", -1),
    ("editorial_derivation_run", "outside_session", -1),
    ("editorial_derivation_run", "limit_reached", -1),
    ("editorial_derivation_command", "request_digest", "invalid"),
    ("editorial_candidate_provenance", "normalized_phrase", ""),
    ("editorial_candidate_provenance", "transcript_revision", 0),
    ("editorial_candidate_provenance", "timing_revision", 0),
    ("editorial_candidate_provenance", "timing_qualification", "invalid"),
    ("editorial_candidate_provenance", "asset_start_microseconds", -1),
    ("editorial_candidate_provenance", "asset_end_microseconds", -1),
])
def test_0019_new_table_checks_reject_invalid_inserts(
    render_postgres_dsn: str, table: str, field: str, value: object,
) -> None:
    h = PostgresHarness(render_postgres_dsn)
    h.transcript()
    h.timing()
    h.derive()
    with psycopg.Connection[dict[str, Any]].connect(h.dsn, row_factory=dict_row) as connection:
        row = connection.execute(sql.SQL("SELECT * FROM stageflow.{} LIMIT 1").format(
            sql.Identifier(table),
        )).fetchone()
        assert row is not None
    row[field] = value
    if "input_set" in row:
        row["input_set"] = Jsonb(row["input_set"])
    with pytest.raises(psycopg.errors.CheckViolation) as error:
        with psycopg.connect(h.dsn) as connection:
            connection.execute(sql.SQL("INSERT INTO stageflow.{} ({}) VALUES ({})").format(
                sql.Identifier(table), sql.SQL(",").join(map(sql.Identifier, row)),
                sql.SQL(",").join(sql.Placeholder() for _ in row),
            ), tuple(row.values()))
    expected = (f"{table}_check" if field == "asset_end_microseconds"
                else f"{table}_{field}_check")
    assert error.value.diag.constraint_name == expected


@pytest.mark.parametrize("both_results", [True, False])
def test_0019_command_receipt_requires_exactly_one_result(
    render_postgres_dsn: str, both_results: bool,
) -> None:
    h = PostgresHarness(render_postgres_dsn)
    run = h.derive()
    with pytest.raises(psycopg.errors.CheckViolation) as error:
        with psycopg.connect(h.dsn) as connection:
            connection.execute(
                """INSERT INTO stageflow.editorial_derivation_command
                   (command_id, request_digest, phrase_list_id, phrase_list_version, run_id)
                   VALUES (%s, %s, %s, %s, %s)""",
                (EntityId.new().value, "a" * 64,
                 h.phrases.id.value if both_results else None,
                 1 if both_results else None, run.id.value if both_results else None),
            )
    assert error.value.diag.constraint_name == "editorial_derivation_command_check"
