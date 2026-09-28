"""Rendering over the shared lease journal and existing Assembly authority."""
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import LiteralString

import psycopg

from app.contexts.assembly.contracts import (
    ApprovalState,
    CompletedMediaAssetContent,
    ExternalContent,
)
from app.contexts.assembly.resolution import is_stale
from app.contexts.assembly.session_contracts import SessionAssembly
from app.contexts.rendering.contracts import (
    RENDER_PRESETS,
    FFmpegIdentity,
    RenderAdjustments,
    RenderedOutput,
    RenderError,
    RenderPlan,
    RenderProfile,
    RenderReason,
    VideoInput,
    effective_profile,
    render_preset,
)
from app.contexts.rendering.planning import build_render_plan
from app.contexts.rendering.service import RenderResultCommitAmbiguousError
from app.contexts.rendering.settings import ChooseRenderSetting, EventRenderSetting
from app.contexts.work_execution import (
    DurableOperation,
    OperationClaim,
    PendingOperation,
    RenderOperationInput,
    WorkerCapability,
    WorkExecutionConflictError,
    WorkExecutionNotFoundError,
    WorkExecutionStorageUnavailableError,
)
from app.shared.ids import EntityId

from .session_assembly_repository import PostgresSessionAssemblyRepository
from .transcription_work_repository import (
    PostgresWorkExecutionRepository,
    Row,
)

_DEFINITE_ROLLBACK_SQLSTATES = frozenset({"40001", "40P01"})


