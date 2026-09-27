from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.contexts.editorial.contracts import EditorialCandidateMoment
from app.contexts.editorial.derivation_contracts import (
    EditorialCandidateProvenance,
    EditorialDerivationInput,
    EditorialDerivationRun,
    EditorialPhraseList,
    EditorialSessionBasis,
    EditorialSkipCounts,
    EditorialTimingBasis,
    EditorialTranscriptSegment,
    EditorialTranscriptWord,
    TimingQualification,
)
from app.contexts.editorial.derivation_repository import EditorialDerivationTransaction
from app.contexts.editorial.repository import (
    EditorialMomentConflictError,
    EditorialMomentNotFoundError,
    EditorialMomentStorageUnavailableError,
)
from app.shared.ids import EntityId

type Row = dict[str, Any]


class PostgresEditorialDerivationRepository:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @contextmanager
    def transaction(self) -> Generator[EditorialDerivationTransaction]:
        try:
            with psycopg.Connection[Row].connect(self._dsn, row_factory=dict_row) as connection:
                yield PostgresEditorialDerivationTransaction(connection)
        except psycopg.OperationalError as exc:
            raise EditorialMomentStorageUnavailableError("postgresql_unavailable") from exc


class PostgresEditorialDerivationTransaction:
    """All readers and writes share the command transaction. No upstream writes."""

    def __init__(self, connection: psycopg.Connection[Row]) -> None:
        self.connection = connection

    def _lock(self, key: str) -> None:
        self.connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            ("editorial_derivation:" + key,),
        )

    def replay(
        self, command_id: EntityId, digest: str,
    ) -> EditorialPhraseList | EditorialDerivationRun | None:
        self._lock(command_id.value)
        row = self.connection.execute(
            "SELECT * FROM stageflow.editorial_derivation_command WHERE command_id = %s",
            (command_id.value,),
        ).fetchone()
        if row is None:
            return None
        if row["request_digest"] != digest:
            raise EditorialMomentConflictError("human_command_operation_id_conflict")
        if row["run_id"] is None:
            return self.phrase_list(
                EntityId(str(row["phrase_list_id"])), row["phrase_list_version"],
            )
        run = self.connection.execute(
            "SELECT * FROM stageflow.editorial_derivation_run WHERE run_id = %s",
            (row["run_id"],),
        ).fetchone()
        assert run is not None
        return _run(run)

    def record_command(
        self, command_id: EntityId, digest: str,
        result: EditorialPhraseList | EditorialDerivationRun,
    ) -> None:
        self.connection.execute(
            """INSERT INTO stageflow.editorial_derivation_command
               (command_id, request_digest, phrase_list_id, phrase_list_version, run_id)
               VALUES (%s, %s, %s, %s, %s)""",
            (command_id.value, digest,
             result.id.value if isinstance(result, EditorialPhraseList) else None,
             result.version if isinstance(result, EditorialPhraseList) else None,
             result.id.value if isinstance(result, EditorialDerivationRun) else None),
        )

    def publish(self, phrase_list: EditorialPhraseList) -> EditorialPhraseList:
        self._lock(f"phrase:{phrase_list.event_id.value}:{phrase_list.key}")
        if self.connection.execute(
            "SELECT 1 FROM stageflow.business_event WHERE event_id = %s",
            (phrase_list.event_id.value,),
        ).fetchone() is None:
            raise EditorialMomentNotFoundError("event_not_found")
        prior = self.connection.execute(
            """SELECT phrase_list_id FROM stageflow.editorial_phrase_list
               WHERE event_id = %s AND phrase_key = %s ORDER BY version LIMIT 1""",
            (phrase_list.event_id.value, phrase_list.key),
        ).fetchone()
        if prior is not None:
            phrase_list = replace(phrase_list, id=EntityId(str(prior["phrase_list_id"])))
        row = self.connection.execute(
            """INSERT INTO stageflow.editorial_phrase_list
               (phrase_list_id, event_id, phrase_key, version, name, phrases,
                created_by, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT DO NOTHING RETURNING phrase_list_id""",
            (phrase_list.id.value, phrase_list.event_id.value, phrase_list.key,
             phrase_list.version, phrase_list.name, list(phrase_list.phrases),
             phrase_list.created_by.value, phrase_list.created_at),
        ).fetchone()
        if row is None:
            raise EditorialMomentConflictError("phrase_list_version_exists")
        return phrase_list

    def phrase_list(self, phrase_list_id: EntityId, version: int) -> EditorialPhraseList:
        row = self.connection.execute(
            """SELECT * FROM stageflow.editorial_phrase_list
               WHERE phrase_list_id = %s AND version = %s""", (phrase_list_id.value, version),
        ).fetchone()
        if row is None:
            raise EditorialMomentNotFoundError("phrase_list_not_found")
        return _phrase_list(row)

    def versions(
        self, event_id: EntityId, key: str, after: int, limit: int,
    ) -> tuple[EditorialPhraseList, ...]:
        return tuple(_phrase_list(row) for row in self.connection.execute(
            """SELECT * FROM stageflow.editorial_phrase_list
               WHERE event_id = %s AND phrase_key = %s AND version > %s
               ORDER BY version LIMIT %s""", (event_id.value, key, after, limit),
        ).fetchall())

    def session_basis(self, session_id: EntityId) -> EditorialSessionBasis:
        # Serialize runs for one Session; a shared Kernel lock pins the boundary.
        self._lock("session:" + session_id.value)
        row = self.connection.execute(
            "SELECT * FROM stageflow.session WHERE session_id = %s FOR SHARE", (session_id.value,),
        ).fetchone()
        if row is None:
            raise EditorialMomentNotFoundError("session_not_found")
        return EditorialSessionBasis(session_id, EntityId(str(row["event_id"])), row["revision"],
                                     row["authoritative_start"], row["authoritative_end"])

    def associated_inputs(self, session_id: EntityId) -> tuple[EditorialDerivationInput, ...]:
        # One statement snapshot pins association and both evidence selections. A server
        # cursor bounds each fetch, without truncating the input identity of a run.
        result: list[EditorialDerivationInput] = []
        with self.connection.cursor(name="editorial_input_snapshot") as cursor:
            cursor.execute(
                """SELECT a.asset_id, t.evidence_id AS transcript_evidence_id,
                          t.evidence_revision AS transcript_revision,
                          m.evidence_id AS timing_evidence_id,
                          m.evidence_revision AS timing_revision, m.qualification_status,
                          d.candidate_started_at
                   FROM stageflow.media_association a
                   LEFT JOIN LATERAL (
                       SELECT evidence_id, evidence_revision
                       FROM stageflow.transcript_evidence_revision
                       WHERE asset_id = a.asset_id AND evidence_status = 'complete'
                       ORDER BY evidence_revision DESC LIMIT 1
                   ) t ON TRUE
                   LEFT JOIN LATERAL (
                       SELECT evidence_id, evidence_revision, qualification_status
                       FROM stageflow.media_timing_evidence WHERE asset_id = a.asset_id
                       ORDER BY evidence_revision DESC LIMIT 1
                   ) m ON TRUE
                   LEFT JOIN LATERAL (
                       SELECT min(candidate_started_at) AS candidate_started_at
                       FROM stageflow.media_timing_derivation
                       WHERE evidence_id = m.evidence_id AND rule_id = 'creation_time_plus_duration'
                       HAVING count(*) = 1
                   ) d ON TRUE
                   WHERE a.session_id = %s AND a.association_status = 'associated'
                   ORDER BY a.asset_id""", (session_id.value,),
            )
            while rows := cursor.fetchmany(100):
                for row in rows:
                    timing = None if row["candidate_started_at"] is None else EditorialTimingBasis(
                        EntityId(str(row["timing_evidence_id"])), row["timing_revision"],
                        TimingQualification(row["qualification_status"]),
                        row["candidate_started_at"],
                    )
                    result.append(EditorialDerivationInput(
                        EntityId(str(row["asset_id"])),
                        None if row["transcript_evidence_id"] is None
                        else EntityId(str(row["transcript_evidence_id"])),
                        row["transcript_revision"], timing,
                    ))
        return tuple(result)

    def transcript_segments(self, evidence_id: EntityId) -> Iterator[EditorialTranscriptSegment]:
        with self.connection.cursor(name="editorial_transcript_words") as cursor:
            cursor.execute(
                """SELECT w.* FROM stageflow.transcript_evidence_segment s
                   JOIN stageflow.transcript_evidence_word w USING (evidence_id, segment_id)
                   WHERE s.evidence_id = %s ORDER BY s.segment_ordinal, w.word_ordinal""",
                (evidence_id.value,),
            )
            segment_id: EntityId | None = None
            words: list[EditorialTranscriptWord] = []
            while rows := cursor.fetchmany(1000):
                for row in rows:
                    current = EntityId(str(row["segment_id"]))
                    if segment_id is not None and current != segment_id:
                        yield EditorialTranscriptSegment(segment_id, tuple(words))
                        words = []
                    segment_id = current
                    words.append(EditorialTranscriptWord(
                        EntityId(str(row["word_id"])), row["word_text"],
                        row["asset_start_microseconds"], row["asset_end_microseconds"],
                    ))
            if segment_id is not None:
                yield EditorialTranscriptSegment(segment_id, tuple(words))

    def find_run(self, input_digest: str) -> EditorialDerivationRun | None:
        row = self.connection.execute(
            "SELECT * FROM stageflow.editorial_derivation_run WHERE input_digest = %s",
            (input_digest,),
        ).fetchone()
        return None if row is None else _run(row)

    def save_run(
        self, run: EditorialDerivationRun, candidates: tuple[EditorialCandidateMoment, ...],
    ) -> None:
        self.connection.execute(
            """INSERT INTO stageflow.editorial_derivation_run
               (run_id, session_id, phrase_list_id, phrase_list_version, input_set, input_digest,
                created_by, created_at, candidate_ids, no_transcript, no_timing_evidence,
                no_session_start, outside_session, limit_reached)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (run.id.value, run.session_id.value, run.phrase_list_id.value, run.phrase_list_version,
             Jsonb([_input_document(item) for item in run.inputs]), run.input_digest,
             run.created_by.value, run.created_at, [item.value for item in run.candidate_ids],
             run.skips.no_transcript, run.skips.no_timing_evidence, run.skips.no_session_start,
             run.skips.outside_session, run.skips.limit_reached),
        )
        for candidate in candidates:
            self.connection.execute(
                """INSERT INTO stageflow.editorial_candidate_moment
                   (candidate_moment_id, session_id, expected_session_revision,
                    timeline_start_microseconds, timeline_end_microseconds,
                    session_authoritative_start, session_authoritative_end,
                    origin, epistemic_kind, reason_code, source_kind, actor_id, operation_id,
                    declared_at, revision)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, 'derived', 'derived',
                           'transcript_phrase_match', 'transcript_phrase_match', %s, NULL, %s, 1)
                """,
                (candidate.id.value, candidate.session_id.value,
                 candidate.expected_session_revision,
                 candidate.timeline_start_microseconds, candidate.timeline_end_microseconds,
                 candidate.session_authoritative_start, candidate.session_authoritative_end,
                 candidate.actor_id.value, candidate.declared_at),
            )
            p = candidate.provenance
            assert p is not None
            self.connection.execute(
                """INSERT INTO stageflow.editorial_candidate_provenance
                   (candidate_moment_id, run_id, phrase_list_id, phrase_list_version,
                    normalized_phrase,
                    asset_id, transcript_evidence_id, transcript_revision, segment_id,
                    first_word_id, last_word_id, asset_start_microseconds, asset_end_microseconds,
                    timing_evidence_id, timing_revision, timing_qualification)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (candidate.id.value, p.run_id.value, p.phrase_list_id.value, p.phrase_list_version,
                 p.normalized_phrase, p.asset_id.value, p.transcript_evidence_id.value,
                 p.transcript_revision, p.segment_id.value, p.first_word_id.value,
                 p.last_word_id.value, p.asset_start_microseconds, p.asset_end_microseconds,
                 p.timing_evidence_id.value, p.timing_revision, p.timing_qualification.value),
            )
            self.connection.execute(
                """INSERT INTO stageflow.editorial_candidate_moment_location_history
                   (location_evaluation_id, candidate_moment_id, evaluated_session_revision,
                    session_authoritative_start, session_authoritative_end,
                    location_conflict_reason, evaluated_at) VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (EntityId.new().value, candidate.id.value, candidate.expected_session_revision,
                 candidate.session_authoritative_start, candidate.session_authoritative_end,
                 candidate.location_conflict_reason, candidate.declared_at),
            )


def _phrase_list(row: Row) -> EditorialPhraseList:
    return EditorialPhraseList(
        EntityId(str(row["phrase_list_id"])), EntityId(str(row["event_id"])), row["phrase_key"],
        row["version"], row["name"], tuple(row["phrases"]), EntityId(str(row["created_by"])),
        row["created_at"],
    )


def _input_document(item: EditorialDerivationInput) -> Row:
    return {
        "asset_id": item.asset_id.value,
        "transcript_evidence_id": None if item.transcript_evidence_id is None
        else item.transcript_evidence_id.value,
        "transcript_revision": item.transcript_revision,
        "timing": None if item.timing is None else {
            "evidence_id": item.timing.evidence_id.value, "revision": item.timing.revision,
            "qualification": item.timing.qualification.value,
            "candidate_started_at": item.timing.candidate_started_at.isoformat(),
        },
    }


def _run(row: Row) -> EditorialDerivationRun:
    inputs: list[EditorialDerivationInput] = []
    for item in row["input_set"]:
        t = item["timing"]
        timing = None if t is None else EditorialTimingBasis(
            EntityId(t["evidence_id"]), t["revision"], TimingQualification(t["qualification"]),
            datetime.fromisoformat(t["candidate_started_at"]),
        )
        inputs.append(EditorialDerivationInput(
            EntityId(item["asset_id"]), None if item["transcript_evidence_id"] is None
            else EntityId(item["transcript_evidence_id"]), item["transcript_revision"], timing,
        ))
    return EditorialDerivationRun(
        EntityId(str(row["run_id"])), EntityId(str(row["session_id"])),
        EntityId(str(row["phrase_list_id"])), row["phrase_list_version"], tuple(inputs),
        row["input_digest"], EntityId(str(row["created_by"])), row["created_at"],
        tuple(EntityId(str(item)) for item in row["candidate_ids"]),
        EditorialSkipCounts(**{
            name: row[name] for name in EditorialSkipCounts.__dataclass_fields__
        }),
    )


def provenance_from_row(row: Row | None) -> EditorialCandidateProvenance | None:
    if row is None:
        return None
    return EditorialCandidateProvenance(
        EntityId(str(row["run_id"])), EntityId(str(row["phrase_list_id"])),
        row["phrase_list_version"],
        row["normalized_phrase"], EntityId(str(row["asset_id"])),
        EntityId(str(row["transcript_evidence_id"])), row["transcript_revision"],
        EntityId(str(row["segment_id"])), EntityId(str(row["first_word_id"])),
        EntityId(str(row["last_word_id"])),
        row["asset_start_microseconds"], row["asset_end_microseconds"],
        EntityId(str(row["timing_evidence_id"])),
        row["timing_revision"], row["timing_qualification"],
    )
