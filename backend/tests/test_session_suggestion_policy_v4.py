"""Exact chain arithmetic and synthetic acceptance evidence for policy v4."""
import json
from dataclasses import fields, replace
from datetime import timedelta
from fractions import Fraction
from time import perf_counter
from typing import Any
from unittest.mock import patch

import pytest

from app.contexts.production.session_suggestions import policy_v2, policy_v3, policy_v4
from app.contexts.production.session_suggestions.contracts import (
    CandidateV3,
    CandidateV4,
    EdgeKind,
    InputSnapshot,
    ScheduleOffsetSetting,
    Span,
    Strength,
)
from app.contexts.production.session_suggestions.evaluation import evaluate_accuracy
from app.contexts.production.session_suggestions.harness import parse_manifest, run_manifest
from app.contexts.production.session_suggestions.policy_v2 import (
    Changeover,
    Edge,
    WeightedChangeover,
)
from app.contexts.production.session_suggestions.policy_v4 import (
    Alignment,
    best_alignment,
    edge_cost,
    evaluate,
    retain,
    round_seconds,
)
from app.contexts.production.session_suggestions.scenarios import SCENARIOS, generate_scenario
from tests.test_session_suggestion_policy import asset, at, expectation
from tests.test_session_suggestion_policy_v3 import override


def chain(plans: tuple[tuple[int, int], ...], changes: tuple[tuple[int, int], ...],
          setting: ScheduleOffsetSetting | None = None) -> Alignment:
    weighted = tuple(WeightedChangeover(Changeover(at(a), at(b), EdgeKind.FREEZE),
                                        Fraction(10), Fraction(0)) for a, b in changes)
    return best_alignment(
        tuple(expectation(a, b, i + 1) for i, (a, b) in enumerate(plans)), weighted,
        tuple(Edge(c.span.end, c.span.kind, False, False) for c in weighted),
        tuple(Edge(c.span.start, c.span.kind, False, False) for c in weighted),
        (0,) * len(changes), (0,) * len(changes), setting)


def path(node: Alignment) -> tuple[tuple[Edge, Edge], ...]:
    result: list[tuple[Edge, Edge]] = []
    while node.parent is not None:
        assert node.edges is not None
        result.append(node.edges)
        node = node.parent
    return tuple(reversed(result))


def test_lateness_carried_jump_cost_and_shifted_fallback() -> None:
    node = chain(((0, 300), (5000, 5300), (9400, 9700)),
                 ((600, 600), (900, 900), (10000, 10000), (10300, 10300)))
    # Four strengths, one 600/30 anchor charge, no later lateness changes.
    assert node.score == 20 and node.lateness == 600_000_000
    edges = path(node)
    assert [(a.at, b.at) for a, b in edges] == [
        (at(600), at(900)), (at(5600), at(5900)), (at(10000), at(10300))]
    assert edges[1][0].kind == edges[1][1].kind == EdgeKind.SCHEDULE
    assert node.parent is not None and node.parent.cursor == 2
    jump = chain(((0, 300),), ((600, 600), (960, 960)))
    assert jump.score == -1  # 20 - 600/30 - 60/60
    assert edge_cost(600_000_001, 600_000_000, False) == Fraction(1, 60_000_000)


def test_fallback_start_end_and_pending_anchor_do_not_consume_evidence() -> None:
    node = chain(((0, 300), (5000, 5300)), ((5500, 5500),))
    edges = path(node)
    assert node.score == 10 - Fraction(500, 30)
    assert edges[0][0].kind == edges[0][1].kind == EdgeKind.SCHEDULE
    assert edges[1][1].kind == EdgeKind.SCHEDULE and edges[1][1].at == at(5800)
    assert node.cursor == 1 and node.lateness == 500_000_000 and not node.pending_anchor
    # A fallback start also retains the anchor for the first observed end.
    end_only = chain(((0, 3000),), ((3600, 3600),), override((0, 600)))
    assert end_only.score == 10
    assert path(end_only)[0][0] == Edge(at(600), EdgeKind.SCHEDULE, False, False)


def test_state_key_retains_different_lateness_and_pending_anchor() -> None:
    root = Alignment(Fraction(0), -1, 0, True, None, None)
    edges = (Edge(at(0), EdgeKind.SCHEDULE, False, False),
             Edge(at(300), EdgeKind.SCHEDULE, False, False))
    states: dict[tuple[int, int, bool], Alignment] = {}
    for late, pending in ((0, True), (0, False), (600_000_000, False)):
        retain(states, Alignment(Fraction(0), 1, late, pending, root, edges))
    assert set(states) == {(1, 0, True), (1, 0, False), (1, 600_000_000, False)}
    retain(states, Alignment(Fraction(1), 1, 0, False, root, edges))
    assert states[1, 0, False].score == 1


