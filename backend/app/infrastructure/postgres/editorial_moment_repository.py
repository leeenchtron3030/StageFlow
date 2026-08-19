from __future__ import annotations

from datetime import datetime
from typing import Any, cast

import psycopg
from psycopg.rows import dict_row

from app.contexts.editorial.moments import (
    DeclareEditorialMoment,
    EditorialCandidateMoment,
    EditorialMomentConflictError,
    EditorialMomentNotFoundError,
    EditorialMomentStorageUnavailableError,
)
from app.shared.ids import EntityId

type Row = dict[str, Any]


class PostgresEditorialMomentRepository:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def _connect(self) -> psycopg.Connection[Row]:
        return psycopg.Connection[Row].connect(self._dsn, row_factory=dict_row)

    def declare(self, command: DeclareEditorialMoment) -> EditorialCandidateMoment:
        try:
            with self._connect() as connection:
                inserted = connection.execute(
                    """
                    INSERT INTO stageflow.human_command_idempotency (
                        operation_id, command_kind, request_digest, result_id, recorded_at
                    ) VALUES (%s, 'editorial_moment_declaration', %s, %s, %s)
                    ON CONFLICT (operation_id) DO NOTHING
                    RETURNING result_id
                    """,
                    (
                        command.operation_id.value,
                        command.request_digest,
                        command.candidate_moment_id.value,
                        command.declared_at,
                    ),
                ).fetchone()
                moment_id = command.candidate_moment_id
                if inserted is None:
                    replay = connection.execute(
                        """
                        SELECT command_kind, request_digest, result_id
                        FROM stageflow.human_command_idempotency
                        WHERE operation_id = %s
                        """,
                        (command.operation_id.value,),
                    ).fetchone()
                    assert replay is not None
                    if (
                        replay["command_kind"] != "editorial_moment_declaration"
                        or replay["request_digest"] != command.request_digest
                    ):
                        raise EditorialMomentConflictError(
                            "human_command_operation_id_conflict"
                        )
                    moment_id = EntityId(str(replay["result_id"]))
                    existing = connection.execute(
                        """
                        SELECT * FROM stageflow.editorial_candidate_moment
                        WHERE candidate_moment_id = %s
                        """,
                        (moment_id.value,),
                    ).fetchone()
                    assert existing is not None
                    return _moment(existing)

                session = connection.execute(
                    "SELECT * FROM stageflow.session WHERE session_id = %s FOR SHARE",
                    (command.session_id.value,),
                ).fetchone()
                if session is None:
                    raise EditorialMomentNotFoundError("session_not_found")
                if int(session["revision"]) != command.expected_session_revision:
                    raise EditorialMomentConflictError("session_revision_conflict")
                authoritative_start = cast(datetime, session["authoritative_start"])
                authoritative_end = cast(datetime | None, session["authoritative_end"])
                if authoritative_end is not None:
                    duration_microseconds = int(
                        (authoritative_end - authoritative_start).total_seconds() * 1_000_000
                    )
                    end = (
                        command.timeline_start_microseconds
                        if command.timeline_end_microseconds is None
                        else command.timeline_end_microseconds
                    )
                    if end > duration_microseconds:
                        raise EditorialMomentConflictError(
                            "moment_outside_session_boundary"
                        )
                row = connection.execute(
                    """
                    INSERT INTO stageflow.editorial_candidate_moment (
                        candidate_moment_id, session_id, expected_session_revision,
                        timeline_start_microseconds, timeline_end_microseconds,
                        session_authoritative_start, session_authoritative_end,
                        origin, epistemic_kind, reason_code, actor_id, operation_id,
                        note, declared_at, revision
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'declared', 'declared',
                              'human_mark_moment', %s, %s, %s, %s, 1)
                    RETURNING *
                    """,
                    (
                        moment_id.value,
                        command.session_id.value,
                        command.expected_session_revision,
                        command.timeline_start_microseconds,
                        command.timeline_end_microseconds,
                        authoritative_start,
                        authoritative_end,
                        command.actor_id.value,
                        command.operation_id.value,
                        command.note,
                        command.declared_at,
                    ),
                ).fetchone()
                assert row is not None
                return _moment(row)
        except psycopg.OperationalError as exc:
            raise EditorialMomentStorageUnavailableError(
                "postgresql_unavailable"
            ) from exc

    def list_for_session(
        self, session_id: EntityId, *, limit: int = 100
    ) -> tuple[EditorialCandidateMoment, ...]:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT * FROM stageflow.editorial_candidate_moment
                    WHERE session_id = %s
                    ORDER BY timeline_start_microseconds, candidate_moment_id
                    LIMIT %s
                    """,
                    (session_id.value, limit),
                ).fetchall()
                return tuple(_moment(row) for row in rows)
        except psycopg.OperationalError as exc:
            raise EditorialMomentStorageUnavailableError(
                "postgresql_unavailable"
            ) from exc


def _moment(row: Row) -> EditorialCandidateMoment:
    return EditorialCandidateMoment(
        id=EntityId(str(row["candidate_moment_id"])),
        session_id=EntityId(str(row["session_id"])),
        expected_session_revision=int(row["expected_session_revision"]),
        timeline_start_microseconds=int(row["timeline_start_microseconds"]),
        timeline_end_microseconds=cast(int | None, row["timeline_end_microseconds"]),
        session_authoritative_start=cast(datetime, row["session_authoritative_start"]),
        session_authoritative_end=cast(datetime | None, row["session_authoritative_end"]),
        actor_id=EntityId(str(row["actor_id"])),
        operation_id=EntityId(str(row["operation_id"])),
        note=cast(str | None, row["note"]),
        declared_at=cast(datetime, row["declared_at"]),
        revision=int(row["revision"]),
        origin=str(row["origin"]),
        epistemic_kind=str(row["epistemic_kind"]),
        reason_code=str(row["reason_code"]),
    )


__all__ = ["PostgresEditorialMomentRepository"]
