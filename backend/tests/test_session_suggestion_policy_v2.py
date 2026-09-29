"""Only synthetic timelines; recorded v1 has its unchanged separate suite."""
from dataclasses import asdict, replace
from fractions import Fraction

import pytest

from app.contexts.events import ProgramExpectationLifecycle
from app.contexts.production.session_suggestions.contracts import (
    POLICY_V1,
    POLICY_V2,
    POLICY_V3,
    AssetInput,
    EdgeKind,
    InputSnapshot,
    Span,
    Strength,
    SuggestionRun,
)
from app.contexts.production.session_suggestions.policy import Changeover
from app.contexts.production.session_suggestions.policy import evaluate as evaluate_v1
from app.contexts.production.session_suggestions.policy_v2 import evaluate, weight
from tests.test_session_suggestion_policy import NOW, asset, at, eid, expectation
from tests.test_session_suggestions import Harness


def scheduled(snapshot: InputSnapshot):
    return tuple(c for c in evaluate(snapshot).candidates if c.expectation is not None)


def test_consecutive_talks_share_merged_title_card_with_audio() -> None:
    result = scheduled(InputSnapshot((expectation(0, 1700), expectation(1800, 3600, 2)),
                                    (asset(freezes=((1700, 1730), (1745, 1800))),)))
    assert [c.span for c in result] == [Span(at(0), at(1700)), Span(at(1800), at(3600))]
    assert all(c.strength == Strength.MEDIUM and not c.overlap for c in result)
    assert result[0].end_edge_kind == result[1].start_edge_kind == EdgeKind.FREEZE


def test_shared_changeover_strength_is_counted_once_in_joint_score() -> None:
    media = asset(0, 3000, freezes=((1000, 1060), (1200, 1800)), silences=((1200, 1500),))
    result = scheduled(InputSnapshot((expectation(0, 1000), expectation(1060, 3000, 2)), (media,)))
    # Sharing the first freeze scores 61. Sharing the silent second freeze scores
    # 80 - (200+740)/30 = 48 2/3. Incorrect double-counting would score 68 2/3
    # for the second freeze, defeating the first (incorrectly 62).
    assert [c.span for c in result] == [Span(at(0), at(1000)), Span(at(1060), at(3000))]


def test_equal_plan_starts_are_ordered_by_lowest_expectation_id() -> None:
    first, second = expectation(0, 1800), expectation(0, 1800, 2)
    snapshot = InputSnapshot((second, first), (asset(0, 3600, freezes=((1800, 1860),)),))
    result = scheduled(snapshot)
    assert result[0].expectation is not None and result[0].expectation.id == first.id
    assert evaluate(snapshot) == evaluate(replace(snapshot, expectations=(first, second)))


@pytest.mark.parametrize("length,recognized", [(45, False), (59, False), (60, True)])
def test_freeze_threshold_is_inclusive(length: int, recognized: bool) -> None:
    result = scheduled(InputSnapshot((expectation(0, 3000),),
                                    (asset(0, 7000, freezes=((3000, 3000 + length),)),)))
    assert (result[0].end_edge_kind == EdgeKind.FREEZE) is recognized


@pytest.mark.parametrize("gap,recognized", [(15, True), (16, False)])
def test_merge_gap_threshold(gap: int, recognized: bool) -> None:
    result = scheduled(InputSnapshot((expectation(0, 3000),), (asset(
        0, 7000, freezes=((3000, 3030), (3030 + gap, 3060 + gap))),)))
    assert (result[0].end_edge_kind == EdgeKind.FREEZE) is recognized


def test_long_silent_changeover_beats_nearer_slide_freeze() -> None:
    media = asset(0, 10000, freezes=((1900, 2000), (2050, 2450)), silences=((2050, 2450),))
    result = scheduled(InputSnapshot((expectation(2000, 10000),), (media,)))
    assert result[0].span.start == at(2450)
    assert result[0].start_silence_support and result[0].strength == Strength.STRONG


@pytest.mark.parametrize("drift", [-900, 0, 900])
def test_drift_joint_alignment_is_monotone(drift: int) -> None:
    plans = (expectation(drift, 3000 + drift), expectation(3300 + drift, 6600 + drift, 2),
             expectation(6900 + drift, 10200 + drift, 3))
    media = asset(0, 10200, freezes=((3000, 3300), (6600, 6900)),
                  silences=((3000, 3300), (6600, 6900)))
    result = scheduled(InputSnapshot(plans, (media,)))
    assert [c.span for c in result] == [Span(at(0), at(3000)), Span(at(3300), at(6600)),
                                       Span(at(6900), at(10200))]
    assert all(not c.overlap for c in result)


@pytest.mark.parametrize("gap,kind", [(29, EdgeKind.SCHEDULE), (30, EdgeKind.GAP),
                                     (3600, EdgeKind.GAP)])
