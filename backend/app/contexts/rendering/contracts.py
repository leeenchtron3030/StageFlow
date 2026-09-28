"""Immutable render intent and output identity. No filesystem or execution authority."""
import re
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from fractions import Fraction
from typing import Literal

from app.contexts.assembly.contracts import ContentReference
from app.contexts.assembly.session_contracts import AssemblyRevision, MetadataValue, positive
from app.shared.ids import EntityId
from app.shared.time.validation import require_aware_datetime


class RenderReason(StrEnum):
    NOT_APPROVED = "render_revision_not_approved"
    STALE = "render_revision_stale"
    NOT_VIDEO = "render_input_not_video"
    INPUT_MISSING = "input_missing"
    HASH_MISMATCH = "input_hash_mismatch"
    IDENTITY_REFUSED = "ffmpeg_identity_refused"
    EXIT_NONZERO = "ffmpeg_exit_nonzero"
    CUDA_FALLBACK = "cuda_decode_fallback"
    NVENC_UNAVAILABLE = "nvenc_unavailable"
    OUTPUT_INVALID = "render_output_invalid"
    STORE_UNAVAILABLE = "render_store_unavailable"
    INTERNAL = "render_internal_error"
    HUMAN_REQUIRED = "render_human_required"
    PROFILE_UNSUPPORTED = "render_profile_unsupported"
    METADATA_INVALID = "render_metadata_invalid"
    ADJUSTMENT_OUT_OF_BOUNDS = "render_adjustment_out_of_bounds"
    SETTING_CHANGED = "render_setting_changed"


class RenderError(RuntimeError):
    def __init__(self, code: RenderReason, *, retryable: bool = False) -> None:
        self.code = RenderReason(code)
        self.retryable = retryable
        super().__init__(self.code.value)


@dataclass(frozen=True, slots=True)
class RenderProfile:
    id: str = "h264-nvenc-1080p-video"
    version: str = "3"
    encoder: Literal["h264_nvenc"] = "h264_nvenc"
    preset: Literal["p4"] = "p4"
    rate_control: Literal["vbr"] = "vbr"
    bit_rate: int = 8_000_000
    gop: int = 60
    width: int = 1920
    height: int = 1080
    container: Literal["mp4"] = "mp4"
    decode: Literal["cuda"] = "cuda"
    audio_codec: Literal["aac"] | None = "aac"
    audio_sample_rate: int | None = 48000
    audio_channels: int | None = 2
    audio_bit_rate: int | None = 192000
    # None records v1's passthrough behavior; new requests require the current profile.
    output_frame_rate: Fraction | None = Fraction(30000, 1001)

    def __post_init__(self) -> None:
        if self.audio_codec is not None and (
            type(self.audio_codec) is not str or self.audio_codec != "aac"
        ):
            raise RenderError(RenderReason.PROFILE_UNSUPPORTED)
        for value in (self.audio_sample_rate, self.audio_channels, self.audio_bit_rate):
            if value is not None and (type(value) is not int or value <= 0):
                raise RenderError(RenderReason.PROFILE_UNSUPPORTED)
        if self.output_frame_rate is not None and type(self.output_frame_rate) is not Fraction:
            raise RenderError(RenderReason.PROFILE_UNSUPPORTED)


CURRENT_RENDER_PROFILE = RenderProfile()
RENDER_PROFILE_V1 = RenderProfile(version="1", output_frame_rate=None, audio_codec=None,
                                 audio_sample_rate=None, audio_channels=None, audio_bit_rate=None)
RENDER_PROFILE_V2 = RenderProfile(version="2", audio_codec=None, audio_sample_rate=None,
                                 audio_channels=None, audio_bit_rate=None)


@dataclass(frozen=True, slots=True)
class RenderAdjustments:
    video_bit_rate: int | None = None
    audio_bit_rate: int | None = None

    def __post_init__(self) -> None:
        for value in (self.video_bit_rate, self.audio_bit_rate):
            if value is not None and (type(value) is not int or value <= 0):
                raise RenderError(RenderReason.ADJUSTMENT_OUT_OF_BOUNDS)