def test_override_mid_block_resets_next_observed_edge_and_latest_entry_wins() -> None:
    snapshot = InputSnapshot((expectation(0, 1800), expectation(2100, 3900, 2)),
                            (asset(0, 4800, freezes=((1800, 3000),),
                                   silences=((1800, 3000),)),))
    setting = override((1, 100), (2000, 900), (2200, -300))
    result = evaluate(snapshot, setting)
    assert not result.blocks
    scheduled = [c for c in result.candidates if isinstance(c, CandidateV4) and c.expectation]
    assert [c.span for c in scheduled] == [Span(at(0), at(1800)), Span(at(3000), at(4800))]
    assert [c.schedule_offset_source for c in scheduled] == ['none', 'producer']
    assert [c.schedule_offset_seconds for c in scheduled] == [0, 900]
    assert len(policy_v3.evaluate(snapshot, setting).blocks) == 1
    assert policy_v3.evaluate(snapshot, setting).blocks[0].schedule_offset_source != 'producer'
    assert chain(((0, 300), (2100, 2400)),
                 ((0, 0), (300, 300), (3060, 3060), (3360, 3360)),
                 override((2000, 900))).score == 38  # 40 - 60/30 after reset
    assert evaluate(snapshot, override()) == evaluate(snapshot)


@pytest.mark.parametrize('sign', [-1, 1])
@pytest.mark.parametrize('extra,observed', [(0, True), (1, False)])
def test_hard_bound_inclusive_even_with_producer_window(sign: int, extra: int,
                                                        observed: bool) -> None:
    late = sign * (policy_v4.HARD_BOUND + extra)
    node = chain(((10000, 13000),), ((10000 + late, 10000 + late),
                                    (13000 + late, 13000 + late)),
                 override((0, sign * policy_v4.HARD_BOUND)))
    a, b = path(node)[0]
    assert (a.kind == EdgeKind.FREEZE) == observed
    assert (b.kind == EdgeKind.FREEZE) == observed
    if not observed:
        assert node.cursor == -1 and node.pending_anchor
        assert a.at == at(10000 + sign * policy_v4.HARD_BOUND)


@pytest.mark.parametrize('distance,observed', [(1200, True), (1201, False)])
def test_chain_window_inclusive(distance: int, observed: bool) -> None:
    # Keep the end outside the start window, to avoid an alternative start.
    node = chain(((0, 3000),), ((distance, distance), (3000 + distance, 3000 + distance)))
    assert (path(node)[0][0].kind == EdgeKind.FREEZE) == observed


@pytest.mark.parametrize('microseconds,seconds', [
    (499999, 0), (500000, 1), (1500000, 2), (-499999, 0), (-500000, -1), (-1500000, -2)])
def test_offset_rounding_ties_away_from_zero(microseconds: int, seconds: int) -> None:
    assert round_seconds(microseconds) == seconds


def test_candidate_offset_roundtrip_and_legacy_validation_unchanged() -> None:
    from app.contexts.production.session_suggestions.serialization import (
        candidate,
        candidate_document,
    )

    snapshot = InputSnapshot((expectation(0, 300),), (asset(.5, 300.5),))
    value = evaluate(snapshot).candidates[0]
    assert isinstance(value, CandidateV4)
    assert value.schedule_offset_seconds == 1 and value.schedule_offset_source == 'estimated'
    assert value.strength == Strength.MEDIUM
    for seconds, source in ((5400, 'estimated'), (7200, 'producer'), (0, 'none')):
        adjusted = replace(value, schedule_offset_seconds=seconds,
                           schedule_offset_source=type(value.schedule_offset_source)(source))
        assert candidate({**candidate_document(adjusted), 'policy_version': '4'}) == adjusted
    with pytest.raises(ValueError):
        replace(value, schedule_offset_seconds=5401)
    components: dict[str, Any] = {f.name: getattr(value, f.name) for f in fields(value)}
    components["schedule_offset_seconds"] = 5400
    with pytest.raises(ValueError):
        CandidateV3(**components)


