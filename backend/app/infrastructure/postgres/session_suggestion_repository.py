"""Append-only suggestions and a transaction-bound, unchanged Kernel adapter."""
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timedelta
from types import TracebackType
from typing import Any, cast

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.contexts.editorial.derivation import match_phrases
from app.contexts.editorial.derivation_contracts import TimingQualification
from app.contexts.production.event_mode_kernel.contracts import (
    ProducerWorkQueuePosition,
    ProducerWorkQueueSubject,
)
from app.contexts.production.event_mode_kernel.service import DurableEventModeKernel
from app.contexts.production.media_segmentation_evidence.contracts import SegmentationInterval
from app.contexts.production.session_suggestions import serialization as serde
from app.contexts.production.session_suggestions.contracts import (
    MAX_INPUTS,
    AssetInput,
    InputSnapshot,
    Policy,
    PolicyV2,
    PolicyV3,
    PolicyV4,
    Reference,
    ScheduleBlock,
    ScheduleOffsetEntry,
    ScheduleOffsetSetting,
    ScheduleOffsetSource,
    SessionSuggestion,
    SkipCounts,
    Span,
    SuggestionConflictError,
    SuggestionDecision,
    SuggestionNotFoundError,
    SuggestionRun,
    SuggestionStatus,
    SuggestionStorageUnavailableError,
)
from app.contexts.production.session_suggestions.repository import SuggestionTransaction
from app.contexts.production.session_suggestions.service import reference_document
from app.contexts.production.session_suggestions.work_queue import (
    suggestion_work_queue_subject,
    validate_work_queue_limit,
)
from app.infrastructure.postgres.boundary_cue_repository import PostgresBoundaryCueTransaction
from app.infrastructure.postgres.boundary_proposal_repository import (
    PostgresBoundaryProposalTransaction,
)
from app.infrastructure.postgres.editorial_derivation_repository import (
    PostgresEditorialDerivationTransaction,
)
from app.infrastructure.postgres.event_mode_kernel_repository import (
    PostgresEventModeKernelRepository,
)
from app.shared.ids import EntityId
from app.shared.time import Clock

type Row = dict[str, Any]


class _BorrowedConnection:
    """Kernel methods use `with _connect()`; the enclosing suggestion owns commit."""
    def __init__(self, connection: psycopg.Connection[Row]) -> None:
        self.connection = connection

    def __enter__(self) -> psycopg.Connection[Row]:
        return self.connection

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None,
                 traceback: TracebackType | None) -> None:
        pass


class _BoundKernelRepository(PostgresEventModeKernelRepository):
    def __init__(self, connection: psycopg.Connection[Row]) -> None:
        self.connection = connection

    def _connect(self) -> psycopg.Connection[Row]:
        return cast(psycopg.Connection[Row], _BorrowedConnection(self.connection))


class PostgresSuggestionRepository:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @contextmanager
    def transaction(self, clock: Clock) -> Generator[SuggestionTransaction]:
        try:
            with psycopg.Connection[Row].connect(self._dsn, row_factory=dict_row) as connection:
                yield PostgresSuggestionTransaction(connection, clock)
        except psycopg.OperationalError as exc:
            raise SuggestionStorageUnavailableError("postgresql_unavailable") from exc


