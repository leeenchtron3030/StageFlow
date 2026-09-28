from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
from typing import Any, LiteralString, cast

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import rendering as api
from app.contexts.assembly.session_contracts import AssemblyRevision
from app.contexts.rendering.contracts import (
    CURRENT_RENDER_PROFILE,
    RENDER_PRESETS,
    FFmpegIdentity,
    RenderActor,
    RenderAdjustments,
    RenderError,
)
from app.contexts.rendering.service import RenderingService
from app.contexts.rendering.settings import ChooseRenderSetting
from app.contexts.work_execution import (
    DurableOperation,
    OperationFailure,
    RenderOperationInput,
    WorkExecutionConflictError,
    WorkExecutionStorageUnavailableError,
)
from app.contexts.work_execution.application import pending_render_operation
from app.demo.render_worker import render_capability
from app.infrastructure.postgres import PostgresMigrationRunner
from app.infrastructure.postgres.render_repository import PostgresRenderRepository
from app.shared.ids import EntityId
from app.shared.time import FixedClock
from tests.test_packaging_asset_foundation import SyncHttpClient
from tests.test_render_work_execution import (
    NOW,
    Harness,
    MutableClock,
    claim_request,
    general_repository,
    render_request,
    worker,
)
from tests.test_render_work_execution import render_postgres_dsn as render_postgres_dsn
from tests.test_rendering_phase_b import approved_revision as approved_revision
from tests.test_rendering_phase_b import output_for


def command(event_id: EntityId, index: int = 0, expected: int | None = None,
            adjustments: RenderAdjustments | None = None) -> ChooseRenderSetting:
    profile = RENDER_PRESETS[index].profile
    return ChooseRenderSetting(event_id, profile.id, profile.version,
                               adjustments or RenderAdjustments(), RenderActor(EntityId.new()),
                               EntityId.new(), expected)


def test_setting_replay_conflict_versions_and_immutable_history(
    render_postgres_dsn: str, approved_revision: AssemblyRevision,
) -> None:
    repo = PostgresRenderRepository(render_postgres_dsn)
    event = approved_revision.event_id
    assert repo.setting_history(event) == ()
    first = command(event, adjustments=RenderAdjustments(8_000_000, 192_000))
    chosen = repo.choose_setting(first, NOW)
    assert chosen.version == 1 and chosen.adjustments == RenderAdjustments()
    assert repo.choose_setting(first, NOW + timedelta(days=1)) == chosen
    with pytest.raises(WorkExecutionConflictError):
        repo.choose_setting(replace(first, actor=RenderActor(EntityId.new())), NOW)
    stale = command(event, 1)
    with pytest.raises(RenderError, match="render_setting_changed"):
        repo.choose_setting(stale, NOW)
    # A refusal has no receipt: correcting its expectation can use the same ID.
    second = repo.choose_setting(replace(stale, expected_version=1), NOW)
    assert second.version == 2
    assert repo.setting_history(event) == (second, chosen)
    assert repo.choose_setting(first, NOW) == chosen
    with psycopg.connect(render_postgres_dsn) as conn:
        for action in ("UPDATE stageflow.event_render_setting SET version=99",
                       "DELETE FROM stageflow.event_render_setting"):
            with pytest.raises(psycopg.Error, match="render_history_is_immutable"):
                with conn.transaction():
                    conn.execute(cast(LiteralString, action))
    with pytest.raises(psycopg.Error, match="event_render_setting_reverse_refused"):
        PostgresMigrationRunner(render_postgres_dsn).reverse_event_render_setting_v1()


