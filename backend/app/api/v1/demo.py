from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.api.v1.response_models import (
    ImmutableIntMapping,
    ProgramChangeResponse,
    program_change_responses,
)
from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.editorial import (
    EditorialCandidateMoment,
    EditorialMomentConflictError,
    EditorialMomentNotFoundError,
    EditorialMomentStorageUnavailableError,
)
from app.contexts.events import ProgramExpectationReconciliation
from app.contexts.production.event_mode_kernel import (
    KernelConflictError,
    KernelNotFoundError,
    KernelStorageUnavailableError,
)
from app.contexts.production.event_mode_kernel.contracts import (
    Session,
    StartSessionRequest,
)
from app.contexts.transcription_evidence import TranscriptEvidenceRevision
from app.contexts.work_execution.repository import WorkExecutionStorageUnavailableError
from app.core.config.deployment import RuntimeProfile
from app.demo.service import (
    DemoApplication,
    ProcessTranscriptionRequest,
    ProcessTranscriptionResult,
)
from app.infrastructure.devcon import DevconReadError
from app.infrastructure.postgres import PostgresWorkExecutionRepository
from app.shared.ids import EntityId

router = APIRouter(prefix="/demo", tags=["demo"])
type EditorialReviewStateValue = Literal[
    "unreviewed",
    "approved",
    "rejected",
    "revision_requested",
    "deferred",
]
_TRANSCRIPT_ASSET_LIMIT = 4
_TRANSCRIPT_SEGMENT_LIMIT = 50
_TRANSCRIPT_WORD_LIMIT = 50
_OPERATION_LIMIT = 100



class ProgramRefreshResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    observed: int
    added: int
    changed: int
    unchanged: int
    withdrawn: int
    restored: int
    synchronized_at: datetime
    current_expectation_count: int
    changes: tuple[ProgramChangeResponse, ...]
    changes_truncated: bool
    evidence_kind: Literal["external"] = "external"
    authority_notice: str = "Program evidence only; no Session authority changed."

class ConfirmedCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation_id: UUID
    actor_id: UUID
    confirmed: Literal["confirmed"]


class StartSessionCommand(ConfirmedCommand):
    stage_id: UUID
    program_expectation_id: UUID | None = None
    title: Annotated[str | None, Field(min_length=1, max_length=200)] = None
    authoritative_start: AwareDatetime


class EndPresentationCommand(ConfirmedCommand):
    session_id: UUID
    boundary_at: AwareDatetime
    reason: Annotated[str, Field(min_length=1, max_length=200)]


class ProcessTranscriptionCommand(ConfirmedCommand):
    session_id: UUID


class PackageReadyCommand(ConfirmedCommand):
    session_id: UUID
    reason: Annotated[str, Field(min_length=1, max_length=200)]


class ApprovePackageCommand(ConfirmedCommand):
    session_id: UUID
    package_revision: Annotated[int, Field(ge=1)]


class MarkMomentCommand(ConfirmedCommand):
    session_id: UUID
    expected_session_revision: Annotated[int, Field(ge=1)]
    timeline_start_microseconds: Annotated[int, Field(ge=0)]
    timeline_end_microseconds: Annotated[int | None, Field(ge=0)] = None
    note: Annotated[str | None, Field(min_length=1, max_length=500)] = None


class SessionCommandResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation_id: str
    session_id: str
    activity_state: str
    package_state: str
    package_revision: int
    revision: int
    authoritative_start: datetime
    authoritative_end: datetime | None


class ProcessTranscriptionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation_id: str
    candidates_seen: int
    assets_registered: int
    transcription_operation_ids: tuple[str, ...]
    operation_states: tuple[str, ...]


class EditorialMomentResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation_id: str
    candidate_moment_id: str
    session_id: str
    expected_session_revision: int
    timeline_start_microseconds: int
    timeline_end_microseconds: int | None
    origin: Literal["declared"]
    epistemic_kind: Literal["declared"]
    reason_code: Literal["human_mark_moment"]
    source_kind: Literal["producer_declaration"]
    review_state: EditorialReviewStateValue
    actor_id: str
    note: str | None
    declared_at: datetime
    created_at: datetime
    updated_at: datetime
    location_conflict: bool
    location_conflict_reason: str | None
    revision: int


class OperationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation_id: str
    asset_id: str
    status: str
    attempt_count: int
    max_attempts: int
    last_reason_code: str | None
    created_at: datetime
    updated_at: datetime


class TranscriptWordResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    word_id: str
    ordinal: int
    text: str
    asset_start_microseconds: int
    asset_end_microseconds: int
    confidence: float | None
    confidence_semantics: str | None


class TranscriptSegmentResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    segment_id: str
    ordinal: int
    text: str
    asset_start_microseconds: int
    asset_end_microseconds: int
    speaker_label: str | None
    speaker_evidence_kind: str | None
    confidence: float | None
    confidence_semantics: str | None
    limitations: tuple[str, ...]
    words: tuple[TranscriptWordResponse, ...]
    words_truncated: bool
    word_limit: int = _TRANSCRIPT_WORD_LIMIT


class TranscriptEvidenceResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str
    operation_id: str
    asset_id: str
    revision: int
    status: str
    language: str | None
    provider_id: str
    provider_version: str
    model_id: str
    model_version: str
    produced_at: datetime
    applied_at: datetime
    limitations: tuple[str, ...]
    partial_reason: str | None
    failure_reason: str | None
    segments: tuple[TranscriptSegmentResponse, ...]
    segments_truncated: bool
    segment_limit: int = _TRANSCRIPT_SEGMENT_LIMIT


class WorkProjectionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    counts: ImmutableIntMapping
    oldest_eligible_at: datetime | None
    active_lease_count: int
    attention_codes: tuple[str, ...]


class SessionWorkspaceResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str
    activity_state: str
    package_state: str
    package_revision: int
    revision: int
    label: Literal["Transcription Evidence"] = "Transcription Evidence"
    authority_notice: str = "Evidence only; not authoritative Session Transcript truth."
    work: WorkProjectionResponse
    operations: tuple[OperationResponse, ...]
    operations_truncated: bool
    operation_limit: int = _OPERATION_LIMIT
    transcript_evidence: tuple[TranscriptEvidenceResponse, ...]
    transcript_assets_truncated: bool
    transcript_asset_limit: int = _TRANSCRIPT_ASSET_LIMIT
    moments: tuple[EditorialMomentResponse, ...]


def _components(request: Request) -> KernelComponents:
    components = getattr(request.app.state, "kernel", None)
    if not isinstance(components, KernelComponents):
        raise HTTPException(status_code=503, detail="demo_runtime_unavailable")
    if (
        components.configuration.deployment.runtime_profile
        is not RuntimeProfile.DEMO_SINGLE_STAGE
    ):
        raise HTTPException(status_code=404, detail="demo_profile_not_active")
    return components


def _session_response(operation_id: UUID, session: Session) -> SessionCommandResponse:
    return SessionCommandResponse(
        operation_id=str(operation_id),
        session_id=session.id.value,
        activity_state=session.activity_state.value,
        package_state=session.package_state.value,
        package_revision=session.package_revision,
        revision=session.revision,
        authoritative_start=session.authoritative_start,
        authoritative_end=session.authoritative_end,
    )


def _moment_response(moment: EditorialCandidateMoment) -> EditorialMomentResponse:
    return EditorialMomentResponse(
        operation_id=moment.operation_id.value,
        candidate_moment_id=moment.id.value,
        session_id=moment.session_id.value,
        expected_session_revision=moment.expected_session_revision,
        timeline_start_microseconds=moment.timeline_start_microseconds,
        timeline_end_microseconds=moment.timeline_end_microseconds,
        origin="declared",
        epistemic_kind="declared",
        reason_code="human_mark_moment",
        source_kind="producer_declaration",
        review_state=moment.review_state.value,
        actor_id=moment.actor_id.value,
        note=moment.note,
        declared_at=moment.declared_at,
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
    if isinstance(exc, (KernelNotFoundError, EditorialMomentNotFoundError)):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (KernelConflictError, EditorialMomentConflictError)):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(
        exc,
        (KernelStorageUnavailableError, EditorialMomentStorageUnavailableError),
    ):
        return HTTPException(status_code=503, detail="postgresql_unavailable")
    return HTTPException(status_code=422, detail=str(exc))


