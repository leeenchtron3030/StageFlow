"""Synthetic registration-to-transcript tests; PostgreSQL fixture rolls everything back."""
from dataclasses import replace
from datetime import timedelta
from typing import Any, cast
from unittest.mock import Mock
from uuid import NAMESPACE_URL, uuid5

import psycopg
import pytest
from psycopg.rows import dict_row

from app.bootstrap.event_mode_kernel import KernelComponents
from app.bootstrap.media_cycle import MediaCycleResult
from app.contexts.production.event_mode_kernel import (
    DurableEventModeKernel,
    InMemoryEventModeKernelRepository,
    StartSessionRequest,
)
from app.contexts.production.event_mode_kernel.contracts import (
    MediaCandidate,
    MediaRegistrationState,
    RegisteredMediaAsset,
)
from app.contexts.production.event_mode_kernel.repository import EventModeKernelRepository
from app.contexts.production.session_suggestions.contracts import Reference
from app.contexts.production.session_suggestions.service import SessionSuggestionService
from app.contexts.transcription_evidence import prepare_transcript_evidence
from app.contexts.work_execution import (
    ClaimRequest,
    DurableOperation,
    EventNetworkPolicy,
    ExecutionLocality,
    OperationFailure,
    OperationStatus,
    PendingOperation,
    TranscriptionOperationApplication,
    TranscriptionOperationInput,
    Worker,
    WorkerCapability,
    WorkerHealth,
    WorkerPressure,
)
from app.contexts.work_execution.memory import InMemoryWorkExecutionRepository
from app.core.config.deployment import EffectiveKernelConfiguration, KernelDeploymentConfiguration
from app.demo.autonomous import AutonomousEventNodeCoordinator
from app.demo.service import DemoApplication, ProcessTranscriptionRequest, ReconcileMediaRequest
from app.infrastructure.postgres import (
    PostgresEventModeKernelRepository,
    PostgresWorkExecutionRepository,
)
from app.infrastructure.postgres.session_suggestion_repository import PostgresSuggestionRepository
from app.shared.ids import EntityId
from tests.test_demo_autonomous_event_node import MutableClock, memory_transcription_targets
from tests.test_durable_event_mode_kernel import ACTOR_ID, NOW, bootstrap_request
from tests.test_render_work_execution import render_postgres_dsn as render_postgres_dsn
from tests.test_transcription_worker_substrate import enqueue_request, transcript_result


class MemoryTargets(InMemoryWorkExecutionRepository):
    def __init__(self, kernel: InMemoryEventModeKernelRepository, clock: MutableClock) -> None:
        super().__init__(clock, input_types=(TranscriptionOperationInput,))
        self.kernel_repository = kernel

    def list_transcription_targets(
        self, *, deployment_id: str, event_id: EntityId,
        execution_profile_id: str, execution_profile_version: str,
        session_id: EntityId | None = None, after: EntityId | None = None, limit: int = 500,
    ) -> tuple[tuple[EntityId, DurableOperation | None], ...]:
        return memory_transcription_targets(
            self.kernel_repository, cast(tuple[DurableOperation, ...],
                                         tuple(self.operations.values())),
            deployment_id=deployment_id, event_id=event_id,
            execution_profile_id=execution_profile_id,
            execution_profile_version=execution_profile_version,
            session_id=session_id, after=after, limit=limit,
        )


