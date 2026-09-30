"""Local live replay through public APIs and workers; stdout contains numeric JSON only."""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import time
import tomllib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn, Protocol, cast
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import UUID

# A script launched by path does not inherit backend's package search path.
REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "backend"))

from app.contexts.production.session_suggestions.contracts import Span  # noqa: E402
from app.contexts.production.session_suggestions.evaluation import (  # noqa: E402
    evaluate_accuracy,
    match_intervals,
)

MAX_BYTES = 64 * 1024 * 1024
MAX_BLOCKS = 1000
SKIPS = (
    "no_timing_evidence", "no_segmentation", "clock_implausible", "no_coverage",
    "no_planned_time", "already_realized",
)


class Refusal(ValueError):
    """Invalid input or a safety precondition that has not been met."""


class PipelineFailure(RuntimeError):
    """A bounded pipeline step failed; retain completed observations."""


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise Refusal()


def positive(value: str | float) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise Refusal()
    return number


def schedule(durations: Sequence[float], pace: float) -> tuple[float, ...]:
    """Completion deadlines since replay start, including the first block's duration."""
    positive(pace)
    elapsed = 0.0
    deadlines: list[float] = []
    for duration in durations:
        elapsed += positive(duration) / pace
        deadlines.append(positive(elapsed))
    return tuple(deadlines)


def run_due(copied: int, total: int, every: int) -> bool:
    return copied == total or copied % every == 0


def parse_truth(raw: str) -> tuple[Span, ...]:
    values: Any = json.loads(raw)
    if not isinstance(values, list):
        raise Refusal()
    records = cast(list[Any], values)
    if not 1 <= len(records) <= MAX_BLOCKS:
        raise Refusal()
    spans: list[Span] = []
    for record in records:
        if not isinstance(record, dict) or set(cast(dict[str, Any], record)) != {"start", "end"}:
            raise Refusal()
        interval = cast(dict[str, Any], record)
        spans.append(Span(datetime.fromisoformat(interval["start"]),
                          datetime.fromisoformat(interval["end"])))
    return tuple(sorted(spans, key=lambda span: (span.start, span.end)))


def validate_locations(
    source: Path, blocks: Path, truth: Path | None, repository: Path,
    *, source_empty: bool, secret: str,
) -> None:
    """Pure checks on resolved paths and caller-supplied filesystem facts."""
    if (not secret.strip() or not source_empty or source.is_relative_to(repository)
            or blocks.is_relative_to(repository) or source == blocks
            or blocks.is_relative_to(source)
            or (truth is not None and (truth.is_relative_to(repository)
                                      or truth.is_relative_to(source)))):
        raise Refusal()


@dataclass(frozen=True)
class Settings:
    blocks: tuple[Path, ...]
    source: Path
    durations: tuple[float, ...]
    pace: float
    every: int
    actor: str
    event_key: str
    deployment_id: str
    node_id: str
    truth: tuple[Span, ...] = ()
    timeout: float = 600
    poll: float = 1


@dataclass(frozen=True)
class Observation:
    copied: int
    wall_seconds: float
    media_seconds: float
    suggestions: tuple[Span, ...]
    skips: tuple[int, ...]


@dataclass
class Progress:
    copied: int = 0
    registered: int = 0
    settled: int = 0
    origin: datetime | None = None
    observations: list[Observation] = field(default_factory=lambda: list[Observation]())


def talk_metrics(progress: Progress, truth: tuple[Span, ...]) -> list[dict[str, Any]]:
    """Compare each match with its previous match, retaining it across absent runs."""
    first: list[float | None] = [None] * len(truth)
    previous: list[Span | None] = [None] * len(truth)
    changes = [0] * len(truth)
    maximum = [0.0] * len(truth)
    for run in progress.observations:
        for target, suggestion in match_intervals(run.suggestions, truth):
            current = run.suggestions[suggestion]
            prior = previous[target]
            if prior is None and progress.origin is not None:
                truth_end = (truth[target].end - progress.origin).total_seconds()
                first[target] = max(0.0, run.media_seconds - truth_end)
            if prior is not None:
                move = max(abs((current.start - prior.start).total_seconds()),
                           abs((current.end - prior.end).total_seconds()))
                changes[target] += int(move > 1.0)
                maximum[target] = max(maximum[target], move)
            previous[target] = current
    return [{"ordinal": i + 1, "time_to_first_suggestion_seconds": first[i],
             "stability_change_count": changes[i], "maximum_edge_move_seconds": maximum[i]}
            for i in range(len(truth))]


