from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, cast

import psycopg
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.contexts.events import (
    BootstrapStatus,
    BusinessEvent,
    EventStageBootstrapRequest,
    EventStageBootstrapResult,
    ProgramExpectation,
    ProgramExpectationChange,
    ProgramExpectationChangeKind,
    ProgramExpectationFieldChange,
    ProgramExpectationLifecycle,
    ProgramExpectationReconciliation,
    ProgramExpectationSnapshot,
    Stage,
)
from app.contexts.production.event_mode_kernel.contracts import (
    AssociationAuthority,
    AssociationInputReference,
    AssociationStatus,
    BoundaryDecision,
    CompletionDecision,
    EpistemicKind,
    EventOperationalStatus,
    HumanCommandKind,
    MediaAssociation,
    MediaCandidate,
    MediaOperationalProjection,
    MediaRegistrationState,
    PackageReadyDecision,
    ReconciliationRun,
    ReconciliationStatus,
    RegisteredMediaAsset,
    ResourceObservation,
    Session,
    SessionActivityState,
    SessionBoundaryProposal,
    SessionOperationalProjection,
    SessionPackageState,
    StageOperationalStatus,
    StartSessionRequest,
)
from app.contexts.production.event_mode_kernel.program_reconciliation import (
    plan_program_reconciliation,
)
from app.contexts.production.event_mode_kernel.repository import (
    EventModeKernelRepository,
    KernelConflictError,
    KernelNotFoundError,
    KernelStorageUnavailableError,
)
from app.shared.ids import EntityId

type Row = dict[str, Any]


@dataclass(frozen=True, slots=True)
class _HumanCommandReplay:
    result_id: EntityId
    result_snapshot: Mapping[str, object] | None


def _digest(value: Mapping[str, object]) -> str:
    document = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(document.encode("utf-8")).hexdigest()


def _association_input(value: Mapping[str, object]) -> AssociationInputReference:
    revision = value.get("revision")
    return AssociationInputReference(
        record_type=str(value["record_type"]),
        record_id=str(value["record_id"]),
        revision=None if revision is None else int(str(revision)),
    )


def _association_inputs(
    values: tuple[AssociationInputReference, ...] | list[AssociationInputReference],
) -> list[dict[str, object]]:
    return [
        {
            "record_type": value.record_type,
            "record_id": value.record_id,
            "revision": value.revision,
        }
        for value in values
    ]


def _event(row: Row) -> BusinessEvent:
    return BusinessEvent(
        id=EntityId(str(row["event_id"])),
        key=cast(str, row["event_key"]),
        name=cast(str, row["name"]),
        external_references=cast(dict[str, str], row["external_references"]),
        revision=cast(int, row["revision"]),
        created_at=cast(datetime, row["created_at"]),
        updated_at=cast(datetime, row["updated_at"]),
    )


def _stage(row: Row, source_bindings: Mapping[str, str]) -> Stage:
    return Stage(
        id=EntityId(str(row["stage_id"])),
        event_id=EntityId(str(row["event_id"])),
        key=cast(str, row["stage_key"]),
        name=cast(str, row["name"]),
        source_bindings=source_bindings,
        external_references=cast(dict[str, str], row["external_references"]),
        revision=cast(int, row["revision"]),
        created_at=cast(datetime, row["created_at"]),
        updated_at=cast(datetime, row["updated_at"]),
    )


def _expectation(row: Row) -> ProgramExpectation:
    return ProgramExpectation(
        id=EntityId(str(row["expectation_id"])),
        event_id=EntityId(str(row["event_id"])),
        key=cast(str, row["expectation_key"]),
        stage_id=(
            None
            if row["expected_stage_id"] is None
            else EntityId(str(row["expected_stage_id"]))
        ),
        title=cast(str, row["title"]),
        speakers=cast(list[str], row["speakers"]),
        planned_start=cast(datetime | None, row["planned_start"]),
        planned_end=cast(datetime | None, row["planned_end"]),
        external_references=cast(dict[str, str], row["external_references"]),
        revision=cast(int, row["revision"]),
        recorded_at=cast(datetime, row["recorded_at"]),
        lifecycle_state=ProgramExpectationLifecycle(cast(str, row["lifecycle_state"])),
        synchronization_scope=cast(str | None, row["synchronization_scope"]),
        last_observed_at=cast(datetime, row["last_observed_at"]),
        lifecycle_changed_at=cast(datetime, row["lifecycle_changed_at"]),
    )


def _expectation_revision(row: Row) -> ProgramExpectation:
    revision_row = dict(row)
    revision_row["revision"] = revision_row["expectation_revision"]
    return _expectation(revision_row)


def _program_change_document(change: ProgramExpectationChange) -> dict[str, object]:
    return {
        "kind": change.kind.value,
        "expectation_id": change.expectation_id.value,
        "expectation_key": change.expectation_key,
        "title": change.title,
        "external_session_id": change.external_session_id,
        "fields": [
            {
                "field": field.field,
                "previous": field.previous,
                "current": field.current,
            }
            for field in change.fields
        ],
    }


def _program_change(value: Mapping[str, object]) -> ProgramExpectationChange:
    raw_fields = value.get("fields", ())
    fields = cast(list[Mapping[str, object]], raw_fields)
    return ProgramExpectationChange(
        kind=ProgramExpectationChangeKind(str(value["kind"])),
        expectation_id=EntityId(str(value["expectation_id"])),
        expectation_key=str(value["expectation_key"]),
        title=str(value["title"]),
        external_session_id=(
            None
            if value.get("external_session_id") is None
            else str(value["external_session_id"])
        ),
        fields=tuple(
            ProgramExpectationFieldChange(
                field=str(item["field"]),
                previous=(None if item.get("previous") is None else str(item["previous"])),
                current=(None if item.get("current") is None else str(item["current"])),
            )
            for item in fields
        ),
    )

def _session(row: Row) -> Session:
    return Session(
        id=EntityId(str(row["session_id"])),
        event_id=EntityId(str(row["event_id"])),
        stage_id=EntityId(str(row["stage_id"])),
        program_expectation_id=(
            None
            if row["program_expectation_id"] is None
            else EntityId(str(row["program_expectation_id"]))
        ),
        title=cast(str | None, row["title"]),
        activity_state=SessionActivityState(cast(str, row["activity_state"])),
        package_state=SessionPackageState(cast(str, row["package_state"])),
        authoritative_start=cast(datetime, row["authoritative_start"]),
        authoritative_end=cast(datetime | None, row["authoritative_end"]),
        package_revision=cast(int, row["package_revision"]),
        revision=cast(int, row["revision"]),
        created_by=EntityId(str(row["created_by"])),
        created_at=cast(datetime, row["created_at"]),
        updated_at=cast(datetime, row["updated_at"]),
    )


def _session_result_snapshot(session: Session) -> dict[str, object]:
    return {
        "schema_version": "session-result-v1",
        "session": {
            "session_id": session.id.value,
            "event_id": session.event_id.value,
            "stage_id": session.stage_id.value,
            "program_expectation_id": (
                None
                if session.program_expectation_id is None
                else session.program_expectation_id.value
            ),
            "title": session.title,
            "activity_state": session.activity_state.value,
            "package_state": session.package_state.value,
            "authoritative_start": session.authoritative_start.isoformat(),
            "authoritative_end": (
                None
                if session.authoritative_end is None
                else session.authoritative_end.isoformat()
            ),
            "package_revision": session.package_revision,
            "revision": session.revision,
            "created_by": session.created_by.value,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
        },
    }


def _session_from_result_snapshot(snapshot: Mapping[str, object]) -> Session:
    untyped_payload = snapshot.get("session")
    if snapshot.get("schema_version") != "session-result-v1" or not isinstance(
        untyped_payload, Mapping
    ):
        raise KernelConflictError("human_command_result_snapshot_invalid")
    payload = cast(Mapping[str, object], untyped_payload)

    def timestamp(name: str) -> datetime:
        value = payload[name]
        if not isinstance(value, str):
            raise KernelConflictError("human_command_result_snapshot_invalid")
        return datetime.fromisoformat(value)

    end = payload["authoritative_end"]
    expectation_id = payload["program_expectation_id"]
    return Session(
        id=EntityId(str(payload["session_id"])),
        event_id=EntityId(str(payload["event_id"])),
        stage_id=EntityId(str(payload["stage_id"])),
        program_expectation_id=(
            None if expectation_id is None else EntityId(str(expectation_id))
        ),
        title=None if payload["title"] is None else str(payload["title"]),
        activity_state=SessionActivityState(str(payload["activity_state"])),
        package_state=SessionPackageState(str(payload["package_state"])),
        authoritative_start=timestamp("authoritative_start"),
        authoritative_end=(
            None if end is None else datetime.fromisoformat(str(end))
        ),
        package_revision=int(str(payload["package_revision"])),
        revision=int(str(payload["revision"])),
        created_by=EntityId(str(payload["created_by"])),
        created_at=timestamp("created_at"),
        updated_at=timestamp("updated_at"),
    )


def _session_operational_projection(row: Row) -> SessionOperationalProjection:
    return SessionOperationalProjection(
        session_id=EntityId(str(row["session_id"])),
        activity_state=SessionActivityState(cast(str, row["activity_state"])),
        package_state=SessionPackageState(cast(str, row["package_state"])),
        package_revision=cast(int, row["package_revision"]),
        revision=cast(int, row["revision"]),
        authoritative_start=cast(datetime, row["authoritative_start"]),
        authoritative_end=cast(datetime | None, row["authoritative_end"]),
        program_expectation_id=(
            None
            if row["program_expectation_id"] is None
            else EntityId(str(row["program_expectation_id"]))
        ),
        program_expectation_title=cast(str | None, row.get("expectation_title")),
        program_expectation_revision=cast(int | None, row.get("expectation_revision")),
        program_expectation_planned_start=cast(
            datetime | None, row.get("expectation_planned_start")
        ),
        program_expectation_planned_end=cast(
            datetime | None, row.get("expectation_planned_end")
        ),
        completion_decision_id=(
            None
            if row.get("completion_decision_id") is None
            else EntityId(str(row["completion_decision_id"]))
        ),
        completion_actor_id=(
            None
            if row.get("completion_actor_id") is None
            else EntityId(str(row["completion_actor_id"]))
        ),
        completion_decided_at=cast(
            datetime | None, row.get("completion_decided_at")
        ),
    )


