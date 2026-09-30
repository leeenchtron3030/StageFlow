"""Media-free v5 harness/scenario fixtures and the ported generator's seed contract."""
import json
from dataclasses import asdict, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from app.contexts.production.session_suggestions import harness, policy_v5
from app.contexts.production.session_suggestions.contracts import (
    InputSnapshot,
    PolicyResultV3,
    ScheduleOffsetSetting,
)
from app.contexts.production.session_suggestions.harness import (
    ManifestError,
    parse_manifest,
    run_manifest,
)
from app.contexts.production.session_suggestions.harness_cli import main
from app.contexts.production.session_suggestions.policy_v3 import evaluate as v3
from app.contexts.production.session_suggestions.scenarios import (
    SCENARIOS,
    generate_scenario,
    realistic_schedule_error,
)
from app.contexts.production.session_suggestions.serialization import asset, asset_document


@pytest.mark.parametrize("name", SCENARIOS)
def test_every_v5_scenario_metrics_pinned(name: str) -> None:
    raw = generate_scenario(name)
    report = run_manifest(parse_manifest(json.dumps(raw)), policy_version="5",
                          cue_profile="conference")
    row = report["scenarios"][0]["per_seed"][0]
    count = 2 if name == "multi-part" else 8 if name == "short-evenly-spaced" else 3
    unscheduled = int(name in ("short-evenly-spaced", "cue-only-edge", "recording-starts-early"))
    assert row["metrics"] == {
        "truth_count": count, "suggestion_count": count + unscheduled,
        "matched_count": count, "recall": 1.0,
        "precision": 7 / 8 if name == "short-evenly-spaced" else 1.0,
        "precision_including_unscheduled": count / (count + unscheduled),
        "unscheduled_count": unscheduled, "median_start_error_seconds": 0.0,
        "median_end_error_seconds": 0.0, "p95_end_error_seconds": 0.0,
        "p95_start_error_seconds": 300.0 if name == "late-recording-start" else 0.0,
        "wrong_day_count": 0,
        "count_within_60_seconds": 2 if name == "late-recording-start" else count,
    }
    assert row["skips"] == {
        "no_timing_evidence": 0, "no_segmentation": 0, "no_coverage": 0,
        "no_planned_time": 0, "already_realized": 0,
        "clock_implausible": int(name == "wrong-clock"),
        "outside_program": int(name == "content-after-program"),
    }
    assert row["target_pass"]
    assert raw == generate_scenario(name)


@pytest.mark.parametrize("name", ["clean-day", "recording-gaps", "multi-part", "wrong-clock",
                                  "late-recording-start", "false-in-talk-end-cue"])
def test_no_cues_matches_v3_on_unaffected_scenarios(name: str) -> None:
    snapshot = parse_manifest(json.dumps(generate_scenario(name)))[0].snapshot
    snapshot = replace(snapshot, assets=tuple(replace(a, start_cues=(), end_cues=())
                                              for a in snapshot.assets))
    old, new = v3(snapshot), policy_v5.evaluate(snapshot)
    assert new.candidates == old.candidates and new.blocks == old.blocks
    new_skips = asdict(new.skips)
    assert new_skips.pop("outside_program") == 0
    assert new_skips == asdict(old.skips)


def test_old_manifest_parse_and_persisted_asset_round_trip_identical() -> None:
    raw = generate_scenario("clean-day")
    block = raw["stages"][0]["blocks"][0]
    block["start_cues"] = [block["start"]]
    block["end_cues"] = [raw["stages"][0]["truth"][0]["end"]]
    old = parse_manifest(json.dumps(raw))[0]
    media = old.snapshot.assets[0]
    assert media.changeover_cues == media.specific_start_cues == media.specific_end_cues == ()
    assert asset(asset_document(media)) == media
    for role in ("start_cues", "end_cues"):
        block[role] = [{"at": t, "specific": False} for t in block[role]]
    block["changeover_cues"] = []
    assert parse_manifest(json.dumps(raw))[0] == old


def test_specific_and_changeover_manifest_projection_and_profile_disable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = generate_scenario("cue-only-edge")
    block = raw["stages"][0]["blocks"][0]
    block["changeover_cues"] = [{"at": block["start"], "specific": True}]
    stages = parse_manifest(json.dumps(raw))
    media = stages[0].snapshot.assets[0]
    assert media.start_cues == media.specific_start_cues
    assert media.end_cues == media.specific_end_cues
    assert media.changeover_cues == (datetime.fromisoformat(block["start"]),)
    assert media.transcript is not None
    observed: list[InputSnapshot] = []
    original = policy_v5.evaluate

    def capture(snapshot: InputSnapshot,
                override: ScheduleOffsetSetting | None = None) -> PolicyResultV3:
        observed.append(snapshot)
        return original(snapshot, override)

    monkeypatch.setattr(policy_v5, "evaluate", capture)
    run_manifest(stages, policy_version="5")
    run_manifest(stages, policy_version="5", cue_profile="conference")
    disabled = observed[0].assets[0]
    assert (disabled.start_cues == disabled.end_cues == disabled.changeover_cues
            == disabled.specific_start_cues == disabled.specific_end_cues == ())
    assert disabled.transcript is None
    assert observed[1] == stages[0].snapshot


@pytest.mark.parametrize("hit", [
    {"at": "2000-01-01T09:00:00Z", "specific": 1},
    {"at": "2000-01-01T09:00:00Z", "phrase": "PRIVATE"},
    {"specific": True}, {"at": "2000-01-01T09:00:00"},
    {"at": "2000-01-02T09:00:00Z"}, None, 1,
])
@pytest.mark.parametrize("role", ["start_cues", "end_cues", "changeover_cues"])
def test_malformed_cues_sanitized_and_bounded(hit: Any, role: str) -> None:
    raw = generate_scenario("clean-day")
    raw["stages"][0]["blocks"][0][role] = [hit]
    with pytest.raises(ManifestError, match="^invalid_manifest$"):
        parse_manifest(json.dumps(raw))


