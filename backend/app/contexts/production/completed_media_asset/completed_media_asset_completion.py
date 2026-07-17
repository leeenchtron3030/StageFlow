from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.shared.ids import EntityId

from .completed_media_asset_validation import (
    freeze_metadata,
    normalize_entity_ids,
    require_aware,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


class CompletedMediaAssetCompletionMethod(StrEnum):
    EXPLICIT_RECORDER_FINALIZATION = "explicit_recorder_finalization"
    ATOMIC_RENAME_OBSERVED = "atomic_rename_observed"
    CLOSED_SEGMENT_NOTIFICATION = "closed_segment_notification"
    SIDECAR_COMPLETION_MARKER = "sidecar_completion_marker"
    STABLE_FILE_OBSERVATION = "stable_file_observation"
    MANUAL_DECLARATION = "manual_declaration"
    OTHER_SUPPORTED_METHOD = "other_supported_method"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CompletedMediaAssetCompletion:
    """Caller-supplied declaration that no further writes are expected."""

    id: EntityId
    method: CompletedMediaAssetCompletionMethod
    is_finalized: bool
    finalized_at: datetime
    declaring_runtime_or_adapter_id: EntityId
    source_reference_ids: Sequence[EntityId] = field(default_factory=tuple)
    completion_marker_reference_id: EntityId | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        require_aware(
            self.finalized_at,
            "CompletedMediaAssetCompletion.finalized_at",
        )
        object.__setattr__(
            self,
            "source_reference_ids",
            normalize_entity_ids(
                self.source_reference_ids,
                "CompletedMediaAssetCompletion.source_reference_ids",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_metadata(self.metadata, "CompletedMediaAssetCompletion.metadata"),
        )
