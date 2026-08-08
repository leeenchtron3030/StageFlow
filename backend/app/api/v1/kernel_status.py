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


class StageStatusResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    stage_id: str
    key: str
    name: str
    source_available: bool | None
    session_id: str | None
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
            )
            for stage in status.stages
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


__all__ = ["KernelStatusResponse", "StageStatusResponse", "router"]
