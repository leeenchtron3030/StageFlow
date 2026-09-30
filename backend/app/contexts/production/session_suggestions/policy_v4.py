"""Exact per-talk lateness alignment, preserving v2 evidence and strength rules.

For T talks and C changeovers there are O(T*C) states per layer: each cursor's
lateness can refer to any earlier printed edge, plus an anchor. The conservative
bounds are O(T**2*C**3) time and O(T**2*C) backpointer space. Windows prune
transitions in practice. Fallbacks carry lateness and never consume evidence.
"""
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction

from app.contexts.events import ProgramExpectation, ProgramExpectationLifecycle

from .contracts import (
    AssetInput,
    Candidate,
    CandidateV4,
    EdgeKind,
    InputSnapshot,
    PolicyResultV3,
    PolicyV4,
    Reference,
    ScheduleOffsetSetting,
    ScheduleOffsetSource,
    SkipCounts,
    Span,
    Strength,
)
from .policy_v2 import Changeover, Edge, WeightedChangeover, microseconds, subtract, union, weight

TAU_ANCHOR = 30
TAU_STEP = 60
WINDOW = 1200
HARD_BOUND = 5400
POLICY_V4 = PolicyV4(tau_anchor_seconds=TAU_ANCHOR, tau_step_seconds=TAU_STEP,
                     edge_window_seconds=WINDOW, hard_bound_seconds=HARD_BOUND)