@dataclass(frozen=True, slots=True)
class RenderPreset:
    profile: RenderProfile
    label: str
    video_min: int
    video_max: int
    audio_choices: tuple[int, ...]
    video_step: int = 500_000

    def __post_init__(self) -> None:
        object.__setattr__(self, "audio_choices", tuple(self.audio_choices))


RENDER_PRESETS = (
    RenderPreset(CURRENT_RENDER_PROFILE, "1080p Standard", 6_000_000, 12_000_000,
                 (128_000, 160_000, 192_000, 256_000)),
    RenderPreset(RenderProfile(id="h264-nvenc-1080p-high", version="1",
                               bit_rate=14_000_000, audio_bit_rate=256_000),
                 "1080p High", 10_000_000, 20_000_000, (192_000, 256_000, 320_000)),
    RenderPreset(RenderProfile(id="h264-nvenc-720p", version="1", width=1280, height=720,
                               bit_rate=4_000_000, audio_bit_rate=128_000),
                 "720p Compact", 3_000_000, 6_000_000, (96_000, 128_000, 160_000, 192_000)),
)


def render_preset(profile_id: str, version: str) -> RenderPreset:
    for preset in RENDER_PRESETS:
        if (preset.profile.id, preset.profile.version) == (profile_id, version):
            return preset
    raise RenderError(RenderReason.PROFILE_UNSUPPORTED)


def normalize_adjustments(
    preset: RenderPreset, adjustments: RenderAdjustments,
) -> RenderAdjustments:
    if type(adjustments) is not RenderAdjustments:
        raise RenderError(RenderReason.ADJUSTMENT_OUT_OF_BOUNDS)
    video, audio = adjustments.video_bit_rate, adjustments.audio_bit_rate
    if (video is not None and (not preset.video_min <= video <= preset.video_max
                              or (video - preset.video_min) % preset.video_step)):
        raise RenderError(RenderReason.ADJUSTMENT_OUT_OF_BOUNDS)
    if audio is not None and audio not in preset.audio_choices:
        raise RenderError(RenderReason.ADJUSTMENT_OUT_OF_BOUNDS)
    return RenderAdjustments(None if video == preset.profile.bit_rate else video,
                             None if audio == preset.profile.audio_bit_rate else audio)


def effective_profile(preset: RenderPreset, adjustments: RenderAdjustments) -> RenderProfile:
    if preset != render_preset(preset.profile.id, preset.profile.version):
        raise RenderError(RenderReason.PROFILE_UNSUPPORTED)
    value = normalize_adjustments(preset, adjustments)
    return replace(preset.profile, bit_rate=value.video_bit_rate or preset.profile.bit_rate,
                   audio_bit_rate=value.audio_bit_rate or preset.profile.audio_bit_rate)


def require_requestable(profile: RenderProfile) -> None:
    if (type(profile) is not RenderProfile
            or any(type(value) is not int for value in (
                profile.bit_rate, profile.gop, profile.width, profile.height,
                profile.audio_sample_rate, profile.audio_channels, profile.audio_bit_rate,
            ))
            or any(type(value) is not str for value in (
                profile.id, profile.version, profile.encoder, profile.preset,
                profile.rate_control, profile.container, profile.decode, profile.audio_codec,
            ))):
        raise RenderError(RenderReason.PROFILE_UNSUPPORTED)
    preset = render_preset(profile.id, profile.version)
    try:
        expected = effective_profile(preset, RenderAdjustments(profile.bit_rate,
                                                               profile.audio_bit_rate))
    except RenderError:
        raise RenderError(RenderReason.PROFILE_UNSUPPORTED) from None
    if profile != expected:
        raise RenderError(RenderReason.PROFILE_UNSUPPORTED)


@dataclass(frozen=True, slots=True)
class RenderActor:
    id: EntityId
    authority_kind: Literal["human"] = "human"

    def __post_init__(self) -> None:
        if self.authority_kind != "human":
            raise RenderError(RenderReason.HUMAN_REQUIRED)


