from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.shared.ids import EntityId

from .contracts import MediaTimingEvidence


@dataclass(frozen=True, slots=True)
class MediaTimingObservationProjection:
    observation_id: EntityId
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


@dataclass(frozen=True, slots=True)
class MediaTimingDerivationProjection:
    derivation_id: EntityId
    epistemic_kind: str
    rule_id: str
    rule_version: str
    input_observation_ids: tuple[EntityId, ...]
    candidate_started_at: datetime
    candidate_ended_at: datetime
    derived_at: datetime
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MediaTimingEvidenceProjection:
    evidence_id: EntityId
    asset_id: EntityId
    manifest_id: EntityId
    manifest_version: str
    revision: int
    predecessor_evidence_id: EntityId | None
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
    qualification_record_id: EntityId | None
    qualification_limitations: tuple[str, ...]
    observations: tuple[MediaTimingObservationProjection, ...]
    derivations: tuple[MediaTimingDerivationProjection, ...]
    limitations: tuple[str, ...]
    authorized_use: str = "advisory_only"


def project_media_timing_evidence(
    evidence: MediaTimingEvidence,
) -> MediaTimingEvidenceProjection:
    result = evidence.result
    return MediaTimingEvidenceProjection(
        evidence_id=evidence.id,
        asset_id=evidence.asset_id,
        manifest_id=evidence.manifest_id,
        manifest_version=evidence.manifest_version,
        revision=evidence.revision,
        predecessor_evidence_id=evidence.predecessor_evidence_id,
        applied_at=evidence.applied_at,
        provider_id=result.provenance.provider_id,
        provider_version=result.provenance.provider_version,
        tool_id=result.provenance.tool_id,
        tool_version=result.provenance.tool_version,
        recorder_profile_id=result.provenance.recorder_profile_id,
        recorder_profile_revision=result.provenance.recorder_profile_revision,
        inspected_at=result.provenance.inspected_at,
        qualification_status=result.qualification.status.value,
        qualification_evaluated_at=result.qualification.evaluated_at,
        qualification_record_id=result.qualification.qualification_record_id,
        qualification_limitations=result.qualification.limitations,
        observations=tuple(
            MediaTimingObservationProjection(
                observation_id=item.id,
                epistemic_kind=item.epistemic_kind.value,
                kind=item.kind,
                source_field=item.source_field,
                original_representation=item.original_representation,
                observed_at=item.observed_at,
                timezone_kind=item.timezone_kind.value,
                normalized_timestamp=item.normalized_timestamp,
                normalized_duration_microseconds=(
                    None
                    if item.normalized_duration is None
                    else item.normalized_duration.days * 86_400_000_000
                    + item.normalized_duration.seconds * 1_000_000
                    + item.normalized_duration.microseconds
                ),
                normalized_value=item.normalized_value,
                precision=item.precision,
                stream_selector=item.stream_selector,
                limitations=item.limitations,
            )
            for item in result.observations
        ),
        derivations=tuple(
            MediaTimingDerivationProjection(
                derivation_id=item.id,
                epistemic_kind=item.epistemic_kind.value,
                rule_id=item.rule_id,
                rule_version=item.rule_version,
                input_observation_ids=item.input_observation_ids,
                candidate_started_at=item.candidate_started_at,
                candidate_ended_at=item.candidate_ended_at,
                derived_at=item.derived_at,
                limitations=item.limitations,
            )
            for item in result.derivations
        ),
        limitations=result.limitations,
    )


__all__ = [
    "MediaTimingDerivationProjection",
    "MediaTimingEvidenceProjection",
    "MediaTimingObservationProjection",
    "project_media_timing_evidence",
]
