"""Bounded, qualification-only media timing reconnaissance.

This module deliberately has no production imports. Its reports are sanitized evidence
for calibration work and are prohibited from serving as Session or association authority.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

PROBE_NAME = "stageflow-media-timing-qualification-probe"
PROBE_VERSION = "1.0"
SCHEMA_NAME = "stageflow.media-timing-qualification-report"
SCHEMA_VERSION = "1.0"
DERIVATION_RULE = "embedded-creation-time-plus-container-duration"
DERIVATION_VERSION = "1.0"
DEFAULT_MAX_FILES = 100
HARD_MAX_FILES = 1_000
SAFE_ALIAS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
TIMING_TOKEN = re.compile(r"([A-Za-z_]+):([^\s]+)")


class ProbeError(RuntimeError):
    """An operator-correctable error whose message contains no private media path."""


def _iso_from_timestamp(value: float) -> str:
    return datetime.fromtimestamp(value, tz=UTC).isoformat()


def parse_aware_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(UTC)


def _duration_seconds(value: str) -> float | None:
    match = re.fullmatch(r"(\d+):(\d+):(\d+(?:\.\d+)?)", value.strip())
    if match is None:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _number(value: str | None) -> float | int | None:
    if value is None or value in {"NOPTS", "N/A"}:
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def _stream_description(line: str) -> dict[str, Any] | None:
    match = re.search(r"Stream #\d+:(\d+)(?:\[[^]]+\])?(?:\([^)]*\))?: (Video|Audio): (.+)", line)
    if match is None:
        return None
    stream_index, kind, description = match.groups()
    result: dict[str, Any] = {
        "stream_index": int(stream_index),
        "kind": kind.casefold(),
        "codec_description": description.strip(),
    }
    time_base = re.search(r"(?:^|, )([0-9]+(?:\.[0-9]+)?) tbn(?:,|$)", description)
    if time_base is not None:
        result["time_base_hz"] = _number(time_base.group(1))
    dimensions = re.search(r"(?:^|, )(\d{2,5}x\d{2,5})(?:[\s,]|$)", description)
    if dimensions is not None:
        result["dimensions"] = dimensions.group(1)
    sample_rate = re.search(r"(?:^|, )(\d+) Hz(?:,|$)", description)
    if sample_rate is not None:
        result["sample_rate_hz"] = int(sample_rate.group(1))
    return result


def _packet_observation(line: str) -> dict[str, Any] | None:
    if "demuxer ->" not in line:
        return None
    fields = dict(TIMING_TOKEN.findall(line))
    stream_index = fields.get("ist_index")
    kind = fields.get("type")
    if stream_index is None or kind not in {"audio", "video"}:
        return None
    return {
        "stream_index": int(stream_index),
        "kind": kind,
        "pts": _number(fields.get("pkt_pts")),
        "pts_seconds": _number(fields.get("pkt_pts_time")),
        "dts": _number(fields.get("pkt_dts")),
        "dts_seconds": _number(fields.get("pkt_dts_time")),
        "duration": _number(fields.get("duration")),
        "duration_seconds": _number(fields.get("duration_time")),
    }


def parse_ffmpeg_observations(header_text: str, tail_text: str) -> dict[str, Any]:
    """Parse only stable, useful fields from FFmpeg diagnostic output."""

    raw: dict[str, Any] = {
        "epistemic_kind": "observed",
        "container": {},
        "streams": [],
        "packet_timing": {"first_by_stream": [], "last_by_stream": []},
        "parse_limitations": [],
    }
    container = cast(dict[str, Any], raw["container"])
    streams = cast(list[dict[str, Any]], raw["streams"])

    input_match = re.search(r"^Input #0, (.+?), from ", header_text, re.MULTILINE)
    if input_match is not None:
        container["format"] = input_match.group(1).strip()
    duration_match = re.search(
        r"Duration: ([0-9:.]+), start: (-?[0-9.]+), bitrate: ([^\r\n]+)", header_text
    )
    if duration_match is not None:
        duration = _duration_seconds(duration_match.group(1))
        container.update(
            {
                "duration_seconds": duration,
                "start_seconds": _number(duration_match.group(2)),
                "bitrate_description": duration_match.group(3).strip(),
            }
        )

    tags: dict[str, str] = {}
    for key in ("major_brand", "minor_version", "compatible_brands", "creation_time"):
        match = re.search(rf"^\s*{key}\s*:\s*(.+?)\s*$", header_text, re.MULTILINE)
        if match is not None:
            tags[key] = match.group(1)
    container["tags"] = tags

    seen_streams: set[tuple[int, str]] = set()
    for line in header_text.splitlines():
        stream = _stream_description(line)
        if stream is None:
            continue
        identity = (int(stream["stream_index"]), str(stream["kind"]))
        if identity not in seen_streams:
            streams.append(stream)
            seen_streams.add(identity)

    first: dict[tuple[int, str], dict[str, Any]] = {}
    for line in header_text.splitlines():
        packet = _packet_observation(line)
        if packet is not None:
            identity = (int(packet["stream_index"]), str(packet["kind"]))
            first.setdefault(identity, packet)

    last: dict[tuple[int, str], dict[str, Any]] = {}
    for line in tail_text.splitlines():
        packet = _packet_observation(line)
        if packet is not None:
            identity = (int(packet["stream_index"]), str(packet["kind"]))
            last[identity] = packet

    packet_timing = cast(dict[str, Any], raw["packet_timing"])
    packet_timing["first_by_stream"] = [first[key] for key in sorted(first)]
    packet_timing["last_by_stream"] = [last[key] for key in sorted(last)]
    limitations = cast(list[str], raw["parse_limitations"])
    if duration_match is None:
        limitations.append("container_duration_not_parsed")
    if not first:
        limitations.append("first_packet_timing_not_parsed")
    if not last:
        limitations.append("last_packet_timing_not_parsed")
    return raw


def derive_candidate_interval(raw: dict[str, Any]) -> dict[str, Any] | None:
    container_value = raw.get("container")
    if not isinstance(container_value, dict):
        return None
    container = cast(dict[str, Any], container_value)
    tags_value = container.get("tags")
    if not isinstance(tags_value, dict):
        return None
    tags = cast(dict[str, Any], tags_value)
    creation_time = parse_aware_timestamp(
        str(tags["creation_time"]) if "creation_time" in tags else None
    )
    duration = container.get("duration_seconds")
    if creation_time is None or not isinstance(duration, int | float) or duration < 0:
        return None
    end = creation_time + timedelta(seconds=float(duration))
    return {
        "epistemic_kind": "derived",
        "derivation_rule": DERIVATION_RULE,
        "derivation_version": DERIVATION_VERSION,
        "status": "unqualified_candidate",
        "start_at": creation_time.isoformat(),
        "end_at": end.isoformat(),
        "duration_seconds": duration,
        "authority_use_prohibited": True,
        "limitations": [
            "embedded creation_time semantics are not qualified as content start",
            "container duration and timestamps can differ from useful content boundaries",
            "candidate interval must not drive Session or media association decisions",
        ],
    }


def run_ffmpeg(executable: str, media: Path, *, tail: bool = False) -> str:
    command = [executable, "-nostdin", "-hide_banner", "-debug_ts"]
    if tail:
        command.extend(["-sseof", "-2"])
    command.extend(["-i", os.fspath(media), "-map", "0", "-c", "copy"])
    if not tail:
        command.extend(["-t", "1"])
    command.extend(["-f", "null", "-"])
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProbeError("media inspection tool could not complete") from exc
    if completed.returncode != 0:
        raise ProbeError("media inspection tool reported failure")
    return completed.stderr


def inspect_tool(executable: str) -> dict[str, str]:
    try:
        completed = subprocess.run(
            [executable, "-version"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProbeError("media inspection tool is unavailable") from exc
    match = re.search(r"^ffmpeg version\s+([^\s]+)", completed.stdout, re.IGNORECASE)
    if completed.returncode != 0 or match is None:
        raise ProbeError("media inspection tool version was not recognized")
    name = Path(executable).name
    if not SAFE_ALIAS.fullmatch(name):
        name = "ffmpeg-compatible"
    return {"name": name, "version": match.group(1)}


def discover_media(source: Path, extension: str, max_files: int) -> list[Path]:
    if max_files < 1 or max_files > HARD_MAX_FILES:
        raise ProbeError("max-files is outside the supported bound")
    if not re.fullmatch(r"\.[A-Za-z0-9]{1,10}", extension):
        raise ProbeError("extension must be a simple file suffix")
    try:
        if source.is_symlink():
            raise ProbeError("symbolic-link sources are not supported")
        if source.is_file():
            candidates = [source] if source.suffix.casefold() == extension.casefold() else []
        elif source.is_dir():
            candidates = sorted(
                (
                    child
                    for child in source.iterdir()
                    if child.is_file()
                    and not child.is_symlink()
                    and child.suffix.casefold() == extension.casefold()
                ),
                key=lambda child: child.name.casefold(),
            )
        else:
            raise ProbeError("source must be an existing file or directory")
    except OSError as exc:
        raise ProbeError("source could not be inspected safely") from exc
    if not candidates:
        raise ProbeError("source contains no matching media")
    if len(candidates) > max_files:
        raise ProbeError("source contains more media than max-files permits")
    return candidates


def _file_observation(path: Path) -> dict[str, Any]:
    stat = path.stat()
    change_or_creation_time = stat.st_ctime  # pyright: ignore[reportDeprecated]
    return {
        "epistemic_kind": "observed",
        "authority": "non_authoritative_filesystem_proxy",
        "size_bytes": stat.st_size,
        "platform_change_or_creation_time": _iso_from_timestamp(change_or_creation_time),
        "modified_time": _iso_from_timestamp(stat.st_mtime),
        "limitations": [
            "filesystem timestamps do not establish recorder or useful-content timing"
        ],
    }


def build_report(
    source: Path,
    *,
    source_alias: str,
    executable: str,
    extension: str = ".mp4",
    max_files: int = DEFAULT_MAX_FILES,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    if SAFE_ALIAS.fullmatch(source_alias) is None:
        raise ProbeError("source-alias contains unsupported characters")
    media = discover_media(source, extension, max_files)
    tool = inspect_tool(executable)
    items: list[dict[str, Any]] = []
    for index, path in enumerate(media):
        media_ref = f"media-{index:05d}"
        try:
            raw = parse_ffmpeg_observations(
                run_ffmpeg(executable, path), run_ffmpeg(executable, path, tail=True)
            )
            filesystem = _file_observation(path)
        except (OSError, ProbeError) as exc:
            raise ProbeError(f"inspection failed for {media_ref}") from exc
        item: dict[str, Any] = {
            "media_ref": media_ref,
            "raw_observations": {
                "media_inspection": raw,
                "filesystem_proxy": filesystem,
            },
            "derived_candidate_interval": derive_candidate_interval(raw),
        }
        items.append(item)

    residuals: list[dict[str, Any]] = []
    for previous, current in zip(items, items[1:], strict=False):
        previous_interval = cast(dict[str, Any] | None, previous["derived_candidate_interval"])
        current_interval = cast(dict[str, Any] | None, current["derived_candidate_interval"])
        if not isinstance(previous_interval, dict) or not isinstance(current_interval, dict):
            continue
        prior_end = parse_aware_timestamp(str(previous_interval["end_at"]))
        next_start = parse_aware_timestamp(str(current_interval["start_at"]))
        if prior_end is None or next_start is None:
            continue
        residuals.append(
            {
                "from_media_ref": previous["media_ref"],
                "to_media_ref": current["media_ref"],
                "epistemic_kind": "derived",
                "arithmetic_residual_seconds": (next_start - prior_end).total_seconds(),
                "interpretation": "not_a_content_gap_or_overlap_measurement",
                "authority_use_prohibited": True,
            }
        )

    timestamp = (observed_at or datetime.now(UTC)).astimezone(UTC)
    return {
        "schema_name": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "probe": {"name": PROBE_NAME, "version": PROBE_VERSION},
        "observed_at": timestamp.isoformat(),
        "source": {"alias": source_alias, "media_count": len(items)},
        "inspection_tool": tool,
        "qualification_status": "reconnaissance_only_unqualified",
        "authority_use_prohibited": True,
        "production_semantics_changed": False,
        "media": items,
        "adjacent_candidate_residuals": residuals,
        "limitations": [
            "output omits source paths and filenames but does not sanitize media content",
            "embedded recorder/container times require controlled calibration",
            "packet timestamps describe encoded streams, not useful content semantics",
            "this report is qualification evidence and cannot authorize production behavior",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    source = cast(dict[str, Any], report["source"])
    tool = cast(dict[str, Any], report["inspection_tool"])
    lines = [
        "# Media timing qualification report",
        "",
        f"- Probe: `{PROBE_NAME}` `{PROBE_VERSION}`",
        f"- Schema: `{SCHEMA_NAME}` `{SCHEMA_VERSION}`",
        f"- Source alias: `{source['alias']}`",
        f"- Media count: {source['media_count']}",
        f"- Inspection tool: `{tool['name']}` `{tool['version']}`",
        "- Status: **reconnaissance only / unqualified**",
        "- Authority use: **prohibited**",
        "",
        "| Media ref | Embedded creation time | Duration (s) | Candidate start | Candidate end |",
        "| --- | --- | ---: | --- | --- |",
    ]
    media = cast(list[dict[str, Any]], report["media"])
    for item in media:
        observations = cast(dict[str, Any], item["raw_observations"])
        inspection = cast(dict[str, Any], observations["media_inspection"])
        container = cast(dict[str, Any], inspection["container"])
        tags = cast(dict[str, Any], container.get("tags", {}))
        candidate = cast(dict[str, Any] | None, item["derived_candidate_interval"])
        start = candidate.get("start_at", "—") if isinstance(candidate, dict) else "—"
        end = candidate.get("end_at", "—") if isinstance(candidate, dict) else "—"
        lines.append(
            f"| {item['media_ref']} | {tags.get('creation_time', '—')} | "
            f"{container.get('duration_seconds', '—')} | {start} | {end} |"
        )
    lines.extend(
        [
            "",
            "Adjacent values, when present in JSON, are arithmetic residuals between "
            "unqualified candidate intervals. They are not content gap/overlap measurements.",
            "",
            "This report must not drive Session boundaries, media association, package "
            "membership, or automation.",
            "",
        ]
    )
    return "\n".join(lines)


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
            raise ProbeError("output already exists") from exc
        except OSError as exc:
            raise ProbeError("output could not be published atomically") from exc
    finally:
        temporary.unlink(missing_ok=True)


def write_reports(report: dict[str, Any], json_output: Path, markdown_output: Path) -> None:
    if json_output.resolve(strict=False) == markdown_output.resolve(strict=False):
        raise ProbeError("JSON and Markdown outputs must be different paths")
    if json_output.exists() or markdown_output.exists():
        raise ProbeError("output already exists")
    json_content = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    markdown_content = render_markdown(report)
    _atomic_create(json_output, json_content)
    try:
        _atomic_create(markdown_output, markdown_content)
    except BaseException:
        json_output.unlink(missing_ok=True)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect local media timing for qualification only; output is non-authoritative."
        )
    )
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--source-alias", required=True)
    parser.add_argument("--ffmpeg", required=True)
    parser.add_argument("--json-output", required=True, type=Path)
    parser.add_argument("--markdown-output", required=True, type=Path)
    parser.add_argument("--extension", default=".mp4")
    parser.add_argument("--max-files", default=DEFAULT_MAX_FILES, type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = build_report(
            args.source,
            source_alias=str(args.source_alias),
            executable=str(args.ffmpeg),
            extension=str(args.extension),
            max_files=int(args.max_files),
        )
        write_reports(report, args.json_output, args.markdown_output)
    except ProbeError as exc:
        print(f"media timing probe failed: {exc}", file=sys.stderr)
        return 1
    print("media timing qualification report created")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
