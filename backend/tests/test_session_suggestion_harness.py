"""Synthetic corpus experiments; no real media, filesystem fixture or database."""
import json
from collections.abc import Sequence
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

import pytest

from app.contexts.production.session_suggestions import (
    harness,
    harness_cli,
    policy,
    policy_v2,
    policy_v3,
)
from app.contexts.production.session_suggestions.contracts import (
    InputSnapshot,
    PolicyResult,
    PolicyResultV3,
    ScheduleOffsetEntry,
    ScheduleOffsetSetting,
    ScheduleOffsetSource,
    Span,
    Strength,
)
from app.contexts.production.session_suggestions.evaluation import (
    AccuracyMetrics,
    evaluate_accuracy,
)
from app.contexts.production.session_suggestions.harness import (
    ManifestError,
    drift_schedule,
    markdown_report,
    parse_manifest,
    run_manifest,
)
from app.contexts.production.session_suggestions.harness_cli import main
from app.contexts.production.session_suggestions.policy_v3 import evaluate
from app.contexts.production.session_suggestions.scenarios import generate_scenario


def corpus(name: str = "clean-day") -> str:
    return json.dumps(generate_scenario(name))


@pytest.mark.parametrize("name", ("clean-day", "recording-gaps", "multi-part", "wrong-clock",
                                  "short-evenly-spaced", "late-recording-start"))
def test_scenario_metrics_pinned(name: str) -> None:
    assert generate_scenario(name) == generate_scenario(name)
    row = run_manifest(parse_manifest(corpus(name)))["scenarios"][0]["per_seed"][0]
    count = 2 if name == "multi-part" else 8 if name == "short-evenly-spaced" else 3
    # Short talks: known aliasing weakness — pinned current v3 behaviour, not an ADR pass.
    matched = 6 if name == "short-evenly-spaced" else count
    expected: dict[str, Any] = {
        "truth_count": count, "suggestion_count": count, "matched_count": matched,
        "recall": matched / count, "precision": matched / count,
        "precision_including_unscheduled": matched / count, "unscheduled_count": 0,
        "median_start_error_seconds": 0.0, "median_end_error_seconds": 0.0,
        "p95_start_error_seconds": 300.0 if name == "late-recording-start" else 0.0,
        "p95_end_error_seconds": 0.0, "wrong_day_count": 0,
        "count_within_60_seconds": 2 if name == "late-recording-start" else matched,
    }
    assert row["metrics"] == expected
    assert row["skips"] == {"no_timing_evidence": 0, "no_segmentation": 0,
                            "clock_implausible": int(name == "wrong-clock"),
                            "no_coverage": 0, "no_planned_time": 0, "already_realized": 0}
    assert row["target_pass"] == (name != "short-evenly-spaced")


def test_wrong_clock_never_contributes_placement_or_lineage() -> None:
    stage = parse_manifest(corpus("wrong-clock"))[0]
    bad = stage.snapshot.assets[-1]
    result = evaluate(stage.snapshot)
    assert result.skips.clock_implausible == 1
    assert all(bad.timing not in c.timing_references for c in result.candidates)
    assert all(not set(bad.segmentation_ids) & set(c.segmentation_ids) for c in result.candidates)
    assert [c.span for c in result.candidates] == list(stage.truth)


@pytest.mark.parametrize("version", ["1", "2", "3"])
@pytest.mark.parametrize("model", ["whole-day", "two-part", "independent"])
def test_harness_determinism(version: str, model: str) -> None:
    stages = parse_manifest(corpus())
    a = run_manifest(stages, policy_version=version, schedule_source="drift",
                     drift_model=model, magnitude_seconds=600, seeds=(2, 1))
    b = run_manifest(parse_manifest(corpus()), policy_version=version, schedule_source="drift",
                     drift_model=model, magnitude_seconds=600, seeds=(1, 2, 1))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert stages == parse_manifest(corpus())
    scenario = a["scenarios"][0]
    for key in ("recall", "precision", "precision_including_unscheduled"):
        worst = scenario["worst_seed"][key]
        assert worst["value"] == min(row["metrics"][key] for row in scenario["per_seed"])
        assert worst["value"] == next(row["metrics"][key] for row in scenario["per_seed"]
                                      if row["seed"] == worst["seed"])


