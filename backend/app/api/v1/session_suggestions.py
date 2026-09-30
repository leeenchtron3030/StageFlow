"""Authenticated Event-scoped advisory runs and explicit human decisions."""
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.editorial.repository import (
    EditorialMomentConflictError,
    EditorialMomentNotFoundError,
)
from app.contexts.production.event_mode_kernel.repository import (
    KernelConflictError,
    KernelNotFoundError,
    KernelStorageUnavailableError,
)
from app.contexts.production.session_suggestions.contracts import (
    Reference,
    ScheduleOffsetEntry,
    ScheduleOffsetSetting,
    SessionSuggestion,
    SuggestionConflictError,
    SuggestionDecision,
    SuggestionNotFoundError,
    SuggestionRun,
    SuggestionStatus,
    SuggestionStorageUnavailableError,
)
from app.contexts.production.session_suggestions.cue_catalog import BOUNDARY_CUE_CATALOG, CueRole
from app.contexts.production.session_suggestions.cue_composition import (
    CompositionRequest,
    CueListSizeError,
    CustomPhrase,
    PhraseChoice,
    composition_document,
)
from app.contexts.production.session_suggestions.cue_service import BoundaryCueService
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


class OffsetEntryBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    effective_from: AwareDatetime
    offset_seconds: int = Field(strict=True, ge=-7200, le=7200)


class OffsetBody(HumanBody):
    command_id: UUID
    entries: tuple[OffsetEntryBody, ...] = Field(max_length=20)


class PhraseChoiceBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    group_key: str = Field(min_length=1, max_length=100)
    phrase: str = Field(min_length=1, max_length=100)


class CustomPhraseBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    text: str = Field(min_length=1, max_length=100)
    role: Literal["start", "end", "changeover"]


class CompositionBody(HumanBody):
    command_id: UUID
    catalog_version: int = Field(strict=True, ge=1, le=2_147_483_647)
    profile_key: str | None = Field(default=None, min_length=1, max_length=100)
    group_keys: tuple[Annotated[str, Field(min_length=1, max_length=100)], ...] = Field(
        max_length=20)
    include: tuple[PhraseChoiceBody, ...] = Field(default=(), max_length=400)
    exclude: tuple[PhraseChoiceBody, ...] = Field(default=(), max_length=400)
    custom_phrases: tuple[CustomPhraseBody, ...] = Field(default=(), max_length=400)


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
    except (SuggestionConflictError, KernelConflictError, EditorialMomentConflictError) as exc:
        raise HTTPException(409, str(exc)) from None
    except (SuggestionStorageUnavailableError, KernelStorageUnavailableError):
        raise HTTPException(503, "postgresql_unavailable") from None
    except CueListSizeError as exc:
        raise HTTPException(422, {"code": exc.code, "role": exc.role, "count": exc.count}) from None
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
    return _run(result)


@router.get("/stages/{stage_id}/runs/latest")
def latest_run(event_id: UUID, stage_id: UUID, svc: Service) -> dict[str, object]:
    return _run(_call(lambda: svc.latest_run(EntityId(str(event_id)), EntityId(str(stage_id)))))


def _run(result: SuggestionRun) -> dict[str, object]:
    return {"run_id": result.id.value, "event_id": result.event_id.value,
            "stage_id": result.stage_id.value, "input_digest": result.input_digest,
            "actor_id": result.actor_id.value, "created_at": result.created_at,
            "policy": asdict(result.policy), "skips": asdict(result.skips),
            "blocks": [asdict(b) for b in result.blocks],
            "start_cue_list": None if result.start_cue_list is None else {
                "id": result.start_cue_list.id.value, "version": result.start_cue_list.revision},
            "end_cue_list": None if result.end_cue_list is None else {
                "id": result.end_cue_list.id.value, "version": result.end_cue_list.revision},
            "override_setting_version": result.override_setting_version}


@router.get("/boundary-cue-catalog")
def cue_catalog(event_id: UUID) -> dict[str, object]:
    return {**asdict(BOUNDARY_CUE_CATALOG), "digest": BOUNDARY_CUE_CATALOG.digest}


@router.post("/boundary-cues")
def compose_cues(event_id: UUID, body: CompositionBody, svc: Service) -> dict[str, object]:
    return composition_document(_call(lambda: BoundaryCueService(svc.repository, svc.clock).publish(
        event_id=EntityId(str(event_id)), actor_id=EntityId(str(body.actor_id)),
        command_id=EntityId(str(body.command_id)), authority_kind=body.authority_kind,
        request=CompositionRequest(
            body.catalog_version, body.group_keys, body.profile_key,
            tuple(PhraseChoice(c.group_key, c.phrase) for c in body.include),
            tuple(PhraseChoice(c.group_key, c.phrase) for c in body.exclude),
            tuple(CustomPhrase(c.text, CueRole(c.role)) for c in body.custom_phrases)),
    )))


@router.get("/boundary-cues")
def current_cues(event_id: UUID, svc: Service) -> dict[str, object]:
    value = _call(lambda: BoundaryCueService(svc.repository, svc.clock).current(
        EntityId(str(event_id))))
    return {"current": None if value is None else composition_document(value)}


@router.get("/boundary-cues/history")
def cue_history(event_id: UUID, svc: Service,
                after: Annotated[int, Query(ge=0, le=2_147_483_647)] = 0,
                limit: Annotated[int, Query(ge=1, le=100)] = 50) -> dict[str, object]:
    values, cursor = _call(lambda: BoundaryCueService(svc.repository, svc.clock).history(
        EntityId(str(event_id)), after=after, limit=limit))
    return {"items": [composition_document(v) for v in values],
            "limit": limit, "next_after": cursor}


def _offset(value: ScheduleOffsetSetting) -> dict[str, object]:
    return {"event_id": value.event_id.value, "stage_id": value.stage_id.value,
            "version": value.version, "command_id": value.command_id.value,
            "set_by": value.set_by.value, "set_at": value.set_at,
            "entries": [asdict(e) for e in value.entries], "authorized_use": "advisory_only"}


@router.post("/stages/{stage_id}/schedule-offset")
def set_offset(event_id: UUID, stage_id: UUID, body: OffsetBody, svc: Service) -> dict[str, object]:
    return _offset(_call(lambda: svc.set_offset(
        event_id=EntityId(str(event_id)), stage_id=EntityId(str(stage_id)),
        command_id=EntityId(str(body.command_id)), actor_id=EntityId(str(body.actor_id)),
        authority_kind=body.authority_kind,
        entries=tuple(ScheduleOffsetEntry(e.effective_from, e.offset_seconds)
                      for e in body.entries),
    )))


@router.get("/stages/{stage_id}/schedule-offset")
def current_offset(event_id: UUID, stage_id: UUID, svc: Service) -> dict[str, object]:
    value = _call(lambda: svc.current_offset(EntityId(str(event_id)), EntityId(str(stage_id))))
    return {"current": None if value is None else _offset(value)}


@router.get("/stages/{stage_id}/schedule-offset/history")
def offset_history(event_id: UUID, stage_id: UUID, svc: Service,
                   after: Annotated[int, Query(ge=0, le=2_147_483_647)] = 0,
                   limit: Annotated[int, Query(ge=1, le=100)] = 50) -> dict[str, object]:
    values, cursor = _call(lambda: svc.offset_history(
        EntityId(str(event_id)), EntityId(str(stage_id)), after=after, limit=limit))
    return {"items": [_offset(v) for v in values], "limit": limit, "next_after": cursor}


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
