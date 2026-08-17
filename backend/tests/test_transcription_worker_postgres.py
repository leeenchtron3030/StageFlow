from __future__ import annotations

import inspect
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from app.contexts.transcription_evidence import (
    NormalizedTranscriptResult,
    TranscriptEvidenceStatus,
    TranscriptExecutionProvenance,
    TranscriptSegment,
    prepare_transcript_evidence,
)
from app.contexts.work_execution import (
    ClaimRequest,
    EnqueueTranscriptionOperation,
    EventNetworkPolicy,
    ExecutionLocality,
    OperationClaim,
    OperationStatus,
    TranscriptionOperationApplication,
    TranscriptionOperationInput,
    Worker,
    WorkerCapability,
    WorkerHealth,
    WorkerPressure,
    WorkExecutionConflictError,
    WorkExecutionLeaseLostError,
)
from app.infrastructure.postgres import (
    PostgresMigrationRunner,
    PostgresWorkExecutionRepository,
)
from app.shared.ids import EntityId

_POSTGRES_DSN = os.getenv("STAGEFLOW_TEST_POSTGRES_DSN")


def test_fenced_postgres_transitions_select_database_time() -> None:
    transition_names = (
        "_advance_active_claim",
        "record_failure",
        "apply_transcript_result",
    )

    for transition_name in transition_names:
        transition = getattr(PostgresWorkExecutionRepository, transition_name)
        assert "statement_timestamp() AS database_now" in inspect.getsource(transition)