class PostgresSuggestionTransaction(
    PostgresBoundaryCueTransaction, PostgresBoundaryProposalTransaction,
):
    def __init__(self, connection: psycopg.Connection[Row], clock: Clock) -> None:
        self.connection = connection
        self.kernel = DurableEventModeKernel(
            repository=_BoundKernelRepository(connection), clock=clock)

    def _lock(self, key: str) -> None:
        self.connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                                ("session_suggestion:" + key,))

    def scope(self, event_id: EntityId, stage_id: EntityId) -> None:
        row = self.connection.execute(
            "SELECT 1 FROM stageflow.stage WHERE event_id=%s AND stage_id=%s",
            (event_id.value, stage_id.value),
        ).fetchone()
        if row is None:
            raise SuggestionNotFoundError("stage_not_found")

    def lock_event(self, event_id: EntityId) -> None:
        self._lock("event:" + event_id.value)

    def _offset(self, row: Row) -> ScheduleOffsetSetting:
        entries = self.connection.execute(
            """SELECT effective_from, offset_seconds FROM stageflow.stage_schedule_offset_entry
               WHERE event_id=%s AND stage_id=%s AND version=%s ORDER BY ordinal""",
            (row["event_id"], row["stage_id"], row["version"]),
        ).fetchall()
        return ScheduleOffsetSetting(
            EntityId(str(row["event_id"])), EntityId(str(row["stage_id"])), row["version"],
            EntityId(str(row["command_id"])), row["request_digest"], EntityId(str(row["set_by"])),
            row["set_at"], tuple(ScheduleOffsetEntry(**e) for e in entries),
        )

    def current_offset(self, event_id: EntityId, stage_id: EntityId
                       ) -> ScheduleOffsetSetting | None:
        row = self.connection.execute(
            """SELECT * FROM stageflow.stage_schedule_offset_setting
               WHERE event_id=%s AND stage_id=%s ORDER BY version DESC LIMIT 1""",
            (event_id.value, stage_id.value),
        ).fetchone()
        return None if row is None else self._offset(row)

    def replay_offset(self, command_id: EntityId, digest: str) -> ScheduleOffsetSetting | None:
        self._lock("offset_command:" + command_id.value)
        row = self.connection.execute(
            "SELECT * FROM stageflow.stage_schedule_offset_setting WHERE command_id=%s",
            (command_id.value,),
        ).fetchone()
        if row is not None and row["request_digest"] != digest:
            raise SuggestionConflictError("schedule_offset_command_id_conflict")
        return None if row is None else self._offset(row)

    def save_offset(self, setting: ScheduleOffsetSetting) -> None:
        self.connection.execute(
            """INSERT INTO stageflow.stage_schedule_offset_setting
               (event_id, stage_id, version, command_id, request_digest,
                set_by, set_at, entry_count)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (setting.event_id.value, setting.stage_id.value, setting.version,
             setting.command_id.value, setting.request_digest, setting.set_by.value,
             setting.set_at, len(setting.entries)),
        )
        for ordinal, entry in enumerate(setting.entries):
            self.connection.execute(
                """INSERT INTO stageflow.stage_schedule_offset_entry
                   (event_id, stage_id, version, ordinal, effective_from, offset_seconds)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (setting.event_id.value, setting.stage_id.value, setting.version, ordinal,
                 entry.effective_from, entry.offset_seconds),
            )

    def offset_history(self, event_id: EntityId, stage_id: EntityId, after: int,
                       limit: int) -> tuple[ScheduleOffsetSetting, ...]:
        rows = self.connection.execute(
            """SELECT * FROM stageflow.stage_schedule_offset_setting
               WHERE event_id=%s AND stage_id=%s AND version>%s ORDER BY version LIMIT %s""",
            (event_id.value, stage_id.value, after, limit),
        ).fetchall()
        return tuple(self._offset(r) for r in rows)

    def decision_scope(self, event_id: EntityId, stage_id: EntityId) -> None:
        self.lock_event(event_id)
        # Kernel starts share their actual Stage lock. Lock all Event Stages in
        # stable order because an expectation can be realized on another Stage.
        rows = self.connection.execute(
            "SELECT stage_id FROM stageflow.stage WHERE event_id=%s ORDER BY stage_id FOR UPDATE",
            (event_id.value,),
        ).fetchall()
        if all(str(row["stage_id"]) != stage_id.value for row in rows):
            raise SuggestionNotFoundError("stage_not_found")
        self.connection.execute(
            "SELECT expectation_id FROM stageflow.program_expectation WHERE event_id=%s FOR SHARE",
            (event_id.value,),
        ).fetchall()

    def snapshot(self, event_id: EntityId, stage_id: EntityId,
                 start_cues: Reference | None, end_cues: Reference | None) -> InputSnapshot:
        editorial = PostgresEditorialDerivationTransaction(self.connection)
        phrases = [None if ref is None else editorial.phrase_list(ref.id, ref.revision)
                   for ref in (start_cues, end_cues)]
        if any(p is not None and p.event_id != event_id for p in phrases):
            raise SuggestionConflictError("phrase_list_event_mismatch")
        rows = self.connection.execute(
            """SELECT a.asset_id, m.evidence_id AS timing_id,
                      m.evidence_revision AS timing_revision,
                      m.qualification_status, d.candidate_started_at, d.candidate_ended_at,
                      t.evidence_id AS transcript_id, t.evidence_revision AS transcript_revision,
                      ARRAY(SELECT evidence_id FROM stageflow.media_segmentation_evidence
                            WHERE asset_id=a.asset_id ORDER BY evidence_id) AS segmentation_ids
               FROM stageflow.completed_media_asset_registry a
               LEFT JOIN LATERAL (SELECT * FROM stageflow.media_timing_evidence
                   WHERE asset_id=a.asset_id ORDER BY evidence_revision DESC LIMIT 1) m ON TRUE
               LEFT JOIN LATERAL (SELECT min(candidate_started_at) AS candidate_started_at,
                   min(candidate_ended_at) AS candidate_ended_at
                   FROM stageflow.media_timing_derivation
                   WHERE evidence_id=m.evidence_id AND rule_id='creation_time_plus_duration'
                   HAVING count(*)=1) d ON TRUE
               LEFT JOIN LATERAL (SELECT evidence_id, evidence_revision
                   FROM stageflow.transcript_evidence_revision
                   WHERE asset_id=a.asset_id AND evidence_status='complete'
                   ORDER BY evidence_revision DESC LIMIT 1) t ON TRUE
               WHERE a.stage_id=%s ORDER BY a.asset_id LIMIT %s""",
            (stage_id.value, MAX_INPUTS + 1),
        ).fetchall()
        if len(rows) > MAX_INPUTS:
            raise SuggestionConflictError("suggestion_input_limit")
        assets: list[AssetInput] = []
        for row in rows:
            intervals = self.connection.execute(
                """SELECT kind, start_microseconds, end_microseconds, profile_id, profile_version
                   FROM stageflow.media_segmentation_interval WHERE evidence_id=ANY(%s::uuid[])
                   ORDER BY start_microseconds, kind""", (row["segmentation_ids"],),
            ).fetchall() if row["segmentation_ids"] else []
            span = None
            if (row["candidate_started_at"] is not None
                    and row["candidate_ended_at"] > row["candidate_started_at"]):
                span = Span(row["candidate_started_at"], row["candidate_ended_at"])
            cues: list[list[datetime]] = [[], []]
            if span is not None and row["transcript_id"] is not None and any(phrases):
                for segment in editorial.transcript_segments(EntityId(str(row["transcript_id"]))):
                    for i, phrase_list in enumerate(phrases):
                        if phrase_list is not None:
                            cues[i].extend(span.start + timedelta(
                                microseconds=m.first_word.asset_start_microseconds)
                                           for m in match_phrases(phrase_list, segment))
            assets.append(AssetInput(
                EntityId(str(row["asset_id"])),
                None if row["timing_id"] is None else Reference(
                    EntityId(str(row["timing_id"])), row["timing_revision"]),
                span, None if row["qualification_status"] is None
                else TimingQualification(row["qualification_status"]),
                tuple(EntityId(str(i)) for i in row["segmentation_ids"]),
                tuple(SegmentationInterval(**r) for r in intervals),
                None if row["transcript_id"] is None else Reference(
                    EntityId(str(row["transcript_id"])), row["transcript_revision"]),
                tuple(cues[0]), tuple(cues[1]),
            ))
        expectations = self.kernel.repository.list_program_expectations(event_id)
        return InputSnapshot(
            tuple(x for x in expectations if x.stage_id == stage_id), tuple(assets))

    def find_run(self, digest: str) -> SuggestionRun | None:
        row = self.connection.execute(
            """SELECT r.* FROM stageflow.session_suggestion_run r WHERE input_digest=%s
               AND run_sequence=(SELECT max(run_sequence)
                   FROM stageflow.session_suggestion_run WHERE stage_id=r.stage_id)""",
            (digest,),
        ).fetchone()
        return None if row is None else self._read_run(row)

    def latest_run(self, event_id: EntityId, stage_id: EntityId) -> SuggestionRun | None:
        row = self.connection.execute(
            """SELECT * FROM stageflow.session_suggestion_run
               WHERE event_id=%s AND stage_id=%s ORDER BY run_sequence DESC LIMIT 1""",
            (event_id.value, stage_id.value),
        ).fetchone()
        return None if row is None else self._read_run(row)

    def _read_run(self, row: Row) -> SuggestionRun:
        blocks: tuple[ScheduleBlock, ...] = ()
        if row["policy_version"] == "3":
            rows = self.connection.execute(
                """SELECT * FROM stageflow.session_suggestion_run_block
                   WHERE run_id=%s ORDER BY ordinal""",
                (row["run_id"],),
            ).fetchall()
            blocks = tuple(ScheduleBlock(
                r["ordinal"], r["first_planned_start"], r["last_planned_start"], r["talk_count"],
                r["schedule_offset_seconds"], ScheduleOffsetSource(r["schedule_offset_source"]),
                r["estimate_score_margin"], r["override_setting_version"],
            ) for r in rows)
        return _run(row, blocks)

    def list_pending_confirmations(
        self, event_id: EntityId, *, after: ProducerWorkQueuePosition | None = None,
        limit: int = 50,
    ) -> tuple[ProducerWorkQueueSubject, ...]:
        validate_work_queue_limit(limit)
        cursor_sql = ""
        parameters: list[object] = [event_id.value]
        if after is not None:
            cursor_sql = """AND (6, r.created_at, ('suggestions:' || r.stage_id::text) COLLATE "C")
                > (%s, %s, %s COLLATE "C")"""
            parameters.extend((after.priority, after.updated_at, after.projection_id))
        parameters.append(limit)
        rows = self.connection.execute(
            """SELECT r.run_id, r.event_id, r.stage_id, r.created_at,
                      count(*) AS open_count,
                      count(*) FILTER (WHERE s.strength='weak') AS weak_count
               FROM stageflow.session_suggestion_run r
               JOIN stageflow.session_suggestion s ON s.run_id=r.run_id
               WHERE r.event_id=%s
                 AND NOT EXISTS (SELECT 1 FROM stageflow.session_suggestion_run newer
                     WHERE newer.stage_id=r.stage_id AND newer.run_sequence>r.run_sequence)
                 AND NOT EXISTS (SELECT 1 FROM stageflow.session_suggestion_decision d
                     WHERE d.suggestion_id=s.suggestion_id)
               """ + cursor_sql + """
               GROUP BY r.run_id, r.event_id, r.stage_id, r.created_at
               ORDER BY r.created_at, ('suggestions:' || r.stage_id::text) COLLATE "C"
               LIMIT %s""", parameters,
        ).fetchall()
        return tuple(suggestion_work_queue_subject(
            event_id=EntityId(str(r["event_id"])), stage_id=EntityId(str(r["stage_id"])),
            run_id=EntityId(str(r["run_id"])), created_at=r["created_at"],
            open_count=r["open_count"], weak_count=r["weak_count"],
        ) for r in rows)

    def save_run(self, run: SuggestionRun, suggestions: tuple[SessionSuggestion, ...]) -> None:
        self.connection.execute(
            """INSERT INTO stageflow.session_suggestion_run
               (run_id, event_id, stage_id, input_digest, actor_id, created_at,
                expectation_references, asset_inputs, start_cue_list_id, start_cue_list_version,
                end_cue_list_id, end_cue_list_version, policy_id, policy_version, policy_constants,
                no_timing_evidence, no_segmentation, clock_implausible,
                no_coverage, no_planned_time, already_realized,
                override_setting_version, block_count, boundary_proposals_created)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (run.id.value, run.event_id.value, run.stage_id.value,
             run.input_digest, run.actor_id.value,
             run.created_at, Jsonb([reference_document(r) for r in run.expectations]),
             Jsonb([serde.asset_document(a) for a in run.assets]),
             None if run.start_cue_list is None else run.start_cue_list.id.value,
             None if run.start_cue_list is None else run.start_cue_list.revision,
             None if run.end_cue_list is None else run.end_cue_list.id.value,
             None if run.end_cue_list is None else run.end_cue_list.revision,
             run.policy.id, run.policy.version, Jsonb(asdict(run.policy)),
             *asdict(run.skips).values(), run.override_setting_version, len(run.blocks),
             run.boundary_proposals_created),
        )
        for block in run.blocks:
            self.connection.execute(
                """INSERT INTO stageflow.session_suggestion_run_block
                   (run_id, event_id, stage_id, ordinal, first_planned_start, last_planned_start,
                    talk_count, schedule_offset_seconds, schedule_offset_source,
                    estimate_score_margin, override_setting_version)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (run.id.value, run.event_id.value, run.stage_id.value, block.ordinal,
                 block.first_planned_start, block.last_planned_start, block.talk_count,
                 block.schedule_offset_seconds, block.schedule_offset_source.value,
                 block.estimate_score_margin, block.override_setting_version),
            )
        for suggestion in suggestions:
            doc = serde.candidate_document(suggestion.candidate)
            doc.update(suggestion_id=suggestion.id.value, run_id=run.id.value,
                       event_id=run.event_id.value, stage_id=run.stage_id.value,
                       policy_id=run.policy.id, policy_version=run.policy.version)
            for name in ("timing_references", "transcript_references"):
                doc[name] = Jsonb(doc[name])
            statement = sql.SQL("INSERT INTO stageflow.session_suggestion ({}) VALUES ({})").format(
                sql.SQL(",").join(map(sql.Identifier, doc)),
                sql.SQL(",").join(sql.Placeholder() for _ in doc))
            self.connection.execute(statement, tuple(doc.values()))

    def get(self, event_id: EntityId, suggestion_id: EntityId) -> SessionSuggestion:
        row = self.connection.execute(
            "SELECT * FROM stageflow.session_suggestion WHERE suggestion_id=%s AND event_id=%s",
            (suggestion_id.value, event_id.value),
        ).fetchone()
        if row is None:
            raise SuggestionNotFoundError("suggestion_not_found")
        return _suggestion(row)

    def status(self, suggestion: SessionSuggestion) -> SuggestionStatus:
        row = self.connection.execute(
            _STATUS_SQL + " WHERE s.suggestion_id=%s", (suggestion.id.value,),
        ).fetchone()
        assert row is not None
        return SuggestionStatus(row["derived_status"])

    def replay(self, command_id: EntityId, digest: str) -> SuggestionDecision | None:
        self._lock("command:" + command_id.value)
        row = self.connection.execute(
            "SELECT * FROM stageflow.session_suggestion_decision WHERE command_id=%s",
            (command_id.value,),
        ).fetchone()
        if row is not None and row["request_digest"] != digest:
            raise SuggestionConflictError("suggestion_command_id_conflict")
        return None if row is None else _decision(row)

    def save_decision(self, decision: SuggestionDecision) -> None:
        self.connection.execute(
            """INSERT INTO stageflow.session_suggestion_decision
               (command_id, request_digest, suggestion_id, actor_id, decided_at, kind, reason,
                session_id, used_start, used_end) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (decision.command_id.value, decision.request_digest, decision.suggestion_id.value,
             decision.actor_id.value, decision.decided_at, decision.kind.value, decision.reason,
             None if decision.session_id is None else decision.session_id.value,
             None if decision.used_span is None else decision.used_span.start,
             None if decision.used_span is None else decision.used_span.end),
        )

    def page(self, event_id: EntityId, stage_id: EntityId, status: SuggestionStatus,
             after: EntityId | None, limit: int) -> tuple[SessionSuggestion, ...]:
        rows = self.connection.execute(
            "SELECT * FROM (" + _STATUS_SQL + """ WHERE s.event_id=%s AND s.stage_id=%s) q
                WHERE derived_status=%s AND (%s::uuid IS NULL OR suggestion_id>%s::uuid)
                ORDER BY suggestion_id LIMIT %s""",
            (event_id.value, stage_id.value, status.value, None if after is None else after.value,
             None if after is None else after.value, limit),
        ).fetchall()
        return tuple(_suggestion(r) for r in rows)


_STATUS_SQL = """SELECT s.*, CASE
    WHEN r.run_sequence < (SELECT max(run_sequence) FROM stageflow.session_suggestion_run
                          WHERE stage_id=s.stage_id) THEN 'superseded'
    WHEN d.kind IS NOT NULL THEN d.kind ELSE 'open' END AS derived_status
    FROM stageflow.session_suggestion s JOIN stageflow.session_suggestion_run r USING(run_id)
    LEFT JOIN stageflow.session_suggestion_decision d USING(suggestion_id)"""


def _run(row: Row, blocks: tuple[ScheduleBlock, ...] = ()) -> SuggestionRun:
    return SuggestionRun(
        EntityId(str(row["run_id"])), EntityId(str(row["event_id"])),
        EntityId(str(row["stage_id"])),
        row["input_digest"], EntityId(str(row["actor_id"])), row["created_at"],
        serde.references(row["expectation_references"]),
        tuple(serde.asset(a) for a in row["asset_inputs"]),
        None if row["start_cue_list_id"] is None else Reference(
            EntityId(str(row["start_cue_list_id"])), row["start_cue_list_version"]),
        None if row["end_cue_list_id"] is None else Reference(
            EntityId(str(row["end_cue_list_id"])), row["end_cue_list_version"]),
        SkipCounts(**{k: row[k] for k in SkipCounts.__dataclass_fields__}),
        {"1": Policy, "2": PolicyV2, "3": PolicyV3, "4": PolicyV4}[row["policy_version"]](
            **row["policy_constants"]),
        blocks, row.get("override_setting_version"), row["boundary_proposals_created"],
    )


def _suggestion(row: Row) -> SessionSuggestion:
    return SessionSuggestion(EntityId(str(row["suggestion_id"])), EntityId(str(row["run_id"])),
                             EntityId(str(row["event_id"])), EntityId(str(row["stage_id"])),
                             serde.candidate(row),
                             row["policy_id"], row["policy_version"])


def _decision(row: Row) -> SuggestionDecision:
    return SuggestionDecision(EntityId(str(row["command_id"])), row["request_digest"],
                               EntityId(str(row["suggestion_id"])),
                               EntityId(str(row["actor_id"])), row["decided_at"],
                               SuggestionStatus(row["kind"]), row["reason"],
                               None if row["session_id"] is None
                               else EntityId(str(row["session_id"])),
                               None if row["used_start"] is None
                               else Span(row["used_start"], row["used_end"]))
