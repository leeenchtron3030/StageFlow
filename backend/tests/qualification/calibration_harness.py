"""Deterministic, qualification-only recorder calibration tooling.

The generated markers and reports are External test evidence. They are deliberately
isolated from production imports and prohibited from changing StageFlow authority.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import re
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Any, cast

try:
    from qualification import media_timing_probe as timing_probe
except ModuleNotFoundError:  # Direct execution places this directory on sys.path.
    import media_timing_probe as timing_probe

HARNESS_NAME = "stageflow-recorder-calibration-harness"
HARNESS_VERSION = "1.0"
SOURCE_SCHEMA = "stageflow.recorder-calibration-source"
REPORT_SCHEMA = "stageflow.recorder-calibration-report"
SUMMARY_SCHEMA = "stageflow.recorder-calibration-summary"
SCHEMA_VERSION = "1.0"
MARKER_SCHEMA = "binary-frame-clock-v1"
DEFAULT_COUNTER_BITS = 24
DEFAULT_CELL_WIDTH = 8
DEFAULT_CELL_HEIGHT = 8
SYNC_PATTERN = (1, 0, 1, 0)
HARD_MAX_DECODE_BYTES = 128 * 1024 * 1024
HARD_MAX_REPORT_BYTES = 5 * 1024 * 1024
HARD_MAX_REPORTS = 100
SAFE_VALUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:=+ -]{0,199}$")
SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)(authorization|credential|password|private[_ -]?key|secret|token)\s*[:=]"
)


class CalibrationError(RuntimeError):
    """An operator-correctable error with a privacy-safe message."""


def _safe_value(value: str, field_name: str) -> str:
    normalized = value.strip()
    if SAFE_VALUE.fullmatch(normalized) is None or SENSITIVE_ASSIGNMENT.search(normalized):
        raise CalibrationError(f"{field_name} is not a sanitized value")
    return normalized


def _aware_utc(value: str, field_name: str) -> datetime:
    parsed = timing_probe.parse_aware_timestamp(value)
    if parsed is None:
        raise CalibrationError(f"{field_name} must be a timezone-aware timestamp")
    return parsed.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class MarkerSpec:
    frame_rate: int
    counter_bits: int = DEFAULT_COUNTER_BITS
    cell_width: int = DEFAULT_CELL_WIDTH
    cell_height: int = DEFAULT_CELL_HEIGHT

    def __post_init__(self) -> None:
        if self.frame_rate < 1 or self.frame_rate > 120:
            raise CalibrationError("frame-rate is outside the supported bound")
        if self.counter_bits < 8 or self.counter_bits > 32:
            raise CalibrationError("counter-bits is outside the supported bound")
        if self.cell_width < 4 or self.cell_width > 32:
            raise CalibrationError("cell-width is outside the supported bound")
        if self.cell_height < 4 or self.cell_height > 32:
            raise CalibrationError("cell-height is outside the supported bound")

    @property
    def marker_cells(self) -> int:
        return len(SYNC_PATTERN) + self.counter_bits

    @property
    def marker_width(self) -> int:
        return self.marker_cells * self.cell_width

    @property
    def precision_seconds(self) -> float:
        return 1 / self.frame_rate


@dataclass(frozen=True, slots=True)
class TrialContext:
    trial_id: str
    condition: str
    batch_id: str
    repetition: int
    recorder_product: str
    recorder_version: str
    recorder_profile_id: str
    recorder_profile_revision: int
    segment_duration_seconds: float
    vmix_exercised: bool
    clock_status: str
    clock_source: str
    timeline_origin_utc: datetime | None
    configuration: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "trial_id",
            "condition",
            "batch_id",
            "recorder_product",
            "recorder_version",
            "recorder_profile_id",
            "clock_status",
            "clock_source",
        ):
            object.__setattr__(self, field_name, _safe_value(getattr(self, field_name), field_name))
        if self.repetition < 1:
            raise CalibrationError("repetition must be positive")
        if self.recorder_profile_revision < 1:
            raise CalibrationError("recorder-profile-revision must be positive")
        if not math.isfinite(self.segment_duration_seconds) or self.segment_duration_seconds <= 0:
            raise CalibrationError("segment-duration-seconds must be positive and finite")
        if self.timeline_origin_utc is not None:
            if (
                self.timeline_origin_utc.tzinfo is None
                or self.timeline_origin_utc.utcoffset() is None
            ):
                raise CalibrationError("timeline origin must be timezone-aware")
            object.__setattr__(
                self,
                "timeline_origin_utc",
                self.timeline_origin_utc.astimezone(UTC),
            )
        object.__setattr__(
            self,
            "configuration",
            tuple(sorted({_safe_value(value, "configuration") for value in self.configuration})),
        )


def _escape_filter_expression(expression: str) -> str:
    return expression.replace(",", r"\,")


def build_video_filter(
    *,
    spec: MarkerSpec,
    duration_seconds: float,
    boundary_seconds: float,
    width: int,
    height: int,
) -> str:
    if duration_seconds < 2 or not math.isfinite(duration_seconds):
        raise CalibrationError("duration-seconds must be finite and at least two")
    if boundary_seconds <= 0 or not math.isfinite(boundary_seconds):
        raise CalibrationError("boundary-seconds must be positive and finite")
    if width < spec.marker_width or height < 96:
        raise CalibrationError("video dimensions are too small for calibration markers")

    filters = [
        (
            "drawbox=x=0:y=0:w=iw:h=ih:color=green@0.55:t=fill:"
            f"enable='{_escape_filter_expression('lt(t,1)')}'"
        ),
        (
            "drawbox=x=0:y=0:w=iw:h=ih:color=blue@0.55:t=fill:"
            f"enable='{_escape_filter_expression(f'gte(t,{duration_seconds - 1:g})')}'"
        ),
        (
            f"drawbox=x=0:y=0:w={spec.marker_width}:h={spec.cell_height}:"
            "color=black:t=fill"
        ),
    ]
    for index, value in enumerate(SYNC_PATTERN):
        if value:
            filters.append(
                f"drawbox=x={index * spec.cell_width}:y=0:w={spec.cell_width}:"
                f"h={spec.cell_height}:color=white:t=fill"
            )
    for bit in range(spec.counter_bits):
        expression = _escape_filter_expression(
            f"gte(mod(floor((t*{spec.frame_rate}+0.5)/{2**bit}),2),1)"
        )
        filters.append(
            f"drawbox=x={(len(SYNC_PATTERN) + bit) * spec.cell_width}:y=0:"
            f"w={spec.cell_width}:h={spec.cell_height}:color=white:t=fill:"
            f"enable='{expression}'"
        )
    filters.extend(
        [
            (
                "drawbox=x=0:y=24:w=iw:h=12:color=white@0.85:t=fill:"
                f"enable='{_escape_filter_expression('lt(mod(t,1),0.08)')}'"
            ),
            (
                "drawbox=x=0:y=42:w=iw:h=18:color=red@0.85:t=fill:"
                f"enable='{_escape_filter_expression(f'lt(mod(t,{boundary_seconds:g}),0.16)')}'"
            ),
        ]
    )
    return ",".join(filters)


def build_audio_source(*, duration_seconds: float, boundary_seconds: float) -> str:
    if duration_seconds < 2 or boundary_seconds <= 0:
        raise CalibrationError("audio marker durations must be positive")
    once_per_second = "0.72*sin(2*PI*1000*t)*lt(mod(t\\,1)\\,0.025)"
    boundary = (
        "0.20*sin(2*PI*1700*t)*"
        f"lt(mod(t\\,{boundary_seconds:g})\\,0.075)"
    )
    start = "0.16*sin(2*PI*500*t)*lt(t\\,0.40)"
    end = f"0.16*sin(2*PI*750*t)*gte(t\\,{duration_seconds - 0.40:g})"
    return f"aevalsrc={once_per_second}+{boundary}+{start}+{end}:s=48000:d={duration_seconds:g}"


def build_generation_command(
    executable: str,
    output: Path,
    *,
    spec: MarkerSpec,
    duration_seconds: float,
    boundary_seconds: float,
    width: int,
    height: int,
    timeline_origin_utc: datetime,
) -> list[str]:
    video_filter = build_video_filter(
        spec=spec,
        duration_seconds=duration_seconds,
        boundary_seconds=boundary_seconds,
        width=width,
        height=height,
    )
    return [
        executable,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-n",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size={width}x{height}:rate={spec.frame_rate}:duration={duration_seconds:g}",
        "-f",
        "lavfi",
        "-i",
        build_audio_source(
            duration_seconds=duration_seconds,
            boundary_seconds=boundary_seconds,
        ),
        "-vf",
        video_filter,
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-g",
        str(spec.frame_rate),
        "-keyint_min",
        str(spec.frame_rate),
        "-sc_threshold",
        "0",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-metadata",
        f"creation_time={timeline_origin_utc.astimezone(UTC).isoformat()}",
        "-movflags",
        "+faststart",
        "-shortest",
        os.fspath(output),
    ]


def _atomic_create(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise CalibrationError("output already exists") from exc
        except OSError as exc:
            raise CalibrationError("output could not be published atomically") from exc
    finally:
        temporary.unlink(missing_ok=True)


def generate_source(
    executable: str,
    output: Path,
    manifest_output: Path,
    *,
    source_alias: str,
    spec: MarkerSpec,
    duration_seconds: float,
    boundary_seconds: float,
    width: int,
    height: int,
    timeline_origin_utc: datetime,
) -> dict[str, Any]:
    alias = _safe_value(source_alias, "source-alias")
    if output.resolve(strict=False) == manifest_output.resolve(strict=False):
        raise CalibrationError("source and manifest outputs must be different paths")
    if output.exists() or manifest_output.exists():
        raise CalibrationError("output already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    tool = timing_probe.inspect_tool(executable)
    command = build_generation_command(
        executable,
        output,
        spec=spec,
        duration_seconds=duration_seconds,
        boundary_seconds=boundary_seconds,
        width=width,
        height=height,
        timeline_origin_utc=timeline_origin_utc,
    )
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            timeout=max(120, int(duration_seconds * 3)),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        output.unlink(missing_ok=True)
        raise CalibrationError("calibration source generation could not complete") from exc
    if completed.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
        output.unlink(missing_ok=True)
        raise CalibrationError("calibration source generation failed")

    origin = timeline_origin_utc.astimezone(UTC)
    manifest: dict[str, Any] = {
        "schema_name": SOURCE_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "harness": {"name": HARNESS_NAME, "version": HARNESS_VERSION},
        "source_alias": alias,
        "inspection_tool": tool,
        "timeline_origin_utc": origin.isoformat(),
        "duration_seconds": duration_seconds,
        "frame_rate": spec.frame_rate,
        "dimensions": f"{width}x{height}",
        "boundary_marker_seconds": boundary_seconds,
        "marker": {
            "schema": MARKER_SCHEMA,
            "counter_bits": spec.counter_bits,
            "cell_width": spec.cell_width,
            "cell_height": spec.cell_height,
            "sync_pattern": list(SYNC_PATTERN),
            "precision_seconds": spec.precision_seconds,
        },
        "audio_markers": {
            "once_per_second_hz": 1000,
            "boundary_hz": 1700,
            "start_hz": 500,
            "end_hz": 750,
        },
        "epistemic_kind": "external_calibration_source",
        "authority_use_prohibited": True,
        "limitations": [
            "timeline origin becomes wall-clock evidence only with an independently "
            "verified real-time playback start",
            "generated source does not exercise vMix or qualify a recorder profile",
        ],
    }
    try:
        _atomic_create(
            manifest_output,
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        )
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return manifest


def build_marker_decode_command(executable: str, media: Path, spec: MarkerSpec) -> list[str]:
    marker_filter = (
        f"crop={spec.marker_width}:{spec.cell_height}:0:0,"
        f"scale={spec.marker_cells}:1:flags=area,format=gray"
    )
    return [
        executable,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        os.fspath(media),
        "-map",
        "0:v:0",
        "-vf",
        marker_filter,
        "-fps_mode",
        "passthrough",
        "-frames:v",
        str(HARD_MAX_DECODE_BYTES // spec.marker_cells),
        "-f",
        "rawvideo",
        "-pix_fmt",
        "gray",
        "-",
    ]


def run_marker_decode(executable: str, media: Path, spec: MarkerSpec) -> bytes:
    try:
        completed = subprocess.run(
            build_marker_decode_command(executable, media, spec),
            check=False,
            capture_output=True,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CalibrationError("content marker decode could not complete") from exc
    if completed.returncode != 0:
        raise CalibrationError("content marker decode failed")
    maximum_payload = (HARD_MAX_DECODE_BYTES // spec.marker_cells) * spec.marker_cells
    if len(completed.stdout) >= maximum_payload:
        raise CalibrationError("content marker decode exceeded its output bound")
    return completed.stdout


def decode_marker_payload(payload: bytes, spec: MarkerSpec) -> dict[str, Any]:
    frame_size = spec.marker_cells
    if not payload or len(payload) % frame_size:
        raise CalibrationError("decoded marker stream has an invalid size")
    indices: list[int] = []
    invalid_frames = 0
    for offset in range(0, len(payload), frame_size):
        cells = payload[offset : offset + frame_size]
        values = tuple(1 if value >= 128 else 0 for value in cells)
        if values[: len(SYNC_PATTERN)] != SYNC_PATTERN:
            invalid_frames += 1
            continue
        counter = sum(
            value << bit
            for bit, value in enumerate(values[len(SYNC_PATTERN) :])
        )
        indices.append(counter)
    if not indices:
        raise CalibrationError("no valid calibration content markers were decoded")

    deltas = [
        current - previous
        for previous, current in zip(indices, indices[1:], strict=False)
    ]
    gaps = [delta - 1 for delta in deltas if delta > 1]
    duplicate_count = sum(delta == 0 for delta in deltas)
    reverse_count = sum(delta < 0 for delta in deltas)
    return {
        "epistemic_kind": "observed",
        "marker_schema": MARKER_SCHEMA,
        "decoded_frame_count": len(indices),
        "invalid_marker_frame_count": invalid_frames,
        "first_frame_index": indices[0],
        "last_frame_index": indices[-1],
        "first_content_offset_seconds": indices[0] / spec.frame_rate,
        "last_content_frame_offset_seconds": indices[-1] / spec.frame_rate,
        "content_end_exclusive_offset_seconds": (indices[-1] + 1) / spec.frame_rate,
        "precision_seconds": spec.precision_seconds,
        "duplicate_transition_count": duplicate_count,
        "missing_source_frame_count": sum(gaps),
        "reverse_transition_count": reverse_count,
        "sequence_repeatable": invalid_frames == 0
        and duplicate_count == 0
        and not gaps
        and reverse_count == 0,
    }


def _environment_facts() -> dict[str, str]:
    local_now = datetime.now().astimezone()
    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "machine": platform.machine(),
        "local_timezone": local_now.tzname() or "unknown",
    }


def _content_derivation(
    item: Mapping[str, Any],
    marker: Mapping[str, Any],
    trial: TrialContext,
) -> dict[str, Any]:
    first_offset = float(marker["first_content_offset_seconds"])
    end_offset = float(marker["content_end_exclusive_offset_seconds"])
    result: dict[str, Any] = {
        "epistemic_kind": "derived",
        "content_start_offset_seconds": first_offset,
        "content_end_exclusive_offset_seconds": end_offset,
        "content_duration_seconds": end_offset - first_offset,
        "precision_seconds": marker["precision_seconds"],
        "authority_use_prohibited": True,
        "limitations": [],
    }
    candidate = item.get("derived_candidate_interval")
    if trial.timeline_origin_utc is None:
        cast(list[str], result["limitations"]).append(
            "no independently verified playback origin was supplied; absolute content "
            "time and anchor error are unavailable"
        )
        return result
    content_start = trial.timeline_origin_utc + timedelta(seconds=first_offset)
    content_end = trial.timeline_origin_utc + timedelta(seconds=end_offset)
    result["candidate_content_started_at"] = content_start.isoformat()
    result["candidate_content_ended_at"] = content_end.isoformat()
    if isinstance(candidate, Mapping):
        candidate_mapping = cast(Mapping[str, object], candidate)
        embedded_start = timing_probe.parse_aware_timestamp(
            str(candidate_mapping.get("start_at"))
        )
        embedded_end = timing_probe.parse_aware_timestamp(
            str(candidate_mapping.get("end_at"))
        )
        if embedded_start is not None:
            result["embedded_anchor_minus_content_start_seconds"] = (
                embedded_start - content_start
            ).total_seconds()
        if embedded_end is not None:
            result["embedded_candidate_end_minus_content_end_seconds"] = (
                embedded_end - content_end
            ).total_seconds()
    if trial.clock_status.casefold() != "verified_stable":
        cast(list[str], result["limitations"]).append(
            "absolute comparison is not qualification-grade because clock status is "
            "not verified_stable"
        )
    return result


def build_calibration_report(
    source: Path,
    *,
    source_alias: str,
    executable: str,
    spec: MarkerSpec,
    trial: TrialContext,
    extension: str = ".mp4",
    max_files: int = timing_probe.DEFAULT_MAX_FILES,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    base = timing_probe.build_report(
        source,
        source_alias=source_alias,
        executable=executable,
        extension=extension,
        max_files=max_files,
        observed_at=observed_at,
    )
    media_paths = timing_probe.discover_media(source, extension, max_files)
    media = cast(list[dict[str, Any]], base["media"])
    for path, item in zip(media_paths, media, strict=True):
        marker = decode_marker_payload(run_marker_decode(executable, path, spec), spec)
        item["raw_observations"]["content_markers"] = marker
        item["derived_content_timing"] = _content_derivation(item, marker, trial)

    content_residuals: list[dict[str, Any]] = []
    for previous, current in zip(media, media[1:], strict=False):
        previous_marker = previous["raw_observations"]["content_markers"]
        current_marker = current["raw_observations"]["content_markers"]
        missing_frames = int(current_marker["first_frame_index"]) - (
            int(previous_marker["last_frame_index"]) + 1
        )
        content_residuals.append(
            {
                "from_media_ref": previous["media_ref"],
                "to_media_ref": current["media_ref"],
                "epistemic_kind": "derived",
                "frame_residual": missing_frames,
                "gap_positive_overlap_negative_seconds": missing_frames / spec.frame_rate,
                "precision_seconds": spec.precision_seconds,
                "authority_use_prohibited": True,
            }
        )

    anchor_errors = [
        abs(float(value))
        for item in media
        if isinstance(item.get("derived_content_timing"), Mapping)
        and (
            value := cast(Mapping[str, Any], item["derived_content_timing"]).get(
                "embedded_anchor_minus_content_start_seconds"
            )
        )
        is not None
    ]
    qualification_grade = (
        trial.vmix_exercised
        and trial.clock_status.casefold() == "verified_stable"
        and trial.timeline_origin_utc is not None
        and all(
            bool(item["raw_observations"]["content_markers"]["sequence_repeatable"])
            for item in media
        )
    )
    return {
        "schema_name": REPORT_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "harness": {"name": HARNESS_NAME, "version": HARNESS_VERSION},
        "observed_at": base["observed_at"],
        "source": base["source"],
        "inspection_tool": base["inspection_tool"],
        "environment": _environment_facts(),
        "trial": {
            "trial_id": trial.trial_id,
            "condition": trial.condition,
            "batch_id": trial.batch_id,
            "repetition": trial.repetition,
            "segment_duration_seconds": trial.segment_duration_seconds,
            "vmix_exercised": trial.vmix_exercised,
            "clock_status": trial.clock_status,
            "clock_source": trial.clock_source,
        },
        "recorder": {
            "product": trial.recorder_product,
            "version": trial.recorder_version,
            "profile_id": trial.recorder_profile_id,
            "profile_revision": trial.recorder_profile_revision,
            "configuration": list(trial.configuration),
        },
        "marker": {
            "schema": MARKER_SCHEMA,
            "frame_rate": spec.frame_rate,
            "counter_bits": spec.counter_bits,
            "precision_seconds": spec.precision_seconds,
        },
        "qualification_status": "unqualified_candidate_evidence",
        "qualification_grade_trial": qualification_grade,
        "authority_use_prohibited": True,
        "production_semantics_changed": False,
        "media": media,
        "content_adjacency_residuals": content_residuals,
        "trial_statistics": {
            "segment_count": len(media),
            "anchor_error_sample_count": len(anchor_errors),
            "median_absolute_anchor_error_seconds": median(anchor_errors)
            if anchor_errors
            else None,
            "maximum_absolute_anchor_error_seconds": max(anchor_errors)
            if anchor_errors
            else None,
            "all_marker_sequences_repeatable": all(
                bool(item["raw_observations"]["content_markers"]["sequence_repeatable"])
                for item in media
            ),
        },
        "limitations": [
            "this trial remains unqualified until its explicit recorder profile is "
            "accepted through Yellow review",
            "qualification-grade trial means inputs are analyzable; it does not grant "
            "production authority",
            "reports omit private paths and filenames but do not sanitize external media content",
        ],
    }


def summarize_reports(reports: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not reports:
        raise CalibrationError("at least one calibration report is required")
    profile_keys: set[tuple[str, int]] = set()
    conditions: dict[str, int] = {}
    anchor_errors: list[float] = []
    residuals: list[float] = []
    analyzable = 0
    for report in reports:
        if report.get("schema_name") != REPORT_SCHEMA:
            raise CalibrationError("summary input has an unsupported schema")
        recorder = cast(Mapping[str, Any], report["recorder"])
        profile_keys.add((str(recorder["profile_id"]), int(recorder["profile_revision"])))
        trial = cast(Mapping[str, Any], report["trial"])
        condition = str(trial["condition"])
        conditions[condition] = conditions.get(condition, 0) + 1
        if bool(report.get("qualification_grade_trial")):
            analyzable += 1
        for item_value in cast(Sequence[object], report["media"]):
            item = cast(Mapping[str, Any], item_value)
            derived = cast(Mapping[str, Any], item["derived_content_timing"])
            value = derived.get("embedded_anchor_minus_content_start_seconds")
            if isinstance(value, int | float):
                anchor_errors.append(abs(float(value)))
        for residual_value in cast(Sequence[object], report["content_adjacency_residuals"]):
            residual = cast(Mapping[str, Any], residual_value)
            value = residual.get("gap_positive_overlap_negative_seconds")
            if isinstance(value, int | float):
                residuals.append(float(value))
    if len(profile_keys) != 1:
        raise CalibrationError("summary inputs must use one recorder profile revision")
    profile_id, profile_revision = next(iter(profile_keys))
    return {
        "schema_name": SUMMARY_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "harness": {"name": HARNESS_NAME, "version": HARNESS_VERSION},
        "recorder_profile": {"profile_id": profile_id, "profile_revision": profile_revision},
        "trial_count": len(reports),
        "qualification_grade_trial_count": analyzable,
        "condition_counts": dict(sorted(conditions.items())),
        "anchor_error_sample_count": len(anchor_errors),
        "median_absolute_anchor_error_seconds": median(anchor_errors)
        if anchor_errors
        else None,
        "maximum_absolute_anchor_error_seconds": max(anchor_errors)
        if anchor_errors
        else None,
        "maximum_absolute_content_adjacency_residual_seconds": max(
            (abs(value) for value in residuals), default=None
        ),
        "qualification_status": "candidate_only_unqualified",
        "authority_use_prohibited": True,
        "limitations": [
            "summary statistics do not accept or qualify the recorder profile",
            "untested conditions and excluded trials must remain explicit in the Yellow package",
        ],
    }


def load_reports(paths: Sequence[Path]) -> list[Mapping[str, Any]]:
    if not paths or len(paths) > HARD_MAX_REPORTS:
        raise CalibrationError("report count is outside the supported bound")
    reports: list[Mapping[str, Any]] = []
    for path in paths:
        try:
            if path.is_symlink() or not path.is_file():
                raise CalibrationError("summary input must be a regular report file")
            if path.stat().st_size > HARD_MAX_REPORT_BYTES:
                raise CalibrationError("summary input exceeds the supported size")
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise CalibrationError("summary input could not be read safely") from exc
        if not isinstance(value, dict):
            raise CalibrationError("summary input must contain a report object")
        reports.append(cast(Mapping[str, Any], value))
    return reports


def render_summary_markdown(summary: Mapping[str, Any]) -> str:
    profile = cast(Mapping[str, Any], summary["recorder_profile"])
    conditions = cast(Mapping[str, Any], summary["condition_counts"])
    lines = [
        "# Recorder calibration summary",
        "",
        f"- Harness: `{HARNESS_NAME}` `{HARNESS_VERSION}`",
        f"- Profile: `{profile['profile_id']}` revision {profile['profile_revision']}",
        f"- Trials: {summary['trial_count']}",
        f"- Qualification-grade trials: {summary['qualification_grade_trial_count']}",
        "- Qualification: **candidate evidence only / unqualified**",
        "- Authority use: **prohibited**",
        "",
        "| Condition | Trial count |",
        "| --- | ---: |",
    ]
    for condition, count in conditions.items():
        lines.append(f"| `{condition}` | {count} |")
    lines.extend(
        [
            "",
            "Statistics",
            "",
            f"- Anchor samples: {summary['anchor_error_sample_count']}",
            "- Median absolute anchor error: "
            f"{summary['median_absolute_anchor_error_seconds']}",
            "- Maximum absolute anchor error: "
            f"{summary['maximum_absolute_anchor_error_seconds']}",
            "- Maximum absolute content adjacency residual: "
            f"{summary['maximum_absolute_content_adjacency_residual_seconds']}",
            "",
            "This summary does not qualify the recorder profile or authorize production use.",
            "",
        ]
    )
    return "\n".join(lines)


def write_summary(
    summary: Mapping[str, Any], json_output: Path, markdown_output: Path
) -> None:
    if json_output.resolve(strict=False) == markdown_output.resolve(strict=False):
        raise CalibrationError("JSON and Markdown outputs must be different paths")
    if json_output.exists() or markdown_output.exists():
        raise CalibrationError("output already exists")
    _atomic_create(
        json_output,
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    )
    try:
        _atomic_create(markdown_output, render_summary_markdown(summary))
    except BaseException:
        json_output.unlink(missing_ok=True)
        raise


def render_markdown(report: Mapping[str, Any]) -> str:
    trial = cast(Mapping[str, Any], report["trial"])
    recorder = cast(Mapping[str, Any], report["recorder"])
    statistics = cast(Mapping[str, Any], report["trial_statistics"])
    lines = [
        "# Recorder calibration result",
        "",
        f"- Harness: `{HARNESS_NAME}` `{HARNESS_VERSION}`",
        f"- Trial: `{trial['trial_id']}` / `{trial['condition']}` / "
        f"repetition {trial['repetition']}",
        f"- Recorder: `{recorder['product']}` `{recorder['version']}`",
        f"- Profile: `{recorder['profile_id']}` revision {recorder['profile_revision']}",
        f"- vMix exercised: **{str(trial['vmix_exercised']).lower()}**",
        f"- Clock status: `{trial['clock_status']}`",
        "- Qualification: **candidate evidence only / unqualified**",
        "- Authority use: **prohibited**",
        "",
        "| Media ref | Embedded creation time | Content start offset (s) | "
        "Content end offset (s) | Anchor - content start (s) |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for item_value in cast(Sequence[object], report["media"]):
        item = cast(Mapping[str, Any], item_value)
        raw = cast(Mapping[str, Any], item["raw_observations"])
        inspection = cast(Mapping[str, Any], raw["media_inspection"])
        container = cast(Mapping[str, Any], inspection["container"])
        tags = cast(Mapping[str, Any], container.get("tags", {}))
        derived = cast(Mapping[str, Any], item["derived_content_timing"])
        lines.append(
            f"| {item['media_ref']} | {tags.get('creation_time', '—')} | "
            f"{derived['content_start_offset_seconds']} | "
            f"{derived['content_end_exclusive_offset_seconds']} | "
            f"{derived.get('embedded_anchor_minus_content_start_seconds', '—')} |"
        )
    lines.extend(
        [
            "",
            "Marker sequences repeatable: "
            f"**{str(statistics['all_marker_sequences_repeatable']).lower()}**.",
            "",
            "Content adjacency values in JSON are measured from decoded source-frame markers. "
            "They remain Derived qualification evidence and do not change Session or "
            "media authority.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report: Mapping[str, Any], json_output: Path, markdown_output: Path) -> None:
    if json_output.resolve(strict=False) == markdown_output.resolve(strict=False):
        raise CalibrationError("JSON and Markdown outputs must be different paths")
    if json_output.exists() or markdown_output.exists():
        raise CalibrationError("output already exists")
    _atomic_create(
        json_output,
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    )
    try:
        _atomic_create(markdown_output, render_markdown(report))
    except BaseException:
        json_output.unlink(missing_ok=True)
        raise


def _trial_from_args(args: argparse.Namespace) -> TrialContext:
    origin = (
        _aware_utc(str(args.timeline_origin_utc), "timeline-origin-utc")
        if args.timeline_origin_utc
        else None
    )
    return TrialContext(
        trial_id=str(args.trial_id),
        condition=str(args.condition),
        batch_id=str(args.batch_id),
        repetition=int(args.repetition),
        recorder_product=str(args.recorder_product),
        recorder_version=str(args.recorder_version),
        recorder_profile_id=str(args.recorder_profile_id),
        recorder_profile_revision=int(args.recorder_profile_revision),
        segment_duration_seconds=float(args.segment_duration_seconds),
        vmix_exercised=bool(args.vmix_exercised),
        clock_status=str(args.clock_status),
        clock_source=str(args.clock_source),
        timeline_origin_utc=origin,
        configuration=tuple(args.configuration),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate or analyze deterministic recorder calibration media; "
            "qualification-only."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate", help="generate deterministic source media")
    generate.add_argument("--ffmpeg", required=True)
    generate.add_argument("--output", required=True, type=Path)
    generate.add_argument("--manifest-output", required=True, type=Path)
    generate.add_argument("--source-alias", required=True)
    generate.add_argument("--timeline-origin-utc", required=True)
    generate.add_argument("--duration-seconds", required=True, type=float)
    generate.add_argument("--boundary-seconds", default=60.0, type=float)
    generate.add_argument("--frame-rate", default=30, type=int)
    generate.add_argument("--width", default=1280, type=int)
    generate.add_argument("--height", default=720, type=int)

    analyze = subparsers.add_parser("analyze", help="analyze recorded calibration segments")
    analyze.add_argument("--source", required=True, type=Path)
    analyze.add_argument("--source-alias", required=True)
    analyze.add_argument("--ffmpeg", required=True)
    analyze.add_argument("--json-output", required=True, type=Path)
    analyze.add_argument("--markdown-output", required=True, type=Path)
    analyze.add_argument("--trial-id", required=True)
    analyze.add_argument("--condition", required=True)
    analyze.add_argument("--batch-id", required=True)
    analyze.add_argument("--repetition", default=1, type=int)
    analyze.add_argument("--recorder-product", required=True)
    analyze.add_argument("--recorder-version", required=True)
    analyze.add_argument("--recorder-profile-id", required=True)
    analyze.add_argument("--recorder-profile-revision", default=1, type=int)
    analyze.add_argument("--segment-duration-seconds", required=True, type=float)
    analyze.add_argument("--frame-rate", default=30, type=int)
    analyze.add_argument("--timeline-origin-utc")
    analyze.add_argument("--clock-status", default="not_verified")
    analyze.add_argument("--clock-source", default="not_recorded")
    analyze.add_argument("--configuration", action="append", default=[])
    analyze.add_argument("--vmix-exercised", action="store_true")
    analyze.add_argument("--extension", default=".mp4")
    analyze.add_argument("--max-files", default=timing_probe.DEFAULT_MAX_FILES, type=int)
    summarize = subparsers.add_parser(
        "summarize", help="summarize repeated reports for one recorder profile revision"
    )
    summarize.add_argument("--report", action="append", required=True, type=Path)
    summarize.add_argument("--json-output", required=True, type=Path)
    summarize.add_argument("--markdown-output", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "generate":
            generate_source(
                str(args.ffmpeg),
                args.output,
                args.manifest_output,
                source_alias=str(args.source_alias),
                spec=MarkerSpec(frame_rate=int(args.frame_rate)),
                duration_seconds=float(args.duration_seconds),
                boundary_seconds=float(args.boundary_seconds),
                width=int(args.width),
                height=int(args.height),
                timeline_origin_utc=_aware_utc(
                    str(args.timeline_origin_utc), "timeline-origin-utc"
                ),
            )
            print("calibration source and manifest created")
            return 0
        if args.command == "summarize":
            summary = summarize_reports(load_reports(tuple(args.report)))
            write_summary(summary, args.json_output, args.markdown_output)
            print("calibration summary created")
            return 0
        report = build_calibration_report(
            args.source,
            source_alias=str(args.source_alias),
            executable=str(args.ffmpeg),
            spec=MarkerSpec(frame_rate=int(args.frame_rate)),
            trial=_trial_from_args(args),
            extension=str(args.extension),
            max_files=int(args.max_files),
        )
        write_report(report, args.json_output, args.markdown_output)
    except (CalibrationError, timing_probe.ProbeError) as exc:
        print(f"calibration harness failed: {exc}", file=sys.stderr)
        return 1
    print("calibration report created")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
