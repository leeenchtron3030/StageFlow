from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.assembly.contracts import (
    MAX_INTEGER,
    ApprovalAction,
    ApprovalState,
    CompletedMediaAssetContent,
    ExternalContent,
    PackagingAsset,
    PackagingAssetApprovalDecision,
    PackagingAssetRevision,
    PackagingAssetRole,
    RevisionContent,
)
from app.contexts.assembly.repository import (
    PackagingAssetConflictError,
    PackagingAssetNotFoundError,
    PackagingAssetStorageUnavailableError,
)
from app.contexts.assembly.service import PackagingAssetService
from app.shared.ids import EntityId

router = APIRouter(prefix="/assembly", tags=["assembly"])


class StrictModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class HumanCommand(StrictModel):
    operation_id: UUID
    actor_id: UUID
    confirmed: Literal["confirmed"]


class RegisterCommand(HumanCommand):
    event_id: UUID
    stage_id: UUID | None = None
    name: Annotated[str, Field(min_length=1, max_length=200)]
    role: PackagingAssetRole


class ExternalContentBody(StrictModel):
    kind: Literal["external_content"]
    content_key: Annotated[str, Field(min_length=1, max_length=200)]
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    byte_size: Annotated[int, Field(ge=0, le=MAX_INTEGER, strict=True)]
    media_type: Annotated[str, Field(min_length=1, max_length=127)]


class CompletedContentBody(StrictModel):
    kind: Literal["completed_media_asset"]
    asset_id: UUID


type ContentBody = Annotated[
    ExternalContentBody | CompletedContentBody, Field(discriminator="kind")
]


class RevisionCommand(HumanCommand):
    expected_revision: Annotated[int, Field(ge=0, le=MAX_INTEGER - 1, strict=True)]
    content: ContentBody
    measured_duration_microseconds: Annotated[
        int | None, Field(ge=0, le=MAX_INTEGER, strict=True)
    ] = None
    effective_from: AwareDatetime | None = None
    effective_until: AwareDatetime | None = None


class ApprovalCommand(HumanCommand):
    revision_number: Annotated[int, Field(ge=1, le=MAX_INTEGER, strict=True)]
    expected_revision: Annotated[int, Field(ge=1, le=MAX_INTEGER, strict=True)]
    action: ApprovalAction
    reason: Annotated[str, Field(min_length=1, max_length=500)]


class AssetResponse(StrictModel):
    packaging_asset_id: str
    event_id: str
    stage_id: str | None
    name: str
    role: PackagingAssetRole
    created_at: AwareDatetime


class RevisionResponse(StrictModel):
    revision_id: str
    packaging_asset_id: str
    revision_number: int
    content: ContentBody
    measured_duration_microseconds: int | None
    effective_from: AwareDatetime | None
    effective_until: AwareDatetime | None
    created_at: AwareDatetime


class DecisionResponse(StrictModel):
    decision_id: str
    packaging_asset_id: str
    revision_number: int
    sequence: int
    actor_id: str
    decided_at: AwareDatetime
    action: ApprovalAction
    reason: str


class AssetItem(StrictModel):
    asset: AssetResponse
    current_revision_number: int
    decision_count: int


class RevisionItem(StrictModel):
    revision: RevisionResponse
    approval_state: ApprovalState
    decision_count: int
    latest_decision: DecisionResponse | None


class AssetListResponse(StrictModel):
    event_id: str
    items: tuple[AssetItem, ...]
    total_count: int
    next_after: str | None
    items_truncated: bool
    limit: int


class RevisionListResponse(StrictModel):
    event_id: str
    packaging_asset_id: str
    items: tuple[RevisionItem, ...]
    total_count: int
    next_after: int | None
    items_truncated: bool
    limit: int


def _service(request: Request) -> PackagingAssetService:
    components = getattr(request.app.state, "kernel", None)
    if not isinstance(components, KernelComponents) or components.packaging_assets is None:
        raise HTTPException(status_code=503, detail="packaging_asset_service_unavailable")
    return components.packaging_assets


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, PackagingAssetNotFoundError):
        return HTTPException(404, str(exc))
    if isinstance(exc, PackagingAssetConflictError):
        return HTTPException(409, str(exc))
    if isinstance(exc, PackagingAssetStorageUnavailableError):
        return HTTPException(503, "postgresql_unavailable")
    return HTTPException(422, str(exc))


_ERRORS = (PackagingAssetNotFoundError, PackagingAssetConflictError,
           PackagingAssetStorageUnavailableError, ValueError)


def _asset(asset: PackagingAsset) -> AssetResponse:
    return AssetResponse(
        packaging_asset_id=asset.id.value, event_id=asset.event_id.value,
        stage_id=None if asset.stage_id is None else asset.stage_id.value,
        name=asset.name, role=asset.role, created_at=asset.created_at,
    )


