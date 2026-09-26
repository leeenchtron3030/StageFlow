from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from fractions import Fraction
from typing import cast
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import rendering as rendering_api
from app.api.v1.router import router
from app.contexts.assembly.session_contracts import AssemblyRevision
from app.contexts.rendering.contracts import (
    CURRENT_RENDER_PROFILE,
    FIRST_RENDER_PROFILE,
    RENDER_PROFILE_V1,
    FFmpegIdentity,
    RenderActor,
    RenderError,
    RenderProfile,
    RenderReason,
    require_profile,
)
from app.contexts.rendering.service import RenderingService
from app.contexts.work_execution import OperationStatus, RenderOperationInput
from app.contexts.work_execution.application import pending_render_operation
from app.demo.render_worker import render_capability
from app.infrastructure.postgres.render_repository import PostgresRenderRepository
from app.shared.ids import EntityId
from app.shared.time import FixedClock
from tests.test_packaging_asset_foundation import HEADERS, SyncHttpClient
from tests.test_render_work_execution import (
    NOW,
    Harness,
    MutableClock,
    claim_request,
    general_repository,
    render_request,
    worker,
)
from tests.test_render_work_execution import harness as harness
from tests.test_render_work_execution import render_postgres_dsn as render_postgres_dsn
from tests.test_rendering_phase_b import MemoryRendering, output_for
from tests.test_rendering_phase_b import approved_revision as approved_revision


def test_current_profile_rate_is_immutable_and_v1_is_recorded_only() -> None:
    profile = CURRENT_RENDER_PROFILE
    assert RenderProfile() == profile
    assert FIRST_RENDER_PROFILE is profile
    assert profile.version == "2" and profile.output_frame_rate == Fraction(30000, 1001)
    assert RENDER_PROFILE_V1.version == "1" and RENDER_PROFILE_V1.output_frame_rate is None
    assert replace(profile, version="1", output_frame_rate=None) == RENDER_PROFILE_V1
    with pytest.raises(FrozenInstanceError):
        profile.__setattr__("output_frame_rate", Fraction(25))
    for unsupported in (RENDER_PROFILE_V1, replace(profile, output_frame_rate=Fraction(30))):
        with pytest.raises(RenderError, match="render_profile_unsupported"):
            require_profile(unsupported)
    for not_a_fraction in (29.97, 30):
        with pytest.raises(RenderError, match="render_profile_unsupported"):
            RenderProfile(output_frame_rate=cast(Fraction, not_a_fraction))
    output = output_for(EntityId.new(), EntityId.new(), EntityId.new())
    with pytest.raises(RenderError, match="render_output_invalid"):
        replace(output, profile_version="3")


def test_service_refuses_v1_before_repository_access() -> None:
    repository = Mock()
    with pytest.raises(RenderError) as failure:
        RenderingService(repository, FixedClock(NOW), "synthetic").request_render(
            EntityId.new(), RENDER_PROFILE_V1, RenderActor(EntityId.new()), EntityId.new(),
        )
    assert failure.value.code == RenderReason.PROFILE_UNSUPPORTED
    assert repository.mock_calls == []


@pytest.mark.parametrize("version", [None, "2", "1"])
def test_api_defaults_to_v2_and_refuses_v1_bounded(
    monkeypatch: pytest.MonkeyPatch, version: str | None,
) -> None:
    memory = MemoryRendering()
    def api_service(request: object) -> RenderingService:
        return memory.service()

    monkeypatch.setattr(rendering_api, "_service", api_service)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    client = cast(SyncHttpClient, TestClient(app))
    body = {"assembly_revision_id": memory.source.revision.id.value,
            "actor_id": EntityId.new().value, "command_id": EntityId.new().value,
            "confirmed": "confirmed"}
    if version is not None:
        body["profile_version"] = version
    response = client.post("/api/v1/rendering/requests", headers=HEADERS, json=body)
    if version == "1":
        assert response.status_code == 409
        assert response.json() == {"detail": "render_profile_unsupported"}
        assert memory.work.operations == {}
    else:
        assert response.status_code == 200
        assert response.json()["profile_version"] == "2"
        assert next(iter(memory.work.operations.values())).input.execution_profile_version == "2"


def test_v2_on_v1_rendered_revision_creates_new_operation_and_replays() -> None:
    memory = MemoryRendering()
    old_request = replace(render_request(), event_id=memory.source.revision.event_id,
        input=RenderOperationInput(memory.source.revision.id, RENDER_PROFILE_V1.id, "1", "old"))
    old = memory.work.enqueue(pending_render_operation(old_request))
    output = replace(output_for(old.id, EntityId.new(), memory.source.revision.id),
                     profile_version="1")
    memory.outputs.append(output)
    completed = replace(old, status=OperationStatus.SUCCEEDED,
                        terminal_result_type="rendered_output",
                        terminal_result_rendered_output_id=output.id)
    memory.work.operations[old.id] = completed
    actor, command = RenderActor(EntityId.new()), EntityId.new()
    current = memory.service().request_render(memory.source.revision.id, CURRENT_RENDER_PROFILE,
                                               actor, command)
    assert current.id != old.id and current.work_key != old.work_key
    assert current.input.execution_profile_version == "2"
    for replay_command in (command, EntityId.new()):
        assert memory.service().request_render(memory.source.revision.id, CURRENT_RENDER_PROFILE,
                                                actor, replay_command) == current
    assert memory.work.get_operation(old.id) == completed
    assert memory.outputs == [output] and output.profile_version == "1"


