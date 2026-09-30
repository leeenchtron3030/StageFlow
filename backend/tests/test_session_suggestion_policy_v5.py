"""Synthetic boundary evidence; legacy policies and persisted fields remain intact."""
from dataclasses import FrozenInstanceError, asdict, fields, replace
from datetime import datetime
from fractions import Fraction
from time import perf_counter
from zoneinfo import ZoneInfo

import pytest

from app.contexts.production.session_suggestions.contracts import (
    POLICY_V3,
    EdgeKind,
    InputSnapshot,
    SkipCounts,
    SkipCountsV5,
    Span,
    Strength,
)
from app.contexts.production.session_suggestions.cue_catalog import BOUNDARY_CUE_CATALOG
from app.contexts.production.session_suggestions.cue_composition import CompositionRequest, compose
from app.contexts.production.session_suggestions.policy import Changeover, Edge
from app.contexts.production.session_suggestions.policy import evaluate as v1
from app.contexts.production.session_suggestions.policy_v2 import evaluate as v2
from app.contexts.production.session_suggestions.policy_v3 import evaluate as v3
from app.contexts.production.session_suggestions.policy_v5 import (
    POLICY_V5,
    cue_edges,
    cue_support,
    eligible_edges,
    evaluate,
)
from tests.test_session_suggestion_policy import asset, at, expectation
from tests.test_session_suggestion_policy_v3 import override


def test_proximity_hand_computed_and_microsecond_exact() -> None:
    assert cue_support(at(0), tuple(at(t) for t in (-31, -30, -15, 0, 10, 30, 31))) == (
        5 + 10 + Fraction(20, 3))
    assert cue_support(at(0), (at(0.000001),)) == Fraction(29_999_999, 3_000_000)
    assert cue_support(at(0), ()) == 0


def test_cue_distance_and_clustering_use_instants_across_dst_fold() -> None:
    zone = ZoneInfo("America/Los_Angeles")
    first = datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=0)
    second = datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=1)
    assert cue_support(first, (second,)) == 0
    assert cue_edges((second, first), (), (), True) == ()


@pytest.mark.parametrize("start,expected", [(True, 100), (False, 160)])
def test_cluster_uses_earliest_start_latest_end_and_inclusive_sixty_seconds(
    start: bool, expected: int,
) -> None:
    assert cue_edges((at(160), at(100)), (), (), start) == (at(expected),)
    assert cue_edges((at(100), at(160.000001)), (), (), start) == ()
    assert cue_edges((at(100),), (), (), start) == ()
    assert cue_edges((at(100),), (at(100),), (), start) == (at(100),)
    # No transitive chaining beyond the first hit's 60-second cluster window.
    assert cue_edges((at(0), at(50), at(100)), (), (), start) == (at(0 if start else 50),)


@pytest.mark.parametrize("start", [False, True])
@pytest.mark.parametrize("distance,present", [(30, False), (30.000001, True)])
def test_cue_edge_gap_is_role_specific_and_inclusive(
    start: bool, distance: float, present: bool,
) -> None:
    change = Changeover(at(100), at(200), EdgeKind.FREEZE)
    t = at((200 if start else 100) + distance)
    assert bool(cue_edges((t,), (t,), (change,), start)) is present
    wrong_role = at(100 if start else 200)
    assert cue_edges((wrong_role,), (wrong_role,), (change,), start) == (wrong_role,)
    coverage = Changeover(t, t, EdgeKind.COVERAGE)
    assert cue_edges((t,), (t,), (coverage,), start) == (t,)


