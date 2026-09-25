from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, LiteralString

import psycopg
from psycopg.rows import dict_row

from app.contexts.assembly.contracts import (
    ApprovalAction,
    ApprovalState,
    AssetPage,
    AssetSummary,
    CommandIdentity,
    CompletedMediaAssetContent,
    ExternalContent,
    PackagingAsset,
    PackagingAssetApprovalDecision,
    PackagingAssetRevision,
    PackagingAssetRole,
    RevisionContent,
    RevisionPage,
    RevisionSummary,
    nonnegative,
    validate_page,
)
from app.contexts.assembly.repository import (
    PackagingAssetConflictError,
    PackagingAssetNotFoundError,
    PackagingAssetStorageUnavailableError,
)
from app.shared.ids import EntityId

type Row = dict[str, Any]


class PostgresPackagingAssetRepository:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @contextmanager
    def _transaction(self, *, read: bool = False) -> Generator[psycopg.Connection[Row]]:
        try:
            with psycopg.Connection[Row].connect(self._dsn, row_factory=dict_row) as connection:
                if read:
                    connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                yield connection
        except psycopg.OperationalError as exc:
            raise PackagingAssetStorageUnavailableError("postgresql_unavailable") from exc
        except psycopg.errors.ForeignKeyViolation as exc:
            raise PackagingAssetNotFoundError("packaging_asset_reference_not_found") from exc
        except psycopg.errors.UniqueViolation as exc:
            raise PackagingAssetConflictError("packaging_asset_identity_conflict") from exc

    def _claim(
        self, connection: psycopg.Connection[Row], command: CommandIdentity,
        kind: str, result_id: EntityId, replay_query: LiteralString,
    ) -> Row | None:
        inserted = connection.execute(
            """INSERT INTO stageflow.packaging_asset_command
               (operation_id, command_kind, request_digest, result_id, actor_id, recorded_at)
               VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (operation_id) DO NOTHING
               RETURNING result_id""",
            (command.operation_id.value, kind, command.request_digest,
             result_id.value, command.actor_id.value, command.recorded_at),
        ).fetchone()
        if inserted is not None:
            return None
        receipt = connection.execute(
            "SELECT * FROM stageflow.packaging_asset_command WHERE operation_id = %s",
            (command.operation_id.value,),
        ).fetchone()
        assert receipt is not None
        if receipt["command_kind"] != kind or receipt["request_digest"] != command.request_digest:
            raise PackagingAssetConflictError("human_command_operation_id_conflict")
        result = connection.execute(replay_query, (receipt["result_id"],)).fetchone()
        assert result is not None
        return result

    def _lock_revision(
        self, connection: psycopg.Connection[Row], asset_id: EntityId, expected: int,
    ) -> None:
        # Serialize all revision/decision appends for this asset, across processes.
        asset = connection.execute(
            "SELECT 1 FROM stageflow.packaging_asset WHERE packaging_asset_id = %s FOR UPDATE",
            (asset_id.value,),
        ).fetchone()
        if asset is None:
            raise PackagingAssetNotFoundError("packaging_asset_not_found")
        row = connection.execute(
            """SELECT COALESCE(max(revision_number), 0) AS current_revision
               FROM stageflow.packaging_asset_revision WHERE packaging_asset_id = %s""",
            (asset_id.value,),
        ).fetchone()
        assert row is not None
        if row["current_revision"] != expected:
            raise PackagingAssetConflictError("packaging_asset_revision_conflict")

    def register(self, command: CommandIdentity, asset: PackagingAsset) -> PackagingAsset:
        with self._transaction() as connection:
            replay = self._claim(
                connection, command, "packaging_asset_registration", asset.id,
                "SELECT * FROM stageflow.packaging_asset WHERE packaging_asset_id = %s",
            )
            if replay is not None:
                return _asset(replay)
            connection.execute(
                """INSERT INTO stageflow.packaging_asset
                   (packaging_asset_id, event_id, stage_id, name, role, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (asset.id.value, asset.event_id.value,
                 None if asset.stage_id is None else asset.stage_id.value,
                 asset.name, asset.role.value, asset.created_at),
            )
            return asset

    def revise(
        self, command: CommandIdentity, revision: PackagingAssetRevision, *, expected_revision: int,
    ) -> PackagingAssetRevision:
        with self._transaction() as connection:
            replay = self._claim(
                connection, command, "packaging_asset_revision", revision.id,
                "SELECT * FROM stageflow.packaging_asset_revision WHERE revision_id = %s",
            )
            if replay is not None:
                return _revision(replay)
            self._lock_revision(connection, revision.packaging_asset_id, expected_revision)
            if revision.revision_number != expected_revision + 1:
                raise PackagingAssetConflictError("packaging_asset_revision_conflict")
            content = revision.content
            ref = content.reference
            external = ref if isinstance(ref, ExternalContent) else None
            connection.execute(
                """INSERT INTO stageflow.packaging_asset_revision
                   (revision_id, packaging_asset_id, revision_number, content_kind,
                    content_key, sha256, byte_size, media_type, completed_media_asset_id,
                    measured_duration_microseconds, effective_from, effective_until, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (revision.id.value, revision.packaging_asset_id.value, revision.revision_number,
                 "external_content" if external is not None else "completed_media_asset",
                 None if external is None else external.content_key,
                 None if external is None else external.sha256,
                 None if external is None else external.byte_size,
                 None if external is None else external.media_type,
                 ref.asset_id.value if isinstance(ref, CompletedMediaAssetContent) else None,
                 content.measured_duration_microseconds, content.effective_from,
                 content.effective_until, revision.created_at),
            )
            return revision

    def decide(
        self, command: CommandIdentity, *, decision_id: EntityId, packaging_asset_id: EntityId,
        revision_number: int, expected_revision: int, action: ApprovalAction, reason: str,
    ) -> PackagingAssetApprovalDecision:
        with self._transaction() as connection:
            replay = self._claim(
                connection, command, "packaging_asset_approval", decision_id,
                "SELECT * FROM stageflow.packaging_asset_approval_decision WHERE decision_id = %s",
            )
            if replay is not None:
                return _decision(replay)
            self._lock_revision(connection, packaging_asset_id, expected_revision)
            if not 1 <= revision_number <= expected_revision:
                raise PackagingAssetNotFoundError("packaging_asset_revision_not_found")
            row = connection.execute(
                """INSERT INTO stageflow.packaging_asset_approval_decision
                   (decision_id, packaging_asset_id, revision_number, decision_sequence,
                    actor_id, decided_at, action, reason)
                   SELECT %s, %s, %s, COALESCE(max(decision_sequence), 0) + 1, %s, %s, %s, %s
                   FROM stageflow.packaging_asset_approval_decision WHERE packaging_asset_id = %s
                   RETURNING *""",
                (decision_id.value, packaging_asset_id.value, revision_number,
                 command.actor_id.value, command.recorded_at, action.value, reason,
                 packaging_asset_id.value),
            ).fetchone()
            assert row is not None
            return _decision(row)

    def list_assets(
        self, event_id: EntityId, *, after: EntityId | None = None, limit: int = 50,
    ) -> AssetPage:
        validate_page(limit)
        with self._transaction(read=True) as connection:
            count = connection.execute(
                "SELECT count(*) AS total FROM stageflow.packaging_asset WHERE event_id = %s",
                (event_id.value,),
            ).fetchone()
            assert count is not None
            rows = connection.execute(
                """WITH page AS (
                    SELECT * FROM stageflow.packaging_asset
                    WHERE event_id = %s AND (%s::uuid IS NULL OR packaging_asset_id > %s::uuid)
                    ORDER BY packaging_asset_id LIMIT %s
                ) SELECT page.*, COALESCE(r.current_revision, 0) AS current_revision,
                    d.decision_count FROM page
                LEFT JOIN LATERAL (
                    SELECT max(revision_number) AS current_revision
                    FROM stageflow.packaging_asset_revision
                    WHERE packaging_asset_id = page.packaging_asset_id
                ) r ON TRUE
                LEFT JOIN LATERAL (
                    SELECT count(*) AS decision_count
                    FROM stageflow.packaging_asset_approval_decision
                    WHERE packaging_asset_id = page.packaging_asset_id
                ) d ON TRUE ORDER BY page.packaging_asset_id""",
                (event_id.value, None if after is None else after.value,
                 None if after is None else after.value, limit + 1),
            ).fetchall()
            items = tuple(AssetSummary(_asset(row), row["current_revision"], row["decision_count"])
                          for row in rows[:limit])
            return AssetPage(items, count["total"],
                             items[-1].asset.id if len(rows) > limit else None)

    def list_revisions(
        self, event_id: EntityId, packaging_asset_id: EntityId, *, after: int = 0, limit: int = 50,
    ) -> RevisionPage:
        validate_page(limit)
        nonnegative(after, "after")
        with self._transaction(read=True) as connection:
            asset = connection.execute(
                """SELECT 1 FROM stageflow.packaging_asset
                   WHERE event_id = %s AND packaging_asset_id = %s""",
                (event_id.value, packaging_asset_id.value),
            ).fetchone()
            if asset is None:
                raise PackagingAssetNotFoundError("packaging_asset_not_found")
            count = connection.execute(
                """SELECT count(*) AS total FROM stageflow.packaging_asset_revision
                   WHERE packaging_asset_id = %s""", (packaging_asset_id.value,),
            ).fetchone()
            assert count is not None
            rows = connection.execute(
                """WITH page AS (
                    SELECT * FROM stageflow.packaging_asset_revision
                    WHERE packaging_asset_id = %s AND revision_number > %s
                    ORDER BY revision_number LIMIT %s
                ) SELECT page.*, d.decision_count, latest.decision_id, latest.decision_sequence,
                    latest.actor_id, latest.decided_at, latest.action, latest.reason
                FROM page LEFT JOIN LATERAL (
                    SELECT count(*) AS decision_count
                    FROM stageflow.packaging_asset_approval_decision
                    WHERE packaging_asset_id = page.packaging_asset_id
                        AND revision_number = page.revision_number
                ) d ON TRUE LEFT JOIN LATERAL (
                    SELECT * FROM stageflow.packaging_asset_approval_decision
                    WHERE packaging_asset_id = page.packaging_asset_id
                        AND revision_number = page.revision_number
                    ORDER BY decision_sequence DESC LIMIT 1
                ) latest ON TRUE ORDER BY page.revision_number""",
                (packaging_asset_id.value, after, limit + 1),
            ).fetchall()
            items: list[RevisionSummary] = []
            for row in rows[:limit]:
                decision = None if row["decision_id"] is None else _decision(row)
                items.append(RevisionSummary(
                    _revision(row), ApprovalState.UNREVIEWED if decision is None
                    else decision.approval_state, row["decision_count"], decision,
                ))
            return RevisionPage(tuple(items), count["total"],
                                items[-1].revision.revision_number if len(rows) > limit else None)


def _asset(row: Row) -> PackagingAsset:
    return PackagingAsset(
        EntityId(str(row["packaging_asset_id"])), EntityId(str(row["event_id"])),
        None if row["stage_id"] is None else EntityId(str(row["stage_id"])),
        row["name"], PackagingAssetRole(row["role"]), row["created_at"],
    )


def _revision(row: Row) -> PackagingAssetRevision:
    reference = (ExternalContent(
        row["content_key"], row["sha256"], row["byte_size"], row["media_type"])
                 if row["content_kind"] == "external_content"
                 else CompletedMediaAssetContent(EntityId(str(row["completed_media_asset_id"]))))
    return PackagingAssetRevision(
        EntityId(str(row["revision_id"])), EntityId(str(row["packaging_asset_id"])),
        row["revision_number"], RevisionContent(reference, row["measured_duration_microseconds"],
                                              row["effective_from"], row["effective_until"]),
        row["created_at"],
    )


def _decision(row: Row) -> PackagingAssetApprovalDecision:
    return PackagingAssetApprovalDecision(
        EntityId(str(row["decision_id"])), EntityId(str(row["packaging_asset_id"])),
        row["revision_number"], row["decision_sequence"], EntityId(str(row["actor_id"])),
        row["decided_at"], ApprovalAction(row["action"]), row["reason"],
    )
