"""Append-only Assembly persistence, reading Kernel and Packaging authority in one transaction."""
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import replace
from typing import Any, LiteralString

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import TypeAdapter

from app.contexts.assembly.contracts import (
    ApprovalState,
    CommandIdentity,
    CompletedMediaAssetContent,
    ExternalContent,
    PackagingAsset,
    PackagingAssetRevision,
    PackagingAssetRole,
    RevisionContent,
    nonnegative,
    validate_page,
)
from app.contexts.assembly.resolution import build_revision, is_stale, resolve_metadata
from app.contexts.assembly.session_contracts import (
    AssemblyAction,
    AssemblyApprovalDecision,
    AssemblyInputs,
    AssemblyMetadataOverride,
    AssemblyPage,
    AssemblyRevision,
    AssemblySlot,
    AssemblyTemplate,
    AssemblyValidation,
    CompletionMember,
    ExplicitBinding,
    MediaOrderSource,
    MetadataField,
    MetadataOverrideAction,
    MetadataOverridePage,
    MetadataValue,
    PackagingCandidate,
    SessionAssembly,
    SlotBinding,
    TemplatePage,
    ValidationIssue,
)
from app.contexts.assembly.session_repository import (
    AssemblyConflictError,
    AssemblyNotFoundError,
    AssemblyStorageUnavailableError,
)
from app.shared.ids import EntityId

type Row = dict[str, Any]
type Connection = psycopg.Connection[Row]
SLOTS = TypeAdapter(tuple[AssemblySlot, ...])
ISSUES = TypeAdapter(tuple[ValidationIssue, ...])


def _id(value: object) -> EntityId:
    return EntityId(str(value))


def _template(row: Row) -> AssemblyTemplate:
    return AssemblyTemplate(_id(row["template_id"]), _id(row["event_id"]), row["template_key"],
                            row["version"], row["name"], SLOTS.validate_python(row["slots"]),
                            tuple(MetadataField(f) for f in row["required_metadata"]),
                            row["created_at"])


def _decision(row: Row) -> AssemblyApprovalDecision:
    return AssemblyApprovalDecision(
        _id(row["decision_id"]), _id(row["session_id"]), _id(row["revision_id"]), row["sequence"],
        _id(row["actor_id"]), row["decided_at"], AssemblyAction(row["action"]), row["reason"],
        row["authority_kind"],
    )


def _override(row: Row) -> AssemblyMetadataOverride:
    return AssemblyMetadataOverride(
        _id(row["override_id"]), _id(row["session_id"]), MetadataField(row["field"]),
        MetadataOverrideAction(row["action"]), tuple(row["values_json"]), row["sequence"],
        _id(row["actor_id"]), row["recorded_at"], row["reason"], row["authority_kind"],
    )


