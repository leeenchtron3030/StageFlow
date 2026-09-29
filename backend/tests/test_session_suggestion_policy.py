"""Synthetic recorder timelines prove the versioned Phase 2 policy."""
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta

import pytest

from app.contexts.editorial.derivation_contracts import TimingQualification
from app.contexts.events import ProgramExpectation, ProgramExpectationLifecycle
from app.contexts.production.media_segmentation_evidence.contracts import SegmentationInterval
from app.contexts.production.session_suggestions.contracts import (
    POLICY_V1,
    AssetInput,
    EdgeKind,
    InputSnapshot,
    Reference,
    SkipCounts,
    Span,
    Strength,
)
from app.contexts.production.session_suggestions.policy import evaluate
from app.shared.ids import EntityId

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def eid(n: int) -> EntityId:
    return EntityId(f"10400000-0000-0000-0000-{n:012d}")


def at(seconds: float) -> datetime:
    return NOW + timedelta(seconds=seconds)


def expectation(start: float | None, end: float | None, n: int = 1) -> ProgramExpectation:
    return ProgramExpectation(eid(n), eid(900), f"talk-{n}", eid(901), f"Talk {n}", (),
                              None if start is None else at(start),
                              None if end is None else at(end), {}, 1, NOW)


def asset(start: float = 0, end: float = 3600, *, n: int = 10,
          freezes: tuple[tuple[int, int], ...] = (),
          silences: tuple[tuple[int, int], ...] = ()) -> AssetInput:
    intervals = tuple(SegmentationInterval("freeze", a * 1_000_000, b * 1_000_000)
                      for a, b in freezes) + tuple(
                          SegmentationInterval("silence", a * 1_000_000, b * 1_000_000)
                          for a, b in silences)
    return AssetInput(eid(n), Reference(eid(n + 1), 1), Span(at(start), at(end)),
                      TimingQualification.UNQUALIFIED, (eid(n + 2),), intervals)


def test_clean_changeover_freeze_breaks_audio_and_strength() -> None:
    expectations = (expectation(60, 1700), expectation(1850, 3600, 2))
    media = asset(freezes=((1700, 1730), (1745, 1800), (800, 807)))
    result = evaluate(InputSnapshot(expectations, (media,)))
    assert [(x.span.start, x.span.end) for x in result.candidates] == [
        (at(0), at(1700)), (at(1800), at(3600)),
    ]
    assert all(x.strength == Strength.MEDIUM for x in result.candidates)
    assert all(x.timing_qualifications == (TimingQualification.UNQUALIFIED,)
               for x in result.candidates)
    supported = replace(media, intervals=media.intervals + (
        SegmentationInterval("silence", 1710_000_000, 1720_000_000),))
    assert all(x.strength == Strength.STRONG for x in evaluate(
        InputSnapshot(expectations, (supported,))).candidates)


@pytest.mark.parametrize("duration,merge_gap,expected", [(30, 15, True), (29, 15, False),
                                                        (30, 16, False)])
def test_exact_freeze_thresholds(duration: int, merge_gap: int, expected: bool) -> None:
    first = 10
    result = evaluate(InputSnapshot((expectation(0, 1800),), (asset(
        freezes=((1800, 1800 + first),
                 (1800 + first + merge_gap, 1800 + duration)),
    ),))) if duration > first + merge_gap else None
    assert result is not None
    assert (result.candidates[0].end_edge_kind == EdgeKind.FREEZE) == expected


def test_recording_gap_and_no_transcript() -> None:
    result = evaluate(InputSnapshot((expectation(0, 1800), expectation(1900, 3600, 2)),
                                    (asset(end=1800), asset(1900, 3600, n=20))))
    assert result.candidates[0].span.end == at(1800)
    assert result.candidates[1].span.start == at(1900)
    assert result.candidates[0].end_edge_kind == EdgeKind.GAP
    assert not result.candidates[0].transcript_references


@pytest.mark.parametrize("drift", [-1200, 1200])
def test_twenty_minute_edge_window_inclusive(drift: int) -> None:
    media = asset(0, 10000, freezes=((4000, 4100),))
    result = evaluate(InputSnapshot((expectation(4100 + drift, 10000),), (media,)))
    scheduled = next(x for x in result.candidates if x.expectation is not None)
    assert scheduled.span.start == at(4100)
    assert scheduled.start_plan_offset_seconds == -drift


def test_schedule_fallback_no_coverage_missing_plan_and_wrong_clock() -> None:
    result = evaluate(InputSnapshot((expectation(4000, 6000),), (asset(0, 10000),)))
    scheduled = next(x for x in result.candidates if x.expectation is not None)
    assert scheduled.span == Span(at(4000), at(6000))
    assert scheduled.strength == Strength.WEAK
    assert scheduled.start_edge_kind == scheduled.end_edge_kind == EdgeKind.SCHEDULE
    result = evaluate(InputSnapshot((expectation(4000, 6000),), (asset(100000, 110000),)))
    assert not result.candidates and result.skips.clock_implausible == 1
    assert result.skips.no_coverage == 1
    result = evaluate(InputSnapshot((expectation(None, None),), (asset(0, 180),)))
    assert result.skips.no_planned_time == 1
    assert result.candidates[0].expectation is None
    result = evaluate(InputSnapshot((expectation(0, 180),), (asset(0, 180), AssetInput(eid(44)))))
    assert result.skips.no_timing_evidence == 1


