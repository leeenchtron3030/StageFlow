from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict

from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.production.event_mode_kernel.contracts import EventOperationalStatus
from app.contexts.production.event_mode_kernel.repository import (
    KernelStorageUnavailableError,
)

router = APIRouter(prefix="/kernel", tags=["kernel"])


class AssemblingSessionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str
    activity_state: str
    package_state: str
    package_revision: int
    revision: int
    authoritative_start: datetime
    authoritative_end: datetime | None


class StageStatusResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    stage_id: str
    key: str
    name: str
    source_available: bool | None
    session_id: str | None
    assembling_session_ids: tuple[str, ...]
    assembling_sessions: tuple[AssemblingSessionResponse, ...]
    session_activity_state: str | None
    session_package_state: str | None
    session_package_revision: int | None
    session_revision: int | None
    session_authoritative_start: datetime | None
    session_authoritative_end: datetime | None
    last_media_arrived_at: datetime | None
    discovered: int
    stabilizing: int
    ready: int
    registered: int
    associated: int
    unresolved: int
    conflicting: int
    attention_codes: tuple[str, ...]


class MediaStatusResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_id: str
    proposed_asset_id: str
    asset_id: str | None
    stage_id: str
    source_binding_key: str
    registration_state: str
    discovered_at: datetime
    last_observed_at: datetime
    association_status: str | None
    association_authority: str | None
    session_id: str | None
    epistemic_kinds: tuple[str, ...]
    media_started_at: datetime | None
    media_ended_at: datetime | None
    diagnostic_codes: tuple[str, ...]


class BoundaryProposalResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    proposal_id: str
    session_id: str
    boundary_kind: str
    boundary_at: datetime
    epistemic_kind: str
    proposer_id: str
    evidence_ids: tuple[str, ...]
    policy_id: str
    policy_version: str
    model_id: str | None
    model_version: str | None
    reason: str
    proposed_at: datetime


class KernelStatusResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    configured: bool
    event_id: str | None
    event_key: str | None
    event_name: str | None
    database_available: bool
    ready: bool
    recovering: bool
    reconciliation_status: str | None
    reconciliation_started_at: datetime | None
    reconciliation_completed_at: datetime | None
    stages: tuple[StageStatusResponse, ...]
    recent_media: tuple[MediaStatusResponse, ...] = ()
    boundary_proposals: tuple[BoundaryProposalResponse, ...] = ()
    attention_codes: tuple[str, ...]
    startup_error: str | None = None