def test_lunch_and_exact_coverage_gap_threshold(gap: int, kind: EdgeKind) -> None:
    result = scheduled(InputSnapshot((expectation(0, 3000), expectation(3000 + gap, 9000, 2)),
                                    (asset(0, 3000), asset(3000 + gap, 9000, n=20))))
    assert result[0].end_edge_kind == result[1].start_edge_kind == kind
    assert result[0].span.end <= result[1].span.start


def test_owner_probe_overlapping_schedule_fallbacks_keep_planned_times() -> None:
    plans = (expectation(2000, 6000), expectation(4000, 8000, 2))
    result = scheduled(InputSnapshot(plans, (asset(0, 10000),)))
    assert len(result) == 2
    assert [c.span for c in result] == [Span(at(2000), at(6000)), Span(at(4000), at(8000))]
    assert all(c.overlap and c.strength == Strength.WEAK for c in result)
    assert all(c.start_edge_kind == c.end_edge_kind == EdgeKind.SCHEDULE for c in result)


def test_fallback_overlap_does_not_reset_evidence_cursor() -> None:
    result = scheduled(InputSnapshot(
        (expectation(0, 3000), expectation(1000, 5000, 2), expectation(4000, 9000, 3)),
        (asset(0, 9000, freezes=((3000, 3300),)),)))
    assert len(result) == 3
    assert result[0].span.end == at(3000)
    assert result[-1].span.start >= at(3300)
    assert all(c.strength == Strength.WEAK for c in result if c.overlap)


def test_schedule_end_fallback_does_not_allow_reusing_observed_start() -> None:
    media = replace(asset(0, 10000, freezes=((3400, 4000),)), start_cues=(at(4000),))
    snapshot = InputSnapshot((expectation(4000, 4600), expectation(4720, 6400, 2)), (media,))
    result = scheduled(snapshot)
    assert [c.span for c in result] == [Span(at(4000), at(4600)), Span(at(4720), at(6400))]
    assert result[0].start_edge_kind == EdgeKind.FREEZE and result[0].start_cue_support
    assert result[0].end_edge_kind == EdgeKind.SCHEDULE
    assert result[1].start_edge_kind == result[1].end_edge_kind == EdgeKind.SCHEDULE
    assert not result[1].start_cue_support
    assert all(not c.overlap for c in result)
    assert evaluate(snapshot) == evaluate(replace(
        snapshot, expectations=snapshot.expectations[::-1]))


def test_schedule_start_fallback_does_not_allow_reusing_observed_end() -> None:
    media = replace(asset(0, 10000, freezes=((4000, 4600),)), end_cues=(at(4000),))
    snapshot = InputSnapshot((expectation(2000, 4000), expectation(3000, 5000, 2)), (media,))
    result = scheduled(snapshot)
    assert [c.span for c in result] == [Span(at(2000), at(4000)), Span(at(3000), at(5000))]
    assert result[0].start_edge_kind == EdgeKind.SCHEDULE
    assert result[0].end_edge_kind == EdgeKind.FREEZE and result[0].end_cue_support
    assert result[1].start_edge_kind == result[1].end_edge_kind == EdgeKind.SCHEDULE
    assert not result[1].end_cue_support
    assert all(c.overlap and c.strength == Strength.WEAK for c in result)
    assert evaluate(snapshot) == evaluate(replace(
        snapshot, expectations=snapshot.expectations[::-1]))


def test_shared_changeover_start_cues_still_count_for_the_next_talk() -> None:
    media = replace(asset(0, 4000, freezes=((1700, 1800), (1900, 1960))),
                    start_cues=tuple(at(1900) for _ in range(5)))
    result = scheduled(InputSnapshot((expectation(0, 1700), expectation(1800, 3600, 2)),
                                     (media,)))
    assert result[0].span.end == at(1700) and result[1].span.start == at(1800)
    assert result[1].start_edge_kind == EdgeKind.FREEZE and result[1].start_cue_support


def test_each_predecessor_can_fall_back_without_losing_better_joint_path() -> None:
    result = scheduled(InputSnapshot((expectation(0, 500), expectation(400, 650, 2)),
                                    (asset(0, 2000, freezes=((300, 400), (500, 700))),)))
    assert [c.span for c in result] == [Span(at(0), at(500)), Span(at(400), at(650))]
    assert result[1].start_edge_kind == result[1].end_edge_kind == EdgeKind.SCHEDULE
    assert all(c.overlap and c.strength == Strength.WEAK for c in result)


@pytest.mark.parametrize("drift,kind", [(-1200, EdgeKind.FREEZE), (1200, EdgeKind.FREEZE),
                                       (-1201, EdgeKind.SCHEDULE), (1201, EdgeKind.SCHEDULE)])
def test_hard_window_and_unclipped_fallback(drift: int, kind: EdgeKind) -> None:
    result = scheduled(InputSnapshot((expectation(4000 + drift, 10000),),
                                    (asset(0, 10000, freezes=((3900, 4000),)),)))
    assert result[0].start_edge_kind == kind
    assert result[0].span.start == at(4000 if kind == EdgeKind.FREEZE else 4000 + drift)
    outside = scheduled(InputSnapshot((expectation(-1201, 4000),), (asset(0, 8000),)))
    assert not outside  # no coverage in the start window