def test_manifest_schedule_as_is_and_stage_isolation() -> None:
    raw = generate_scenario("short-evenly-spaced")
    raw["stages"].append(generate_scenario("clean-day")["stages"][0])
    stages = parse_manifest(json.dumps(raw))
    report = run_manifest(stages, magnitude_seconds=999, seeds=(8, 9))
    for scenario in report["scenarios"]:
        a, b = scenario["per_seed"]
        assert a["metrics"] == b["metrics"]
    assert report["scenarios"][0]["per_seed"][0]["metrics"]["recall"] == 0.75
    assert report["scenarios"][1]["per_seed"][0]["metrics"]["recall"] == 1.0
    assert stages[0].snapshot.expectations[0].planned_start == (
        stages[0].truth[0].start + timedelta(seconds=420))
    with pytest.raises(FrozenInstanceError):
        stages[0].truth = ()  # type: ignore[misc]


def test_precision_scheduled_and_inclusive_preserve_legacy_matching() -> None:
    stage = parse_manifest(corpus())[0]
    a, b, c = evaluate(stage.snapshot).candidates
    unscheduled = replace(c, expectation=None, start_plan_offset_seconds=None,
                          end_plan_offset_seconds=None, strength=Strength.WEAK,
                          schedule_offset_seconds=0,
                          schedule_offset_source=ScheduleOffsetSource.NONE)
    metrics = evaluate_accuracy((a, a, b, unscheduled), stage.truth,
                                planned_span=Span(stage.truth[0].start, stage.truth[-1].end))
    assert metrics.matched_count == 3 and metrics.recall == 1.0
    assert metrics.suggestion_count == 4 and metrics.unscheduled_count == 1
    assert metrics.precision == 2 / 3 and metrics.precision_including_unscheduled == 3 / 4
    assert metrics.wrong_day_count == 0
    only = evaluate_accuracy((unscheduled,), (c.span,))
    assert only.precision == 0 and only.precision_including_unscheduled == 1
    empty = evaluate_accuracy((), ())
    assert empty.precision == empty.precision_including_unscheduled == 0
    assert empty.wrong_day_count is None


def test_wrong_day_inclusive_margin_either_edge_and_unscheduled() -> None:
    stage = parse_manifest(corpus())[0]
    planned = Span(stage.truth[0].start, stage.truth[-1].end)
    lower, upper = planned.start - timedelta(hours=12), planned.end + timedelta(hours=12)
    spans = (Span(lower, lower + timedelta(seconds=1)),
             Span(upper - timedelta(seconds=1), upper),
             Span(lower - timedelta(microseconds=1), lower + timedelta(seconds=1)),
             Span(upper - timedelta(seconds=1), upper + timedelta(microseconds=1)))
    assert evaluate_accuracy(spans, (), planned_span=planned).wrong_day_count == 2
    candidate = evaluate(stage.snapshot).candidates[0]
    candidate = replace(candidate, span=Span(lower - timedelta(days=2), lower),
                        expectation=None, start_plan_offset_seconds=None,
                        end_plan_offset_seconds=None, strength=Strength.WEAK,
                        schedule_offset_source=ScheduleOffsetSource.NONE)
    assert evaluate_accuracy((candidate,), (), planned_span=planned).wrong_day_count == 1


def test_cue_profile_applies_only_supplied_timestamps_and_offsets_reach_policy() -> None:
    stage = parse_manifest(corpus())[0]
    plain = run_manifest((stage,))
    profile = run_manifest((stage,), cue_profile="conference")
    assert profile["cue_phrase_counts"] == {"start": 32, "end": 32}
    assert profile["scenarios"] == plain["scenarios"]
    raw = generate_scenario("clean-day")
    raw["stages"][0]["blocks"][0]["start_cues"] = [raw["stages"][0]["truth"][0]["start"]]
    with_cues = parse_manifest(json.dumps(raw))[0]
    assert evaluate(with_cues.snapshot).candidates[0].start_cue_support
    shifted = replace(stage, snapshot=replace(stage.snapshot, expectations=tuple(
        replace(p, planned_start=p.planned_start + timedelta(seconds=600),
                planned_end=p.planned_end + timedelta(seconds=600))
        for p in stage.snapshot.expectations
        if p.planned_start is not None and p.planned_end is not None)))
    restored = run_manifest((shifted,), producer_offsets=(
        ScheduleOffsetEntry(stage.truth[0].start - timedelta(days=1), -600),))
    assert restored["scenarios"][0]["per_seed"][0]["metrics"] == (
        plain["scenarios"][0]["per_seed"][0]["metrics"])