def test_request_freezes_setting_stale_enqueues_nothing_and_effective_keys(
    render_postgres_dsn: str, approved_revision: AssemblyRevision,
) -> None:
    repo = PostgresRenderRepository(render_postgres_dsn)
    service = RenderingService(repo, FixedClock(NOW), "test-deployment")
    actor = RenderActor(EntityId.new())
    def request(expected: int | None):
        return service.request_render(approved_revision.id, None, actor, EntityId.new(), expected)
    default = request(None)
    first = repo.choose_setting(command(approved_revision.event_id), NOW)
    # Unadjusted settings retain the old work key and operation input, including provenance.
    assert request(first.version) == default
    high = repo.choose_setting(command(approved_revision.event_id, 1, first.version,
                                        RenderAdjustments(20_000_000, 320_000)), NOW)
    with pytest.raises(RenderError, match="render_setting_changed"):
        request(first.version)
    before, _ = repo.list_render_operations(
        approved_revision.event_id, approved_revision.session_id)
    assert before == (default,)
    adjusted = request(high.version)
    assert adjusted.id != default.id and adjusted.work_key != default.work_key
    assert (adjusted.input.video_bit_rate, adjusted.input.audio_bit_rate,
            adjusted.input.event_render_setting_version) == (20_000_000, 320_000, 2)
    assert request(high.version) == adjusted
    with pytest.raises(RenderError, match="render_setting_changed"):
        service.request_render(approved_revision.id, CURRENT_RENDER_PROFILE, actor, EntityId.new())
    changed = repo.choose_setting(command(approved_revision.event_id, 2, high.version), NOW)
    compact = request(changed.version)
    assert compact.input.execution_profile_id == RENDER_PRESETS[2].profile.id
    assert repo.get_operation(default.id) == default
    assert repo.get_operation(adjusted.id) == adjusted
    # Lost responses replay frozen receipt intent even after the Event changes.
    assert service.request_render(approved_revision.id, None, actor, default.id, None) == default
    assert service.request_render(approved_revision.id, None, actor, adjusted.id, 2) == adjusted
    with pytest.raises(WorkExecutionConflictError):
        service.request_render(approved_revision.id, None, RenderActor(EntityId.new()),
                               adjusted.id, 2)


def test_migration_empty_reverse_reapply_preserves_existing_input(
    render_postgres_dsn: str, approved_revision: AssemblyRevision,
) -> None:
    repo = PostgresRenderRepository(render_postgres_dsn)
    existing = RenderingService(repo, FixedClock(NOW), "test-deployment").request_render(
        approved_revision.id, CURRENT_RENDER_PROFILE, RenderActor(EntityId.new()), EntityId.new())
    runner = PostgresMigrationRunner(render_postgres_dsn)
    runner.reverse_event_render_setting_v1()
    with psycopg.connect(render_postgres_dsn) as conn:
        before = conn.execute("SELECT * FROM stageflow.render_operation_input").fetchall()
        constraints = conn.execute("SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
                                   "WHERE conrelid='stageflow.render_operation_input'::regclass"
                                   " ORDER BY conname").fetchall()
    runner.apply_event_render_setting_v1()
    assert repo.get_operation(existing.id) == existing
    runner.reverse_event_render_setting_v1()
    with psycopg.connect(render_postgres_dsn) as conn:
        assert conn.execute("SELECT * FROM stageflow.render_operation_input").fetchall() == before
        assert conn.execute("SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
                            "WHERE conrelid='stageflow.render_operation_input'::regclass"
                            " ORDER BY conname").fetchall() == constraints
    runner.apply_event_render_setting_v1()


def test_every_declared_preset_claimed_and_other_worker_does_not_claim(
    render_postgres_dsn: str, approved_revision: AssemblyRevision,
) -> None:
    repo = PostgresRenderRepository(render_postgres_dsn)
    service = RenderingService(repo, FixedClock(NOW), "test-deployment")
    harness = Harness(general_repository(render_postgres_dsn),
        replace(render_request(), event_id=approved_revision.event_id), MutableClock(),
        render_postgres_dsn)
    renderer = worker(harness, "render")
    operations: list[DurableOperation[RenderOperationInput]] = []
    for index, _preset in enumerate(RENDER_PRESETS):
        setting = repo.choose_setting(command(approved_revision.event_id, index,
                                               index or None), NOW)
        operations.append(service.request_render(approved_revision.id, None,
            RenderActor(EntityId.new()), EntityId.new(), setting.version))
    assert repo.claim_next(claim_request(renderer)) is None  # v1 history declaration only
    for preset in RENDER_PRESETS:
        repo.register_render_capability(render_capability(renderer.id,
            FFmpegIdentity("synthetic", "a" * 64), True, NOW + timedelta(seconds=1),
            preset.profile))
    with psycopg.connect(render_postgres_dsn) as conn:
        rows = conn.execute(
            "SELECT * FROM stageflow.work_worker_capability WHERE worker_id=%s "
            "AND effective_until IS NULL", (renderer.id.value,),
        ).fetchall()
        assert len(rows) == 3
    claimed: set[EntityId] = set()
    for _ in operations:
        claim = repo.claim_next(claim_request(renderer))
        assert claim is not None
        claimed.add(claim.operation.id)
        assert repo.claim_next(claim_request(renderer)) is None  # one GPU lease
        repo.record_failure(claim, OperationFailure("synthetic", False, "synthetic"))
    assert claimed == {operation.id for operation in operations}


