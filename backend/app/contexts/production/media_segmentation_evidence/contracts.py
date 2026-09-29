"""Bounded immutable observations and fixed segmentation profile lineage."""
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.shared.ids import EntityId
from app.shared.time import require_aware_datetime

MAX_INTERVALS = 10_000
MAX_OFFSET_US = 315_576_000_000_000


class MediaSegmentationError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool = False) -> None:
        if code not in {
            "render_identity_refused", "input_missing", "render_exit_nonzero",
            "render_output_invalid", "media_segmentation_interval_limit",
            "media_segmentation_timeout", "media_segmentation_internal",
        }:
            code, retryable = "media_segmentation_internal", False
        self.code, self.retryable = code, retryable
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SegmentationProfile:
    id: str = "freeze-silence"
    version: str = "1"
    video_filter: str = "fps=5,scale=320:-2,freezedetect=n=0.003:d=4"
    audio_filter: str = "silencedetect=n=-40dB:d=3"
    decode: str = "cpu"
    demuxer_allowlist: str = "mov,mp4,m4a,3gp,3g2,mj2,matroska,webm,mxf,wav"


CURRENT_SEGMENTATION_PROFILE = SegmentationProfile()


@dataclass(frozen=True, slots=True)
class SegmentationInterval:
    kind: Literal["freeze", "silence"]
    start_microseconds: int
    end_microseconds: int
    profile_id: str = CURRENT_SEGMENTATION_PROFILE.id
    profile_version: str = CURRENT_SEGMENTATION_PROFILE.version

    def __post_init__(self) -> None:
        if (self.kind not in {"freeze", "silence"}
                or type(self.start_microseconds) is not int
                or type(self.end_microseconds) is not int
                or not 0 <= self.start_microseconds < self.end_microseconds <= MAX_OFFSET_US
                or (self.profile_id, self.profile_version) != (
                    CURRENT_SEGMENTATION_PROFILE.id, CURRENT_SEGMENTATION_PROFILE.version)):
            raise ValueError("media_segmentation_interval_invalid")


@dataclass(frozen=True, slots=True)
class SegmentationResult:
    intervals: tuple[SegmentationInterval, ...]
    duration_microseconds: int
    ffmpeg_version: str
    ffmpeg_sha256: str
    inspected_at: datetime
    profile: SegmentationProfile = CURRENT_SEGMENTATION_PROFILE

    def __post_init__(self) -> None:
        require_aware_datetime(self.inspected_at, "inspected_at")
        intervals = tuple(self.intervals)
        if len(intervals) > MAX_INTERVALS:
            raise MediaSegmentationError("media_segmentation_interval_limit")
        if (type(self.duration_microseconds) is not int
                or not 0 < self.duration_microseconds <= MAX_OFFSET_US
                or self.profile != CURRENT_SEGMENTATION_PROFILE
                or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+~-]{0,127}",
                                self.ffmpeg_version) is None
                or re.fullmatch(r"[0-9a-f]{64}", self.ffmpeg_sha256) is None):
            raise ValueError("media_segmentation_result_invalid")
        previous: dict[str, int] = {}
        for item in intervals:
            if (item.end_microseconds > self.duration_microseconds
                    or item.start_microseconds < previous.get(item.kind, 0)):
                raise ValueError("media_segmentation_interval_order_invalid")
            previous[item.kind] = item.end_microseconds
        object.__setattr__(self, "intervals", tuple(sorted(
            intervals, key=lambda item: (item.start_microseconds, item.kind))))


@dataclass(frozen=True, slots=True)
class MediaSegmentationEvidence:
    id: EntityId
    operation_id: EntityId
    asset_id: EntityId
    manifest_id: EntityId
    manifest_version: str
    producing_attempt_id: EntityId
    result: SegmentationResult
    recorded_at: datetime

    def __post_init__(self) -> None:
        require_aware_datetime(self.recorded_at, "recorded_at")
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", self.manifest_version) is None:
            raise ValueError("media_segmentation_manifest_version_invalid")
