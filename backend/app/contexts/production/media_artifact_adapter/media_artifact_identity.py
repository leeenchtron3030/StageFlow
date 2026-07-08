from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class MediaArtifactAdapterKind(StrEnum):
    FILESYSTEM_SOURCE = "filesystem_source"
    NETWORK_SOURCE = "network_source"
    CLOUD_SOURCE = "cloud_source"
    MANUAL_SOURCE = "manual_source"
    SIMULATED_SOURCE = "simulated_source"
    UNKNOWN = "unknown"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class MediaArtifactIdentity:
    """Generic identity information for a media artifact adapter."""

    adapter_name: str
    adapter_kind: MediaArtifactAdapterKind
    location_label: str | None = None
    stage_label: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.adapter_name.strip():
            raise ValueError("MediaArtifactIdentity adapter_name must not be empty.")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
