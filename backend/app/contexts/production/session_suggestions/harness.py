"""Pure corpus validation and deterministic policy experiments; no storage or network."""
import json
import random
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass, fields, replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import NAMESPACE_URL, uuid5

from app.contexts.editorial.derivation_contracts import TimingQualification
from app.contexts.events import ProgramExpectation
from app.contexts.production.media_segmentation_evidence.contracts import (
    MAX_INTERVALS,
    MAX_OFFSET_US,
    SegmentationInterval,
)
from app.shared.ids import EntityId

from . import policy, policy_v2, policy_v3
from .contracts import (
    MAX_INPUTS,
    AssetInput,
    InputSnapshot,
    Reference,
    ScheduleOffsetEntry,
    ScheduleOffsetSetting,
    Span,
    validate_offset_entries,
)
from .cue_catalog import BOUNDARY_CUE_CATALOG
from .cue_composition import CompositionRequest, compose
from .evaluation import AccuracyMetrics, evaluate_accuracy

_EPOCH = datetime(2000, 1, 1, tzinfo=UTC)
_MODELS = ("whole-day", "two-part", "independent")
MAX_MANIFEST_BYTES = 64 * 1024 * 1024


class ManifestError(ValueError):
    """A bounded error with no source values, locations or paths."""

    def __init__(self) -> None:
        super().__init__("invalid_manifest")


@dataclass(frozen=True, slots=True)
class StageManifest:
    snapshot: InputSnapshot
    truth: tuple[Span, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "truth", tuple(self.truth))


def _id(name: str) -> EntityId:
    return EntityId(str(uuid5(NAMESPACE_URL, "stageflow:validation:" + name)))


def _record(value: Any, required: set[str], optional: set[str] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManifestError()
    record = cast(dict[str, Any], value)
    if not required <= record.keys() or record.keys() - required - (optional or set()):
        raise ManifestError()
    return record


def _array(value: Any, limit: int = MAX_INPUTS) -> list[Any]:
    if not isinstance(value, list) or len(cast(list[Any], value)) > limit:
        raise ManifestError()
    return cast(list[Any], value)


def _time(value: Any) -> datetime:
    # Require a full ISO date-time and an explicit UTC offset (not a date-only value).
    if not isinstance(value, str) or re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
            r"(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})", value) is None:
        raise ManifestError()
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ManifestError()
    return result.astimezone(UTC)


def _span(value: Any, start: str = "start", end: str = "end") -> Span:
    return Span(_time(value[start]), _time(value[end]))


def parse_manifest(payload: str) -> tuple[StageManifest, ...]:
    """Validate JSON plus temporal bounds; detach all nested data into frozen contracts."""
    try:
        if len(payload) > MAX_MANIFEST_BYTES or len(payload.encode("utf-8")) > MAX_MANIFEST_BYTES:
            raise ManifestError()
        root = _record(json.loads(payload), {"stages"})
        stages = _array(root["stages"])
        if not stages:
            raise ManifestError()
        return tuple(_stage(value, index) for index, value in enumerate(stages))
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        raise ManifestError() from None


def _stage(value: Any, index: int) -> StageManifest:
    stage = _record(value, {"blocks", "schedule", "truth"})
    assets: list[AssetInput] = []
    for ordinal, value in enumerate(_array(stage["blocks"])):
        block = _record(value, {"start", "duration_us", "intervals"}, {"start_cues", "end_cues"})
        duration = block["duration_us"]
        if type(duration) is not int or not 0 < duration <= MAX_OFFSET_US:
            raise ManifestError()
        start = _time(block["start"])
        coverage = Span(start, start + timedelta(microseconds=duration))
        intervals: list[SegmentationInterval] = []
        for value in _array(block["intervals"], MAX_INTERVALS):
            item = _record(value, {"kind", "start_us", "end_us"})
            interval = SegmentationInterval(item["kind"], item["start_us"], item["end_us"])
            if interval.end_microseconds > duration:
                raise ManifestError()
            intervals.append(interval)
        cues = [tuple(_time(v) for v in _array(block.get(role, [])))
                for role in ("start_cues", "end_cues")]
        if any(not coverage.start <= t <= coverage.end for role in cues for t in role):
            raise ManifestError()
        prefix = f"{index}:block:{ordinal}"
        assets.append(AssetInput(
            _id(prefix), Reference(_id(prefix + ":timing"), 1), coverage,
            TimingQualification.UNQUALIFIED, (_id(prefix + ":segmentation"),),
            tuple(intervals), Reference(_id(prefix + ":transcript"), 1) if any(cues) else None,
            cues[0], cues[1],
        ))
    expectations: list[ProgramExpectation] = []
    keys: set[str] = set()
    for ordinal, value in enumerate(_array(stage["schedule"])):
        item = _record(value, {"key", "planned_start", "planned_end"})
        key = item["key"]
        if not isinstance(key, str) or not 1 <= len(key) <= 200 or key in keys:
            raise ManifestError()
        keys.add(key)
        span = _span(item, "planned_start", "planned_end")
        expectations.append(_expectation(index, ordinal, span))
    truth = tuple(_span(_record(v, {"start", "end"})) for v in _array(stage["truth"]))
    return StageManifest(InputSnapshot(tuple(expectations), tuple(assets)), truth)