class Harness:
    def __init__(self, monkeypatch: pytest.MonkeyPatch, dsn: str | None = None) -> None:
        self.dsn = dsn
        self.clock = MutableClock(NOW + timedelta(days=1))
        self.kernel_repository: EventModeKernelRepository = (
            InMemoryEventModeKernelRepository() if dsn is None
            else PostgresEventModeKernelRepository(dsn)
        )
        self.kernel = DurableEventModeKernel(repository=self.kernel_repository, clock=self.clock)
        boot = self.kernel.bootstrap(bootstrap_request())
        assert boot.event is not None
        self.event, self.stage = boot.event.id, boot.stages[0].id
        deployment = KernelDeploymentConfiguration.model_validate({
            "schema_version": "1.0", "deployment_id": "test-deployment", "node_id": "test-node",
            "node_role": "node", "postgres_dsn_secret_ref": "TEST_DSN",
            "event": {"key": boot.event.key, "name": "Synthetic Event", "stages": [{
                "key": "main", "name": "Main", "sources": [{
                    "key": "main-recorder", "path": "C:/synthetic"}]}]},
            "local_transcription": {"model_version": "synthetic", "model_path": "C:/synthetic",
                                    "ffmpeg_path": "C:/synthetic/ffmpeg.exe",
                                    "execution_profile_id": "test-profile",
                                    "execution_profile_version": "v1"},
        })
        config = EffectiveKernelConfiguration(
            deployment=deployment, postgres_dsn=dsn or "postgresql://synthetic-unused",
            sources={}, field_sources={},
        )
        self.components = KernelComponents(config, self.kernel_repository, self.kernel)
        # Discovery is already separately covered; these tests begin at registration.
        def cycle(components: KernelComponents, **kwargs: object) -> MediaCycleResult:
            return MediaCycleResult("synthetic", 0, 0, (), ())

        monkeypatch.setattr(KernelComponents, "run_media_cycle", cycle)
        self.memory = (MemoryTargets(
            cast(InMemoryEventModeKernelRepository, self.kernel_repository), self.clock,
        ) if dsn is None else None)
        self.restart()

    def restart(self) -> None:
        self.components = KernelComponents(
            self.components.configuration, self.kernel_repository, self.kernel)
        self.repository = (PostgresWorkExecutionRepository(self.dsn) if self.dsn is not None
                           else cast(PostgresWorkExecutionRepository, self.memory))
        self.application = DemoApplication(self.components,
            TranscriptionOperationApplication(self.repository), self.repository)

    def asset(self, ordinal: int) -> RegisteredMediaAsset:
        at = NOW + timedelta(seconds=ordinal)
        candidate = MediaCandidate(EntityId.new(), EntityId.new(), self.stage, "main-recorder",
                                   f"C:/synthetic/{ordinal}.wav", at, at,
                                   MediaRegistrationState.READY, 1)
        self.kernel_repository.register_candidate(candidate)
        asset = RegisteredMediaAsset(candidate.proposed_asset_id, candidate.id, EntityId.new(),
                                     self.stage, "main-recorder", at)
        return self.kernel_repository.register_asset(asset)

    def reconcile(self):
        return self.application.reconcile_media(
            ReconcileMediaRequest("synthetic", self.clock.now()))

    def session(self) -> EntityId:
        return self.kernel.start_session(StartSessionRequest(
            EntityId.new(), self.event, self.stage, ACTOR_ID, NOW, self.clock.now(),
        )).id

    def assign(self, asset: RegisteredMediaAsset, session: EntityId) -> None:
        self.kernel.assign_asset(operation_id=EntityId.new(), asset_id=asset.id, session_id=session,
                                 actor_id=ACTOR_ID, reason="Synthetic assignment")

    def manual(self, session: EntityId):
        return self.application.process_transcription(ProcessTranscriptionRequest(
            EntityId.new(), session, self.clock.now()))

    def claim(self):
        worker = Worker(EntityId.new(), "synthetic-worker", "test-deployment", self.event,
                        True, False, "v1", 1, NOW, NOW)
        self.repository.register_worker(worker)
        self.repository.register_capability(WorkerCapability(
            id=EntityId.new(), worker_id=worker.id, operation_kind="transcription",
            operation_schema_version="v1", execution_profile_id="test-profile",
            execution_profile_version="v1", locality=ExecutionLocality.LOCAL,
            accepted_asset_formats=("wav",), supports_word_timing=True,
            supports_speaker_labels=False, provider_id=None, provider_version=None,
            model_id=None, model_version=None, runtime_id="synthetic", runtime_version="v1",
            configured_eligible=True, effective_from=NOW,
        ))
        self.repository.record_presence(worker.id, ttl=timedelta(minutes=5), maximum_concurrency=1,
            health=WorkerHealth.AVAILABLE, pressure=WorkerPressure.NORMAL)
        claim = self.repository.claim_next(ClaimRequest(
            worker.id, EventNetworkPolicy.LOCAL_ONLY, timedelta(minutes=1)))
        assert claim is not None
        return self.repository.mark_running(claim)


