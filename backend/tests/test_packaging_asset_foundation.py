from __future__ import annotations

import os
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from typing import Protocol, cast
from uuid import uuid4

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from app.api.authentication import API_SECRET_HEADER
from app.api.v1.router import router
from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.assembly.contracts import (
    ApprovalAction,
    ApprovalState,
    CompletedMediaAssetContent,
    ExternalContent,
    PackagingAsset,
    PackagingAssetApprovalDecision,
    PackagingAssetRevision,
    PackagingAssetRole,
    RevisionContent,
)
from app.contexts.assembly.memory import InMemoryPackagingAssetRepository
from app.contexts.assembly.repository import (
    PackagingAssetConflictError,
    PackagingAssetNotFoundError,
    PackagingAssetRepository,
    PackagingAssetStorageUnavailableError,
)
from app.contexts.assembly.service import PackagingAssetService
from app.contexts.events import EventStageBootstrapRequest, StageBootstrapDefinition
from app.contexts.production.event_mode_kernel import (
    DurableEventModeKernel,
    InMemoryEventModeKernelRepository,
)
from app.contexts.production.event_mode_kernel.contracts import (
    MediaCandidate,
    MediaRegistrationState,
    RegisteredMediaAsset,
)
from app.core.config.deployment import EffectiveKernelConfiguration
from app.infrastructure.postgres import PostgresEventModeKernelRepository, PostgresMigrationRunner
from app.infrastructure.postgres.packaging_asset_repository import PostgresPackagingAssetRepository
from app.shared.ids import EntityId
from app.shared.time import FixedClock

NOW = datetime(2026, 9, 24, 12, tzinfo=UTC)
EVENT = EntityId.new()
OTHER_EVENT = EntityId.new()
STAGE = EntityId.new()
MEDIA = EntityId.new()
ACTOR = EntityId.new()
CONTENT = RevisionContent(ExternalContent("branding-01", "a" * 64, 500, "video/mp4"))
HEADERS = {API_SECRET_HEADER: "stageflow-test-only-shared-secret-0123456789"}


class SyncHttpClient(Protocol):
    def get(self, url: str, *, headers: Mapping[str, str] | None = None) -> Response: ...

    def post(
        self, url: str, *, headers: Mapping[str, str] | None = None, json: object | None = None,
    ) -> Response: ...


def assert_frozen(value: object, attribute: str, replacement: object) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(value, attribute, replacement)


@pytest.fixture
def service() -> PackagingAssetService:
    return PackagingAssetService(InMemoryPackagingAssetRepository(
        event_ids=frozenset((EVENT, OTHER_EVENT)), stages={STAGE: EVENT},
        completed_asset_ids=frozenset((MEDIA,)),
    ), FixedClock(NOW))


def register(service: PackagingAssetService, operation: EntityId | None = None) -> PackagingAsset:
    return service.register(
        operation_id=operation or EntityId.new(), actor_id=ACTOR,
        event_id=EVENT, stage_id=STAGE, name="Opening", role=PackagingAssetRole.OPENING_BUMPER,
    )


def revise(
    service: PackagingAssetService, asset: PackagingAsset, expected: int = 0,
    operation: EntityId | None = None, content: RevisionContent = CONTENT,
) -> PackagingAssetRevision:
    return service.revise(
        operation_id=operation or EntityId.new(), actor_id=ACTOR, packaging_asset_id=asset.id,
        expected_revision=expected, content=content,
    )