def _revision(revision: PackagingAssetRevision) -> RevisionResponse:
    content = revision.content
    ref = content.reference
    body = (ExternalContentBody(kind="external_content", content_key=ref.content_key,
                                sha256=ref.sha256, byte_size=ref.byte_size,
                                media_type=ref.media_type)
            if isinstance(ref, ExternalContent) else
            CompletedContentBody(kind="completed_media_asset", asset_id=UUID(ref.asset_id.value)))
    return RevisionResponse(
        revision_id=revision.id.value, packaging_asset_id=revision.packaging_asset_id.value,
        revision_number=revision.revision_number, content=body,
        measured_duration_microseconds=content.measured_duration_microseconds,
        effective_from=content.effective_from, effective_until=content.effective_until,
        created_at=revision.created_at,
    )


def _decision(decision: PackagingAssetApprovalDecision) -> DecisionResponse:
    return DecisionResponse(
        decision_id=decision.id.value, packaging_asset_id=decision.packaging_asset_id.value,
        revision_number=decision.revision_number, sequence=decision.sequence,
        actor_id=decision.actor_id.value, decided_at=decision.decided_at,
        action=decision.action, reason=decision.reason,
    )


@router.post("/packaging-assets")
def register(command: RegisterCommand, request: Request) -> AssetResponse:
    try:
        return _asset(_service(request).register(
            operation_id=EntityId(str(command.operation_id)),
            actor_id=EntityId(str(command.actor_id)),
            event_id=EntityId(str(command.event_id)), name=command.name, role=command.role,
            stage_id=None if command.stage_id is None else EntityId(str(command.stage_id)),
        ))
    except _ERRORS as exc:
        raise _error(exc) from exc


@router.post("/packaging-assets/{packaging_asset_id}/revisions")
def revise(
    packaging_asset_id: UUID, command: RevisionCommand, request: Request,
) -> RevisionResponse:
    try:
        ref = command.content
        reference = (ExternalContent(ref.content_key, ref.sha256, ref.byte_size, ref.media_type)
                     if isinstance(ref, ExternalContentBody)
                     else CompletedMediaAssetContent(EntityId(str(ref.asset_id))))
        return _revision(_service(request).revise(
            operation_id=EntityId(str(command.operation_id)),
            actor_id=EntityId(str(command.actor_id)),
            packaging_asset_id=EntityId(str(packaging_asset_id)),
            expected_revision=command.expected_revision,
            content=RevisionContent(reference, command.measured_duration_microseconds,
                                    command.effective_from, command.effective_until),
        ))
    except _ERRORS as exc:
        raise _error(exc) from exc


@router.post("/packaging-assets/{packaging_asset_id}/approvals")
def decide(
    packaging_asset_id: UUID, command: ApprovalCommand, request: Request,
) -> DecisionResponse:
    try:
        return _decision(_service(request).decide(
            operation_id=EntityId(str(command.operation_id)),
            actor_id=EntityId(str(command.actor_id)),
            packaging_asset_id=EntityId(str(packaging_asset_id)),
            revision_number=command.revision_number, expected_revision=command.expected_revision,
            action=command.action, reason=command.reason,
        ))
    except _ERRORS as exc:
        raise _error(exc) from exc


@router.get("/events/{event_id}/packaging-assets")
def list_assets(
    event_id: UUID, request: Request, limit: Annotated[int, Query(ge=1, le=100)] = 50,
    after: UUID | None = None,
) -> AssetListResponse:
    try:
        page = _service(request).repository.list_assets(
            EntityId(str(event_id)),
            after=None if after is None else EntityId(str(after)), limit=limit,
        )
        return AssetListResponse(
            event_id=str(event_id), items=tuple(AssetItem(
                asset=_asset(item.asset), current_revision_number=item.current_revision_number,
                decision_count=item.decision_count,
            ) for item in page.items), total_count=page.total_count,
            next_after=None if page.next_after is None else page.next_after.value,
            items_truncated=page.next_after is not None, limit=limit,
        )
    except _ERRORS as exc:
        raise _error(exc) from exc


@router.get("/events/{event_id}/packaging-assets/{packaging_asset_id}/revisions")
def list_revisions(
    event_id: UUID, packaging_asset_id: UUID, request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    after: Annotated[int, Query(ge=0, le=MAX_INTEGER)] = 0,
) -> RevisionListResponse:
    try:
        page = _service(request).repository.list_revisions(
            EntityId(str(event_id)), EntityId(str(packaging_asset_id)), after=after, limit=limit,
        )
        return RevisionListResponse(
            event_id=str(event_id), packaging_asset_id=str(packaging_asset_id),
            items=tuple(RevisionItem(
                revision=_revision(item.revision), approval_state=item.approval_state,
                decision_count=item.decision_count,
                latest_decision=(None if item.latest_decision is None
                                 else _decision(item.latest_decision)),
            ) for item in page.items), total_count=page.total_count, next_after=page.next_after,
            items_truncated=page.next_after is not None, limit=limit,
        )
    except _ERRORS as exc:
        raise _error(exc) from exc
