"""Local live replay through public APIs and workers; stdout contains numeric JSON only."""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
import tomllib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn, Protocol, cast
from urllib.error import URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import UUID, uuid4

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


class PhaseTimeout(PipelineFailure):
    """A deadline expired, distinguishable from a protocol or pipeline failure."""


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
    transcription: bool = False
    arrival: str = "atomic"
    profile_label: str | None = None

    @property
    def upgraded(self) -> bool:
        return self.transcription or self.arrival == "growing" or self.profile_label is not None


@dataclass(frozen=True)
class Observation:
    copied: int
    wall_seconds: float
    media_seconds: float
    suggestions: tuple[Span, ...]
    skips: tuple[int, ...]
    segmentation_settled: int | None = None
    transcription_settled: int | None = None


@dataclass
class BlockObservation:
    ordinal: int
    closed: float
    registered: float | None = None
    timing: float | None = None
    segmentation: float | None = None
    transcription: float | None = None
    suggestion: float | None = None


@dataclass
class Progress:
    upgraded: bool = False
    transcription: bool = False
    profile_label: str | None = None
    blocks: list[BlockObservation] = field(default_factory=lambda: list[BlockObservation]())
    transcription_enqueue_baseline: int = 0
    transcription_counter_seen: int = 0
    transcription_unavailable_count: int = 0
    transcription_partial_count: int = 0
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
    if progress.profile_label is not None:
        result["profile_label"] = progress.profile_label
    if progress.upgraded:
        result.update(upgrade_report(progress, truth))
    return result


def upgrade_report(progress: Progress, truth: tuple[Span, ...]) -> dict[str, Any]:
    stages = ["registered", "timing", "segmentation", "suggestion"]
    result: dict[str, Any] = {}
    if progress.transcription:
        stages.append("transcription")
        result["transcription_enqueue_baseline"] = progress.transcription_enqueue_baseline
        result["transcription_unavailable_count"] = progress.transcription_unavailable_count
        result["transcription_partial_count"] = progress.transcription_partial_count
    result["stage_timings"] = [
        {"ordinal": b.ordinal, **{name: None if getattr(b, name) is None
         else getattr(b, name) - b.closed for name in stages}} for b in progress.blocks]
    result["stage_summary"] = {}
    for name in stages:
        values = sorted(getattr(b, name) - b.closed for b in progress.blocks
                        if getattr(b, name) is not None)
        result["stage_summary"][name] = {
            "median": statistics.median(values) if values else None,
            "p95": values[math.ceil(.95 * len(values)) - 1] if values else None,
        }
    kinds = ["segmentation"] + (["transcription"] if progress.transcription else [])
    result["evidence_timeline"] = {
        "blocks": [{"ordinal": b.ordinal, **{k: getattr(b, k) for k in kinds}}
                   for b in progress.blocks],
        "runs": [{"ordinal": i, "media_seconds": run.media_seconds,
                  **{k: (getattr(run, k + "_settled")
                         if getattr(run, k + "_settled") is not None else
                         max((b.ordinal for b in progress.blocks
                              if getattr(b, k) is not None
                              and getattr(b, k) <= run.media_seconds), default=0))
                     for k in kinds}}
                 for i, run in enumerate(progress.observations, 1)],
    }
    if truth:
        result["talks"] = talk_metrics(progress, truth)
        matched: list[list[tuple[float, Span]]] = [[] for _ in truth]
        for run in progress.observations:
            for target, suggestion in match_intervals(run.suggestions, truth):
                matched[target].append((run.media_seconds, run.suggestions[suggestion]))
        for i, talk in enumerate(result["talks"]):
            matches = matched[i]
            end = (truth[i].end - progress.origin).total_seconds() if progress.origin else None
            selected = {"first": matches[0][1] if matches else None}
            for offset in (300, 900):
                eligible = [span for seconds, span in matches
                            if end is not None and seconds <= end + offset]
                selected[f"plus_{offset}"] = eligible[-1] if eligible else None
            for name, span in selected.items():
                talk[name + "_start_error_seconds"] = (None if span is None else
                    abs((span.start - truth[i].start).total_seconds()))
                talk[name + "_end_error_seconds"] = (None if span is None else
                    abs((span.end - truth[i].end).total_seconds()))
    return result


def execute(settings: Settings, io: Effects) -> tuple[int, dict[str, Any]]:
    progress = Progress(upgraded=settings.upgraded, transcription=settings.transcription,
                        profile_label=settings.profile_label)
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

    def worker(self, kind: str, timeout: float) -> str | None: ...

    def writer(self, settings: Settings, started: float) -> Writer: ...

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


