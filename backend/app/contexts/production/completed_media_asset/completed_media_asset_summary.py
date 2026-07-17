from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.shared.ids import EntityId

from .completed_media_asset import CompletedMediaAsset
from .completed_media_asset_integrity import CompletedMediaAssetIntegrityStatus
from .completed_media_asset_kind import CompletedMediaAssetKind
from .completed_media_asset_readiness import CompletedMediaAssetReadinessStatus
from .completed_media_asset_source import CompletedMediaAssetRuntimeProfile


@dataclass(frozen=True, slots=True)
class CompletedMediaAssetSummary:
    """Privacy-safe deterministic asset summary with no source location."""

    asset_id: EntityId
    asset_kind: CompletedMediaAssetKind
    manifest_version: str
    runtime_profile: CompletedMediaAssetRuntimeProfile
    source_runtime_id: EntityId
    original_filename: str
    file_size_bytes: int
    duration: timedelta | None
    stage_id: EntityId | None
    recording_block_id: EntityId | None
    recording_group_id: EntityId | None
    segment_index: int | None
    finalized_at: datetime
    safe_to_read_status: CompletedMediaAssetReadinessStatus
    integrity_status: CompletedMediaAssetIntegrityStatus
    container_format: str | None
    video_codec: str | None
    audio_codec: str | None
    warning_codes: tuple[str, ...]

    @classmethod
    def from_asset(cls, asset: CompletedMediaAsset) -> CompletedMediaAssetSummary:
        technical = asset.technical_description
        relationship = asset.relationship
        integrity_status = (
            asset.integrity.status
            if asset.integrity is not None
            else CompletedMediaAssetIntegrityStatus.NOT_ASSESSED
        )
        duration = (
            technical.duration
            if technical is not None and technical.duration is not None
            else relationship.actual_duration
            if relationship is not None
            else None
        )
        return cls(
            asset_id=asset.id,
            asset_kind=asset.kind,
            manifest_version=asset.manifest.schema_version,
            runtime_profile=asset.source.runtime_profile,
            source_runtime_id=asset.source.runtime_id,
            original_filename=asset.primary_resource.original_filename,
            file_size_bytes=asset.primary_resource.file_size_bytes,
            duration=duration,
            stage_id=asset.context.stage_id,
            recording_block_id=asset.context.recording_block_id,
            recording_group_id=(
                relationship.recording_group_id if relationship is not None else None
            ),
            segment_index=(
                relationship.segment_index if relationship is not None else None
            ),
            finalized_at=asset.finalized_at,
            safe_to_read_status=asset.readiness.status,
            integrity_status=integrity_status,
            container_format=(
                technical.container_format
                if technical is not None
                else asset.primary_resource.container_type
            ),
            video_codec=technical.video_codec if technical is not None else None,
            audio_codec=technical.audio_codec if technical is not None else None,
            warning_codes=_warning_codes(asset, integrity_status),
        )


def _warning_codes(
    asset: CompletedMediaAsset,
    integrity_status: CompletedMediaAssetIntegrityStatus,
) -> tuple[str, ...]:
    warnings: set[str] = set()
    if asset.integrity is None:
        warnings.add("integrity_not_provided")
    elif integrity_status is CompletedMediaAssetIntegrityStatus.FAILED:
        warnings.add("integrity_failed")
    elif integrity_status is CompletedMediaAssetIntegrityStatus.NOT_ASSESSED:
        warnings.add("integrity_not_assessed")
    elif integrity_status is CompletedMediaAssetIntegrityStatus.UNKNOWN:
        warnings.add("integrity_unknown")
    if asset.kind is CompletedMediaAssetKind.UNKNOWN:
        warnings.add("asset_kind_unknown")
    if asset.source.runtime_profile is CompletedMediaAssetRuntimeProfile.UNKNOWN:
        warnings.add("runtime_profile_unknown")
    return tuple(sorted(warnings))
