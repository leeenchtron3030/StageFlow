from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class VisionAdapterKind(StrEnum):
    LOCAL_VISION_SOURCE = "local_vision_source"
    CLOUD_VISION_SOURCE = "cloud_vision_source"
    CAMERA_ANALYSIS_SOURCE = "camera_analysis_source"
    MANUAL_ANNOTATION_SOURCE = "manual_annotation_source"
    SIMULATED_SOURCE = "simulated_source"
    UNKNOWN = "unknown"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class VisionAdapterIdentity:
    """Generic identity information for a vision source adapter."""

    adapter_name: str
    adapter_kind: VisionAdapterKind
    stage_label: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.adapter_name.strip():
            raise ValueError("VisionAdapterIdentity adapter_name must not be empty.")
        if self.stage_label is not None and not self.stage_label.strip():
            raise ValueError("VisionAdapterIdentity stage_label must not be empty.")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