class PostgresRenderRepository(PostgresWorkExecutionRepository[RenderOperationInput]):
    def __init__(self, dsn: str) -> None:
        super().__init__(dsn, input_types=(RenderOperationInput,))
        self.assembly = PostgresSessionAssemblyRepository(dsn)

    def register_render_capability(self, capability: WorkerCapability) -> WorkerCapability:
        """Current preset declarations, including unavailable GPU observations."""
        if (capability.operation_kind != "render" or capability.effective_until is not None
                or capability.accepted_asset_formats is not None
                or capability.supports_word_timing or capability.supports_speaker_labels):
            raise WorkExecutionConflictError("render_capability_invalid")
        with self._connect() as conn:
            worker = conn.execute(
                "SELECT worker_id FROM stageflow.work_worker WHERE worker_id=%s FOR UPDATE",
                (capability.worker_id.value,),
            ).fetchone()
            if worker is None:
                raise WorkExecutionNotFoundError("worker_not_found")
            current = capability
            conn.execute(
                """UPDATE stageflow.work_worker_capability SET effective_until=%s
                   WHERE worker_id=%s AND operation_kind='render' AND effective_until IS NULL
                     AND (execution_profile_id=%s OR NOT (execution_profile_id=ANY(%s)))""",
                (current.effective_from, current.worker_id.value, current.execution_profile_id,
                 [preset.profile.id for preset in RENDER_PRESETS]),
            )
            conn.execute(
                """INSERT INTO stageflow.work_worker_capability
                   (capability_id,worker_id,operation_kind,operation_schema_version,
                    execution_profile_id,execution_profile_version,locality,accepted_asset_formats,
                    supports_word_timing,supports_speaker_labels,provider_id,provider_version,
                    model_id,model_version,runtime_id,runtime_version,configured_eligible,
                    effective_from,effective_until)
                   VALUES (%s,%s,'render',%s,%s,%s,%s,NULL,false,false,NULL,NULL,NULL,NULL,
                           %s,%s,%s,%s,NULL)""",
                (current.id.value, current.worker_id.value, current.operation_schema_version,
                 current.execution_profile_id, current.execution_profile_version,
                 current.locality.value, current.runtime_id, current.runtime_version,
                 current.configured_eligible, current.effective_from),
            )
            return current

    def request(self, pending: PendingOperation[RenderOperationInput]) -> DurableOperation[
        RenderOperationInput
    ]:
        return self.enqueue(pending)

    def request_at_setting(
        self, event_id: EntityId, command_id: EntityId,
        build: Callable[[EventRenderSetting | None], PendingOperation[RenderOperationInput]],
    ) -> DurableOperation[RenderOperationInput]:
        try:
            with self._connect() as conn:
                self._lock_setting(conn, event_id)
                # Resolve a recorded command against its frozen setting before checking
                # optimistic concurrency: a lost response must remain safely replayable.
                old = conn.execute(
                    """SELECT i.event_render_setting_version FROM stageflow.work_operation o
                       JOIN stageflow.render_operation_input i USING (operation_id)
                       WHERE o.operation_id=%s AND o.event_id=%s""",
                    (command_id.value, event_id.value),
                ).fetchone()
                if old is not None:
                    row = conn.execute(
                        "SELECT * FROM stageflow.event_render_setting "
                        "WHERE event_id=%s AND version=%s",
                        (event_id.value, old["event_render_setting_version"]),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT * FROM stageflow.event_render_setting WHERE event_id=%s "
                        "ORDER BY version DESC LIMIT 1", (event_id.value,),
                    ).fetchone()
                return self._enqueue(conn, build(None if row is None else _setting(row)))
        except (psycopg.InterfaceError, psycopg.OperationalError):
            raise WorkExecutionStorageUnavailableError("postgresql_unavailable") from None

    def _lock_setting(self, conn: psycopg.Connection[Row], event_id: EntityId) -> None:
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 20))", (event_id.value,))
        if conn.execute("SELECT 1 FROM stageflow.business_event WHERE event_id=%s",
                        (event_id.value,)).fetchone() is None:
            raise WorkExecutionNotFoundError("event_not_found")

    def choose_setting(self, command: ChooseRenderSetting, now: datetime) -> EventRenderSetting:
        try:
            with self._connect() as conn:
                conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 21))",
                             (command.command_id.value,))
                old = conn.execute(
                    "SELECT * FROM stageflow.event_render_setting WHERE command_id=%s",
                    (command.command_id.value,),
                ).fetchone()
                if old is not None:
                    if old["request_digest"] != command.digest:
                        raise WorkExecutionConflictError("render_setting_command_conflict")
                    return _setting(old)
                self._lock_setting(conn, command.event_id)
                current = conn.execute(
                    "SELECT max(version) AS version FROM stageflow.event_render_setting "
                    "WHERE event_id=%s", (command.event_id.value,),
                ).fetchone()
                version = current["version"] if current else None
                if version != command.expected_version:
                    raise RenderError(RenderReason.SETTING_CHANGED)
                value = EventRenderSetting(command.event_id, (version or 0) + 1,
                    command.profile_id, command.profile_version, command.adjustments,
                    command.command_id, command.digest, command.actor.id, now)
                conn.execute(
                    """INSERT INTO stageflow.event_render_setting
                       (event_id,version,render_profile_id,render_profile_version,
                        video_bit_rate,audio_bit_rate,command_id,request_digest,selected_by,selected_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (value.event_id.value, value.version, value.profile_id, value.profile_version,
                     value.adjustments.video_bit_rate, value.adjustments.audio_bit_rate,
                     value.command_id.value, value.request_digest, value.selected_by.value,
                     value.selected_at),
                )
                return value
        except (psycopg.InterfaceError, psycopg.OperationalError):
            raise WorkExecutionStorageUnavailableError("postgresql_unavailable") from None

    def setting_history(self, event_id: EntityId) -> tuple[EventRenderSetting, ...]:
        try:
            with self._connect() as conn:
                if conn.execute("SELECT 1 FROM stageflow.business_event WHERE event_id=%s",
                                (event_id.value,)).fetchone() is None:
                    raise WorkExecutionNotFoundError("event_not_found")
                rows = conn.execute(
                    "SELECT * FROM stageflow.event_render_setting WHERE event_id=%s "
                    "ORDER BY version DESC", (event_id.value,),
                ).fetchall()
                return tuple(_setting(row) for row in rows)
        except (psycopg.InterfaceError, psycopg.OperationalError):
            raise WorkExecutionStorageUnavailableError("postgresql_unavailable") from None

    def event_for_revision(self, revision_id: EntityId) -> EntityId:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT event_id FROM stageflow.assembly_revision WHERE revision_id=%s",
                    (revision_id.value,),
                ).fetchone()
                if row is None:
                    raise WorkExecutionNotFoundError("assembly_revision_not_found")
                return EntityId(str(row["event_id"]))
        except (psycopg.InterfaceError, psycopg.OperationalError):
            raise WorkExecutionStorageUnavailableError("postgresql_unavailable") from None

    def _validate_new_operation(
        self, connection: psycopg.Connection[Row], pending: PendingOperation[RenderOperationInput],
    ) -> None:
        value = pending.request.input
        profile = effective_profile(render_preset(value.execution_profile_id,
                                                  value.execution_profile_version),
                                    RenderAdjustments(value.video_bit_rate, value.audio_bit_rate))
        plan = self._plan(connection, value.assembly_revision_id, profile, lock=True)
        if plan.revision.event_id != pending.request.event_id:
            raise WorkExecutionConflictError("render_event_conflict")

    def load_plan(self, revision_id: EntityId, profile: RenderProfile) -> RenderPlan:
        try:
            with self._connect() as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                return self._plan(conn, revision_id, profile, lock=False)
        except (psycopg.InterfaceError, psycopg.OperationalError):
            raise WorkExecutionStorageUnavailableError("postgresql_unavailable") from None

    def _plan(
        self, conn: psycopg.Connection[Row], revision_id: EntityId, profile: RenderProfile,
        *, lock: bool,
    ) -> RenderPlan:
        revision, current = self.assembly.read_render_source(conn, revision_id, lock=lock)
        # Session locking matches proposal, completion, override and approval commands.
        # Packaging locks match approval/revocation and precede reading their current state.
        if lock:
            conn.execute("""SELECT packaging_asset_id FROM stageflow.packaging_asset
                            WHERE event_id=%s ORDER BY packaging_asset_id FOR SHARE""",
                         (revision.event_id.value,)).fetchall()
        decision = conn.execute(
            """SELECT action FROM stageflow.assembly_approval_decision
               WHERE revision_id=%s ORDER BY sequence DESC LIMIT 1""", (revision_id.value,),
        ).fetchone()
        packaging: dict[EntityId, VideoInput] = {}
        approved: set[EntityId] = set()
        for binding in revision.bindings:
            if binding.packaging_revision_id is None:
                continue
            row = conn.execute(
                """SELECT r.*, d.action FROM stageflow.packaging_asset_revision r
                   LEFT JOIN LATERAL (SELECT action FROM stageflow.packaging_asset_approval_decision
                     WHERE packaging_asset_id=r.packaging_asset_id
                       AND revision_number=r.revision_number
                     ORDER BY decision_sequence DESC LIMIT 1) d ON TRUE
                   WHERE r.revision_id=%s""", (binding.packaging_revision_id.value,),
            ).fetchone()
            if row is None:
                raise WorkExecutionNotFoundError("packaging_revision_not_found")
            if row["action"] == "approve":
                approved.add(binding.packaging_revision_id)
            if row["content_kind"] == "external_content":
                reference = ExternalContent(row["content_key"], row["sha256"], row["byte_size"],
                                            row["media_type"])
                packaging[binding.packaging_revision_id] = VideoInput(reference, row["media_type"])
            else:
                packaging[binding.packaging_revision_id] = self._media(
                    conn, EntityId(str(row["completed_media_asset_id"])),
                )
        state = ApprovalState.APPROVED if decision and decision["action"] == "approve" else (
            ApprovalState.UNREVIEWED
        )
        stale = is_stale(revision, current.package_revision, frozenset(approved), current.metadata)
        assembly = SessionAssembly(revision, revision.revision_number, stale, state, 0, None)
        return build_render_plan(assembly, profile, packaging, {
            m.asset_id: self._media(conn, m.asset_id) for m in revision.membership
        })

    def _media(self, conn: psycopg.Connection[Row], asset_id: EntityId) -> VideoInput:
        row = conn.execute(
            """SELECT c.source_reference FROM stageflow.completed_media_asset_registry a
               JOIN stageflow.media_candidate c USING (candidate_id) WHERE a.asset_id=%s""",
            (asset_id.value,),
        ).fetchone()
        if row is None:
            raise WorkExecutionNotFoundError("completed_media_asset_not_found")
        suffix = Path(row["source_reference"]).suffix.casefold()
        return VideoInput(CompletedMediaAssetContent(asset_id),
                          "video/mp4" if suffix in {".mp4", ".mov", ".mkv", ".mxf"}
                          else "application/octet-stream")

    def apply_render_result(
        self, claim: OperationClaim[RenderOperationInput], output: RenderedOutput,
    ) -> RenderedOutput:
        value = claim.operation.input
        if (output.operation_id != claim.operation.id
                or output.producing_attempt_id != claim.attempt.id
                or output.assembly_revision_id != value.assembly_revision_id
                or output.profile_id != value.execution_profile_id
                or output.profile_version != value.execution_profile_version
                or output.video_bit_rate != value.video_bit_rate
                or output.audio_bit_rate != value.audio_bit_rate
                or output.event_render_setting_version != value.event_render_setting_version):
            raise WorkExecutionConflictError("render_result_identity_conflict")
        commit_started = False
        try:
            with self._connect() as conn:
                row = conn.execute(
                    """SELECT o.*, statement_timestamp() AS database_now
                       FROM stageflow.work_operation o WHERE operation_id=%s FOR UPDATE""",
                    (claim.operation.id.value,),
                ).fetchone()
                old = conn.execute(
                    """SELECT o.*, i.video_bit_rate, i.audio_bit_rate,
                              i.event_render_setting_version FROM stageflow.rendered_output o
                       JOIN stageflow.render_operation_input i USING (operation_id)
                       WHERE operation_id=%s""", (claim.operation.id.value,),
                ).fetchone()
                if old is not None:
                    if _output(old) != output:
                        raise WorkExecutionConflictError("render_result_identity_conflict")
                    return _output(old)
                self._assert_active_claim(row, claim)
                conn.execute(
                    """INSERT INTO stageflow.rendered_output
                       (output_id,assembly_revision_id,render_profile_id,render_profile_version,
                        operation_id,producing_attempt_id,content_key,sha256,manifest_content_key,
                        manifest_sha256,byte_size,media_type,duration_microseconds,frame_count,
                        ffmpeg_version,ffmpeg_sha256,produced_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (output.id.value, output.assembly_revision_id.value, output.profile_id,
                     output.profile_version, output.operation_id.value,
                     output.producing_attempt_id.value, output.content_key, output.sha256,
                     output.manifest_content_key, output.manifest_sha256, output.byte_size,
                     output.media_type, output.duration_microseconds, output.frame_count,
                     output.ffmpeg.version, output.ffmpeg.sha256, output.produced_at),
                )
                conn.execute(
                    """UPDATE stageflow.work_operation_attempt SET attempt_status='finalized',
                       finalized_at=statement_timestamp(), outcome='succeeded', retryable=false,
                       reason_code='result_applied', diagnostic_summary='render_result_applied'
                       WHERE attempt_id=%s""", (claim.attempt.id.value,),
                )
                conn.execute(
                    """UPDATE stageflow.work_operation SET operation_status='succeeded',
                       terminal_result_type='rendered_output',
                       terminal_result_rendered_output_id=%s,
                       current_attempt_id=NULL, lease_owner_worker_id=NULL, lease_expires_at=NULL,
                       last_reason_code=NULL, row_revision=row_revision+1,
                       updated_at=statement_timestamp()
                       WHERE operation_id=%s""", (output.id.value, claim.operation.id.value),
                )
                commit_started = True
                return output
        except (psycopg.InterfaceError, psycopg.OperationalError) as exc:
            # Once COMMIT is sent, only a known rollback is definite; anything else may have
            # committed, so the published files must be kept for the operator.
            if commit_started and exc.sqlstate not in _DEFINITE_ROLLBACK_SQLSTATES:
                raise RenderResultCommitAmbiguousError("render_commit_ambiguous") from None
            raise WorkExecutionStorageUnavailableError("postgresql_unavailable") from None

    def list_render_operations(
        self, event_id: EntityId, session_id: EntityId, *, after: EntityId | None = None,
        limit: int = 50, newest_first: bool = False,
    ) -> tuple[tuple[DurableOperation[RenderOperationInput], ...], EntityId | None]:
        rows = self._list(event_id, session_id, after, limit, outputs=False,
                          newest_first=newest_first)
        try:
            with self._connect() as conn:
                items = tuple(self._operation(row, conn) for row in rows[:limit])
        except (psycopg.InterfaceError, psycopg.OperationalError):
            raise WorkExecutionStorageUnavailableError("postgresql_unavailable") from None
        return items, items[-1].id if len(rows) > limit else None

    def list_outputs(
        self, event_id: EntityId, session_id: EntityId, *, after: EntityId | None = None,
        limit: int = 50,
    ) -> tuple[tuple[RenderedOutput, ...], EntityId | None]:
        rows = self._list(event_id, session_id, after, limit, outputs=True)
        items = tuple(_output(row) for row in rows[:limit])
        return items, items[-1].id if len(rows) > limit else None

    def _list(self, event: EntityId, session: EntityId, after: EntityId | None,
              limit: int, *, outputs: bool, newest_first: bool = False) -> list[Row]:
        if not 1 <= limit <= 100:
            raise ValueError("render_limit_out_of_bounds")
        query: LiteralString
        if outputs:
            query = """SELECT o.*, i.video_bit_rate, i.audio_bit_rate,
                              i.event_render_setting_version
                       FROM stageflow.rendered_output o
                       JOIN stageflow.render_operation_input i USING (operation_id)
                       JOIN stageflow.assembly_revision r ON r.revision_id=o.assembly_revision_id
                       WHERE r.event_id=%s AND r.session_id=%s
                         AND (%s::uuid IS NULL OR o.output_id>%s::uuid)
                       ORDER BY o.output_id LIMIT %s"""
        elif newest_first:
            query = """SELECT o.* FROM stageflow.work_operation o
                       JOIN stageflow.render_operation_input i USING (operation_id)
                       JOIN stageflow.assembly_revision r ON r.revision_id=i.assembly_revision_id
                       WHERE r.event_id=%s AND r.session_id=%s AND o.operation_kind='render'
                         AND (%s::uuid IS NULL OR (o.created_at, o.operation_id) < (
                             SELECT c.created_at, c.operation_id FROM stageflow.work_operation c
                             WHERE c.operation_id=%s::uuid))
                       ORDER BY o.created_at DESC, o.operation_id DESC LIMIT %s"""
        else:
            query = """SELECT o.* FROM stageflow.work_operation o
                       JOIN stageflow.render_operation_input i USING (operation_id)
                       JOIN stageflow.assembly_revision r ON r.revision_id=i.assembly_revision_id
                       WHERE r.event_id=%s AND r.session_id=%s AND o.operation_kind='render'
                         AND (%s::uuid IS NULL OR o.operation_id>%s::uuid)
                       ORDER BY o.operation_id LIMIT %s"""
        try:
            with self._connect() as conn:
                return conn.execute(query, (event.value, session.value,
                                           None if after is None else after.value,
                                           None if after is None else after.value,
                                           limit + 1)).fetchall()
        except (psycopg.InterfaceError, psycopg.OperationalError):
            raise WorkExecutionStorageUnavailableError("postgresql_unavailable") from None


def _output(row: Row) -> RenderedOutput:
    return RenderedOutput(
        EntityId(str(row["output_id"])), EntityId(str(row["assembly_revision_id"])),
        row["render_profile_id"], row["render_profile_version"], EntityId(str(row["operation_id"])),
        EntityId(str(row["producing_attempt_id"])), row["content_key"], row["sha256"],
        row["manifest_content_key"], row["manifest_sha256"], row["byte_size"], row["media_type"],
        row["duration_microseconds"], row["frame_count"],
        FFmpegIdentity(row["ffmpeg_version"], row["ffmpeg_sha256"]), row["produced_at"],
        row["video_bit_rate"], row["audio_bit_rate"], row["event_render_setting_version"],
    )


def _setting(row: Row) -> EventRenderSetting:
    return EventRenderSetting(
        EntityId(str(row["event_id"])), row["version"], row["render_profile_id"],
        row["render_profile_version"],
        RenderAdjustments(row["video_bit_rate"], row["audio_bit_rate"]),
        EntityId(str(row["command_id"])), row["request_digest"],
        EntityId(str(row["selected_by"])), row["selected_at"],
    )