def _candidate(row: Row) -> MediaCandidate:
    return MediaCandidate(
        id=EntityId(str(row["candidate_id"])),
        proposed_asset_id=EntityId(str(row["proposed_asset_id"])),
        stage_id=EntityId(str(row["stage_id"])),
        source_binding_key=cast(str, row["source_binding_key"]),
        source_reference=cast(str, row["source_reference"]),
        discovered_at=cast(datetime, row["discovered_at"]),
        last_observed_at=cast(datetime, row["last_observed_at"]),
        state=MediaRegistrationState(cast(str, row["registration_state"])),
        revision=cast(int, row["revision"]),
    )


def _asset(row: Row) -> RegisteredMediaAsset:
    return RegisteredMediaAsset(
        id=EntityId(str(row["asset_id"])),
        candidate_id=EntityId(str(row["candidate_id"])),
        manifest_id=EntityId(str(row["manifest_id"])),
        stage_id=EntityId(str(row["stage_id"])),
        source_binding_key=cast(str, row["source_binding_key"]),
        registered_at=cast(datetime, row["registered_at"]),
        media_started_at=cast(datetime | None, row["media_started_at"]),
        media_ended_at=cast(datetime | None, row["media_ended_at"]),
    )


def _association(row: Row) -> MediaAssociation:
    return MediaAssociation(
        asset_id=EntityId(str(row["asset_id"])),
        status=AssociationStatus(cast(str, row["association_status"])),
        session_id=(
            None if row["session_id"] is None else EntityId(str(row["session_id"]))
        ),
        authority=AssociationAuthority(cast(str, row["authority"])),
        reason_codes=cast(list[str], row["reason_codes"]),
        evidence_ids=tuple(
            EntityId(value) for value in cast(list[str], row["evidence_ids"])
        ),
        revision=cast(int, row["revision"]),
        decided_at=cast(datetime, row["decided_at"]),
        actor_id=None if row["actor_id"] is None else EntityId(str(row["actor_id"])),
        operation_id=(
            None
            if row.get("operation_id") is None
            else EntityId(str(row["operation_id"]))
        ),
        policy_id=cast(str | None, row.get("policy_id")),
        policy_version=cast(str | None, row.get("policy_version")),
        input_references=tuple(
            _association_input(value)
            for value in cast(list[dict[str, object]], row["input_references"])
        ),
    )


def _reconciliation(row: Row) -> ReconciliationRun:
    return ReconciliationRun(
        id=EntityId(str(row["reconciliation_run_id"])),
        event_id=EntityId(str(row["event_id"])),
        status=ReconciliationStatus(cast(str, row["status"])),
        scope=cast(str, row["scope"]),
        started_at=cast(datetime, row["started_at"]),
        completed_at=cast(datetime | None, row["completed_at"]),
        candidates_seen=cast(int, row["candidates_seen"]),
        assets_registered=cast(int, row["assets_registered"]),
        failure_code=cast(str | None, row["failure_code"]),
    )


def _boundary_proposal(row: Row) -> SessionBoundaryProposal:
    return SessionBoundaryProposal(
        id=EntityId(str(row["boundary_proposal_id"])),
        session_id=EntityId(str(row["session_id"])),
        boundary_kind=cast(str, row["boundary_kind"]),
        boundary_at=cast(datetime, row["boundary_at"]),
        epistemic_kind=EpistemicKind(cast(str, row["epistemic_kind"])),
        proposer_id=EntityId(str(row["proposer_id"])),
        evidence_ids=tuple(
            EntityId(value) for value in cast(list[str], row["evidence_ids"])
        ),
        policy_id=cast(str, row["policy_id"]),
        policy_version=cast(str, row["policy_version"]),
        model_id=cast(str | None, row["model_id"]),
        model_version=cast(str | None, row["model_version"]),
        reason=cast(str, row["reason"]),
        proposed_at=cast(datetime, row["proposed_at"]),
    )