@dataclass(frozen=True, slots=True)
class RenderRequest:
    assembly_revision_id: EntityId
    profile: RenderProfile | None
    actor: RenderActor
    command_id: EntityId
    expected_setting_version: int | None | Literal["unspecified"] = "unspecified"
    requested_profile_id: str | None = None
    requested_profile_version: str | None = None

    def __post_init__(self) -> None:
        if self.profile is not None:
            require_requestable(self.profile)
        if self.actor.authority_kind != "human":
            raise RenderError(RenderReason.HUMAN_REQUIRED)
        if (self.expected_setting_version != "unspecified"
                and self.expected_setting_version is not None):
            if type(self.expected_setting_version) is not int or self.expected_setting_version <= 0:
                raise ValueError("render_setting_version_invalid")


@dataclass(frozen=True, slots=True)
class VideoInput:
    reference: ContentReference
    media_type: str


@dataclass(frozen=True, slots=True)
class RenderManifest:
    assembly_revision_id: EntityId
    session_id: EntityId
    event_id: EntityId
    profile_id: str
    profile_version: str
    metadata: tuple[MetadataValue, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", tuple(self.metadata))
        # Metadata has a closed shape: immutable provenance and tuple-of-string values.
        # Reject mutable/unknown nested values rather than retaining caller-owned objects.
        if any(type(value) is not str for entry in self.metadata for value in entry.values):
            raise RenderError(RenderReason.METADATA_INVALID)


@dataclass(frozen=True, slots=True)
class RenderPlan:
    revision: AssemblyRevision
    profile: RenderProfile
    inputs: tuple[VideoInput, ...]
    manifest: RenderManifest

    def __post_init__(self) -> None:
        object.__setattr__(self, "inputs", tuple(self.inputs))
        require_requestable(self.profile)


@dataclass(frozen=True, slots=True)
class FFmpegIdentity:
    version: str
    sha256: str

    def __post_init__(self) -> None:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+~-]{0,79}", self.version) is None:
            raise RenderError(RenderReason.IDENTITY_REFUSED)
        if re.fullmatch(r"[0-9a-f]{64}", self.sha256) is None:
            raise RenderError(RenderReason.IDENTITY_REFUSED)


@dataclass(frozen=True, slots=True)
class RenderedOutput:
    id: EntityId
    assembly_revision_id: EntityId
    profile_id: str
    profile_version: str
    operation_id: EntityId
    producing_attempt_id: EntityId
    content_key: str
    sha256: str
    manifest_content_key: str
    manifest_sha256: str
    byte_size: int
    media_type: Literal["video/mp4"]
    duration_microseconds: int
    frame_count: int
    ffmpeg: FFmpegIdentity
    produced_at: datetime
    video_bit_rate: int | None = None
    audio_bit_rate: int | None = None
    event_render_setting_version: int | None = None

    def __post_init__(self) -> None:
        if (self.media_type != "video/mp4"
                or (self.profile_id, self.profile_version) not in (
                    *((p.profile.id, p.profile.version) for p in RENDER_PRESETS),
                    (RENDER_PROFILE_V1.id, RENDER_PROFILE_V1.version),
                    (RENDER_PROFILE_V2.id, RENDER_PROFILE_V2.version))):
            raise RenderError(RenderReason.OUTPUT_INVALID)
        for name in ("content_key", "manifest_content_key"):
            if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", getattr(self, name)) is None:
                raise RenderError(RenderReason.OUTPUT_INVALID)
        for name in ("sha256", "manifest_sha256"):
            if re.fullmatch(r"[0-9a-f]{64}", getattr(self, name)) is None:
                raise RenderError(RenderReason.OUTPUT_INVALID)
        for name in ("byte_size", "duration_microseconds", "frame_count"):
            positive(getattr(self, name), name)
        require_aware_datetime(self.produced_at, "produced_at")