def test_changeover_cues_support_both_roles_but_never_create_edges() -> None:
    snapshot = InputSnapshot((expectation(0, 1800), expectation(1860, 3600, 2)),
                             (asset(freezes=((1800, 1860),)),))
    # Two hits, one near each role: role support is measured against its own edge.
    media = replace(snapshot.assets[0], changeover_cues=(at(1810), at(1850)))
    result = evaluate(replace(snapshot, assets=(media,)), override((0, 0)))
    a, b = result.candidates
    assert a.end_cue_support and b.start_cue_support
    assert a.end_edge_kind == b.start_edge_kind == EdgeKind.FREEZE
    assert a.strength == b.strength == Strength.STRONG
    empty = replace(media, intervals=(), changeover_cues=(at(1800), at(1810)))
    assert all(EdgeKind.CUE not in (c.start_edge_kind, c.end_edge_kind)
               for c in evaluate(replace(snapshot, assets=(empty,))).candidates)


def test_proximity_changes_selection_without_changing_offset_estimation() -> None:
    base = asset(0, 6000, freezes=((1700, 1800), (1830, 2070)), silences=((1830, 2070),))
    snap = InputSnapshot((expectation(1800, 6000),), (base,))
    before = evaluate(snap, override((0, 0)))
    assert next(c for c in before.candidates if c.expectation is not None).span.start == at(2070)
    media = replace(base, start_cues=(at(1800),))
    result = evaluate(replace(snap, assets=(media,)), override((0, 0)))
    candidate = next(c for c in result.candidates if c.expectation is not None)
    assert candidate.span.start == at(1800)
    assert candidate.start_cue_support
    assert result.blocks == v3(snap, override((0, 0))).blocks


def test_segment_and_studio_take_matches_never_enter_session_roles() -> None:
    composition = compose(CompositionRequest(1, ("panels", "studio.takes", "studio.wraps")))
    phrases = {p.text for p in composition.segments}
    assert {"action", "cut", "take 1"} <= phrases
    assert not phrases.intersection(composition.start + composition.end)
    snap = InputSnapshot((expectation(0, 3600),), (asset(),))
    # Simulate matching only segment phrases using the accepted role projection.
    hits = tuple((phrase, at(1800)) for phrase in sorted(phrases))
    media = replace(snap.assets[0],
                    start_cues=tuple(t for phrase, t in hits if phrase in composition.start),
                    end_cues=tuple(t for phrase, t in hits if phrase in composition.end))
    assert evaluate(replace(snap, assets=(media,))) == evaluate(snap)
    studio = next(g for g in BOUNDARY_CUE_CATALOG.groups if g.key == "studio.takes")
    assert all(p.role == "segment" for p in studio.phrases)


def test_cue_only_edges_are_medium_and_role_separated() -> None:
    media = replace(asset(0, 6000), start_cues=(at(300),), specific_start_cues=(at(300),),
                    end_cues=(at(3300), at(3320)))
    snap = InputSnapshot((expectation(300, 3320),), (media,))
    result = evaluate(snap, override((0, 0)))
    c = next(c for c in result.candidates if c.expectation is not None)
    assert c.span == Span(at(300), at(3320))
    assert c.start_edge_kind == c.end_edge_kind == EdgeKind.CUE
    assert c.start_cue_support and c.end_cue_support and c.strength == Strength.MEDIUM
    remaining = [c for c in result.candidates if c.expectation is None]
    assert remaining[0].end_edge_kind == EdgeKind.SCHEDULE
    assert remaining[1].start_edge_kind == EdgeKind.SCHEDULE
    with pytest.raises(ValueError, match="strength"):
        replace(c, strength=Strength.STRONG)


def test_one_cue_edge_limits_strength_even_with_silent_changeover() -> None:
    media = replace(asset(0, 6000, freezes=((3300, 3600),), silences=((3300, 3600),)),
                    start_cues=(at(300),), specific_start_cues=(at(300),))
    result = evaluate(InputSnapshot((expectation(300, 3300),), (media,)), override((0, 0)))
    c = next(c for c in result.candidates if c.expectation is not None)
    assert c.start_edge_kind == EdgeKind.CUE and c.end_edge_kind == EdgeKind.FREEZE
    assert c.end_silence_support and c.strength == Strength.MEDIUM


