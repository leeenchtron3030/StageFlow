from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, cast

import psycopg
from psycopg.rows import dict_row

from app.contexts.editorial.contracts import (
    DeclareEditorialMoment,
    EditorialCandidateMoment,
    EditorialCandidateOrigin,
    EditorialClip,
    EditorialGenerationState,
    EditorialLocationConflictReason,
    EditorialMomentReviewAction,
    EditorialMomentReviewDecision,
    EditorialMomentReviewResult,
    EditorialReviewQueueItem,
    EditorialReviewQueuePage,
    EditorialReviewQueuePosition,
    EditorialReviewRange,
    EditorialReviewState,
    EditorialSessionCandidateProjection,
    ReviewEditorialMoment,
)
from app.contexts.editorial.repository import (
    EditorialMomentConflictError,
    EditorialMomentNotFoundError,
    EditorialMomentStorageUnavailableError,
)
from app.shared.ids import EntityId

type Row = dict[str, Any]

_MOMENT_SELECT = """
    SELECT moment.*,
           location.evaluated_at AS location_evaluated_at,
           location.location_conflict_reason,
           review.action AS current_review_action,
           review.decided_at AS review_decided_at
    FROM stageflow.editorial_candidate_moment AS moment
    LEFT JOIN LATERAL (
        SELECT evaluated_at, location_conflict_reason
        FROM stageflow.editorial_candidate_moment_location_history
        WHERE candidate_moment_id = moment.candidate_moment_id
        ORDER BY evaluated_session_revision DESC, evaluated_at DESC
        LIMIT 1
    ) AS location ON TRUE
    LEFT JOIN LATERAL (
        SELECT action, decided_at
        FROM stageflow.editorial_moment_review_decision
        WHERE candidate_moment_id = moment.candidate_moment_id
        ORDER BY decision_sequence DESC
        LIMIT 1
    ) AS review ON TRUE
"""


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
                        _MOMENT_SELECT + " WHERE moment.candidate_moment_id = %s",
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

    def review(
        self, command: ReviewEditorialMoment
    ) -> EditorialMomentReviewResult:
        try:
            with self._connect() as connection:
                replay = connection.execute(
                    """
                    SELECT *
                    FROM stageflow.editorial_moment_review_decision
                    WHERE operation_id = %s
                    """,
                    (command.operation_id.value,),
                ).fetchone()
                if replay is not None:
                    return _review_replay(connection, command, replay)

                candidate = connection.execute(
                    """
                    SELECT *
                    FROM stageflow.editorial_candidate_moment
                    WHERE candidate_moment_id = %s
                    FOR SHARE
                    """,
                    (command.candidate_moment_id.value,),
                ).fetchone()
                if candidate is None:
                    raise EditorialMomentNotFoundError("candidate_moment_not_found")
                candidate_revision = int(candidate["revision"])
                if candidate_revision != command.expected_candidate_revision:
                    raise EditorialMomentConflictError(
                        "candidate_revision_conflict"
                    )

                inserted = connection.execute(
                    """
                    INSERT INTO stageflow.editorial_moment_review_decision (
                        review_decision_id, operation_id, request_digest,
                        candidate_moment_id, candidate_revision, actor_id,
                        action, reason, notes,
                        adjusted_timeline_start_microseconds,
                        adjusted_timeline_end_microseconds, decided_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (operation_id) DO NOTHING
                    RETURNING *
                    """,
                    (
                        command.review_decision_id.value,
                        command.operation_id.value,
                        command.request_digest,
                        command.candidate_moment_id.value,
                        candidate_revision,
                        command.actor_id.value,
                        command.action.value,
                        command.reason,
                        command.notes,
                        (
                            None
                            if command.adjusted_range is None
                            else command.adjusted_range.timeline_start_microseconds
                        ),
                        (
                            None
                            if command.adjusted_range is None
                            else command.adjusted_range.timeline_end_microseconds
                        ),
                        command.decided_at,
                    ),
                ).fetchone()
                if inserted is None:
                    concurrent_replay = connection.execute(
                        """
                        SELECT *
                        FROM stageflow.editorial_moment_review_decision
                        WHERE operation_id = %s
                        """,
                        (command.operation_id.value,),
                    ).fetchone()
                    assert concurrent_replay is not None
                    return _review_replay(
                        connection,
                        command,
                        concurrent_replay,
                    )

                decision = _decision(inserted)
                clip: EditorialClip | None = None
                if (
                    command.action
                    is EditorialMomentReviewAction.APPROVE_AND_CREATE_CLIP
                ):
                    approved_range = command.adjusted_range
                    if approved_range is None:
                        candidate_end = cast(
                            int | None,
                            candidate["timeline_end_microseconds"],
                        )
                        if candidate_end is None:
                            raise EditorialMomentConflictError(
                                "approval_requires_timeline_range"
                            )
                        approved_range = EditorialReviewRange(
                            timeline_start_microseconds=int(
                                candidate["timeline_start_microseconds"]
                            ),
                            timeline_end_microseconds=candidate_end,
                        )
                    assert command.clip_id is not None
                    clip_row = connection.execute(
                        """
                        INSERT INTO stageflow.editorial_clip (
                            clip_id, session_id, candidate_moment_id,
                            candidate_revision, review_decision_id,
                            timeline_start_microseconds,
                            timeline_end_microseconds, created_at, revision
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1)
                        RETURNING *
                        """,
                        (
                            command.clip_id.value,
                            str(candidate["session_id"]),
                            command.candidate_moment_id.value,
                            candidate_revision,
                            decision.id.value,
                            approved_range.timeline_start_microseconds,
                            approved_range.timeline_end_microseconds,
                            command.decided_at,
                        ),
                    ).fetchone()
                    assert clip_row is not None
                    clip = _clip(clip_row)
                return EditorialMomentReviewResult(
                    decision=decision,
                    clip=clip,
                )
        except psycopg.OperationalError as exc:
            raise EditorialMomentStorageUnavailableError(
                "postgresql_unavailable"
            ) from exc

    def list_review_queue(
        self,
        event_id: EntityId,
        *,
        after: EditorialReviewQueuePosition | None = None,
        limit: int = 100,
    ) -> EditorialReviewQueuePage:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        after_priority = None if after is None else after.review_priority
        after_created_at = None if after is None else after.created_at
        after_candidate_id = (
            None if after is None else after.candidate_moment_id.value
        )
        try:
            with self._connect() as connection:
                summary = connection.execute(
                    """
                    SELECT
                        count(*) AS total_candidate_count,
                        count(*) FILTER (
                            WHERE latest.action IS NULL
                               OR latest.action IN ('revise_range', 'defer')
                        ) AS pending_candidate_count,
                        min(moment.declared_at) FILTER (
                            WHERE latest.action IS NULL
                               OR latest.action IN ('revise_range', 'defer')
                        ) AS oldest_pending_candidate_at
                    FROM stageflow.editorial_candidate_moment AS moment
                    JOIN stageflow.session AS session
                        ON session.session_id = moment.session_id
                    JOIN stageflow.stage AS stage
                        ON stage.stage_id = session.stage_id
                    LEFT JOIN LATERAL (
                        SELECT action
                        FROM stageflow.editorial_moment_review_decision
                        WHERE candidate_moment_id = moment.candidate_moment_id
                        ORDER BY decision_sequence DESC
                        LIMIT 1
                    ) AS latest ON TRUE
                    WHERE stage.event_id = %s
                    """,
                    (event_id.value,),
                ).fetchone()
                assert summary is not None
                rows = connection.execute(
                    """
                    WITH ranked AS (
                        SELECT
                            moment.candidate_moment_id,
                            moment.declared_at,
                            CASE latest.action
                                WHEN 'revise_range' THEN 1
                                WHEN 'defer' THEN 2
                                WHEN 'reject' THEN 3
                                WHEN 'approve_and_create_clip' THEN 4
                                ELSE 0
                            END AS review_priority
                        FROM stageflow.editorial_candidate_moment AS moment
                        JOIN stageflow.session AS session
                            ON session.session_id = moment.session_id
                        JOIN stageflow.stage AS stage
                            ON stage.stage_id = session.stage_id
                        LEFT JOIN LATERAL (
                            SELECT action
                            FROM stageflow.editorial_moment_review_decision
                            WHERE candidate_moment_id = moment.candidate_moment_id
                            ORDER BY decision_sequence DESC
                            LIMIT 1
                        ) AS latest ON TRUE
                        WHERE stage.event_id = %s
                    ),
                    page AS (
                        SELECT *
                        FROM ranked
                        WHERE %s::integer IS NULL
                           OR (
                                review_priority,
                                declared_at,
                                candidate_moment_id
                           ) > (%s, %s, %s)
                        ORDER BY
                            review_priority,
                            declared_at,
                            candidate_moment_id
                        LIMIT %s
                    )
                    SELECT moment.*,
                           session.stage_id,
                           stage.event_id,
                           page.review_priority,
                           location.evaluated_at AS location_evaluated_at,
                           location.location_conflict_reason,
                           latest.action AS current_review_action,
                           latest.decided_at AS review_decided_at
                    FROM page
                    JOIN stageflow.editorial_candidate_moment AS moment
                        ON moment.candidate_moment_id = page.candidate_moment_id
                    JOIN stageflow.session AS session
                        ON session.session_id = moment.session_id
                    JOIN stageflow.stage AS stage
                        ON stage.stage_id = session.stage_id
                    LEFT JOIN LATERAL (
                        SELECT evaluated_at, location_conflict_reason
                        FROM stageflow.editorial_candidate_moment_location_history
                        WHERE candidate_moment_id = moment.candidate_moment_id
                        ORDER BY evaluated_session_revision DESC, evaluated_at DESC
                        LIMIT 1
                    ) AS location ON TRUE
                    LEFT JOIN LATERAL (
                        SELECT action, decided_at
                        FROM stageflow.editorial_moment_review_decision
                        WHERE candidate_moment_id = moment.candidate_moment_id
                        ORDER BY decision_sequence DESC
                        LIMIT 1
                    ) AS latest ON TRUE
                    ORDER BY
                        page.review_priority,
                        page.declared_at,
                        page.candidate_moment_id
                    """,
                    (
                        event_id.value,
                        after_priority,
                        after_priority,
                        after_created_at,
                        after_candidate_id,
                        limit,
                    ),
                ).fetchall()
                candidate_ids = [
                    str(row["candidate_moment_id"]) for row in rows
                ]
                decisions_by_candidate = {
                    candidate_id: list[EditorialMomentReviewDecision]()
                    for candidate_id in candidate_ids
                }
                clips_by_candidate = {
                    candidate_id: list[EditorialClip]()
                    for candidate_id in candidate_ids
                }
                if candidate_ids:
                    decision_rows = connection.execute(
                        """
                        WITH ranked AS (
                            SELECT *,
                                   row_number() OVER (
                                       PARTITION BY candidate_moment_id
                                       ORDER BY decision_sequence DESC
                                   ) AS history_ordinal
                            FROM stageflow.editorial_moment_review_decision
                            WHERE candidate_moment_id = ANY(%s::uuid[])
                        )
                        SELECT *
                        FROM ranked
                        WHERE history_ordinal <= 101
                        ORDER BY candidate_moment_id, history_ordinal
                        """,
                        (candidate_ids,),
                    ).fetchall()
                    for row in decision_rows:
                        decisions_by_candidate[
                            str(row["candidate_moment_id"])
                        ].append(_decision(row))
                    clip_rows = connection.execute(
                        """
                        WITH ranked AS (
                            SELECT *,
                                   row_number() OVER (
                                       PARTITION BY candidate_moment_id
                                       ORDER BY created_at DESC, clip_id DESC
                                   ) AS history_ordinal
                            FROM stageflow.editorial_clip
                            WHERE candidate_moment_id = ANY(%s::uuid[])
                        )
                        SELECT *
                        FROM ranked
                        WHERE history_ordinal <= 101
                        ORDER BY candidate_moment_id, history_ordinal
                        """,
                        (candidate_ids,),
                    ).fetchall()
                    for row in clip_rows:
                        clips_by_candidate[
                            str(row["candidate_moment_id"])
                        ].append(_clip(row))
                items = tuple(
                    EditorialReviewQueueItem(
                        event_id=EntityId(str(row["event_id"])),
                        stage_id=EntityId(str(row["stage_id"])),
                        candidate=_moment(row),
                        decisions=tuple(
                            reversed(
                                decisions_by_candidate[
                                    str(row["candidate_moment_id"])
                                ][:100]
                            )
                        ),
                        clips=tuple(
                            reversed(
                                clips_by_candidate[
                                    str(row["candidate_moment_id"])
                                ][:100]
                            )
                        ),
                        review_priority=int(row["review_priority"]),
                        history_truncated=(
                            len(
                                decisions_by_candidate[
                                    str(row["candidate_moment_id"])
                                ]
                            )
                            > 100
                            or len(
                                clips_by_candidate[
                                    str(row["candidate_moment_id"])
                                ]
                            )
                            > 100
                        ),
                    )
                    for row in rows
                )
                return EditorialReviewQueuePage(
                    event_id=event_id,
                    items=items,
                    total_candidate_count=int(
                        summary["total_candidate_count"]
                    ),
                    pending_candidate_count=int(
                        summary["pending_candidate_count"]
                    ),
                    oldest_pending_candidate_at=cast(
                        datetime | None,
                        summary["oldest_pending_candidate_at"],
                    ),
                )
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
                    _MOMENT_SELECT
                    + """
                    WHERE moment.session_id = %s
                    ORDER BY moment.timeline_start_microseconds,
                             moment.candidate_moment_id
                    LIMIT %s
                    """,
                    (session_id.value, limit),
                ).fetchall()
                return tuple(_moment(row) for row in rows)
        except psycopg.OperationalError as exc:
            raise EditorialMomentStorageUnavailableError(
                "postgresql_unavailable"
            ) from exc

    def projection_for_session(
        self, session_id: EntityId
    ) -> EditorialSessionCandidateProjection:
        return self.projections_for_sessions((session_id,))[0]

    def projections_for_sessions(
        self, session_ids: tuple[EntityId, ...]
    ) -> tuple[EditorialSessionCandidateProjection, ...]:
        if not session_ids:
            return ()
        if len(session_ids) > 500:
            raise ValueError("at most 500 Session projections may be requested")
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    WITH requested AS (
                        SELECT session_id, ordinal
                        FROM unnest(%s::uuid[]) WITH ORDINALITY
                            AS value(session_id, ordinal)
                    )
                    SELECT requested.session_id,
                           count(moment.candidate_moment_id) AS candidate_count,
                           max(
                               greatest(
                                   moment.declared_at,
                                   coalesce(location.evaluated_at, moment.declared_at),
                                   coalesce(review.decided_at, moment.declared_at)
                               )
                           ) AS latest_candidate_activity_at,
                           count(moment.candidate_moment_id) FILTER (
                               WHERE location.location_conflict_reason IS NOT NULL
                           ) AS location_conflict_count
                    FROM requested
                    LEFT JOIN stageflow.editorial_candidate_moment AS moment
                        ON moment.session_id = requested.session_id
                    LEFT JOIN LATERAL (
                        SELECT evaluated_at, location_conflict_reason
                        FROM stageflow.editorial_candidate_moment_location_history
                        WHERE candidate_moment_id = moment.candidate_moment_id
                        ORDER BY evaluated_session_revision DESC, evaluated_at DESC
                        LIMIT 1
                    ) AS location ON TRUE
                    LEFT JOIN LATERAL (
                        SELECT decided_at
                        FROM stageflow.editorial_moment_review_decision
                        WHERE candidate_moment_id = moment.candidate_moment_id
                        ORDER BY decision_sequence DESC
                        LIMIT 1
                    ) AS review ON TRUE
                    GROUP BY requested.session_id, requested.ordinal
                    ORDER BY requested.ordinal
                    """,
                    ([item.value for item in session_ids],),
                ).fetchall()
                return tuple(
                    EditorialSessionCandidateProjection(
                        session_id=EntityId(str(row["session_id"])),
                        candidate_count=int(row["candidate_count"]),
                        latest_candidate_activity_at=cast(
                            datetime | None, row["latest_candidate_activity_at"]
                        ),
                        generation_state=EditorialGenerationState.HEALTHY,
                        location_conflict_count=int(row["location_conflict_count"]),
                    )
                    for row in rows
                )
        except psycopg.OperationalError as exc:
            raise EditorialMomentStorageUnavailableError(
                "postgresql_unavailable"
            ) from exc

    def revalidate_session_locations(
        self, session_id: EntityId, *, evaluated_at: datetime
    ) -> tuple[EditorialCandidateMoment, ...]:
        try:
            with self._connect() as connection:
                session = connection.execute(
                    "SELECT * FROM stageflow.session WHERE session_id = %s FOR SHARE",
                    (session_id.value,),
                ).fetchone()
                if session is None:
                    raise EditorialMomentNotFoundError("session_not_found")
                candidates = connection.execute(
                    """
                    SELECT * FROM stageflow.editorial_candidate_moment
                    WHERE session_id = %s
                    ORDER BY timeline_start_microseconds, candidate_moment_id
                    """,
                    (session_id.value,),
                ).fetchall()
                for candidate in candidates:
                    reason = _location_conflict_reason(candidate, session)
                    connection.execute(
                        """
                        INSERT INTO stageflow.editorial_candidate_moment_location_history (
                            location_evaluation_id, candidate_moment_id,
                            evaluated_session_revision, session_authoritative_start,
                            session_authoritative_end, location_conflict_reason,
                            evaluated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (
                            candidate_moment_id, evaluated_session_revision
                        ) DO NOTHING
                        """,
                        (
                            EntityId.new().value,
                            str(candidate["candidate_moment_id"]),
                            int(session["revision"]),
                            cast(datetime, session["authoritative_start"]),
                            cast(datetime | None, session["authoritative_end"]),
                            None if reason is None else reason.value,
                            evaluated_at,
                        ),
                    )
                rows = connection.execute(
                    _MOMENT_SELECT
                    + """
                    WHERE moment.session_id = %s
                    ORDER BY moment.timeline_start_microseconds,
                             moment.candidate_moment_id
                    """,
                    (session_id.value,),
                ).fetchall()
                return tuple(_moment(row) for row in rows)
        except psycopg.OperationalError as exc:
            raise EditorialMomentStorageUnavailableError(
                "postgresql_unavailable"
            ) from exc


def _moment(row: Row) -> EditorialCandidateMoment:
    current_review_action = row.get("current_review_action")
    review_state = (
        EditorialReviewState.UNREVIEWED
        if current_review_action is None
        else EditorialMomentReviewAction(
            str(current_review_action)
        ).projected_state
    )
    activity_times = (
        cast(datetime | None, row.get("location_evaluated_at")),
        cast(datetime | None, row.get("review_decided_at")),
    )
    updated_at = max(
        (
            cast(datetime, row["declared_at"]),
            *(item for item in activity_times if item is not None),
        )
    )
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
        origin=EditorialCandidateOrigin(str(row["origin"])),
        epistemic_kind=EditorialCandidateOrigin(str(row["epistemic_kind"])),
        reason_code=str(row["reason_code"]),
        review_state=review_state,
        updated_at=updated_at,
        location_conflict_reason=(
            None
            if row.get("location_conflict_reason") is None
            else EditorialLocationConflictReason(
                str(row["location_conflict_reason"])
            )
        ),
    )


def _decision(row: Row) -> EditorialMomentReviewDecision:
    adjusted_start = cast(
        int | None,
        row["adjusted_timeline_start_microseconds"],
    )
    adjusted_end = cast(
        int | None,
        row["adjusted_timeline_end_microseconds"],
    )
    adjusted_range = (
        None
        if adjusted_start is None
        else EditorialReviewRange(
            timeline_start_microseconds=adjusted_start,
            timeline_end_microseconds=cast(int, adjusted_end),
        )
    )
    return EditorialMomentReviewDecision(
        id=EntityId(str(row["review_decision_id"])),
        sequence=int(row["decision_sequence"]),
        operation_id=EntityId(str(row["operation_id"])),
        candidate_moment_id=EntityId(str(row["candidate_moment_id"])),
        candidate_revision=int(row["candidate_revision"]),
        actor_id=EntityId(str(row["actor_id"])),
        action=EditorialMomentReviewAction(str(row["action"])),
        reason=str(row["reason"]),
        notes=cast(str | None, row["notes"]),
        adjusted_range=adjusted_range,
        decided_at=cast(datetime, row["decided_at"]),
    )


def _clip(row: Row) -> EditorialClip:
    return EditorialClip(
        id=EntityId(str(row["clip_id"])),
        session_id=EntityId(str(row["session_id"])),
        candidate_moment_id=EntityId(str(row["candidate_moment_id"])),
        candidate_revision=int(row["candidate_revision"]),
        review_decision_id=EntityId(str(row["review_decision_id"])),
        approved_range=EditorialReviewRange(
            timeline_start_microseconds=int(
                row["timeline_start_microseconds"]
            ),
            timeline_end_microseconds=int(row["timeline_end_microseconds"]),
        ),
        created_at=cast(datetime, row["created_at"]),
        revision=int(row["revision"]),
    )


def _review_replay(
    connection: psycopg.Connection[Row],
    command: ReviewEditorialMoment,
    row: Row,
) -> EditorialMomentReviewResult:
    if str(row["request_digest"]) != command.request_digest:
        raise EditorialMomentConflictError(
            "human_command_operation_id_conflict"
        )
    decision = _decision(row)
    clip_row = connection.execute(
        """
        SELECT *
        FROM stageflow.editorial_clip
        WHERE review_decision_id = %s
        """,
        (decision.id.value,),
    ).fetchone()
    return EditorialMomentReviewResult(
        decision=decision,
        clip=None if clip_row is None else _clip(clip_row),
    )


def _location_conflict_reason(
    candidate: Row, session: Row
) -> EditorialLocationConflictReason | None:
    basis_start = cast(datetime, candidate["session_authoritative_start"])
    start = basis_start + timedelta(
        microseconds=int(candidate["timeline_start_microseconds"])
    )
    timeline_end = cast(int | None, candidate["timeline_end_microseconds"])
    end = basis_start + timedelta(
        microseconds=(
            int(candidate["timeline_start_microseconds"])
            if timeline_end is None
            else timeline_end
        )
    )
    authoritative_start = cast(datetime, session["authoritative_start"])
    authoritative_end = cast(datetime | None, session["authoritative_end"])
    if end < authoritative_start or (
        authoritative_end is not None and start > authoritative_end
    ):
        return EditorialLocationConflictReason.EXCLUDED
    if start < authoritative_start or (
        authoritative_end is not None and end > authoritative_end
    ):
        return EditorialLocationConflictReason.PARTIALLY_EXCLUDED
    return None


__all__ = ["PostgresEditorialMomentRepository"]