def _seed_asset(
    dsn: str,
    *,
    observed_at: datetime,
) -> tuple[EntityId, EntityId, EntityId]:
    suffix = EntityId.new().value
    event_id = EntityId.new()
    stage_id = EntityId.new()
    candidate_id = EntityId.new()
    asset_id = EntityId.new()
    manifest_id = EntityId.new()
    source_key = f"transcription-source-{suffix}"
    with psycopg.connect(dsn) as connection:
        connection.execute(
            """
            INSERT INTO stageflow.business_event (
                event_id, event_key, name, revision, created_at, updated_at
            ) VALUES (%s, %s, 'Transcription test', 1, %s, %s)
            """,
            (
                event_id.value,
                f"transcription-event-{suffix}",
                observed_at,
                observed_at,
            ),
        )
        connection.execute(
            """
            INSERT INTO stageflow.stage (
                stage_id, event_id, stage_key, name,
                revision, created_at, updated_at
            ) VALUES (%s, %s, %s, 'Main', 1, %s, %s)
            """,
            (
                stage_id.value,
                event_id.value,
                f"stage-{suffix}",
                observed_at,
                observed_at,
            ),
        )
        connection.execute(
            """
            INSERT INTO stageflow.stage_source_binding (
                source_binding_key, stage_id, source_reference,
                revision, updated_at
            ) VALUES (%s, %s, 'sanitized-reference', 1, %s)
            """,
            (source_key, stage_id.value, observed_at),
        )
        connection.execute(
            """
            INSERT INTO stageflow.media_candidate (
                candidate_id, proposed_asset_id, stage_id,
                source_binding_key, source_reference,
                discovered_at, last_observed_at,
                registration_state, revision
            ) VALUES (
                %s, %s, %s, %s, 'sanitized-reference',
                %s, %s, 'registered', 1
            )
            """,
            (
                candidate_id.value,
                asset_id.value,
                stage_id.value,
                source_key,
                observed_at,
                observed_at,
            ),
        )
        connection.execute(
            """
            INSERT INTO stageflow.completed_media_asset_registry (
                asset_id, candidate_id, manifest_id, stage_id,
                source_binding_key, registered_at
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                asset_id.value,
                candidate_id.value,
                manifest_id.value,
                stage_id.value,
                source_key,
                observed_at,
            ),
        )
    return event_id, asset_id, manifest_id


def _register_worker(
    repository: PostgresWorkExecutionRepository,
    *,
    event_id: EntityId,
    observed_at: datetime,
    profiles: tuple[tuple[str, ExecutionLocality], ...],
) -> Worker:
    worker = Worker(
        id=EntityId.new(),
        node_id=f"node-{EntityId.new().value}",
        deployment_id="test-deployment",
        event_id=event_id,
        enabled=True,
        draining=False,
        implementation_version="test-v1",
        revision=1,
        created_at=observed_at,
        updated_at=observed_at,
    )
    repository.register_worker(worker)
    for profile, locality in profiles:
        repository.register_capability(
            WorkerCapability(
                id=EntityId.new(),
                worker_id=worker.id,
                operation_kind="transcription",
                operation_schema_version="v1",
                execution_profile_id="test-profile",
                execution_profile_version=profile,
                locality=locality,
                accepted_asset_formats=("wav",),
                supports_word_timing=True,
                supports_speaker_labels=False,
                provider_id=None,
                provider_version=None,
                model_id=None,
                model_version=None,
                runtime_id="deterministic-test-runtime",
                runtime_version="v1",
                configured_eligible=True,
                effective_from=observed_at,
            )
        )
    repository.record_presence(
        worker.id,
        ttl=timedelta(minutes=5),
        maximum_concurrency=2,
        health=WorkerHealth.AVAILABLE,
        pressure=WorkerPressure.NORMAL,
    )
    return worker


def _enqueue(
    repository: PostgresWorkExecutionRepository,
    *,
    event_id: EntityId,
    asset_id: EntityId,
    manifest_id: EntityId,
    profile_version: str,
    requested_at: datetime,
    requires_cloud: bool = False,
) -> EnqueueTranscriptionOperation:
    request = EnqueueTranscriptionOperation(
        operation_id=EntityId.new(),
        idempotency_key=f"transcription:{asset_id.value}:{profile_version}",
        deployment_id="test-deployment",
        event_id=event_id,
        input=TranscriptionOperationInput(
            asset_id=asset_id,
            manifest_id=manifest_id,
            manifest_version="manifest-v1",
            asset_format="wav",
            execution_profile_id="test-profile",
            execution_profile_version=profile_version,
            request_word_timing=True,
            requires_cloud=requires_cloud,
        ),
        priority=10,
        eligible_at=requested_at,
        max_attempts=3,
        retry_delay=timedelta(seconds=1),
        required_for_event=True,
        requested_at=requested_at,
    )
    TranscriptionOperationApplication(repository).enqueue(request)
    return request


def _result(produced_at: datetime, *, text: str) -> NormalizedTranscriptResult:
    return NormalizedTranscriptResult(
        status=TranscriptEvidenceStatus.COMPLETE,
        provenance=TranscriptExecutionProvenance(
            provider_id="deterministic-fake",
            provider_version="v1",
            model_id="fake-model",
            model_version="v1",
            execution_tool_id="test-adapter",
            execution_tool_version="v1",
            execution_revision=f"fixture-{text.replace(' ', '-')}",
            produced_at=produced_at,
        ),
        language="en",
        segments=(
            TranscriptSegment(
                id=EntityId.new(),
                ordinal=0,
                text=text,
                asset_start_microseconds=0,
                asset_end_microseconds=1_000_000,
            ),
        ),
        limitations=("synthetic_test_evidence",),
    )


@pytest.mark.skipif(
    not _POSTGRES_DSN,
    reason=(
        "STAGEFLOW_TEST_POSTGRES_DSN is required for real PostgreSQL "
        "worker durability checks."
    ),
)
def test_real_postgres_worker_concurrency_fencing_lineage_and_reversal() -> None:
    assert _POSTGRES_DSN is not None
    dsn = _POSTGRES_DSN
    runner = PostgresMigrationRunner(dsn)
    runner.apply_event_mode_kernel_v1()
    with psycopg.connect(dsn) as connection:
        existing_rows = connection.execute(
            """
            SELECT
                (SELECT count(*) FROM stageflow.work_worker)
                + (SELECT count(*) FROM stageflow.work_operation)
                + (SELECT count(*)
                   FROM stageflow.transcript_evidence_revision)
            """
        ).fetchone()
    assert existing_rows is not None
    if int(existing_rows[0]) != 0:
        pytest.skip("requires an isolated database without existing worker data")
    repository = PostgresWorkExecutionRepository(dsn)
    observed_at = datetime.now(UTC) - timedelta(seconds=2)
    event_id, asset_id, manifest_id = _seed_asset(
        dsn,
        observed_at=observed_at,
    )
    first_worker = _register_worker(
        repository,
        event_id=event_id,
        observed_at=observed_at,
        profiles=(
            ("v1", ExecutionLocality.LOCAL),
            ("v2", ExecutionLocality.LOCAL),
            ("v3", ExecutionLocality.LOCAL),
            ("cloud-v1", ExecutionLocality.CLOUD),
        ),
    )
    second_worker = _register_worker(
        repository,
        event_id=event_id,
        observed_at=observed_at,
        profiles=(
            ("v2", ExecutionLocality.LOCAL),
            ("v3", ExecutionLocality.LOCAL),
        ),
    )

    first_request = _enqueue(
        repository,
        event_id=event_id,
        asset_id=asset_id,
        manifest_id=manifest_id,
        profile_version="v1",
        requested_at=observed_at,
    )
    replay = TranscriptionOperationApplication(repository).enqueue(first_request)
    assert replay.id == first_request.operation_id

    with pytest.raises(
        WorkExecutionConflictError,
        match="transcription_enqueue_identity_conflict",
    ):
        TranscriptionOperationApplication(repository).enqueue(
            replace(first_request, priority=first_request.priority + 1)
        )
    first_claim = repository.claim_next(
        ClaimRequest(
            worker_id=first_worker.id,
            network_policy=EventNetworkPolicy.LOCAL_ONLY,
            lease_duration=timedelta(seconds=30),
        )
    )
    assert first_claim is not None
    first_claim = repository.mark_running(first_claim)
    first_claim = repository.renew(
        first_claim,
        lease_duration=timedelta(seconds=30),
    )
    first_evidence = repository.apply_transcript_result(
        first_claim,
        prepare_transcript_evidence(
            first_claim,
            _result(observed_at, text="first revision"),
        ),
    )
    assert first_evidence.revision == 1
    assert first_evidence.predecessor_evidence_id is None
    assert repository.get_operation(first_request.operation_id).status is (
        OperationStatus.SUCCEEDED
    )

    second_request = _enqueue(
        repository,
        event_id=event_id,
        asset_id=asset_id,
        manifest_id=manifest_id,
        profile_version="v2",
        requested_at=observed_at,
    )
    claim_request_one = ClaimRequest(
        worker_id=first_worker.id,
        network_policy=EventNetworkPolicy.LOCAL_ONLY,
        lease_duration=timedelta(seconds=30),
    )
    claim_request_two = ClaimRequest(
        worker_id=second_worker.id,
        network_policy=EventNetworkPolicy.LOCAL_ONLY,
        lease_duration=timedelta(seconds=30),
    )
    def claim_from_fresh_repository(
        request: ClaimRequest,
    ) -> OperationClaim | None:
        return PostgresWorkExecutionRepository(dsn).claim_next(request)

    with ThreadPoolExecutor(max_workers=2) as executor:
        claims = tuple(
            executor.map(
                claim_from_fresh_repository,
                (claim_request_one, claim_request_two),
            )
        )
    winners = tuple(item for item in claims if item is not None)
    assert len(winners) == 1
    second_claim = repository.mark_running(winners[0])
    second_evidence = repository.apply_transcript_result(
        second_claim,
        prepare_transcript_evidence(
            second_claim,
            _result(observed_at, text="second revision"),
        ),
    )
    assert second_evidence.revision == 2
    assert second_evidence.predecessor_evidence_id == first_evidence.id
    assert repository.get_operation(second_request.operation_id).status is (
        OperationStatus.SUCCEEDED
    )

    third_request = _enqueue(
        repository,
        event_id=event_id,
        asset_id=asset_id,
        manifest_id=manifest_id,
        profile_version="v3",
        requested_at=observed_at,
    )
    stale_claim = repository.claim_next(claim_request_one)
    assert stale_claim is not None
    with psycopg.connect(dsn) as connection:
        connection.execute(
            """
            UPDATE stageflow.work_operation
            SET lease_expires_at = statement_timestamp() - interval '1 second'
            WHERE operation_id = %s
            """,
            (third_request.operation_id.value,),
        )
        connection.execute(
            """
            UPDATE stageflow.work_operation_attempt
            SET lease_started_at = statement_timestamp() - interval '2 seconds',
                lease_expires_at = statement_timestamp() - interval '1 second'
            WHERE attempt_id = %s
            """,
            (stale_claim.attempt.id.value,),
        )
    restarted = PostgresWorkExecutionRepository(dsn)
    reconciled = restarted.reconcile_expired()
    assert any(item.id == third_request.operation_id for item in reconciled)
    with psycopg.connect(dsn) as connection:
        connection.execute(
            """
            UPDATE stageflow.work_operation
            SET eligible_at = statement_timestamp() - interval '1 second'
            WHERE operation_id = %s
            """,
            (third_request.operation_id.value,),
        )
    current_claim = restarted.claim_next(claim_request_two)
    assert current_claim is not None
    assert current_claim.attempt.fence_generation == 2
    with pytest.raises(WorkExecutionLeaseLostError, match="operation_lease_lost"):
        restarted.apply_transcript_result(
            stale_claim,
            prepare_transcript_evidence(
                stale_claim,
                _result(observed_at, text="stale result"),
            ),
        )
    current_claim = restarted.mark_running(current_claim)
    third_evidence = restarted.apply_transcript_result(
        current_claim,
        prepare_transcript_evidence(
            current_claim,
            _result(observed_at, text="third revision"),
        ),
    )
    assert third_evidence.revision == 3

    cloud_request = _enqueue(
        repository,
        event_id=event_id,
        asset_id=asset_id,
        manifest_id=manifest_id,
        profile_version="cloud-v1",
        requested_at=observed_at,
        requires_cloud=True,
    )
    assert repository.claim_next(claim_request_one) is None
    assert repository.get_operation(cloud_request.operation_id).status is (
        OperationStatus.DEFERRED
    )
    cloud_claim = repository.claim_next(
        ClaimRequest(
            worker_id=first_worker.id,
            network_policy=EventNetworkPolicy.NETWORK_PERMITTED,
            lease_duration=timedelta(seconds=30),
        )
    )
    assert cloud_claim is not None
    assert cloud_claim.operation.id == cloud_request.operation_id

    runner.reverse_transcription_worker_v1()
    with psycopg.connect(dsn) as connection:
        asset = connection.execute(
            """
            SELECT count(*)
            FROM stageflow.completed_media_asset_registry
            WHERE asset_id = %s
            """,
            (asset_id.value,),
        ).fetchone()
        marker = connection.execute(
            """
            SELECT count(*) FROM stageflow.schema_migration
            WHERE version = '0007_transcription_worker'
            """
        ).fetchone()
    assert asset == (1,)
    assert marker == (0,)
    runner.apply_transcription_worker_v1()
