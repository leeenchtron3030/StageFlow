from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.production.media_timing_evidence import (
    MediaTimingEvidenceStorageUnavailableError,
    project_media_timing_evidence,
)
from app.shared.ids import EntityId

router = APIRouter(prefix="/media-assets", tags=["media timing evidence"])


class MediaTimingObservationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    observation_id: str
    epistemic_kind: str
    kind: str
    source_field: str
    original_representation: str
    observed_at: datetime
    timezone_kind: str
    normalized_timestamp: datetime | None
    normalized_duration_microseconds: int | None
    normalized_value: str | None
    precision: str | None
    stream_selector: str | None
    limitations: tuple[str, ...]


class MediaTimingDerivationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    derivation_id: str
    epistemic_kind: str
    rule_id: str
    rule_version: str
    input_observation_ids: tuple[str, ...]
    candidate_started_at: datetime
    candidate_ended_at: datetime
    derived_at: datetime
    limitations: tuple[str, ...]


class MediaTimingEvidenceResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str
    asset_id: str
    manifest_id: str
    manifest_version: str
    revision: int
    predecessor_evidence_id: str | None
    applied_at: datetime
    provider_id: str
    provider_version: str
    tool_id: str
    tool_version: str
    recorder_profile_id: str
    recorder_profile_revision: int
    inspected_at: datetime
    qualification_status: str
    qualification_evaluated_at: datetime
    qualification_record_id: str | None
    qualification_limitations: tuple[str, ...]
    observations: tuple[MediaTimingObservationResponse, ...]
    derivations: tuple[MediaTimingDerivationResponse, ...]
    limitations: tuple[str, ...]
    authorized_use: str


class MediaTimingEvidenceHistoryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset_id: str
    active_revision: int | None
    evidence: tuple[MediaTimingEvidenceResponse, ...]


def _response(value: object) -> MediaTimingEvidenceResponse:
    from app.contexts.production.media_timing_evidence.projection import (
        MediaTimingEvidenceProjection,
    )

    assert isinstance(value, MediaTimingEvidenceProjection)
    return MediaTimingEvidenceResponse(
        evidence_id=value.evidence_id.value,
        asset_id=value.asset_id.value,
        manifest_id=value.manifest_id.value,
        manifest_version=value.manifest_version,
        revision=value.revision,
        predecessor_evidence_id=(
            None
            if value.predecessor_evidence_id is None
            else value.predecessor_evidence_id.value
        ),
        applied_at=value.applied_at,
        provider_id=value.provider_id,
        provider_version=value.provider_version,
        tool_id=value.tool_id,
        tool_version=value.tool_version,
        recorder_profile_id=value.recorder_profile_id,
        recorder_profile_revision=value.recorder_profile_revision,
        inspected_at=value.inspected_at,
        qualification_status=value.qualification_status,
        qualification_evaluated_at=value.qualification_evaluated_at,
        qualification_record_id=(
            None
            if value.qualification_record_id is None
            else value.qualification_record_id.value
        ),
        qualification_limitations=value.qualification_limitations,
        observations=tuple(
            MediaTimingObservationResponse(
                observation_id=item.observation_id.value,
                epistemic_kind=item.epistemic_kind,
                kind=item.kind,
                source_field=item.source_field,
                original_representation=item.original_representation,
                observed_at=item.observed_at,
                timezone_kind=item.timezone_kind,
                normalized_timestamp=item.normalized_timestamp,
                normalized_duration_microseconds=item.normalized_duration_microseconds,
                normalized_value=item.normalized_value,
                precision=item.precision,
                stream_selector=item.stream_selector,
                limitations=item.limitations,
            )
            for item in value.observations
        ),
        derivations=tuple(
            MediaTimingDerivationResponse(
                derivation_id=item.derivation_id.value,
                epistemic_kind=item.epistemic_kind,
                rule_id=item.rule_id,
                rule_version=item.rule_version,
                input_observation_ids=tuple(
                    observation_id.value
                    for observation_id in item.input_observation_ids
                ),
                candidate_started_at=item.candidate_started_at,
                candidate_ended_at=item.candidate_ended_at,
                derived_at=item.derived_at,
                limitations=item.limitations,
            )
            for item in value.derivations
        ),
        limitations=value.limitations,
        authorized_use=value.authorized_use,
    )


@router.get(
    "/{asset_id}/timing-evidence",
    response_model=MediaTimingEvidenceHistoryResponse,
)
def media_timing_evidence_history(
    asset_id: UUID,
    request: Request,
) -> MediaTimingEvidenceHistoryResponse:
    components = getattr(request.app.state, "kernel", None)
    if not isinstance(components, KernelComponents):
        raise HTTPException(status_code=503, detail="kernel_not_configured")
    identifier = EntityId.parse(str(asset_id))
    if components.repository.get_asset(identifier) is None:
        raise HTTPException(status_code=404, detail="completed_media_asset_not_found")
    repository = components.media_timing_evidence_repository
    if repository is None:
        raise HTTPException(status_code=503, detail="media_timing_evidence_not_composed")
    try:
        history = repository.history(identifier)
    except MediaTimingEvidenceStorageUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail="media_timing_evidence_storage_unavailable",
        ) from exc
    projected = tuple(_response(project_media_timing_evidence(item)) for item in history)
    return MediaTimingEvidenceHistoryResponse(
        asset_id=identifier.value,
        active_revision=None if not projected else projected[-1].revision,
        evidence=projected,
    )


__all__ = [
    "MediaTimingDerivationResponse",
    "MediaTimingEvidenceHistoryResponse",
    "MediaTimingEvidenceResponse",
    "MediaTimingObservationResponse",
    "router",
]
