"""Authenticated human render requests and bounded Event/Session reads."""
from dataclasses import replace
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict

from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.assembly.session_repository import AssemblyNotFoundError
from app.contexts.rendering.contracts import (
    CURRENT_RENDER_PROFILE,
    RenderActor,
    RenderedOutput,
    RenderError,
)
from app.contexts.rendering.service import RenderingService
from app.contexts.work_execution import (
    DurableOperation,
    RenderOperationInput,
    WorkExecutionConflictError,
    WorkExecutionNotFoundError,
    WorkExecutionStorageUnavailableError,
)
from app.infrastructure.postgres.render_repository import PostgresRenderRepository
from app.shared.ids import EntityId

router = APIRouter(prefix="/rendering", tags=["rendering"])


class RequestBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    assembly_revision_id: UUID
    profile_id: Literal["h264-nvenc-1080p-video"] = "h264-nvenc-1080p-video"
    profile_version: Literal["1", "2"] = "2"
    actor_id: UUID
    command_id: UUID
    confirmed: Literal["confirmed"]
    authority_kind: Literal["human"] = "human"


def _service(request: Request) -> RenderingService:
    components = getattr(request.app.state, "kernel", None)
    if not isinstance(components, KernelComponents):
        raise HTTPException(503, "rendering_service_unavailable")
    local = components.configuration.deployment.local_render
    if local is None or not local.enabled:
        raise HTTPException(503, "local_render_not_enabled")
    return RenderingService(
        PostgresRenderRepository(components.configuration.postgres_dsn),
        components.kernel.clock, components.configuration.deployment.deployment_id,
    )


def _operation(operation: DurableOperation[RenderOperationInput]) -> dict[str, object]:
    return {
        "operation_id": operation.id.value, "state": operation.status.value,
        "assembly_revision_id": operation.input.assembly_revision_id.value,
        "profile_id": operation.input.execution_profile_id,
        "profile_version": operation.input.execution_profile_version,
        "attempt_count": operation.attempt_count, "reason_code": operation.last_reason_code,
        "rendered_output_id": None if operation.terminal_result_rendered_output_id is None
        else operation.terminal_result_rendered_output_id.value,
    }


def _output(output: RenderedOutput) -> dict[str, object]:
    return {
        "output_id": output.id.value, "assembly_revision_id": output.assembly_revision_id.value,
        "profile_id": output.profile_id, "profile_version": output.profile_version,
        "operation_id": output.operation_id.value,
        "producing_attempt_id": output.producing_attempt_id.value,
        "content_key": output.content_key, "sha256": output.sha256,
        "manifest_content_key": output.manifest_content_key,
        "manifest_sha256": output.manifest_sha256,
        "byte_size": output.byte_size, "media_type": output.media_type,
        "duration_microseconds": output.duration_microseconds, "frame_count": output.frame_count,
        "ffmpeg_version": output.ffmpeg.version, "ffmpeg_sha256": output.ffmpeg.sha256,
        "produced_at": output.produced_at.isoformat(),
    }


@router.post("/requests")
def request_render(body: RequestBody, request: Request) -> dict[str, object]:
    try:
        return _operation(_service(request).request_render(
            EntityId(str(body.assembly_revision_id)),
            replace(CURRENT_RENDER_PROFILE, version=body.profile_version),
            RenderActor(EntityId(str(body.actor_id))), EntityId(str(body.command_id)),
        ))
    except RenderError as exc:
        raise HTTPException(409, exc.code.value) from None
    except (WorkExecutionNotFoundError, AssemblyNotFoundError):
        raise HTTPException(404, "render_reference_not_found") from None
    except WorkExecutionConflictError:
        raise HTTPException(409, "render_request_conflict") from None
    except WorkExecutionStorageUnavailableError:
        raise HTTPException(503, "postgresql_unavailable") from None


@router.get("/operations")
def operations(
    request: Request, event_id: UUID, session_id: UUID,
    limit: Annotated[int, Query(ge=1, le=100)] = 50, after: UUID | None = None,
) -> dict[str, object]:
    repository = _service(request).repository
    assert isinstance(repository, PostgresRenderRepository)
    try:
        items, cursor = repository.list_render_operations(
            EntityId(str(event_id)), EntityId(str(session_id)), limit=limit,
            after=None if after is None else EntityId(str(after)),
        )
    except WorkExecutionStorageUnavailableError:
        raise HTTPException(503, "postgresql_unavailable") from None
    return {"items": [_operation(item) for item in items], "limit": limit,
            "next_after": None if cursor is None else cursor.value}


@router.get("/outputs")
def outputs(
    request: Request, event_id: UUID, session_id: UUID,
    limit: Annotated[int, Query(ge=1, le=100)] = 50, after: UUID | None = None,
) -> dict[str, object]:
    repository = _service(request).repository
    assert isinstance(repository, PostgresRenderRepository)
    try:
        items, cursor = repository.list_outputs(
            EntityId(str(event_id)), EntityId(str(session_id)), limit=limit,
            after=None if after is None else EntityId(str(after)),
        )
    except WorkExecutionStorageUnavailableError:
        raise HTTPException(503, "postgresql_unavailable") from None
    return {"items": [_output(item) for item in items], "limit": limit,
            "next_after": None if cursor is None else cursor.value}
