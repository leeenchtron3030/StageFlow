"""Authenticated human render requests and bounded Event/Session reads."""
from datetime import UTC
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.assembly.session_repository import AssemblyNotFoundError
from app.contexts.rendering.contracts import (
    RENDER_PRESETS,
    RenderActor,
    RenderAdjustments,
    RenderedOutput,
    RenderError,
    effective_profile,
    render_preset,
)
from app.contexts.rendering.service import RenderingService
from app.contexts.rendering.settings import (
    ChooseRenderSetting,
    EventRenderSetting,
    RenderSettingsService,
)
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
    profile_id: str | None = None
    profile_version: str | None = None
    expected_setting_version: Annotated[StrictInt, Field(gt=0)] | None = None
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
        "video_bit_rate": operation.input.video_bit_rate,
        "audio_bit_rate": operation.input.audio_bit_rate,
        "event_render_setting_version": operation.input.event_render_setting_version,
        "attempt_count": operation.attempt_count, "reason_code": operation.last_reason_code,
        "created_at": operation.created_at.isoformat(),
        "updated_at": operation.updated_at.isoformat(),
        "rendered_output_id": None if operation.terminal_result_rendered_output_id is None
        else operation.terminal_result_rendered_output_id.value,
    }


def _output(output: RenderedOutput) -> dict[str, object]:
    return {
        "output_id": output.id.value, "assembly_revision_id": output.assembly_revision_id.value,
        "profile_id": output.profile_id, "profile_version": output.profile_version,
        "operation_id": output.operation_id.value,
        "video_bit_rate": output.video_bit_rate, "audio_bit_rate": output.audio_bit_rate,
        "event_render_setting_version": output.event_render_setting_version,
        "producing_attempt_id": output.producing_attempt_id.value,
        "content_key": output.content_key, "sha256": output.sha256,
        "manifest_content_key": output.manifest_content_key,
        "manifest_sha256": output.manifest_sha256,
        "byte_size": output.byte_size, "media_type": output.media_type,
        "duration_microseconds": output.duration_microseconds, "frame_count": output.frame_count,
        "ffmpeg_version": output.ffmpeg.version, "ffmpeg_sha256": output.ffmpeg.sha256,
        "produced_at": output.produced_at.isoformat(),
    }


# ED-0098 bodies carried no setting version and defaulted to Standard v3; keep that meaning so
# they succeed only while the Event's effective setting is exactly unadjusted Standard v3.
LEGACY_PROFILE = ("h264-nvenc-1080p-video", "3")


def _requested_profile(body: RequestBody) -> tuple[str | None, str | None]:
    if "expected_setting_version" in body.model_fields_set:
        return body.profile_id, body.profile_version
    return (body.profile_id or LEGACY_PROFILE[0], body.profile_version or LEGACY_PROFILE[1])


@router.post("/requests")
def request_render(body: RequestBody, request: Request) -> dict[str, object]:
    requested_id, requested_version = _requested_profile(body)
    try:
        return _operation(_service(request).request_render(
            EntityId(str(body.assembly_revision_id)),
            None,
            RenderActor(EntityId(str(body.actor_id))), EntityId(str(body.command_id)),
            (body.expected_setting_version
             if "expected_setting_version" in body.model_fields_set else "unspecified"),
            requested_profile_id=requested_id, requested_profile_version=requested_version,
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
            newest_first=True,
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


class SettingBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    profile_id: str
    profile_version: str
    video_bit_rate: StrictInt | None = None
    audio_bit_rate: StrictInt | None = None
    expected_version: Annotated[StrictInt, Field(gt=0)] | None
    actor_id: UUID
    command_id: UUID
    confirmed: Literal["confirmed"]
    authority_kind: Literal["human"] = "human"


def _setting_document(event_id: EntityId, value: EventRenderSetting | None) -> dict[str, object]:
    preset = RENDER_PRESETS[0] if value is None else render_preset(value.profile_id,
                                                                 value.profile_version)
    adjustments = RenderAdjustments() if value is None else value.adjustments
    profile = effective_profile(preset, adjustments)
    return {
        "event_id": event_id.value, "version": None if value is None else value.version,
        "profile_id": profile.id, "profile_version": profile.version,
        "video_bit_rate": adjustments.video_bit_rate, "audio_bit_rate": adjustments.audio_bit_rate,
        "effective_video_bit_rate": profile.bit_rate,
        "effective_audio_bit_rate": profile.audio_bit_rate,
        "selected_by": None if value is None else value.selected_by.value,
        "selected_at": None if value is None else value.selected_at.astimezone(UTC).isoformat(),
        "command_id": None if value is None else value.command_id.value,
    }


@router.get("/presets")
def presets() -> dict[str, object]:
    return {"items": [{
        "profile_id": p.profile.id, "profile_version": p.profile.version,
        "width": p.profile.width, "height": p.profile.height,
        "video_bit_rate": p.profile.bit_rate, "video_min": p.video_min,
        "video_max": p.video_max, "video_step": p.video_step,
        "audio_bit_rate": p.profile.audio_bit_rate, "audio_choices": p.audio_choices,
        "default": p == RENDER_PRESETS[0],
    } for p in RENDER_PRESETS]}


@router.get("/events/{event_id}/render-setting")
def render_setting(event_id: UUID, request: Request) -> dict[str, object]:
    repository = _service(request).repository
    assert isinstance(repository, PostgresRenderRepository)
    event = EntityId(str(event_id))
    try:
        history = repository.setting_history(event)
        return {"current": _setting_document(event, history[0] if history else None),
                "history": [_setting_document(event, item) for item in history]}
    except WorkExecutionNotFoundError:
        raise HTTPException(404, "render_reference_not_found") from None
    except WorkExecutionStorageUnavailableError:
        raise HTTPException(503, "postgresql_unavailable") from None


@router.post("/events/{event_id}/render-setting")
def choose_render_setting(event_id: UUID, body: SettingBody, request: Request) -> dict[str, object]:
    service = _service(request)
    repository = service.repository
    assert isinstance(repository, PostgresRenderRepository)
    event = EntityId(str(event_id))
    try:
        command = ChooseRenderSetting(event, body.profile_id, body.profile_version,
            RenderAdjustments(body.video_bit_rate, body.audio_bit_rate),
            RenderActor(EntityId(str(body.actor_id))), EntityId(str(body.command_id)),
            body.expected_version)
        chosen = RenderSettingsService(repository, service.clock).choose(command)
        return _setting_document(event, chosen)
    except RenderError as exc:
        raise HTTPException(409, exc.code.value) from None
    except WorkExecutionConflictError:
        raise HTTPException(409, "render_setting_command_conflict") from None
    except WorkExecutionNotFoundError:
        raise HTTPException(404, "render_reference_not_found") from None
    except WorkExecutionStorageUnavailableError:
        raise HTTPException(503, "postgresql_unavailable") from None
