from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.shared.ids import EntityId

from .completed_media_asset_validation import (
    freeze_metadata,
    normalize_entity_ids,
    require_aware,
    require_optional_aware,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class CompletedMediaAssetProvenance:
    """Exact ID-only origin and declaration lineage for a completed asset."""

    source_runtime_id: EntityId
    finalized_at: datetime
    readiness_declaration_id: EntityId
    manifest_id: EntityId
    source_host_id: EntityId | None = None
    recorder_application_id: EntityId | None = None
    producer_id: EntityId | None = None
    source_event_ids: Sequence[EntityId] = field(default_factory=tuple)
    recording_started_at: datetime | None = None
    recording_ended_at: datetime | None = None
    integrity_declaration_id: EntityId | None = None
    adapter_id: EntityId | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware(
            self.finalized_at,
            "CompletedMediaAssetProvenance.finalized_at",
        )
        require_optional_aware(
            self.recording_started_at,
            "CompletedMediaAssetProvenance.recording_started_at",
        )
        require_optional_aware(
            self.recording_ended_at,
            "CompletedMediaAssetProvenance.recording_ended_at",
        )
        if (
            self.recording_started_at is not None
            and self.recording_ended_at is not None
            and self.recording_started_at > self.recording_ended_at
        ):
            raise ValueError("Recording start must not be after recording end.")
        if (
            self.recording_ended_at is not None
            and self.finalized_at < self.recording_ended_at
        ):
            raise ValueError("Asset finalization must not precede recording end.")
        object.__setattr__(
            self,
            "source_event_ids",
            normalize_entity_ids(
                self.source_event_ids,
                "CompletedMediaAssetProvenance.source_event_ids",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_metadata(self.metadata, "CompletedMediaAssetProvenance.metadata"),
        )
