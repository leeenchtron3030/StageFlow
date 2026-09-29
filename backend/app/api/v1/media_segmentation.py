"""Authenticated, bounded inspection commands and advisory summaries."""
from dataclasses import asdict
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.production.media_segmentation_evidence.enqueue import MediaSegmentationEnqueue
from app.contexts.work_execution import (
    DurableOperation,
    MediaSegmentationOperationInput,
    WorkExecutionConflictError,
    WorkExecutionStorageUnavailableError,
)
from app.infrastructure.postgres.media_segmentation_repository import (
    PostgresMediaSegmentationRepository,
)
from app.shared.ids import EntityId

router = APIRouter(prefix="/media-segmentation", tags=["media segmentation"])


class EnqueueBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    actor_id: UUID
    authority_kind: Literal["human"] = "human"
    confirmed: Literal["confirmed"]
    limit: int = Field(default=50, ge=1, le=100)
    after: UUID | None = None


def _components(request: Request) -> KernelComponents:
    components = getattr(request.app.state, "kernel", None)
    if not isinstance(components, KernelComponents):
        raise HTTPException(503, "kernel_not_configured")
    return components


def _repository(request: Request) -> PostgresMediaSegmentationRepository:
    return PostgresMediaSegmentationRepository(_components(request).configuration.postgres_dsn)


def _operation(value: DurableOperation[MediaSegmentationOperationInput]) -> dict[str, object]:
    return {"operation_id": value.id.value, "asset_id": value.input.asset_id.value,
            "state": value.status.value, "attempt_count": value.attempt_count,
            "reason_code": value.last_reason_code,
            "profile_id": value.input.segmentation_profile_id,
            "profile_version": value.input.segmentation_profile_version,
            "evidence_id": None if value.terminal_result_media_segmentation_evidence_id is None
            else value.terminal_result_media_segmentation_evidence_id.value}


@router.post("/events/{event_id}/requests")
def enqueue_existing(event_id: UUID, body: EnqueueBody, request: Request) -> dict[str, object]:
    components = _components(request)
    local = components.configuration.deployment.local_media_segmentation
    if local is None or not local.enabled:
        raise HTTPException(503, "local_media_segmentation_not_enabled")
    repository = _repository(request)
    try:
        items, cursor = MediaSegmentationEnqueue(repository,
            components.configuration.deployment.deployment_id,
            components.kernel.clock).enqueue_existing(
                repository, EntityId(str(event_id)), actor_id=EntityId(str(body.actor_id)),
                authority_kind=body.authority_kind, confirmed=body.confirmed == "confirmed",
                limit=body.limit, after=None if body.after is None else EntityId(str(body.after)),
            )
    except WorkExecutionConflictError:
        raise HTTPException(409, "media_segmentation_enqueue_conflict") from None
    except WorkExecutionStorageUnavailableError:
        raise HTTPException(503, "postgresql_unavailable") from None
    return {"items": [_operation(item) for item in items], "limit": body.limit,
            "next_after": None if cursor is None else cursor.value}


@router.get("/events/{event_id}/operations")
def operations(event_id: UUID, request: Request,
               limit: Annotated[int, Query(ge=1, le=100)] = 50,
               after: UUID | None = None) -> dict[str, object]:
    try:
        items, cursor = _repository(request).page(EntityId(str(event_id)), limit=limit,
            after=None if after is None else EntityId(str(after)))
    except WorkExecutionStorageUnavailableError:
        raise HTTPException(503, "postgresql_unavailable") from None
    return {"items": [_operation(item) for item in items], "limit": limit,
            "next_after": None if cursor is None else cursor.value}


def _evidence_page(request: Request, *, asset_id: UUID | None = None,
                   session_id: UUID | None = None, limit: int, after: UUID | None
                   ) -> dict[str, object]:
    components = _components(request)
    if asset_id is not None and components.repository.get_asset(EntityId(str(asset_id))) is None:
        raise HTTPException(404, "completed_media_asset_not_found")
    if (session_id is not None
            and components.repository.get_session(EntityId(str(session_id))) is None):
        raise HTTPException(404, "session_not_found")
    try:
        items, cursor = _repository(request).evidence_page(
            asset_id=None if asset_id is None else EntityId(str(asset_id)),
            session_id=None if session_id is None else EntityId(str(session_id)),
            limit=limit, after=None if after is None else EntityId(str(after)))
    except WorkExecutionStorageUnavailableError:
        raise HTTPException(503, "postgresql_unavailable") from None
    return {"items": [{
        "evidence_id": item.id.value, "operation_id": item.operation_id.value,
        "asset_id": item.asset_id.value, "manifest_id": item.manifest_id.value,
        "manifest_version": item.manifest_version,
        "producing_attempt_id": item.producing_attempt_id.value,
        "recorded_at": item.recorded_at.isoformat(),
        "result": asdict(item.result), "authorized_use": "advisory_only",
    } for item in items], "limit": limit, "next_after": None if cursor is None else cursor.value}


@router.get("/assets/{asset_id}/evidence")
def asset_evidence(asset_id: UUID, request: Request,
                   limit: Annotated[int, Query(ge=1, le=10)] = 5,
                   after: UUID | None = None) -> dict[str, object]:
    return _evidence_page(request, asset_id=asset_id, limit=limit, after=after)


@router.get("/sessions/{session_id}/evidence")
def session_evidence(session_id: UUID, request: Request,
                     limit: Annotated[int, Query(ge=1, le=10)] = 5,
                     after: UUID | None = None) -> dict[str, object]:
    return _evidence_page(request, session_id=session_id, limit=limit, after=after)
