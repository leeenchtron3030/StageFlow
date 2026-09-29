"""Atomic fenced segmentation evidence with bounded, scoped reads."""
import psycopg

from app.contexts.production.media_segmentation_evidence.contracts import (
    MediaSegmentationEvidence,
    SegmentationInterval,
    SegmentationProfile,
    SegmentationResult,
)
from app.contexts.production.media_segmentation_evidence.enqueue import RegisteredSegmentationAsset
from app.contexts.production.media_segmentation_evidence.repository import (
    check_page,
    check_result_identity,
)
from app.contexts.production.media_segmentation_evidence.worker import (
    SegmentationResultCommitAmbiguousError,
)
from app.contexts.work_execution import (
    DurableOperation,
    MediaSegmentationOperationInput,
    OperationClaim,
    WorkExecutionStorageUnavailableError,
)
from app.shared.ids import EntityId

from .transcription_work_repository import PostgresWorkExecutionRepository, Row


class PostgresMediaSegmentationRepository(
    PostgresWorkExecutionRepository[MediaSegmentationOperationInput],
):
    def __init__(self, dsn: str) -> None:
        super().__init__(dsn, input_types=(MediaSegmentationOperationInput,))

    def apply_result(self, claim: OperationClaim[MediaSegmentationOperationInput],
                     evidence: MediaSegmentationEvidence) -> MediaSegmentationEvidence:
        check_result_identity(claim, evidence)
        commit_started = False
        try:
            with self._connect() as conn:
                row = conn.execute(
                    """SELECT o.*, statement_timestamp() AS database_now
                       FROM stageflow.work_operation o WHERE operation_id=%s FOR UPDATE""",
                    (claim.operation.id.value,)).fetchone()
                self._assert_active_claim(row, claim)
                result, profile = evidence.result, evidence.result.profile
                conn.execute(
                    """INSERT INTO stageflow.media_segmentation_evidence (
                       evidence_id, operation_id, asset_id, manifest_id, manifest_version,
                       producing_attempt_id, profile_id, profile_version, video_filter,
                       audio_filter, decode, demuxer_allowlist, duration_microseconds,
                       interval_count, ffmpeg_version, ffmpeg_sha256, inspected_at, recorded_at
                       ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (evidence.id.value, evidence.operation_id.value, evidence.asset_id.value,
                     evidence.manifest_id.value, evidence.manifest_version,
                     evidence.producing_attempt_id.value, profile.id, profile.version,
                     profile.video_filter, profile.audio_filter, profile.decode,
                     profile.demuxer_allowlist, result.duration_microseconds, len(result.intervals),
                     result.ffmpeg_version, result.ffmpeg_sha256, result.inspected_at,
                     evidence.recorded_at))
                with conn.cursor() as cursor:
                    cursor.executemany(
                        """INSERT INTO stageflow.media_segmentation_interval (
                           evidence_id, ordinal, kind, start_microseconds, end_microseconds,
                           profile_id, profile_version) VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                        [(evidence.id.value, index, item.kind, item.start_microseconds,
                          item.end_microseconds, item.profile_id, item.profile_version)
                         for index, item in enumerate(result.intervals)])
                conn.execute(
                    """UPDATE stageflow.work_operation_attempt SET attempt_status='finalized',
                       finalized_at=statement_timestamp(), outcome='succeeded', retryable=false,
                       reason_code='result_applied',
                       diagnostic_summary='media_segmentation_result_applied'
                       WHERE attempt_id=%s""", (claim.attempt.id.value,))
                conn.execute(
                    """UPDATE stageflow.work_operation SET operation_status='succeeded',
                       terminal_result_type='media_segmentation_evidence',
                       terminal_result_media_segmentation_evidence_id=%s,
                       current_attempt_id=NULL, lease_owner_worker_id=NULL, lease_expires_at=NULL,
                       last_reason_code=NULL, row_revision=row_revision+1,
                       updated_at=statement_timestamp() WHERE operation_id=%s""",
                    (evidence.id.value, claim.operation.id.value))
                commit_started = True
            return evidence
        except (psycopg.InterfaceError, psycopg.OperationalError) as exc:
            if commit_started and exc.sqlstate not in {"40001", "40P01"}:
                raise SegmentationResultCommitAmbiguousError(
                    "media_segmentation_commit_ambiguous") from None
            raise WorkExecutionStorageUnavailableError("postgresql_unavailable") from None

    def evidence_page(self, *, asset_id: EntityId | None = None,
                      session_id: EntityId | None = None, limit: int = 5,
                      after: EntityId | None = None
                      ) -> tuple[tuple[MediaSegmentationEvidence, ...], EntityId | None]:
        check_page(asset_id, session_id, limit)
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """SELECT e.* FROM stageflow.media_segmentation_evidence e
                       WHERE (%s::uuid IS NULL OR e.asset_id=%s::uuid)
                         AND (%s::uuid IS NULL OR EXISTS (
                             SELECT 1 FROM stageflow.media_association a WHERE a.asset_id=e.asset_id
                             AND a.session_id=%s::uuid AND a.association_status='associated'))
                         AND (%s::uuid IS NULL OR e.evidence_id>%s::uuid)
                       ORDER BY e.evidence_id LIMIT %s""",
                    (None if asset_id is None else asset_id.value,
                     None if asset_id is None else asset_id.value,
                     None if session_id is None else session_id.value,
                     None if session_id is None else session_id.value,
                     None if after is None else after.value,
                     None if after is None else after.value, limit+1)).fetchall()
                items = tuple(self._evidence(row, conn) for row in rows[:limit])
                return items, items[-1].id if len(rows) > limit else None
        except (psycopg.InterfaceError, psycopg.OperationalError):
            raise WorkExecutionStorageUnavailableError("postgresql_unavailable") from None

    @staticmethod
    def _evidence(row: Row, conn: psycopg.Connection[Row]) -> MediaSegmentationEvidence:
        intervals = conn.execute(
            """SELECT * FROM stageflow.media_segmentation_interval
               WHERE evidence_id=%s ORDER BY ordinal LIMIT 10000""",
            (row["evidence_id"],)).fetchall()
        return MediaSegmentationEvidence(
            EntityId(str(row["evidence_id"])), EntityId(str(row["operation_id"])),
            EntityId(str(row["asset_id"])), EntityId(str(row["manifest_id"])),
            row["manifest_version"], EntityId(str(row["producing_attempt_id"])),
            SegmentationResult(tuple(SegmentationInterval(
                item["kind"], item["start_microseconds"], item["end_microseconds"],
                item["profile_id"], item["profile_version"]) for item in intervals),
                row["duration_microseconds"], row["ffmpeg_version"], row["ffmpeg_sha256"],
                row["inspected_at"], SegmentationProfile(row["profile_id"], row["profile_version"],
                    row["video_filter"], row["audio_filter"], row["decode"],
                    row["demuxer_allowlist"])),
            row["recorded_at"])

    def page(
        self, event_id: EntityId, *, limit: int = 50, after: EntityId | None = None,
    ) -> tuple[tuple[DurableOperation[MediaSegmentationOperationInput], ...], EntityId | None]:
        if not 1 <= limit <= 100:
            raise ValueError("media_segmentation_limit_out_of_bounds")
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """SELECT * FROM stageflow.work_operation
                       WHERE operation_kind='media_segmentation'
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
    ) -> tuple[tuple[RegisteredSegmentationAsset, ...], EntityId | None]:
        if not 1 <= limit <= 100:
            raise ValueError("media_segmentation_limit_out_of_bounds")
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
                items = tuple(RegisteredSegmentationAsset(
                    EntityId(str(row["asset_id"])), EntityId(str(row["manifest_id"])),
                    row["registered_at"],
                ) for row in rows[:limit])
                return items, items[-1].asset_id if len(rows) > limit else None
        except (psycopg.InterfaceError, psycopg.OperationalError):
            raise WorkExecutionStorageUnavailableError("postgresql_unavailable") from None

    def assets_without_operation(
        self, event_id: EntityId, *, limit: int = 100,
    ) -> tuple[RegisteredSegmentationAsset, ...]:
        """Bound recovery work; durable enqueues remove assets from subsequent pages."""
        if not 1 <= limit <= 100:
            raise ValueError("media_segmentation_limit_out_of_bounds")
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """SELECT a.asset_id, a.manifest_id, a.registered_at
                       FROM stageflow.completed_media_asset_registry a
                       JOIN stageflow.stage s USING (stage_id)
                       WHERE s.event_id=%s AND NOT EXISTS (
                           SELECT 1 FROM stageflow.work_operation o
                           WHERE o.event_id=s.event_id AND o.asset_id=a.asset_id
                             AND o.operation_kind='media_segmentation')
                       ORDER BY a.asset_id LIMIT %s""",
                    (event_id.value, limit),
                ).fetchall()
                return tuple(RegisteredSegmentationAsset(
                    EntityId(str(row["asset_id"])), EntityId(str(row["manifest_id"])),
                    row["registered_at"],
                ) for row in rows)
        except (psycopg.InterfaceError, psycopg.OperationalError):
            raise WorkExecutionStorageUnavailableError("postgresql_unavailable") from None
