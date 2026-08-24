from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Mapping
from datetime import datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict

from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.production.event_mode_kernel import (
    KernelStorageUnavailableError,
    ProducerWorkQueuePosition,
    ProducerWorkQueueSubject,
)
from app.shared.ids import EntityId

router = APIRouter(prefix="/producer", tags=["producer"])


class ProducerWorkQueueItemResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    item_id: str
    decision_type: Literal[
        "package_ready_for_review",
        "package_correction_required",
        "association_unresolved",
        "association_conflict",
    ]
    subject_kind: Literal["session_package", "media_association"]
    subject_id: str
    subject_revision: int
    event_id: str
    stage_id: str
    session_id: str | None
    priority: int
    reason_codes: tuple[str, ...]
    action_reference: str
    created_at: datetime
    updated_at: datetime


class ProducerWorkQueueResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str
    items: tuple[ProducerWorkQueueItemResponse, ...]
    next_cursor: str | None
    items_truncated: bool
    limit: int


def _encode_cursor(
    position: ProducerWorkQueuePosition,
    *,
    event_id: EntityId,
) -> str:
    payload = json.dumps(
        {
            "v": 1,
            "event_id": event_id.value,
            "priority": position.priority,
            "updated_at": position.updated_at.isoformat(),
            "projection_id": position.projection_id,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(
    cursor: str,
    *,
    event_id: EntityId,
) -> ProducerWorkQueuePosition:
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
        priority = payload["priority"]
        if not isinstance(priority, int) or isinstance(priority, bool):
            raise ValueError("invalid cursor priority")
        return ProducerWorkQueuePosition(
            priority=priority,
            updated_at=datetime.fromisoformat(str(payload["updated_at"])),
            projection_id=str(payload["projection_id"]),
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
            detail="invalid_work_queue_cursor",
        ) from exc


def _response(subject: ProducerWorkQueueSubject) -> ProducerWorkQueueItemResponse:
    return ProducerWorkQueueItemResponse(
        item_id=subject.projection_id,
        decision_type=subject.decision_type.value,
        subject_kind=subject.subject_kind.value,
        subject_id=subject.subject_id.value,
        subject_revision=subject.subject_revision,
        event_id=subject.event_id.value,
        stage_id=subject.stage_id.value,
        session_id=(
            None if subject.session_id is None else subject.session_id.value
        ),
        priority=subject.priority,
        reason_codes=tuple(subject.reason_codes),
        action_reference=subject.action_reference,
        created_at=subject.created_at,
        updated_at=subject.updated_at,
    )


@router.get(
    "/events/{event_id}/work-queue",
    response_model=ProducerWorkQueueResponse,
)
def producer_work_queue(
    event_id: UUID,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(min_length=1, max_length=512)] = None,
) -> ProducerWorkQueueResponse:
    components = getattr(request.app.state, "kernel", None)
    if not isinstance(components, KernelComponents):
        raise HTTPException(status_code=503, detail="kernel_runtime_unavailable")
    parsed_event_id = EntityId(str(event_id))
    after = (
        None
        if cursor is None
        else _decode_cursor(cursor, event_id=parsed_event_id)
    )
    try:
        subjects = components.repository.list_producer_work_queue(
            parsed_event_id,
            after=after,
            limit=limit + 1,
        )
    except KernelStorageUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail="postgresql_unavailable",
        ) from exc
    items = subjects[:limit]
    truncated = len(subjects) > limit
    return ProducerWorkQueueResponse(
        event_id=parsed_event_id.value,
        items=tuple(_response(subject) for subject in items),
        next_cursor=(
            _encode_cursor(items[-1].position, event_id=parsed_event_id)
            if truncated and items
            else None
        ),
        items_truncated=truncated,
        limit=limit,
    )


__all__ = [
    "ProducerWorkQueueItemResponse",
    "ProducerWorkQueueResponse",
    "router",
]
