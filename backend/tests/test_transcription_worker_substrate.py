from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.contexts.production.media_timing_evidence import (
    MediaTimingDerivation,
    MediaTimingEvidence,
    MediaTimingInspectionProvenance,
    MediaTimingInspectionResult,
    MediaTimingObservation,
    RecorderProfileQualification,
    RecorderProfileQualificationStatus,
    TimingTimezoneKind,
)
from app.contexts.transcription_evidence import (
    NormalizedTranscriptResult,
    PendingTranscriptEvidence,
    TranscriptEvidenceRevision,
    TranscriptEvidenceStatus,
    TranscriptExecutionProvenance,
    TranscriptionExecutionError,
    TranscriptionExecutionRequest,
    TranscriptSegment,
    TranscriptTimingEpistemicKind,
    TranscriptWord,
    align_with_media_timing,
)
from app.contexts.work_execution import (
    AttemptStatus,
    ClaimRequest,
    DurableOperation,
    EnqueueTranscriptionOperation,
    EventNetworkPolicy,
    OperationAttempt,
    OperationClaim,
    OperationFailure,
    OperationStatus,
    PendingOperation,
    TranscriptionOperationInput,
    TranscriptionWorker,
    Worker,
    WorkerCapability,
    WorkerCycleOutcome,
    WorkerHealth,
    WorkerPresence,
    WorkerPressure,
    WorkExecutionProjection,
    WorkExecutionRepository,
    enqueue_request_digest,
    transcription_work_key,
)
from app.shared.ids import EntityId

NOW = datetime(2026, 8, 17, 12, tzinfo=UTC)


def operation_input(*, profile_version: str = "v1") -> TranscriptionOperationInput:
    return TranscriptionOperationInput(
        asset_id=EntityId.new(),
        manifest_id=EntityId.new(),
        manifest_version="manifest-v1",
        asset_format="wav",
        execution_profile_id="test-profile",
        execution_profile_version=profile_version,
        requested_language="en",
        request_word_timing=True,
        request_speaker_labels=False,
    )


def enqueue_request(
    value: TranscriptionOperationInput,
) -> EnqueueTranscriptionOperation:
    return EnqueueTranscriptionOperation(
        operation_id=EntityId.new(),
        idempotency_key=f"transcription:{value.asset_id.value}",
        deployment_id="test-deployment",
        event_id=None,
        input=value,
        priority=10,
        eligible_at=NOW,
        max_attempts=3,
        retry_delay=timedelta(seconds=5),
        required_for_event=False,
        requested_at=NOW,
    )


def claimed_operation(
    value: TranscriptionOperationInput,
) -> OperationClaim:
    operation_id = EntityId.new()
    worker_id = EntityId.new()
    attempt_id = EntityId.new()
    operation = DurableOperation(
        id=operation_id,
        kind="transcription",
        schema_version="v1",
        deployment_id="test-deployment",
        event_id=None,
        input=value,
        idempotency_key=f"operation:{operation_id.value}",
        request_digest="1" * 64,
        work_key="2" * 64,
        priority=10,
        eligible_at=NOW,
        status=OperationStatus.LEASED,
        max_attempts=3,
        retry_delay=timedelta(seconds=5),
        required_for_event=False,
        attempt_count=1,
        fence_generation=1,
        current_attempt_id=attempt_id,
        lease_owner_worker_id=worker_id,
        lease_expires_at=NOW + timedelta(minutes=1),
        cancellation_requested_at=None,
        terminal_result_type=None,
        terminal_result_id=None,
        terminal_result_revision=None,
        last_reason_code=None,
        revision=2,
        created_at=NOW,
        updated_at=NOW,
    )
    attempt = OperationAttempt(
        id=attempt_id,
        operation_id=operation_id,
        worker_id=worker_id,
        attempt_number=1,
        fence_generation=1,
        status=AttemptStatus.LEASED,
        lease_started_at=NOW,
        lease_expires_at=NOW + timedelta(minutes=1),
        execution_started_at=None,
        finalized_at=None,
        outcome=None,
        retryable=None,
        reason_code=None,
        diagnostic_summary=None,
        created_at=NOW,
    )
    return OperationClaim(operation=operation, attempt=attempt)


def transcript_result() -> NormalizedTranscriptResult:
    segment = TranscriptSegment(
        id=EntityId.new(),
        ordinal=0,
        text="bounded deterministic transcript",
        asset_start_microseconds=250_000,
        asset_end_microseconds=1_250_000,
        confidence=0.8,
        confidence_semantics="provider_probability",
        words=(
            TranscriptWord(
                id=EntityId.new(),
                ordinal=0,
                text="bounded",
                asset_start_microseconds=250_000,
                asset_end_microseconds=600_000,
            ),
        ),
    )
    return NormalizedTranscriptResult(
        status=TranscriptEvidenceStatus.COMPLETE,
        provenance=TranscriptExecutionProvenance(
            provider_id="deterministic-fake",
            provider_version="v1",
            model_id="fake-model",
            model_version="v1",
            execution_tool_id="test-adapter",
            execution_tool_version="v1",
            execution_revision="fixture-v1",
            produced_at=NOW,
        ),
        language="en",
        segments=(segment,),
        limitations=("synthetic_test_evidence",),
    )


