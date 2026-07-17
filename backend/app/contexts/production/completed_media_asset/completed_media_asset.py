from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.shared.ids import EntityId

from .completed_media_asset_completion import CompletedMediaAssetCompletion
from .completed_media_asset_context import CompletedMediaAssetContext
from .completed_media_asset_integrity import CompletedMediaAssetIntegrity
from .completed_media_asset_kind import CompletedMediaAssetKind
from .completed_media_asset_manifest import CompletedMediaAssetManifest
from .completed_media_asset_provenance import CompletedMediaAssetProvenance
from .completed_media_asset_readiness import (
    CompletedMediaAssetReadiness,
    CompletedMediaAssetReadinessStatus,
)
from .completed_media_asset_relationship import CompletedMediaAssetRelationship
from .completed_media_asset_resource import (
    CompletedMediaAssetResource,
    CompletedMediaAssetResourceReference,
)
from .completed_media_asset_source import CompletedMediaAssetSource
from .completed_media_asset_technical_description import (
    CompletedMediaAssetTechnicalDescription,
)
from .completed_media_asset_validation import (
    freeze_metadata,
    require_aware,
    require_optional_aware,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class CompletedMediaAsset:
    """One finalized logical media asset that StageFlow may safely read."""

    id: EntityId
    kind: CompletedMediaAssetKind
    manifest: CompletedMediaAssetManifest
    primary_resource: CompletedMediaAssetResource
    source: CompletedMediaAssetSource
    provenance: CompletedMediaAssetProvenance
    context: CompletedMediaAssetContext
    completion: CompletedMediaAssetCompletion
    readiness: CompletedMediaAssetReadiness
    finalized_at: datetime
    manifested_at: datetime
    related_resources: Sequence[CompletedMediaAssetResourceReference] = field(
        default_factory=tuple
    )
    relationship: CompletedMediaAssetRelationship | None = None
    integrity: CompletedMediaAssetIntegrity | None = None
    technical_description: CompletedMediaAssetTechnicalDescription | None = None
    recorded_start_at: datetime | None = None
    recorded_end_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        related_resources = _normalize_related_resources(self.related_resources)
        object.__setattr__(self, "related_resources", related_resources)
        require_aware(self.finalized_at, "CompletedMediaAsset.finalized_at")
        require_aware(self.manifested_at, "CompletedMediaAsset.manifested_at")
        require_optional_aware(
            self.recorded_start_at,
            "CompletedMediaAsset.recorded_start_at",
        )
        require_optional_aware(
            self.recorded_end_at,
            "CompletedMediaAsset.recorded_end_at",
        )
        self._validate_identity_graph(related_resources)
        self._validate_source_provenance()
        self._validate_declarations()
        self._validate_timestamps()
        self._validate_media_consistency()
        object.__setattr__(
            self,
            "metadata",
            freeze_metadata(self.metadata, "CompletedMediaAsset.metadata"),
        )

    def _validate_identity_graph(
        self,
        related_resources: tuple[CompletedMediaAssetResourceReference, ...],
    ) -> None:
        if self.manifest.asset_id != self.id:
            raise ValueError("Manifest asset ID must match CompletedMediaAsset ID.")
        if self.manifest.source_resource_id != self.primary_resource.id:
            raise ValueError("Manifest source resource must match the primary resource.")
        related_ids = tuple(reference.resource_id for reference in related_resources)
        if self.primary_resource.id in related_ids:
            raise ValueError("Primary resource cannot also be a related resource.")
        if self.manifest.related_resource_ids != related_ids:
            raise ValueError("Manifest related resources must match asset references.")
        if self.provenance.manifest_id != self.manifest.id:
            raise ValueError("Provenance manifest ID must match the asset manifest.")
        if self.provenance.readiness_declaration_id != self.readiness.id:
            raise ValueError("Provenance readiness ID must match the readiness declaration.")
        if self.integrity is None:
            if self.provenance.integrity_declaration_id is not None:
                raise ValueError("Provenance cannot reference absent integrity information.")
        elif self.provenance.integrity_declaration_id != self.integrity.id:
            raise ValueError("Provenance integrity ID must match integrity information.")

    def _validate_source_provenance(self) -> None:
        if self.source.runtime_id != self.manifest.producer_runtime_id:
            raise ValueError("Manifest producer Runtime must match the asset source.")
        if self.source.runtime_id != self.provenance.source_runtime_id:
            raise ValueError("Source and provenance Runtime IDs must match.")
        for field_name, source_value, provenance_value in (
            ("host", self.source.host_id, self.provenance.source_host_id),
            (
                "recorder application",
                self.source.recorder_application_id,
                self.provenance.recorder_application_id,
            ),
            ("producer", self.source.producer_id, self.provenance.producer_id),
            ("adapter", self.source.adapter_id, self.provenance.adapter_id),
        ):
            if (
                source_value is not None
                and provenance_value is not None
                and source_value != provenance_value
            ):
                raise ValueError(f"Source and provenance {field_name} IDs must match.")
        if (
            self.source.source_event_id is not None
            and self.source.source_event_id not in self.provenance.source_event_ids
        ):
            raise ValueError("Source Event ID must be retained in provenance.")

    def _validate_declarations(self) -> None:
        if not self.completion.is_finalized:
            raise ValueError("CompletedMediaAsset requires finalized completion.")
        if self.readiness.status is not CompletedMediaAssetReadinessStatus.SAFE_TO_READ:
            raise ValueError("CompletedMediaAsset requires categorical safe-to-read status.")
        if self.completion.finalized_at != self.finalized_at:
            raise ValueError("Completion finalization time must match the asset.")
        if self.provenance.finalized_at != self.finalized_at:
            raise ValueError("Provenance finalization time must match the asset.")
        if self.manifest.created_at != self.manifested_at:
            raise ValueError("Manifest creation time must match manifested_at.")

    def _validate_timestamps(self) -> None:
        if (
            self.recorded_start_at is not None
            and self.recorded_end_at is not None
            and self.recorded_start_at > self.recorded_end_at
        ):
            raise ValueError("Recorded start must not be after recorded end.")
        if self.recorded_end_at is not None and self.finalized_at < self.recorded_end_at:
            raise ValueError("Finalization must not precede recorded end.")
        if self.readiness.assessed_at < self.finalized_at:
            raise ValueError("Readiness assessment must not precede finalization.")
        if self.manifested_at < self.finalized_at:
            raise ValueError("Manifest creation must not precede finalization.")
        for field_name, asset_value, provenance_value in (
            (
                "recording start",
                self.recorded_start_at,
                self.provenance.recording_started_at,
            ),
            (
                "recording end",
                self.recorded_end_at,
                self.provenance.recording_ended_at,
            ),
        ):
            if (
                asset_value is not None
                and provenance_value is not None
                and asset_value != provenance_value
            ):
                raise ValueError(f"Asset and provenance {field_name} times must match.")

    def _validate_media_consistency(self) -> None:
        if (
            self.integrity is not None
            and self.integrity.checksum_byte_size is not None
            and self.integrity.checksum_byte_size != self.primary_resource.file_size_bytes
        ):
            raise ValueError("Checksum byte size must match the primary resource size.")
        if self.technical_description is not None:
            technical_container = self.technical_description.container_format
            resource_container = self.primary_resource.container_type
            if (
                technical_container is not None
                and resource_container is not None
                and technical_container.casefold() != resource_container.casefold()
            ):
                raise ValueError("Technical and resource container descriptions must match.")
            relationship_duration = (
                self.relationship.actual_duration
                if self.relationship is not None
                else None
            )
            if (
                self.technical_description.duration is not None
                and relationship_duration is not None
                and self.technical_description.duration != relationship_duration
            ):
                raise ValueError("Technical and relationship durations must match.")
        if self.relationship is None:
            return
        for relationship_id in (
            self.relationship.parent_recording_id,
            self.relationship.previous_asset_id,
            self.relationship.next_asset_id,
            *self.relationship.related_asset_ids,
        ):
            if relationship_id == self.id:
                raise ValueError("An asset relationship must not reference itself.")
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
            self.kind is not CompletedMediaAssetKind.RECORDING_SEGMENT
            and any(value is not None for value in segment_fields)
        ):
            raise ValueError("Segment relationship fields require recording_segment kind.")


def _normalize_related_resources(
    resources: Sequence[CompletedMediaAssetResourceReference],
) -> tuple[CompletedMediaAssetResourceReference, ...]:
    by_id: dict[str, CompletedMediaAssetResourceReference] = {}
    for resource in resources:
        existing = by_id.get(resource.resource_id.value)
        if existing is not None and existing != resource:
            raise ValueError("One related resource ID cannot describe conflicting resources.")
        by_id[resource.resource_id.value] = resource
    return tuple(by_id[value] for value in sorted(by_id))
