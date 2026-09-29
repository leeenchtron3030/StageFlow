"""Synthetic schedules only; v1/v2 retain their own behavioral suites."""
from dataclasses import asdict, replace
from datetime import timedelta
from fractions import Fraction
from time import perf_counter

import pytest

from app.contexts.production.session_suggestions.contracts import (
    CandidateV3,
    EdgeKind,
    InputSnapshot,
    ScheduleOffsetEntry,
    ScheduleOffsetSetting,
    ScheduleOffsetSource,
    Span,
)
from app.contexts.production.session_suggestions.policy import Changeover
from app.contexts.production.session_suggestions.policy_v2 import evaluate as evaluate_v2
from app.contexts.production.session_suggestions.policy_v2 import weight
from app.contexts.production.session_suggestions.policy_v3 import (
    estimate_offset,
    evaluate,
    schedule_blocks,
    support_score,
)
from tests.test_session_suggestion_policy import NOW, asset, at, eid, expectation


def override(*entries: tuple[int, int]) -> ScheduleOffsetSetting:
    return ScheduleOffsetSetting(eid(900), eid(901), 1, eid(902), "a" * 64, eid(903), NOW,
                                 tuple(ScheduleOffsetEntry(at(t), s) for t, s in entries))


@pytest.mark.parametrize("offset", [-1500, 1500])
def test_whole_day_25_minutes_aligns_every_talk_and_reports_printed_offsets(offset: int) -> None:
    snapshot = InputSnapshot(
        (expectation(0, 3000), expectation(3300, 6600, 2), expectation(6900, 10200, 3)),
        (asset(offset, 10200 + offset, freezes=((3000, 3300), (6600, 6900)),
               silences=((3000, 3300), (6600, 6900))),))
    result = evaluate(snapshot)
    planned = tuple(c for c in result.candidates if c.expectation is not None)
    assert [c.span for c in planned] == [Span(at(a + offset), at(b + offset))
                                        for a, b in ((0, 3000), (3300, 6600), (6900, 10200))]
    assert len(result.blocks) == 1 and result.blocks[0].talk_count == 3
    assert result.blocks[0].schedule_offset_seconds == offset
    assert result.blocks[0].estimate_score_margin >= 18
    for c in planned:
        assert isinstance(c, CandidateV3)
        assert c.schedule_offset_seconds == offset
        assert c.schedule_offset_source == ScheduleOffsetSource.ESTIMATED
        assert c.start_plan_offset_seconds == c.end_plan_offset_seconds == offset
        assert not c.overlap
    assert evaluate(snapshot) == evaluate(replace(
        snapshot, expectations=snapshot.expectations[::-1]))


def test_lunch_blocks_have_independent_offsets_and_override_uses_planned_time() -> None:
    snapshot = InputSnapshot((expectation(0, 3000), expectation(6000, 9000, 2)),
                             (asset(300, 3300), asset(7200, 10200, n=20)))
    result = evaluate(snapshot)
    assert [b.schedule_offset_seconds for b in result.blocks] == [300, 1200]
    assert [c.span for c in result.candidates] == [Span(at(300), at(3300)),
                                                 Span(at(7200), at(10200))]
    result = evaluate(snapshot, override((6000, 0), (6500, -100)))
    assert [b.schedule_offset_seconds for b in result.blocks] == [300, 0]
    assert [b.schedule_offset_source for b in result.blocks] == ["estimated", "producer"]
    assert [b.override_setting_version for b in result.blocks] == [None, 1]
    assert result.blocks[1].estimate_score_margin > 6  # estimate retained even with override
    assert evaluate(snapshot, override()) == evaluate(snapshot)


def test_latest_applicable_override_entry_wins() -> None:
    snapshot = InputSnapshot((expectation(6000, 9000),), ())
    result = evaluate(snapshot, override((0, 100), (3000, 200), (7000, 300)))
    assert len(result.blocks) == 1
    assert result.blocks[0].schedule_offset_seconds == 200
    assert result.blocks[0].schedule_offset_source == "producer"


@pytest.mark.parametrize("gap,blocks", [(-300, 1), (1199, 1), (1200, 2), (1201, 2)])
def test_block_break_is_inclusive_and_uses_previous_end(gap: int, blocks: int) -> None:
    plans = (expectation(0, 3000), expectation(3000 + gap, 9000, 2))
    result = evaluate(InputSnapshot(plans, ()))
    assert len(result.blocks) == blocks
    assert sum(b.talk_count for b in result.blocks) == 2
    assert all(b.schedule_offset_source == "none" for b in result.blocks)