@pytest.mark.parametrize('name', SCENARIOS)
def test_suite_v4_results_pinned(name: str) -> None:
    stages = parse_manifest(json.dumps(generate_scenario(name)))
    row = run_manifest(stages, policy_version='4')['scenarios'][0]['per_seed'][0]
    short = name == 'short-evenly-spaced'
    count = 2 if name == 'multi-part' else 8 if short else 3
    assert row['metrics'] == {
        'truth_count': count, 'suggestion_count': count + int(short), 'matched_count': count,
        'recall': 1.0, 'precision': 7 / 8 if short else 1.0,
        'precision_including_unscheduled': 8 / 9 if short else 1.0,
        'unscheduled_count': int(short), 'median_start_error_seconds': 0.0,
        'median_end_error_seconds': 0.0,
        'p95_start_error_seconds': (120.0 if short else
                                    300.0 if name == 'late-recording-start' else 0.0),
        'p95_end_error_seconds': 0.0, 'wrong_day_count': 0,
        'count_within_60_seconds': 7 if short else 2 if name == 'late-recording-start' else count,
    }
    assert row['skips'] == {'no_timing_evidence': 0, 'no_segmentation': 0,
                            'clock_implausible': int(name == 'wrong-clock'), 'no_coverage': 0,
                            'no_planned_time': 0, 'already_realized': 0}
    assert row['target_pass']


@pytest.mark.parametrize('anchored,score,own_score', [(False, 81, 80), (True, 95, 94)])
def test_short_evenly_spaced_residual_assignment_and_scores(anchored: bool, score: int,
                                                           own_score: int) -> None:
    stage = parse_manifest(json.dumps(generate_scenario('short-evenly-spaced')))[0]
    first = stage.snapshot.expectations[0].planned_start
    assert first is not None
    setting = replace(override((0, -420)), entries=(replace(
        override((0, -420)).entries[0], effective_from=first),)) if anchored else None
    with patch.object(policy_v4, 'align', wraps=policy_v4.align) as aligned:
        result = evaluate(stage.snapshot, setting)
    assert aligned.call_args is not None
    best = best_alignment(*aligned.call_args.args)
    assert best.score == score
    # Best own-identity path uses coverage at both outer edges. Strength = 102;
    # first lateness -540, then -420, finally -300; each later change costs 2.
    assert Fraction(102) - edge_cost(-540_000_000, -420_000_000 if anchored else 0, True) - 4 == (
        own_score)
    origin = stage.truth[0].start
    expected = [(-120, 300), (420, 720), (840, 1140), (1260, 1560),
                (1680, 1980), (2100, 2400), (2940, 3240), (3360, 3660)]
    scheduled = [c for c in result.candidates if c.expectation]
    assert [(c.expectation.id, c.span) for c in scheduled if c.expectation] == [
        (e.id, Span(origin + timedelta(seconds=a), origin + timedelta(seconds=b)))
        for e, (a, b) in zip(stage.snapshot.expectations, expected, strict=True)]
    assert [c.span for c in result.candidates if c.expectation is None] == [stage.truth[6]]
    assert evaluate_accuracy(result.candidates, stage.truth).recall == 1.0
    # Recall's interval matching includes unscheduled activity and does not prove identity.
    assert sum(c.span == truth for c, truth in zip(scheduled, stage.truth, strict=True)) == 5


def asymmetric_fixture() -> InputSnapshot:
    truth = ((0, 600), (780, 1860), (2160, 2580), (2700, 4200), (4620, 5400))
    holds = ((600, 780), (1860, 2160), (2580, 2700), (4200, 4620), (5400, 6000))
    return InputSnapshot(tuple(expectation(a + 1500, b + 1500, i + 1)
                               for i, (a, b) in enumerate(truth)),
                         (asset(0, 6000, freezes=holds, silences=holds),))


def test_asymmetric_shift_override_restores_every_own_expectation() -> None:
    snapshot = asymmetric_fixture()
    truth = tuple(Span(e.planned_start - timedelta(seconds=1500),
                       e.planned_end - timedelta(seconds=1500)) for e in snapshot.expectations
                  if e.planned_start is not None and e.planned_end is not None)
    plain, anchored = evaluate(snapshot), evaluate(snapshot, override((1500, -1500)))
    assert [c.span for c in anchored.candidates] == list(truth)
    assert [c.expectation.id for c in anchored.candidates if c.expectation] == [
        e.id for e in snapshot.expectations]
    assert evaluate_accuracy(anchored.candidates, truth).recall == 1.0
    assert all(isinstance(c, CandidateV4) and c.schedule_offset_source == 'producer'
               and c.schedule_offset_seconds == -1500 for c in anchored.candidates)
    assert [c.span for c in plain.candidates if c.expectation] != list(truth)


def test_clean_day_zero_drift_matches_v2_and_deterministic_input_permutations() -> None:
    stage = parse_manifest(json.dumps(generate_scenario('clean-day')))[0]
    a = evaluate_accuracy(evaluate(stage.snapshot).candidates, stage.truth)
    b = evaluate_accuracy(policy_v2.evaluate(stage.snapshot).candidates, stage.truth)
    assert (a.recall, a.median_start_error_seconds, a.median_end_error_seconds) == (
        b.recall, b.median_start_error_seconds, b.median_end_error_seconds)
    assert evaluate(stage.snapshot) == evaluate(replace(
        stage.snapshot, expectations=stage.snapshot.expectations[::-1],
        assets=stage.snapshot.assets[::-1]))