class PostgresSessionAssemblyRepository:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def read_render_source(
        self, conn: Connection, revision_id: EntityId, *, lock: bool,
    ) -> tuple[AssemblyRevision, AssemblyInputs]:
        """Read pinned facts and the existing staleness inputs in an enlisted transaction."""
        revision = self._get_revision(conn, revision_id)
        session = self._session(conn, revision.session_id, lock=lock)
        return revision, self._inputs(conn, session)

    @contextmanager
    def _transaction(self, *, read: bool = False) -> Generator[Connection]:
        try:
            with psycopg.Connection[Row].connect(self._dsn, row_factory=dict_row) as connection:
                if read:
                    connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                yield connection
        except psycopg.OperationalError as exc:
            raise AssemblyStorageUnavailableError("postgresql_unavailable") from exc
        except psycopg.errors.ForeignKeyViolation as exc:
            raise AssemblyNotFoundError("assembly_reference_not_found") from exc
        except psycopg.errors.UniqueViolation as exc:
            raise AssemblyConflictError("assembly_identity_conflict") from exc

    def _claim(
        self, conn: Connection, command: CommandIdentity, kind: str, result_id: EntityId,
    ) -> EntityId | None:
        row = conn.execute(
            """INSERT INTO stageflow.assembly_command
               (operation_id, command_kind, request_digest, result_id, actor_id, recorded_at)
               VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (operation_id) DO NOTHING
               RETURNING result_id""",
            (command.operation_id.value, kind, command.request_digest, result_id.value,
             command.actor_id.value, command.recorded_at),
        ).fetchone()
        if row is not None:
            return None
        receipt = conn.execute("SELECT * FROM stageflow.assembly_command WHERE operation_id=%s",
                               (command.operation_id.value,)).fetchone()
        assert receipt is not None
        if receipt["command_kind"] != kind or receipt["request_digest"] != command.request_digest:
            raise AssemblyConflictError("human_command_operation_id_conflict")
        return _id(receipt["result_id"])

    def record_metadata_override(
        self, command: CommandIdentity, entry: AssemblyMetadataOverride, expected_sequence: int,
    ) -> AssemblyMetadataOverride:
        with self._transaction() as conn:
            # The new row owns its receipt: 0013's command-kind constraint stays unchanged.
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                         ("assembly_metadata_override:" + command.operation_id.value,))
            receipt = conn.execute(
                "SELECT * FROM stageflow.assembly_metadata_override WHERE operation_id=%s",
                (command.operation_id.value,),
            ).fetchone()
            if receipt is not None:
                if receipt["request_digest"] != command.request_digest:
                    raise AssemblyConflictError("human_command_operation_id_conflict")
                return _override(receipt)
            self._session(conn, entry.session_id, lock=True)
            if self._current(conn, entry.session_id) is None:
                raise AssemblyNotFoundError("session_assembly_not_found")
            current = conn.execute(
                """SELECT COALESCE(max(sequence),0) AS sequence
                   FROM stageflow.assembly_metadata_override WHERE session_id=%s""",
                (entry.session_id.value,),
            ).fetchone()
            assert current is not None
            if current["sequence"] != expected_sequence or entry.sequence != expected_sequence + 1:
                raise AssemblyConflictError("metadata_override_sequence_conflict")
            conn.execute(
                """INSERT INTO stageflow.assembly_metadata_override
                   (override_id,session_id,field,action,values_json,sequence,actor_id,recorded_at,
                    reason,authority_kind,operation_id,request_digest)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (entry.id.value, entry.session_id.value, entry.field.value, entry.action.value,
                 Jsonb(list(entry.values)), entry.sequence, entry.actor_id.value, entry.recorded_at,
                 entry.reason, entry.authority_kind, command.operation_id.value,
                 command.request_digest),
            )
            return entry

    def list_metadata_overrides(
        self, event_id: EntityId, session_id: EntityId, *, after: int = 0, limit: int = 50,
    ) -> MetadataOverridePage:
        validate_page(limit)
        nonnegative(after, "after")
        with self._transaction(read=True) as conn:
            session = self._session(conn, session_id)
            if _id(session["event_id"]) != event_id:
                raise AssemblyNotFoundError("session_not_in_event")
            if self._current(conn, session_id) is None:
                raise AssemblyNotFoundError("session_assembly_not_found")
            count = conn.execute(
                """SELECT count(*) AS total FROM stageflow.assembly_metadata_override
                   WHERE session_id=%s""", (session_id.value,),
            ).fetchone()
            assert count is not None
            rows = conn.execute(
                """SELECT * FROM stageflow.assembly_metadata_override
                   WHERE session_id=%s AND sequence>%s ORDER BY sequence LIMIT %s""",
                (session_id.value, after, limit + 1),
            ).fetchall()
            items = tuple(_override(row) for row in rows[:limit])
            return MetadataOverridePage(items, count["total"],
                                        items[-1].sequence if len(rows) > limit else None)

    def create_template(
        self, command: CommandIdentity, template: AssemblyTemplate, expected_version: int,
    ) -> AssemblyTemplate:
        with self._transaction() as conn:
            replay = self._claim(conn, command, "template", template.id)
            if replay is not None:
                return self._get_template(conn, replay)
            # Stable Event row serializes first and later template versions, without a mutation.
            event = conn.execute(
                "SELECT 1 FROM stageflow.business_event WHERE event_id=%s FOR UPDATE",
                (template.event_id.value,),
            ).fetchone()
            if event is None:
                raise AssemblyNotFoundError("event_not_found")
            current = conn.execute(
                """SELECT COALESCE(max(version),0) AS version FROM stageflow.assembly_template
                   WHERE event_id=%s AND template_key=%s""",
                (template.event_id.value, template.template_key),
            ).fetchone()
            assert current is not None
            if current["version"] != expected_version or template.version != expected_version + 1:
                raise AssemblyConflictError("template_version_conflict")
            conn.execute(
                """INSERT INTO stageflow.assembly_template
                   (template_id,event_id,template_key,version,name,slots,required_metadata,created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (template.id.value, template.event_id.value, template.template_key,
                 template.version,
                 template.name, Jsonb(SLOTS.dump_python(template.slots, mode="json")),
                 Jsonb(list(template.required_metadata)), template.created_at),
            )
            return template

    def _get_template(self, conn: Connection, template_id: EntityId) -> AssemblyTemplate:
        row = conn.execute("SELECT * FROM stageflow.assembly_template WHERE template_id=%s",
                           (template_id.value,)).fetchone()
        if row is None:
            raise AssemblyNotFoundError("assembly_template_not_found")
        return _template(row)

    def _session(self, conn: Connection, session_id: EntityId, *, lock: bool = False) -> Row:
        query: LiteralString = "SELECT * FROM stageflow.session WHERE session_id=%s"
        if lock:
            query += " FOR UPDATE"
        row = conn.execute(query, (session_id.value,)).fetchone()
        if row is None:
            raise AssemblyNotFoundError("session_not_found")
        return row

    def _inputs(self, conn: Connection, session: Row) -> AssemblyInputs:
        completion = None
        members: tuple[CompletionMember, ...] = ()
        if session["package_state"] == "complete":
            completion = conn.execute(
                """SELECT * FROM stageflow.session_completion_history
                   WHERE session_id=%s AND package_revision=%s AND approved
                   ORDER BY decided_at DESC, completion_decision_id DESC LIMIT 1""",
                (session["session_id"], session["package_revision"]),
            ).fetchone()
            if completion is not None and completion["membership_snapshot_status"] != "unresolved":
                rows = conn.execute(
                    """SELECT m.asset_id,m.association_revision,a.media_started_at,a.registered_at
                       FROM stageflow.session_completion_asset m
                       JOIN stageflow.completed_media_asset_registry a USING (asset_id)
                       WHERE m.completion_decision_id=%s""",
                    (completion["completion_decision_id"],),
                ).fetchall()
                members = tuple(CompletionMember(_id(r["asset_id"]), r["association_revision"],
                                                 r["media_started_at"], r["registered_at"],
                                                 MediaOrderSource.MEDIA_TIMING
                                                 if r["media_started_at"] is not None
                                                 else MediaOrderSource.REGISTRATION_TIME,
                                                 r["media_started_at"] or r["registered_at"])
                                for r in rows)
        metadata: tuple[MetadataValue, ...] = ()
        if session["program_expectation_id"] is not None:
            row = conn.execute(
                """SELECT r.* FROM stageflow.program_expectation p
                   JOIN stageflow.program_expectation_revision r
                       ON r.expectation_id=p.expectation_id
                       AND r.expectation_revision=p.revision
                   WHERE p.expectation_id=%s AND p.event_id=%s""",
                (session["program_expectation_id"], session["event_id"]),
            ).fetchone()
            if row is not None:
                source_id, version = _id(row["expectation_id"]), row["expectation_revision"]
                # Display strings are unordered source data, not participant identities or billing.
                metadata = (
                    MetadataValue(MetadataField.PARTICIPANT_NAMES, tuple(sorted(row["speakers"])),
                                  source_id, version),
                    MetadataValue(MetadataField.SESSION_TITLE, (row["title"],), source_id, version),
                )
        inputs = AssemblyInputs(
            _id(session["session_id"]), _id(session["event_id"]), _id(session["stage_id"]),
            session["authoritative_start"], session["package_revision"],
            session["package_state"] == "complete",
            None if completion is None else _id(completion["completion_decision_id"]),
            members, metadata,
        )
        # At most one latest entry for each of the two supported fields.
        overrides = tuple(_override(r) for r in conn.execute(
            """SELECT DISTINCT ON (field) * FROM stageflow.assembly_metadata_override
               WHERE session_id=%s ORDER BY field, sequence DESC""", (session["session_id"],),
        ))
        return replace(inputs, metadata=resolve_metadata(inputs, overrides))

    def _candidates(self, conn: Connection, event_id: EntityId) -> tuple[PackagingCandidate, ...]:
        # Packaging commands lock these same roots. Deterministic order prevents lock inversion.
        conn.execute("""SELECT packaging_asset_id FROM stageflow.packaging_asset
                        WHERE event_id=%s ORDER BY packaging_asset_id FOR SHARE""",
                     (event_id.value,)).fetchall()
        rows = conn.execute(
            """SELECT a.*, r.*, a.created_at AS asset_created_at
               FROM stageflow.packaging_asset a JOIN stageflow.packaging_asset_revision r
                   USING (packaging_asset_id)
               JOIN LATERAL (SELECT action FROM stageflow.packaging_asset_approval_decision d
                   WHERE d.packaging_asset_id=r.packaging_asset_id
                     AND d.revision_number=r.revision_number
                   ORDER BY decision_sequence DESC LIMIT 1) d ON d.action='approve'
               WHERE a.event_id=%s""", (event_id.value,),
        ).fetchall()
        return tuple(_candidate(r) for r in rows)

    def _current(self, conn: Connection, session_id: EntityId) -> Row | None:
        return conn.execute("""SELECT * FROM stageflow.assembly_revision WHERE session_id=%s
                               ORDER BY revision_number DESC LIMIT 1""",
                            (session_id.value,)).fetchone()

    def propose(
        self, command: CommandIdentity, *, revision_id: EntityId, session_id: EntityId,
        template_id: EntityId, expected_revision: int, expected_package_revision: int,
        explicit: tuple[ExplicitBinding, ...],
    ) -> AssemblyRevision:
        with self._transaction() as conn:
            replay = self._claim(conn, command, "proposal", revision_id)
            if replay is not None:
                return self._get_revision(conn, replay)
            session = self._session(conn, session_id, lock=True)
            current = self._current(conn, session_id)
            number = 0 if current is None else current["revision_number"]
            if number != expected_revision:
                raise AssemblyConflictError("assembly_revision_conflict")
            if session["package_revision"] != expected_package_revision:
                raise AssemblyConflictError("package_revision_conflict")
            template = self._get_template(conn, template_id)
            if template.event_id != _id(session["event_id"]):
                raise AssemblyNotFoundError("template_not_in_session_event")
            revision = build_revision(
                command, revision_id, number + 1,
                None if current is None else _id(current["revision_id"]), template,
                self._inputs(conn, session), self._candidates(conn, template.event_id), explicit,
            )
            self._insert_revision(conn, revision)
            return revision

    def _insert_revision(self, conn: Connection, r: AssemblyRevision) -> None:
        conn.execute(
            """INSERT INTO stageflow.assembly_revision
               (revision_id,session_id,event_id,revision_number,supersedes_id,template_id,
                package_revision,completion_decision_id,validation_state,validation_issues,
                actor_id,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (r.id.value, r.session_id.value, r.event_id.value, r.revision_number,
             None if r.supersedes_id is None else r.supersedes_id.value, r.template_id.value,
             r.package_revision, None if r.completion_decision_id is None
             else r.completion_decision_id.value, r.validation.state,
             Jsonb(ISSUES.dump_python(r.validation.issues, mode="json")),
             r.actor_id.value, r.created_at),
        )
        with conn.cursor() as cursor:
            cursor.executemany(
                """INSERT INTO stageflow.assembly_member
                   (revision_id,position,completion_decision_id,asset_id,association_revision,
                    media_started_at,order_source,order_key_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                [(r.id.value, i, None if r.completion_decision_id is None
                  else r.completion_decision_id.value, m.asset_id.value, m.association_revision,
                  m.media_started_at, m.order_source.value, m.order_key_at)
                 for i, m in enumerate(r.membership)],
            )
            cursor.executemany(
                """INSERT INTO stageflow.assembly_binding
                   (revision_id,position,slot_key,packaging_revision_id,outcome)
                   VALUES (%s,%s,%s,%s,%s)""",
                [(r.id.value, i, b.slot_key, None if b.packaging_revision_id is None
                  else b.packaging_revision_id.value, b.outcome) for i, b in enumerate(r.bindings)],
            )
            cursor.executemany(
                """INSERT INTO stageflow.assembly_metadata_snapshot
                   (revision_id,field,values_json,source,source_id,source_revision)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                [(r.id.value, m.field.value, Jsonb(list(m.values)), m.source, m.source_id.value,
                  m.source_revision) for m in r.metadata if m.source == "program_expectation"],
            )

            cursor.executemany(
                """INSERT INTO stageflow.assembly_metadata_override_snapshot
                   (revision_id,field,override_id) VALUES (%s,%s,%s)""",
                [(r.id.value, m.field.value, m.source_id.value) for m in r.metadata
                 if m.source == "operator_override"],
            )

    def _get_revision(self, conn: Connection, revision_id: EntityId) -> AssemblyRevision:
        row = conn.execute("SELECT * FROM stageflow.assembly_revision WHERE revision_id=%s",
                           (revision_id.value,)).fetchone()
        if row is None:
            raise AssemblyNotFoundError("assembly_revision_not_found")
        return self._hydrate(conn, [row])[0]

    def _hydrate(self, conn: Connection, rows: list[Row]) -> tuple[AssemblyRevision, ...]:
        ids = [r["revision_id"] for r in rows]
        members: dict[EntityId, list[CompletionMember]] = {}
        bindings: dict[EntityId, list[SlotBinding]] = {}
        metadata: dict[EntityId, list[MetadataValue]] = {}
        for m in conn.execute("""SELECT m.*,a.registered_at FROM stageflow.assembly_member m
                                 JOIN stageflow.completed_media_asset_registry a USING (asset_id)
                                 WHERE revision_id=ANY(%s::uuid[]) ORDER BY position""", (ids,)):
            members.setdefault(_id(m["revision_id"]), []).append(CompletionMember(
                _id(m["asset_id"]), m["association_revision"], m["media_started_at"],
                m["registered_at"], MediaOrderSource(m["order_source"] or "media_timing"),
                m["media_started_at"] if m["order_source"] is None else m["order_key_at"],
            ))
        for b in conn.execute("""SELECT * FROM stageflow.assembly_binding
                                 WHERE revision_id=ANY(%s::uuid[]) ORDER BY position""", (ids,)):
            bindings.setdefault(_id(b["revision_id"]), []).append(SlotBinding(
                b["slot_key"], None if b["packaging_revision_id"] is None
                else _id(b["packaging_revision_id"]), b["outcome"],
            ))
        for m in conn.execute("""SELECT revision_id,field,values_json,source,
                                        source_id,source_revision
                                 FROM stageflow.assembly_metadata_snapshot
                                 WHERE revision_id=ANY(%s::uuid[])
                                 UNION ALL
                                 SELECT s.revision_id,s.field,o.values_json,'operator_override',
                                        o.override_id,o.sequence
                                 FROM stageflow.assembly_metadata_override_snapshot s
                                 JOIN stageflow.assembly_metadata_override o USING (override_id)
                                 WHERE s.revision_id=ANY(%s::uuid[]) ORDER BY field""", (ids, ids)):
            metadata.setdefault(_id(m["revision_id"]), []).append(MetadataValue(
                MetadataField(m["field"]), tuple(m["values_json"]), _id(m["source_id"]),
                m["source_revision"], m["source"],
            ))
        return tuple(AssemblyRevision(
            _id(r["revision_id"]), _id(r["session_id"]), _id(r["event_id"]), r["revision_number"],
            None if r["supersedes_id"] is None else _id(r["supersedes_id"]), _id(r["template_id"]),
            r["package_revision"], None if r["completion_decision_id"] is None
            else _id(r["completion_decision_id"]), tuple(members.get(_id(r["revision_id"]), [])),
            tuple(bindings.get(_id(r["revision_id"]), [])),
            tuple(metadata.get(_id(r["revision_id"]), [])),
            AssemblyValidation(ISSUES.validate_python(r["validation_issues"])),
            _id(r["actor_id"]), r["created_at"],
        ) for r in rows)

    def decide(
        self, command: CommandIdentity, *, decision_id: EntityId, session_id: EntityId,
        revision_number: int, expected_revision: int, expected_decision_count: int,
        action: AssemblyAction, reason: str,
    ) -> AssemblyApprovalDecision:
        with self._transaction() as conn:
            replay = self._claim(conn, command, "decision", decision_id)
            if replay is not None:
                row = conn.execute("""SELECT * FROM stageflow.assembly_approval_decision
                                      WHERE decision_id=%s""", (replay.value,)).fetchone()
                assert row is not None
                return _decision(row)
            session = self._session(conn, session_id, lock=True)
            current = self._current(conn, session_id)
            count = conn.execute(
                """SELECT count(*) AS total,
                   count(*) FILTER (WHERE revision_id=%s) AS revision_count
                   FROM stageflow.assembly_approval_decision WHERE session_id=%s""",
                (None if current is None else current["revision_id"], session_id.value),
            ).fetchone()
            assert count is not None
            if current is None or current["revision_number"] != expected_revision or (
                revision_number != expected_revision
                or count["revision_count"] != expected_decision_count
            ):
                raise AssemblyConflictError("assembly_revision_conflict")
            revision = self._hydrate(conn, [current])[0]
            approved = frozenset(c.revision.id for c in self._candidates(conn, revision.event_id))
            if revision.validation.state != "valid" or is_stale(
                revision, session["package_revision"], approved,
                self._inputs(conn, session).metadata,
            ):
                raise AssemblyConflictError("assembly_not_approvable")
            decision = AssemblyApprovalDecision(
                decision_id, session_id, revision.id, count["total"] + 1, command.actor_id,
                command.recorded_at, action, reason,
            )
            conn.execute(
                """INSERT INTO stageflow.assembly_approval_decision
                   (decision_id,session_id,revision_id,sequence,actor_id,decided_at,action,reason,
                    authority_kind) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (decision.id.value, session_id.value, revision.id.value, decision.sequence,
                 decision.actor_id.value, decision.decided_at, decision.action.value,
                 decision.reason, decision.authority_kind),
            )
            return decision

    def list_templates(
        self, event_id: EntityId, *, after: EntityId | None = None, limit: int = 50,
    ) -> TemplatePage:
        validate_page(limit)
        with self._transaction(read=True) as conn:
            count = conn.execute("""SELECT count(*) AS total FROM stageflow.assembly_template
                                    WHERE event_id=%s""", (event_id.value,)).fetchone()
            assert count is not None
            rows = conn.execute(
                """SELECT * FROM stageflow.assembly_template WHERE event_id=%s
                   AND (%s::uuid IS NULL OR template_id>%s::uuid) ORDER BY template_id LIMIT %s""",
                (event_id.value, None if after is None else after.value,
                 None if after is None else after.value, limit + 1),
            ).fetchall()
            items = tuple(_template(r) for r in rows[:limit])
            return TemplatePage(items, count["total"], items[-1].id if len(rows) > limit else None)

    def list_revisions(
        self, event_id: EntityId, session_id: EntityId, *, after: int = 0, limit: int = 50,
    ) -> AssemblyPage:
        validate_page(limit)
        nonnegative(after, "after")
        with self._transaction(read=True) as conn:
            session = self._session(conn, session_id)
            if _id(session["event_id"]) != event_id:
                raise AssemblyNotFoundError("session_not_in_event")
            count = conn.execute("""SELECT count(*) AS total FROM stageflow.assembly_revision
                                    WHERE session_id=%s""", (session_id.value,)).fetchone()
            assert count is not None
            rows = conn.execute(
                """SELECT r.*, d.decision_id, d.sequence, d.actor_id AS decision_actor_id,
                          d.decided_at,d.action,d.reason,d.authority_kind, n.decision_count
                   FROM stageflow.assembly_revision r
                   LEFT JOIN LATERAL (SELECT * FROM stageflow.assembly_approval_decision
                       WHERE revision_id=r.revision_id ORDER BY sequence DESC LIMIT 1) d ON TRUE
                   LEFT JOIN LATERAL (SELECT count(*) AS decision_count
                       FROM stageflow.assembly_approval_decision WHERE revision_id=r.revision_id
                   ) n ON TRUE
                   WHERE r.session_id=%s AND r.revision_number>%s
                   ORDER BY r.revision_number LIMIT %s""", (session_id.value, after, limit + 1),
            ).fetchall()
            revisions = self._hydrate(conn, rows[:limit])
            ids = [b.packaging_revision_id.value for r in revisions for b in r.bindings
                   if b.packaging_revision_id is not None]
            approved = frozenset(_id(r["revision_id"]) for r in conn.execute(
                """SELECT r.revision_id FROM stageflow.packaging_asset_revision r
                   JOIN LATERAL (SELECT action FROM stageflow.packaging_asset_approval_decision
                     WHERE packaging_asset_id=r.packaging_asset_id
                       AND revision_number=r.revision_number
                     ORDER BY decision_sequence DESC LIMIT 1) d ON d.action='approve'
                   WHERE r.revision_id=ANY(%s::uuid[])""", (ids,),
            ))
            metadata = self._inputs(conn, session).metadata
            items: list[SessionAssembly] = []
            for revision, row in zip(revisions, rows[:limit], strict=True):
                latest = None if row["decision_id"] is None else _decision({
                    **row, "actor_id": row["decision_actor_id"],
                })
                state = ApprovalState.UNREVIEWED if latest is None else (
                    ApprovalState.APPROVED if latest.action == AssemblyAction.APPROVE
                    else ApprovalState.REJECTED
                )
                items.append(SessionAssembly(revision, count["total"], is_stale(
                    revision, session["package_revision"], approved, metadata,
                ), state, row["decision_count"], latest))
            return AssemblyPage(tuple(items), count["total"],
                                items[-1].revision.revision_number if len(rows) > limit else None)


def _candidate(row: Row) -> PackagingCandidate:
    asset = PackagingAsset(
        _id(row["packaging_asset_id"]), _id(row["event_id"]),
        None if row["stage_id"] is None else _id(row["stage_id"]), row["name"],
        PackagingAssetRole(row["role"]), row["asset_created_at"],
    )
    reference = (ExternalContent(row["content_key"], row["sha256"],
                                 row["byte_size"], row["media_type"])
                 if row["content_kind"] == "external_content" else
                 CompletedMediaAssetContent(_id(row["completed_media_asset_id"])))
    revision = PackagingAssetRevision(
        _id(row["revision_id"]), asset.id, row["revision_number"],
        RevisionContent(reference, row["measured_duration_microseconds"],
                        row["effective_from"], row["effective_until"]), row["created_at"],
    )
    return PackagingCandidate(asset, revision, ApprovalState.APPROVED)
