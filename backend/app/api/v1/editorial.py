from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.editorial import (
    EditorialCandidateMoment,
    EditorialClip,
    EditorialMomentConflictError,
    EditorialMomentNotFoundError,
    EditorialMomentReviewAction,
    EditorialMomentReviewDecision,
    EditorialMomentReviewResult,
    EditorialMomentStorageUnavailableError,
    EditorialReviewQueueItem,
    EditorialReviewQueuePosition,
)
from app.contexts.production.event_mode_kernel import KernelStorageUnavailableError
from app.shared.ids import EntityId

router = APIRouter(prefix="/editorial", tags=["editorial"])

type EditorialReviewActionValue = Literal[
    "approve_and_create_clip",
    "reject",
    "revise_range",
    "defer",
]
type EditorialReviewStateValue = Literal[
    "unreviewed",
    "approved",
    "rejected",
    "revision_requested",
    "deferred",
]


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


class ReviewEditorialMomentCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation_id: UUID
    actor_id: UUID
    confirmed: Literal["confirmed"]
    expected_candidate_revision: Annotated[int, Field(ge=1)]
    action: EditorialReviewActionValue
    reason: Annotated[str, Field(min_length=1, max_length=500)]
    notes: Annotated[str | None, Field(min_length=1, max_length=1000)] = None
    adjusted_timeline_start_microseconds: Annotated[
        int | None, Field(ge=0)
    ] = None
    adjusted_timeline_end_microseconds: Annotated[
        int | None, Field(ge=0)
    ] = None


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
    review_state: EditorialReviewStateValue
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


class EditorialMomentReviewDecisionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    review_decision_id: str
    sequence: int
    operation_id: str
    candidate_moment_id: str
    candidate_revision: int
    actor_id: str
    action: EditorialReviewActionValue
    reason: str
    notes: str | None
    adjusted_timeline_start_microseconds: int | None
    adjusted_timeline_end_microseconds: int | None
    decided_at: AwareDatetime


class EditorialClipResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    clip_id: str
    session_id: str
    candidate_moment_id: str
    candidate_revision: int
    review_decision_id: str
    timeline_start_microseconds: int
    timeline_end_microseconds: int
    created_at: AwareDatetime
    revision: int


class EditorialMomentReviewResultResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision: EditorialMomentReviewDecisionResponse
    clip: EditorialClipResponse | None


class EditorialReviewQueueItemResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str
    stage_id: str
    candidate: EditorialCandidateMomentResponse
    decisions: tuple[EditorialMomentReviewDecisionResponse, ...]
    clips: tuple[EditorialClipResponse, ...]
    history_truncated: bool


class EditorialReviewQueueResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str
    total_candidate_count: int
    pending_candidate_count: int
    oldest_pending_candidate_at: AwareDatetime | None
    oldest_pending_age_seconds: int | None
    measured_at: AwareDatetime
    items: tuple[EditorialReviewQueueItemResponse, ...]
    next_cursor: str | None
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
        review_state=moment.review_state.value,
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


def _decision_response(
    decision: EditorialMomentReviewDecision,
) -> EditorialMomentReviewDecisionResponse:
    adjusted_range = decision.adjusted_range
    return EditorialMomentReviewDecisionResponse(
        review_decision_id=decision.id.value,
        sequence=decision.sequence,
        operation_id=decision.operation_id.value,
        candidate_moment_id=decision.candidate_moment_id.value,
        candidate_revision=decision.candidate_revision,
        actor_id=decision.actor_id.value,
        action=decision.action.value,
        reason=decision.reason,
        notes=decision.notes,
        adjusted_timeline_start_microseconds=(
            None
            if adjusted_range is None
            else adjusted_range.timeline_start_microseconds
        ),
        adjusted_timeline_end_microseconds=(
            None
            if adjusted_range is None
            else adjusted_range.timeline_end_microseconds
        ),
        decided_at=decision.decided_at,
    )


def _clip_response(clip: EditorialClip) -> EditorialClipResponse:
    return EditorialClipResponse(
        clip_id=clip.id.value,
        session_id=clip.session_id.value,
        candidate_moment_id=clip.candidate_moment_id.value,
        candidate_revision=clip.candidate_revision,
        review_decision_id=clip.review_decision_id.value,
        timeline_start_microseconds=(
            clip.approved_range.timeline_start_microseconds
        ),
        timeline_end_microseconds=clip.approved_range.timeline_end_microseconds,
        created_at=clip.created_at,
        revision=clip.revision,
    )


def _review_result_response(
    result: EditorialMomentReviewResult,
) -> EditorialMomentReviewResultResponse:
    return EditorialMomentReviewResultResponse(
        decision=_decision_response(result.decision),
        clip=None if result.clip is None else _clip_response(result.clip),
    )


def _queue_item_response(
    item: EditorialReviewQueueItem,
) -> EditorialReviewQueueItemResponse:
    return EditorialReviewQueueItemResponse(
        event_id=item.event_id.value,
        stage_id=item.stage_id.value,
        candidate=_response(item.candidate),
        decisions=tuple(
            _decision_response(decision) for decision in item.decisions
        ),
        clips=tuple(_clip_response(clip) for clip in item.clips),
        history_truncated=item.history_truncated,
    )