@pytest.mark.parametrize("delta,kind", [(1200, EdgeKind.CUE), (1200.000001, EdgeKind.SCHEDULE)])
def test_cue_edges_obey_offset_shifted_window(delta: float, kind: EdgeKind) -> None:
    media = replace(asset(-5000, 10000), start_cues=(at(600 + delta),),
                    specific_start_cues=(at(600 + delta),))
    result = evaluate(InputSnapshot((expectation(0, 6000),), (media,)), override((0, 600)))
    c = next(c for c in result.candidates if c.expectation is not None)
    assert c.start_edge_kind == kind
    assert c.span.start == (at(600 + delta) if kind == EdgeKind.CUE else at(600))


def test_coverage_fallback_is_per_shifted_role_window_before_order_filter() -> None:
    edges = (Edge(at(0), EdgeKind.COVERAGE, False, False),
             Edge(at(1200), EdgeKind.CUE, False, True))
    assert eligible_edges(edges, at(0), frozenset((at(1200),))) == (1,)
    assert eligible_edges(edges, at(-0.000001), frozenset((at(1200),))) == (0,)
    assert eligible_edges(edges, at(0), frozenset()) == (0,)
    snap = InputSnapshot((expectation(0, 3600),), (asset(-600, 3600, freezes=((480, 600),)),))
    result = evaluate(snap, override((0, 0)))
    c = next(c for c in result.candidates if c.expectation is not None)
    assert c.span == Span(at(0), at(3600))
    assert c.start_edge_kind == EdgeKind.FREEZE and c.end_edge_kind == EdgeKind.COVERAGE


@pytest.mark.parametrize("side", ["before", "after"])
@pytest.mark.parametrize("extra,skipped", [(0, 0), (0.000001, 1)])
@pytest.mark.parametrize("offset", [0, 600])
def test_outside_program_exact_margin_and_applicable_offset(
    side: str, extra: float, skipped: int, offset: int,
) -> None:
    a, b = ((-1920 - extra, -1800 - extra) if side == "before"
            else (4800 + extra, 4920 + extra))
    snap = InputSnapshot((expectation(0, 3000),),
                         (asset(offset, 3000 + offset), asset(a + offset, b + offset, n=20)))
    result = evaluate(snap, override((-100, offset)))
    assert result.skips.outside_program == skipped
    assert sum(c.expectation is None for c in result.candidates) == 1 - skipped
    assert next(c for c in result.candidates if c.expectation is not None).span == (
        Span(at(offset), at(3000 + offset)))


def test_no_plan_has_no_program_limit_and_skips_stay_backward_compatible() -> None:
    snap = InputSnapshot((), (asset(),))
    result = evaluate(snap)
    assert len(result.candidates) == 1 and result.skips.outside_program == 0
    legacy_names = ["no_timing_evidence", "no_segmentation", "clock_implausible",
                    "no_coverage", "no_planned_time", "already_realized"]
    assert [f.name for f in fields(SkipCounts)] == legacy_names
    for policy in (v1, v2, v3):
        assert policy(snap).skips.outside_program == 0
        assert list(asdict(policy(snap).skips)) == legacy_names
    with pytest.raises(ValueError, match="skip count"):
        SkipCountsV5(outside_program=-1)


@pytest.mark.parametrize("extra,skipped", [(0, 0), (0.000001, 2)])
def test_program_span_uses_each_blocks_offset(extra: float, skipped: int) -> None:
    plans = (expectation(0, 3000), expectation(6000, 9000, 2))
    media = (asset(600, 3600), asset(5700, 8700, n=20),
             asset(-1320 - extra, -1200 - extra, n=30),
             asset(10500 + extra, 10620 + extra, n=40))
    result = evaluate(InputSnapshot(plans, media), override((0, 600), (6000, -300)))
    assert [b.schedule_offset_seconds for b in result.blocks] == [600, -300]
    assert result.skips.outside_program == skipped
    assert sum(c.expectation is None for c in result.candidates) == 2 - skipped