def test_worker_v2_capability_claims_only_v2_leaving_v1_pending(harness: Harness) -> None:
    old_request = replace(harness.request, input=replace(harness.request.input,
        execution_profile_id=CURRENT_RENDER_PROFILE.id, execution_profile_version="1"))
    old = harness.repository.enqueue(pending_render_operation(old_request))
    renderer = worker(harness, "render")
    capability = render_capability(renderer.id, FFmpegIdentity("synthetic", "a" * 64), True, NOW)
    assert capability.execution_profile_id == CURRENT_RENDER_PROFILE.id
    assert capability.execution_profile_version == "2"
    harness.repository.register_capability(capability)
    request = replace(claim_request(renderer), operation_kind="render")
    assert harness.repository.claim_next(request) is None
    new_request = replace(old_request, operation_id=EntityId.new(), idempotency_key="new-v2",
                          input=replace(old_request.input, execution_profile_version="2"))
    current = harness.repository.enqueue(pending_render_operation(new_request))
    claim = harness.repository.claim_next(request)
    assert claim is not None and claim.operation.id == current.id
    assert claim.operation.input.execution_profile_version == "2"
    # ADR-0025 may promote due pending work to eligible before capability matching; the
    # guarantee is that a v2 worker never claims, leases, or attempts v1 work.
    unclaimed = harness.repository.get_operation(old.id)
    assert unclaimed.status in {OperationStatus.PENDING, OperationStatus.ELIGIBLE}
    assert unclaimed.current_attempt_id is None and unclaimed.attempt_count == 0
    assert unclaimed.input == old.input and unclaimed.work_key == old.work_key


def test_postgres_v1_history_hydrates_lists_and_v2_rerenders(
    render_postgres_dsn: str, approved_revision: AssemblyRevision,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Seed an authentic historical operation through the generic substrate, which retains
    # versioned history; new human requests still go through RenderingService's v2 guard.
    generic = general_repository(render_postgres_dsn)
    envelope = replace(render_request(), event_id=approved_revision.event_id,
        input=RenderOperationInput(approved_revision.id, RENDER_PROFILE_V1.id, "1", "old"))
    old = generic.enqueue(pending_render_operation(envelope))
    harness_value = Harness(generic, envelope, MutableClock(), render_postgres_dsn)
    renderer = worker(harness_value, "render")
    historical_capability = replace(render_capability(renderer.id,
        FFmpegIdentity("synthetic", "a" * 64), True, NOW + timedelta(seconds=1)),
        execution_profile_version="1")
    repo = PostgresRenderRepository(render_postgres_dsn)
    repo.register_render_capability(historical_capability)
    claim = repo.claim_next(replace(claim_request(renderer), operation_kind="render"))
    assert claim is not None and claim.operation.id == old.id
    claim = repo.mark_running(claim)
    output = replace(output_for(old.id, claim.attempt.id, approved_revision.id),
                     profile_version="1")
    repo.apply_render_result(claim, output)

    restarted = PostgresRenderRepository(render_postgres_dsn)
    service = RenderingService(restarted, FixedClock(NOW), "test-deployment")
    actor, command = RenderActor(EntityId.new()), EntityId.new()
    current = service.request_render(approved_revision.id, CURRENT_RENDER_PROFILE, actor, command)
    assert current.id != old.id and current.work_key != old.work_key
    assert current.input.execution_profile_version == "2"
    assert service.request_render(approved_revision.id, CURRENT_RENDER_PROFILE,
                                   actor, command) == current
    assert service.request_render(approved_revision.id, CURRENT_RENDER_PROFILE,
                                   actor, EntityId.new()) == current
    assert restarted.get_operation(old.id).status == OperationStatus.SUCCEEDED
    assert restarted.list_outputs(approved_revision.event_id,
                                   approved_revision.session_id) == ((output,), None)
    operations, _ = restarted.list_render_operations(approved_revision.event_id,
                                                      approved_revision.session_id)
    assert {item.input.execution_profile_version for item in operations} == {"1", "2"}
    def api_service(request: object) -> RenderingService:
        return service

    monkeypatch.setattr(rendering_api, "_service", api_service)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    client = cast(SyncHttpClient, TestClient(app))
    response = client.get("/api/v1/rendering/outputs"
        f"?event_id={approved_revision.event_id.value}&session_id={approved_revision.session_id.value}",
        headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["items"][0]["profile_version"] == "1"
    assert response.json()["items"][0]["output_id"] == output.id.value