def test_registration_revisions_and_delayed_replay_return_original_results(
    service: PackagingAssetService,
) -> None:
    registration, revision_op = EntityId.new(), EntityId.new()
    asset = register(service, registration)
    assert service.repository.list_assets(EVENT).items[0].current_revision_number == 0
    first = revise(service, asset, operation=revision_op)
    second = revise(service, asset, 1)
    assert (first.revision_number, second.revision_number) == (1, 2)
    assert revise(service, asset, operation=revision_op) == first
    assert register(service, registration) == asset
    assert revise(service, register(service)).revision_number == 1
    with pytest.raises(PackagingAssetConflictError, match="operation_id_conflict"):
        service.register(operation_id=registration, actor_id=ACTOR, event_id=EVENT,
                         name="Changed", role=PackagingAssetRole.OUTRO)
    with pytest.raises(PackagingAssetConflictError, match="operation_id_conflict"):
        revise(service, asset, 2, revision_op)
    with pytest.raises(PackagingAssetConflictError, match="operation_id_conflict"):
        revise(service, asset, 2, registration)
    assert_frozen(first, "revision_number", 99)
    assert_frozen(first.content.reference, "content_key", "replacement")


def test_approval_is_revision_scoped_append_ordered_and_replay_safe(
    service: PackagingAssetService,
) -> None:
    asset = register(service)
    revise(service, asset)
    decisions: list[PackagingAssetApprovalDecision] = []
    for action, state in ((ApprovalAction.APPROVE, ApprovalState.APPROVED),
                          (ApprovalAction.REJECT, ApprovalState.REJECTED),
                          (ApprovalAction.REVOKE, ApprovalState.REVOKED)):
        # Append sequence, not wall-clock ordering, owns current approval state.
        service.clock = FixedClock(NOW - timedelta(seconds=len(decisions)))
        operation = EntityId.new()
        result = service.decide(
            operation_id=operation, actor_id=ACTOR, packaging_asset_id=asset.id,
            revision_number=1, expected_revision=1, action=action, reason="Human review",
        )
        decisions.append(result)
        assert service.decide(
            operation_id=operation, actor_id=ACTOR, packaging_asset_id=asset.id,
            revision_number=1, expected_revision=1, action=action, reason="Human review",
        ) == result
        with pytest.raises(PackagingAssetConflictError, match="operation_id_conflict"):
            service.decide(
                operation_id=operation, actor_id=ACTOR, packaging_asset_id=asset.id,
                revision_number=1, expected_revision=1, action=action, reason="Changed",
            )
        item = service.repository.list_revisions(EVENT, asset.id).items[0]
        assert item.approval_state == state
        assert item.decision_count == len(decisions)
    assert [decision.sequence for decision in decisions] == [1, 2, 3]
    assert_frozen(decisions[0], "action", ApprovalAction.REJECT)
    revise(service, asset, 1)
    projection = service.repository.list_revisions(EVENT, asset.id)
    assert projection.items[1].approval_state == ApprovalState.UNREVIEWED
    assert projection.items[0].approval_state == ApprovalState.REVOKED
    # Old revisions remain deliberately addressable, with a fresh asset revision guard.
    service.decide(operation_id=EntityId.new(), actor_id=ACTOR, packaging_asset_id=asset.id,
                   revision_number=1, expected_revision=2, action=ApprovalAction.APPROVE,
                   reason="Reapproved old content")
    assert service.repository.list_revisions(EVENT, asset.id).items[1].decision_count == 0


def test_stale_missing_and_failed_commands_leave_no_partial_state(
    service: PackagingAssetService,
) -> None:
    asset = register(service)
    revise(service, asset)
    with pytest.raises(PackagingAssetConflictError, match="revision_conflict"):
        revise(service, asset)
    with pytest.raises(PackagingAssetConflictError, match="revision_conflict"):
        service.decide(operation_id=EntityId.new(), actor_id=ACTOR, packaging_asset_id=asset.id,
                       revision_number=1, expected_revision=2, action=ApprovalAction.APPROVE,
                       reason="Stale")
    with pytest.raises(PackagingAssetNotFoundError, match="revision_not_found"):
        service.decide(operation_id=EntityId.new(), actor_id=ACTOR, packaging_asset_id=asset.id,
                       revision_number=2, expected_revision=1, action=ApprovalAction.APPROVE,
                       reason="Unknown")
    failed_op = EntityId.new()
    with pytest.raises(PackagingAssetNotFoundError):
        revise(service, asset, 1, failed_op,
               RevisionContent(CompletedMediaAssetContent(EntityId.new())))
    recovered = revise(service, asset, 1, failed_op,
                       RevisionContent(CompletedMediaAssetContent(MEDIA)))
    assert recovered.content.reference == CompletedMediaAssetContent(MEDIA)
    assert service.repository.list_assets(EVENT).items[0].decision_count == 0
    with pytest.raises(PackagingAssetNotFoundError):
        service.register(operation_id=EntityId.new(), actor_id=ACTOR, event_id=OTHER_EVENT,
                         stage_id=STAGE, name="Wrong Stage", role=PackagingAssetRole.OUTRO)


