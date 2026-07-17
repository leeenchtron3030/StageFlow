from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum
from typing import Any

from .completed_media_asset_validation import (
    freeze_metadata,
    require_non_negative_duration,
    require_optional_non_empty,
    require_positive_number,
)


def _empty_metadata() -> Mapping[str, Any]:
    return {}


class CompletedMediaAssetFrameRateMode(StrEnum):
    CONSTANT = "constant"
    VARIABLE = "variable"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CompletedMediaAssetTechnicalDescription:
    """Optional probe-compatible media facts with no compatibility policy."""

    container_format: str | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    width: int | None = None
    height: int | None = None
    frame_rate: float | None = None
    audio_sample_rate: int | None = None
    audio_channel_count: int | None = None
    duration: timedelta | None = None
    timecode_start: str | None = None
    timecode_end: str | None = None
    frame_rate_mode: CompletedMediaAssetFrameRateMode | None = None
    media_stream_count: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        for field_name in (
            "container_format",
            "video_codec",
            "audio_codec",
            "timecode_start",
            "timecode_end",
        ):
            object.__setattr__(
                self,
                field_name,
                require_optional_non_empty(
                    getattr(self, field_name),
                    f"CompletedMediaAssetTechnicalDescription.{field_name}",
                ),
            )
        require_positive_number(
            self.width,
            "CompletedMediaAssetTechnicalDescription.width",
        )
        require_positive_number(
            self.height,
            "CompletedMediaAssetTechnicalDescription.height",
        )
        require_positive_number(
            self.frame_rate,
            "CompletedMediaAssetTechnicalDescription.frame_rate",
        )
        require_positive_number(
            self.audio_sample_rate,
            "CompletedMediaAssetTechnicalDescription.audio_sample_rate",
        )
        require_positive_number(
            self.audio_channel_count,
            "CompletedMediaAssetTechnicalDescription.audio_channel_count",
        )
        require_positive_number(
            self.media_stream_count,
            "CompletedMediaAssetTechnicalDescription.media_stream_count",
        )
        require_non_negative_duration(
            self.duration,
            "CompletedMediaAssetTechnicalDescription.duration",
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_metadata(
                self.metadata,
                "CompletedMediaAssetTechnicalDescription.metadata",
            ),
        )