def test_full_day_thirty_talks_eighty_changeovers_cost_bound() -> None:
    # 29 changeovers and 49 within-talk freezes, plus two coverage bounds = 80.
    holds = tuple((i * 1500 + 1320, (i + 1) * 1500) for i in range(29))
    noise = tuple((i * 1500 + offset, i * 1500 + offset + 60)
                  for i in range(30) for offset in (300, 700))[:49]
    snapshot = InputSnapshot(tuple(expectation(i * 1500, i * 1500 + 1320, i + 1)
                                   for i in range(30)),
                             (asset(0, 44820, freezes=tuple(sorted(holds + noise)),
                                    silences=holds),))
    started = perf_counter()
    result = evaluate(snapshot)
    elapsed = perf_counter() - started
    assert len([c for c in result.candidates if c.expectation]) == 30
    assert elapsed < 3.0, elapsed


def test_equal_score_earliest_edges_and_lowest_expectation_id() -> None:
    node = chain(((0, 300),), ((-30, -30), (30, 30), (300, 300)))
    assert node.score == Fraction(37, 2)
    assert path(node)[0][0].at == at(-30)
    low, high = expectation(0, 300, 1), expectation(0, 300, 2)
    snapshot = InputSnapshot((high, low), (asset(0, 300),))
    result = evaluate(snapshot)
    assert result == evaluate(replace(snapshot, expectations=(low, high)))
    assert [c.expectation.id for c in result.candidates if c.expectation] == [low.id, high.id]
    assert result.candidates[0].start_edge_kind == EdgeKind.COVERAGE
    assert [c.span for c in result.candidates] == [Span(at(0), at(300)), Span(at(300), at(600))]
    assert result.candidates[1].end_edge_kind == EdgeKind.SCHEDULE
    assert result.candidates[1].strength == Strength.WEAK


def test_shared_changeover_strength_once_cues_per_edge_and_immutability() -> None:
    from dataclasses import FrozenInstanceError

    media = replace(asset(0, 720, freezes=((300, 420),), silences=((300, 420),)),
                    start_cues=(at(420),), end_cues=(at(300),))
    snapshot = InputSnapshot((expectation(0, 300), expectation(420, 720, 2)), (media,))
    with patch.object(policy_v4, 'align', wraps=policy_v4.align) as aligned:
        result = evaluate(snapshot)
    assert aligned.call_args is not None
    assert best_alignment(*aligned.call_args.args).score == 68  # 30 + 6 + 30 + 1 + 1
    assert result.candidates[0].end_cue_support and result.candidates[1].start_cue_support
    assert all(c.strength == Strength.STRONG for c in result.candidates)
    with pytest.raises(FrozenInstanceError):
        result.candidates[0].overlap = True  # type: ignore[misc]
    assert snapshot.assets == (media,)


def test_v2_coverage_skips_minimum_and_clock_filter_still_use_printed_plan() -> None:
    snapshot = InputSnapshot((expectation(None, None), expectation(4000, 4030, 2)),
                            (asset(0, 10000), asset(100000, 110000, n=20)))
    result = evaluate(snapshot, override((0, 7200)))
    assert result.skips.no_planned_time == 1 and result.skips.no_coverage == 1
    assert result.skips.clock_implausible == 1
    assert all(c.expectation is None for c in result.candidates)
    assert all(isinstance(c, CandidateV4) and c.schedule_offset_seconds == 0
               and c.schedule_offset_source == 'none' for c in result.candidates)
    assert all(snapshot.assets[1].timing not in c.timing_references for c in result.candidates)


def test_fallback_paths_with_same_cursor_keep_lateness_for_future_edges() -> None:
    # Cursor-only pruning loses this globally best path (score -5 versus -10).
    # The observed start carries -300 through three fallback edges; the later
    # observed end changes lateness to +600. Cost is 300/30 + 900/60.
    node = chain(((0, 600), (3600, 3900), (3900, 4500), (5400, 6000)),
                 ((3000, 3000), (3300, 3300), (6600, 6600), (7200, 7200), (7500, 7500)))
    assert node.score == 20 - 10 - 15
    assert [(a.at, b.at) for a, b in path(node)] == [
        (at(0), at(600)), (at(3300), at(3600)), (at(3600), at(4200)), (at(5100), at(6600))]
