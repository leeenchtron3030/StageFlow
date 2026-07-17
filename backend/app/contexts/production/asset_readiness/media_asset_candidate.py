from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.contexts.production.completed_media_asset import (
    CompletedMediaAssetContext,
    CompletedMediaAssetKind,
    CompletedMediaAssetRelationship,
    CompletedMediaAssetRuntimeProfile,
)
from app.shared.ids import EntityId

from .asset_readiness_validation import freeze_readiness_metadata, require_aware
from .media_asset_candidate_resource import MediaAssetCandidateResource


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class MediaAssetCandidate:
    """One known media resource that may later become eligible as a completed asset."""

    id: EntityId
    proposed_asset_id: EntityId
    primary_resource: MediaAssetCandidateResource
    source_runtime_id: EntityId
    runtime_profile: CompletedMediaAssetRuntimeProfile
    first_observed_at: datetime
    context: CompletedMediaAssetContext
    intended_asset_kind: CompletedMediaAssetKind | None = None
    source_host_id: EntityId | None = None
    recorder_application_id: EntityId | None = None
    adapter_id: EntityId | None = None
    relationship: CompletedMediaAssetRelationship | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware(self.first_observed_at, "MediaAssetCandidate.first_observed_at")
        if (
            self.source_host_id is not None
            and self.primary_resource.source_host_id is not None
            and self.source_host_id != self.primary_resource.source_host_id
        ):
            raise ValueError("Candidate and resource source host IDs must match.")
        segment_fields = ()
        if self.relationship is not None:
            segment_fields = (
                self.relationship.segment_index,
                self.relationship.sequence_number,
                self.relationship.previous_asset_id,
                self.relationship.next_asset_id,
                self.relationship.expected_segment_duration,
                self.relationship.actual_duration,
                self.relationship.is_first_known_segment,
                self.relationship.is_final_known_segment,
            )
        if (
            self.intended_asset_kind is not None
            and self.intended_asset_kind is not CompletedMediaAssetKind.RECORDING_SEGMENT
            and any(value is not None for value in segment_fields)
        ):
            raise ValueError("Segment relationship fields require recording_segment intent.")
        object.__setattr__(
            self,
            "metadata",
            freeze_readiness_metadata(self.metadata, "MediaAssetCandidate.metadata"),
        )