class FakeRepository(WorkExecutionRepository):
    def __init__(self, claim: OperationClaim) -> None:
        self.claim: OperationClaim | None = claim
        self.renewal_count = 0
        self.applied: PendingTranscriptEvidence | None = None

    def enqueue(self, pending: PendingOperation) -> DurableOperation:
        raise NotImplementedError

    def register_worker(self, worker: Worker) -> Worker:
        raise NotImplementedError

    def register_capability(
        self,
        capability: WorkerCapability,
    ) -> WorkerCapability:
        raise NotImplementedError

    def record_presence(
        self,
        worker_id: EntityId,
        *,
        ttl: timedelta,
        maximum_concurrency: int,
        health: WorkerHealth,
        pressure: WorkerPressure,
    ) -> WorkerPresence:
        raise NotImplementedError

    def claim_next(self, request: ClaimRequest) -> OperationClaim | None:
        claim = self.claim
        self.claim = None
        return claim

    def mark_running(self, claim: OperationClaim) -> OperationClaim:
        active = OperationClaim(
            operation=replace(claim.operation, status=OperationStatus.RUNNING),
            attempt=replace(
                claim.attempt,
                status=AttemptStatus.RUNNING,
                execution_started_at=NOW,
            ),
        )
        return active

    def renew(
        self,
        claim: OperationClaim,
        *,
        lease_duration: timedelta,
    ) -> OperationClaim:
        self.renewal_count += 1
        expires = claim.attempt.lease_expires_at + lease_duration
        return OperationClaim(
            operation=replace(claim.operation, lease_expires_at=expires),
            attempt=replace(claim.attempt, lease_expires_at=expires),
        )

    def record_failure(
        self,
        claim: OperationClaim,
        failure: OperationFailure,
    ) -> DurableOperation:
        return replace(claim.operation, status=OperationStatus.TERMINAL_FAILED)

    def apply_transcript_result(
        self,
        claim: OperationClaim,
        pending: PendingTranscriptEvidence,
    ) -> TranscriptEvidenceRevision:
        self.applied = pending
        return TranscriptEvidenceRevision(
            id=pending.id,
            operation_id=pending.operation_id,
            work_key=pending.work_key,
            result_digest=pending.result_digest,
            asset_id=pending.asset_id,
            manifest_id=pending.manifest_id,
            manifest_version=pending.manifest_version,
            revision=1,
            predecessor_evidence_id=None,
            applied_at=NOW,
            result=pending.result,
            alignments=pending.alignments,
        )

    def reconcile_expired(
        self,
        *,
        limit: int = 100,
    ) -> tuple[DurableOperation, ...]:
        raise NotImplementedError

    def get_operation(self, operation_id: EntityId) -> DurableOperation:
        raise NotImplementedError

    def list_attempts(
        self,
        operation_id: EntityId,
    ) -> tuple[OperationAttempt, ...]:
        raise NotImplementedError

    def get_transcript_evidence(
        self,
        evidence_id: EntityId,
    ) -> TranscriptEvidenceRevision:
        raise NotImplementedError

    def status_projection(
        self,
        *,
        deployment_id: str,
        event_id: EntityId | None,
    ) -> WorkExecutionProjection:
        raise NotImplementedError


class DeterministicAdapter:
    def __init__(self, result: NormalizedTranscriptResult) -> None:
        self.result = result
        self.requests: list[TranscriptionExecutionRequest] = []

    def execute(
        self,
        request: TranscriptionExecutionRequest,
        renew_lease: Callable[[], None],
    ) -> NormalizedTranscriptResult:
        self.requests.append(request)
        renew_lease()
        return self.result


class FailingAdapter:
    def execute(
        self,
        request: TranscriptionExecutionRequest,
        renew_lease: Callable[[], None],
    ) -> NormalizedTranscriptResult:
        raise TranscriptionExecutionError(
            "provider_unavailable",
            retryable=False,
            diagnostic_summary="deterministic provider failure",
        )


def test_stable_work_key_excludes_schedule_but_enqueue_digest_does_not() -> None:
    value = operation_input()
    first = enqueue_request(value)
    second = replace(
        first,
        operation_id=EntityId.new(),
        idempotency_key="transcription:alternate",
        priority=50,
    )

    assert transcription_work_key(first) == transcription_work_key(second)
    assert enqueue_request_digest(first) != enqueue_request_digest(second)
    assert transcription_work_key(
        replace(first, input=replace(value, execution_profile_version="v2"))
    ) != transcription_work_key(first)


def test_evidence_contract_preserves_relative_timing_and_known_confidence() -> None:
    result = transcript_result()
    segment = result.segments[0]

    assert segment.epistemic_kind is TranscriptTimingEpistemicKind.OBSERVED
    assert segment.asset_start_microseconds == 250_000
    assert segment.confidence_semantics == "provider_probability"
    assert segment.words[0].asset_start_microseconds == 250_000
    with pytest.raises(ValueError, match="requires explicit known semantics"):
        replace(segment, confidence_semantics=None)


