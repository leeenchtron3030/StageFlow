from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Protocol

from app.shared.ids import EntityId

from .contracts import (
    ApplyMediaTimingEvidenceRequest,
    MediaTimingEvidence,
    MediaTimingInspectionResult,
    PendingMediaTimingEvidence,
)
from .repository import MediaTimingEvidenceRepository


class MediaTimingInspectionPort(Protocol):
    """Future execution seam; providers return facts and never mutate authority."""

    def inspect(self, request: object) -> MediaTimingInspectionResult: ...


def _microseconds(value: timedelta | None) -> int | None:
    if value is None:
        return None
    return (
        value.days * 86_400_000_000
        + value.seconds * 1_000_000
        + value.microseconds
    )


def _time(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def request_digest(request: ApplyMediaTimingEvidenceRequest) -> str:
    result = request.result
    document = {
        "schema": "stageflow.media_timing_evidence.application.v1",
        "asset_id": request.asset_id.value,
        "manifest_id": request.manifest_id.value,
        "manifest_version": request.manifest_version,
        "applied_at": request.applied_at.isoformat(),
        "provenance": {
            "provider_id": result.provenance.provider_id,
            "provider_version": result.provenance.provider_version,
            "tool_id": result.provenance.tool_id,
            "tool_version": result.provenance.tool_version,
            "recorder_profile_id": result.provenance.recorder_profile_id,
            "recorder_profile_revision": result.provenance.recorder_profile_revision,
            "inspected_at": result.provenance.inspected_at.isoformat(),
        },
        "observations": [
            {
                "id": item.id.value,
                "kind": item.kind,
                "source_field": item.source_field,
                "original_representation": item.original_representation,
                "observed_at": item.observed_at.isoformat(),
                "timezone_kind": item.timezone_kind.value,
                "normalized_timestamp": _time(item.normalized_timestamp),
                "normalized_duration_microseconds": _microseconds(item.normalized_duration),
                "normalized_value": item.normalized_value,
                "precision": item.precision,
                "stream_selector": item.stream_selector,
                "limitations": item.limitations,
            }
            for item in result.observations
        ],
        "derivations": [
            {
                "id": item.id.value,
                "rule_id": item.rule_id,
                "rule_version": item.rule_version,
                "input_observation_ids": [value.value for value in item.input_observation_ids],
                "candidate_started_at": item.candidate_started_at.isoformat(),
                "candidate_ended_at": item.candidate_ended_at.isoformat(),
                "derived_at": item.derived_at.isoformat(),
                "limitations": item.limitations,
            }
            for item in result.derivations
        ],
        "qualification": {
            "profile_id": result.qualification.profile_id,
            "profile_revision": result.qualification.profile_revision,
            "status": result.qualification.status.value,
            "evaluated_at": result.qualification.evaluated_at.isoformat(),
            "qualification_record_id": (
                None
                if result.qualification.qualification_record_id is None
                else result.qualification.qualification_record_id.value
            ),
            "limitations": result.qualification.limitations,
        },
        "limitations": result.limitations,
    }
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class MediaTimingEvidenceApplication:
    repository: MediaTimingEvidenceRepository

    def apply(self, request: ApplyMediaTimingEvidenceRequest) -> MediaTimingEvidence:
        return self.repository.append(
            PendingMediaTimingEvidence(
                id=EntityId.new(),
                request=request,
                request_digest=request_digest(request),
            )
        )


__all__ = [
    "MediaTimingEvidenceApplication",
    "MediaTimingInspectionPort",
    "request_digest",
]
