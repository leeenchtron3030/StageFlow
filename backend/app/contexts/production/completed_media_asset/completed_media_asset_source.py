from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.shared.ids import EntityId

from .completed_media_asset_validation import (
    freeze_metadata,
    normalize_strings,
    require_optional_non_empty,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


class CompletedMediaAssetRuntimeProfile(StrEnum):
    AGENT = "agent"
    NODE = "node"
    EXTERNAL_COMPATIBLE_SOURCE = "external_compatible_source"
    DEVELOPMENT = "development"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CompletedMediaAssetSource:
    """Deployment provenance for the Runtime that declared the completed asset."""

    runtime_id: EntityId
    runtime_profile: CompletedMediaAssetRuntimeProfile
    host_id: EntityId | None = None
    recorder_application_id: EntityId | None = None
    recorder_application_version: str | None = None
    adapter_id: EntityId | None = None
    producer_id: EntityId | None = None
    source_event_id: EntityId | None = None
    compatibility_identifiers: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "recorder_application_version",
            require_optional_non_empty(
                self.recorder_application_version,
                "CompletedMediaAssetSource.recorder_application_version",
            ),
        )
        object.__setattr__(
            self,
            "compatibility_identifiers",
            normalize_strings(
                self.compatibility_identifiers,
                "CompletedMediaAssetSource.compatibility_identifiers",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_metadata(self.metadata, "CompletedMediaAssetSource.metadata"),
        )
