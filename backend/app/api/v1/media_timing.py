"""Authenticated, bounded inspection commands and advisory summaries."""
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.production.media_timing_evidence import MediaTimingEvidenceStorageUnavailableError
from app.contexts.production.media_timing_evidence.enqueue import MediaTimingEnqueue
from app.contexts.work_execution import (
    DurableOperation,
    MediaTimingOperationInput,
    WorkExecutionConflictError,
    WorkExecutionStorageUnavailableError,
)
from app.infrastructure.postgres.media_timing_work_repository import (
    PostgresMediaTimingWorkRepository,
)
from app.shared.ids import EntityId

router = APIRouter(prefix="/media-timing", tags=["media timing"])


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


def _repository(request: Request) -> PostgresMediaTimingWorkRepository:
    return PostgresMediaTimingWorkRepository(_components(request).configuration.postgres_dsn)


def _operation(value: DurableOperation[MediaTimingOperationInput]) -> dict[str, object]:
    return {"operation_id": value.id.value, "asset_id": value.input.asset_id.value,
            "state": value.status.value, "attempt_count": value.attempt_count,
            "reason_code": value.last_reason_code,
            "profile_id": value.input.inspection_profile_id,
            "profile_version": value.input.inspection_profile_version,
            "evidence_id": None if value.terminal_result_media_timing_evidence_id is None
            else value.terminal_result_media_timing_evidence_id.value}


@router.post("/events/{event_id}/requests")
def enqueue_existing(event_id: UUID, body: EnqueueBody, request: Request) -> dict[str, object]:
    components = _components(request)
    local = components.configuration.deployment.local_media_timing
    if local is None or not local.enabled:
        raise HTTPException(503, "local_media_timing_not_enabled")
    repository = _repository(request)
    try:
        items, cursor = MediaTimingEnqueue(repository,
            components.configuration.deployment.deployment_id,
            components.kernel.clock).enqueue_existing(
                repository, EntityId(str(event_id)), actor_id=EntityId(str(body.actor_id)),
                authority_kind=body.authority_kind, confirmed=body.confirmed == "confirmed",
                limit=body.limit, after=None if body.after is None else EntityId(str(body.after)),
            )
    except WorkExecutionConflictError:
        raise HTTPException(409, "media_timing_enqueue_conflict") from None
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


@router.get("/assets/{asset_id}/latest")
def latest(asset_id: UUID, request: Request) -> dict[str, object]:
    components = _components(request)
    identifier = EntityId(str(asset_id))
    if components.repository.get_asset(identifier) is None:
        raise HTTPException(404, "completed_media_asset_not_found")
    repository = components.media_timing_evidence_repository
    if repository is None:
        raise HTTPException(503, "media_timing_evidence_not_composed")
    try:
        evidence = repository.get_active(identifier)
    except MediaTimingEvidenceStorageUnavailableError:
        raise HTTPException(503, "media_timing_evidence_storage_unavailable") from None
    if evidence is None:
        return {"asset_id": identifier.value, "evidence": None}
    result = evidence.result
    interval = result.derivations[-1] if result.derivations else None
    limitations = tuple(sorted(set(result.limitations + result.qualification.limitations)))
    return {"asset_id": identifier.value, "evidence": {
        "evidence_id": evidence.id.value, "revision": evidence.revision,
        "qualification": result.qualification.status.value,
        "limitations": limitations[:100], "limitations_truncated": len(limitations) > 100,
        "candidate_interval": None if interval is None else {
            "started_at": interval.candidate_started_at.isoformat(),
            "ended_at": interval.candidate_ended_at.isoformat(),
        }, "authorized_use": "advisory_only",
    }}
