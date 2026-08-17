from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any, cast

import psycopg
from psycopg.rows import dict_row

from app.contexts.production.media_timing_evidence import (
    RecorderProfileQualificationStatus,
)
from app.contexts.transcription_evidence import (
    DerivedTranscriptAlignment,
    NormalizedTranscriptResult,
    PendingTranscriptEvidence,
    SpeakerEvidenceKind,
    TranscriptEvidenceRevision,
    TranscriptEvidenceStatus,
    TranscriptExecutionProvenance,
    TranscriptSegment,
    TranscriptWord,
)
from app.contexts.work_execution import (
    AttemptOutcome,
    AttemptStatus,
    ClaimRequest,
    DurableOperation,
    EventNetworkPolicy,
    ExecutionLocality,
    OperationAttempt,
    OperationClaim,
    OperationFailure,
    OperationStatus,
    OperationStatusCount,
    PendingOperation,
    TranscriptionOperationInput,
    Worker,
    WorkerCapability,
    WorkerHealth,
    WorkerPresence,
    WorkerPressure,
    WorkExecutionConflictError,
    WorkExecutionLeaseLostError,
    WorkExecutionNotFoundError,
    WorkExecutionProjection,
    WorkExecutionRepository,
    WorkExecutionStorageUnavailableError,
)
from app.shared.ids import EntityId

Row = dict[str, Any]