def test_setting_api_shapes_legacy_body_and_bounded_refusals(
    render_postgres_dsn: str, approved_revision: AssemblyRevision, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = PostgresRenderRepository(render_postgres_dsn)
    service = RenderingService(repo, FixedClock(NOW), "test-deployment")
    def api_service(request: object) -> RenderingService:
        return service
    monkeypatch.setattr(api, "_service", api_service)
    app = FastAPI()
    app.include_router(api.router)
    client = cast(SyncHttpClient, TestClient(app))
    path = f"/rendering/events/{approved_revision.event_id.value}/render-setting"
    assert len(client.get("/rendering/presets").json()["items"]) == 3
    assert client.get(path).json()["current"]["version"] is None
    body: dict[str, Any] = {"assembly_revision_id": approved_revision.id.value,
        "profile_version": "3", "actor_id": EntityId.new().value,
        "command_id": EntityId.new().value, "confirmed": "confirmed"}
    assert client.post("/rendering/requests", json=body).status_code == 200
    for preset in RENDER_PRESETS[1:]:
        assert client.post("/rendering/requests", json={
            **{key: value for key, value in body.items() if key != "profile_version"},
            "profile_id": preset.profile.id, "command_id": EntityId.new().value,
        }).json() == {"detail": "render_setting_changed"}
    setting = {"profile_id": CURRENT_RENDER_PROFILE.id, "profile_version": "3",
        "actor_id": body["actor_id"], "command_id": EntityId.new().value,
        "expected_version": None, "confirmed": "confirmed", "video_bit_rate": 6_500_000}
    chosen = client.post(path, json=setting)
    assert chosen.status_code == 200 and chosen.json()["version"] == 1
    assert chosen.json()["effective_video_bit_rate"] == 6_500_000
    assert client.post(path, json=setting).json() == chosen.json()
    assert client.get(path).json()["history"] == [chosen.json()]
    setting["command_id"] = EntityId.new().value
    assert client.post(path, json=setting).json() == {"detail": "render_setting_changed"}
    setting.update(expected_version=1, video_bit_rate=6_500_001)
    assert client.post(path, json=setting).json() == {"detail": "render_adjustment_out_of_bounds"}
    body["command_id"] = EntityId.new().value
    assert client.post("/rendering/requests", json=body).json() == {
        "detail": "render_setting_changed"}
    body["expected_setting_version"] = 1
    response = client.post("/rendering/requests", json=body)
    assert response.status_code == 200
    assert response.json()["video_bit_rate"] == 6_500_000
    for invalid in (True, "6500000", 6500000.0):
        setting["video_bit_rate"] = invalid
        assert client.post(path, json=setting).status_code == 422
    # Each optional profile field independently constrains the setting resolved in enqueue.
    high = repo.choose_setting(command(approved_revision.event_id, 1, 1), NOW)
    body.pop("profile_version")
    body["expected_setting_version"] = high.version
    for fields in ({"profile_id": high.profile_id}, {"profile_version": high.profile_version}, {}):
        response = client.post("/rendering/requests", json={
            **body, **fields, "command_id": EntityId.new().value})
        assert response.status_code == 200
        assert response.json()["profile_id"] == high.profile_id
    response = client.post("/rendering/requests", json={
        **body, "profile_id": RENDER_PRESETS[2].profile.id, "command_id": EntityId.new().value})
    assert response.json() == {"detail": "render_setting_changed"}
    for fields in ({"profile_id": CURRENT_RENDER_PROFILE.id}, {"profile_version": "3"}):
        response = client.post("/rendering/requests", json={
            **body, **fields, "command_id": EntityId.new().value})
        assert response.json() == {"detail": "render_setting_changed"}
    for version in ("1", "2"):
        response = client.post("/rendering/requests", json={
            **body, "profile_id": CURRENT_RENDER_PROFILE.id, "profile_version": version,
            "command_id": EntityId.new().value})
        assert response.json() == {"detail": "render_profile_unsupported"}


def test_setting_transaction_failure_rolls_back_row_and_receipt(
    render_postgres_dsn: str, approved_revision: AssemblyRevision, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = PostgresRenderRepository(render_postgres_dsn)
    choose = command(approved_revision.event_id)
    connect = cast(Any, repo)._connect
    @contextmanager
    def failing() -> Generator[Any]:
        with connect() as conn:
            yield conn
            raise psycopg.OperationalError("synthetic_rollback")
    with monkeypatch.context() as patch:
        patch.setattr(repo, "_connect", failing)
        with pytest.raises(WorkExecutionStorageUnavailableError):
            repo.choose_setting(choose, NOW)
    assert repo.setting_history(approved_revision.event_id) == ()
    assert repo.choose_setting(choose, NOW).version == 1


def test_reverse_refuses_input_adjustments_without_a_setting_row(
    render_postgres_dsn: str, approved_revision: AssemblyRevision,
) -> None:
    repo = PostgresRenderRepository(render_postgres_dsn)
    request = render_request()
    request = replace(request, event_id=approved_revision.event_id,
        input=replace(request.input, assembly_revision_id=approved_revision.id,
            execution_profile_id=CURRENT_RENDER_PROFILE.id, execution_profile_version="3",
            video_bit_rate=6_500_000))
    operation = repo.request(pending_render_operation(request))
    assert repo.setting_history(approved_revision.event_id) == ()
    with psycopg.connect(render_postgres_dsn) as conn:
        with pytest.raises(psycopg.Error, match="render_history_is_immutable"):
            with conn.transaction():
                conn.execute("UPDATE stageflow.render_operation_input SET video_bit_rate=NULL "
                             "WHERE operation_id=%s", (operation.id.value,))
    with pytest.raises(psycopg.Error, match="event_render_setting_reverse_refused"):
        PostgresMigrationRunner(render_postgres_dsn).reverse_event_render_setting_v1()
    assert repo.get_operation(operation.id) == operation


def test_quality_change_preserves_output_bytes_identity_and_listing_provenance(
    render_postgres_dsn: str, approved_revision: AssemblyRevision,
) -> None:
    repo = PostgresRenderRepository(render_postgres_dsn)
    setting = repo.choose_setting(command(approved_revision.event_id, 1, None,
        RenderAdjustments(20_000_000, 320_000)), NOW)
    operation = RenderingService(repo, FixedClock(NOW), "test-deployment").request_render(
        approved_revision.id, None, RenderActor(EntityId.new()), EntityId.new(), setting.version)
    harness = Harness(general_repository(render_postgres_dsn),
        replace(render_request(), event_id=approved_revision.event_id), MutableClock(),
        render_postgres_dsn)
    renderer = worker(harness, "render")
    repo.register_render_capability(render_capability(renderer.id,
        FFmpegIdentity("synthetic", "a" * 64), True, NOW + timedelta(seconds=1),
        RENDER_PRESETS[1].profile))
    claim = repo.claim_next(claim_request(renderer))
    assert claim is not None
    output = replace(output_for(operation.id, claim.attempt.id, approved_revision.id),
        profile_id=setting.profile_id, profile_version=setting.profile_version,
        video_bit_rate=20_000_000, audio_bit_rate=320_000, event_render_setting_version=1)
    repo.apply_render_result(claim, output)
    with psycopg.connect(render_postgres_dsn) as conn:
        before = conn.execute("SELECT * FROM stageflow.rendered_output WHERE output_id=%s",
                              (output.id.value,)).fetchone()
    repo.choose_setting(command(approved_revision.event_id, 2, 1), NOW)
    with psycopg.connect(render_postgres_dsn) as conn:
        assert conn.execute("SELECT * FROM stageflow.rendered_output WHERE output_id=%s",
                            (output.id.value,)).fetchone() == before
    assert repo.list_outputs(approved_revision.event_id,
                             approved_revision.session_id) == ((output,), None)
    assert vars(api)["_output"](output)["video_bit_rate"] == 20_000_000