def test_worker_cycle_renews_and_applies_deterministic_evidence() -> None:
    claim = claimed_operation(operation_input())
    repository = FakeRepository(claim)
    adapter = DeterministicAdapter(transcript_result())
    worker = TranscriptionWorker(repository=repository, execution_port=adapter)

    result = worker.run_once(
        ClaimRequest(
            worker_id=claim.attempt.worker_id,
            network_policy=EventNetworkPolicy.LOCAL_ONLY,
            lease_duration=timedelta(seconds=30),
        )
    )

    assert result.outcome is WorkerCycleOutcome.SUCCEEDED
    assert result.operation_id == claim.operation.id
    assert repository.renewal_count == 1
    assert repository.applied is not None
    assert repository.applied.asset_id == claim.operation.input.asset_id
    assert adapter.requests[0].fence_generation == 1


def test_worker_cycle_maps_typed_execution_failure_without_retry() -> None:
    claim = claimed_operation(operation_input())
    worker = TranscriptionWorker(
        repository=FakeRepository(claim),
        execution_port=FailingAdapter(),
    )

    result = worker.run_once(
        ClaimRequest(
            worker_id=claim.attempt.worker_id,
            network_policy=EventNetworkPolicy.LOCAL_ONLY,
            lease_duration=timedelta(seconds=30),
        )
    )

    assert result.outcome is WorkerCycleOutcome.TERMINAL_FAILED


def test_unqualified_mte_alignment_is_advisory_and_preserves_relative_values() -> None:
    result = transcript_result()
    observation_id = EntityId.new()
    started = NOW - timedelta(hours=1)
    evidence = MediaTimingEvidence(
        id=EntityId.new(),
        asset_id=EntityId.new(),
        manifest_id=EntityId.new(),
        manifest_version="manifest-v1",
        revision=1,
        predecessor_evidence_id=None,
        operation_id=EntityId.new(),
        request_digest="request-v1",
        applied_at=NOW,
        result=MediaTimingInspectionResult(
            provenance=MediaTimingInspectionProvenance(
                provider_id="probe",
                provider_version="v1",
                tool_id="probe-tool",
                tool_version="v1",
                recorder_profile_id="vmix-unqualified",
                recorder_profile_revision=1,
                inspected_at=NOW - timedelta(minutes=1),
            ),
            observations=(
                MediaTimingObservation(
                    id=observation_id,
                    kind="container_timestamp",
                    source_field="creation_time",
                    original_representation="2026-08-17T11:00:00Z",
                    observed_at=NOW - timedelta(minutes=1),
                    timezone_kind=TimingTimezoneKind.EXPLICIT_UTC,
                    normalized_timestamp=started,
                ),
            ),
            derivations=(
                MediaTimingDerivation(
                    id=EntityId.new(),
                    rule_id="container_start_plus_duration",
                    rule_version="v1",
                    input_observation_ids=(observation_id,),
                    candidate_started_at=started,
                    candidate_ended_at=started + timedelta(hours=1),
                    derived_at=NOW - timedelta(minutes=1),
                ),
            ),
            qualification=RecorderProfileQualification(
                profile_id="vmix-unqualified",
                profile_revision=1,
                status=RecorderProfileQualificationStatus.UNQUALIFIED,
                evaluated_at=NOW - timedelta(minutes=1),
                limitations=("profile_not_qualified",),
            ),
        ),
    )

    alignments = align_with_media_timing(result, evidence, derived_at=NOW)
    segment = result.segments[0]

    assert segment.asset_start_microseconds == 250_000
    assert alignments[0].epistemic_kind is TranscriptTimingEpistemicKind.DERIVED
    assert alignments[0].wall_clock_started_at == started + timedelta(
        microseconds=250_000
    )
    assert "recorder_profile_unqualified" in alignments[0].limitations
    assert (
        alignments[0].qualification_status
        is RecorderProfileQualificationStatus.UNQUALIFIED
    )


def test_migration_separates_durable_history_from_replaceable_presence() -> None:
    sql = Path(__file__).parents[1] / "app" / "infrastructure" / "postgres" / "sql"
    forward = (sql / "0007_transcription_worker_forward.sql").read_text(
        encoding="utf-8"
    )
    reverse = (sql / "0007_transcription_worker_reverse.sql").read_text(
        encoding="utf-8"
    )

    assert "work_operation_attempt" in forward
    assert "work_worker_capability" in forward
    assert "worker_id uuid PRIMARY KEY" in forward
    presence = forward.split(
        "CREATE TABLE IF NOT EXISTS stageflow.work_worker_presence",
        maxsplit=1,
    )[1].split(");", maxsplit=1)[0]
    assert "utilization" not in presence
    assert "expires_at timestamptz NOT NULL" in presence
    assert "FOR UPDATE" not in forward
    assert "completed_media_asset_registry" not in reverse
    assert "media_timing_evidence" not in reverse
    assert "business_event" not in reverse