def test_no_plan_no_evidence_weak_gain_and_beyond_search_limit() -> None:
    assert evaluate(InputSnapshot((), ())).blocks == ()
    no_media = evaluate(InputSnapshot((expectation(0, 3000),), ()))
    assert no_media.blocks[0].schedule_offset_seconds == 0
    assert no_media.blocks[0].schedule_offset_source == "none"
    # A lone 60-second freeze supplies less than six points of improvement.
    snapshot = InputSnapshot((expectation(5000, 8000),),
                             (asset(0, 20000, freezes=((8200, 8260),)),))
    result = evaluate(snapshot)
    assert 0 < result.blocks[0].estimate_score_margin < 6
    assert result.blocks[0].schedule_offset_source == "none"
    late = InputSnapshot((expectation(0, 3000),), (asset(7500, 10500),))
    result = evaluate(late)
    assert result.blocks[0].schedule_offset_seconds == 0
    assert result.blocks[0].schedule_offset_source == "none"
    assert result.skips == evaluate_v2(late).skips
    assert [c.span for c in result.candidates] == [c.span for c in evaluate_v2(late).candidates]


def test_exact_score_uses_correct_edges_and_microseconds() -> None:
    planned = (expectation(0, 3000),)
    changes = (weight(Changeover(at(-300), at(0.000001), EdgeKind.FREEZE), ()),
               weight(Changeover(at(3000), at(3300), EdgeKind.GAP), ()))
    expected = changes[0].strength * Fraction(179999999, 180000000) + changes[1].strength
    assert support_score(planned, changes, 0) == expected
    assert support_score(planned, changes, 600) == -1


@pytest.mark.parametrize("shorter_microseconds,source", [(0, "estimated"), (1, "none")])
def test_six_point_gate_is_inclusive_without_rounding(
    shorter_microseconds: int, source: str,
) -> None:
    # A fully silent 140-second freeze weighs 7; the 600-second offset costs 1.
    start = at(460) + timedelta(microseconds=shorter_microseconds)
    changes = (weight(Changeover(start, at(600), EdgeKind.FREEZE), (Span(start, at(600)),)),)
    plans = (expectation(0, 10000),)
    offset, margin = estimate_offset(plans, changes)
    assert offset == 600
    assert margin == Fraction(6) - Fraction(shorter_microseconds, 20_000_000)
    blocks, _ = schedule_blocks(plans, changes, None)
    assert blocks[0].schedule_offset_source == source


@pytest.mark.parametrize("offset", [-3600, -610, 610, 3600])
def test_grid_refinement_and_search_bounds(offset: int) -> None:
    planned = (expectation(0, 10000),)
    changes = tuple(weight(Changeover(at(t + offset), at(t + offset), EdgeKind.COVERAGE), ())
                    for t in (0, 10000))
    estimated, margin = estimate_offset(planned, changes)
    assert estimated == offset and margin > 6


def test_ties_choose_smaller_absolute_then_earlier_offset() -> None:
    planned = (expectation(0, 10000),)
    changes = tuple(weight(Changeover(at(t + d), at(t + d), EdgeKind.COVERAGE), ())
                    for t in (0, 10000) for d in (-600, 600))
    assert estimate_offset(planned, changes)[0] == -600
    assert estimate_offset(planned, tuple(reversed(changes))) == estimate_offset(planned, changes)
    zero = tuple(weight(Changeover(at(t), at(t), EdgeKind.COVERAGE), ()) for t in (0, 10000))
    assert estimate_offset(planned, zero)[0] == 0


def test_zero_override_reproduces_every_v2_component_and_unscheduled_stays_none() -> None:
    snapshot = InputSnapshot((expectation(400, 1800),), (asset(0, 7000),))
    old = evaluate_v2(snapshot)
    new = evaluate(snapshot, override((-100, 0)))
    assert new.skips == old.skips
    assert len(new.candidates) == len(old.candidates)
    for a, b in zip(old.candidates, new.candidates, strict=True):
        assert isinstance(b, CandidateV3)
        doc = asdict(b)
        del doc["schedule_offset_seconds"], doc["schedule_offset_source"]
        assert asdict(a) == doc
        assert b.schedule_offset_seconds == 0
        assert b.schedule_offset_source == ("none" if b.expectation is None else "producer")


def test_true_override_reproduces_zero_drift_alignment_and_strength() -> None:
    media = asset(1500, 11700, freezes=((3000, 3300), (6600, 6900)))
    planned = (expectation(0, 3000), expectation(3300, 6600, 2), expectation(6900, 10200, 3))
    shifted = tuple(replace(p, planned_start=p.planned_start + timedelta(seconds=1500),
                            planned_end=p.planned_end + timedelta(seconds=1500))
                    for p in planned if p.planned_start is not None and p.planned_end is not None)
    truth = evaluate_v2(InputSnapshot(shifted, (media,)))
    actual = evaluate(InputSnapshot(planned, (media,)), override((0, 1500)))
    assert [(c.span, c.strength) for c in actual.candidates] == [
        (c.span, c.strength) for c in truth.candidates]


def test_full_day_cost_is_seconds() -> None:
    planned = tuple(expectation(i * 1800, i * 1800 + 1500, i + 1) for i in range(12))
    freezes = tuple((i * 450 + 200, i * 450 + 300) for i in range(48))
    started = perf_counter()
    result = evaluate(InputSnapshot(planned, (asset(0, 22000, freezes=freezes),)))
    assert result.blocks[0].talk_count == 12
    assert perf_counter() - started < 10