def round_seconds(value: int) -> int:
    """Round integer microseconds to seconds, nearest with ties away from zero."""
    return (1 if value >= 0 else -1) * ((abs(value) + 500_000) // 1_000_000)


@dataclass
class Alignment:
    score: Fraction
    cursor: int
    lateness: int
    pending_anchor: bool
    parent: "Alignment | None"
    edges: tuple[Edge, Edge] | None
    rank: int = 0

    def tie_key(self) -> tuple[int, datetime, datetime]:
        assert self.parent is not None and self.edges is not None
        return self.parent.rank, self.edges[0].at, self.edges[1].at


def retain(following: dict[tuple[int, int, bool], Alignment], node: Alignment) -> None:
    key = node.cursor, node.lateness, node.pending_anchor
    old = following.get(key)
    if (old is None or node.score > old.score
            or node.score == old.score and node.tie_key() < old.tie_key()):
        following[key] = node


def edge_cost(lateness: int, previous: int, pending_anchor: bool) -> Fraction:
    return Fraction(abs(lateness - previous),
                    (TAU_ANCHOR if pending_anchor else TAU_STEP) * 1_000_000)


def best_alignment(planned: tuple[ProgramExpectation, ...],
                   changeovers: tuple[WeightedChangeover, ...],
                   start_edges: tuple[Edge, ...], end_edges: tuple[Edge, ...],
                   start_counts: tuple[int, ...], end_counts: tuple[int, ...],
                   override: ScheduleOffsetSetting | None = None,
                   ) -> Alignment:
    states = {(-1, 0, True): Alignment(Fraction(0), -1, 0, True, None, None)}
    entries = () if override is None else override.entries
    next_entry = 0
    for expectation in planned:
        assert expectation.planned_start is not None and expectation.planned_end is not None
        start, end = expectation.planned_start, expectation.planned_end
        anchor = None
        while next_entry < len(entries) and entries[next_entry].effective_from <= start:
            anchor = entries[next_entry].offset_seconds * 1_000_000
            next_entry += 1
        following: dict[tuple[int, int, bool], Alignment] = {}
        # Hard-bound filtering is independent of the path; chain windows are not.
        starts = tuple((j, e, microseconds(e.at - start)) for j, e in enumerate(start_edges)
                       if abs(microseconds(e.at - start)) <= HARD_BOUND * 1_000_000)
        ends = tuple((k, e, microseconds(e.at - end)) for k, e in enumerate(end_edges)
                     if abs(microseconds(e.at - end)) <= HARD_BOUND * 1_000_000)
        for previous in states.values():
            late = previous.lateness if anchor is None else anchor
            pending = previous.pending_anchor if anchor is None else True
            available_starts = tuple((j, e, d) for j, e, d in starts
                                     if 2*j+1 > previous.cursor
                                     and abs(d - late) <= WINDOW * 1_000_000)
            fallback_start = Edge(start + timedelta(microseconds=late),
                                  EdgeKind.SCHEDULE, False, False)
            viable = False
            for j, a, start_late in available_starts or ((None, fallback_start, late),):
                cursor = previous.cursor if j is None else 2*j+1
                start_score = previous.score
                after_start_pending = pending
                if j is not None:
                    if j != previous.cursor // 2:
                        start_score += changeovers[j].strength
                    start_score += POLICY_V4.cue_bonus * start_counts[j]
                    start_score -= edge_cost(start_late, late, pending)
                    after_start_pending = False
                available_ends = tuple((k, e, d) for k, e, d in ends
                                       if 2*k > cursor
                                       and abs(d - start_late) <= WINDOW * 1_000_000
                                       and microseconds(e.at - a.at) >=
                                       POLICY_V4.minimum_session_seconds * 1_000_000)
                fallback_end = Edge(end + timedelta(microseconds=start_late),
                                    EdgeKind.SCHEDULE, False, False)
                for k, b, end_late in available_ends or ((None, fallback_end, start_late),):
                    if microseconds(b.at - a.at) < POLICY_V4.minimum_session_seconds * 1_000_000:
                        continue
                    viable = True
                    score = start_score
                    last, next_pending = cursor, after_start_pending
                    if k is not None:
                        if k != cursor // 2:
                            score += changeovers[k].strength
                        score += POLICY_V4.cue_bonus * end_counts[k]
                        score -= edge_cost(end_late, start_late, after_start_pending)
                        last, next_pending = 2*k, False
                    retain(following, Alignment(score, last, end_late, next_pending,
                                                previous, (a, b)))
            if not viable:
                retain(following, Alignment(previous.score, previous.cursor, late, pending,
                    previous, (fallback_start, Edge(end + timedelta(microseconds=late),
                                                    EdgeKind.SCHEDULE, False, False))))
        for rank, node in enumerate(sorted(following.values(), key=lambda n: n.tie_key())):
            node.rank = rank
        states = following
    return min(states.values(), key=lambda n: (-n.score, n.rank))


def align(planned: tuple[ProgramExpectation, ...],
          changeovers: tuple[WeightedChangeover, ...],
          start_edges: tuple[Edge, ...], end_edges: tuple[Edge, ...],
          start_counts: tuple[int, ...], end_counts: tuple[int, ...],
          override: ScheduleOffsetSetting | None = None,
          ) -> tuple[tuple[Edge, Edge], ...]:
    best = best_alignment(planned, changeovers, start_edges, end_edges,
                          start_counts, end_counts, override)
    result: list[tuple[Edge, Edge]] = []
    while best.parent is not None:
        assert best.edges is not None
        result.append(best.edges)
        best = best.parent
    return tuple(reversed(result))


def evaluate(snapshot: InputSnapshot, override: ScheduleOffsetSetting | None = None
             ) -> PolicyResultV3:
    p = POLICY_V4
    current = tuple(replace(
        x, planned_start=None if x.planned_start is None else x.planned_start.astimezone(UTC),
        planned_end=None if x.planned_end is None else x.planned_end.astimezone(UTC),
    ) for x in snapshot.expectations if x.lifecycle_state == ProgramExpectationLifecycle.CURRENT)
    planned = tuple(sorted(
        (x for x in current if x.planned_start is not None and x.planned_end is not None),
        key=lambda x: (x.planned_start, x.id.value),
    ))
    skips = dict.fromkeys(SkipCounts.__dataclass_fields__, 0)
    skips["no_planned_time"] = len(current) - len(planned)
    starts = [x.planned_start for x in planned if x.planned_start is not None]
    ends = [x.planned_end for x in planned if x.planned_end is not None]
    lower = min(starts) - timedelta(seconds=p.clock_margin_seconds) if starts else None
    upper = max(ends) + timedelta(seconds=p.clock_margin_seconds) if ends else None
    used: list[AssetInput] = []
    for item in sorted(snapshot.assets, key=lambda x: x.asset_id.value):
        if item.coverage is None:
            skips["no_timing_evidence"] += 1
            continue
        if (lower is not None and upper is not None
                and (item.coverage.end <= lower or item.coverage.start >= upper)):
            skips["clock_implausible"] += 1
            continue
        if not item.segmentation_ids:
            skips["no_segmentation"] += 1
        used.append(item)
    coverage = union(tuple(x.coverage for x in used if x.coverage is not None))
    freezes: list[Span] = []
    silences: list[Span] = []
    for item in used:
        assert item.coverage is not None
        for interval in item.intervals:
            start = item.coverage.start + timedelta(microseconds=interval.start_microseconds)
            end = min(item.coverage.end, item.coverage.start
                      + timedelta(microseconds=interval.end_microseconds))
            if start < end:
                (freezes if interval.kind == "freeze" else silences).append(Span(start, end))
    changes = [Changeover(x.start, x.end, EdgeKind.FREEZE)
               for x in union(tuple(freezes), p.freeze_merge_seconds)
               if (x.end - x.start).total_seconds() >= p.changeover_seconds]
    changes.extend(Changeover(a.end, b.start, EdgeKind.GAP)
                   for a, b in zip(coverage, coverage[1:], strict=False)
                   if (b.start - a.end).total_seconds() >= p.coverage_gap_seconds)
    if coverage:
        changes.extend((Changeover(coverage[0].start, coverage[0].start, EdgeKind.COVERAGE),
                        Changeover(coverage[-1].end, coverage[-1].end, EdgeKind.COVERAGE)))
    changes.sort(key=lambda x: (x.start, x.end, x.kind))
    silence_union = union(tuple(silences))
    weighted = tuple(weight(c, silence_union) for c in changes)
    start_cues = tuple(t for x in used for t in x.start_cues)
    end_cues = tuple(t for x in used for t in x.end_cues)

    def cue_count(c: Changeover, start: bool) -> int:
        at = c.end if start else c.start
        before = p.start_cue_before_seconds if start else p.end_cue_before_seconds
        after = p.start_cue_after_seconds if start else p.end_cue_after_seconds
        return sum(-before <= (t - at).total_seconds() <= after
                   for t in (start_cues if start else end_cues))

    start_counts = tuple(cue_count(c, True) for c in changes)
    end_counts = tuple(cue_count(c, False) for c in changes)

    def edge(index: int, start: bool) -> Edge:
        c = weighted[index]
        return Edge(c.span.end if start else c.span.start, c.span.kind,
                    c.silent_share >= Fraction(str(p.silence_support_share)),
                    (start_counts if start else end_counts)[index] > 0)

    def candidate(expectation: ProgramExpectation | None, a: Edge, b: Edge,
                  overlap: bool = False) -> Candidate:
        weak = expectation is None or overlap or EdgeKind.SCHEDULE in (a.kind, b.kind)
        support = a.silence or b.silence or a.cue or b.cue
        offset = (0 if expectation is None or expectation.planned_start is None else
                  round_seconds(microseconds(a.at - expectation.planned_start)))
        producer = (expectation is not None and expectation.planned_start is not None
                    and override is not None and any(
                        e.effective_from <= expectation.planned_start for e in override.entries))
        return CandidateV4(
            None if expectation is None else Reference(expectation.id, expectation.revision),
            Span(a.at, b.at), a.kind, b.kind,
            None if expectation is None or expectation.planned_start is None
            else (a.at - expectation.planned_start).total_seconds(),
            None if expectation is None or expectation.planned_end is None
            else (b.at - expectation.planned_end).total_seconds(),
            a.silence, b.silence, a.cue, b.cue, overlap,
            Strength.WEAK if weak else Strength.STRONG if support else Strength.MEDIUM,
            tuple(sorted({x.qualification for x in used if x.qualification is not None})),
            tuple(x.timing for x in used if x.timing is not None),
            tuple(sorted({i for x in used for i in x.segmentation_ids}, key=lambda x: x.value)),
            tuple(x.transcript for x in used if x.transcript is not None),
            offset, (ScheduleOffsetSource.PRODUCER if producer else
                     ScheduleOffsetSource.ESTIMATED if offset else ScheduleOffsetSource.NONE),
        )

    eligible: list[ProgramExpectation] = []
    window = timedelta(seconds=p.edge_window_seconds)
    for expectation in planned:
        assert expectation.planned_start is not None and expectation.planned_end is not None
        if all(any(c.start <= at + window and c.end >= at - window for c in coverage)
               for at in (expectation.planned_start, expectation.planned_end)):
            eligible.append(expectation)
        else:
            skips["no_coverage"] += 1
    aligned = align(tuple(eligible), weighted,
                    tuple(edge(i, True) for i in range(len(changes))),
                    tuple(edge(i, False) for i in range(len(changes))),
                    start_counts, end_counts, override)
    candidates: list[Candidate] = []
    for expectation, (a, b) in zip(eligible, aligned, strict=True):
        if (b.at - a.at).total_seconds() < p.minimum_session_seconds:
            # A too-short planned fallback has no viable suggestion. Preserve
            # v1's accounting instead of constructing an invalid contract.
            skips["no_coverage"] += 1
            continue
        candidates.append(candidate(expectation, a, b))
    for i, a in enumerate(candidates):
        if any(i != j and a.span.start < b.span.end and b.span.start < a.span.end
               for j, b in enumerate(candidates)):
            candidates[i] = replace(a, overlap=True, strength=Strength.WEAK)
    excluded = tuple(x.span for x in candidates) + tuple(
        Span(c.start, c.end) for c in changes if c.start < c.end)
    for covered in coverage:
        for span in subtract(covered, excluded):
            if (span.end - span.start).total_seconds() >= p.unscheduled_seconds:
                a = next((edge(i, True) for i, c in enumerate(changes) if c.end == span.start),
                         Edge(span.start, EdgeKind.SCHEDULE, False, False))
                b = next((edge(i, False) for i, c in enumerate(changes) if c.start == span.end),
                         Edge(span.end, EdgeKind.SCHEDULE, False, False))
                candidates.append(candidate(None, a, b))
    return PolicyResultV3(tuple(sorted(candidates, key=lambda x: (
        x.span.start, x.span.end, "" if x.expectation is None else x.expectation.id.value,
    ))), SkipCounts(**skips))