def _program_refresh_response(
    result: ProgramExpectationReconciliation,
) -> ProgramRefreshResponse:
    return ProgramRefreshResponse(
        provider=result.provider,
        observed=result.observed,
        added=result.added,
        changed=result.changed,
        unchanged=result.unchanged,
        withdrawn=result.withdrawn,
        restored=result.restored,
        synchronized_at=result.synchronized_at,
        current_expectation_count=len(result.expectations),
        changes=program_change_responses(result.changes),
        changes_truncated=result.changes_truncated,
    )


@router.post("/program/refresh", response_model=ProgramRefreshResponse)
def refresh_program(request: Request, response: Response) -> ProgramRefreshResponse:
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    components = _components(request)
    try:
        return _program_refresh_response(components.sync_devcon_program())
    except (DevconReadError, KernelStorageUnavailableError) as exc:
        raise HTTPException(
            status_code=503,
            detail="program_refresh_failed_using_last_successful_snapshot",
        ) from exc
    except (KernelNotFoundError, KernelConflictError) as exc:
        raise _translate_error(exc) from exc

@router.post("/sessions/start", response_model=SessionCommandResponse)
def start_session(command: StartSessionCommand, request: Request) -> SessionCommandResponse:
    components = _components(request)
    event = components.repository.get_event_by_key(components.event_key)
    if event is None:
        raise HTTPException(status_code=409, detail="explicit_event_stage_bootstrap_required")
    try:
        session = components.kernel.start_session(
            StartSessionRequest(
                operation_id=EntityId(str(command.operation_id)),
                event_id=event.id,
                stage_id=EntityId(str(command.stage_id)),
                actor_id=EntityId(str(command.actor_id)),
                authoritative_start=command.authoritative_start,
                requested_at=components.kernel.clock.now(),
                program_expectation_id=(
                    None
                    if command.program_expectation_id is None
                    else EntityId(str(command.program_expectation_id))
                ),
                title=command.title,
            )
        )
        return _session_response(command.operation_id, session)
    except (KernelNotFoundError, KernelConflictError, KernelStorageUnavailableError) as exc:
        raise _translate_error(exc) from exc


@router.post("/sessions/end-presentation", response_model=SessionCommandResponse)
def end_presentation(
    command: EndPresentationCommand, request: Request
) -> SessionCommandResponse:
    components = _components(request)
    try:
        session = components.correct_session_boundary(
            operation_id=EntityId(str(command.operation_id)),
            session_id=EntityId(str(command.session_id)),
            boundary_kind="end",
            boundary_at=command.boundary_at,
            actor_id=EntityId(str(command.actor_id)),
            reason=command.reason,
        )
        return _session_response(command.operation_id, session)
    except (
        KernelNotFoundError,
        KernelConflictError,
        KernelStorageUnavailableError,
        EditorialMomentStorageUnavailableError,
    ) as exc:
        raise _translate_error(exc) from exc


@router.post("/sessions/process-transcription", response_model=ProcessTranscriptionResponse)
def process_transcription(
    command: ProcessTranscriptionCommand, request: Request
) -> ProcessTranscriptionResponse:
    components = _components(request)
    try:
        result: ProcessTranscriptionResult = DemoApplication.from_components(
            components
        ).process_transcription(
            ProcessTranscriptionRequest(
                operation_id=EntityId(str(command.operation_id)),
                session_id=EntityId(str(command.session_id)),
                requested_at=components.kernel.clock.now(),
            )
        )
        return ProcessTranscriptionResponse(
            operation_id=result.command_operation_id.value,
            candidates_seen=result.candidates_seen,
            assets_registered=result.assets_registered,
            transcription_operation_ids=tuple(
                item.id.value for item in result.operations
            ),
            operation_states=tuple(item.status.value for item in result.operations),
        )
    except (KernelNotFoundError, KernelConflictError, KernelStorageUnavailableError) as exc:
        raise _translate_error(exc) from exc


@router.post("/sessions/package-ready", response_model=SessionCommandResponse)
def package_ready(
    command: PackageReadyCommand, request: Request
) -> SessionCommandResponse:
    components = _components(request)
    try:
        session = components.kernel.declare_package_ready(
            operation_id=EntityId(str(command.operation_id)),
            session_id=EntityId(str(command.session_id)),
            actor_id=EntityId(str(command.actor_id)),
            reason=command.reason,
        )
        return _session_response(command.operation_id, session)
    except (KernelNotFoundError, KernelConflictError, KernelStorageUnavailableError) as exc:
        raise _translate_error(exc) from exc