def _expectation(stage: int, ordinal: int, span: Span) -> ProgramExpectation:
    return ProgramExpectation(
        _id(f"{stage}:talk:{ordinal}"), _id("event"), str(ordinal), _id(f"stage:{stage}"),
        "Anonymous talk", (), span.start, span.end, {}, 1, _EPOCH,
    )


def drift_schedule(truth: Sequence[Span], *, model: str, magnitude_seconds: int,
                   seed: int, stage_ordinal: int) -> tuple[Span, ...]:
    """Generate plans per event day, in chronological truth order; see README RNG contract."""
    if model not in _MODELS or type(magnitude_seconds) is not int or magnitude_seconds < 0:
        raise ValueError("invalid_options")
    days: list[list[Span]] = []
    for span in sorted(truth, key=lambda t: (t.start, t.end)):
        if not days or span.start - days[-1][-1].end >= timedelta(hours=6):
            days.append([])
        days[-1].append(span)
    result: list[Span] = []
    for day_ordinal, talks in enumerate(days):
        rng = random.Random(
            f"stageflow:session-suggestions:harness:v1:{model}:{seed}:{stage_ordinal}:{day_ordinal}")
        split = (max(range(1, len(talks)),
                     key=lambda i: talks[i].start - talks[i - 1].end) if len(talks) > 1 else 1)
        offset = 0.0
        for i, talk in enumerate(talks):
            if model != "independent" and (i == 0 or model == "two-part" and i == split):
                offset = rng.uniform(-magnitude_seconds, magnitude_seconds)
            jitter = magnitude_seconds if model == "independent" else 60
            start = talk.start + timedelta(seconds=offset + rng.uniform(-jitter, jitter))
            end = talk.end + timedelta(seconds=offset + rng.uniform(-jitter, jitter))
            # Historical drift experiments clamp every planned talk to at least 120 s.
            result.append(Span(start, max(start + timedelta(seconds=120), end)))
    return tuple(result)