@pytest.mark.parametrize("key", ["/tmp/a", "C:\\media\\a", "C:a", "../a", "a/b",
                                "a\\b", "\\\\host\\share", "file:///a", "a.mp4",
                                "%2Fa", "~", "", "a\n", "a" * 201])
def test_external_content_rejects_path_syntax(key: str) -> None:
    with pytest.raises(ValueError, match="opaque token"):
        ExternalContent(key, "a" * 64, 1, "video/mp4")


@pytest.mark.parametrize(
    "change", ["digest", "size", "media_type", "duration", "naive", "interval"],
)
def test_content_contract_validation(change: str) -> None:
    with pytest.raises(ValueError):
        if change == "digest":
            ExternalContent("key", "bad", 1, "video/mp4")
        elif change == "size":
            ExternalContent("key", "a" * 64, -1, "video/mp4")
        elif change == "media_type":
            ExternalContent("key", "a" * 64, 1, "unknown")
        elif change == "duration":
            replace(CONTENT, measured_duration_microseconds=-1)
        elif change == "naive":
            replace(CONTENT, effective_from=NOW.replace(tzinfo=None))
        else:
            replace(CONTENT, effective_from=NOW, effective_until=NOW)


def test_equivalent_aware_times_have_same_digest(service: PackagingAssetService) -> None:
    asset, operation = register(service), EntityId.new()
    content = replace(CONTENT, effective_from=NOW, effective_until=NOW + timedelta(days=1))
    revision = revise(service, asset, operation=operation, content=content)
    assert revise(service, asset, operation=operation, content=replace(
        content, effective_from=NOW.astimezone(timezone(timedelta(hours=3))),
    )) == revision


@pytest.mark.parametrize("field", ["byte_size", "measured_duration_microseconds"])
def test_integer_storage_bounds_rejected_before_write(
    service: PackagingAssetService, field: str,
) -> None:
    maximum = 2**63 - 1
    if field == "byte_size":
        assert ExternalContent("key", "a" * 64, maximum, "video/mp4").byte_size == maximum
        with pytest.raises(ValueError):
            ExternalContent("key", "a" * 64, maximum + 1, "video/mp4")
    else:
        assert replace(CONTENT, measured_duration_microseconds=maximum)
        with pytest.raises(ValueError):
            replace(CONTENT, measured_duration_microseconds=maximum + 1)
    asset = register(service)
    body: dict[str, object] = {
        "operation_id": EntityId.new().value, "actor_id": ACTOR.value,
        "confirmed": "confirmed", "expected_revision": 0,
    }
    ref: dict[str, object] = {"kind": "external_content", "content_key": "key",
                              "sha256": "a" * 64, "byte_size": 1, "media_type": "video/mp4"}
    if field == "byte_size":
        ref[field] = maximum + 1
    else:
        body[field] = maximum + 1
    body["content"] = ref
    assert client_for(service).post(
        f"/api/v1/assembly/packaging-assets/{asset.id.value}/revisions",
        headers=HEADERS, json=body,
    ).status_code == 422
    assert service.repository.list_revisions(EVENT, asset.id).total_count == 0