def test_schema_has_additive_cue_forms() -> None:
    schema = json.loads(Path(harness.__file__).with_name("corpus-manifest.schema.json").read_text())
    defs = schema["$defs"]
    for role in ("start_cues", "end_cues", "changeover_cues"):
        assert defs["block"]["properties"][role]["items"] == {"$ref": "#/$defs/cue"}
    assert defs["cue"]["oneOf"][0] == {"$ref": "#/$defs/time"}
    assert defs["cue"]["oneOf"][1]["properties"]["specific"] == {"type": "boolean"}


def test_v5_cli_dispatch_offsets_and_determinism(monkeypatch: pytest.MonkeyPatch,
                                                 capsys: pytest.CaptureFixture[str]) -> None:
    payload = json.dumps(generate_scenario("clean-day"))

    def read(*args: object, **kwargs: object) -> str:
        return payload

    monkeypatch.setattr(Path, "read_text", read)
    args = ["PRIVATE", "--policy-version", "5", "--producer-offset",
            "2000-01-01T00:00:00Z", "0", "--cue-profile", "conference"]
    assert main(args) == 0
    first = capsys.readouterr()
    assert not first.err and "PRIVATE" not in first.out
    assert json.loads(first.out)["policy_version"] == 5
    assert main(args) == 0
    assert capsys.readouterr() == first
    stages = parse_manifest(payload)
    for model in ("whole-day", "two-part", "independent"):
        a = run_manifest(stages, policy_version="5", schedule_source="drift",
                         drift_model=model, magnitude_seconds=600, seeds=(7, 3))
        b = run_manifest(stages, policy_version="5", schedule_source="drift",
                         drift_model=model, magnitude_seconds=600, seeds=(3, 7, 3))
        assert a == b


def test_ported_generator_seed_and_cue_draw_order_pinned() -> None:
    stage, timeline = realistic_schedule_error(7, talk_count=3, cues=True, timeline=True)
    assert timeline["talks"] == [
        {"schedule_index": 0, "start_seconds": -71, "end_seconds": 1078},
        {"schedule_index": 1, "start_seconds": 1240, "end_seconds": 2402},
        {"schedule_index": 2, "start_seconds": 2577, "end_seconds": 3475},
    ]
    base = datetime.fromisoformat(stage["schedule"][0]["planned_start"])
    hits = {role: [(int((datetime.fromisoformat(hit["at"]) - base).total_seconds()),
                    hit["specific"]) for b in stage["blocks"] for hit in b.get(role, [])]
            for role in ("start_cues", "end_cues", "changeover_cues")}
    assert hits == {
        "start_cues": [(-72, True), (1235, True), (2575, True)],
        "end_cues": [(549, False), (1080, True), (1770, False), (2396, True),
                     (2720, False), (3479, True)],
        "changeover_cues": [(1080, True), (2411, True), (3485, True)],
    }
    assert stage == realistic_schedule_error(7, talk_count=3, cues=True)
    assert realistic_schedule_error(7, talk_count=3) == {
        **stage, "blocks": [{k: v for k, v in block.items() if not k.endswith("_cues")}
                            for block in stage["blocks"]]}


@pytest.mark.parametrize("recall", [0.0, 0.5, 1.0])
def test_generator_recall_false_hits_bounds_and_optional_edits(recall: float) -> None:
    for seed in range(1, 21):
        stage, timeline = realistic_schedule_error(seed, talk_count=4, cues=True,
                                                   cue_recall=recall, dropped=True,
                                                   added=True, after_program=True, timeline=True)
        parsed = parse_manifest(json.dumps({"stages": [stage]}))[0]
        assert len(parsed.truth) == 5 and len(parsed.snapshot.expectations) == 4
        truth_starts = [t.start for t in parsed.truth]
        truth_ends = [t.end for t in parsed.truth]
        for role, truth in (("start_cues", truth_starts), ("end_cues", truth_ends),
                            ("changeover_cues", truth_ends)):
            hits = [hit for block in stage["blocks"] for hit in block.get(role, [])]
            kept = [hit for hit in hits if hit["specific"]]
            if recall in (0, 1):
                assert len(kept) == int(recall * 5)
            assert all(any(abs(datetime.fromisoformat(h["at"]) - t) <= timedelta(seconds=10)
                           for t in truth) for h in kept)
            false = [h for h in hits if not h["specific"]]
            assert len(false) == (5 if role == "end_cues" else 0)
            assert all(any(t.start + timedelta(seconds=60) <= datetime.fromisoformat(h["at"])
                           <= t.end - timedelta(seconds=60) for t in parsed.truth) for h in false)
        plain, plain_timeline = realistic_schedule_error(seed, talk_count=4, dropped=True,
                                                         added=True, after_program=True,
                                                         timeline=True)
        assert timeline == plain_timeline
        assert stage["schedule"] == plain["schedule"] and stage["truth"] == plain["truth"]


@pytest.mark.parametrize("options", [
    {"seed": -1}, {"seed": True}, {"talk_count": 1}, {"slot_seconds": 1199},
    {"cue_recall": -0.1}, {"cue_recall": 1.1}, {"cue_recall": float("nan")},
    {"cue_recall": True}, {"cues": 1},
])
def test_generator_invalid_options(options: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="^invalid_scenario_options$"):
        arguments: dict[str, Any] = {"seed": 7}
        arguments.update(options)
        realistic_schedule_error(**arguments)
