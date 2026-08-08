from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.shared.metadata import freeze_metadata


class TranscriptAdapterKind(StrEnum):
    LOCAL_TRANSCRIPTION_SOURCE = "local_transcription_source"
    CLOUD_TRANSCRIPTION_SOURCE = "cloud_transcription_source"
    CAPTION_SOURCE = "caption_source"
    MANUAL_TRANSCRIPT_SOURCE = "manual_transcript_source"
    SIMULATED_SOURCE = "simulated_source"
    UNKNOWN = "unknown"


def _empty_metadata() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class TranscriptAdapterIdentity:
    """Generic identity information for a transcript source adapter."""

    adapter_name: str
    adapter_kind: TranscriptAdapterKind
    stage_label: str | None = None
    language_label: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if not self.adapter_name.strip():
            raise ValueError("TranscriptAdapterIdentity adapter_name must not be empty.")
        if self.stage_label is not None and not self.stage_label.strip():
            raise ValueError("TranscriptAdapterIdentity stage_label must not be empty.")
        if self.language_label is not None and not self.language_label.strip():
            raise ValueError("TranscriptAdapterIdentity language_label must not be empty.")
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
