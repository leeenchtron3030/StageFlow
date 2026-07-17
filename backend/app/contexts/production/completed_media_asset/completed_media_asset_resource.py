from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit

from app.shared.ids import EntityId

from .completed_media_asset_validation import (
    freeze_metadata,
    require_non_empty,
    require_optional_aware,
    require_optional_non_empty,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


class CompletedMediaAssetLocationScheme(StrEnum):
    LOCAL_FILESYSTEM = "local_filesystem"
    MOUNTED_VOLUME = "mounted_volume"
    STORAGE_DEVICE_RELATIVE = "storage_device_relative"
    NETWORK_SHARE = "network_share"
    URI = "uri"
    OTHER_SUPPORTED_LOCATION = "other_supported_location"
    UNKNOWN = "unknown"


class CompletedMediaAssetRelatedResourceKind(StrEnum):
    RECORDER_SIDECAR_METADATA = "recorder_sidecar_metadata"
    CHECKSUM_SIDECAR = "checksum_sidecar"
    CAPTION_SIDECAR = "caption_sidecar"
    WAVEFORM_SIDECAR = "waveform_sidecar"
    RECORDER_MARKER = "recorder_marker"
    OTHER_SUPPORTED_RESOURCE = "other_supported_resource"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CompletedMediaAssetSourceLocation:
    """Small descriptive source reference with no access or mounting behavior."""

    location_scheme: CompletedMediaAssetLocationScheme
    location_value: str
    volume_id: EntityId | None = None
    host_id: EntityId | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        location = require_non_empty(
            self.location_value,
            "CompletedMediaAssetSourceLocation.location_value",
        )
        if "\x00" in location:
            raise ValueError("Source location must not contain a null byte.")
        parsed = urlsplit(location)
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("Source location must not embed credentials.")
        object.__setattr__(self, "location_value", location)
        object.__setattr__(
            self,
            "metadata",
            freeze_metadata(
                self.metadata,
                "CompletedMediaAssetSourceLocation.metadata",
            ),
        )


@dataclass(frozen=True, slots=True)
class CompletedMediaAssetResource:
    """Immutable reference to the primary finalized media resource."""

    id: EntityId
    original_filename: str
    source_location: CompletedMediaAssetSourceLocation
    file_size_bytes: int
    media_type: str | None = None
    container_type: str | None = None
    filesystem_created_at: datetime | None = None
    filesystem_modified_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        filename = require_non_empty(
            self.original_filename,
            "CompletedMediaAssetResource.original_filename",
        )
        if filename in {".", ".."} or "/" in filename or "\\" in filename:
            raise ValueError("Original filename must not contain a source path.")
        if self.file_size_bytes < 0:
            raise ValueError("Completed media resource file size must not be negative.")
        object.__setattr__(self, "original_filename", filename)
        object.__setattr__(
            self,
            "media_type",
            require_optional_non_empty(
                self.media_type,
                "CompletedMediaAssetResource.media_type",
            ),
        )
        object.__setattr__(
            self,
            "container_type",
            require_optional_non_empty(
                self.container_type,
                "CompletedMediaAssetResource.container_type",
            ),
        )
        require_optional_aware(
            self.filesystem_created_at,
            "CompletedMediaAssetResource.filesystem_created_at",
        )
        require_optional_aware(
            self.filesystem_modified_at,
            "CompletedMediaAssetResource.filesystem_modified_at",
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_metadata(self.metadata, "CompletedMediaAssetResource.metadata"),
        )

    @property
    def source_volume_id(self) -> EntityId | None:
        return self.source_location.volume_id


@dataclass(frozen=True, slots=True)
class CompletedMediaAssetResourceReference:
    """ID-only or lightweight reference to one optional associated resource."""

    resource_id: EntityId
    resource_kind: CompletedMediaAssetRelatedResourceKind
    label: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "label",
            require_optional_non_empty(
                self.label,
                "CompletedMediaAssetResourceReference.label",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_metadata(
                self.metadata,
                "CompletedMediaAssetResourceReference.metadata",
            ),
        )