def report(progress: Progress, truth: tuple[Span, ...], error_count: int) -> dict[str, Any]:
    """Construct an allowlisted document; no raw input/API dictionaries are serialized."""
    result: dict[str, Any] = {
        "error_count": error_count, "blocks_copied": progress.copied,
        "blocks_registered": progress.registered, "blocks_settled": progress.settled,
        "runs": [{"ordinal": ordinal, "blocks_copied": run.copied,
                  "wall_seconds": run.wall_seconds, "media_seconds": run.media_seconds,
                  "suggestion_count": len(run.suggestions),
                  "skips": dict(zip(SKIPS, run.skips, strict=True))}
                 for ordinal, run in enumerate(progress.observations, 1)],
    }
    if truth:
        result["talks"] = talk_metrics(progress, truth)
        final = evaluate_accuracy(
            progress.observations[-1].suggestions if progress.observations else (), truth,
        )
        result["final_accuracy"] = {
            "truth_count": final.truth_count, "suggestion_count": final.suggestion_count,
            "matched_count": final.matched_count, "recall": final.recall,
            "median_start_error_seconds": final.median_start_error_seconds,
            "median_end_error_seconds": final.median_end_error_seconds,
        }
    return result


def execute(settings: Settings, io: Effects) -> tuple[int, dict[str, Any]]:
    progress = Progress()
    try:
        drive(settings, io, progress)
    except Refusal:
        if not progress.copied:
            return 1, {"error_count": 1}
        return 3, report(progress, settings.truth, 1)
    except (Exception, KeyboardInterrupt):
        # Includes HTTP/subprocess errors and unexpected failures. Never echo diagnostics.
        return 3, report(progress, settings.truth, 1)
    return 0, report(progress, settings.truth, 0)