class PostgresEventModeKernelRepository(EventModeKernelRepository):
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def _connect(self) -> psycopg.Connection[Row]:
        return psycopg.Connection[Row].connect(self._dsn, row_factory=dict_row)

    @staticmethod
    def _reserve_human_command(
        connection: psycopg.Connection[Row],
        *,
        operation_id: EntityId,
        command_kind: HumanCommandKind,
        request_digest: str,
        result_id: EntityId,
        recorded_at: datetime,
    ) -> _HumanCommandReplay | None:
        inserted = connection.execute(
            """
            INSERT INTO stageflow.human_command_idempotency (
                operation_id, command_kind, request_digest, result_id, recorded_at
            ) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (operation_id) DO NOTHING
            RETURNING result_id
            """,
            (
                operation_id.value,
                command_kind.value,
                request_digest,
                result_id.value,
                recorded_at,
            ),
        ).fetchone()
        if inserted is not None:
            return None
        replay = connection.execute(
            """
            SELECT command_kind, request_digest, result_id, result_snapshot
            FROM stageflow.human_command_idempotency WHERE operation_id = %s
            """,
            (operation_id.value,),
        ).fetchone()
        assert replay is not None
        if (
            replay["command_kind"] != command_kind.value
            or replay["request_digest"] != request_digest
        ):
            raise KernelConflictError("human_command_operation_id_conflict")
        snapshot = cast(Mapping[str, object] | None, replay["result_snapshot"])
        return _HumanCommandReplay(
            result_id=EntityId(str(replay["result_id"])),
            result_snapshot=snapshot,
        )

    @staticmethod
    def _record_session_result(
        connection: psycopg.Connection[Row],
        *,
        operation_id: EntityId,
        session: Session,
    ) -> None:
        updated = connection.execute(
            """
            UPDATE stageflow.human_command_idempotency
            SET result_snapshot = %s
            WHERE operation_id = %s
            """,
            (Jsonb(_session_result_snapshot(session)), operation_id.value),
        )
        if updated.rowcount != 1:
            raise KernelConflictError("human_command_result_snapshot_missing")

    def bootstrap(self, request: EventStageBootstrapRequest) -> EventStageBootstrapResult:
        for attempt in range(2):
            try:
                return self._bootstrap_once(request)
            except UniqueViolation:
                if attempt == 1:
                    raise KernelConflictError("concurrent_bootstrap_conflict") from None
            except psycopg.OperationalError as exc:
                raise KernelStorageUnavailableError("postgresql_unavailable") from exc
        raise AssertionError("unreachable")

    def _bootstrap_once(
        self, request: EventStageBootstrapRequest
    ) -> EventStageBootstrapResult:
        request_digest = _digest(
            {
                "event_key": request.event_key,
                "event_name": request.event_name,
                "external_references": dict(request.external_references),
                "stages": [
                    {
                        "key": item.key,
                        "name": item.name,
                        "sources": dict(item.source_bindings),
                        "external_references": dict(item.external_references),
                    }
                    for item in request.stages
                ],
                "actor_id": request.actor_id.value,
            }
        )
        with self._connect() as connection:
            operation = connection.execute(
                """
                SELECT event_id, request_digest, result_status
                FROM stageflow.event_stage_bootstrap_operation
                WHERE operation_id = %s
                """,
                (request.operation_id.value,),
            ).fetchone()
            if operation is not None:
                if operation["request_digest"] != request_digest:
                    raise KernelConflictError("bootstrap_operation_id_conflict")
                event = self._get_event(connection, EntityId(str(operation["event_id"])))
                assert event is not None
                return EventStageBootstrapResult(
                    status=BootstrapStatus(cast(str, operation["result_status"])),
                    event=event,
                    stages=self._list_stages(connection, event.id),
                )

            event_row = connection.execute(
                "SELECT * FROM stageflow.business_event WHERE event_key = %s FOR UPDATE",
                (request.event_key,),
            ).fetchone()
            created = event_row is None
            changed = False
            if event_row is None:
                event_id = EntityId.new()
                connection.execute(
                    """
                    INSERT INTO stageflow.business_event (
                        event_id, event_key, name, external_references, revision,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, 1, %s, %s)
                    """,
                    (
                        event_id.value,
                        request.event_key,
                        request.event_name,
                        Jsonb(dict(request.external_references)),
                        request.requested_at,
                        request.requested_at,
                    ),
                )
            else:
                event_id = EntityId(str(event_row["event_id"]))
                if (
                    event_row["name"] != request.event_name
                    or event_row["external_references"]
                    != dict(request.external_references)
                ):
                    connection.execute(
                        """
                        UPDATE stageflow.business_event
                        SET name = %s, external_references = %s,
                            revision = revision + 1, updated_at = %s
                        WHERE event_id = %s
                        """,
                        (
                            request.event_name,
                            Jsonb(dict(request.external_references)),
                            request.requested_at,
                            event_id.value,
                        ),
                    )
                    changed = True

            existing_stage_rows = connection.execute(
                "SELECT * FROM stageflow.stage WHERE event_id = %s FOR UPDATE",
                (event_id.value,),
            ).fetchall()
            existing_by_key = {
                cast(str, row["stage_key"]): row for row in existing_stage_rows
            }
            requested_keys = {item.key for item in request.stages}
            if set(existing_by_key) - requested_keys:
                raise KernelConflictError("stage_removal_not_permitted")

            existing_sources = connection.execute(
                """
                SELECT b.source_binding_key, b.stage_id
                FROM stageflow.stage_source_binding b
                JOIN stageflow.stage s ON s.stage_id = b.stage_id
                WHERE s.event_id = %s
                FOR UPDATE OF b
                """,
                (event_id.value,),
            ).fetchall()
            source_owners = {
                cast(str, row["source_binding_key"]): str(row["stage_id"])
                for row in existing_sources
            }
            for definition in request.stages:
                existing = existing_by_key.get(definition.key)
                stage_id = None if existing is None else str(existing["stage_id"])
                for source_key in definition.source_bindings:
                    owner = source_owners.get(source_key)
                    if owner is not None and owner != stage_id:
                        raise KernelConflictError("source_binding_stage_conflict")

            for definition in request.stages:
                existing = existing_by_key.get(definition.key)
                if existing is None:
                    stage_id = EntityId.new()
                    connection.execute(
                        """
                        INSERT INTO stageflow.stage (
                            stage_id, event_id, stage_key, name, external_references,
                            revision, created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, 1, %s, %s)
                        """,
                        (
                            stage_id.value,
                            event_id.value,
                            definition.key,
                            definition.name,
                            Jsonb(dict(definition.external_references)),
                            request.requested_at,
                            request.requested_at,
                        ),
                    )
                    if not created:
                        changed = True
                else:
                    stage_id = EntityId(str(existing["stage_id"]))
                    existing_binding_rows = connection.execute(
                        """
                        SELECT source_binding_key, source_reference
                        FROM stageflow.stage_source_binding WHERE stage_id = %s
                        """,
                        (stage_id.value,),
                    ).fetchall()
                    existing_bindings = {
                        cast(str, row["source_binding_key"]): cast(
                            str, row["source_reference"]
                        )
                        for row in existing_binding_rows
                    }
                    if set(existing_bindings) - set(definition.source_bindings):
                        raise KernelConflictError("source_binding_removal_not_permitted")
                    if (
                        existing["name"] != definition.name
                        or existing["external_references"]
                        != dict(definition.external_references)
                        or existing_bindings != dict(definition.source_bindings)
                    ):
                        connection.execute(
                            """
                            UPDATE stageflow.stage
                            SET name = %s, external_references = %s,
                                revision = revision + 1, updated_at = %s
                            WHERE stage_id = %s
                            """,
                            (
                                definition.name,
                                Jsonb(dict(definition.external_references)),
                                request.requested_at,
                                stage_id.value,
                            ),
                        )
                        changed = True
                for source_key, source_reference in definition.source_bindings.items():
                    connection.execute(
                        """
                        INSERT INTO stageflow.stage_source_binding (
                            source_binding_key, stage_id, source_reference, revision, updated_at
                        ) VALUES (%s, %s, %s, 1, %s)
                        ON CONFLICT (source_binding_key) DO UPDATE
                        SET source_reference = EXCLUDED.source_reference,
                            revision = stageflow.stage_source_binding.revision + 1,
                            updated_at = EXCLUDED.updated_at
                        WHERE stageflow.stage_source_binding.stage_id = EXCLUDED.stage_id
                          AND stageflow.stage_source_binding.source_reference
                              IS DISTINCT FROM EXCLUDED.source_reference
                        """,
                        (
                            source_key,
                            stage_id.value,
                            source_reference,
                            request.requested_at,
                        ),
                    )

            status = (
                BootstrapStatus.CREATED
                if created
                else BootstrapStatus.UPDATED
                if changed
                else BootstrapStatus.RESOLVED
            )
            connection.execute(
                """
                INSERT INTO stageflow.event_stage_bootstrap_operation (
                    operation_id, event_id, request_digest, result_status, applied_at
                ) VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    request.operation_id.value,
                    event_id.value,
                    request_digest,
                    status.value,
                    request.requested_at,
                ),
            )
            event = self._get_event(connection, event_id)
            assert event is not None
            return EventStageBootstrapResult(
                status=status,
                event=event,
                stages=self._list_stages(connection, event_id),
            )

    def _get_event(
        self, connection: psycopg.Connection[Row], event_id: EntityId
    ) -> BusinessEvent | None:
        row = connection.execute(
            "SELECT * FROM stageflow.business_event WHERE event_id = %s",
            (event_id.value,),
        ).fetchone()
        return None if row is None else _event(row)

    def get_event_by_key(self, event_key: str) -> BusinessEvent | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM stageflow.business_event WHERE event_key = %s",
                    (event_key,),
                ).fetchone()
                return None if row is None else _event(row)
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def _list_stages(
        self, connection: psycopg.Connection[Row], event_id: EntityId
    ) -> tuple[Stage, ...]:
        rows = connection.execute(
            "SELECT * FROM stageflow.stage WHERE event_id = %s ORDER BY stage_key",
            (event_id.value,),
        ).fetchall()
        stages: list[Stage] = []
        for row in rows:
            bindings = connection.execute(
                """
                SELECT source_binding_key, source_reference
                FROM stageflow.stage_source_binding
                WHERE stage_id = %s ORDER BY source_binding_key
                """,
                (str(row["stage_id"]),),
            ).fetchall()
            stages.append(
                _stage(
                    row,
                    {
                        cast(str, item["source_binding_key"]): cast(
                            str, item["source_reference"]
                        )
                        for item in bindings
                    },
                )
            )
        return tuple(stages)

    def list_stages(self, event_id: EntityId) -> tuple[Stage, ...]:
        try:
            with self._connect() as connection:
                return self._list_stages(connection, event_id)
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def get_stage_by_key(self, event_id: EntityId, stage_key: str) -> Stage | None:
        return next(
            (stage for stage in self.list_stages(event_id) if stage.key == stage_key), None
        )

    @staticmethod
    def _write_program_expectation(
        connection: Any,
        expectation: ProgramExpectation,
        *,
        write_revision: bool,
    ) -> None:
        connection.execute(
            """
            INSERT INTO stageflow.program_expectation (
                expectation_id, event_id, expectation_key, expected_stage_id,
                title, speakers, planned_start, planned_end, external_references,
                revision, recorded_at, lifecycle_state, synchronization_scope,
                last_observed_at, lifecycle_changed_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (expectation_id) DO UPDATE SET
                event_id = EXCLUDED.event_id,
                expectation_key = EXCLUDED.expectation_key,
                expected_stage_id = EXCLUDED.expected_stage_id,
                title = EXCLUDED.title,
                speakers = EXCLUDED.speakers,
                planned_start = EXCLUDED.planned_start,
                planned_end = EXCLUDED.planned_end,
                external_references = EXCLUDED.external_references,
                revision = EXCLUDED.revision,
                recorded_at = EXCLUDED.recorded_at,
                lifecycle_state = EXCLUDED.lifecycle_state,
                synchronization_scope = EXCLUDED.synchronization_scope,
                last_observed_at = EXCLUDED.last_observed_at,
                lifecycle_changed_at = EXCLUDED.lifecycle_changed_at
            """,
            (
                expectation.id.value,
                expectation.event_id.value,
                expectation.key,
                None if expectation.stage_id is None else expectation.stage_id.value,
                expectation.title,
                Jsonb(list(expectation.speakers)),
                expectation.planned_start,
                expectation.planned_end,
                Jsonb(dict(expectation.external_references)),
                expectation.revision,
                expectation.recorded_at,
                expectation.lifecycle_state.value,
                expectation.synchronization_scope,
                expectation.last_observed_at,
                expectation.lifecycle_changed_at,
            ),
        )
        if not write_revision:
            return
        connection.execute(
            """
            INSERT INTO stageflow.program_expectation_revision (
                revision_id, expectation_id, expectation_revision,
                expected_stage_id, title, speakers, planned_start, planned_end,
                external_references, recorded_at, lifecycle_state,
                synchronization_scope, last_observed_at, lifecycle_changed_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                EntityId.new().value,
                expectation.id.value,
                expectation.revision,
                None if expectation.stage_id is None else expectation.stage_id.value,
                expectation.title,
                Jsonb(list(expectation.speakers)),
                expectation.planned_start,
                expectation.planned_end,
                Jsonb(dict(expectation.external_references)),
                expectation.recorded_at,
                expectation.lifecycle_state.value,
                expectation.synchronization_scope,
                expectation.last_observed_at,
                expectation.lifecycle_changed_at,
            ),
        )

    def put_program_expectation(self, expectation: ProgramExpectation) -> ProgramExpectation:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT * FROM stageflow.program_expectation
                    WHERE event_id = %s AND expectation_key = %s FOR UPDATE
                    """,
                    (expectation.event_id.value, expectation.key),
                ).fetchone()
                if row is None:
                    saved = replace(expectation, revision=1)
                else:
                    existing = _expectation(row)
                    saved = replace(
                        expectation,
                        id=existing.id,
                        revision=existing.revision + 1,
                    )
                self._write_program_expectation(
                    connection, saved, write_revision=True
                )
                return saved
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def get_program_expectation(self, expectation_id: EntityId) -> ProgramExpectation | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM stageflow.program_expectation WHERE expectation_id = %s",
                    (expectation_id.value,),
                ).fetchone()
                return None if row is None else _expectation(row)
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def list_program_expectations(
        self, event_id: EntityId
    ) -> tuple[ProgramExpectation, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT * FROM stageflow.program_expectation
                    WHERE event_id = %s
                    ORDER BY planned_start ASC NULLS LAST, expectation_key ASC
                    """,
                    (event_id.value,),
                ).fetchall()
                return tuple(_expectation(row) for row in rows)
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def list_program_expectation_revisions(
        self, expectation_id: EntityId
    ) -> tuple[ProgramExpectation, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT
                        expectation.event_id,
                        expectation.expectation_key,
                        revision.expectation_id,
                        revision.expectation_revision,
                        revision.expected_stage_id,
                        revision.title,
                        revision.speakers,
                        revision.planned_start,
                        revision.planned_end,
                        revision.external_references,
                        revision.recorded_at,
                        revision.lifecycle_state,
                        revision.synchronization_scope,
                        revision.last_observed_at,
                        revision.lifecycle_changed_at
                    FROM stageflow.program_expectation_revision revision
                    JOIN stageflow.program_expectation expectation
                      ON expectation.expectation_id = revision.expectation_id
                    WHERE revision.expectation_id = %s
                    ORDER BY revision.expectation_revision
                    """,
                    (expectation_id.value,),
                ).fetchall()
                return tuple(_expectation_revision(row) for row in rows)
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def reconcile_program_expectations(
        self, snapshot: ProgramExpectationSnapshot
    ) -> ProgramExpectationReconciliation:
        try:
            with self._connect() as connection:
                stage = connection.execute(
                    """
                    SELECT event_id FROM stageflow.stage
                    WHERE stage_id = %s FOR UPDATE
                    """,
                    (snapshot.stage_id.value,),
                ).fetchone()
                if stage is None or str(stage["event_id"]) != snapshot.event_id.value:
                    raise KernelConflictError("program_snapshot_stage_event_mismatch")
                rows = connection.execute(
                    """
                    SELECT * FROM stageflow.program_expectation
                    WHERE event_id = %s FOR UPDATE
                    """,
                    (snapshot.event_id.value,),
                ).fetchall()
                plan = plan_program_reconciliation(
                    (_expectation(row) for row in rows), snapshot
                )
                for mutation in plan.mutations:
                    self._write_program_expectation(
                        connection,
                        mutation.expectation,
                        write_revision=mutation.write_revision,
                    )
                result = plan.result
                connection.execute(
                    """
                    INSERT INTO stageflow.program_expectation_sync_snapshot (
                        event_id, expected_stage_id, synchronization_scope, provider,
                        synchronized_at, observed, added, changed, unchanged,
                        withdrawn, restored, change_summary, changes_truncated
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (event_id, expected_stage_id, synchronization_scope)
                    DO UPDATE SET
                        provider = EXCLUDED.provider,
                        synchronized_at = EXCLUDED.synchronized_at,
                        observed = EXCLUDED.observed,
                        added = EXCLUDED.added,
                        changed = EXCLUDED.changed,
                        unchanged = EXCLUDED.unchanged,
                        withdrawn = EXCLUDED.withdrawn,
                        restored = EXCLUDED.restored,
                        change_summary = EXCLUDED.change_summary,
                        changes_truncated = EXCLUDED.changes_truncated
                    """,
                    (
                        result.event_id.value,
                        result.stage_id.value,
                        result.synchronization_scope,
                        result.provider,
                        result.synchronized_at,
                        result.observed,
                        result.added,
                        result.changed,
                        result.unchanged,
                        result.withdrawn,
                        result.restored,
                        Jsonb([_program_change_document(item) for item in result.changes]),
                        result.changes_truncated,
                    ),
                )
                return result
        except psycopg.Error as exc:
            raise KernelStorageUnavailableError(
                "postgresql_reconciliation_failed"
            ) from exc

    def get_latest_program_reconciliation(
        self, event_id: EntityId, stage_id: EntityId
    ) -> ProgramExpectationReconciliation | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT * FROM stageflow.program_expectation_sync_snapshot
                    WHERE event_id = %s AND expected_stage_id = %s
                    ORDER BY synchronized_at DESC, synchronization_scope ASC
                    LIMIT 1
                    """,
                    (event_id.value, stage_id.value),
                ).fetchone()
                if row is None:
                    return None
                expectations = connection.execute(
                    """
                    SELECT * FROM stageflow.program_expectation
                    WHERE event_id = %s
                      AND expected_stage_id = %s
                      AND synchronization_scope = %s
                      AND lifecycle_state = 'current'
                    ORDER BY planned_start ASC NULLS LAST, expectation_key ASC
                    """,
                    (event_id.value, stage_id.value, row["synchronization_scope"]),
                ).fetchall()
                raw_changes = cast(list[Mapping[str, object]], row["change_summary"])
                return ProgramExpectationReconciliation(
                    event_id=event_id,
                    stage_id=stage_id,
                    provider=cast(str, row["provider"]),
                    synchronization_scope=cast(str, row["synchronization_scope"]),
                    synchronized_at=cast(datetime, row["synchronized_at"]),
                    observed=cast(int, row["observed"]),
                    added=cast(int, row["added"]),
                    changed=cast(int, row["changed"]),
                    unchanged=cast(int, row["unchanged"]),
                    withdrawn=cast(int, row["withdrawn"]),
                    restored=cast(int, row["restored"]),
                    expectations=tuple(_expectation(item) for item in expectations),
                    changes=tuple(_program_change(item) for item in raw_changes),
                    changes_truncated=cast(bool, row["changes_truncated"]),
                )
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def start_session(self, request: StartSessionRequest) -> Session:
        request_digest = _digest(
            {
                "event_id": request.event_id.value,
                "stage_id": request.stage_id.value,
                "expectation_id": (
                    None
                    if request.program_expectation_id is None
                    else request.program_expectation_id.value
                ),
                "actor_id": request.actor_id.value,
                "authoritative_start": request.authoritative_start.isoformat(),
                "title": request.title,
            }
        )
        try:
            with self._connect() as connection:
                replay = connection.execute(
                    """
                    SELECT operation.session_id, operation.request_digest,
                           command.result_snapshot
                    FROM stageflow.session_start_operation operation
                    LEFT JOIN stageflow.human_command_idempotency command
                      ON command.operation_id = operation.operation_id
                    WHERE operation.operation_id = %s
                    """,
                    (request.operation_id.value,),
                ).fetchone()
                if replay is not None:
                    if replay["request_digest"] != request_digest:
                        raise KernelConflictError("session_start_operation_id_conflict")
                    snapshot = cast(
                        Mapping[str, object] | None, replay["result_snapshot"]
                    )
                    if snapshot is not None:
                        return _session_from_result_snapshot(snapshot)
                    row = connection.execute(
                        "SELECT * FROM stageflow.session WHERE session_id = %s",
                        (str(replay["session_id"]),),
                    ).fetchone()
                    assert row is not None
                    return _session(row)
                session_id = EntityId.new()
                command_replay_id = self._reserve_human_command(
                    connection,
                    operation_id=request.operation_id,
                    command_kind=HumanCommandKind.SESSION_START,
                    request_digest=request_digest,
                    result_id=session_id,
                    recorded_at=request.requested_at,
                )
                if command_replay_id is not None:
                    if command_replay_id.result_snapshot is not None:
                        return _session_from_result_snapshot(
                            command_replay_id.result_snapshot
                        )
                    row = connection.execute(
                        "SELECT * FROM stageflow.session WHERE session_id = %s",
                        (command_replay_id.result_id.value,),
                    ).fetchone()
                    assert row is not None
                    return _session(row)
                stage = connection.execute(
                    "SELECT event_id FROM stageflow.stage WHERE stage_id = %s FOR SHARE",
                    (request.stage_id.value,),
                ).fetchone()
                if stage is None or str(stage["event_id"]) != request.event_id.value:
                    raise KernelConflictError("stage_event_mismatch")
                if request.program_expectation_id is not None:
                    expectation = connection.execute(
                        """
                        SELECT event_id, lifecycle_state
                        FROM stageflow.program_expectation
                        WHERE expectation_id = %s
                        """,
                        (request.program_expectation_id.value,),
                    ).fetchone()
                    if (
                        expectation is None
                        or str(expectation["event_id"]) != request.event_id.value
                    ):
                        raise KernelConflictError("program_expectation_event_mismatch")
                    if expectation["lifecycle_state"] == "withdrawn":
                        raise KernelConflictError("program_expectation_withdrawn")
                connection.execute(
                    """
                    INSERT INTO stageflow.session (
                        session_id, event_id, stage_id, program_expectation_id, title,
                        activity_state, package_state, authoritative_start,
                        authoritative_end, package_revision, revision, created_by,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, 'presentation_active',
                              'assembling', %s, NULL, 1, 1, %s, %s, %s)
                    """,
                    (
                        session_id.value,
                        request.event_id.value,
                        request.stage_id.value,
                        None
                        if request.program_expectation_id is None
                        else request.program_expectation_id.value,
                        request.title,
                        request.authoritative_start,
                        request.actor_id.value,
                        request.requested_at,
                        request.requested_at,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO stageflow.session_boundary_history (
                        boundary_decision_id, session_id, boundary_kind, boundary_at,
                        epistemic_kind, actor_id, reason, decided_at,
                        resulting_session_revision, operation_id
                    ) VALUES (%s, %s, 'start', %s, 'declared', %s,
                              'human_session_start', %s, 1, %s)
                    """,
                    (
                        EntityId.new().value,
                        session_id.value,
                        request.authoritative_start,
                        request.actor_id.value,
                        request.requested_at,
                        request.operation_id.value,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO stageflow.session_start_operation (
                        operation_id, session_id, request_digest, applied_at
                    ) VALUES (%s, %s, %s, %s)
                    """,
                    (
                        request.operation_id.value,
                        session_id.value,
                        request_digest,
                        request.requested_at,
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM stageflow.session WHERE session_id = %s",
                    (session_id.value,),
                ).fetchone()
                assert row is not None
                saved = _session(row)
                self._record_session_result(
                    connection,
                    operation_id=request.operation_id,
                    session=saved,
                )
                return saved
        except UniqueViolation as exc:
            raise KernelConflictError("stage_already_has_active_session") from exc
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def get_session(self, session_id: EntityId) -> Session | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM stageflow.session WHERE session_id = %s",
                    (session_id.value,),
                ).fetchone()
                return None if row is None else _session(row)
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def list_sessions_for_stage(self, stage_id: EntityId) -> tuple[Session, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT * FROM stageflow.session WHERE stage_id = %s
                    ORDER BY authoritative_start, session_id
                    """,
                    (stage_id.value,),
                ).fetchall()
                return tuple(_session(row) for row in rows)
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def correct_boundary(
        self,
        *,
        session_id: EntityId,
        boundary_kind: str,
        boundary_at: datetime,
        actor_id: EntityId,
        reason: str,
        decided_at: datetime,
        operation_id: EntityId,
        request_digest: str,
    ) -> tuple[Session, BoundaryDecision]:
        try:
            with self._connect() as connection:
                decision_id = EntityId.new()
                replay_id = self._reserve_human_command(
                    connection,
                    operation_id=operation_id,
                    command_kind=HumanCommandKind.SESSION_BOUNDARY_CORRECTION,
                    request_digest=request_digest,
                    result_id=decision_id,
                    recorded_at=decided_at,
                )
                if replay_id is not None:
                    replay = connection.execute(
                        """
                        SELECT * FROM stageflow.session_boundary_history
                        WHERE boundary_decision_id = %s
                        """,
                        (replay_id.result_id.value,),
                    ).fetchone()
                    assert replay is not None
                    if replay_id.result_snapshot is not None:
                        replayed_session = _session_from_result_snapshot(
                            replay_id.result_snapshot
                        )
                    else:
                        session_row = connection.execute(
                            "SELECT * FROM stageflow.session WHERE session_id = %s",
                            (str(replay["session_id"]),),
                        ).fetchone()
                        assert session_row is not None
                        replayed_session = _session(session_row)
                    return replayed_session, BoundaryDecision(
                        id=replay_id.result_id,
                        session_id=EntityId(str(replay["session_id"])),
                        boundary_kind=cast(str, replay["boundary_kind"]),
                        boundary_at=cast(datetime, replay["boundary_at"]),
                        authority=EpistemicKind(cast(str, replay["epistemic_kind"])),
                        actor_id=EntityId(str(replay["actor_id"])),
                        reason=cast(str, replay["reason"]),
                        decided_at=cast(datetime, replay["decided_at"]),
                        resulting_session_revision=cast(
                            int, replay["resulting_session_revision"]
                        ),
                        operation_id=operation_id,
                    )
                row = connection.execute(
                    "SELECT * FROM stageflow.session WHERE session_id = %s FOR UPDATE",
                    (session_id.value,),
                ).fetchone()
                if row is None:
                    raise KernelNotFoundError("session_not_found")
                current = _session(row)
                start = boundary_at if boundary_kind == "start" else current.authoritative_start
                end = boundary_at if boundary_kind == "end" else current.authoritative_end
                if boundary_kind not in {"start", "end"}:
                    raise ValueError("boundary_kind must be start or end")
                if end is not None and end < start:
                    raise KernelConflictError("session_boundary_order_conflict")
                package_revision = current.package_revision
                package_state = current.package_state
                if package_state is SessionPackageState.COMPLETE:
                    package_revision += 1
                    package_state = SessionPackageState.CORRECTION_REQUIRED
                activity_state = (
                    SessionActivityState.PRESENTATION_ENDED
                    if boundary_kind == "end"
                    else current.activity_state
                )
                revision = current.revision + 1
                connection.execute(
                    """
                    UPDATE stageflow.session SET
                        authoritative_start = %s, authoritative_end = %s,
                        activity_state = %s, package_state = %s,
                        package_revision = %s, revision = %s, updated_at = %s
                    WHERE session_id = %s
                    """,
                    (
                        start,
                        end,
                        activity_state.value,
                        package_state.value,
                        package_revision,
                        revision,
                        decided_at,
                        session_id.value,
                    ),
                )
                decision = BoundaryDecision(
                    id=decision_id,
                    session_id=session_id,
                    boundary_kind=boundary_kind,
                    boundary_at=boundary_at,
                    authority=EpistemicKind.DECLARED,
                    actor_id=actor_id,
                    reason=reason,
                    decided_at=decided_at,
                    resulting_session_revision=revision,
                    operation_id=operation_id,
                )
                connection.execute(
                    """
                    INSERT INTO stageflow.session_boundary_history (
                        boundary_decision_id, session_id, boundary_kind, boundary_at,
                        epistemic_kind, actor_id, reason, decided_at,
                        resulting_session_revision, operation_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        decision.id.value,
                        session_id.value,
                        boundary_kind,
                        boundary_at,
                        decision.authority.value,
                        actor_id.value,
                        reason,
                        decided_at,
                        revision,
                        operation_id.value,
                    ),
                )
                updated = connection.execute(
                    "SELECT * FROM stageflow.session WHERE session_id = %s",
                    (session_id.value,),
                ).fetchone()
                assert updated is not None
                saved = _session(updated)
                self._record_session_result(
                    connection,
                    operation_id=operation_id,
                    session=saved,
                )
                return saved, decision
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def put_boundary_proposal(
        self, proposal: SessionBoundaryProposal
    ) -> SessionBoundaryProposal:
        try:
            with self._connect() as connection:
                session = connection.execute(
                    "SELECT 1 FROM stageflow.session WHERE session_id = %s",
                    (proposal.session_id.value,),
                ).fetchone()
                if session is None:
                    raise KernelNotFoundError("session_not_found")
                row = connection.execute(
                    """
                    SELECT * FROM stageflow.session_boundary_proposal
                    WHERE boundary_proposal_id = %s FOR UPDATE
                    """,
                    (proposal.id.value,),
                ).fetchone()
                if row is not None:
                    existing = _boundary_proposal(row)
                    if existing != proposal:
                        raise KernelConflictError("boundary_proposal_identity_conflict")
                    return existing
                connection.execute(
                    """
                    INSERT INTO stageflow.session_boundary_proposal (
                        boundary_proposal_id, session_id, boundary_kind, boundary_at,
                        epistemic_kind, proposer_id, evidence_ids, policy_id,
                        policy_version, model_id, model_version, reason, proposed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        proposal.id.value,
                        proposal.session_id.value,
                        proposal.boundary_kind,
                        proposal.boundary_at,
                        proposal.epistemic_kind.value,
                        proposal.proposer_id.value,
                        Jsonb([value.value for value in proposal.evidence_ids]),
                        proposal.policy_id,
                        proposal.policy_version,
                        proposal.model_id,
                        proposal.model_version,
                        proposal.reason,
                        proposal.proposed_at,
                    ),
                )
                return proposal
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def list_boundary_proposals(
        self, session_id: EntityId, *, limit: int = 100
    ) -> tuple[SessionBoundaryProposal, ...]:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT * FROM stageflow.session_boundary_proposal
                    WHERE session_id = %s
                    ORDER BY proposed_at DESC, boundary_proposal_id DESC
                    LIMIT %s
                    """,
                    (session_id.value, limit),
                ).fetchall()
                return tuple(_boundary_proposal(row) for row in rows)
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def register_candidate(self, candidate: MediaCandidate) -> MediaCandidate:
        try:
            with self._connect() as connection:
                binding = connection.execute(
                    """
                    SELECT stage_id FROM stageflow.stage_source_binding
                    WHERE source_binding_key = %s
                    """,
                    (candidate.source_binding_key,),
                ).fetchone()
                if (
                    binding is None
                    or str(binding["stage_id"]) != candidate.stage_id.value
                ):
                    raise KernelConflictError("candidate_source_stage_conflict")
                row = connection.execute(
                    "SELECT * FROM stageflow.media_candidate WHERE candidate_id = %s FOR UPDATE",
                    (candidate.id.value,),
                ).fetchone()
                if row is None:
                    connection.execute(
                        """
                        INSERT INTO stageflow.media_candidate (
                            candidate_id, proposed_asset_id, stage_id, source_binding_key,
                            source_reference, discovered_at, last_observed_at,
                            registration_state, revision
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1)
                        """,
                        (
                            candidate.id.value,
                            candidate.proposed_asset_id.value,
                            candidate.stage_id.value,
                            candidate.source_binding_key,
                            candidate.source_reference,
                            candidate.discovered_at,
                            candidate.last_observed_at,
                            candidate.state.value,
                        ),
                    )
                else:
                    existing = _candidate(row)
                    if (
                        existing.proposed_asset_id != candidate.proposed_asset_id
                        or existing.stage_id != candidate.stage_id
                        or existing.source_binding_key != candidate.source_binding_key
                        or existing.source_reference != candidate.source_reference
                    ):
                        raise KernelConflictError("candidate_identity_conflict")
                    if candidate.last_observed_at > existing.last_observed_at:
                        connection.execute(
                            """
                            UPDATE stageflow.media_candidate
                            SET last_observed_at = GREATEST(last_observed_at, %s),
                                revision = revision + 1
                            WHERE candidate_id = %s
                            """,
                            (
                                candidate.last_observed_at,
                                candidate.id.value,
                            ),
                        )
                saved = connection.execute(
                    "SELECT * FROM stageflow.media_candidate WHERE candidate_id = %s",
                    (candidate.id.value,),
                ).fetchone()
                assert saved is not None
                return _candidate(saved)
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def get_candidate(self, candidate_id: EntityId) -> MediaCandidate | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM stageflow.media_candidate WHERE candidate_id = %s",
                    (candidate_id.value,),
                ).fetchone()
                return None if row is None else _candidate(row)
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def record_observation(self, observation: ResourceObservation) -> ResourceObservation:
        try:
            with self._connect() as connection:
                existing_row = connection.execute(
                    """
                    SELECT observation_id, candidate_id, observation_kind,
                           epistemic_kind, observed_at, recorded_at, facts
                    FROM stageflow.media_resource_observation
                    WHERE observation_id = %s FOR UPDATE
                    """,
                    (observation.id.value,),
                ).fetchone()
                if existing_row is not None:
                    existing = ResourceObservation(
                        id=EntityId(str(existing_row["observation_id"])),
                        candidate_id=EntityId(str(existing_row["candidate_id"])),
                        observation_kind=cast(str, existing_row["observation_kind"]),
                        epistemic_kind=EpistemicKind(existing_row["epistemic_kind"]),
                        observed_at=cast(datetime, existing_row["observed_at"]),
                        recorded_at=cast(datetime, existing_row["recorded_at"]),
                        facts=cast(dict[str, object], existing_row["facts"]),
                    )
                    if existing != observation:
                        raise KernelConflictError("observation_identity_conflict")
                    return existing
                connection.execute(
                    """
                    INSERT INTO stageflow.media_resource_observation (
                        observation_id, candidate_id, observation_kind, epistemic_kind,
                        observed_at, recorded_at, facts
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        observation.id.value,
                        observation.candidate_id.value,
                        observation.observation_kind,
                        observation.epistemic_kind.value,
                        observation.observed_at,
                        observation.recorded_at,
                        Jsonb(dict(observation.facts)),
                    ),
                )
                connection.execute(
                    """
                    UPDATE stageflow.media_candidate
                    SET last_observed_at = GREATEST(last_observed_at, %s),
                        revision = revision + 1
                    WHERE candidate_id = %s
                    """,
                    (observation.observed_at, observation.candidate_id.value),
                )
                return observation
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def list_observations(self, candidate_id: EntityId) -> tuple[ResourceObservation, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT observation_id, candidate_id, observation_kind,
                           epistemic_kind, observed_at, recorded_at, facts
                    FROM stageflow.media_resource_observation
                    WHERE candidate_id = %s
                    ORDER BY observed_at, observation_id
                    """,
                    (candidate_id.value,),
                ).fetchall()
                return tuple(
                    ResourceObservation(
                        id=EntityId(str(row["observation_id"])),
                        candidate_id=EntityId(str(row["candidate_id"])),
                        observation_kind=cast(str, row["observation_kind"]),
                        epistemic_kind=EpistemicKind(cast(str, row["epistemic_kind"])),
                        observed_at=cast(datetime, row["observed_at"]),
                        recorded_at=cast(datetime, row["recorded_at"]),
                        facts=cast(dict[str, object], row["facts"]),
                    )
                    for row in rows
                )
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def mark_candidate_state(
        self, candidate_id: EntityId, state: str, at: datetime
    ) -> MediaCandidate:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    UPDATE stageflow.media_candidate SET
                        registration_state = %s,
                        last_observed_at = GREATEST(last_observed_at, %s),
                        revision = revision + 1
                    WHERE candidate_id = %s RETURNING *
                    """,
                    (state, at, candidate_id.value),
                ).fetchone()
                if row is None:
                    raise KernelNotFoundError("candidate_not_found")
                return _candidate(row)
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def register_asset(self, asset: RegisteredMediaAsset) -> RegisteredMediaAsset:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT * FROM stageflow.completed_media_asset_registry
                    WHERE asset_id = %s FOR UPDATE
                    """,
                    (asset.id.value,),
                ).fetchone()
                if row is not None:
                    existing = _asset(row)
                    if existing != asset:
                        raise KernelConflictError("asset_identity_conflict")
                    return existing
                candidate = connection.execute(
                    "SELECT * FROM stageflow.media_candidate WHERE candidate_id = %s FOR UPDATE",
                    (asset.candidate_id.value,),
                ).fetchone()
                if candidate is None:
                    raise KernelNotFoundError("candidate_not_found")
                if str(candidate["stage_id"]) != asset.stage_id.value:
                    raise KernelConflictError("asset_candidate_stage_conflict")
                if candidate["source_binding_key"] != asset.source_binding_key:
                    raise KernelConflictError("asset_candidate_source_conflict")
                connection.execute(
                    """
                    INSERT INTO stageflow.completed_media_asset_registry (
                        asset_id, candidate_id, manifest_id, stage_id, source_binding_key,
                        media_started_at, media_ended_at, registered_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        asset.id.value,
                        asset.candidate_id.value,
                        asset.manifest_id.value,
                        asset.stage_id.value,
                        asset.source_binding_key,
                        asset.media_started_at,
                        asset.media_ended_at,
                        asset.registered_at,
                    ),
                )
                connection.execute(
                    """
                    UPDATE stageflow.media_candidate SET registration_state = 'registered',
                        last_observed_at = GREATEST(last_observed_at, %s),
                        revision = revision + 1 WHERE candidate_id = %s
                    """,
                    (asset.registered_at, asset.candidate_id.value),
                )
                return asset
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def get_asset(self, asset_id: EntityId) -> RegisteredMediaAsset | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT * FROM stageflow.completed_media_asset_registry WHERE asset_id = %s
                    """,
                    (asset_id.value,),
                ).fetchone()
                return None if row is None else _asset(row)
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def put_association(
        self, association: MediaAssociation, *, request_digest: str | None = None
    ) -> MediaAssociation:
        try:
            with self._connect() as connection:
                history_id = EntityId.new()
                if association.authority is AssociationAuthority.HUMAN:
                    assert association.operation_id is not None
                    if request_digest is None:
                        raise ValueError("Human association requires a request digest.")
                    replay_id = self._reserve_human_command(
                        connection,
                        operation_id=association.operation_id,
                        command_kind=HumanCommandKind.MEDIA_ASSIGNMENT,
                        request_digest=request_digest,
                        result_id=history_id,
                        recorded_at=association.decided_at,
                    )
                    if replay_id is not None:
                        replay = connection.execute(
                            """
                            SELECT asset_id, association_status, session_id, authority,
                                   reason_codes, evidence_ids, actor_id,
                                   association_revision AS revision, decided_at,
                                   operation_id, policy_id, policy_version,
                                   input_references
                            FROM stageflow.media_association_history
                            WHERE association_history_id = %s
                            """,
                            (replay_id.result_id.value,),
                        ).fetchone()
                        assert replay is not None
                        return _association(replay)
                elif request_digest is not None:
                    raise ValueError(
                        "Deterministic association cannot carry a human digest."
                    )

                current = connection.execute(
                    "SELECT * FROM stageflow.media_association WHERE asset_id = %s FOR UPDATE",
                    (association.asset_id.value,),
                ).fetchone()
                expected_revision = (
                    1 if current is None else cast(int, current["revision"]) + 1
                )
                if association.revision != expected_revision:
                    raise KernelConflictError("association_revision_conflict")
                asset = connection.execute(
                    """
                    SELECT stage_id FROM stageflow.completed_media_asset_registry
                    WHERE asset_id = %s
                    """,
                    (association.asset_id.value,),
                ).fetchone()
                if asset is None:
                    raise KernelNotFoundError("asset_not_found")

                old_session_id = (
                    None
                    if current is None
                    or current["association_status"] != AssociationStatus.ASSOCIATED.value
                    else EntityId(str(current["session_id"]))
                )
                new_session_id = (
                    association.session_id
                    if association.status is AssociationStatus.ASSOCIATED
                    else None
                )
                affected_ids = sorted(
                    {
                        value
                        for value in (old_session_id, new_session_id)
                        if value is not None
                    },
                    key=lambda value: value.value,
                )
                affected: dict[EntityId, Row] = {}
                for session_id in affected_ids:
                    session_row = connection.execute(
                        "SELECT * FROM stageflow.session WHERE session_id = %s FOR UPDATE",
                        (session_id.value,),
                    ).fetchone()
                    if session_row is None:
                        raise KernelNotFoundError("session_not_found")
                    affected[session_id] = session_row
                if new_session_id is not None and str(asset["stage_id"]) != str(
                    affected[new_session_id]["stage_id"]
                ):
                    raise KernelConflictError("association_stage_conflict")

                if old_session_id != new_session_id:
                    for session_id, session_row in affected.items():
                        if (
                            session_row["package_state"]
                            == SessionPackageState.COMPLETE.value
                        ):
                            connection.execute(
                                """
                                UPDATE stageflow.session SET
                                    package_state = 'correction_required',
                                    package_revision = package_revision + 1,
                                    revision = revision + 1, updated_at = %s
                                WHERE session_id = %s
                                """,
                                (association.decided_at, session_id.value),
                            )

                association_values = (
                    association.asset_id.value,
                    association.status.value,
                    None
                    if association.session_id is None
                    else association.session_id.value,
                    association.authority.value,
                    Jsonb(list(association.reason_codes)),
                    Jsonb([value.value for value in association.evidence_ids]),
                    None
                    if association.actor_id is None
                    else association.actor_id.value,
                    association.revision,
                    association.decided_at,
                    None
                    if association.operation_id is None
                    else association.operation_id.value,
                    association.policy_id,
                    association.policy_version,
                    Jsonb(_association_inputs(list(association.input_references))),
                )
                connection.execute(
                    """
                    INSERT INTO stageflow.media_association (
                        asset_id, association_status, session_id, authority, reason_codes,
                        evidence_ids, actor_id, revision, decided_at, operation_id,
                        policy_id, policy_version, input_references
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (asset_id) DO UPDATE SET
                        association_status = EXCLUDED.association_status,
                        session_id = EXCLUDED.session_id, authority = EXCLUDED.authority,
                        reason_codes = EXCLUDED.reason_codes,
                        evidence_ids = EXCLUDED.evidence_ids,
                        actor_id = EXCLUDED.actor_id, revision = EXCLUDED.revision,
                        decided_at = EXCLUDED.decided_at,
                        operation_id = EXCLUDED.operation_id,
                        policy_id = EXCLUDED.policy_id,
                        policy_version = EXCLUDED.policy_version,
                        input_references = EXCLUDED.input_references
                    """,
                    association_values,
                )
                connection.execute(
                    """
                    INSERT INTO stageflow.media_association_history (
                        association_history_id, asset_id, association_revision,
                        association_status, session_id, authority, reason_codes,
                        evidence_ids, actor_id, decided_at, operation_id,
                        policy_id, policy_version, input_references
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        history_id.value,
                        association.asset_id.value,
                        association.revision,
                        association.status.value,
                        None
                        if association.session_id is None
                        else association.session_id.value,
                        association.authority.value,
                        Jsonb(list(association.reason_codes)),
                        Jsonb([value.value for value in association.evidence_ids]),
                        None
                        if association.actor_id is None
                        else association.actor_id.value,
                        association.decided_at,
                        None
                        if association.operation_id is None
                        else association.operation_id.value,
                        association.policy_id,
                        association.policy_version,
                        Jsonb(_association_inputs(list(association.input_references))),
                    ),
                )
                return association
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def get_association(self, asset_id: EntityId) -> MediaAssociation | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM stageflow.media_association WHERE asset_id = %s",
                    (asset_id.value,),
                ).fetchone()
                return None if row is None else _association(row)
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def set_package_state(self, session_id: EntityId, state: str, at: datetime) -> Session:
        if state == SessionPackageState.COMPLETE.value:
            raise KernelConflictError("completion_requires_human_decision")
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    UPDATE stageflow.session SET package_state = %s,
                        revision = revision + 1, updated_at = %s
                    WHERE session_id = %s RETURNING *
                    """,
                    (state, at, session_id.value),
                ).fetchone()
                if row is None:
                    raise KernelNotFoundError("session_not_found")
                return _session(row)
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def declare_package_ready(
        self, decision: PackageReadyDecision, *, request_digest: str
    ) -> Session:
        try:
            with self._connect() as connection:
                replay_id = self._reserve_human_command(
                    connection,
                    operation_id=decision.operation_id,
                    command_kind=HumanCommandKind.PACKAGE_READY,
                    request_digest=request_digest,
                    result_id=decision.id,
                    recorded_at=decision.decided_at,
                )
                if replay_id is not None:
                    replay = connection.execute(
                        """
                        SELECT session_id FROM stageflow.session_package_ready_history
                        WHERE package_ready_decision_id = %s
                        """,
                        (replay_id.result_id.value,),
                    ).fetchone()
                    assert replay is not None
                    if replay_id.result_snapshot is not None:
                        return _session_from_result_snapshot(replay_id.result_snapshot)
                    replayed_session = connection.execute(
                        "SELECT * FROM stageflow.session WHERE session_id = %s",
                        (str(replay["session_id"]),),
                    ).fetchone()
                    assert replayed_session is not None
                    return _session(replayed_session)
                row = connection.execute(
                    "SELECT * FROM stageflow.session WHERE session_id = %s FOR UPDATE",
                    (decision.session_id.value,),
                ).fetchone()
                if row is None:
                    raise KernelNotFoundError("session_not_found")
                current = _session(row)
                if current.package_revision != decision.package_revision:
                    raise KernelConflictError("package_revision_conflict")
                if (
                    current.activity_state is not SessionActivityState.PRESENTATION_ENDED
                    or current.authoritative_end is None
                ):
                    raise KernelConflictError("session_presentation_not_ended")
                if current.package_state is not SessionPackageState.ASSEMBLING:
                    raise KernelConflictError("package_not_assembling")
                updated = connection.execute(
                    """
                    UPDATE stageflow.session SET package_state = 'ready_for_review',
                        revision = revision + 1, updated_at = %s
                    WHERE session_id = %s RETURNING *
                    """,
                    (decision.decided_at, decision.session_id.value),
                ).fetchone()
                assert updated is not None
                saved = _session(updated)
                connection.execute(
                    """
                    INSERT INTO stageflow.session_package_ready_history (
                        package_ready_decision_id, session_id, package_revision,
                        actor_id, reason, decided_at, operation_id,
                        resulting_session_revision
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        decision.id.value,
                        decision.session_id.value,
                        decision.package_revision,
                        decision.actor_id.value,
                        decision.reason,
                        decision.decided_at,
                        decision.operation_id.value,
                        saved.revision,
                    ),
                )
                self._record_session_result(
                    connection,
                    operation_id=decision.operation_id,
                    session=saved,
                )
                return saved
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def complete_session(
        self, decision: CompletionDecision, *, request_digest: str
    ) -> Session:
        try:
            with self._connect() as connection:
                replay_id = self._reserve_human_command(
                    connection,
                    operation_id=decision.operation_id,
                    command_kind=HumanCommandKind.PACKAGE_COMPLETION,
                    request_digest=request_digest,
                    result_id=decision.id,
                    recorded_at=decision.decided_at,
                )
                if replay_id is not None:
                    replay = connection.execute(
                        """
                        SELECT session_id FROM stageflow.session_completion_history
                        WHERE completion_decision_id = %s
                        """,
                        (replay_id.result_id.value,),
                    ).fetchone()
                    assert replay is not None
                    if replay_id.result_snapshot is not None:
                        return _session_from_result_snapshot(replay_id.result_snapshot)
                    replayed_session = connection.execute(
                        "SELECT * FROM stageflow.session WHERE session_id = %s",
                        (str(replay["session_id"]),),
                    ).fetchone()
                    assert replayed_session is not None
                    return _session(replayed_session)
                row = connection.execute(
                    "SELECT * FROM stageflow.session WHERE session_id = %s FOR UPDATE",
                    (decision.session_id.value,),
                ).fetchone()
                if row is None:
                    raise KernelNotFoundError("session_not_found")
                current = _session(row)
                if current.package_revision != decision.package_revision:
                    raise KernelConflictError("package_revision_conflict")
                if current.package_state not in {
                    SessionPackageState.READY_FOR_REVIEW,
                    SessionPackageState.IN_REVIEW,
                }:
                    raise KernelConflictError("package_not_ready_for_completion")
                state = (
                    SessionPackageState.COMPLETE
                    if decision.approved
                    else SessionPackageState.CORRECTION_REQUIRED
                )
                updated = connection.execute(
                    """
                    UPDATE stageflow.session SET package_state = %s,
                        revision = revision + 1, updated_at = %s
                    WHERE session_id = %s RETURNING *
                    """,
                    (state.value, decision.decided_at, decision.session_id.value),
                ).fetchone()
                connection.execute(
                    """
                    INSERT INTO stageflow.session_completion_history (
                        completion_decision_id, session_id, package_revision, actor_id,
                        approved, reason, decided_at, operation_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        decision.id.value,
                        decision.session_id.value,
                        decision.package_revision,
                        decision.actor_id.value,
                        decision.approved,
                        decision.reason,
                        decision.decided_at,
                        decision.operation_id.value,
                    ),
                )
                if decision.approved:
                    connection.execute(
                        """
                        INSERT INTO stageflow.session_completion_asset (
                            completion_decision_id, session_id, package_revision,
                            asset_id, association_revision
                        )
                        SELECT %s, %s, %s, asset_id, revision
                        FROM stageflow.media_association
                        WHERE association_status = 'associated' AND session_id = %s
                        """,
                        (
                            decision.id.value,
                            decision.session_id.value,
                            decision.package_revision,
                            decision.session_id.value,
                        ),
                    )
                assert updated is not None
                saved = _session(updated)
                self._record_session_result(
                    connection,
                    operation_id=decision.operation_id,
                    session=saved,
                )
                return saved
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def list_approved_package_asset_ids(
        self, completion_decision_id: EntityId
    ) -> tuple[EntityId, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT asset_id FROM stageflow.session_completion_asset
                    WHERE completion_decision_id = %s ORDER BY asset_id
                    """,
                    (completion_decision_id.value,),
                ).fetchall()
                return tuple(EntityId(str(row["asset_id"])) for row in rows)
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def put_reconciliation(self, run: ReconciliationRun) -> ReconciliationRun:
        try:
            with self._connect() as connection:
                existing_row = connection.execute(
                    """
                    SELECT * FROM stageflow.reconciliation_run
                    WHERE reconciliation_run_id = %s FOR UPDATE
                    """,
                    (run.id.value,),
                ).fetchone()
                if existing_row is not None:
                    existing = _reconciliation(existing_row)
                    if (
                        existing.event_id != run.event_id
                        or existing.scope != run.scope
                        or existing.started_at != run.started_at
                    ):
                        raise KernelConflictError("reconciliation_identity_conflict")
                    if (
                        existing.status is not ReconciliationStatus.RUNNING
                        and existing != run
                    ):
                        raise KernelConflictError("reconciliation_already_finished")
                connection.execute(
                    """
                    INSERT INTO stageflow.reconciliation_run (
                        reconciliation_run_id, event_id, status, scope, started_at,
                        completed_at, candidates_seen, assets_registered, failure_code
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (reconciliation_run_id) DO UPDATE SET
                        status = EXCLUDED.status, completed_at = EXCLUDED.completed_at,
                        candidates_seen = EXCLUDED.candidates_seen,
                        assets_registered = EXCLUDED.assets_registered,
                        failure_code = EXCLUDED.failure_code
                    WHERE stageflow.reconciliation_run.event_id = EXCLUDED.event_id
                    """,
                    (
                        run.id.value,
                        run.event_id.value,
                        run.status.value,
                        run.scope,
                        run.started_at,
                        run.completed_at,
                        run.candidates_seen,
                        run.assets_registered,
                        run.failure_code,
                    ),
                )
                return run
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def get_latest_reconciliation(self, event_id: EntityId) -> ReconciliationRun | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT * FROM stageflow.reconciliation_run WHERE event_id = %s
                    ORDER BY sequence DESC LIMIT 1
                    """,
                    (event_id.value,),
                ).fetchone()
                return None if row is None else _reconciliation(row)
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def list_recent_media(
        self, event_id: EntityId, *, limit: int = 100
    ) -> tuple[MediaOperationalProjection, ...]:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT c.*, a.asset_id, a.media_started_at, a.media_ended_at,
                           x.association_status, x.authority, x.session_id,
                           x.reason_codes, x.evidence_ids, x.policy_id,
                           x.policy_version, x.input_references, x.actor_id,
                           x.decided_at,
                           COALESCE(
                             (
                               SELECT jsonb_agg(DISTINCT o.epistemic_kind)
                               FROM stageflow.media_resource_observation o
                               WHERE o.candidate_id = c.candidate_id
                             ),
                             '[]'::jsonb
                           ) AS epistemic_kinds
                    FROM stageflow.media_candidate c
                    JOIN stageflow.stage s ON s.stage_id = c.stage_id
                    LEFT JOIN stageflow.completed_media_asset_registry a
                      ON a.candidate_id = c.candidate_id
                    LEFT JOIN stageflow.media_association x ON x.asset_id = a.asset_id
                    WHERE s.event_id = %s
                    ORDER BY c.last_observed_at DESC, c.candidate_id DESC
                    LIMIT %s
                    """,
                    (event_id.value, limit),
                ).fetchall()
                return tuple(
                    MediaOperationalProjection(
                        candidate_id=EntityId(str(row["candidate_id"])),
                        proposed_asset_id=EntityId(str(row["proposed_asset_id"])),
                        asset_id=(
                            None
                            if row["asset_id"] is None
                            else EntityId(str(row["asset_id"]))
                        ),
                        stage_id=EntityId(str(row["stage_id"])),
                        source_binding_key=cast(str, row["source_binding_key"]),
                        registration_state=MediaRegistrationState(
                            cast(str, row["registration_state"])
                        ),
                        discovered_at=cast(datetime, row["discovered_at"]),
                        last_observed_at=cast(datetime, row["last_observed_at"]),
                        association_status=(
                            None
                            if row["association_status"] is None
                            else AssociationStatus(cast(str, row["association_status"]))
                        ),
                        association_authority=(
                            None
                            if row["authority"] is None
                            else AssociationAuthority(cast(str, row["authority"]))
                        ),
                        session_id=(
                            None
                            if row["session_id"] is None
                            else EntityId(str(row["session_id"]))
                        ),
                        epistemic_kinds=tuple(
                            EpistemicKind(value)
                            for value in cast(list[str], row["epistemic_kinds"])
                        ),
                        media_started_at=cast(datetime | None, row["media_started_at"]),
                        media_ended_at=cast(datetime | None, row["media_ended_at"]),
                        diagnostic_codes=tuple(
                            code
                            for code in (
                                "not_observed"
                                if row["registration_state"] == "discovered"
                                else "readiness_pending"
                                if row["registration_state"] == "stabilizing"
                                else None,
                                (
                                    None
                                    if row["association_status"] in {None, "associated"}
                                    else f"association_{row['association_status']}"
                                ),
                            )
                            if code is not None
                        ),
                        association_reason_codes=(
                            ()
                            if row["reason_codes"] is None
                            else cast(list[str], row["reason_codes"])
                        ),
                        association_evidence_ids=(
                            ()
                            if row["evidence_ids"] is None
                            else tuple(
                                EntityId(value)
                                for value in cast(list[str], row["evidence_ids"])
                            )
                        ),
                        association_policy_id=cast(str | None, row["policy_id"]),
                        association_policy_version=cast(
                            str | None, row["policy_version"]
                        ),
                        association_input_references=(
                            ()
                            if row["input_references"] is None
                            else tuple(
                                _association_input(value)
                                for value in cast(
                                    list[dict[str, object]], row["input_references"]
                                )
                            )
                        ),
                        association_actor_id=(
                            None
                            if row["actor_id"] is None
                            else EntityId(str(row["actor_id"]))
                        ),
                        association_decided_at=cast(
                            datetime | None, row["decided_at"]
                        ),
                    )
                    for row in rows
                )
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc

    def operational_status(
        self,
        event_id: EntityId,
        *,
        database_available: bool = True,
        recovery_required: bool = False,
        source_availability: dict[str, bool] | None = None,
    ) -> EventOperationalStatus:
        try:
            with self._connect() as connection:
                event = self._get_event(connection, event_id)
                if event is None:
                    raise KernelNotFoundError("event_not_found")
                availability = source_availability or {}
                stage_statuses: list[StageOperationalStatus] = []
                attention: list[str] = []
                session_limit = 20
                for stage in self._list_stages(connection, event_id):
                    counts_row = connection.execute(
                        """
                        SELECT
                          count(*) FILTER (WHERE c.registration_state = 'discovered') AS discovered,
                          count(*) FILTER (
                              WHERE c.registration_state = 'stabilizing'
                          ) AS stabilizing,
                          count(*) FILTER (WHERE c.registration_state = 'ready') AS ready,
                          max(c.last_observed_at) AS last_arrival
                        FROM stageflow.media_candidate c WHERE c.stage_id = %s
                        """,
                        (stage.id.value,),
                    ).fetchone()
                    association_row = connection.execute(
                        """
                        SELECT count(a.asset_id) AS registered,
                          count(*) FILTER (WHERE x.association_status = 'associated') AS associated,
                          count(*) FILTER (WHERE x.association_status = 'unresolved') AS unresolved,
                          count(*) FILTER (WHERE x.association_status = 'conflict') AS conflicting
                        FROM stageflow.completed_media_asset_registry a
                        LEFT JOIN stageflow.media_association x ON x.asset_id = a.asset_id
                        WHERE a.stage_id = %s
                        """,
                        (stage.id.value,),
                    ).fetchone()
                    session_row = connection.execute(
                        """
                        SELECT * FROM stageflow.session
                        WHERE stage_id = %s AND (
                            activity_state = 'presentation_active'
                            OR package_state IN (
                                'assembling', 'ready_for_review', 'in_review',
                                'correction_required'
                            )
                        ) ORDER BY authoritative_start DESC LIMIT 1
                        """,
                        (stage.id.value,),
                    ).fetchone()
                    assembling_rows = connection.execute(
                        """
                        SELECT s.*, e.title AS expectation_title,
                               e.revision AS expectation_revision,
                               e.planned_start AS expectation_planned_start,
                               e.planned_end AS expectation_planned_end,
                               c.completion_decision_id,
                               c.actor_id AS completion_actor_id,
                               c.decided_at AS completion_decided_at
                        FROM stageflow.session s
                        LEFT JOIN stageflow.program_expectation e
                          ON e.expectation_id = s.program_expectation_id
                        LEFT JOIN LATERAL (
                            SELECT completion_decision_id, actor_id, decided_at
                            FROM stageflow.session_completion_history
                            WHERE session_id = s.session_id AND approved
                            ORDER BY decided_at DESC, completion_decision_id DESC
                            LIMIT 1
                        ) c ON TRUE
                        WHERE s.stage_id = %s AND s.package_state IN (
                            'assembling', 'correction_required'
                        )
                        ORDER BY s.authoritative_start DESC, s.session_id DESC
                        LIMIT %s
                        """,
                        (stage.id.value, session_limit + 1),
                    ).fetchall()
                    recent_rows = connection.execute(
                        """
                        SELECT s.*, e.title AS expectation_title,
                               e.revision AS expectation_revision,
                               e.planned_start AS expectation_planned_start,
                               e.planned_end AS expectation_planned_end,
                               c.completion_decision_id,
                               c.actor_id AS completion_actor_id,
                               c.decided_at AS completion_decided_at
                        FROM stageflow.session s
                        LEFT JOIN stageflow.program_expectation e
                          ON e.expectation_id = s.program_expectation_id
                        LEFT JOIN LATERAL (
                            SELECT completion_decision_id, actor_id, decided_at
                            FROM stageflow.session_completion_history
                            WHERE session_id = s.session_id AND approved
                            ORDER BY decided_at DESC, completion_decision_id DESC
                            LIMIT 1
                        ) c ON TRUE
                        WHERE s.stage_id = %s
                        ORDER BY s.authoritative_start DESC, s.session_id DESC
                        LIMIT %s
                        """,
                        (stage.id.value, session_limit + 1),
                    ).fetchall()
                    bounded_assembling = assembling_rows[:session_limit]
                    bounded_recent = recent_rows[:session_limit]
                    assert counts_row is not None and association_row is not None
                    source_values = [availability.get(key) for key in stage.source_bindings]
                    known = [value for value in source_values if value is not None]
                    source_available = all(known) if known else None
                    unresolved = cast(int, association_row["unresolved"])
                    conflicting = cast(int, association_row["conflicting"])
                    stage_attention: list[str] = []
                    if unresolved:
                        stage_attention.append("unresolved_media")
                    if conflicting:
                        stage_attention.append("association_conflict")
                    if source_available is False:
                        stage_attention.append("source_unavailable")
                    attention.extend(
                        f"stage:{stage.key}:{code}" for code in stage_attention
                    )
                    stage_statuses.append(
                        StageOperationalStatus(
                            stage_id=stage.id,
                            stage_key=stage.key,
                            stage_name=stage.name,
                            source_available=source_available,
                            active_or_assembling_session_id=(
                                None
                                if session_row is None
                                else EntityId(str(session_row["session_id"]))
                            ),
                            assembling_session_ids=tuple(
                                EntityId(str(row["session_id"]))
                                for row in bounded_assembling
                            ),
                            assembling_sessions=tuple(
                                _session_operational_projection(row)
                                for row in bounded_assembling
                            ),
                            session_activity_state=(
                                None
                                if session_row is None
                                else SessionActivityState(session_row["activity_state"])
                            ),
                            session_package_state=(
                                None
                                if session_row is None
                                else SessionPackageState(session_row["package_state"])
                            ),
                            session_package_revision=(
                                None
                                if session_row is None
                                else cast(int, session_row["package_revision"])
                            ),
                            session_revision=(
                                None
                                if session_row is None
                                else cast(int, session_row["revision"])
                            ),
                            session_authoritative_start=(
                                None
                                if session_row is None
                                else cast(datetime, session_row["authoritative_start"])
                            ),
                            session_authoritative_end=(
                                None
                                if session_row is None
                                else cast(
                                    datetime | None,
                                    session_row["authoritative_end"],
                                )
                            ),
                            last_media_arrived_at=cast(
                                datetime | None, counts_row["last_arrival"]
                            ),
                            discovered_media=cast(int, counts_row["discovered"]),
                            stabilizing_media=cast(int, counts_row["stabilizing"]),
                            ready_media=cast(int, counts_row["ready"]),
                            registered_media=cast(int, association_row["registered"]),
                            associated_media=cast(int, association_row["associated"]),
                            unresolved_media=unresolved,
                            conflicting_media=conflicting,
                            attention_codes=stage_attention,
                            assembling_sessions_truncated=(
                                len(assembling_rows) > session_limit
                            ),
                            recent_sessions=tuple(
                                _session_operational_projection(row)
                                for row in bounded_recent
                            ),
                            recent_sessions_truncated=(
                                len(recent_rows) > session_limit
                            ),
                            session_limit=session_limit,
                        )
                    )
                latest_row = connection.execute(
                    """
                    SELECT * FROM stageflow.reconciliation_run WHERE event_id = %s
                    ORDER BY sequence DESC LIMIT 1
                    """,
                    (event_id.value,),
                ).fetchone()
                latest = None if latest_row is None else _reconciliation(latest_row)
                recovering = recovery_required or (
                    latest is not None
                    and latest.status is ReconciliationStatus.RUNNING
                )
                ready = (
                    database_available
                    and not recovering
                    and latest is not None
                    and latest.status is ReconciliationStatus.COMPLETED
                )
                if recovering:
                    attention.append(
                        "postgresql_reconciliation_required"
                        if recovery_required
                        else "startup_reconciliation_running"
                    )
                if latest is not None and latest.status is ReconciliationStatus.FAILED:
                    attention.append("startup_reconciliation_failed")
                proposal_rows = connection.execute(
                    """
                    SELECT p.* FROM stageflow.session_boundary_proposal p
                    JOIN stageflow.session s ON s.session_id = p.session_id
                    WHERE s.event_id = %s
                    ORDER BY p.proposed_at DESC, p.boundary_proposal_id DESC
                    LIMIT 100
                    """,
                    (event_id.value,),
                ).fetchall()
                return EventOperationalStatus(
                    event_id=event.id,
                    event_key=event.key,
                    event_name=event.name,
                    database_available=database_available,
                    ready=ready,
                    recovering=recovering,
                    stages=stage_statuses,
                    attention_codes=attention,
                    latest_reconciliation=latest,
                    recent_media=self.list_recent_media(event_id),
                    boundary_proposals=tuple(
                        _boundary_proposal(row) for row in proposal_rows
                    ),
                )
        except psycopg.OperationalError as exc:
            raise KernelStorageUnavailableError("postgresql_unavailable") from exc


__all__ = ["PostgresEventModeKernelRepository"]
