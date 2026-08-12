from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.shared.metadata import freeze_metadata


class RecordingAdapterKind(StrEnum):
    SOFTWARE_RECORDER = "software_recorder"
    HARDWARE_RECORDER = "hardware_recorder"
    LIVESTREAM_ENCODER = "livestream_encoder"
    MANUAL_OPERATOR = "manual_operator"
    SIMULATED_RECORDER = "simulated_recorder"
    UNKNOWN = "unknown"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class RecordingAdapterIdentity:
    """Generic identity information for a recording system adapter."""

    adapter_name: str
    adapter_kind: RecordingAdapterKind
    location_label: str | None = None
    stage_label: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.adapter_name.strip():
            raise ValueError("RecordingAdapterIdentity adapter_name must not be empty.")
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