def test_event_pagination_counts_and_revision_state_beyond_page(
    service: PackagingAssetService,
) -> None:
    assets = [register(service) for _ in range(4)]
    service.register(operation_id=EntityId.new(), actor_id=ACTOR, event_id=OTHER_EVENT,
                     name="Other", role=PackagingAssetRole.SPONSOR_CARD)
    first = service.repository.list_assets(EVENT, limit=2)
    second = service.repository.list_assets(EVENT, limit=2, after=first.next_after)
    assert first.total_count == second.total_count == 4
    assert len(first.items) == len(second.items) == 2
    assert second.next_after is None
    assert {item.asset.id for item in first.items + second.items} == {asset.id for asset in assets}
    for number in range(3):
        revise(service, assets[0], number)
    revision_page = service.repository.list_revisions(EVENT, assets[0].id, limit=1)
    assert revision_page.total_count == 3 and revision_page.next_after == 1
    assert service.repository.list_revisions(EVENT, assets[0].id, after=1).items[0].revision == (
        service.repository.list_revisions(EVENT, assets[0].id).items[1].revision
    )
    with pytest.raises(PackagingAssetNotFoundError):
        service.repository.list_revisions(OTHER_EVENT, assets[0].id)
    for limit in (0, 101):
        with pytest.raises(ValueError):
            service.repository.list_assets(EVENT, limit=limit)
    assert service.repository.list_assets(
        EVENT, after=EntityId("ffffffff-ffff-ffff-ffff-ffffffffffff"),
    ) == replace(first, items=(), next_after=None)


def test_concurrent_revision_guard_and_exact_replay(service: PackagingAssetService) -> None:
    asset = register(service)
    def append(_: int) -> str:
        try:
            revise(service, asset)
            return "created"
        except PackagingAssetConflictError:
            return "stale"
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sorted(pool.map(append, range(4))) == ["created", "stale", "stale", "stale"]
    operation = EntityId.new()
    def replay(_: int) -> PackagingAssetRevision:
        return revise(service, asset, 1, operation)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(replay, range(4)))
    assert all(result == results[0] for result in results)


def client_for(service: PackagingAssetService) -> SyncHttpClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    kernel_repository = InMemoryEventModeKernelRepository()
    app.state.kernel = KernelComponents(
        configuration=cast(EffectiveKernelConfiguration, None), repository=kernel_repository,
        kernel=DurableEventModeKernel(repository=kernel_repository, clock=FixedClock(NOW)),
        packaging_assets=service,
    )
    return cast(SyncHttpClient, TestClient(app))


