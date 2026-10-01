"""Read-only transcription availability, without transcript or worker diagnostics."""
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.production.event_mode_kernel.repository import KernelStorageUnavailableError
from app.contexts.work_execution import WorkExecutionStorageUnavailableError
from app.infrastructure.postgres import PostgresWorkExecutionRepository
from app.shared.ids import EntityId

router = APIRouter(prefix="/transcription", tags=["transcription"])


def _components(request: Request) -> KernelComponents:
    components = getattr(request.app.state, "kernel", None)
    if not isinstance(components, KernelComponents):
        raise HTTPException(503, "kernel_not_configured")
    return components


def _repository(request: Request) -> PostgresWorkExecutionRepository:
    return PostgresWorkExecutionRepository(_components(request).configuration.postgres_dsn)


@router.get("/assets/{asset_id}/status")
def status(asset_id: UUID, request: Request) -> dict[str, object]:
    components = _components(request)
    identifier = EntityId(str(asset_id))
    try:
        if components.repository.get_asset(identifier) is None:
            raise HTTPException(404, "completed_media_asset_not_found")
        local = components.configuration.deployment.local_transcription
        if local is None:
            raise HTTPException(503, "local_transcription_not_configured")
        operation, complete, partial = _repository(request).asset_transcription_status(
            identifier, deployment_id=components.configuration.deployment.deployment_id,
            execution_profile_id=local.execution_profile_id,
            execution_profile_version=local.execution_profile_version,
        )
    except (KernelStorageUnavailableError, WorkExecutionStorageUnavailableError):
        raise HTTPException(503, "postgresql_unavailable") from None
    return {"asset_id": identifier.value, "operation": None if operation is None else {
        "state": operation.status.value,
        "execution_profile_id": operation.input.execution_profile_id,
        "execution_profile_version": operation.input.execution_profile_version,
    }, "complete_evidence": complete, "partial_evidence": partial}