@pytest.fixture(params=("memory", "postgres"))
def h(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Harness:
    dsn = request.getfixturevalue("render_postgres_dsn") if request.param == "postgres" else None
    return Harness(monkeypatch, dsn)


def test_all_unassociated_assets_arrival_order_bounded_backlog_and_restart(h: Harness) -> None:
    # Insert out of timestamp order, with more assets than the old recent-media limit.
    assets = [h.asset(i) for i in reversed(range(503))]
    expected = list(reversed(assets))
    first = h.reconcile()
    assert first.operations_enqueued == 500
    assert [o.input.asset_id for o in first.operations] == [a.id for a in expected[:500]]
    assert not first.enqueue_failures
    h.restart()
    second = h.reconcile()
    assert second.operations_enqueued == 3
    assert [o.input.asset_id for o in second.operations] == [a.id for a in expected[500:]]
    assert h.reconcile().operations_enqueued == 0
    assert all(h.kernel_repository.get_association(a.id) is None for a in assets)
    assert not h.kernel_repository.list_sessions_for_stage(h.stage)
    # Reporting a prior operation must not depend on the newest 500 operations.
    session = h.session()
    h.assign(expected[0], session)
    assert h.manual(session).operations == (first.operations[0],)
    assert h.manual(session).operations_enqueued == 0


def test_persistent_enqueue_failures_do_not_starve_later_registrations(
    h: Harness, monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocked = {h.asset(i).id for i in range(500)}
    later = h.asset(500)
    enqueue = h.repository.enqueue

    def fail_early(pending: PendingOperation) -> DurableOperation:
        if pending.request.input.asset_id in blocked:
            raise RuntimeError("synthetic_enqueue_failure")
        return enqueue(pending)

    monkeypatch.setattr(h.repository, "enqueue", fail_early)
    first = h.reconcile()
    assert first.operations_enqueued == 0 and len(first.enqueue_failures) == 100
    second = h.reconcile()
    assert second.operations_enqueued == 1
    assert second.operations[0].input.asset_id == later.id
    assert h.reconcile().operations_enqueued == 0  # wraps and revisits failed registrations
    monkeypatch.setattr(h.repository, "enqueue", enqueue)
    h.restart()
    assert h.reconcile().operations_enqueued == 500
    assert h.reconcile().operations_enqueued == 0


def test_mixed_assets_session_trigger_reuses_before_and_after_reassociation(h: Harness) -> None:
    first, second = h.asset(0), h.asset(1)
    session = h.session()
    h.assign(first, session)
    result = h.reconcile()
    assert result.operations_enqueued == 2
    assert [o.input.asset_id for o in result.operations] == [first.id, second.id]
    assert h.manual(session).operations == (result.operations[0],)
    h.assign(second, session)
    assert h.manual(session).operations == result.operations
    assert h.manual(session).operations_enqueued == 0
    h.kernel.correct_session_boundary(operation_id=EntityId.new(), session_id=session,
        boundary_kind="end", boundary_at=NOW + timedelta(minutes=1), actor_id=ACTOR_ID,
        reason="Synthetic end")
    later = h.kernel.start_session(StartSessionRequest(
        EntityId.new(), h.event, h.stage, ACTOR_ID, NOW + timedelta(minutes=1), h.clock.now(),
    )).id
    h.assign(second, later)
    assert h.manual(later).operations == (result.operations[1],)
    assert h.reconcile().operations_enqueued == 0


def test_legacy_session_key_operation_is_reused_by_input(h: Harness) -> None:
    asset, session = h.asset(0), h.session()
    value = TranscriptionOperationInput(asset.id, asset.manifest_id, "1.0", "wav",
                                        "test-profile", "v1", request_word_timing=True)
    old = replace(enqueue_request(value),
        operation_id=EntityId(str(uuid5(NAMESPACE_URL,
            f"stageflow:demo-transcription:test-deployment:{h.event.value}:{session.value}:"
            f"{asset.id.value}:{asset.manifest_id.value}:test-profile:v1"))),
        idempotency_key=f"demo-process:{session.value}:{asset.id.value}", event_id=h.event)
    operation = h.application.work.enqueue(old)
    h.restart()
    assert h.reconcile().operations_enqueued == 0
    h.assign(asset, session)
    assert h.manual(session).operations == (operation,)
    assert h.manual(session).operations_enqueued == 0


def test_session_trigger_first_uses_the_same_asset_identity(h: Harness) -> None:
    asset, session = h.asset(0), h.session()
    h.assign(asset, session)
    manual = h.manual(session)
    assert manual.operations_enqueued == 1
    assert h.reconcile().operations_enqueued == 0
    h.restart()
    assert h.manual(session).operations == manual.operations
    assert h.manual(session).operations_enqueued == 0


def test_execution_profile_revision_is_a_distinct_operation(h: Harness) -> None:
    h.asset(0)
    first = h.reconcile().operations[0]
    config = h.components.configuration
    profile = config.deployment.local_transcription
    assert profile is not None
    h.components.configuration = config.model_copy(update={"deployment":
        config.deployment.model_copy(update={"local_transcription":
            profile.model_copy(update={"execution_profile_version": "v2"})})})
    second = h.reconcile().operations[0]
    assert second.id != first.id and second.idempotency_key != first.idempotency_key
    assert h.reconcile().operations_enqueued == 0


def test_not_configured_enqueues_nothing(h: Harness) -> None:
    h.asset(0)
    config = h.components.configuration
    h.components.configuration = config.model_copy(update={"deployment":
        config.deployment.model_copy(update={"local_transcription": None})})
    with pytest.raises(RuntimeError, match="local_transcription_not_configured"):
        h.reconcile()
    assert h.repository.list_operations(deployment_id="test-deployment", event_id=h.event) == ()


@pytest.mark.parametrize("retryable", (True, False))
def test_failed_work_stays_on_original_operation(h: Harness, retryable: bool) -> None:
    asset = h.asset(0)
    operation = h.reconcile().operations[0]
    failed = h.repository.record_failure(h.claim(), OperationFailure(
        "synthetic_failure", retryable, "Synthetic provider failure"))
    assert failed.status is (
        OperationStatus.RETRY_WAIT if retryable else OperationStatus.TERMINAL_FAILED)
    assert failed.max_attempts == 3 and failed.retry_delay == timedelta(seconds=30)
    h.restart()
    assert h.reconcile().operations_enqueued == 0
    session = h.session()
    h.assign(asset, session)
    assert h.manual(session).operations == (failed,)
    assert failed.id == operation.id


def test_completed_unassociated_transcript_is_reused_after_restart(h: Harness) -> None:
    asset = h.asset(0)
    operation = h.reconcile().operations[0]
    claim = h.claim()
    evidence = h.repository.apply_transcript_result(
        claim, prepare_transcript_evidence(claim, transcript_result()))
    assert evidence.asset_id == asset.id
    assert h.kernel_repository.get_association(asset.id) is None
    h.restart()
    assert h.reconcile().operations_enqueued == 0
    session = h.session()
    h.assign(asset, session)
    manual = h.manual(session)
    assert manual.operations_enqueued == 0
    assert manual.operations[0].id == operation.id
    assert manual.operations[0].status is OperationStatus.SUCCEEDED


def test_autonomous_counters_count_unassociated_assets_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    h = Harness(monkeypatch)
    h.asset(0)
    h.asset(1)
    def application(cls: type[DemoApplication], components: KernelComponents) -> DemoApplication:
        return h.application

    monkeypatch.setattr(DemoApplication, "from_components", classmethod(application))
    coordinator = AutonomousEventNodeCoordinator(h.components)
    coordinator.run_media_cycle()
    coordinator.run_media_cycle()
    assert coordinator.status().media_cycle_count == 2
    assert coordinator.status().transcription_operations_enqueued == 2
    assert coordinator.status().transcription_enqueue_failures == 0


def test_suggestion_run_reads_transcript_produced_for_unassociated_asset(
    render_postgres_dsn: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    h = Harness(monkeypatch, render_postgres_dsn)
    asset = h.asset(0)
    service = SessionSuggestionService(PostgresSuggestionRepository(render_postgres_dsn), h.clock)
    before = service.run(event_id=h.event, stage_id=h.stage, actor_id=ACTOR_ID)
    assert before.assets[0].transcript is None
    h.reconcile()
    claim = h.claim()
    evidence = h.repository.apply_transcript_result(
        claim, prepare_transcript_evidence(claim, transcript_result()))
    after = service.run(event_id=h.event, stage_id=h.stage, actor_id=ACTOR_ID)
    assert after.assets[0].asset_id == asset.id
    assert after.assets[0].transcript == Reference(evidence.id, evidence.revision)
    assert after.id != before.id
    assert h.kernel_repository.get_association(asset.id) is None
    assert not h.kernel_repository.list_sessions_for_stage(h.stage)
    assert service.run(event_id=h.event, stage_id=h.stage, actor_id=ACTOR_ID) == after


def test_postgres_event_targets_match_prior_query_with_large_operation_journal(
    render_postgres_dsn: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    h = Harness(monkeypatch, render_postgres_dsn)
    assets = [h.asset(i) for i in range(120)]

    def enqueue(asset: RegisteredMediaAsset, version: str = "v1") -> None:
        value = TranscriptionOperationInput(
            asset.id, asset.manifest_id, "1.0", "wav", "test-profile", version,
            request_word_timing=True,
        )
        request = enqueue_request(value)
        h.application.work.enqueue(replace(
            request, event_id=h.event,
            idempotency_key=f"legacy-session:{request.operation_id.value}",
        ))

    # Failed and retrying legacy work must exclude its asset just like queued work.
    for asset, retryable in zip(assets[:2], (False, True), strict=True):
        enqueue(asset)
        h.repository.record_failure(h.claim(), OperationFailure(
            "synthetic_failure", retryable, "Synthetic provider failure"))
    for asset in assets[2:60]:
        enqueue(asset)
    # 960 unrelated operations share asset/manifest identity, but not the profile
    # revision. They must neither hide targets nor change arrival-order pagination.
    for asset in assets:
        for version in range(2, 10):
            enqueue(asset, f"v{version}")

    for after, limit in ((None, 500), (None, 17), (assets[76].id, 17)):
        cursor = None if after is None else after.value
        with psycopg.Connection[dict[str, Any]].connect(
            render_postgres_dsn, row_factory=dict_row,
        ) as connection:
            # Frozen pre-fix event-wide selection is the equivalence oracle.
            previous = connection.execute(
                """
                SELECT a.asset_id
                FROM stageflow.completed_media_asset_registry a
                JOIN stageflow.stage s USING (stage_id)
                LEFT JOIN stageflow.media_association x USING (asset_id)
                LEFT JOIN LATERAL (
                    SELECT o.operation_id FROM stageflow.work_operation o
                    WHERE o.operation_kind = 'transcription'
                      AND o.deployment_id = %s AND o.event_id = s.event_id
                      AND o.asset_id = a.asset_id AND o.manifest_id = a.manifest_id
                      AND o.manifest_version = '1.0'
                      AND o.execution_profile_id = %s
                      AND o.execution_profile_version = %s
                    ORDER BY (o.operation_status = 'terminal_failed'),
                             o.created_at, o.operation_id
                    LIMIT 1
                ) prior ON true
                WHERE s.event_id = %s
                  AND (%s::uuid IS NULL OR (a.registered_at, a.asset_id) > (
                      SELECT registered_at, asset_id
                      FROM stageflow.completed_media_asset_registry WHERE asset_id = %s
                  )) AND prior.operation_id IS NULL
                ORDER BY a.registered_at, a.asset_id
                LIMIT %s
                """,
                ("test-deployment", "test-profile", "v1", h.event.value,
                 cursor, cursor, limit),
            ).fetchall()
            # Capture and explain the actual repository query, not a test copy.
            execute = Mock(wraps=connection.execute)
            with monkeypatch.context() as patch:
                patch.setattr(connection, "execute", execute)
                targets = h.repository.list_transcription_targets(
                    deployment_id="test-deployment", event_id=h.event,
                    execution_profile_id="test-profile", execution_profile_version="v1",
                    after=after, limit=limit,
                )
            query, parameters = execute.call_args_list[0].args
            explained = connection.execute("EXPLAIN (FORMAT JSON) " + query, parameters).fetchone()
            assert explained is not None

            def nodes(plan: dict[str, Any]) -> list[dict[str, Any]]:
                return [plan, *(node for child in plan.get("Plans", []) for node in nodes(child))]

            plan_nodes = nodes(explained["QUERY PLAN"][0]["Plan"])
            # Assert structure, not costs, timings, join algorithm or formatted text.
            assert any(node.get("Join Type") == "Anti" and any(
                child.get("Relation Name") == "work_operation" for child in nodes(node)
            ) for node in plan_nodes)
            assert not any(node.get("Parent Relationship") == "SubPlan" and any(
                child.get("Relation Name") == "work_operation" for child in nodes(node)
            ) for node in plan_nodes)
        expected = assets[60 if after is None else 77:][:limit]
        assert targets == tuple((a.id, None) for a in expected)
        assert [asset_id.value for asset_id, _ in targets] == [
            str(row["asset_id"]) for row in previous]