def test_harness_enables_supplied_cues_only_with_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = generate_scenario("clean-day")
    block = raw["stages"][0]["blocks"][0]
    block["start_cues"] = [raw["stages"][0]["truth"][0]["start"]]
    block["end_cues"] = [raw["stages"][0]["truth"][0]["end"]]
    stages = parse_manifest(json.dumps(raw))
    observed: list[tuple[bool, bool]] = []

    def capture(snapshot: InputSnapshot,
                override: ScheduleOffsetSetting | None = None) -> PolicyResultV3:
        result = evaluate(snapshot, override)
        observed.append((result.candidates[0].start_cue_support,
                         result.candidates[0].end_cue_support))
        return result

    monkeypatch.setattr(policy_v3, "evaluate", capture)
    run_manifest(stages)
    run_manifest(stages, cue_profile="conference")
    run_manifest(parse_manifest(corpus()), cue_profile="conference")
    assert observed == [(False, False), (True, True), (False, False)]


def test_output_contains_no_manifest_strings() -> None:
    raw = generate_scenario("clean-day")
    raw["stages"][0]["schedule"][0]["key"] = "PRIVATE/path/title/key"
    result = run_manifest(parse_manifest(json.dumps(raw)), cue_profile="conference")
    output = json.dumps(result) + markdown_report(result)
    def values(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            return [s for v in cast(dict[str, Any], value).values() for s in values(v)]
        if isinstance(value, list):
            return [s for v in cast(list[Any], value) for s in values(v)]
        return []
    assert all(value not in output for value in values(raw))
    assert "conference" not in output


@pytest.mark.parametrize("payload", ["PRIVATE", "[]", "{}", '{"stages": []}',
                                     '{"stages":[null]}', '{"stages": ["PRIVATE"]}'])
def test_manifest_errors_are_sanitized(payload: str) -> None:
    with pytest.raises(ManifestError, match="^invalid_manifest$"):
        parse_manifest(payload)


@pytest.mark.parametrize("field,value", [
    ("start", "PRIVATE"), ("start", "2000-01-01T09:00:00"),
    ("duration_us", True), ("duration_us", -1), ("duration_us", 315576000000001),
    ("intervals", [{"kind": "PRIVATE", "start_us": 0, "end_us": 1}]),
    ("intervals", [{"kind": "freeze", "start_us": 1, "end_us": 0}]),
    ("intervals", [{"kind": "freeze", "start_us": 0, "end_us": 6000000001}]),
    ("start_cues", ["2002-01-01T09:00:00Z"]), ("private_path", "PRIVATE"),
])
def test_manifest_block_bounds_sanitized(field: str, value: Any) -> None:
    raw = generate_scenario("clean-day")
    raw["stages"][0]["blocks"][0][field] = value
    with pytest.raises(ManifestError, match="^invalid_manifest$"):
        parse_manifest(json.dumps(raw))


def test_duplicate_keys_and_reversed_truth_rejected() -> None:
    raw = generate_scenario("clean-day")
    raw["stages"][0]["schedule"][1]["key"] = "talk-0"
    with pytest.raises(ManifestError):
        parse_manifest(json.dumps(raw))
    raw = generate_scenario("clean-day")
    raw["stages"][0]["truth"][0]["end"] = raw["stages"][0]["truth"][0]["start"]
    with pytest.raises(ManifestError):
        parse_manifest(json.dumps(raw))


@pytest.mark.parametrize("name,code", [("clean-day", 0), ("short-evenly-spaced", 2)])
def test_cli_success_and_target_failure(name: str, code: int, monkeypatch: pytest.MonkeyPatch,
                                        capsys: pytest.CaptureFixture[str]) -> None:
    def read(*args: object, **kwargs: object) -> str:
        return corpus(name)
    monkeypatch.setattr(Path, "read_text", read)
    assert main(["PRIVATE/path", "--markdown"]) == code
    output = capsys.readouterr()
    assert not output.err and "PRIVATE" not in output.out and "2000-" not in output.out
    assert "| Stage |" in output.out


@pytest.mark.parametrize("args", [[], ["PRIVATE", "--seeds", "PRIVATE"],
                                      ["PRIVATE", "--cue-profile", "PRIVATE"],
                                      ["PRIVATE", "--policy-version", "PRIVATE"],
                                      ["PRIVATE", "--magnitude-seconds", "-1"],
                                      ["PRIVATE", "--producer-offset", "PRIVATE", "5"],
                                      ["PRIVATE", "--PRIVATE"], ["--help=PRIVATE"]])
def test_cli_errors_sanitized(args: list[str], monkeypatch: pytest.MonkeyPatch,
                              capsys: pytest.CaptureFixture[str]) -> None:
    def read(*args: object, **kwargs: object) -> str:
        return corpus()
    monkeypatch.setattr(Path, "read_text", read)
    assert main(args) == 1
    output = capsys.readouterr()
    assert output.out == '{"error_count": 1}\n' and not output.err


def test_cli_read_failure_sanitized(monkeypatch: pytest.MonkeyPatch,
                                  capsys: pytest.CaptureFixture[str]) -> None:
    def fail(*args: Any, **kwargs: Any) -> str:
        raise OSError("PRIVATE/path")
    monkeypatch.setattr(Path, "read_text", fail)
    assert main(["PRIVATE/path"]) == 1
    assert capsys.readouterr().out == '{"error_count": 1}\n'


def test_zero_drift_jitter_is_model_specific() -> None:
    truth = parse_manifest(corpus())[0].truth
    for model in ("whole-day", "two-part", "independent"):
        plans = drift_schedule(truth, model=model, magnitude_seconds=0, seed=0, stage_ordinal=0)
        if model == "independent":
            assert plans == truth
        else:
            assert plans != truth  # Historical whole-day/two-part models retain 60 s jitter.
            assert all(abs((a.start - b.start).total_seconds()) <= 60
                       for a, b in zip(plans, truth, strict=True))


@pytest.mark.parametrize("model,first,second", [
    ("whole-day", (579861123, 616913887), (-432768228, -454323409)),
    ("two-part", (-83315631, -96494239), (-689330226, -710682855)),
    ("independent", (296475006, -183524994), (396431071, 122915536)),
])
def test_drift_multiday_seed_contract_and_model_shape(
    model: str, first: tuple[int, int], second: tuple[int, int],
) -> None:
    start = parse_manifest(corpus())[0].truth[0].start
    truth = tuple(Span(start + timedelta(seconds=d * 86400 + i),
                       start + timedelta(seconds=d * 86400 + i + 600))
                  for d in (0, 1) for i in (0, 1000, 4000, 5000))
    plans = drift_schedule(truth, model=model, magnitude_seconds=900, seed=7, stage_ordinal=0)
    offsets = [((a.start - b.start) // timedelta(microseconds=1),
                (a.end - b.end) // timedelta(microseconds=1))
               for a, b in zip(plans, truth, strict=True)]
    assert offsets[0] == first and offsets[4] == second
    assert plans[:4] == drift_schedule(truth[:4], model=model, magnitude_seconds=900,
                                      seed=7, stage_ordinal=0)
    assert plans == drift_schedule(tuple(reversed(truth)), model=model, magnitude_seconds=900,
                                   seed=7, stage_ordinal=0)
    if model == "whole-day":
        assert max(a for a, _ in offsets[:4]) - min(a for a, _ in offsets[:4]) <= 120_000_000
    elif model == "two-part":
        assert abs(offsets[0][0] - offsets[1][0]) <= 120_000_000
        assert abs(offsets[2][0] - offsets[3][0]) <= 120_000_000
        assert abs(offsets[2][0] - offsets[1][0]) > 120_000_000
    else:
        assert plans[0].end - plans[0].start == timedelta(seconds=120)  # Minimum plan clamp.


@pytest.mark.parametrize("model", ["whole-day", "two-part", "independent"])
def test_drift_minimum_plan_length_all_models(model: str) -> None:
    start = parse_manifest(corpus())[0].truth[0].start
    truth = (Span(start, start + timedelta(seconds=1)),)
    plans = drift_schedule(truth, model=model, magnitude_seconds=0, seed=0, stage_ordinal=0)
    assert plans[0].end - plans[0].start == timedelta(seconds=120)


@pytest.mark.parametrize("model", ["whole-day", "two-part"])
def test_drift_event_day_crosses_midnight_with_largest_break_split(model: str) -> None:
    start = parse_manifest(corpus())[0].truth[0].start.replace(hour=23)
    # Midnight falls between talks 1 and 2; the largest planned break is before talk 3.
    truth = tuple(Span(start + timedelta(seconds=i), start + timedelta(seconds=i + 600))
                  for i in (0, 3600, 9000, 12600))
    plans = drift_schedule(tuple(reversed(truth)), model=model, magnitude_seconds=900,
                           seed=7, stage_ordinal=0)
    offsets = [(a.start - b.start).total_seconds() for a, b in zip(plans, truth, strict=True)]
    if model == "whole-day":
        assert max(offsets) - min(offsets) <= 120
    else:
        assert abs(offsets[0] - offsets[1]) <= 120
        assert abs(offsets[2] - offsets[3]) <= 120
        assert abs(offsets[2] - offsets[1]) > 120
    # Moving the same event day away from midnight preserves every seeded draw.
    shifted = tuple(Span(t.start - timedelta(hours=12), t.end - timedelta(hours=12)) for t in truth)
    expected = drift_schedule(shifted, model=model, magnitude_seconds=900, seed=7, stage_ordinal=0)
    assert plans == tuple(Span(t.start + timedelta(hours=12), t.end + timedelta(hours=12))
                          for t in expected)


@pytest.mark.parametrize("model", ["whole-day", "two-part", "independent"])
def test_drift_event_day_six_hour_gap_inclusive(model: str) -> None:
    start = parse_manifest(corpus())[0].truth[0].start
    first = Span(start, start + timedelta(minutes=10))
    boundary = first.end + timedelta(hours=6)
    new_day = Span(boundary, boundary + timedelta(minutes=10))
    separate = drift_schedule((first, new_day), model=model, magnitude_seconds=900,
                              seed=7, stage_ordinal=0)
    next_date = Span(new_day.start + timedelta(days=1), new_day.end + timedelta(days=1))
    expected = drift_schedule((first, next_date), model=model, magnitude_seconds=900,
                              seed=7, stage_ordinal=0)
    assert separate[0] == expected[0]
    assert separate[1] == Span(expected[1].start - timedelta(days=1),
                               expected[1].end - timedelta(days=1))
    same_day = Span(new_day.start - timedelta(microseconds=1),
                    new_day.end - timedelta(microseconds=1))
    together = drift_schedule((first, same_day), model=model, magnitude_seconds=900,
                              seed=7, stage_ordinal=0)
    assert together[1].start - same_day.start != separate[1].start - new_day.start


def test_cli_unexpected_exception_sanitized(monkeypatch: pytest.MonkeyPatch,
                                           capsys: pytest.CaptureFixture[str]) -> None:
    def read(*args: object, **kwargs: object) -> str:
        return corpus()

    monkeypatch.setattr(Path, "read_text", read)

    def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("PRIVATE")

    monkeypatch.setattr(harness_cli, "run_manifest", fail)
    assert main(["PRIVATE/path"]) == 1
    output = capsys.readouterr()
    assert output.out == '{"error_count": 1}\n' and not output.err


@pytest.mark.parametrize("failure", [KeyboardInterrupt, SystemExit])
def test_cli_does_not_catch_base_exceptions(failure: type[BaseException],
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    def read(*args: object, **kwargs: object) -> str:
        return corpus()

    monkeypatch.setattr(Path, "read_text", read)

    def fail(*args: Any, **kwargs: Any) -> None:
        raise failure()

    monkeypatch.setattr(harness_cli, "run_manifest", fail)
    with pytest.raises(failure):
        main(["PRIVATE/path"])


def test_manifest_byte_cap_before_json_and_cli_sanitized(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    assert harness.MAX_MANIFEST_BYTES == 64 * 1024 * 1024
    raw = generate_scenario("clean-day")
    raw["stages"][0]["schedule"][0]["key"] = "é"
    payload = json.dumps(raw, ensure_ascii=False)
    size = len(payload.encode("utf-8"))
    monkeypatch.setattr(harness, "MAX_MANIFEST_BYTES", size)
    assert parse_manifest(payload)
    monkeypatch.setattr(harness, "MAX_MANIFEST_BYTES", size - 1)

    def read(*args: object, **kwargs: object) -> str:
        return payload

    monkeypatch.setattr(Path, "read_text", read)

    def fail(*args: Any, **kwargs: Any) -> None:
        pytest.fail("oversized manifest reached json.loads")

    monkeypatch.setattr(harness.json, "loads", fail)
    for oversized in (payload, " " * (size + 1)):
        with pytest.raises(ManifestError, match="^invalid_manifest$"):
            parse_manifest(oversized)
    assert main(["PRIVATE/path"]) == 1
    output = capsys.readouterr()
    assert output.out == '{"error_count": 1}\n' and not output.err


@pytest.mark.parametrize("version", ["1", "2", "3"])
def test_policy_version_dispatches_to_distinct_module(version: str,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    stages = parse_manifest(corpus())
    observed: list[str] = []

    def v1(snapshot: InputSnapshot) -> PolicyResult:
        observed.append("1")
        return original_v1(snapshot)

    def v2(snapshot: InputSnapshot) -> PolicyResult:
        observed.append("2")
        return original_v2(snapshot)

    def v3(snapshot: InputSnapshot, override: ScheduleOffsetSetting | None) -> PolicyResultV3:
        observed.append("3")
        return evaluate(snapshot, override)

    original_v1, original_v2 = policy.evaluate, policy_v2.evaluate
    monkeypatch.setattr(policy, "evaluate", v1)
    monkeypatch.setattr(policy_v2, "evaluate", v2)
    monkeypatch.setattr(policy_v3, "evaluate", v3)
    run_manifest(stages, policy_version=version)
    assert observed == [version]


@pytest.mark.parametrize("version", ["1", "2"])
def test_cli_producer_offsets_rejected_for_older_policies(
    version: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    def read(*args: object, **kwargs: object) -> str:
        return corpus()

    monkeypatch.setattr(Path, "read_text", read)
    assert main(["PRIVATE/path", "--policy-version", version, "--producer-offset",
                 "2000-01-01T00:00:00Z", "600"]) == 1
    output = capsys.readouterr()
    assert output.out == '{"error_count": 1}\n' and not output.err


@pytest.mark.parametrize("source", ["manifest", "drift"])
def test_planned_span_required_and_cli_sanitized(
    source: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    raw = generate_scenario("clean-day")
    raw["stages"][0]["schedule" if source == "manifest" else "truth"] = []
    payload = json.dumps(raw)
    with pytest.raises(ValueError, match="^planned_span_required$"):
        run_manifest(parse_manifest(payload), schedule_source=source)

    def read(*args: object, **kwargs: object) -> str:
        return payload

    monkeypatch.setattr(Path, "read_text", read)
    assert main(["PRIVATE/path", "--schedule-source", source]) == 1
    output = capsys.readouterr()
    assert output.out == '{"error_count": 1}\n' and not output.err


@pytest.mark.parametrize("missing", [False, True])
def test_worst_seed_max_side_metrics_and_none(missing: bool,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    stage = parse_manifest(corpus())[0]
    base = evaluate_accuracy(stage.truth, stage.truth,
                             planned_span=Span(stage.truth[0].start, stage.truth[-1].end))
    errors = ("median_start_error_seconds", "median_end_error_seconds",
              "p95_start_error_seconds", "p95_end_error_seconds")
    maxima = (*errors, "truth_count", "suggestion_count", "unscheduled_count", "wrong_day_count")
    # Different metrics peak on different seeds; a missing error is worse than any number.
    rows = [replace(base, **{metric: 100 + i}) for i, metric in enumerate(maxima)]
    if missing:
        rows += [replace(base, **{metric: None}) for metric in (*errors, "wrong_day_count")]
    results = iter(rows)

    def metrics(*args: Any, **kwargs: Any) -> AccuracyMetrics:
        return next(results)

    monkeypatch.setattr(harness, "evaluate_accuracy", metrics)
    seeds: Sequence[int] = tuple(range(len(rows)))
    scenario = run_manifest((stage,), seeds=seeds)["scenarios"][0]
    for i, metric in enumerate(maxima):
        missing_fields = (*errors, "wrong_day_count")
        if missing and metric in missing_fields:
            expected = {"seed": len(maxima) + missing_fields.index(metric), "value": None}
        else:
            expected = {"seed": i, "value": 100 + i}
        assert scenario["worst_seed"][metric] == expected
