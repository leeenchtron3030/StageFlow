"""Authenticated Event-scoped advisory runs and explicit human decisions."""
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.editorial.repository import EditorialMomentNotFoundError
from app.contexts.production.event_mode_kernel.repository import (
    KernelConflictError,
    KernelNotFoundError,
    KernelStorageUnavailableError,
)
from app.contexts.production.session_suggestions.contracts import (
    Reference,
    SessionSuggestion,
    SuggestionConflictError,
    SuggestionDecision,
    SuggestionNotFoundError,
    SuggestionStatus,
    SuggestionStorageUnavailableError,
)
from app.contexts.production.session_suggestions.serialization import candidate_document
from app.contexts.production.session_suggestions.service import SessionSuggestionService
from app.infrastructure.postgres.session_suggestion_repository import PostgresSuggestionRepository
from app.shared.ids import EntityId

router = APIRouter(prefix="/session-suggestions/events/{event_id}", tags=["session suggestions"])


class HumanBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    actor_id: UUID
    authority_kind: Literal["human"] = "human"


class CueList(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: UUID
    version: int = Field(ge=1, le=2_147_483_647)

    def reference(self) -> Reference:
        return Reference(EntityId(str(self.id)), self.version)


class RunBody(HumanBody):
    start_cue_list: CueList | None = None
    end_cue_list: CueList | None = None


class ConfirmBody(HumanBody):
    command_id: UUID
    start: AwareDatetime | None = None
    end: AwareDatetime | None = None


class RejectBody(HumanBody):
    command_id: UUID
    reason: str = Field(min_length=1, max_length=500)


def service(request: Request) -> SessionSuggestionService:
    components = getattr(request.app.state, "kernel", None)
    if not isinstance(components, KernelComponents):
        raise HTTPException(503, "kernel_not_configured")
    repository = PostgresSuggestionRepository(components.configuration.postgres_dsn)
    return SessionSuggestionService(repository, components.kernel.clock)


Service = Annotated[SessionSuggestionService, Depends(service)]


def _call[T](action: Callable[[], T]) -> T:
    try:
        return action()
    except (SuggestionNotFoundError, KernelNotFoundError, EditorialMomentNotFoundError) as exc:
        raise HTTPException(404, str(exc)) from None
    except (SuggestionConflictError, KernelConflictError) as exc:
        raise HTTPException(409, str(exc)) from None
    except (SuggestionStorageUnavailableError, KernelStorageUnavailableError):
        raise HTTPException(503, "postgresql_unavailable") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


def _suggestion(value: SessionSuggestion, status: SuggestionStatus) -> dict[str, object]:
    return {"suggestion_id": value.id.value, "run_id": value.run_id.value,
            "event_id": value.event_id.value, "stage_id": value.stage_id.value,
            "policy_id": value.policy_id, "policy_version": value.policy_version,
            "status": status.value, "authorized_use": "advisory_only",
            **candidate_document(value.candidate)}


def _decision(value: SuggestionDecision) -> dict[str, object]:
    return {"command_id": value.command_id.value, "suggestion_id": value.suggestion_id.value,
            "actor_id": value.actor_id.value, "decided_at": value.decided_at,
            "kind": value.kind.value, "reason": value.reason,
            "session_id": None if value.session_id is None else value.session_id.value,
            "used_start": None if value.used_span is None else value.used_span.start,
            "used_end": None if value.used_span is None else value.used_span.end}


@router.post("/stages/{stage_id}/runs")
def run(event_id: UUID, stage_id: UUID, body: RunBody, svc: Service) -> dict[str, object]:
    result = _call(lambda: svc.run(
        event_id=EntityId(str(event_id)), stage_id=EntityId(str(stage_id)),
        actor_id=EntityId(str(body.actor_id)), authority_kind=body.authority_kind,
        start_cue_list=None if body.start_cue_list is None else body.start_cue_list.reference(),
        end_cue_list=None if body.end_cue_list is None else body.end_cue_list.reference(),
    ))
    return {"run_id": result.id.value, "event_id": result.event_id.value,
            "stage_id": result.stage_id.value, "input_digest": result.input_digest,
            "actor_id": result.actor_id.value, "created_at": result.created_at,
            "policy": asdict(result.policy), "skips": asdict(result.skips)}


@router.get("/stages/{stage_id}/suggestions")
def page(event_id: UUID, stage_id: UUID, svc: Service,
         status: SuggestionStatus = SuggestionStatus.OPEN,
         limit: Annotated[int, Query(ge=1, le=100)] = 50,
         after: UUID | None = None) -> dict[str, object]:
    values, cursor = _call(lambda: svc.page(EntityId(str(event_id)), EntityId(str(stage_id)),
                                          status=status, limit=limit,
                                          after=None if after is None else EntityId(str(after))))
    return {"items": [_suggestion(x, status) for x in values], "limit": limit,
            "next_after": None if cursor is None else cursor.value}


@router.get("/suggestions/{suggestion_id}")
def read(event_id: UUID, suggestion_id: UUID, svc: Service) -> dict[str, object]:
    value, status = _call(lambda: svc.read(EntityId(str(event_id)), EntityId(str(suggestion_id))))
    return _suggestion(value, status)


@router.post("/suggestions/{suggestion_id}/confirm")
def confirm(event_id: UUID, suggestion_id: UUID, body: ConfirmBody,
            svc: Service) -> dict[str, object]:
    start: datetime | None = body.start
    end: datetime | None = body.end
    return _decision(_call(lambda: svc.confirm(
        event_id=EntityId(str(event_id)), suggestion_id=EntityId(str(suggestion_id)),
        command_id=EntityId(str(body.command_id)), actor_id=EntityId(str(body.actor_id)),
        start=start, end=end, authority_kind=body.authority_kind,
    )))


@router.post("/suggestions/{suggestion_id}/reject")
def reject(event_id: UUID, suggestion_id: UUID, body: RejectBody,
           svc: Service) -> dict[str, object]:
    return _decision(_call(lambda: svc.reject(
        event_id=EntityId(str(event_id)), suggestion_id=EntityId(str(suggestion_id)),
        command_id=EntityId(str(body.command_id)), actor_id=EntityId(str(body.actor_id)),
        reason=body.reason, authority_kind=body.authority_kind,
    )))