def run_manifest(stages: Sequence[StageManifest], *, policy_version: str = "3",
                 schedule_source: str = "manifest", drift_model: str = "whole-day",
                 magnitude_seconds: int = 0, seeds: Sequence[int] = (0,),
                 cue_profile: str | None = None,
                 producer_offsets: tuple[ScheduleOffsetEntry, ...] = (),
                 ) -> dict[str, Any]:
    """Return only anonymous ordinals, closed labels, numeric metrics and pass booleans."""
    if (policy_version not in ("1", "2", "3") or schedule_source not in ("manifest", "drift")
            or drift_model not in _MODELS or type(magnitude_seconds) is not int
            or not 0 <= magnitude_seconds <= 86400 or not seeds
            or len(seeds) > 100 or any(type(s) is not int for s in seeds)
            or not stages or len(stages) > MAX_INPUTS
            or producer_offsets and policy_version != "3"):
        raise ValueError("invalid_options")
    validate_offset_entries(producer_offsets)
    cues = None
    if cue_profile is not None:
        profile = next((p for p in BOUNDARY_CUE_CATALOG.profiles if p.key == cue_profile), None)
        if profile is None:
            raise ValueError("invalid_options")
        cues = compose(CompositionRequest(BOUNDARY_CUE_CATALOG.version,
                                          profile.group_keys, profile.key))
    scenarios: list[dict[str, Any]] = []
    for index, stage in enumerate(stages):
        rows: list[dict[str, Any]] = []
        for seed in sorted(set(seeds)):
            snapshot = stage.snapshot
            if schedule_source == "drift":
                plans = drift_schedule(stage.truth, model=drift_model,
                                       magnitude_seconds=magnitude_seconds, seed=seed,
                                       stage_ordinal=index)
                snapshot = replace(snapshot, expectations=tuple(
                    _expectation(index, i, span) for i, span in enumerate(plans)))
            if not snapshot.expectations:
                raise ValueError("planned_span_required")
            if cues is None:
                snapshot = replace(snapshot, assets=tuple(replace(
                    a, start_cues=(), end_cues=(), transcript=None) for a in snapshot.assets))
            override = ScheduleOffsetSetting(
                _id("event"), _id(f"stage:{index}"), 1, _id("command"), "0" * 64,
                _id("actor"), _EPOCH, producer_offsets) if producer_offsets else None
            if policy_version == "3":
                result = policy_v3.evaluate(snapshot, override)
            else:
                evaluator = policy.evaluate if policy_version == "1" else policy_v2.evaluate
                result = evaluator(snapshot)
            starts = [p.planned_start for p in snapshot.expectations if p.planned_start is not None]
            ends = [p.planned_end for p in snapshot.expectations if p.planned_end is not None]
            metrics = asdict(evaluate_accuracy(result.candidates, stage.truth,
                                              planned_span=Span(min(starts), max(ends))))
            rows.append({"seed": seed, "metrics": metrics, "skips": asdict(result.skips),
                         "target_pass": _passes(metrics)})
        scenarios.append({"stage_ordinal": index, "per_seed": rows,
                          "worst_seed": _worst(rows),
                          "target_pass": all(row["target_pass"] for row in rows)})
    return {"policy_version": int(policy_version), "schedule_source": schedule_source,
            "drift_model": drift_model if schedule_source == "drift" else None,
            "magnitude_seconds": magnitude_seconds if schedule_source == "drift" else 0,
            "cue_phrase_counts": {"start": len(cues.start) if cues else 0,
                                  "end": len(cues.end) if cues else 0},
            "scenarios": scenarios}


def _passes(metrics: dict[str, Any]) -> bool:
    return (metrics["wrong_day_count"] == 0 and metrics["recall"] >= 0.9
            and metrics["median_start_error_seconds"] is not None
            and metrics["median_end_error_seconds"] is not None
            and metrics["median_start_error_seconds"] <= 30
            and metrics["median_end_error_seconds"] <= 30)


def _worst(rows: list[dict[str, Any]]) -> dict[str, Any]:
    # Each metric has its own worst seed, as in the historical accuracy tables.
    lower_is_worse = {"recall", "precision", "precision_including_unscheduled",
                      "matched_count", "count_within_60_seconds"}
    result: dict[str, Any] = {}
    for metric in rows[0]["metrics"]:
        def rank(row: dict[str, Any], metric: str = metric) -> float:
            value = row["metrics"][metric]
            if value is None:
                return float("inf")
            return -float(value) if metric in lower_is_worse else float(value)
        worst = max(rows, key=rank)
        result[metric] = {"seed": worst["seed"], "value": worst["metrics"][metric]}
    return result


def markdown_report(report: dict[str, Any]) -> str:
    """Render only the known numeric report fields; never interpolate caller labels."""
    lines = ["| Stage | Kind | Seed | Metric | Value |",
             "| --- | --- | --- | --- | --- |"]
    for scenario in report["scenarios"]:
        for row in scenario["per_seed"]:
            for field in fields(AccuracyMetrics):
                lines.append(f"| {scenario['stage_ordinal']} | per seed | {row['seed']} | "
                             f"{field.name} | {row['metrics'][field.name]} |")
        for field in fields(AccuracyMetrics):
            worst = scenario["worst_seed"][field.name]
            lines.append(f"| {scenario['stage_ordinal']} | worst | {worst['seed']} | "
                         f"{field.name} | {worst['value']} |")
    return "\n".join(lines)