class Effects(Protocol):
    def request(self, method: str, path: str, body: dict[str, Any] | None,
                timeout: float) -> dict[str, Any]: ...

    def copy(self, block: Path, source: Path, ordinal: int) -> None: ...

    def worker(self, kind: str, timeout: float) -> None: ...

    def now(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...


def atomic_copy(block: Path, source: Path, ordinal: int) -> None:
    # Bootstrap discovery explicitly excludes .partial and .tmp, before extension matching.
    final = source / f"block-{ordinal:06d}{block.suffix.lower()}"
    temporary = final.with_name(final.name + ".partial")
    if final.exists():
        raise PipelineFailure()
    # Exclusive creation also refuses another replay's in-progress copy.
    with temporary.open("xb") as target, block.open("rb") as incoming:
        shutil.copyfileobj(incoming, target)
        target.flush()
        os.fsync(target.fileno())
    # Deliberately retain partial files on failure for operator inspection. Never delete media.
    temporary.rename(final)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> None:
        raise PipelineFailure()


class LocalEffects:
    def __init__(self, base_url: str, environment: Mapping[str, str]) -> None:
        self.base_url = base_url.rstrip("/")
        self.environment = dict(environment)
        self.secret = environment["STAGEFLOW_API_SHARED_SECRET"]
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, method: str, path: str, body: dict[str, Any] | None,
                timeout: float) -> dict[str, Any]:
        request = Request(self.base_url + path, method=method,
                          data=None if body is None else json.dumps(body).encode("utf-8"),
                          headers={"X-StageFlow-API-Secret": self.secret,
                                   "Content-Type": "application/json"})
        with self.opener.open(request, timeout=min(30, timeout)) as response:
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise PipelineFailure()
        value: Any = json.loads(raw)
        if not isinstance(value, dict):
            raise PipelineFailure()
        return cast(dict[str, Any], value)

    def copy(self, block: Path, source: Path, ordinal: int) -> None:
        atomic_copy(block, source, ordinal)

    def worker(self, kind: str, timeout: float) -> None:
        subprocess.run(
            [sys.executable, "-m", f"app.demo.{kind}_worker", "--once"],
            cwd=REPOSITORY / "backend", env=self.environment,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=timeout, check=True,
        )

    def now(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


def remaining(io: Effects, deadline: float) -> float:
    seconds = deadline - io.now()
    if seconds <= 0:
        raise PipelineFailure()
    return seconds


def pause(io: Effects, deadline: float, poll: float) -> None:
    io.sleep(min(poll, remaining(io, deadline)))


def page_items(io: Effects, method: str, path: str, deadline: float,
               body: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    cursor: str | None = None
    seen: set[str] = set()
    while True:
        parameters: dict[str, Any] = {"limit": 100}
        if cursor is not None:
            parameters["after"] = cursor
        query = ("&" if "?" in path else "?") + urlencode(parameters)
        response = io.request(method, path + query if body is None else path,
                              None if body is None else {**body, **parameters},
                              remaining(io, deadline))
        items.extend(response["items"])
        if len(items) > MAX_BLOCKS * 10:
            raise PipelineFailure()
        cursor = response["next_after"]
        if cursor is None:
            return items
        cursor = str(UUID(cursor))
        if cursor in seen:
            raise PipelineFailure()
        seen.add(cursor)


def status_stage(status: dict[str, Any], settings: Settings) -> dict[str, Any]:
    if (status["event_key"] != settings.event_key
            or status["deployment_id"] != settings.deployment_id
            or status["node_id"] != settings.node_id
            or not status["database_available"]
            or not status["automation"]["enabled"] or len(status["stages"]) != 1):
        raise Refusal()
    stage: dict[str, Any] = status["stages"][0]
    if stage["key"] != "main":
        raise Refusal()
    return stage


def settle(io: Effects, settings: Settings, event: str, asset: str, kind: str) -> None:
    deadline = io.now() + settings.timeout
    path = f"/api/v1/{kind.replace('_', '-')}/events/{event}"
    requested = page_items(io, "POST", path + "/requests", deadline,
                           {"actor_id": settings.actor, "confirmed": "confirmed"})
    if not any(item["asset_id"] == asset for item in requested):
        raise PipelineFailure()
    while True:
        operations = page_items(io, "GET", path + "/operations", deadline)
        if any(item["state"] in {"terminal_failed", "cancelled"} for item in operations):
            raise PipelineFailure()
        if (any(item["asset_id"] == asset for item in operations)
                and all(item["state"] == "succeeded" for item in operations)):
            return
        io.worker(kind, remaining(io, deadline))
        pause(io, deadline, settings.poll)


def drive(settings: Settings, io: Effects, progress: Progress) -> None:
    deadline = io.now() + settings.timeout
    while True:
        status = io.request("GET", "/api/v1/kernel/status", None, remaining(io, deadline))
        stage = status_stage(status, settings)
        if status["ready"]:
            break
        # Autonomous discovery temporarily marks the latest reconciliation as running.
        pause(io, deadline, settings.poll)
    # A fresh Event and one exclusive source make each registration increment unambiguous.
    if any(stage[key] for key in (
        "discovered", "stabilizing", "ready", "registered", "associated",
    )):
        raise Refusal()
    event, stage_id = str(UUID(status["event_id"])), str(UUID(stage["stage_id"]))
    started = io.now()
    seen_assets: set[str] = set()
    for ordinal, (block, due) in enumerate(
        zip(settings.blocks, schedule(settings.durations, settings.pace), strict=True), 1,
    ):
        while (delay := started + due - io.now()) > 0:
            io.sleep(min(delay, 60))
        io.copy(block, settings.source, ordinal)
        progress.copied = ordinal
        deadline = io.now() + settings.timeout
        while True:
            status = io.request("GET", "/api/v1/kernel/status", None, remaining(io, deadline))
            current = status_stage(status, settings)
            if current["stage_id"] != stage_id or status["event_id"] != event:
                raise PipelineFailure()
            if current["registered"] > ordinal:
                raise PipelineFailure()
            if current["registered"] == ordinal:
                progress.registered = ordinal
                # recent_media is capped at 100 and cannot identify every registered asset.
                # Normal idempotent timing enqueue provides a complete paginated asset set.
                requested = page_items(io, "POST",
                    f"/api/v1/media-timing/events/{event}/requests", deadline,
                    {"actor_id": settings.actor, "confirmed": "confirmed"})
                added = {str(UUID(item["asset_id"])) for item in requested} - seen_assets
                if len(added) != 1:
                    raise PipelineFailure()
                asset = added.pop()
                seen_assets.add(asset)
                break
            pause(io, deadline, settings.poll)
        for kind in ("media_timing", "media_segmentation"):
            settle(io, settings, event, asset, kind)
        progress.settled = ordinal
        if ordinal == 1 and settings.truth:
            timing = io.request("GET", f"/api/v1/media-timing/assets/{asset}/latest",
                                None, settings.timeout)
            interval = timing["evidence"]["candidate_interval"]
            progress.origin = Span(datetime.fromisoformat(interval["started_at"]),
                                   datetime.fromisoformat(interval["ended_at"])).start
        if run_due(ordinal, len(settings.blocks), settings.every):
            deadline = io.now() + settings.timeout
            path = f"/api/v1/session-suggestions/events/{event}/stages/{stage_id}"
            created = io.request("POST", path + "/runs", {"actor_id": settings.actor},
                                 remaining(io, deadline))
            latest = io.request("GET", path + "/runs/latest", None, remaining(io, deadline))
            if created["run_id"] != latest["run_id"]:
                raise PipelineFailure()
            values = page_items(io, "GET", path + "/suggestions?status=open", deadline)
            if any(value["run_id"] != latest["run_id"] for value in values):
                raise PipelineFailure()
            spans = tuple(Span(datetime.fromisoformat(value["suggested_start"]),
                               datetime.fromisoformat(value["suggested_end"])) for value in values)
            skips = tuple(latest["skips"][key] for key in SKIPS)
            if any(type(value) is not int or value < 0 for value in skips):
                raise PipelineFailure()
            elapsed = io.now() - started
            media_seconds = elapsed * settings.pace
            if not math.isfinite(media_seconds):
                raise PipelineFailure()
            progress.observations.append(Observation(ordinal, elapsed, media_seconds,
                                                     spans, skips))


def probe_duration(path: Path, executable: Path) -> float:
    result = subprocess.run(
        [str(executable), "-v", "error", "-protocol_whitelist", "file", "-show_entries",
         "format=duration", "-of", "json", str(path)],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        timeout=30, check=True,
    )
    return positive(json.loads(result.stdout)["format"]["duration"])


def prepare(args: argparse.Namespace, environment: Mapping[str, str],
            probe: Callable[[Path, Path], float] = probe_duration) -> Settings:
    source, blocks = args.source.resolve(strict=True), args.blocks.resolve(strict=True)
    truth_path = None if args.truth is None else args.truth.resolve(strict=True)
    validate_locations(source, blocks, truth_path, REPOSITORY,
                       source_empty=source.is_dir() and not any(source.iterdir()),
                       secret=environment.get("STAGEFLOW_API_SHARED_SECRET", ""))
    url = urlsplit(str(args.api_base_url))
    if (url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password
            or url.query or url.fragment or url.path not in {"", "/"}):
        raise Refusal()
    actor = str(UUID(args.actor_id))
    pace = 1.0 if args.pace == "real" else positive(args.pace)
    timeout, poll = positive(args.timeout_seconds), positive(args.poll_seconds)
    if pace < 1 or args.run_every < 1 or poll > timeout:
        raise Refusal()
    config_path = Path(environment["STAGEFLOW_KERNEL_CONFIG_PATH"]).resolve(strict=True)
    with config_path.open("rb") as handle:
        config = tomllib.load(handle)
    stages = config["event"]["stages"]
    if len(stages) != 1 or stages[0]["key"] != "main" or len(stages[0]["sources"]) != 1:
        raise Refusal()
    binding = stages[0]["sources"][0]
    if Path(binding["path"]).resolve(strict=True) != source:
        raise Refusal()
    if not all(config[key]["enabled"] for key in (
        "local_media_timing", "local_media_segmentation", "autonomous_event_node",
    )):
        raise Refusal()
    extensions = set(binding.get("allowed_extensions", [".mov", ".mp4", ".mkv", ".mxf", ".wav"]))
    files = tuple(sorted(blocks.iterdir(), key=lambda path: (path.name.casefold(), path.name)))
    if not 1 <= len(files) <= min(MAX_BLOCKS, binding.get("maximum_candidates", 1000)):
        raise Refusal()
    if any(not path.is_file() or path.is_symlink() or path.name.startswith(".")
           or path.suffix.lower() not in extensions for path in files):
        raise Refusal()
    truth = ()
    if truth_path is not None:
        if truth_path.stat().st_size > MAX_BYTES:
            raise Refusal()
        truth = parse_truth(truth_path.read_text(encoding="utf-8"))
    duration = None if args.duration_seconds is None else positive(args.duration_seconds)
    probe_path = Path(config["local_media_timing"]["ffprobe_path"])
    durations = tuple(duration if duration is not None else probe(path, probe_path)
                      for path in files)
    schedule(durations, pace)
    return Settings(files, source, durations, pace, args.run_every, actor, config["event"]["key"],
                    config["deployment_id"], config["node_id"], truth, timeout, poll)


def main(argv: Sequence[str] | None = None, *,
         environment: Mapping[str, str] | None = None,
         factory: Callable[[str, Mapping[str, str]], Effects] = LocalEffects) -> int:
    parser = Parser(prog="replay-blocks", description=__doc__)
    parser.add_argument("--blocks", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--pace", default="real")
    parser.add_argument("--run-every", type=int, default=1)
    parser.add_argument("--api-base-url", required=True)
    parser.add_argument("--actor-id", required=True)
    parser.add_argument("--truth", type=Path)
    parser.add_argument("--duration-seconds", type=float)
    parser.add_argument("--timeout-seconds", type=float, default=600)
    parser.add_argument("--poll-seconds", type=float, default=1)
    env = os.environ if environment is None else environment
    try:
        args = parser.parse_args(argv)
        settings = prepare(args, env)
        effects = factory(args.api_base_url, env)
    except (Exception, KeyboardInterrupt):
        print('{"error_count": 1}')
        return 1
    try:
        code, document = execute(settings, effects)
        serialized = json.dumps(document, sort_keys=True, allow_nan=False)
    except (Exception, KeyboardInterrupt):
        print('{"error_count": 1}')
        return 3
    print(serialized)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
