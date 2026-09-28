"""Typed timing journal and atomic application of fenced inspection results."""

import psycopg

from app.contexts.production.media_timing_evidence import (
    ApplyMediaTimingEvidenceRequest,
    MediaTimingEvidence,
    MediaTimingEvidenceApplication,
)
from app.contexts.production.media_timing_evidence.enqueue import RegisteredTimingAsset
from app.contexts.production.media_timing_evidence.worker import (
    MediaTimingResultCommitAmbiguousError,
)
from app.contexts.work_execution import (
    DurableOperation,
    MediaTimingOperationInput,
    OperationClaim,
    WorkExecutionConflictError,
    WorkExecutionStorageUnavailableError,
)
from app.shared.ids import EntityId

from .media_timing_evidence_repository import PostgresMediaTimingEvidenceRepository
from .transcription_work_repository import PostgresWorkExecutionRepository

_DEFINITE_ROLLBACK_SQLSTATES = frozenset({"40001", "40P01"})


class PostgresMediaTimingWorkRepository(
    PostgresWorkExecutionRepository[MediaTimingOperationInput],
):
    def __init__(self, dsn: str) -> None:
        super().__init__(dsn, input_types=(MediaTimingOperationInput,))

    def apply_result(
        self, claim: OperationClaim[MediaTimingOperationInput],
        request: ApplyMediaTimingEvidenceRequest,
    ) -> MediaTimingEvidence:
        value = claim.operation.input
        if (request.operation_id != claim.operation.id or request.asset_id != value.asset_id
                or request.manifest_id != value.manifest_id
                or request.manifest_version != value.manifest_version):
            raise WorkExecutionConflictError("media_timing_result_identity_conflict")
        commit_started = False
        try:
            with self._connect() as conn:
                row = conn.execute(
                    """SELECT o.*, statement_timestamp() AS database_now
                       FROM stageflow.work_operation o WHERE operation_id=%s FOR UPDATE""",
                    (claim.operation.id.value,),
                ).fetchone()
                self._assert_active_claim(row, claim)
                evidence = MediaTimingEvidenceApplication(PostgresMediaTimingEvidenceRepository(
                    self._dsn, connection=conn,
                )).apply(request)
                conn.execute(
                    """UPDATE stageflow.work_operation_attempt SET attempt_status='finalized',
                       finalized_at=statement_timestamp(), outcome='succeeded', retryable=false,
                       reason_code='result_applied',
                       diagnostic_summary='media_timing_result_applied'
                       WHERE attempt_id=%s""", (claim.attempt.id.value,),
                )
                conn.execute(
                    """UPDATE stageflow.work_operation SET operation_status='succeeded',
                       terminal_result_type='media_timing_evidence',
                       terminal_result_media_timing_evidence_id=%s,
                       current_attempt_id=NULL, lease_owner_worker_id=NULL, lease_expires_at=NULL,
                       last_reason_code=NULL, row_revision=row_revision+1,
                       updated_at=statement_timestamp() WHERE operation_id=%s""",
                    (evidence.id.value, claim.operation.id.value),
                )
                commit_started = True
                return evidence
        except (psycopg.InterfaceError, psycopg.OperationalError) as exc:
            if commit_started and exc.sqlstate not in _DEFINITE_ROLLBACK_SQLSTATES:
                raise MediaTimingResultCommitAmbiguousError(
                    "media_timing_commit_ambiguous") from None
            raise WorkExecutionStorageUnavailableError("postgresql_unavailable") from None

    def page(
        self, event_id: EntityId, *, limit: int = 50, after: EntityId | None = None,
    ) -> tuple[tuple[DurableOperation[MediaTimingOperationInput], ...], EntityId | None]:
        if not 1 <= limit <= 100:
            raise ValueError("media_timing_limit_out_of_bounds")
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """SELECT * FROM stageflow.work_operation WHERE operation_kind='media_timing'
                       AND event_id=%s AND (%s::uuid IS NULL OR operation_id>%s::uuid)
                       ORDER BY operation_id LIMIT %s""",
                    (event_id.value, None if after is None else after.value,
                     None if after is None else after.value, limit + 1),
                ).fetchall()
                items = tuple(self._operation(row, conn) for row in rows[:limit])
                return items, items[-1].id if len(rows) > limit else None
        except (psycopg.InterfaceError, psycopg.OperationalError):
            raise WorkExecutionStorageUnavailableError("postgresql_unavailable") from None

    def asset_page(
        self, event_id: EntityId, *, limit: int = 50, after: EntityId | None = None,
    ) -> tuple[tuple[RegisteredTimingAsset, ...], EntityId | None]:
        if not 1 <= limit <= 100:
            raise ValueError("media_timing_limit_out_of_bounds")
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """SELECT a.asset_id, a.manifest_id, a.registered_at
                       FROM stageflow.completed_media_asset_registry a
                       JOIN stageflow.stage s USING (stage_id)
                       WHERE s.event_id=%s AND (%s::uuid IS NULL OR a.asset_id>%s::uuid)
                       ORDER BY a.asset_id LIMIT %s""",
                    (event_id.value, None if after is None else after.value,
                     None if after is None else after.value, limit + 1),
                ).fetchall()
                items = tuple(RegisteredTimingAsset(
                    EntityId(str(row["asset_id"])), EntityId(str(row["manifest_id"])),
                    row["registered_at"],
                ) for row in rows[:limit])
                return items, items[-1].asset_id if len(rows) > limit else None
        except (psycopg.InterfaceError, psycopg.OperationalError):
            raise WorkExecutionStorageUnavailableError("postgresql_unavailable") from None

    def assets_without_operation(
        self, event_id: EntityId, *, limit: int = 100,
    ) -> tuple[RegisteredTimingAsset, ...]:
        """Bound recovery work; durable enqueues remove assets from subsequent pages."""
        if not 1 <= limit <= 100:
            raise ValueError("media_timing_limit_out_of_bounds")
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """SELECT a.asset_id, a.manifest_id, a.registered_at
                       FROM stageflow.completed_media_asset_registry a
                       JOIN stageflow.stage s USING (stage_id)
                       WHERE s.event_id=%s AND NOT EXISTS (
                           SELECT 1 FROM stageflow.work_operation o
                           WHERE o.event_id=s.event_id AND o.asset_id=a.asset_id
                             AND o.operation_kind='media_timing')
                       ORDER BY a.asset_id LIMIT %s""",
                    (event_id.value, limit),
                ).fetchall()
                return tuple(RegisteredTimingAsset(
                    EntityId(str(row["asset_id"])), EntityId(str(row["manifest_id"])),
                    row["registered_at"],
                ) for row in rows)
        except (psycopg.InterfaceError, psycopg.OperationalError):
            raise WorkExecutionStorageUnavailableError("postgresql_unavailable") from None