def test_api_authentication_commands_validation_and_event_reads(
    service: PackagingAssetService,
) -> None:
    client = client_for(service)
    base = "/api/v1/assembly"
    command = {"operation_id": EntityId.new().value, "actor_id": ACTOR.value,
               "confirmed": "confirmed", "event_id": EVENT.value,
               "role": "opening_bumper", "name": "Intro"}
    assert client.post(base + "/packaging-assets", json=command).status_code == 401
    response = client.post(base + "/packaging-assets", json=command, headers=HEADERS)
    assert response.status_code == 200
    asset_id = response.json()["packaging_asset_id"]
    assert client.post(base + "/packaging-assets", json=command, headers=HEADERS).json() == (
        response.json()
    )
    target = f"{base}/packaging-assets/{asset_id}"
    content_body = {"kind": "external_content", "content_key": "intro-1",
                    "sha256": "b" * 64, "byte_size": 20, "media_type": "video/mp4"}
    revision = {"operation_id": EntityId.new().value, "actor_id": ACTOR.value,
                "confirmed": "confirmed", "expected_revision": 0,
                "content": content_body}
    assert client.post(target + "/revisions", json=revision).status_code == 401
    assert client.post(target + "/revisions", json=revision, headers=HEADERS).status_code == 200
    assert client.post(
        target + "/revisions", json={**revision, "operation_id": EntityId.new().value},
        headers=HEADERS,
    ).status_code == 409
    assert client.post(target + "/revisions", json={**revision, "path": "C:/a"},
                       headers=HEADERS).status_code == 422
    assert client.post(target + "/revisions", json={**revision, "content": {
        **content_body, "content_key": "../a",
    }}, headers=HEADERS).status_code == 422
    approval = {"operation_id": EntityId.new().value, "actor_id": ACTOR.value,
                "confirmed": "confirmed", "expected_revision": 1, "revision_number": 1,
                "action": "approve", "reason": "Reviewed"}
    assert client.post(target + "/approvals", json=approval).status_code == 401
    assert client.post(target + "/approvals", json=approval, headers=HEADERS).status_code == 200
    event_target = f"{base}/events/{EVENT.value}/packaging-assets"
    assert client.get(event_target).status_code == 401
    register(service)
    page = client.get(event_target + "?limit=1", headers=HEADERS).json()
    assert page["items_truncated"] and page["next_after"] and page["total_count"] == 2
    assert client.get(event_target + "?limit=101", headers=HEADERS).status_code == 422
    assert client.get(event_target + "?after=bad", headers=HEADERS).status_code == 422
    history_target = event_target + f"/{asset_id}/revisions"
    assert client.get(history_target).status_code == 401
    history = client.get(history_target, headers=HEADERS).json()
    assert history["items"][0]["approval_state"] == "approved"
    assert client.get(history_target.replace(EVENT.value, OTHER_EVENT.value),
                      headers=HEADERS).status_code == 404


def test_storage_failure_is_503_without_fallback(service: PackagingAssetService) -> None:
    class Unavailable(InMemoryPackagingAssetRepository):
        def register(self, *args: object, **kwargs: object) -> PackagingAsset:
            raise PackagingAssetStorageUnavailableError("private connection diagnostics")
    service.repository = Unavailable(event_ids=frozenset(), stages={})
    response = client_for(service).post("/api/v1/assembly/packaging-assets", headers=HEADERS, json={
        "operation_id": EntityId.new().value, "actor_id": ACTOR.value, "confirmed": "confirmed",
        "event_id": EVENT.value, "role": "outro", "name": "Outro",
    })
    assert response.status_code == 503
    assert response.json() == {"detail": "postgresql_unavailable"}


def test_text_storage_constraints_fail_before_committing(service: PackagingAssetService) -> None:
    client = client_for(service)
    base = "/api/v1/assembly/packaging-assets"
    human = {"operation_id": EntityId.new().value, "actor_id": ACTOR.value,
             "confirmed": "confirmed"}
    assert client.post(base, headers=HEADERS, json={
        **human, "event_id": EVENT.value, "role": "outro", "name": "bad\x00name",
    }).status_code == 422
    assert service.repository.list_assets(EVENT).total_count == 0
    asset = register(service)
    revise(service, asset)
    assert client.post(base + f"/{asset.id.value}/approvals", headers=HEADERS, json={
        **human, "revision_number": 1, "expected_revision": 1,
        "action": "approve", "reason": "bad\x00reason",
    }).status_code == 422
    assert service.repository.list_revisions(EVENT, asset.id).items[0].decision_count == 0


def test_migration_runner_orders_0012_before_0011(monkeypatch: pytest.MonkeyPatch) -> None:
    executed: list[str] = []
    def record(self: PostgresMigrationRunner, filename: str, *, version: str) -> None:
        executed.append(version)
    monkeypatch.setattr(PostgresMigrationRunner, "_execute_if_present", record)
    PostgresMigrationRunner("unused").reverse_editorial_review_foundation_v1()
    assert executed == ["0014_assembly_metadata_overrides",
                        "0013_session_assembly_foundation", "0012_packaging_asset_foundation",
                        "0011_editorial_review_foundation"]