@router.post("/sessions/approve-package", response_model=SessionCommandResponse)
def approve_package(
    command: ApprovePackageCommand, request: Request
) -> SessionCommandResponse:
    components = _components(request)
    try:
        session = components.kernel.complete_package(
            operation_id=EntityId(str(command.operation_id)),
            session_id=EntityId(str(command.session_id)),
            actor_id=EntityId(str(command.actor_id)),
            approved=True,
            reason=(
                "demo_operator_approved_package_revision_"
                f"{command.package_revision}"
            ),
            expected_package_revision=command.package_revision,
        )
        return _session_response(command.operation_id, session)
    except (KernelNotFoundError, KernelConflictError) as exc:
        raise _translate_error(exc) from exc


@router.post("/moments/mark", response_model=EditorialMomentResponse)
def mark_moment(command: MarkMomentCommand, request: Request) -> EditorialMomentResponse:
    components = _components(request)
    if components.editorial_moments is None:
        raise HTTPException(status_code=503, detail="editorial_moment_service_unavailable")
    try:
        moment = components.editorial_moments.mark_moment(
            operation_id=EntityId(str(command.operation_id)),
            session_id=EntityId(str(command.session_id)),
            expected_session_revision=command.expected_session_revision,
            timeline_start_microseconds=command.timeline_start_microseconds,
            timeline_end_microseconds=command.timeline_end_microseconds,
            actor_id=EntityId(str(command.actor_id)),
            note=command.note,
        )
        return _moment_response(moment)
    except (
        EditorialMomentNotFoundError,
        EditorialMomentConflictError,
        EditorialMomentStorageUnavailableError,
        ValueError,
    ) as exc:
        raise _translate_error(exc) from exc


def _transcript_response(
    evidence: TranscriptEvidenceRevision,
) -> TranscriptEvidenceResponse:
    return TranscriptEvidenceResponse(
        evidence_id=evidence.id.value,
        operation_id=evidence.operation_id.value,
        asset_id=evidence.asset_id.value,
        revision=evidence.revision,
        status=evidence.result.status.value,
        language=evidence.result.language,
        provider_id=evidence.result.provenance.provider_id,
        provider_version=evidence.result.provenance.provider_version,
        model_id=evidence.result.provenance.model_id,
        model_version=evidence.result.provenance.model_version,
        produced_at=evidence.result.provenance.produced_at,
        applied_at=evidence.applied_at,
        limitations=tuple(evidence.result.limitations),
        partial_reason=evidence.result.partial_reason,
        failure_reason=evidence.result.failure_reason,
        segments=tuple(
            TranscriptSegmentResponse(
                segment_id=segment.id.value,
                ordinal=segment.ordinal,
                text=segment.text,
                asset_start_microseconds=segment.asset_start_microseconds,
                asset_end_microseconds=segment.asset_end_microseconds,
                speaker_label=segment.speaker_label,
                speaker_evidence_kind=(
                    None
                    if segment.speaker_evidence_kind is None
                    else segment.speaker_evidence_kind.value
                ),
                confidence=segment.confidence,
                confidence_semantics=segment.confidence_semantics,
                limitations=tuple(segment.limitations),
                words=tuple(
                    TranscriptWordResponse(
                        word_id=word.id.value,
                        ordinal=word.ordinal,
                        text=word.text,
                        asset_start_microseconds=word.asset_start_microseconds,
                        asset_end_microseconds=word.asset_end_microseconds,
                        confidence=word.confidence,
                        confidence_semantics=word.confidence_semantics,
                    )
                    for word in segment.words[:_TRANSCRIPT_WORD_LIMIT]
                ),
                words_truncated=len(segment.words) > _TRANSCRIPT_WORD_LIMIT,
            )
            for segment in evidence.result.segments[:_TRANSCRIPT_SEGMENT_LIMIT]
        ),
        segments_truncated=(
            len(evidence.result.segments) > _TRANSCRIPT_SEGMENT_LIMIT
        ),
    )


