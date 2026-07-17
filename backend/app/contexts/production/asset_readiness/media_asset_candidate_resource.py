from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from app.contexts.production.completed_media_asset import (
    CompletedMediaAssetSourceLocation,
)
from app.shared.ids import EntityId

from .asset_readiness_validation import (
    freeze_readiness_metadata,
    require_non_empty,
    require_optional_non_empty,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class MediaAssetCandidateResource:
    """Descriptive resource identity before size or readiness becomes authoritative."""

    id: EntityId
    original_filename: str
    source_location: CompletedMediaAssetSourceLocation
    source_volume_id: EntityId | None = None
    source_host_id: EntityId | None = None
    media_type_hint: str | None = None
    container_type_hint: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        filename = require_non_empty(
            self.original_filename,
            "MediaAssetCandidateResource.original_filename",
        )
        if filename in {".", ".."} or "/" in filename or "\\" in filename:
            raise ValueError("Candidate filename must not contain a source path.")
        if (
            self.source_volume_id is not None
            and self.source_location.volume_id is not None
            and self.source_volume_id != self.source_location.volume_id
        ):
            raise ValueError("Candidate resource volume IDs must not conflict.")
        if (
            self.source_host_id is not None
            and self.source_location.host_id is not None
            and self.source_host_id != self.source_location.host_id
        ):
            raise ValueError("Candidate resource host IDs must not conflict.")
        object.__setattr__(self, "original_filename", filename)
        object.__setattr__(
            self,
            "media_type_hint",
            require_optional_non_empty(
                self.media_type_hint,
                "MediaAssetCandidateResource.media_type_hint",
            ),
        )
        object.__setattr__(
            self,
            "container_type_hint",
            require_optional_non_empty(
                self.container_type_hint,
                "MediaAssetCandidateResource.container_type_hint",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_readiness_metadata(
                self.metadata,
                "MediaAssetCandidateResource.metadata",
            ),
        )