@pytest.fixture
def postgres_dsn() -> str:
    dsn = os.getenv("STAGEFLOW_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("STAGEFLOW_TEST_POSTGRES_DSN is required for real PostgreSQL validation")
    try:
        with psycopg.connect(dsn, connect_timeout=3):
            pass
    except psycopg.OperationalError:
        pytest.skip("Real PostgreSQL is unreachable from this environment")
    return dsn


def test_postgres_persistence_restart_replay_concurrency_and_reversal(postgres_dsn: str) -> None:
    runner = PostgresMigrationRunner(postgres_dsn)
    runner.apply_event_mode_kernel_v1()
    kernel_repository = PostgresEventModeKernelRepository(postgres_dsn)
    kernel = DurableEventModeKernel(repository=kernel_repository, clock=FixedClock(NOW))
    source_key = f"synthetic-{uuid4().hex}"
    bootstrap_op = EntityId.new()
    bootstrap = kernel.bootstrap(EventStageBootstrapRequest(
        operation_id=bootstrap_op, actor_id=ACTOR, requested_at=NOW,
        event_key=f"packaging-test-{uuid4().hex}", event_name="Synthetic packaging test",
        stages=(StageBootstrapDefinition(key="main", name="Main",
                                         source_bindings={source_key: "synthetic-source"}),),
    ))
    assert bootstrap.event is not None
    event_id = bootstrap.event.id
    repo: PackagingAssetRepository = PostgresPackagingAssetRepository(postgres_dsn)
    service = PackagingAssetService(repo, FixedClock(NOW))
    register_op, revision_op, approval_op = EntityId.new(), EntityId.new(), EntityId.new()
    media_id, candidate_id = EntityId.new(), EntityId.new()
    try:
        asset = service.register(operation_id=register_op, actor_id=ACTOR, event_id=event_id,
                                 stage_id=bootstrap.stages[0].id, name="Intro",
                                 role=PackagingAssetRole.OPENING_BUMPER)
        first = revise(service, asset, operation=revision_op)
        approved = service.decide(operation_id=approval_op, actor_id=ACTOR,
                                  packaging_asset_id=asset.id, revision_number=1,
                                  expected_revision=1,
                                  action=ApprovalAction.APPROVE, reason="Human review")
        def append(_: int) -> str:
            independent = PackagingAssetService(PostgresPackagingAssetRepository(postgres_dsn),
                                                 FixedClock(NOW))
            try:
                revise(independent, asset, 1)
                return "created"
            except PackagingAssetConflictError:
                return "stale"
        with ThreadPoolExecutor(max_workers=3) as pool:
            assert sorted(pool.map(append, range(3))) == ["created", "stale", "stale"]
        restarted = PackagingAssetService(PostgresPackagingAssetRepository(postgres_dsn),
                                          FixedClock(NOW + timedelta(hours=1)))
        assert revise(restarted, asset, operation=revision_op) == first
        assert restarted.decide(operation_id=approval_op, actor_id=ACTOR,
                                packaging_asset_id=asset.id, revision_number=1, expected_revision=1,
                                action=ApprovalAction.APPROVE, reason="Human review") == approved
        assert restarted.register(operation_id=register_op, actor_id=ACTOR, event_id=event_id,
                                   stage_id=bootstrap.stages[0].id, name="Intro",
                                   role=PackagingAssetRole.OPENING_BUMPER) == asset
        with pytest.raises(PackagingAssetConflictError):
            revise(restarted, asset, 2, revision_op)
        with pytest.raises(PackagingAssetNotFoundError):
            revise(restarted, asset, 2, content=RevisionContent(
                CompletedMediaAssetContent(EntityId.new()),
            ))
        history = restarted.repository.list_revisions(event_id, asset.id, limit=1)
        assert history.total_count == 2 and history.next_after == 1
        assert history.items[0].approval_state == ApprovalState.APPROVED
        assert restarted.repository.list_revisions(
            event_id, asset.id, after=1,
        ).items[0].approval_state == (
            ApprovalState.UNREVIEWED
        )
        kernel_repository.register_candidate(MediaCandidate(
            candidate_id, media_id, bootstrap.stages[0].id, source_key, "synthetic-source",
            NOW, NOW, MediaRegistrationState.READY, 1,
        ))
        media = kernel_repository.register_asset(RegisteredMediaAsset(
            media_id, candidate_id, EntityId.new(), bootstrap.stages[0].id, source_key, NOW,
        ))
        third = revise(restarted, asset, 2, content=RevisionContent(
            CompletedMediaAssetContent(media.id), 1000, NOW, NOW + timedelta(days=1),
        ))
        assert restarted.repository.list_revisions(
            event_id, asset.id, after=2,
        ).items[0].revision == third
        for action in (ApprovalAction.REJECT, ApprovalAction.REVOKE):
            restarted.decide(operation_id=EntityId.new(), actor_id=ACTOR,
                             packaging_asset_id=asset.id, revision_number=1, expected_revision=3,
                             action=action, reason="Human correction")
        first_projection = restarted.repository.list_revisions(event_id, asset.id, limit=1).items[0]
        assert first_projection.approval_state == ApprovalState.REVOKED
        assert first_projection.decision_count == 3
        assert kernel_repository.get_asset(media.id) == media
        assert restarted.repository.list_assets(event_id).items[0].current_revision_number == 3
        with psycopg.connect(postgres_dsn) as connection:
            assert connection.execute(
                """SELECT count(*) FROM stageflow.packaging_asset_approval_decision
                   WHERE packaging_asset_id = %s""", (asset.id.value,),
            ).fetchone() == (3,)
            assert connection.execute(
                """SELECT count(*) FROM pg_trigger
                   WHERE tgname IN ('packaging_asset_revision_immutable',
                                    'packaging_asset_approval_immutable') AND tgenabled = 'O'"""
            ).fetchone() == (2,)
        runner.reverse_packaging_asset_foundation_v1()
        with psycopg.connect(postgres_dsn) as connection:
            assert connection.execute(
                "SELECT to_regclass('stageflow.packaging_asset')"
            ).fetchone() == (None,)
            assert connection.execute(
                "SELECT to_regclass('stageflow.editorial_moment_review_decision')"
            ).fetchone() == ("stageflow.editorial_moment_review_decision",)
            assert connection.execute(
                "SELECT to_regclass('stageflow.packaging_asset_command')"
            ).fetchone() == (None,)
        runner.apply_packaging_asset_foundation_v1()
        assert restarted.repository.list_assets(event_id).total_count == 0
        runner.reverse_editorial_review_foundation_v1()
    finally:
        # Isolated test database only. Remove this slice via its explicit reversal,
        # never by deleting immutable history rows; preserve all earlier tables.
        runner.reverse_packaging_asset_foundation_v1()
        runner.apply_editorial_review_foundation_v1()
        with psycopg.connect(postgres_dsn) as connection:
            connection.execute(
                "DELETE FROM stageflow.completed_media_asset_registry WHERE asset_id = %s",
                (media_id.value,),
            )
            connection.execute("DELETE FROM stageflow.media_candidate WHERE candidate_id = %s",
                               (candidate_id.value,))
            connection.execute("DELETE FROM stageflow.stage_source_binding WHERE stage_id = %s",
                               (bootstrap.stages[0].id.value,))
            connection.execute("DELETE FROM stageflow.stage WHERE stage_id = %s",
                               (bootstrap.stages[0].id.value,))
            connection.execute(
                "DELETE FROM stageflow.event_stage_bootstrap_operation WHERE operation_id = %s",
                (bootstrap_op.value,),
            )
            connection.execute("DELETE FROM stageflow.business_event WHERE event_id = %s",
                               (event_id.value,))
