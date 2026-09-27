"""Bounded production inspection policy; recorder semantics remain unqualified."""
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

from app.shared.ids import EntityId

from .contracts import (
    MediaTimingDerivation,
    MediaTimingInspectionProvenance,
    MediaTimingInspectionResult,
    MediaTimingObservation,
    RecorderProfileQualification,
    RecorderProfileQualificationStatus,
    TimingTimezoneKind,
)

UNQUALIFIED = (
    "creation_time recording-start versus file-open semantics are unqualified",
    "container duration is not qualified as exact captured-content duration",
)


class MediaTimingError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool = False) -> None:
        if code not in {
            "media_timing_tool_unavailable", "media_timing_tool_refused",
            "media_timing_output_invalid", "media_timing_timeout", "input_missing",
            "media_timing_internal",
        }:
            code, retryable = "media_timing_internal", False
        self.code = code
        self.retryable = retryable
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class InspectionProfile:
    id: str = "container-creation-time"
    version: str = "1"
    rule_id: str = "creation_time_plus_duration"
    rule_version: str = "1"
    tool_id: str = "ffprobe"


CURRENT_INSPECTION_PROFILE = InspectionProfile()


@dataclass(frozen=True, slots=True)
class InspectionFields:
    creation_time: str | None
    container_duration: str | None
    video_start: str | None
    video_duration: str | None


def inspection_result(
    fields: InspectionFields, *, version: str, digest: str, inspected_at: datetime,
    profile: InspectionProfile = CURRENT_INSPECTION_PROFILE,
) -> MediaTimingInspectionResult:
    if profile != CURRENT_INSPECTION_PROFILE:
        raise MediaTimingError("media_timing_tool_refused")
    observations: list[MediaTimingObservation] = []
    limitations: list[str] = list(UNQUALIFIED)
    started: datetime | None = None
    duration: timedelta | None = None
    creation_id, duration_id = EntityId.new(), EntityId.new()
    original = fields.creation_time
    if original is None:
        limitations.append("creation_time_missing")
    else:
        timezone = TimingTimezoneKind.NAIVE_UNQUALIFIED
        issues: tuple[str, ...] = ()
        # Only timestamp-shaped text can be retained; arbitrary metadata is discarded.
        safe = (bool(original.strip()) and len(original) <= 64
                and re.fullmatch(r"[0-9TtZz :.+-]+", original))
        try:
            value = datetime.fromisoformat(original) if safe else None
            if value is None:
                raise ValueError
            if value.tzinfo is None or value.utcoffset() is None:
                issues = ("creation_time_timezone_unknown",)
            else:
                timezone = (TimingTimezoneKind.EXPLICIT_UTC if value.utcoffset() == timedelta(0)
                            else TimingTimezoneKind.EXPLICIT_OFFSET)
                started = value.astimezone(UTC)
        except (ValueError, OverflowError):
            issues = ("creation_time_invalid",)
        limitations.extend(issues)
        if safe:
            observations.append(MediaTimingObservation(
                creation_id, "creation_time", "format.tags.creation_time", original,
                inspected_at, timezone, normalized_timestamp=started, limitations=issues,
            ))
    for name, raw, source, identifier in (
        ("container_duration", fields.container_duration, "format.duration", duration_id),
        ("video_start", fields.video_start, "stream.start_time", EntityId.new()),
        ("video_duration", fields.video_duration, "stream.duration", EntityId.new()),
    ):
        if raw is None:
            if name == "container_duration":
                limitations.append("container_duration_missing")
            continue
        try:
            if len(raw) > 64 or re.fullmatch(r"[+-]?[0-9]+(?:\.[0-9]+)?", raw) is None:
                raise ValueError
            seconds = Decimal(raw)
            if abs(seconds) > 315_576_000 or (name != "video_start" and seconds < 0):
                raise ValueError
            measured = timedelta(microseconds=int(seconds * 1_000_000))
        except (ValueError, InvalidOperation, OverflowError):
            limitations.append(name + "_invalid")
            continue
        observations.append(MediaTimingObservation(
            identifier, name, source, raw, inspected_at, TimingTimezoneKind.NOT_APPLICABLE,
            normalized_duration=None if name == "video_start" else measured,
            normalized_value=str(seconds) if name == "video_start" else None,
            precision="microseconds",
            stream_selector=None if name == "container_duration" else "v:0",
        ))
        if name == "container_duration":
            duration = measured
    derivations: tuple[MediaTimingDerivation, ...] = ()
    if started is not None and duration is not None:
        try:
            ended = started + duration
        except OverflowError:
            limitations.append("candidate_interval_out_of_range")
        else:
            derivations = (MediaTimingDerivation(
                EntityId.new(), profile.rule_id, profile.rule_version, (creation_id, duration_id),
                started, ended, inspected_at, UNQUALIFIED,
            ),)
    return MediaTimingInspectionResult(
        MediaTimingInspectionProvenance(
            profile.id, profile.version, profile.tool_id + ":sha256:" + digest,
            version, "unspecified-recorder", 1, inspected_at,
        ),
        tuple(observations), derivations,
        RecorderProfileQualification("unspecified-recorder", 1,
            RecorderProfileQualificationStatus.UNQUALIFIED, inspected_at,
            limitations=UNQUALIFIED),
        tuple(limitations),
    )