class PostgresWorkExecutionRepository(WorkExecutionRepository):
    """PostgreSQL operation journal, worker registry, leases, and result commit."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def _connect(self) -> psycopg.Connection[Row]:
        return psycopg.Connection[Row].connect(self._dsn, row_factory=dict_row)

    def enqueue(self, pending: PendingOperation) -> DurableOperation:
        request = pending.request
        try:
            with self._connect() as connection:
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (request.idempotency_key,),
                )
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 1))",
                    (pending.work_key,),
                )
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 2))",
                    (request.operation_id.value,),
                )
                replay = connection.execute(
                    """
                    SELECT * FROM stageflow.work_operation
                    WHERE operation_id = %s OR idempotency_key = %s OR work_key = %s
                    FOR UPDATE
                    """,
                    (
                        request.operation_id.value,
                        request.idempotency_key,
                        pending.work_key,
                    ),
                ).fetchone()
                if replay is not None:
                    if (
                        str(replay["operation_id"]) != request.operation_id.value
                        or str(replay["idempotency_key"]) != request.idempotency_key
                        or str(replay["work_key"]) != pending.work_key
                        or str(replay["request_digest"]) != pending.request_digest
                    ):
                        raise WorkExecutionConflictError(
                            "transcription_enqueue_identity_conflict"
                        )
                    return _operation(replay)

                asset = connection.execute(
                    """
                    SELECT manifest_id
                    FROM stageflow.completed_media_asset_registry
                    WHERE asset_id = %s
                    FOR UPDATE
                    """,
                    (request.input.asset_id.value,),
                ).fetchone()
                if asset is None:
                    raise WorkExecutionNotFoundError(
                        "completed_media_asset_not_found"
                    )
                if str(asset["manifest_id"]) != request.input.manifest_id.value:
                    raise WorkExecutionConflictError(
                        "asset_manifest_identity_conflict"
                    )
                row = connection.execute(
                    """
                    INSERT INTO stageflow.work_operation (
                        operation_id, operation_kind, operation_schema_version,
                        deployment_id, event_id, asset_id, manifest_id,
                        manifest_version, asset_format, execution_profile_id,
                        execution_profile_version, requested_language,
                        request_word_timing, request_speaker_labels,
                        requires_cloud, required_for_event, idempotency_key,
                        request_digest, work_key, priority, eligible_at,
                        operation_status, max_attempts, retry_delay_microseconds,
                        created_at, updated_at
                    ) VALUES (
                        %s, 'transcription', 'v1', %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        'pending', %s, %s, %s, %s
                    )
                    RETURNING *
                    """,
                    (
                        request.operation_id.value,
                        request.deployment_id,
                        None if request.event_id is None else request.event_id.value,
                        request.input.asset_id.value,
                        request.input.manifest_id.value,
                        request.input.manifest_version,
                        request.input.asset_format,
                        request.input.execution_profile_id,
                        request.input.execution_profile_version,
                        request.input.requested_language,
                        request.input.request_word_timing,
                        request.input.request_speaker_labels,
                        request.input.requires_cloud,
                        request.required_for_event,
                        request.idempotency_key,
                        pending.request_digest,
                        pending.work_key,
                        request.priority,
                        request.eligible_at,
                        request.max_attempts,
                        _microseconds(request.retry_delay),
                        request.requested_at,
                        request.requested_at,
                    ),
                ).fetchone()
                assert row is not None
                return _operation(row)
        except (psycopg.InterfaceError, psycopg.OperationalError) as exc:
            raise WorkExecutionStorageUnavailableError(
                "postgresql_work_execution_unavailable"
            ) from exc

    def register_worker(self, worker: Worker) -> Worker:
        try:
            with self._connect() as connection:
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 3))",
                    (worker.id.value,),
                )
                existing = connection.execute(
                    "SELECT * FROM stageflow.work_worker WHERE worker_id = %s FOR UPDATE",
                    (worker.id.value,),
                ).fetchone()
                if existing is not None:
                    restored = _worker(existing)
                    if restored != worker:
                        raise WorkExecutionConflictError(
                            "worker_identity_conflict"
                        )
                    return restored
                connection.execute(
                    """
                    INSERT INTO stageflow.work_worker (
                        worker_id, node_id, deployment_id, event_id, enabled,
                        draining, implementation_version, revision,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        worker.id.value,
                        worker.node_id,
                        worker.deployment_id,
                        None if worker.event_id is None else worker.event_id.value,
                        worker.enabled,
                        worker.draining,
                        worker.implementation_version,
                        worker.revision,
                        worker.created_at,
                        worker.updated_at,
                    ),
                )
                return worker
        except (psycopg.InterfaceError, psycopg.OperationalError) as exc:
            raise WorkExecutionStorageUnavailableError(
                "postgresql_work_execution_unavailable"
            ) from exc

    def register_capability(
        self,
        capability: WorkerCapability,
    ) -> WorkerCapability:
        try:
            with self._connect() as connection:
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 4))",
                    (capability.id.value,),
                )
                existing = connection.execute(
                    """
                    SELECT * FROM stageflow.work_worker_capability
                    WHERE capability_id = %s FOR UPDATE
                    """,
                    (capability.id.value,),
                ).fetchone()
                if existing is not None:
                    restored = _capability(existing)
                    if restored != capability:
                        raise WorkExecutionConflictError(
                            "worker_capability_identity_conflict"
                        )
                    return restored
                connection.execute(
                    """
                    INSERT INTO stageflow.work_worker_capability (
                        capability_id, worker_id, operation_kind,
                        operation_schema_version, execution_profile_id,
                        execution_profile_version, locality,
                        accepted_asset_formats, supports_word_timing,
                        supports_speaker_labels, provider_id, provider_version,
                        model_id, model_version, runtime_id, runtime_version,
                        configured_eligible, effective_from, effective_until
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        capability.id.value,
                        capability.worker_id.value,
                        capability.operation_kind,
                        capability.operation_schema_version,
                        capability.execution_profile_id,
                        capability.execution_profile_version,
                        capability.locality.value,
                        list(capability.accepted_asset_formats),
                        capability.supports_word_timing,
                        capability.supports_speaker_labels,
                        capability.provider_id,
                        capability.provider_version,
                        capability.model_id,
                        capability.model_version,
                        capability.runtime_id,
                        capability.runtime_version,
                        capability.configured_eligible,
                        capability.effective_from,
                        capability.effective_until,
                    ),
                )
                return capability
        except (psycopg.InterfaceError, psycopg.OperationalError) as exc:
            raise WorkExecutionStorageUnavailableError(
                "postgresql_work_execution_unavailable"
            ) from exc

    def record_presence(
        self,
        worker_id: EntityId,
        *,
        ttl: timedelta,
        maximum_concurrency: int,
        health: WorkerHealth,
        pressure: WorkerPressure,
    ) -> WorkerPresence:
        if ttl <= timedelta(0) or ttl > timedelta(hours=1):
            raise ValueError("presence ttl must be positive and at most one hour.")
        if not 1 <= maximum_concurrency <= 64:
            raise ValueError("maximum_concurrency must be between 1 and 64.")

        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    INSERT INTO stageflow.work_worker_presence (
                        worker_id, observed_at, expires_at, maximum_concurrency,
                        health_state, pressure_state
                    )
                    SELECT %s, statement_timestamp(),
                           statement_timestamp() + %s,
                           %s, %s, %s
                    WHERE EXISTS (
                        SELECT 1 FROM stageflow.work_worker
                        WHERE worker_id = %s
                    )
                    ON CONFLICT (worker_id) DO UPDATE SET
                        observed_at = EXCLUDED.observed_at,
                        expires_at = EXCLUDED.expires_at,
                        maximum_concurrency = EXCLUDED.maximum_concurrency,
                        health_state = EXCLUDED.health_state,
                        pressure_state = EXCLUDED.pressure_state
                    RETURNING *
                    """,
                    (
                        worker_id.value,
                        ttl,
                        maximum_concurrency,
                        health.value,
                        pressure.value,
                        worker_id.value,
                    ),
                ).fetchone()
                if row is None:
                    raise WorkExecutionNotFoundError("worker_not_found")
                return _presence(row)
        except (psycopg.InterfaceError, psycopg.OperationalError) as exc:
            raise WorkExecutionStorageUnavailableError(
                "postgresql_work_execution_unavailable"
            ) from exc

    def claim_next(self, request: ClaimRequest) -> OperationClaim | None:
        try:
            with self._connect() as connection:
                worker = connection.execute(
                    """
                    SELECT w.*, p.maximum_concurrency, p.health_state,
                           p.pressure_state, p.expires_at AS presence_expires_at,
                           statement_timestamp() AS database_now
                    FROM stageflow.work_worker w
                    LEFT JOIN stageflow.work_worker_presence p
                        ON p.worker_id = w.worker_id
                    WHERE w.worker_id = %s
                    FOR UPDATE OF w
                    """,
                    (request.worker_id.value,),
                ).fetchone()
                if worker is None:
                    raise WorkExecutionNotFoundError("worker_not_found")
                if (
                    not cast(bool, worker["enabled"])
                    or cast(bool, worker["draining"])
                    or worker["presence_expires_at"] is None
                    or worker["presence_expires_at"] <= worker["database_now"]
                    or worker["health_state"] not in ("available", "degraded")
                ):
                    return None

                active = connection.execute(
                    """
                    SELECT count(*) AS active_count
                    FROM stageflow.work_operation
                    WHERE lease_owner_worker_id = %s
                      AND operation_status IN ('leased', 'running')
                      AND lease_expires_at > statement_timestamp()
                    """,
                    (request.worker_id.value,),
                ).fetchone()
                assert active is not None
                if int(active["active_count"]) >= int(worker["maximum_concurrency"]):
                    return None

                event_condition = (
                    "o.event_id IS NULL"
                    if worker["event_id"] is None
                    else "(o.event_id IS NULL OR o.event_id = %(event_id)s)"
                )
                params: dict[str, object] = {
                    "worker_id": request.worker_id.value,
                    "deployment_id": str(worker["deployment_id"]),
                    "event_id": worker["event_id"],
                }
                connection.execute(
                    """
                    UPDATE stageflow.work_operation
                    SET operation_status = 'eligible',
                        last_reason_code = NULL,
                        row_revision = row_revision + 1,
                        updated_at = statement_timestamp()
                    WHERE deployment_id = %(deployment_id)s
                      AND operation_status IN ('pending', 'retry_wait')
                      AND eligible_at <= statement_timestamp()
                    """,
                    params,
                )
                if request.network_policy is EventNetworkPolicy.LOCAL_ONLY:
                    connection.execute(
                        """
                        UPDATE stageflow.work_operation
                        SET operation_status = 'deferred',
                            last_reason_code = 'cloud_required_event_mode',
                            row_revision = row_revision + 1,
                            updated_at = statement_timestamp()
                        WHERE deployment_id = %(deployment_id)s
                          AND operation_status = 'eligible'
                          AND requires_cloud
                        """,
                        params,
                    )
                else:
                    connection.execute(
                        """
                        UPDATE stageflow.work_operation
                        SET operation_status = 'eligible',
                            last_reason_code = NULL,
                            row_revision = row_revision + 1,
                            updated_at = statement_timestamp()
                        WHERE deployment_id = %(deployment_id)s
                          AND operation_status = 'deferred'
                          AND last_reason_code = 'cloud_required_event_mode'
                          AND eligible_at <= statement_timestamp()
                        """,
                        params,
                    )

                row = connection.execute(
                    f"""
                    SELECT o.*
                    FROM stageflow.work_operation o
                    WHERE o.deployment_id = %(deployment_id)s
                      AND {event_condition}
                      AND o.operation_status = 'eligible'
                      AND (
                          NOT o.requires_cloud
                          OR %(network_permitted)s
                      )
                      AND EXISTS (
                          SELECT 1
                          FROM stageflow.work_worker_capability c
                          WHERE c.worker_id = %(worker_id)s
                            AND c.configured_eligible
                            AND (
                                %(network_permitted)s
                                OR c.locality = 'local'
                            )
                            AND c.operation_kind = o.operation_kind
                            AND c.operation_schema_version =
                                o.operation_schema_version
                            AND c.execution_profile_id =
                                o.execution_profile_id
                            AND c.execution_profile_version =
                                o.execution_profile_version
                            AND o.asset_format =
                                ANY(c.accepted_asset_formats)
                            AND (
                                NOT o.request_word_timing
                                OR c.supports_word_timing
                            )
                            AND (
                                NOT o.request_speaker_labels
                                OR c.supports_speaker_labels
                            )
                            AND (
                                NOT o.requires_cloud
                                OR c.locality = 'cloud'
                            )
                            AND c.effective_from <= statement_timestamp()
                            AND (
                                c.effective_until IS NULL
                                OR c.effective_until > statement_timestamp()
                            )
                      )
                    ORDER BY o.priority DESC, o.eligible_at, o.created_at
                    FOR UPDATE OF o SKIP LOCKED
                    LIMIT 1
                    """,
                    {
                        **params,
                        "network_permitted": (
                            request.network_policy
                            is EventNetworkPolicy.NETWORK_PERMITTED
                        ),
                    },
                ).fetchone()
                if row is None:
                    return None

                attempt_id = EntityId.new()
                attempt_number = int(row["attempt_count"]) + 1
                fence_generation = int(row["fence_generation"]) + 1
                attempt = connection.execute(
                    """
                    INSERT INTO stageflow.work_operation_attempt (
                        attempt_id, operation_id, worker_id, attempt_number,
                        fence_generation, attempt_status, lease_started_at,
                        lease_expires_at, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, 'leased',
                        statement_timestamp(), statement_timestamp() + %s,
                        statement_timestamp()
                    )
                    RETURNING *
                    """,
                    (
                        attempt_id.value,
                        str(row["operation_id"]),
                        request.worker_id.value,
                        attempt_number,
                        fence_generation,
                        request.lease_duration,
                    ),
                ).fetchone()
                operation = connection.execute(
                    """
                    UPDATE stageflow.work_operation
                    SET operation_status = 'leased',
                        attempt_count = %s,
                        fence_generation = %s,
                        current_attempt_id = %s,
                        lease_owner_worker_id = %s,
                        lease_expires_at = statement_timestamp() + %s,
                        last_reason_code = NULL,
                        row_revision = row_revision + 1,
                        updated_at = statement_timestamp()
                    WHERE operation_id = %s
                    RETURNING *
                    """,
                    (
                        attempt_number,
                        fence_generation,
                        attempt_id.value,
                        request.worker_id.value,
                        request.lease_duration,
                        str(row["operation_id"]),
                    ),
                ).fetchone()
                assert attempt is not None and operation is not None
                return OperationClaim(
                    operation=_operation(operation),
                    attempt=_attempt(attempt),
                )
        except (psycopg.InterfaceError, psycopg.OperationalError) as exc:
            raise WorkExecutionStorageUnavailableError(
                "postgresql_work_execution_unavailable"
            ) from exc

    def mark_running(self, claim: OperationClaim) -> OperationClaim:
        return self._advance_active_claim(
            claim,
            operation_status=OperationStatus.RUNNING,
            attempt_status=AttemptStatus.RUNNING,
            lease_duration=None,
        )

    def renew(
        self,
        claim: OperationClaim,
        *,
        lease_duration: timedelta,
    ) -> OperationClaim:
        return self._advance_active_claim(
            claim,
            operation_status=claim.operation.status,
            attempt_status=claim.attempt.status,
            lease_duration=lease_duration,
        )

    def _advance_active_claim(
        self,
        claim: OperationClaim,
        *,
        operation_status: OperationStatus,
        attempt_status: AttemptStatus,
        lease_duration: timedelta | None,
    ) -> OperationClaim:
        try:
            with self._connect() as connection:
                operation_row = connection.execute(
                    """
                    SELECT o.*, statement_timestamp() AS database_now
                    FROM stageflow.work_operation o
                    WHERE operation_id = %s FOR UPDATE
                    """,
                    (claim.operation.id.value,),
                ).fetchone()
                _require_active_claim(operation_row, claim)
                if lease_duration is None:
                    attempt_row = connection.execute(
                        """
                        UPDATE stageflow.work_operation_attempt
                        SET attempt_status = %s,
                            execution_started_at = COALESCE(
                                execution_started_at, statement_timestamp()
                            )
                        WHERE attempt_id = %s
                        RETURNING *
                        """,
                        (attempt_status.value, claim.attempt.id.value),
                    ).fetchone()
                    operation_row = connection.execute(
                        """
                        UPDATE stageflow.work_operation
                        SET operation_status = %s,
                            row_revision = row_revision + 1,
                            updated_at = statement_timestamp()
                        WHERE operation_id = %s
                        RETURNING *
                        """,
                        (operation_status.value, claim.operation.id.value),
                    ).fetchone()
                else:
                    attempt_row = connection.execute(
                        """
                        UPDATE stageflow.work_operation_attempt
                        SET lease_expires_at = statement_timestamp() + %s
                        WHERE attempt_id = %s
                        RETURNING *
                        """,
                        (lease_duration, claim.attempt.id.value),
                    ).fetchone()
                    operation_row = connection.execute(
                        """
                        UPDATE stageflow.work_operation
                        SET lease_expires_at = statement_timestamp() + %s,
                            row_revision = row_revision + 1,
                            updated_at = statement_timestamp()
                        WHERE operation_id = %s
                        RETURNING *
                        """,
                        (lease_duration, claim.operation.id.value),
                    ).fetchone()
                assert attempt_row is not None and operation_row is not None
                return OperationClaim(
                    operation=_operation(operation_row),
                    attempt=_attempt(attempt_row),
                )
        except (psycopg.InterfaceError, psycopg.OperationalError) as exc:
            raise WorkExecutionStorageUnavailableError(
                "postgresql_work_execution_unavailable"
            ) from exc

    def record_failure(
        self,
        claim: OperationClaim,
        failure: OperationFailure,
    ) -> DurableOperation:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT o.*, statement_timestamp() AS database_now
                    FROM stageflow.work_operation o
                    WHERE operation_id = %s FOR UPDATE
                    """,
                    (claim.operation.id.value,),
                ).fetchone()
                _require_active_claim(row, claim)
                assert row is not None
                retryable = (
                    failure.retryable
                    and int(row["attempt_count"]) < int(row["max_attempts"])
                )
                outcome = (
                    AttemptOutcome.RETRYABLE_FAILURE
                    if retryable
                    else AttemptOutcome.TERMINAL_FAILURE
                )
                connection.execute(
                    """
                    UPDATE stageflow.work_operation_attempt
                    SET attempt_status = 'finalized',
                        finalized_at = statement_timestamp(),
                        outcome = %s, retryable = %s,
                        reason_code = %s, diagnostic_summary = %s
                    WHERE attempt_id = %s
                    """,
                    (
                        outcome.value,
                        failure.retryable,
                        failure.reason_code,
                        failure.diagnostic_summary,
                        claim.attempt.id.value,
                    ),
                )
                delay = failure.retry_delay or timedelta(
                    microseconds=int(row["retry_delay_microseconds"])
                )
                status = (
                    OperationStatus.RETRY_WAIT
                    if retryable
                    else OperationStatus.TERMINAL_FAILED
                )
                updated = connection.execute(
                    """
                    UPDATE stageflow.work_operation
                    SET operation_status = %s,
                        eligible_at = CASE
                            WHEN %s THEN statement_timestamp() + %s
                            ELSE eligible_at
                        END,
                        current_attempt_id = NULL,
                        lease_owner_worker_id = NULL,
                        lease_expires_at = NULL,
                        last_reason_code = %s,
                        row_revision = row_revision + 1,
                        updated_at = statement_timestamp()
                    WHERE operation_id = %s
                    RETURNING *
                    """,
                    (
                        status.value,
                        retryable,
                        delay,
                        failure.reason_code,
                        claim.operation.id.value,
                    ),
                ).fetchone()
                assert updated is not None
                return _operation(updated)
        except (psycopg.InterfaceError, psycopg.OperationalError) as exc:
            raise WorkExecutionStorageUnavailableError(
                "postgresql_work_execution_unavailable"
            ) from exc

    def apply_transcript_result(
        self,
        claim: OperationClaim,
        pending: PendingTranscriptEvidence,
    ) -> TranscriptEvidenceRevision:
        try:
            with self._connect() as connection:
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (claim.operation.id.value,),
                )
                existing = connection.execute(
                    """
                    SELECT evidence_id, result_digest, work_key
                    FROM stageflow.transcript_evidence_revision
                    WHERE operation_id = %s
                    """,
                    (claim.operation.id.value,),
                ).fetchone()
                if existing is not None:
                    if (
                        str(existing["result_digest"]) != pending.result_digest
                        or str(existing["work_key"]) != pending.work_key
                    ):
                        raise WorkExecutionConflictError(
                            "transcript_result_identity_conflict"
                        )
                    return self._load_evidence(
                        connection,
                        EntityId.parse(str(existing["evidence_id"])),
                    )

                operation_row = connection.execute(
                    """
                    SELECT o.*, statement_timestamp() AS database_now
                    FROM stageflow.work_operation o
                    WHERE operation_id = %s FOR UPDATE
                    """,
                    (claim.operation.id.value,),
                ).fetchone()
                _require_active_claim(operation_row, claim)
                if (
                    pending.operation_id != claim.operation.id
                    or pending.work_key != claim.operation.work_key
                    or pending.asset_id != claim.operation.input.asset_id
                    or pending.manifest_id != claim.operation.input.manifest_id
                    or pending.manifest_version
                    != claim.operation.input.manifest_version
                ):
                    raise WorkExecutionConflictError(
                        "transcript_result_operation_conflict"
                    )
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 1))",
                    (pending.asset_id.value,),
                )
                predecessor = connection.execute(
                    """
                    SELECT evidence_id, evidence_revision
                    FROM stageflow.transcript_evidence_revision
                    WHERE asset_id = %s
                    ORDER BY evidence_revision DESC
                    LIMIT 1
                    """,
                    (pending.asset_id.value,),
                ).fetchone()
                evidence_revision = (
                    1
                    if predecessor is None
                    else int(predecessor["evidence_revision"]) + 1
                )
                result = pending.result
                provenance = result.provenance
                evidence_row = connection.execute(
                    """
                    INSERT INTO stageflow.transcript_evidence_revision (
                        evidence_id, operation_id, work_key, result_digest,
                        asset_id, manifest_id, manifest_version,
                        evidence_revision, predecessor_evidence_id,
                        evidence_status, provider_id, provider_version,
                        model_id, model_version, execution_tool_id,
                        execution_tool_version, execution_revision, language,
                        produced_at, applied_at, partial_reason,
                        failure_reason, limitations
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, statement_timestamp(), %s, %s, %s
                    )
                    RETURNING applied_at, evidence_revision
                    """,
                    (
                        pending.id.value,
                        pending.operation_id.value,
                        pending.work_key,
                        pending.result_digest,
                        pending.asset_id.value,
                        pending.manifest_id.value,
                        pending.manifest_version,
                        evidence_revision,
                        (
                            None
                            if predecessor is None
                            else str(predecessor["evidence_id"])
                        ),
                        result.status.value,
                        provenance.provider_id,
                        provenance.provider_version,
                        provenance.model_id,
                        provenance.model_version,
                        provenance.execution_tool_id,
                        provenance.execution_tool_version,
                        provenance.execution_revision,
                        result.language,
                        provenance.produced_at,
                        result.partial_reason,
                        result.failure_reason,
                        list(result.limitations),
                    ),
                ).fetchone()
                assert evidence_row is not None
                self._insert_evidence_children(connection, pending)
                changed = connection.execute(
                    """
                    UPDATE stageflow.work_operation_attempt
                    SET attempt_status = 'finalized',
                        finalized_at = statement_timestamp(),
                        outcome = 'succeeded',
                        retryable = false,
                        reason_code = NULL,
                        diagnostic_summary = NULL
                    WHERE attempt_id = %s
                      AND fence_generation = %s
                      AND attempt_status IN ('leased', 'running')
                    """,
                    (
                        claim.attempt.id.value,
                        claim.attempt.fence_generation,
                    ),
                )
                if changed.rowcount != 1:
                    raise WorkExecutionLeaseLostError("operation_lease_lost")
                changed = connection.execute(
                    """
                    UPDATE stageflow.work_operation
                    SET operation_status = 'succeeded',
                        current_attempt_id = NULL,
                        lease_owner_worker_id = NULL,
                        lease_expires_at = NULL,
                        terminal_result_type = 'transcript_evidence',
                        terminal_result_id = %s,
                        terminal_result_revision = %s,
                        last_reason_code = NULL,
                        row_revision = row_revision + 1,
                        updated_at = statement_timestamp()
                    WHERE operation_id = %s
                      AND current_attempt_id = %s
                      AND fence_generation = %s
                    """,
                    (
                        pending.id.value,
                        evidence_revision,
                        claim.operation.id.value,
                        claim.attempt.id.value,
                        claim.attempt.fence_generation,
                    ),
                )
                if changed.rowcount != 1:
                    raise WorkExecutionLeaseLostError("operation_lease_lost")
                return TranscriptEvidenceRevision(
                    id=pending.id,
                    operation_id=pending.operation_id,
                    work_key=pending.work_key,
                    result_digest=pending.result_digest,
                    asset_id=pending.asset_id,
                    manifest_id=pending.manifest_id,
                    manifest_version=pending.manifest_version,
                    revision=int(evidence_row["evidence_revision"]),
                    predecessor_evidence_id=(
                        None
                        if predecessor is None
                        else EntityId.parse(str(predecessor["evidence_id"]))
                    ),
                    applied_at=evidence_row["applied_at"],
                    result=pending.result,
                    alignments=pending.alignments,
                )
        except (psycopg.InterfaceError, psycopg.OperationalError) as exc:
            raise WorkExecutionStorageUnavailableError(
                "postgresql_work_execution_unavailable"
            ) from exc

    def _insert_evidence_children(
        self,
        connection: psycopg.Connection[Row],
        pending: PendingTranscriptEvidence,
    ) -> None:
        for segment in pending.result.segments:
            connection.execute(
                """
                INSERT INTO stageflow.transcript_evidence_segment (
                    evidence_id, segment_id, segment_ordinal,
                    transcript_text, asset_start_microseconds,
                    asset_end_microseconds, speaker_label,
                    speaker_evidence_kind, confidence,
                    confidence_semantics, limitations
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    pending.id.value,
                    segment.id.value,
                    segment.ordinal,
                    segment.text,
                    segment.asset_start_microseconds,
                    segment.asset_end_microseconds,
                    segment.speaker_label,
                    None
                    if segment.speaker_evidence_kind is None
                    else segment.speaker_evidence_kind.value,
                    segment.confidence,
                    segment.confidence_semantics,
                    list(segment.limitations),
                ),
            )
            for word in segment.words:
                connection.execute(
                    """
                    INSERT INTO stageflow.transcript_evidence_word (
                        evidence_id, segment_id, word_id, word_ordinal,
                        word_text, asset_start_microseconds,
                        asset_end_microseconds, confidence,
                        confidence_semantics, limitations
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        pending.id.value,
                        segment.id.value,
                        word.id.value,
                        word.ordinal,
                        word.text,
                        word.asset_start_microseconds,
                        word.asset_end_microseconds,
                        word.confidence,
                        word.confidence_semantics,
                        list(word.limitations),
                    ),
                )
        for alignment in pending.alignments:
            connection.execute(
                """
                INSERT INTO stageflow.transcript_evidence_alignment (
                    evidence_id, segment_id, alignment_id,
                    media_timing_evidence_id, qualification_status,
                    wall_clock_started_at, wall_clock_ended_at,
                    derived_at, limitations
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    pending.id.value,
                    alignment.segment_id.value,
                    alignment.id.value,
                    alignment.media_timing_evidence_id.value,
                    alignment.qualification_status.value,
                    alignment.wall_clock_started_at,
                    alignment.wall_clock_ended_at,
                    alignment.derived_at,
                    list(alignment.limitations),
                ),
            )

    def reconcile_expired(
        self,
        *,
        limit: int = 100,
    ) -> tuple[DurableOperation, ...]:
        if not 1 <= limit <= 1000:
            raise ValueError("reconcile limit must be between 1 and 1000.")
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    UPDATE stageflow.work_operation_attempt a
                    SET attempt_status = 'finalized',
                        finalized_at = statement_timestamp(),
                        outcome = 'orphaned',
                        retryable = true,
                        reason_code = 'orphaned_attempt',
                        diagnostic_summary = 'attempt no longer owns operation'
                    WHERE a.attempt_status IN ('leased', 'running')
                      AND NOT EXISTS (
                          SELECT 1 FROM stageflow.work_operation o
                          WHERE o.current_attempt_id = a.attempt_id
                      )
                    """
                )
                rows = connection.execute(
                    """
                    SELECT o.*, statement_timestamp() AS database_now
                    FROM stageflow.work_operation o
                    WHERE operation_status IN ('leased', 'running', 'cancel_requested')
                      AND lease_expires_at <= statement_timestamp()
                    ORDER BY lease_expires_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT %s
                    """,
                    (limit,),
                ).fetchall()
                reconciled: list[DurableOperation] = []
                for row in rows:
                    evidence = connection.execute(
                        """
                        SELECT evidence_id, evidence_revision
                        FROM stageflow.transcript_evidence_revision
                        WHERE operation_id = %s
                        """,
                        (str(row["operation_id"]),),
                    ).fetchone()
                    attempt_id = row["current_attempt_id"]
                    if attempt_id is not None:
                        connection.execute(
                            """
                            UPDATE stageflow.work_operation_attempt
                            SET attempt_status = 'finalized',
                                finalized_at = statement_timestamp(),
                                outcome = %s,
                                retryable = %s,
                                reason_code = %s,
                                diagnostic_summary = %s
                            WHERE attempt_id = %s
                              AND attempt_status IN ('leased', 'running')
                            """,
                            (
                                (
                                    AttemptOutcome.RESULT_RECONCILED.value
                                    if evidence is not None
                                    else AttemptOutcome.LEASE_LOST.value
                                ),
                                evidence is None,
                                (
                                    "result_reconciled"
                                    if evidence is not None
                                    else "lease_expired"
                                ),
                                (
                                    "durable result reconciled"
                                    if evidence is not None
                                    else "operation lease expired"
                                ),
                                str(attempt_id),
                            ),
                        )
                    if evidence is not None:
                        updated = connection.execute(
                            """
                            UPDATE stageflow.work_operation
                            SET operation_status = 'succeeded',
                                current_attempt_id = NULL,
                                lease_owner_worker_id = NULL,
                                lease_expires_at = NULL,
                                terminal_result_type = 'transcript_evidence',
                                terminal_result_id = %s,
                                terminal_result_revision = %s,
                                last_reason_code = 'result_reconciled',
                                row_revision = row_revision + 1,
                                updated_at = statement_timestamp()
                            WHERE operation_id = %s
                            RETURNING *
                            """,
                            (
                                str(evidence["evidence_id"]),
                                int(evidence["evidence_revision"]),
                                str(row["operation_id"]),
                            ),
                        ).fetchone()
                    else:
                        retryable = int(row["attempt_count"]) < int(row["max_attempts"])
                        updated = connection.execute(
                            """
                            UPDATE stageflow.work_operation
                            SET operation_status = %s,
                                eligible_at = CASE
                                    WHEN %s THEN statement_timestamp()
                                        + make_interval(
                                            secs => retry_delay_microseconds
                                                / 1000000.0
                                        )
                                    ELSE eligible_at
                                END,
                                current_attempt_id = NULL,
                                lease_owner_worker_id = NULL,
                                lease_expires_at = NULL,
                                last_reason_code = 'lease_expired',
                                row_revision = row_revision + 1,
                                updated_at = statement_timestamp()
                            WHERE operation_id = %s
                            RETURNING *
                            """,
                            (
                                (
                                    OperationStatus.RETRY_WAIT.value
                                    if retryable
                                    else OperationStatus.TERMINAL_FAILED.value
                                ),
                                retryable,
                                str(row["operation_id"]),
                            ),
                        ).fetchone()
                    assert updated is not None
                    reconciled.append(_operation(updated))
                return tuple(reconciled)
        except (psycopg.InterfaceError, psycopg.OperationalError) as exc:
            raise WorkExecutionStorageUnavailableError(
                "postgresql_work_execution_unavailable"
            ) from exc

    def get_operation(self, operation_id: EntityId) -> DurableOperation:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT * FROM stageflow.work_operation
                    WHERE operation_id = %s
                    """,
                    (operation_id.value,),
                ).fetchone()
                if row is None:
                    raise WorkExecutionNotFoundError("operation_not_found")
                return _operation(row)
        except (psycopg.InterfaceError, psycopg.OperationalError) as exc:
            raise WorkExecutionStorageUnavailableError(
                "postgresql_work_execution_unavailable"
            ) from exc

    def list_attempts(
        self,
        operation_id: EntityId,
    ) -> tuple[OperationAttempt, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT * FROM stageflow.work_operation_attempt
                    WHERE operation_id = %s
                    ORDER BY attempt_number
                    """,
                    (operation_id.value,),
                ).fetchall()
                return tuple(_attempt(row) for row in rows)
        except (psycopg.InterfaceError, psycopg.OperationalError) as exc:
            raise WorkExecutionStorageUnavailableError(
                "postgresql_work_execution_unavailable"
            ) from exc

    def get_transcript_evidence(
        self,
        evidence_id: EntityId,
    ) -> TranscriptEvidenceRevision:
        try:
            with self._connect() as connection:
                return self._load_evidence(connection, evidence_id)
        except (psycopg.InterfaceError, psycopg.OperationalError) as exc:
            raise WorkExecutionStorageUnavailableError(
                "postgresql_work_execution_unavailable"
            ) from exc

    def _load_evidence(
        self,
        connection: psycopg.Connection[Row],
        evidence_id: EntityId,
    ) -> TranscriptEvidenceRevision:
        row = connection.execute(
            """
            SELECT * FROM stageflow.transcript_evidence_revision
            WHERE evidence_id = %s
            """,
            (evidence_id.value,),
        ).fetchone()
        if row is None:
            raise WorkExecutionNotFoundError("transcript_evidence_not_found")
        segment_rows = connection.execute(
            """
            SELECT * FROM stageflow.transcript_evidence_segment
            WHERE evidence_id = %s ORDER BY segment_ordinal
            """,
            (evidence_id.value,),
        ).fetchall()
        segments: list[TranscriptSegment] = []
        for segment_row in segment_rows:
            word_rows = connection.execute(
                """
                SELECT * FROM stageflow.transcript_evidence_word
                WHERE evidence_id = %s AND segment_id = %s
                ORDER BY word_ordinal
                """,
                (evidence_id.value, str(segment_row["segment_id"])),
            ).fetchall()
            segments.append(
                TranscriptSegment(
                    id=_entity(segment_row["segment_id"]),
                    ordinal=int(segment_row["segment_ordinal"]),
                    text=str(segment_row["transcript_text"]),
                    asset_start_microseconds=int(
                        segment_row["asset_start_microseconds"]
                    ),
                    asset_end_microseconds=int(
                        segment_row["asset_end_microseconds"]
                    ),
                    speaker_label=cast(str | None, segment_row["speaker_label"]),
                    speaker_evidence_kind=(
                        None
                        if segment_row["speaker_evidence_kind"] is None
                        else SpeakerEvidenceKind(
                            str(segment_row["speaker_evidence_kind"])
                        )
                    ),
                    confidence=cast(float | None, segment_row["confidence"]),
                    confidence_semantics=cast(
                        str | None,
                        segment_row["confidence_semantics"],
                    ),
                    words=tuple(_word(item) for item in word_rows),
                    limitations=tuple(segment_row["limitations"]),
                )
            )
        alignment_rows = connection.execute(
            """
            SELECT * FROM stageflow.transcript_evidence_alignment
            WHERE evidence_id = %s ORDER BY segment_id
            """,
            (evidence_id.value,),
        ).fetchall()
        result = NormalizedTranscriptResult(
            status=TranscriptEvidenceStatus(str(row["evidence_status"])),
            provenance=TranscriptExecutionProvenance(
                provider_id=str(row["provider_id"]),
                provider_version=str(row["provider_version"]),
                model_id=str(row["model_id"]),
                model_version=str(row["model_version"]),
                execution_tool_id=str(row["execution_tool_id"]),
                execution_tool_version=str(row["execution_tool_version"]),
                execution_revision=str(row["execution_revision"]),
                produced_at=row["produced_at"],
            ),
            language=cast(str | None, row["language"]),
            segments=tuple(segments),
            limitations=tuple(row["limitations"]),
            partial_reason=cast(str | None, row["partial_reason"]),
            failure_reason=cast(str | None, row["failure_reason"]),
        )
        return TranscriptEvidenceRevision(
            id=_entity(row["evidence_id"]),
            operation_id=_entity(row["operation_id"]),
            work_key=str(row["work_key"]),
            result_digest=str(row["result_digest"]),
            asset_id=_entity(row["asset_id"]),
            manifest_id=_entity(row["manifest_id"]),
            manifest_version=str(row["manifest_version"]),
            revision=int(row["evidence_revision"]),
            predecessor_evidence_id=_optional_entity(
                row["predecessor_evidence_id"]
            ),
            applied_at=row["applied_at"],
            result=result,
            alignments=tuple(_alignment(item) for item in alignment_rows),
        )

    def status_projection(
        self,
        *,
        deployment_id: str,
        event_id: EntityId | None,
    ) -> WorkExecutionProjection:
        try:
            with self._connect() as connection:
                params = {
                    "deployment_id": deployment_id,
                    "event_id": None if event_id is None else event_id.value,
                }
                where = """
                    deployment_id = %(deployment_id)s
                    AND event_id IS NOT DISTINCT FROM %(event_id)s
                """
                now = connection.execute(
                    "SELECT statement_timestamp() AS database_now"
                ).fetchone()
                counts = connection.execute(
                    f"""
                    SELECT operation_status, count(*) AS count
                    FROM stageflow.work_operation
                    WHERE {where}
                    GROUP BY operation_status
                    """,
                    params,
                ).fetchall()
                oldest = connection.execute(
                    f"""
                    SELECT min(eligible_at) AS oldest_eligible_at
                    FROM stageflow.work_operation
                    WHERE {where}
                      AND operation_status = 'eligible'
                    """,
                    params,
                ).fetchone()
                active = connection.execute(
                    f"""
                    SELECT count(*) AS active_count
                    FROM stageflow.work_operation
                    WHERE {where}
                      AND operation_status IN ('leased', 'running')
                      AND lease_expires_at > statement_timestamp()
                    """,
                    params,
                ).fetchone()
                attention_rows = connection.execute(
                    f"""
                    SELECT DISTINCT reason
                    FROM (
                        SELECT 'required_terminal_failure' AS reason
                        FROM stageflow.work_operation
                        WHERE {where}
                          AND required_for_event
                          AND operation_status IN ('terminal_failed', 'blocked')
                        UNION ALL
                        SELECT 'required_missing_capability' AS reason
                        FROM stageflow.work_operation o
                        WHERE {where}
                          AND o.required_for_event
                          AND o.operation_status = 'eligible'
                          AND NOT EXISTS (
                              SELECT 1
                              FROM stageflow.work_worker_capability c
                              JOIN stageflow.work_worker w
                                ON w.worker_id = c.worker_id
                              WHERE w.deployment_id = o.deployment_id
                                AND w.enabled
                                AND NOT w.draining
                                AND c.configured_eligible
                                AND c.operation_kind = o.operation_kind
                                AND c.operation_schema_version =
                                    o.operation_schema_version
                                AND c.execution_profile_id =
                                    o.execution_profile_id
                                AND c.execution_profile_version =
                                    o.execution_profile_version
                                AND o.asset_format =
                                    ANY(c.accepted_asset_formats)
                          )
                    ) AS attention
                    """,
                    params,
                ).fetchall()
                assert now is not None and oldest is not None and active is not None
                return WorkExecutionProjection(
                    generated_at=now["database_now"],
                    counts=tuple(
                        OperationStatusCount(
                            status=OperationStatus(str(item["operation_status"])),
                            count=int(item["count"]),
                        )
                        for item in counts
                    ),
                    oldest_eligible_at=oldest["oldest_eligible_at"],
                    active_lease_count=int(active["active_count"]),
                    attention_codes=tuple(
                        str(item["reason"]) for item in attention_rows
                    ),
                )
        except (psycopg.InterfaceError, psycopg.OperationalError) as exc:
            raise WorkExecutionStorageUnavailableError(
                "postgresql_work_execution_unavailable"
            ) from exc


def _require_active_claim(
    row: Mapping[str, object] | None,
    claim: OperationClaim,
) -> None:
    if (
        row is None
        or row["operation_status"] not in ("leased", "running")
        or str(row["current_attempt_id"]) != claim.attempt.id.value
        or str(row["lease_owner_worker_id"]) != claim.attempt.worker_id.value
        or int(cast(int, row["fence_generation"]))
        != claim.attempt.fence_generation
        or row["lease_expires_at"] is None
        or cast(datetime, row["lease_expires_at"])
        <= cast(datetime, row["database_now"])
    ):
        raise WorkExecutionLeaseLostError("operation_lease_lost")


def _operation(row: Mapping[str, object]) -> DurableOperation:
    return DurableOperation(
        id=_entity(row["operation_id"]),
        kind=str(row["operation_kind"]),
        schema_version=str(row["operation_schema_version"]),
        deployment_id=str(row["deployment_id"]),
        event_id=_optional_entity(row["event_id"]),
        input=TranscriptionOperationInput(
            asset_id=_entity(row["asset_id"]),
            manifest_id=_entity(row["manifest_id"]),
            manifest_version=str(row["manifest_version"]),
            asset_format=str(row["asset_format"]),
            execution_profile_id=str(row["execution_profile_id"]),
            execution_profile_version=str(row["execution_profile_version"]),
            requested_language=cast(str | None, row["requested_language"]),
            request_word_timing=bool(row["request_word_timing"]),
            request_speaker_labels=bool(row["request_speaker_labels"]),
            requires_cloud=bool(row["requires_cloud"]),
        ),
        idempotency_key=str(row["idempotency_key"]),
        request_digest=str(row["request_digest"]),
        work_key=str(row["work_key"]),
        priority=int(cast(int, row["priority"])),
        eligible_at=cast(Any, row["eligible_at"]),
        status=OperationStatus(str(row["operation_status"])),
        max_attempts=int(cast(int, row["max_attempts"])),
        retry_delay=timedelta(
            microseconds=int(cast(int, row["retry_delay_microseconds"]))
        ),
        required_for_event=bool(row["required_for_event"]),
        attempt_count=int(cast(int, row["attempt_count"])),
        fence_generation=int(cast(int, row["fence_generation"])),
        current_attempt_id=_optional_entity(row["current_attempt_id"]),
        lease_owner_worker_id=_optional_entity(row["lease_owner_worker_id"]),
        lease_expires_at=cast(Any, row["lease_expires_at"]),
        cancellation_requested_at=cast(
            Any,
            row["cancellation_requested_at"],
        ),
        terminal_result_type=cast(str | None, row["terminal_result_type"]),
        terminal_result_id=_optional_entity(row["terminal_result_id"]),
        terminal_result_revision=cast(
            int | None,
            row["terminal_result_revision"],
        ),
        last_reason_code=cast(str | None, row["last_reason_code"]),
        revision=int(cast(int, row["row_revision"])),
        created_at=cast(Any, row["created_at"]),
        updated_at=cast(Any, row["updated_at"]),
    )


def _attempt(row: Mapping[str, object]) -> OperationAttempt:
    return OperationAttempt(
        id=_entity(row["attempt_id"]),
        operation_id=_entity(row["operation_id"]),
        worker_id=_entity(row["worker_id"]),
        attempt_number=int(cast(int, row["attempt_number"])),
        fence_generation=int(cast(int, row["fence_generation"])),
        status=AttemptStatus(str(row["attempt_status"])),
        lease_started_at=cast(Any, row["lease_started_at"]),
        lease_expires_at=cast(Any, row["lease_expires_at"]),
        execution_started_at=cast(Any, row["execution_started_at"]),
        finalized_at=cast(Any, row["finalized_at"]),
        outcome=(
            None
            if row["outcome"] is None
            else AttemptOutcome(str(row["outcome"]))
        ),
        retryable=cast(bool | None, row["retryable"]),
        reason_code=cast(str | None, row["reason_code"]),
        diagnostic_summary=cast(str | None, row["diagnostic_summary"]),
        created_at=cast(Any, row["created_at"]),
    )


def _worker(row: Mapping[str, object]) -> Worker:
    return Worker(
        id=_entity(row["worker_id"]),
        node_id=str(row["node_id"]),
        deployment_id=str(row["deployment_id"]),
        event_id=_optional_entity(row["event_id"]),
        enabled=bool(row["enabled"]),
        draining=bool(row["draining"]),
        implementation_version=str(row["implementation_version"]),
        revision=int(cast(int, row["revision"])),
        created_at=cast(Any, row["created_at"]),
        updated_at=cast(Any, row["updated_at"]),
    )


def _capability(row: Mapping[str, object]) -> WorkerCapability:
    return WorkerCapability(
        id=_entity(row["capability_id"]),
        worker_id=_entity(row["worker_id"]),
        operation_kind=str(row["operation_kind"]),
        operation_schema_version=str(row["operation_schema_version"]),
        execution_profile_id=str(row["execution_profile_id"]),
        execution_profile_version=str(row["execution_profile_version"]),
        locality=ExecutionLocality(str(row["locality"])),
        accepted_asset_formats=tuple(cast(list[str], row["accepted_asset_formats"])),
        supports_word_timing=bool(row["supports_word_timing"]),
        supports_speaker_labels=bool(row["supports_speaker_labels"]),
        provider_id=cast(str | None, row["provider_id"]),
        provider_version=cast(str | None, row["provider_version"]),
        model_id=cast(str | None, row["model_id"]),
        model_version=cast(str | None, row["model_version"]),
        runtime_id=str(row["runtime_id"]),
        runtime_version=str(row["runtime_version"]),
        configured_eligible=bool(row["configured_eligible"]),
        effective_from=cast(Any, row["effective_from"]),
        effective_until=cast(Any, row["effective_until"]),
    )


def _presence(row: Mapping[str, object]) -> WorkerPresence:
    return WorkerPresence(
        worker_id=_entity(row["worker_id"]),
        observed_at=cast(Any, row["observed_at"]),
        expires_at=cast(Any, row["expires_at"]),
        maximum_concurrency=int(cast(int, row["maximum_concurrency"])),
        health=WorkerHealth(str(row["health_state"])),
        pressure=WorkerPressure(str(row["pressure_state"])),
    )


def _word(row: Mapping[str, object]) -> TranscriptWord:
    return TranscriptWord(
        id=_entity(row["word_id"]),
        ordinal=int(cast(int, row["word_ordinal"])),
        text=str(row["word_text"]),
        asset_start_microseconds=int(
            cast(int, row["asset_start_microseconds"])
        ),
        asset_end_microseconds=int(cast(int, row["asset_end_microseconds"])),
        confidence=cast(float | None, row["confidence"]),
        confidence_semantics=cast(str | None, row["confidence_semantics"]),
        limitations=tuple(cast(list[str], row["limitations"])),
    )


def _alignment(row: Mapping[str, object]) -> DerivedTranscriptAlignment:
    return DerivedTranscriptAlignment(
        id=_entity(row["alignment_id"]),
        segment_id=_entity(row["segment_id"]),
        media_timing_evidence_id=_entity(row["media_timing_evidence_id"]),
        qualification_status=RecorderProfileQualificationStatus(
            str(row["qualification_status"])
        ),
        wall_clock_started_at=cast(Any, row["wall_clock_started_at"]),
        wall_clock_ended_at=cast(Any, row["wall_clock_ended_at"]),
        derived_at=cast(Any, row["derived_at"]),
        limitations=tuple(cast(list[str], row["limitations"])),
    )


def _entity(value: object) -> EntityId:
    return EntityId.parse(str(value))


def _optional_entity(value: object) -> EntityId | None:
    return None if value is None else _entity(value)


def _microseconds(value: timedelta) -> int:
    return int(value.total_seconds() * 1_000_000)


__all__ = ["PostgresWorkExecutionRepository"]
