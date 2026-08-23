from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.editorial import (
    EditorialCandidateMoment,
    EditorialMomentConflictError,
    EditorialMomentNotFoundError,
    EditorialMomentStorageUnavailableError,
)
from app.contexts.production.event_mode_kernel import KernelStorageUnavailableError
from app.shared.ids import EntityId

router = APIRouter(prefix="/editorial", tags=["editorial"])


class MarkEditorialCandidateMomentCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation_id: UUID
    actor_id: UUID
    confirmed: Literal["confirmed"]
    session_id: UUID
    expected_session_revision: Annotated[int, Field(ge=1)]
    timeline_start_microseconds: Annotated[int, Field(ge=0)]
    timeline_end_microseconds: Annotated[int | None, Field(ge=0)] = None
    note: Annotated[str | None, Field(min_length=1, max_length=500)] = None


class EditorialCandidateMomentResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation_id: str
    candidate_moment_id: str
    session_id: str
    expected_session_revision: int
    timeline_start_microseconds: int
    timeline_end_microseconds: int | None
    session_authoritative_start: AwareDatetime
    session_authoritative_end: AwareDatetime | None
    origin: Literal["declared"]
    epistemic_kind: Literal["declared"]
    source_kind: Literal["producer_declaration"]
    reason_code: Literal["human_mark_moment"]
    review_state: Literal["unreviewed"]
    actor_id: str
    note: str | None
    created_at: datetime
    updated_at: datetime
    location_conflict: bool
    location_conflict_reason: str | None
    revision: int


class EditorialCandidateMomentListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str
    candidate_count: int
    latest_candidate_activity_at: datetime | None
    generation_state: Literal["healthy", "unknown"]
    location_conflict_count: int
    items: tuple[EditorialCandidateMomentResponse, ...]
    items_truncated: bool
    limit: int


def _components(request: Request) -> KernelComponents:
    components = getattr(request.app.state, "kernel", None)
    if not isinstance(components, KernelComponents):
        raise HTTPException(status_code=503, detail="kernel_runtime_unavailable")
    if components.editorial_moments is None:
        raise HTTPException(
            status_code=503, detail="editorial_moment_service_unavailable"
        )
    return components


def _response(moment: EditorialCandidateMoment) -> EditorialCandidateMomentResponse:
    return EditorialCandidateMomentResponse(
        operation_id=moment.operation_id.value,
        candidate_moment_id=moment.id.value,
        session_id=moment.session_id.value,
        expected_session_revision=moment.expected_session_revision,
        timeline_start_microseconds=moment.timeline_start_microseconds,
        timeline_end_microseconds=moment.timeline_end_microseconds,
        session_authoritative_start=moment.session_authoritative_start,
        session_authoritative_end=moment.session_authoritative_end,
        origin="declared",
        epistemic_kind="declared",
        source_kind="producer_declaration",
        reason_code="human_mark_moment",
        review_state="unreviewed",
        actor_id=moment.actor_id.value,
        note=moment.note,
        created_at=moment.created_at,
        updated_at=moment.updated_at or moment.declared_at,
        location_conflict=moment.location_conflict,
        location_conflict_reason=(
            None
            if moment.location_conflict_reason is None
            else moment.location_conflict_reason.value
        ),
        revision=moment.revision,
    )


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, EditorialMomentNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, EditorialMomentConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(
        exc,
        (EditorialMomentStorageUnavailableError, KernelStorageUnavailableError),
    ):
        return HTTPException(status_code=503, detail="postgresql_unavailable")
    return HTTPException(status_code=422, detail=str(exc))


@router.post("/moments/mark", response_model=EditorialCandidateMomentResponse)
def mark_editorial_candidate_moment(
    command: MarkEditorialCandidateMomentCommand,
    request: Request,
) -> EditorialCandidateMomentResponse:
    components = _components(request)
    assert components.editorial_moments is not None
    try:
        return _response(
            components.editorial_moments.mark_moment(
                operation_id=EntityId(str(command.operation_id)),
                session_id=EntityId(str(command.session_id)),
                expected_session_revision=command.expected_session_revision,
                timeline_start_microseconds=command.timeline_start_microseconds,
                timeline_end_microseconds=command.timeline_end_microseconds,
                actor_id=EntityId(str(command.actor_id)),
                note=command.note,
            )
        )
    except (
        EditorialMomentConflictError,
        EditorialMomentNotFoundError,
        EditorialMomentStorageUnavailableError,
        ValueError,
    ) as exc:
        raise _translate_error(exc) from exc


@router.get(
    "/sessions/{session_id}/moments",
    response_model=EditorialCandidateMomentListResponse,
)
def list_editorial_candidate_moments(
    session_id: UUID,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> EditorialCandidateMomentListResponse:
    components = _components(request)
    assert components.editorial_moments is not None
    parsed_session_id = EntityId(str(session_id))
    try:
        if components.repository.get_session(parsed_session_id) is None:
            raise EditorialMomentNotFoundError("session_not_found")
        projection = components.editorial_moments.projection_for_session(
            parsed_session_id
        )
        candidates = components.editorial_moments.list_for_session(
            parsed_session_id, limit=limit + 1
        )
        return EditorialCandidateMomentListResponse(
            session_id=parsed_session_id.value,
            candidate_count=projection.candidate_count,
            latest_candidate_activity_at=projection.latest_candidate_activity_at,
            generation_state=projection.generation_state.value,
            location_conflict_count=projection.location_conflict_count,
            items=tuple(_response(item) for item in candidates[:limit]),
            items_truncated=len(candidates) > limit,
            limit=limit,
        )
    except (
        EditorialMomentNotFoundError,
        EditorialMomentStorageUnavailableError,
        KernelStorageUnavailableError,
        ValueError,
    ) as exc:
        raise _translate_error(exc) from exc


__all__ = [
    "EditorialCandidateMomentListResponse",
    "EditorialCandidateMomentResponse",
    "MarkEditorialCandidateMomentCommand",
    "router",
]
