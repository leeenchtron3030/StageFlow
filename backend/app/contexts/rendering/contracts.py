"""Immutable render intent and output identity. No filesystem or execution authority."""
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
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


class RenderError(RuntimeError):
    def __init__(self, code: RenderReason, *, retryable: bool = False) -> None:
        self.code = RenderReason(code)
        self.retryable = retryable
        super().__init__(self.code.value)


@dataclass(frozen=True, slots=True)
class RenderProfile:
    id: str = "h264-nvenc-1080p-video"
    version: str = "1"
    encoder: Literal["h264_nvenc"] = "h264_nvenc"
    preset: Literal["p4"] = "p4"
    rate_control: Literal["vbr"] = "vbr"
    bit_rate: int = 8_000_000
    gop: int = 60
    width: int = 1920
    height: int = 1080
    container: Literal["mp4"] = "mp4"
    decode: Literal["cuda"] = "cuda"
    audio: Literal[False] = False


FIRST_RENDER_PROFILE = RenderProfile()


def require_profile(profile: RenderProfile) -> None:
    if profile != FIRST_RENDER_PROFILE:
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
    profile: RenderProfile
    actor: RenderActor
    command_id: EntityId

    def __post_init__(self) -> None:
        require_profile(self.profile)
        if self.actor.authority_kind != "human":
            raise RenderError(RenderReason.HUMAN_REQUIRED)


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
        require_profile(self.profile)


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

    def __post_init__(self) -> None:
        if (self.media_type != "video/mp4"
                or self.profile_id != FIRST_RENDER_PROFILE.id
                or self.profile_version != FIRST_RENDER_PROFILE.version):
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
