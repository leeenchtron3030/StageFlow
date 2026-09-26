"""Non-durable Work Execution test repository; never a runtime fallback."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from threading import RLock

from app.contexts.transcription_evidence import (
    PendingTranscriptEvidence,
    TranscriptEvidenceRevision,
)
from app.shared.ids import EntityId
from app.shared.time import Clock

from .contracts import (
    AttemptOutcome,
    AttemptStatus,
    ClaimRequest,
    DurableOperation,
    EventNetworkPolicy,
    ExecutionLocality,
    OperationAttempt,
    OperationClaim,
    OperationFailure,
    OperationInput,
    OperationStatus,
    OperationStatusCount,
    PendingOperation,
    TranscriptionOperationInput,
    Worker,
    WorkerCapability,
    WorkerHealth,
    WorkerPresence,
    WorkerPressure,
    WorkExecutionProjection,
)
from .repository import (
    WorkExecutionConflictError,
    WorkExecutionLeaseLostError,
    WorkExecutionNotFoundError,
    WorkExecutionRepository,
)


class InMemoryWorkExecutionRepository(WorkExecutionRepository[OperationInput]):
    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self.operations: dict[EntityId, DurableOperation[OperationInput]] = {}
        self.attempts: dict[EntityId, OperationAttempt] = {}
        self.workers: dict[EntityId, Worker] = {}
        self.capabilities: dict[EntityId, WorkerCapability] = {}
        self.presence: dict[EntityId, WorkerPresence] = {}
        self.evidence: dict[EntityId, TranscriptEvidenceRevision] = {}
        self._lock = RLock()

    def enqueue(
        self, pending: PendingOperation[OperationInput],
    ) -> DurableOperation[OperationInput]:
        request = pending.request
        with self._lock:
            matches = [old for old in self.operations.values()
                       if old.id == request.operation_id
                       or old.idempotency_key == request.idempotency_key
                       or old.work_key == pending.work_key]
            if len(matches) > 1:
                raise WorkExecutionConflictError("transcription_enqueue_identity_conflict")
            for old in matches:
                if (old.id == request.operation_id or old.idempotency_key == request.idempotency_key
                        or old.work_key == pending.work_key):
                    if (old.kind == request.input.kind == "render"
                            and old.work_key == pending.work_key
                            and old.id != request.operation_id
                            and old.idempotency_key != request.idempotency_key
                            and old.deployment_id == request.deployment_id
                            and old.event_id == request.event_id):
                        return old
                    if (old.id != request.operation_id
                            or old.idempotency_key != request.idempotency_key
                            or old.work_key != pending.work_key
                            or old.request_digest != pending.request_digest):
                        raise WorkExecutionConflictError("transcription_enqueue_identity_conflict")
                    return old
            operation = DurableOperation(
                id=request.operation_id, kind=request.input.kind, schema_version="v1",
                deployment_id=request.deployment_id, event_id=request.event_id, input=request.input,
                idempotency_key=request.idempotency_key, request_digest=pending.request_digest,
                work_key=pending.work_key, priority=request.priority,
                eligible_at=request.eligible_at,
                status=OperationStatus.PENDING, max_attempts=request.max_attempts,
                retry_delay=request.retry_delay, required_for_event=request.required_for_event,
                attempt_count=0, fence_generation=0, current_attempt_id=None,
                lease_owner_worker_id=None, lease_expires_at=None, cancellation_requested_at=None,
                terminal_result_type=None, terminal_result_id=None, terminal_result_revision=None,
                last_reason_code=None, revision=1, created_at=request.requested_at,
                updated_at=request.requested_at,
            )
            self.operations[operation.id] = operation
            return operation

    def register_worker(self, worker: Worker) -> Worker:
        with self._lock:
            old = self.workers.get(worker.id)
            if old is not None:
                if (old.node_id, old.deployment_id, old.event_id) != (
                        worker.node_id, worker.deployment_id, worker.event_id):
                    raise WorkExecutionConflictError("worker_identity_conflict")
                if (old.enabled, old.draining, old.implementation_version) == (
                        worker.enabled, worker.draining, worker.implementation_version):
                    return old
                worker = replace(worker, revision=old.revision + 1, created_at=old.created_at)
            self.workers[worker.id] = worker
            return worker

    def register_capability(self, capability: WorkerCapability) -> WorkerCapability:
        with self._lock:
            if capability.worker_id not in self.workers:
                raise WorkExecutionNotFoundError("worker_not_found")
            old = self.capabilities.get(capability.id)
            if old is not None:
                if replace(capability, effective_from=old.effective_from,
                           effective_until=old.effective_until) != old:
                    raise WorkExecutionConflictError("worker_capability_identity_conflict")
                return old
            self.capabilities[capability.id] = capability
            return capability

    def record_presence(self, worker_id: EntityId, *, ttl: timedelta, maximum_concurrency: int,
                        health: WorkerHealth, pressure: WorkerPressure) -> WorkerPresence:
        with self._lock:
            if worker_id not in self.workers:
                raise WorkExecutionNotFoundError("worker_not_found")
            if not timedelta(0) < ttl <= timedelta(hours=1):
                raise ValueError("presence ttl must be positive and at most one hour.")
            now = self.clock.now()
            presence = WorkerPresence(worker_id, now, now + ttl, maximum_concurrency,
                                      health, pressure)
            self.presence[worker_id] = presence
            return presence

    def claim_next(self, request: ClaimRequest) -> OperationClaim[OperationInput] | None:
        with self._lock:
            now = self.clock.now()
            worker = self.workers.get(request.worker_id)
            presence = self.presence.get(request.worker_id)
            if worker is None:
                raise WorkExecutionNotFoundError("worker_not_found")
            if (not worker.enabled or worker.draining or presence is None
                    or presence.expires_at <= now
                    or presence.health not in (WorkerHealth.AVAILABLE, WorkerHealth.DEGRADED)):
                return None
            active = sum(o.lease_owner_worker_id == worker.id and o.lease_expires_at is not None
                         and o.lease_expires_at > now
                         and o.status in (OperationStatus.LEASED, OperationStatus.RUNNING)
                         for o in self.operations.values())
            if active >= presence.maximum_concurrency:
                return None
            network = request.network_policy == EventNetworkPolicy.NETWORK_PERMITTED
            for operation in sorted(self.operations.values(), key=lambda o: (
                    -o.priority, o.eligible_at, o.created_at)):
                if operation.deployment_id != worker.deployment_id:
                    continue
                if (operation.status in (OperationStatus.PENDING, OperationStatus.RETRY_WAIT)
                        and operation.eligible_at <= now):
                    operation = replace(operation, status=OperationStatus.ELIGIBLE,
                                        last_reason_code=None, revision=operation.revision + 1,
                                        updated_at=now)
                if (operation.status == OperationStatus.ELIGIBLE
                        and operation.input.requires_cloud and not network):
                    operation = replace(operation, status=OperationStatus.DEFERRED,
                                        last_reason_code="cloud_required_event_mode",
                                        revision=operation.revision + 1, updated_at=now)
                elif (operation.status == OperationStatus.DEFERRED and network
                      and operation.last_reason_code == "cloud_required_event_mode"
                      and operation.eligible_at <= now):
                    operation = replace(operation, status=OperationStatus.ELIGIBLE,
                                        last_reason_code=None, revision=operation.revision + 1,
                                        updated_at=now)
                self.operations[operation.id] = operation
                if (operation.status != OperationStatus.ELIGIBLE
                        or operation.event_id not in (None, worker.event_id)
                        or request.operation_kind not in (None, operation.kind)):
                    continue
                if not any(self._matches(c, operation, request)
                           for c in self.capabilities.values()):
                    continue
                attempt = OperationAttempt(
                    EntityId.new(), operation.id, worker.id, operation.attempt_count + 1,
                    operation.fence_generation + 1, AttemptStatus.LEASED,
                    now, now + request.lease_duration, None, None, None, None, None, None, now,
                )
                operation = replace(
                    operation, status=OperationStatus.LEASED, attempt_count=attempt.attempt_number,
                    fence_generation=attempt.fence_generation, current_attempt_id=attempt.id,
                    lease_owner_worker_id=worker.id, lease_expires_at=attempt.lease_expires_at,
                    last_reason_code=None, revision=operation.revision + 1, updated_at=now,
                )
                self.operations[operation.id], self.attempts[attempt.id] = operation, attempt
                return OperationClaim(operation, attempt)
            return None

    def _matches(self, capability: WorkerCapability, operation: DurableOperation[OperationInput],
                 request: ClaimRequest) -> bool:
        value, now = operation.input, self.clock.now()
        if (capability.worker_id != request.worker_id or not capability.configured_eligible
                or capability.operation_kind != operation.kind
                or capability.operation_schema_version != operation.schema_version
                or capability.execution_profile_id != value.execution_profile_id
                or capability.execution_profile_version != value.execution_profile_version
                or capability.effective_from > now
                or (capability.effective_until is not None and capability.effective_until <= now)):
            return False
        if (request.network_policy == EventNetworkPolicy.LOCAL_ONLY
                and capability.locality != ExecutionLocality.LOCAL):
            return False
        if value.requires_cloud and capability.locality != ExecutionLocality.CLOUD:
            return False
        return not isinstance(value, TranscriptionOperationInput) or (
            value.asset_format in (capability.accepted_asset_formats or ())
            and (not value.request_word_timing or capability.supports_word_timing)
            and (not value.request_speaker_labels or capability.supports_speaker_labels)
        )

    def _active(self, claim: OperationClaim[OperationInput]) -> DurableOperation[OperationInput]:
        operation = self.get_operation(claim.operation.id)
        if (operation.status not in (OperationStatus.LEASED, OperationStatus.RUNNING)
                or operation.current_attempt_id != claim.attempt.id
                or operation.lease_owner_worker_id != claim.attempt.worker_id
                or operation.fence_generation != claim.attempt.fence_generation
                or operation.lease_expires_at is None
                or operation.lease_expires_at <= self.clock.now()):
            raise WorkExecutionLeaseLostError("operation_lease_lost")
        return operation

    def mark_running(self, claim: OperationClaim[OperationInput]) -> OperationClaim[OperationInput]:
        return self._advance(claim, None)

    def renew(self, claim: OperationClaim[OperationInput], *,
              lease_duration: timedelta) -> OperationClaim[OperationInput]:
        if not timedelta(0) < lease_duration <= timedelta(hours=1):
            raise ValueError("lease duration must be positive and at most one hour")
        return self._advance(claim, lease_duration)

    def _advance(self, claim: OperationClaim[OperationInput],
                 lease_duration: timedelta | None) -> OperationClaim[OperationInput]:
        with self._lock:
            operation = self._active(claim)
            attempt = self.attempts[claim.attempt.id]
            now = self.clock.now()
            if lease_duration is None:
                operation = replace(operation, status=OperationStatus.RUNNING)
                attempt = replace(attempt, status=AttemptStatus.RUNNING,
                                  execution_started_at=attempt.execution_started_at or now)
            else:
                operation = replace(operation, lease_expires_at=now + lease_duration)
                attempt = replace(attempt, lease_expires_at=now + lease_duration)
            operation = replace(operation, revision=operation.revision + 1, updated_at=now)
            self.operations[operation.id], self.attempts[attempt.id] = operation, attempt
            return OperationClaim(operation, attempt)

    def record_failure(self, claim: OperationClaim[OperationInput],
                       failure: OperationFailure) -> DurableOperation[OperationInput]:
        with self._lock:
            operation = self._active(claim)
            retry = failure.retryable and operation.attempt_count < operation.max_attempts
            finalized = self._finalize(
                operation, OperationStatus.RETRY_WAIT if retry else OperationStatus.TERMINAL_FAILED,
                AttemptOutcome.RETRYABLE_FAILURE if retry else AttemptOutcome.TERMINAL_FAILURE,
                failure.reason_code, failure.diagnostic_summary, retry,
                failure.retry_delay or operation.retry_delay,
            )
            self.attempts[claim.attempt.id] = replace(
                self.attempts[claim.attempt.id], retryable=failure.retryable,
            )
            return finalized

    def _finalize(self, operation: DurableOperation[OperationInput], status: OperationStatus,
                  outcome: AttemptOutcome, reason: str, diagnostic: str, retry: bool,
                  delay: timedelta) -> DurableOperation[OperationInput]:
        now = self.clock.now()
        assert operation.current_attempt_id is not None
        attempt = self.attempts[operation.current_attempt_id]
        self.attempts[attempt.id] = replace(attempt, status=AttemptStatus.FINALIZED,
                                           finalized_at=now, outcome=outcome, retryable=retry,
                                           reason_code=reason, diagnostic_summary=diagnostic)
        operation = replace(operation, status=status, current_attempt_id=None,
                            lease_owner_worker_id=None, lease_expires_at=None,
                            eligible_at=now + delay if retry else operation.eligible_at,
                            last_reason_code=reason, revision=operation.revision + 1,
                            updated_at=now)
        self.operations[operation.id] = operation
        return operation

    def reconcile_expired(
        self, *, limit: int = 100,
    ) -> tuple[DurableOperation[OperationInput], ...]:
        if not 1 <= limit <= 1000:
            raise ValueError("reconcile limit must be between 1 and 1000.")
        with self._lock:
            rows: list[DurableOperation[OperationInput]] = []
            for operation in sorted(self.operations.values(), key=lambda o: o.lease_expires_at
                                    or o.created_at):
                if (operation.status in (OperationStatus.LEASED, OperationStatus.RUNNING,
                                         OperationStatus.CANCEL_REQUESTED)
                        and operation.lease_expires_at is not None
                        and operation.lease_expires_at <= self.clock.now()):
                    retry = operation.attempt_count < operation.max_attempts
                    rows.append(self._finalize(
                        operation,
                        OperationStatus.RETRY_WAIT if retry else OperationStatus.TERMINAL_FAILED,
                        AttemptOutcome.LEASE_LOST, "lease_expired", "operation lease expired",
                        retry, operation.retry_delay,
                    ))
                    if len(rows) == limit:
                        break
            return tuple(rows)

    def get_operation(self, operation_id: EntityId) -> DurableOperation[OperationInput]:
        try:
            return self.operations[operation_id]
        except KeyError as exc:
            raise WorkExecutionNotFoundError("operation_not_found") from exc

    def list_attempts(self, operation_id: EntityId) -> tuple[OperationAttempt, ...]:
        return tuple(sorted((a for a in self.attempts.values() if a.operation_id == operation_id),
                            key=lambda a: a.attempt_number))

    def get_transcript_evidence(self, evidence_id: EntityId) -> TranscriptEvidenceRevision:
        try:
            return self.evidence[evidence_id]
        except KeyError as exc:
            raise WorkExecutionNotFoundError("transcript_evidence_not_found") from exc

    def apply_transcript_result(self, claim: OperationClaim[OperationInput],
                                pending: PendingTranscriptEvidence) -> TranscriptEvidenceRevision:
        with self._lock:
            value = claim.operation.input
            if not isinstance(value, TranscriptionOperationInput):
                raise WorkExecutionConflictError("transcript_result_requires_transcription")
            for old in self.evidence.values():
                if old.operation_id == claim.operation.id:
                    if (old.result_digest != pending.result_digest
                            or old.work_key != pending.work_key):
                        raise WorkExecutionConflictError("transcript_result_identity_conflict")
                    return old
            operation = self._active(claim)
            if (pending.operation_id != operation.id or pending.work_key != operation.work_key
                    or pending.asset_id != value.asset_id
                    or pending.manifest_id != value.manifest_id
                    or pending.manifest_version != value.manifest_version):
                raise WorkExecutionConflictError("transcript_result_identity_conflict")
            previous = sorted((e for e in self.evidence.values() if e.asset_id == value.asset_id),
                              key=lambda e: e.revision)
            evidence = TranscriptEvidenceRevision(
                pending.id, pending.operation_id, pending.work_key, pending.result_digest,
                pending.asset_id, pending.manifest_id, pending.manifest_version, len(previous) + 1,
                previous[-1].id if previous else None, self.clock.now(), pending.result,
                pending.alignments,
            )
            operation = self._finalize(operation, OperationStatus.SUCCEEDED,
                                       AttemptOutcome.SUCCEEDED, "result_applied",
                                       "durable result applied", False, operation.retry_delay)
            self.operations[operation.id] = replace(
                operation, terminal_result_type="transcript_evidence",
                terminal_result_id=evidence.id, terminal_result_revision=evidence.revision,
            )
            self.evidence[evidence.id] = evidence
            return evidence

    def status_projection(self, *, deployment_id: str,
                          event_id: EntityId | None) -> WorkExecutionProjection:
        now = self.clock.now()
        rows = [o for o in self.operations.values()
                if o.deployment_id == deployment_id and o.event_id == event_id]
        eligible = [o.eligible_at for o in rows if o.status == OperationStatus.ELIGIBLE]
        attention: set[str] = set()
        for operation in rows:
            if not operation.required_for_event:
                continue
            if operation.status in (OperationStatus.TERMINAL_FAILED, OperationStatus.BLOCKED):
                attention.add("required_terminal_failure")
            if operation.status == OperationStatus.ELIGIBLE and not any(
                (worker := self.workers[c.worker_id]).deployment_id == operation.deployment_id
                and worker.enabled and not worker.draining and c.configured_eligible
                and c.operation_kind == operation.kind
                and c.operation_schema_version == operation.schema_version
                and c.execution_profile_id == operation.input.execution_profile_id
                and c.execution_profile_version == operation.input.execution_profile_version
                and (operation.input.kind == "render"
                     or operation.input.asset_format in (c.accepted_asset_formats or ()))
                for c in self.capabilities.values()
            ):
                attention.add("required_missing_capability")
        return WorkExecutionProjection(
            now, tuple(OperationStatusCount(s, sum(o.status == s for o in rows))
                       for s in OperationStatus if any(o.status == s for o in rows)),
            min(eligible, default=None),
            sum(o.lease_expires_at is not None and o.lease_expires_at > now
                and o.status in (OperationStatus.LEASED, OperationStatus.RUNNING)
                for o in rows), tuple(attention),
        )