@router.get(
    "/sessions/{session_id}/workspace",
    response_model=SessionWorkspaceResponse,
)
def session_workspace(
    session_id: UUID,
    request: Request,
    response: Response,
) -> SessionWorkspaceResponse:
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    components = _components(request)
    event = components.repository.get_event_by_key(components.event_key)
    if event is None:
        raise HTTPException(status_code=404, detail="event_not_found")
    session_identifier = EntityId(str(session_id))
    session = components.repository.get_session(session_identifier)
    if session is None or session.event_id != event.id:
        raise HTTPException(status_code=404, detail="session_not_found")
    work_repository = PostgresWorkExecutionRepository(
        components.configuration.postgres_dsn
    )
    try:
        projection = work_repository.status_projection(
            deployment_id=components.configuration.deployment.deployment_id,
            event_id=event.id,
        )
        asset_ids = {
            media.asset_id
            for media in components.repository.list_recent_media(event.id, limit=100)
            if media.session_id == session_identifier and media.asset_id is not None
        }
        event_operations = work_repository.list_operations(
            deployment_id=components.configuration.deployment.deployment_id,
            event_id=event.id,
            limit=_OPERATION_LIMIT,
        )
        operations = tuple(
            operation
            for operation in event_operations
            if operation.input.asset_id in asset_ids
        )
        evidence = tuple(
            item
            for asset_id in sorted(asset_ids, key=lambda item: item.value)[
                :_TRANSCRIPT_ASSET_LIMIT
            ]
            for item in work_repository.list_transcript_evidence_for_asset(
                asset_id, limit=1
            )
        )
        moments = (
            ()
            if components.editorial_moments is None
            else components.editorial_moments.list_for_session(
                session_identifier, limit=100
            )
        )
    except (
        WorkExecutionStorageUnavailableError,
        EditorialMomentStorageUnavailableError,
    ) as exc:
        raise HTTPException(status_code=503, detail="postgresql_unavailable") from exc
    return SessionWorkspaceResponse(
        session_id=session.id.value,
        activity_state=session.activity_state.value,
        package_state=session.package_state.value,
        package_revision=session.package_revision,
        revision=session.revision,
        work=WorkProjectionResponse(
            counts={item.status.value: item.count for item in projection.counts},
            oldest_eligible_at=projection.oldest_eligible_at,
            active_lease_count=projection.active_lease_count,
            attention_codes=tuple(projection.attention_codes),
        ),
        operations=tuple(
            OperationResponse(
                operation_id=operation.id.value,
                asset_id=operation.input.asset_id.value,
                status=operation.status.value,
                attempt_count=operation.attempt_count,
                max_attempts=operation.max_attempts,
                last_reason_code=operation.last_reason_code,
                created_at=operation.created_at,
                updated_at=operation.updated_at,
            )
            for operation in operations
        ),
        operations_truncated=len(event_operations) == _OPERATION_LIMIT,
        transcript_evidence=tuple(_transcript_response(item) for item in evidence),
        transcript_assets_truncated=len(asset_ids) > _TRANSCRIPT_ASSET_LIMIT,
        moments=tuple(_moment_response(moment) for moment in moments),
    )


@router.get(
    "/sessions/{session_id}/moments",
    response_model=tuple[EditorialMomentResponse, ...],
)
def list_moments(session_id: UUID, request: Request) -> tuple[EditorialMomentResponse, ...]:
    components = _components(request)
    if components.editorial_moments is None:
        raise HTTPException(status_code=503, detail="editorial_moment_service_unavailable")
    try:
        return tuple(
            _moment_response(moment)
            for moment in components.editorial_moments.list_for_session(
                EntityId(str(session_id)), limit=100
            )
        )
    except EditorialMomentStorageUnavailableError as exc:
        raise _translate_error(exc) from exc


__all__ = [
    "EditorialMomentResponse",
    "EndPresentationCommand",
    "MarkMomentCommand",
    "OperationResponse",
    "ApprovePackageCommand",
    "PackageReadyCommand",
    "ProcessTranscriptionCommand",
    "ProcessTranscriptionResponse",
    "ProgramRefreshResponse",
    "SessionCommandResponse",
    "SessionWorkspaceResponse",
    "TranscriptEvidenceResponse",
    "StartSessionCommand",
    "router",
]