def _response(status: EventOperationalStatus) -> KernelStatusResponse:
    reconciliation = status.latest_reconciliation
    return KernelStatusResponse(
        configured=True,
        event_id=status.event_id.value,
        event_key=status.event_key,
        event_name=status.event_name,
        database_available=status.database_available,
        ready=status.ready,
        recovering=status.recovering,
        reconciliation_status=(
            None if reconciliation is None else reconciliation.status.value
        ),
        reconciliation_started_at=(
            None if reconciliation is None else reconciliation.started_at
        ),
        reconciliation_completed_at=(
            None if reconciliation is None else reconciliation.completed_at
        ),
        stages=tuple(
            StageStatusResponse(
                stage_id=stage.stage_id.value,
                key=stage.stage_key,
                name=stage.stage_name,
                source_available=stage.source_available,
                session_id=(
                    None
                    if stage.active_or_assembling_session_id is None
                    else stage.active_or_assembling_session_id.value
                ),
                assembling_session_ids=tuple(
                    value.value for value in stage.assembling_session_ids
                ),
                assembling_sessions=tuple(
                    AssemblingSessionResponse(
                        session_id=item.session_id.value,
                        activity_state=item.activity_state.value,
                        package_state=item.package_state.value,
                        package_revision=item.package_revision,
                        revision=item.revision,
                        authoritative_start=item.authoritative_start,
                        authoritative_end=item.authoritative_end,
                    )
                    for item in stage.assembling_sessions
                ),
                session_activity_state=(
                    None
                    if stage.session_activity_state is None
                    else stage.session_activity_state.value
                ),
                session_package_state=(
                    None
                    if stage.session_package_state is None
                    else stage.session_package_state.value
                ),
                session_package_revision=stage.session_package_revision,
                session_revision=stage.session_revision,
                session_authoritative_start=stage.session_authoritative_start,
                session_authoritative_end=stage.session_authoritative_end,
                last_media_arrived_at=stage.last_media_arrived_at,
                discovered=stage.discovered_media,
                stabilizing=stage.stabilizing_media,
                ready=stage.ready_media,
                registered=stage.registered_media,
                associated=stage.associated_media,
                unresolved=stage.unresolved_media,
                conflicting=stage.conflicting_media,
                attention_codes=tuple(stage.attention_codes),
            )
            for stage in status.stages
        ),
        recent_media=tuple(
            MediaStatusResponse(
                candidate_id=item.candidate_id.value,
                proposed_asset_id=item.proposed_asset_id.value,
                asset_id=None if item.asset_id is None else item.asset_id.value,
                stage_id=item.stage_id.value,
                source_binding_key=item.source_binding_key,
                registration_state=item.registration_state.value,
                discovered_at=item.discovered_at,
                last_observed_at=item.last_observed_at,
                association_status=(
                    None
                    if item.association_status is None
                    else item.association_status.value
                ),
                association_authority=(
                    None
                    if item.association_authority is None
                    else item.association_authority.value
                ),
                session_id=None if item.session_id is None else item.session_id.value,
                epistemic_kinds=tuple(value.value for value in item.epistemic_kinds),
                media_started_at=item.media_started_at,
                media_ended_at=item.media_ended_at,
                diagnostic_codes=tuple(item.diagnostic_codes),
            )
            for item in status.recent_media
        ),
        boundary_proposals=tuple(
            BoundaryProposalResponse(
                proposal_id=item.id.value,
                session_id=item.session_id.value,
                boundary_kind=item.boundary_kind,
                boundary_at=item.boundary_at,
                epistemic_kind=item.epistemic_kind.value,
                proposer_id=item.proposer_id.value,
                evidence_ids=tuple(value.value for value in item.evidence_ids),
                policy_id=item.policy_id,
                policy_version=item.policy_version,
                model_id=item.model_id,
                model_version=item.model_version,
                reason=item.reason,
                proposed_at=item.proposed_at,
            )
            for item in status.boundary_proposals
        ),
        attention_codes=tuple(status.attention_codes),
    )


@router.get("/status", response_model=KernelStatusResponse)
def kernel_status(request: Request, response: Response) -> KernelStatusResponse:
    components = getattr(request.app.state, "kernel", None)
    startup_error = getattr(request.app.state, "kernel_startup_error", None)
    if components is None:
        return KernelStatusResponse(
            configured=False,
            event_id=None,
            event_key=None,
            event_name=None,
            database_available=False,
            ready=False,
            recovering=False,
            reconciliation_status=None,
            reconciliation_started_at=None,
            reconciliation_completed_at=None,
            stages=(),
            attention_codes=(
                "kernel_startup_failed" if startup_error else "kernel_not_configured",
            ),
            startup_error=startup_error,
        )
    assert isinstance(components, KernelComponents)
    try:
        status = components.status()
    except KernelStorageUnavailableError as exc:
        response.status_code = 503
        return KernelStatusResponse(
            configured=True,
            event_id=None,
            event_key=components.event_key,
            event_name=components.configuration.deployment.event.name,
            database_available=False,
            ready=False,
            recovering=False,
            reconciliation_status=None,
            reconciliation_started_at=None,
            reconciliation_completed_at=None,
            stages=(),
            attention_codes=("postgresql_unavailable",),
            startup_error=str(exc),
        )
    if status is None:
        return KernelStatusResponse(
            configured=True,
            event_id=None,
            event_key=components.event_key,
            event_name=components.configuration.deployment.event.name,
            database_available=True,
            ready=False,
            recovering=False,
            reconciliation_status=None,
            reconciliation_started_at=None,
            reconciliation_completed_at=None,
            stages=(),
            attention_codes=("explicit_event_stage_bootstrap_required",),
        )
    return _response(status)


__all__ = [
    "BoundaryProposalResponse",
    "AssemblingSessionResponse",
    "KernelStatusResponse",
    "MediaStatusResponse",
    "StageStatusResponse",
    "router",
]