class Writer(Protocol):
    def closed(self, ordinal: int) -> float | None: ...

    def stop(self) -> None: ...


def growing_copy(block: Path, source: Path, ordinal: int, start: float, end: float,
                 now: Callable[[], float], sleep: Callable[[float], None]) -> None:
    """One-second-or-finer visible chunks; the last chunk meets the close deadline."""
    final = source / f"block-{ordinal:06d}{block.suffix.lower()}"
    size = block.stat().st_size
    if size <= 0:
        raise PipelineFailure()
    chunks = min(size, max(2, math.ceil(end - start)))
    with final.open("xb") as target, block.open("rb") as incoming:
        written = 0
        for index in range(1, chunks + 1):
            deadline = start + (end - start) * index / chunks
            while (delay := deadline - now()) > 0:
                sleep(min(delay, 60))
            boundary = size * index // chunks
            pending = boundary - written
            while pending:
                data = incoming.read(min(pending, 1024 * 1024))
                if not data:
                    raise PipelineFailure()
                target.write(data)
                pending -= len(data)
            written = boundary
            target.flush()
        os.fsync(target.fileno())


class GrowingWriter:
    """One cancellable writer; closing times and failures cross a locked seam."""
    def __init__(self, settings: Settings, started: float) -> None:
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._closed: dict[int, float] = {}
        self._failed = False
        self._thread = threading.Thread(target=self._write, args=(settings, started), daemon=True)
        self._thread.start()

    def _sleep(self, seconds: float) -> None:
        if self._cancel.wait(seconds):
            raise PipelineFailure()

    def _write(self, settings: Settings, started: float) -> None:
        previous = started
        try:
            for ordinal, (block, due) in enumerate(zip(
                settings.blocks, schedule(settings.durations, settings.pace), strict=True), 1,
            ):
                if self._cancel.is_set():
                    return
                end = started + due
                growing_copy(block, settings.source, ordinal, previous, end,
                             time.monotonic, self._sleep)
                with self._lock:
                    self._closed[ordinal] = time.monotonic()
                previous = end
        except Exception:
            with self._lock:
                self._failed = True

    def closed(self, ordinal: int) -> float | None:
        with self._lock:
            if self._failed:
                raise PipelineFailure()
            return self._closed.get(ordinal)

    def stop(self) -> None:
        self._cancel.set()
        self._thread.join()


