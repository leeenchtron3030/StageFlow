from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from app.contexts.production.media_timing_evidence import (
    ApplyMediaTimingEvidenceRequest,
    MediaTimingDerivation,
    MediaTimingInspectionProvenance,
    MediaTimingInspectionResult,
    MediaTimingObservation,
    RecorderProfileQualification,
    RecorderProfileQualificationStatus,
    TimingTimezoneKind,
)
from app.shared.ids import EntityId

NOW = datetime(2026, 8, 12, 18, 24, 1, tzinfo=UTC)
ASSET_ID = EntityId("71000000-0000-0000-0000-000000000001")
MANIFEST_ID = EntityId("71000000-0000-0000-0000-000000000002")


def evidence_request(
    *,
    operation_number: int = 10,
    inspected_at: datetime = NOW,
    provider_id: str = "ffmpeg-probe",
    profile_id: str = "vmix-reference-profile",
    profile_revision: int = 1,
) -> ApplyMediaTimingEvidenceRequest:
    creation = MediaTimingObservation(
        id=EntityId(f"71000000-0000-0000-0001-{operation_number:012d}"),
        kind="embedded_creation_time",
        source_field="format.tags.creation_time",
        original_representation="2026-08-12T18:24:01.000000Z",
        observed_at=inspected_at,
        timezone_kind=TimingTimezoneKind.EXPLICIT_UTC,
        normalized_timestamp=NOW,
        precision="microsecond",
        limitations=("Recorder semantics are not independently calibrated.",),
    )
    duration = MediaTimingObservation(
        id=EntityId(f"71000000-0000-0000-0002-{operation_number:012d}"),
        kind="measured_duration",
        source_field="format.duration",
        original_representation="60.030000",
        observed_at=inspected_at,
        timezone_kind=TimingTimezoneKind.NOT_APPLICABLE,
        normalized_duration=timedelta(seconds=60, milliseconds=30),
        precision="microsecond",
    )
    derivation = MediaTimingDerivation(
        id=EntityId(f"71000000-0000-0000-0003-{operation_number:012d}"),
        rule_id="creation-time-plus-duration",
        rule_version="1.0",
        input_observation_ids=(creation.id, duration.id),
        candidate_started_at=NOW,
        candidate_ended_at=NOW + timedelta(seconds=60, milliseconds=30),
        derived_at=inspected_at,
        limitations=("Candidate interval is advisory only.",),
    )
    qualification = RecorderProfileQualification(
        profile_id=profile_id,
        profile_revision=profile_revision,
        status=RecorderProfileQualificationStatus.UNQUALIFIED,
        evaluated_at=inspected_at,
        limitations=("Controlled content-time calibration has not passed.",),
    )
    return ApplyMediaTimingEvidenceRequest(
        operation_id=EntityId(
            f"71000000-0000-0000-0004-{operation_number:012d}"
        ),
        asset_id=ASSET_ID,
        manifest_id=MANIFEST_ID,
        manifest_version="1.0",
        applied_at=inspected_at + timedelta(seconds=1),
        result=MediaTimingInspectionResult(
            provenance=MediaTimingInspectionProvenance(
                provider_id=provider_id,
                provider_version="1.0",
                tool_id="ffprobe",
                tool_version="8.0",
                recorder_profile_id=profile_id,
                recorder_profile_revision=profile_revision,
                inspected_at=inspected_at,
            ),
            observations=(creation, duration),
            derivations=(derivation,),
            qualification=qualification,
            limitations=("No authoritative Session or content boundary is established.",),
        ),
    )


def changed_evidence_request(
    request: ApplyMediaTimingEvidenceRequest,
) -> ApplyMediaTimingEvidenceRequest:
    return replace(
        request,
        result=replace(
            request.result,
            limitations=("Conflicting replay payload.",),
        ),
    )