def test_each_supporting_cue_adds_one_point_and_ties_choose_earlier_edge() -> None:
    media = asset(0, 8000, freezes=((1900, 2000), (2040, 2140)))
    plan = (expectation(2070, 8000),)
    assert scheduled(InputSnapshot(plan, (media,)))[0].span.start == at(2000)
    # Only the later edge has these cues in its inclusive +180 s window.
    supported = replace(media, start_cues=(at(2300), at(2320)))
    result = scheduled(InputSnapshot(plan, (supported,)))
    assert result[0].span.start == at(2140) and result[0].start_cue_support
    # 140 s further costs 4 2/3 points: five cues, not one boolean bonus, win.
    plan = (expectation(2000, 8000),)
    supported = replace(media, start_cues=tuple(at(2310 + i) for i in range(5)))
    assert scheduled(InputSnapshot(plan, (supported,)))[0].span.start == at(2140)


def test_strength_formula_silence_union_cap_and_gap_coverage_rules() -> None:
    c = Changeover(at(0), at(1200), EdgeKind.FREEZE)
    assert weight(c, (Span(at(0), at(600)),)).strength == 20
    assert weight(replace(c, kind=EdgeKind.GAP), (Span(at(0), at(1200)),)).strength == 10
    assert weight(Changeover(at(0), at(0), EdgeKind.COVERAGE), ()).strength == 30
    for silence, supported in ((29, False), (30, True)):
        media = asset(0, 8000, freezes=((3000, 3100),),
                      silences=((3000, 3000 + silence), (3000, 3000 + silence)))
        result = scheduled(InputSnapshot((expectation(0, 3000),), (media,)))
        assert result[0].end_silence_support is supported
    assert weight(c, ()).silent_share == Fraction(0)


def test_unscheduled_activity_clocks_lifecycle_and_input_order() -> None:
    plan = expectation(1440, 3000)
    media = asset(0, 3000, freezes=((180, 1440),))
    snapshot = InputSnapshot((plan, expectation(None, None, 2)),
                             (media, asset(100000, 110000, n=30), AssetInput(eid(80))))
    result = evaluate(snapshot)
    assert result.candidates[0].span == Span(at(0), at(180))
    assert result.candidates[0].expectation is None
    assert result.skips.clock_implausible == result.skips.no_planned_time == 1
    assert result.skips.no_timing_evidence == 1
    assert evaluate(InputSnapshot(tuple(reversed(snapshot.expectations)),
                                  tuple(reversed(snapshot.assets)))) == result
    withdrawn = replace(plan, lifecycle_state=ProgramExpectationLifecycle.WITHDRAWN)
    assert all(c.expectation is None for c in evaluate(InputSnapshot((withdrawn,), (media,)))
               .candidates)


def test_exact_sixty_second_v2_and_v1_replay() -> None:
    snapshot = InputSnapshot((expectation(0, 60),), (asset(0, 60),))
    assert scheduled(snapshot)[0].span == Span(at(0), at(60))
    assert evaluate_v1(snapshot).candidates == ()
    assert asdict(POLICY_V1)["changeover_seconds"] == 30
    assert asdict(POLICY_V2)["changeover_seconds"] == 60


def test_owner_thirty_second_fallback_is_skipped_and_counted_as_v1() -> None:
    short = expectation(3000, 3030)
    next_talk = expectation(5000, 8000, 2)
    snapshot = InputSnapshot((short, next_talk), (asset(0, 10000),))
    result = evaluate(snapshot)
    planned = tuple(c for c in result.candidates if c.expectation is not None)
    assert result.skips.no_coverage == evaluate_v1(snapshot).skips.no_coverage == 1
    assert len(planned) == 1 and planned[0].expectation is not None
    assert planned[0].expectation.id == next_talk.id
    assert planned[0].span == Span(at(5000), at(8000))
    assert result == evaluate(snapshot)


def test_short_plan_can_still_yield_a_valid_evidence_interval() -> None:
    result = evaluate(InputSnapshot((expectation(0, 30),), (asset(0, 180),)))
    planned = tuple(c for c in result.candidates if c.expectation is not None)
    assert len(planned) == 1 and planned[0].span == Span(at(0), at(180))
    assert result.skips.no_coverage == 0


def test_new_run_and_suggestion_lineage_and_exact_constants() -> None:
    h = Harness()
    run = h.run()
    assert run.policy == POLICY_V3
    assert h.suggestion().policy_version == "3"
    assert replace(run, policy=POLICY_V1, blocks=()).policy == POLICY_V1
    with pytest.raises(ValueError, match="unsupported"):
        replace(run, policy=replace(POLICY_V2, plan_distance_seconds=31))
    assert isinstance(run, SuggestionRun) and run.created_at == NOW