def test_withdrawn_unscheduled_and_determinism() -> None:
    media = asset(0, 1000, freezes=((180, 240),))
    planned = expectation(240, 1000)
    snapshot = InputSnapshot((planned,), (media,))
    result = evaluate(snapshot)
    assert result == evaluate(snapshot)
    assert result.candidates[0].span == Span(at(0), at(180))
    assert result.candidates[0].expectation is None
    assert result.candidates[0].strength == Strength.WEAK
    withdrawn = replace(planned, lifecycle_state=ProgramExpectationLifecycle.WITHDRAWN)
    result = evaluate(InputSnapshot((withdrawn,), (media,)))
    assert all(x.expectation is None for x in result.candidates)


def test_overlap_shared_changeover_and_unresolved_overlap() -> None:
    # The second planned start chooses coverage start, overlapping the first;
    # the shared interior changeover must replace that selected start.
    planned = (expectation(0, 4500), expectation(500, 8000, 2))
    result = evaluate(InputSnapshot(planned, (asset(0, 8000, freezes=((4000, 4100),)),)))
    scheduled = [x for x in result.candidates if x.expectation is not None]
    assert scheduled[0].span.end == at(4000) and scheduled[1].span.start == at(4100)
    result = evaluate(InputSnapshot((expectation(2000, 6000), expectation(4000, 8000, 2)),
                                    (asset(0, 10000),)))
    scheduled = [x for x in result.candidates if x.expectation is not None]
    assert all(x.overlap and x.strength == Strength.WEAK for x in scheduled)


def test_cue_tie_break_and_asymmetric_windows() -> None:
    media = asset(0, 8000, freezes=((1900, 2000), (2030, 2060)))
    # Cue at +180 from the second edge, outside +180 of the nearer first edge.
    media = replace(media, start_cues=(at(2240),))
    result = evaluate(InputSnapshot((expectation(2000, 8000),), (media,)))
    scheduled = next(x for x in result.candidates if x.expectation is not None)
    assert scheduled.span.start == at(2060) and scheduled.start_cue_support
    result = evaluate(InputSnapshot((expectation(2000, 8000),),
                                    (replace(media, start_cues=(at(2240.001),)),)))
    assert next(x for x in result.candidates if x.expectation is not None).span.start == at(2000)


def test_contract_immutability_aware_times_and_policy_lineage() -> None:
    with pytest.raises(ValueError):
        Span(datetime(2026, 1, 1), at(60))
    with pytest.raises(ValueError):
        SkipCounts(no_coverage=-1)
    with pytest.raises(FrozenInstanceError):
        POLICY_V1.version = "2"  # type: ignore[misc]
    assert (POLICY_V1.freeze_merge_seconds, POLICY_V1.changeover_seconds,
            POLICY_V1.edge_window_seconds, POLICY_V1.minimum_session_seconds,
            POLICY_V1.cue_tie_seconds, POLICY_V1.start_cue_before_seconds,
            POLICY_V1.start_cue_after_seconds, POLICY_V1.end_cue_before_seconds,
            POLICY_V1.end_cue_after_seconds, POLICY_V1.unscheduled_seconds,
            POLICY_V1.clock_margin_seconds) == (15, 30, 1200, 60, 60, 120, 180, 180, 60, 120, 43200)


@pytest.mark.parametrize("seconds,expected", [(119, 0), (120, 1)])
def test_unscheduled_minimum_inclusive(seconds: int, expected: int) -> None:
    assert len(evaluate(InputSnapshot((), (asset(0, seconds),))).candidates) == expected


def test_clock_years_off_excluded_and_no_coverage_within_plausible_day() -> None:
    result = evaluate(InputSnapshot((expectation(0, 1800),), (asset(-63072000, -63070200),)))
    assert result.skips.clock_implausible == 1 and not result.candidates
    result = evaluate(InputSnapshot((expectation(0, 1800),), (asset(10000, 11000),)))
    assert result.skips.clock_implausible == 0 and result.skips.no_coverage == 1
    assert all(x.expectation is None for x in result.candidates)


@pytest.mark.parametrize("offset,supported", [(-180, True), (60, True), (-180.001, False),
                                             (60.001, False)])
def test_end_cue_window_inclusive(offset: float, supported: bool) -> None:
    media = replace(asset(0, 3000, freezes=((1800, 1900),)), end_cues=(at(1800 + offset),))
    result = evaluate(InputSnapshot((expectation(0, 1800),), (media,)))
    scheduled = next(x for x in result.candidates if x.expectation is not None)
    assert scheduled.end_cue_support is supported


def test_scheduled_end_must_be_more_than_sixty_seconds_after_start() -> None:
    result = evaluate(InputSnapshot((expectation(0, 60),), (asset(0, 60),)))
    assert not result.candidates
    assert result.skips.no_coverage == 1


def test_silence_must_overlap_freeze_and_both_planned_offsets_are_required() -> None:
    media = asset(0, 3600, freezes=((1700, 1800),), silences=((1800, 1810),))
    result = evaluate(InputSnapshot((expectation(0, 1700),), (media,)))
    scheduled = next(x for x in result.candidates if x.expectation is not None)
    assert not scheduled.end_silence_support and scheduled.strength == Strength.MEDIUM
    with pytest.raises(ValueError, match="planned offsets"):
        replace(scheduled, start_plan_offset_seconds=None)