def test_additive_cues_detach_inputs_validate_awareness_and_specific_membership() -> None:
    times = [at(100)]
    media = replace(asset(), changeover_cues=times, specific_start_cues=(), start_cues=times)
    times.clear()
    assert media.changeover_cues == media.start_cues == (at(100),)
    with pytest.raises(FrozenInstanceError):
        media.changeover_cues = ()  # type: ignore[misc]
    with pytest.raises(ValueError):
        replace(media, changeover_cues=(at(0).replace(tzinfo=None),))
    with pytest.raises(ValueError, match="specific"):
        replace(media, specific_start_cues=(at(200),))


def test_constants_keep_every_other_v3_setting() -> None:
    old, new = asdict(POLICY_V3), asdict(POLICY_V5)
    assert new.pop("version") == "5"
    assert new.pop("coverage_strength") == 5
    assert [new.pop(k) for k in ("cue_radius", "cue_weight", "cue_edge_gap",
                                "cue_edge_strength", "outside_program_margin")] == (
        [30, 10, 30, 3, 1800])
    del old["version"], old["coverage_strength"]
    assert new == old


def test_no_cues_equals_v3_except_coverage_and_program_span() -> None:
    snap = InputSnapshot((expectation(0, 3000), expectation(3300, 6600, 2)),
                         (asset(0, 6600, freezes=((3000, 3300),)),))
    old, new = v3(snap), evaluate(snap)
    assert new.candidates == old.candidates and new.blocks == old.blocks
    skips = asdict(new.skips)
    assert skips.pop("outside_program") == 0 and skips == asdict(old.skips)
    early = replace(snap, assets=(asset(-600, 6600, freezes=((480, 600), (3600, 3900))),))
    old, new = v3(early, override((0, 0))), evaluate(early, override((0, 0)))
    assert old.candidates[0].span.start == at(-600)
    assert next(c for c in new.candidates if c.expectation is not None).span.start == at(0)
    assert new.blocks == old.blocks
    tail = replace(snap, assets=(*snap.assets, asset(8500, 8800, n=20)))
    old, new = v3(tail, override((0, 0))), evaluate(tail, override((0, 0)))
    assert new.skips.outside_program == 1
    assert new.candidates == tuple(c for c in old.candidates if c.expectation is not None)


def test_full_day_cost_and_permutation_determinism() -> None:
    plans = tuple(expectation(i * 1800, i * 1800 + 1500, i + 1) for i in range(30))
    freezes = tuple((i * 675 + 200, i * 675 + 300) for i in range(80))
    # Move every fifth cue clear of the freezes and their 30-second edge gaps.
    cues = tuple(at(i * 270 + 250 + (150 if i % 5 == 0 else 0)) for i in range(200))
    media = replace(asset(0, 55000, freezes=freezes), start_cues=cues[:70],
                    end_cues=cues[70:140], changeover_cues=cues[140:],
                    specific_start_cues=cues[:70], specific_end_cues=cues[70:140])
    snap = InputSnapshot(plans, (media,))
    started = perf_counter()
    result = evaluate(snap)
    assert len(result.blocks) == 1 and result.blocks[0].talk_count == 30
    assert perf_counter() - started < 10
    cue_edge_count = sum(kind == EdgeKind.CUE for c in result.candidates
                         for kind in (c.start_edge_kind, c.end_edge_kind))
    assert cue_edge_count > 0, f"selected cue-edge count: {cue_edge_count}"
    assert result == evaluate(replace(snap, expectations=plans[::-1], assets=(replace(
        media, start_cues=media.start_cues[::-1], end_cues=media.end_cues[::-1],
        changeover_cues=media.changeover_cues[::-1], intervals=media.intervals[::-1]),)))