def _encode_review_queue_cursor(
    position: EditorialReviewQueuePosition,
    *,
    event_id: EntityId,
) -> str:
    payload = json.dumps(
        {
            "v": 1,
            "event_id": event_id.value,
            "review_priority": position.review_priority,
            "created_at": position.created_at.isoformat(),
            "candidate_moment_id": position.candidate_moment_id.value,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_review_queue_cursor(
    cursor: str,
    *,
    event_id: EntityId,
) -> EditorialReviewQueuePosition:
    try:
        padding = "=" * (-len(cursor) % 4)
        decoded: object = json.loads(
            base64.urlsafe_b64decode((cursor + padding).encode("ascii"))
        )
        if not isinstance(decoded, Mapping):
            raise ValueError("invalid cursor document")
        payload = cast(Mapping[str, object], decoded)
        if payload.get("v") != 1:
            raise ValueError("unsupported cursor")
        if payload.get("event_id") != event_id.value:
            raise ValueError("cursor event scope mismatch")
        review_priority = payload["review_priority"]
        if not isinstance(review_priority, int) or isinstance(
            review_priority, bool
        ):
            raise ValueError("invalid cursor review priority")
        return EditorialReviewQueuePosition(
            review_priority=review_priority,
            created_at=datetime.fromisoformat(str(payload["created_at"])),
            candidate_moment_id=EntityId(str(payload["candidate_moment_id"])),
        )
    except (
        binascii.Error,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        UnicodeError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=422,
            detail="invalid_editorial_review_queue_cursor",
        ) from exc


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


@router.post(
    "/moments/{candidate_moment_id}/reviews",
    response_model=EditorialMomentReviewResultResponse,
)
def review_editorial_candidate_moment(
    candidate_moment_id: UUID,
    command: ReviewEditorialMomentCommand,
    request: Request,
) -> EditorialMomentReviewResultResponse:
    components = _components(request)
    assert components.editorial_moments is not None
    try:
        result = components.editorial_moments.review_moment(
            operation_id=EntityId(str(command.operation_id)),
            candidate_moment_id=EntityId(str(candidate_moment_id)),
            expected_candidate_revision=command.expected_candidate_revision,
            actor_id=EntityId(str(command.actor_id)),
            action=EditorialMomentReviewAction(command.action),
            reason=command.reason,
            notes=command.notes,
            adjusted_timeline_start_microseconds=(
                command.adjusted_timeline_start_microseconds
            ),
            adjusted_timeline_end_microseconds=(
                command.adjusted_timeline_end_microseconds
            ),
        )
        return _review_result_response(result)
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


@router.get(
    "/events/{event_id}/review-queue",
    response_model=EditorialReviewQueueResponse,
)
def editorial_review_queue(
    event_id: UUID,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(min_length=1, max_length=512)] = None,
) -> EditorialReviewQueueResponse:
    components = _components(request)
    assert components.editorial_moments is not None
    parsed_event_id = EntityId(str(event_id))
    after = (
        None
        if cursor is None
        else _decode_review_queue_cursor(
            cursor,
            event_id=parsed_event_id,
        )
    )
    try:
        page = components.editorial_moments.list_review_queue(
            parsed_event_id,
            after=after,
            limit=limit + 1,
        )
    except (
        EditorialMomentStorageUnavailableError,
        ValueError,
    ) as exc:
        raise _translate_error(exc) from exc
    items = page.items[:limit]
    truncated = len(page.items) > limit
    measured_at = components.kernel.clock.now().astimezone(UTC)
    oldest_pending_age_seconds = (
        None
        if page.oldest_pending_candidate_at is None
        else max(
            0,
            int(
                (
                    measured_at - page.oldest_pending_candidate_at
                ).total_seconds()
            ),
        )
    )
    return EditorialReviewQueueResponse(
        event_id=parsed_event_id.value,
        total_candidate_count=page.total_candidate_count,
        pending_candidate_count=page.pending_candidate_count,
        oldest_pending_candidate_at=page.oldest_pending_candidate_at,
        oldest_pending_age_seconds=oldest_pending_age_seconds,
        measured_at=measured_at,
        items=tuple(_queue_item_response(item) for item in items),
        next_cursor=(
            _encode_review_queue_cursor(
                items[-1].position,
                event_id=parsed_event_id,
            )
            if truncated and items
            else None
        ),
        items_truncated=truncated,
        limit=limit,
    )


__all__ = [
    "EditorialClipResponse",
    "EditorialCandidateMomentListResponse",
    "EditorialCandidateMomentResponse",
    "EditorialMomentReviewDecisionResponse",
    "EditorialMomentReviewResultResponse",
    "EditorialReviewQueueItemResponse",
    "EditorialReviewQueueResponse",
    "MarkEditorialCandidateMomentCommand",
    "ReviewEditorialMomentCommand",
    "router",
]