def worker_outcome(raw: bytes) -> str | None:
    if len(raw) > 16384:
        raise PipelineFailure()
    lines = raw.splitlines()
    if not 1 <= len(lines) <= 2:
        raise PipelineFailure()
    values = [json.loads(line) for line in lines]
    # The startup line is intentionally ignored, including all identity fields.
    if values[0].get("state") != "available":
        raise PipelineFailure()
    if len(values) == 1:
        return None
    outcome = values[1].get("outcome")
    if outcome not in {"succeeded", "retry_scheduled", "terminal_failed"}:
        raise PipelineFailure()
    return outcome


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
        try:
            with self.opener.open(request, timeout=min(30, timeout)) as response:
                raw = response.read(MAX_BYTES + 1)
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise TimeoutError() from None
            raise
        if len(raw) > MAX_BYTES:
            raise PipelineFailure()
        value: Any = json.loads(raw)
        if not isinstance(value, dict):
            raise PipelineFailure()
        return cast(dict[str, Any], value)

    def copy(self, block: Path, source: Path, ordinal: int) -> None:
        atomic_copy(block, source, ordinal)

    def writer(self, settings: Settings, started: float) -> Writer:
        return GrowingWriter(settings, started)

    def worker(self, kind: str, timeout: float) -> str | None:
        if kind == "transcription":
            # Drain a bounded pipe in a reader thread so timeout covers reads as well.
            with subprocess.Popen(
                [sys.executable, "-m", "app.demo.worker", "--once"],
                cwd=REPOSITORY / "backend", env=self.environment,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            ) as child:
                output: list[bytes] = []
                def read() -> None:
                    assert child.stdout is not None
                    raw = child.stdout.read(16385)
                    output.append(raw)
                    if len(raw) > 16384:
                        child.kill()
                reader = threading.Thread(target=read, daemon=True)
                reader.start()
                try:
                    child.wait(timeout=timeout)
                except BaseException:
                    child.kill()
                    child.wait()
                    raise
                finally:
                    reader.join()
                if child.returncode != 0:
                    raise PipelineFailure()
                return worker_outcome(output[0])
        subprocess.run(
            [sys.executable, "-m", f"app.demo.{kind}_worker", "--once"],
            cwd=REPOSITORY / "backend", env=self.environment,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=timeout, check=True,
        )
        return None

    def now(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


def remaining(io: Effects, deadline: float) -> float:
    seconds = deadline - io.now()
    if seconds <= 0:
        raise PhaseTimeout()
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


def settle(io: Effects, settings: Settings, event: str, asset: str, kind: str,
           observe: Callable[[str, list[dict[str, Any]]], None] | None = None) -> None:
    deadline = io.now() + settings.timeout
    path = f"/api/v1/{kind.replace('_', '-')}/events/{event}"
    requested = page_items(io, "POST", path + "/requests", deadline,
                           {"actor_id": settings.actor, "confirmed": "confirmed"})
    if not any(item["asset_id"] == asset for item in requested):
        raise PipelineFailure()
    while True:
        operations = page_items(io, "GET", path + "/operations", deadline)
        if observe is not None:
            observe(kind, operations)
        if any(item["state"] in {"terminal_failed", "cancelled"} for item in operations):
            raise PipelineFailure()
        if (any(item["asset_id"] == asset for item in operations)
                and all(item["state"] == "succeeded" for item in operations)):
            return
        io.worker(kind, remaining(io, deadline))
        pause(io, deadline, settings.poll)


def compose_cues(io: Effects, settings: Settings, event: str) -> None:
    deadline = io.now() + settings.timeout
    path = f"/api/v1/session-suggestions/events/{event}"
    current = io.request("GET", path + "/boundary-cues", None, remaining(io, deadline))
    if current["current"] is not None:
        raise Refusal()
    catalog = io.request("GET", path + "/boundary-cue-catalog", None, remaining(io, deadline))
    profiles = [p for p in catalog["profiles"] if p["name"] == "Conference stage"]
    if len(profiles) != 1:
        raise Refusal()
    # A profile selects its groups as the producer UI does; empty groups compose no cues.
    groups = profiles[0]["group_keys"]
    if (not isinstance(groups, list) or not groups
            or not all(isinstance(key, str) and key for key in cast(list[Any], groups))):
        raise Refusal()
    io.request("POST", path + "/boundary-cues", {
        "catalog_version": catalog["version"], "profile_key": profiles[0]["key"],
        "group_keys": list(cast(list[str], groups)), "actor_id": settings.actor,
        "command_id": str(uuid4()),
        "authority_kind": "human",
    }, remaining(io, deadline))


def transcription_counter(status: dict[str, Any]) -> int:
    counter = status["automation"]["transcription_operations_enqueued"]
    if type(counter) is not int or counter < 0:
        raise PipelineFailure()
    return counter


def transcribe(io: Effects, settings: Settings, asset: str, ordinal: int,
               baseline: int, started: float, block: BlockObservation, progress: Progress) -> None:
    deadline = io.now() + settings.timeout
    partial = False
    terminal: str | None = None
    try:
        while io.now() < deadline:
            status = io.request("GET", "/api/v1/kernel/status", None, remaining(io, deadline))
            remaining(io, deadline)
            status_stage(status, settings)
            counter = transcription_counter(status)
            if counter < progress.transcription_counter_seen:
                raise PipelineFailure()
            progress.transcription_counter_seen = counter
            if counter >= baseline + ordinal:
                break
            pause(io, deadline, settings.poll)
        else:
            raise PhaseTimeout()
        deadline = io.now() + settings.timeout
        while io.now() < deadline:
            value = io.request("GET", f"/api/v1/transcription/assets/{asset}/status",
                               None, remaining(io, deadline))
            remaining(io, deadline)
            if value["complete_evidence"]:
                if block.transcription is None:
                    block.transcription = (io.now() - started) * settings.pace
            partial = bool(value["partial_evidence"])
            operation = value["operation"]
            if operation is not None and operation["state"] in {
                "succeeded", "terminal_failed", "cancelled",
            }:
                terminal = operation["state"]
                break
            io.worker("transcription", remaining(io, deadline))
            if io.now() < deadline:
                pause(io, deadline, settings.poll)
    except (PhaseTimeout, TimeoutError, subprocess.TimeoutExpired):
        # This phase is degradable; other worker/HTTP/protocol errors remain failures.
        pass
    if terminal != "succeeded":
        block.transcription = None
    if block.transcription is None:
        progress.transcription_unavailable_count += 1
        progress.transcription_partial_count += int(partial)


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
    baseline = transcription_counter(status) if settings.transcription else 0
    progress.transcription_enqueue_baseline = baseline
    progress.transcription_counter_seen = baseline
    if settings.transcription:
        compose_cues(io, settings, event)
    started = io.now()
    writer = io.writer(settings, started) if settings.arrival == "growing" else None
    try:
        drive_blocks(settings, io, progress, event, stage_id, started, baseline, writer)
    finally:
        if writer is not None:
            writer.stop()


class GrowingEvidence:
    """Map continuous recording order using public timing, retaining overlapping observations."""
    def __init__(self, io: Effects, settings: Settings, progress: Progress,
                 writer: Writer, event: str, stage_id: str, started: float) -> None:
        self.io, self.settings, self.progress, self.writer = io, settings, progress, writer
        self.event, self.stage_id, self.started = event, stage_id, started
        self.assets: list[str] = []
        self.last_start: datetime | None = None
        self.available: dict[str, dict[str, float]] = {
            "media_timing": {}, "media_segmentation": {},
        }
        self.registered: dict[str, float] = {}

    def seconds(self) -> float:
        return (self.io.now() - self.started) * self.settings.pace

    def closures(self) -> None:
        for ordinal in range(len(self.progress.blocks) + 1, len(self.settings.blocks) + 1):
            closed = self.writer.closed(ordinal)
            if closed is None:
                break
            self.progress.blocks.append(BlockObservation(
                ordinal, (closed - self.started) * self.settings.pace))
            self.progress.copied = ordinal
        self.writer.closed(1)  # Check even after the final closure has been recorded.

    def observe(self, kind: str, operations: list[dict[str, Any]]) -> None:
        self.closures()
        for operation in operations:
            if operation["state"] == "succeeded":
                self.available[kind].setdefault(str(UUID(operation["asset_id"])), self.seconds())
        self.apply()

    def apply(self) -> None:
        for i, asset in enumerate(self.assets):
            block = self.progress.blocks[i]
            block.registered = self.registered[asset]
            block.timing = self.available["media_timing"].get(asset)
            block.segmentation = self.available["media_segmentation"].get(asset)

    def synchronize(self, status: dict[str, Any] | None = None) -> None:
        deadline = self.io.now() + self.settings.timeout
        if status is None:
            status = self.io.request("GET", "/api/v1/kernel/status", None,
                                     remaining(self.io, deadline))
        stage = status_stage(status, self.settings)
        if stage["stage_id"] != self.stage_id or status["event_id"] != self.event:
            raise PipelineFailure()
        registered_at = self.seconds()
        self.closures()
        requested = page_items(self.io, "POST",
            f"/api/v1/media-timing/events/{self.event}/requests", deadline,
            {"actor_id": self.settings.actor, "confirmed": "confirmed"})
        added = {str(UUID(item["asset_id"])) for item in requested} - set(self.assets)
        self.closures()
        if len(self.assets) + len(added) > len(self.progress.blocks):
            raise PipelineFailure()
        if not added:
            return
        for asset in added:
            self.registered.setdefault(asset, registered_at)
        # All timing is drained anyway. Its public intervals give recording order
        # without relying on capped discovery projections or scan timestamp ties.
        settle(self.io, self.settings, self.event, next(iter(added)), "media_timing", self.observe)
        intervals: list[tuple[datetime, str]] = []
        for asset in added:
            value = self.io.request("GET", f"/api/v1/media-timing/assets/{asset}/latest",
                                    None, self.settings.timeout)
            interval = value["evidence"]["candidate_interval"]
            span = Span(datetime.fromisoformat(interval["started_at"]),
                        datetime.fromisoformat(interval["ended_at"]))
            intervals.append((span.start, asset))
        intervals.sort()
        if (len({start for start, _ in intervals}) != len(intervals)
                or (self.last_start is not None and intervals[0][0] <= self.last_start)):
            raise PipelineFailure()
        self.closures()
        if len(self.assets) + len(added) > len(self.progress.blocks):
            raise PipelineFailure()  # Discovery must never register a still-growing block.
        self.assets.extend(asset for _, asset in intervals)
        self.last_start = intervals[-1][0]
        self.progress.registered = len(self.assets)
        self.apply()

    def sample_segmentation(self) -> None:
        deadline = self.io.now() + self.settings.timeout
        operations = page_items(self.io, "GET",
            f"/api/v1/media-segmentation/events/{self.event}/operations", deadline)
        self.observe("media_segmentation", operations)


def drive_blocks(settings: Settings, io: Effects, progress: Progress, event: str,
                 stage_id: str, started: float, baseline: int, writer: Writer | None) -> None:
    seen_assets: set[str] = set()
    growing = (GrowingEvidence(io, settings, progress, writer, event, stage_id, started)
               if writer is not None else None)
    for ordinal, (block, due) in enumerate(
        zip(settings.blocks, schedule(settings.durations, settings.pace), strict=True), 1,
    ):
        if writer is None:
            while (delay := started + due - io.now()) > 0:
                io.sleep(min(delay, 60))
            io.copy(block, settings.source, ordinal)
            closed = io.now()
        else:
            deadline = started + due + settings.timeout
            while (closed := writer.closed(ordinal)) is None:
                pause(io, deadline, settings.poll)
        if growing is None:
            progress.copied = ordinal
            measured = BlockObservation(ordinal, (closed - started) * settings.pace)
            progress.blocks.append(measured)
        else:
            growing.closures()
            measured = progress.blocks[ordinal - 1]
        deadline = io.now() + settings.timeout
        while True:
            status = io.request("GET", "/api/v1/kernel/status", None, remaining(io, deadline))
            current = status_stage(status, settings)
            if current["stage_id"] != stage_id or status["event_id"] != event:
                raise PipelineFailure()
            if writer is not None:
                writer.closed(ordinal)  # Surface background failure during pipeline polling.
            if current["registered"] > ordinal and writer is None:
                raise PipelineFailure()
            if current["registered"] >= ordinal:
                if growing is not None:
                    growing.synchronize(status)
                    if len(growing.assets) < ordinal:
                        raise PipelineFailure()
                    asset = growing.assets[ordinal - 1]
                    break
                progress.registered = ordinal
                measured.registered = (io.now() - started) * settings.pace
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
        kinds = (("media_timing", "media_segmentation") if growing is None
                 else ("media_segmentation",))
        for kind in kinds:
            settle(io, settings, event, asset, kind,
                   None if growing is None else growing.observe)
            if growing is None:
                setattr(measured, "timing" if kind == "media_timing" else "segmentation",
                        (io.now() - started) * settings.pace)
            if writer is not None:
                writer.closed(ordinal)
        if settings.transcription:
            transcribe(io, settings, asset, ordinal, baseline, started, measured, progress)
        progress.settled = ordinal
        if ordinal == 1 and settings.truth:
            timing = io.request("GET", f"/api/v1/media-timing/assets/{asset}/latest",
                                None, settings.timeout)
            interval = timing["evidence"]["candidate_interval"]
            progress.origin = Span(datetime.fromisoformat(interval["started_at"]),
                                   datetime.fromisoformat(interval["ended_at"])).start
        if run_due(ordinal, len(settings.blocks), settings.every):
            if growing is not None:
                growing.synchronize()
                growing.sample_segmentation()
                if settings.transcription:
                    for i, registered_asset in enumerate(growing.assets):
                        if i + 1 <= ordinal:
                            continue
                        try:
                            value = io.request("GET",
                                f"/api/v1/transcription/assets/{registered_asset}/status",
                                None, settings.timeout)
                        except TimeoutError:
                            # This block still gets its own bounded phase when reached.
                            continue
                        future = progress.blocks[i]
                        if value["complete_evidence"] and future.transcription is None:
                            future.transcription = growing.seconds()
            deadline = io.now() + settings.timeout
            path = f"/api/v1/session-suggestions/events/{event}/stages/{stage_id}"
            created = io.request("POST", path + "/runs", {"actor_id": settings.actor},
                                 remaining(io, deadline))
            completed = io.now()
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
            elapsed = (completed if settings.upgraded else io.now()) - started
            media_seconds = elapsed * settings.pace
            if not math.isfinite(media_seconds):
                raise PipelineFailure()
            for item in progress.blocks:
                if item.registered is not None and item.suggestion is None:
                    item.suggestion = media_seconds
            copied = progress.copied if growing is not None else ordinal
            available = [max((b.ordinal for b in progress.blocks
                              if getattr(b, kind) is not None
                              and getattr(b, kind) <= media_seconds), default=0)
                         for kind in ("segmentation", "transcription")]
            progress.observations.append(Observation(copied, elapsed, media_seconds,
                                                     spans, skips, *available))


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
    transcription = getattr(args, "transcription", False)
    arrival = getattr(args, "arrival", "atomic")
    label = getattr(args, "profile_label", None)
    if label is not None and re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", label) is None:
        raise Refusal()
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
    if transcription and not isinstance(config.get("local_transcription"), dict):
        raise Refusal()
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
                    config["deployment_id"], config["node_id"], truth, timeout, poll,
                    transcription, arrival, label)


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
    parser.add_argument("--transcription", action="store_true")
    parser.add_argument("--arrival", choices=("growing", "atomic"), default="atomic")
    parser.add_argument("--profile-label")
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
