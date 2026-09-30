"""Pure boundary evidence prototype built on v3; no persisted policy registration.

Offset estimation and joint alignment import v3/v2 unchanged. Local edge views
filter candidates per planned role; exact Fraction bonuses use v2's unit cue
multiplier. No legacy policy constants are patched.
"""
from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction
from typing import cast

from app.contexts.events import ProgramExpectation, ProgramExpectationLifecycle

from .contracts import (
    AssetInput,
    Candidate,
    CandidateV3,
    EdgeKind,
    InputSnapshot,
    PolicyResultV3,
    PolicyV3,
    Reference,
    ScheduleOffsetSetting,
    ScheduleOffsetSource,
    SkipCountsV5,
    Span,
    Strength,
)
from .policy import Changeover, Edge, subtract, union
from .policy_v2 import WeightedChangeover, microseconds, weight
from .policy_v2 import align as align_v2
from .policy_v3 import schedule_blocks

CUE_RADIUS = 30
CUE_WEIGHT = 10
CUE_EDGE_GAP = 30
CUE_EDGE_STRENGTH = 3
COVERAGE_STRENGTH_V5 = 5
OUTSIDE_PROGRAM_MARGIN = 1800


@dataclass(frozen=True, slots=True)
class PolicyV5(PolicyV3):
    version: str = "5"
    cue_radius: int = CUE_RADIUS
    cue_weight: int = CUE_WEIGHT
    cue_edge_gap: int = CUE_EDGE_GAP
    cue_edge_strength: int = CUE_EDGE_STRENGTH
    coverage_strength: int = COVERAGE_STRENGTH_V5
    outside_program_margin: int = OUTSIDE_PROGRAM_MARGIN


POLICY_V5 = PolicyV5()


def cue_support(at: datetime, cues: tuple[datetime, ...]) -> Fraction:
    radius = POLICY_V5.cue_radius * 1_000_000
    at = at.astimezone(UTC)
    return sum((POLICY_V5.cue_weight * Fraction(radius - distance, radius)
                for t in cues
                if (distance := abs(microseconds(t.astimezone(UTC) - at))) <= radius), Fraction(0))


def cue_edges(cues: tuple[datetime, ...], specific: tuple[datetime, ...],
              changes: tuple[Changeover, ...], start: bool) -> tuple[datetime, ...]:
    # Greedy chronological clusters span <=60 s from their first hit, never
    # transitively chaining a long run. Start uses earliest; end uses latest.
    clusters: list[list[datetime]] = []
    for t in sorted(t.astimezone(UTC) for t in cues):
        if not clusters or microseconds(t - clusters[-1][0]) > 60_000_000:
            clusters.append([])
        clusters[-1].append(t)
    specific_set = {t.astimezone(UTC) for t in specific}
    result: list[datetime] = []
    for cluster in clusters:
        if len(cluster) < 2 and cluster[0] not in specific_set:
            continue
        at = cluster[0] if start else cluster[-1]
        if not any(c.kind in (EdgeKind.FREEZE, EdgeKind.GAP)
                   and abs(microseconds((c.end if start else c.start) - at))
                   <= POLICY_V5.cue_edge_gap * 1_000_000 for c in changes):
            result.append(at)
    return tuple(result)


def eligible_edges(edges: tuple[Edge, ...], at: datetime,
                   cue_times: frozenset[datetime]) -> tuple[int, ...]:
    # Coverage is fallback per planned role, before predecessor/cursor filtering.
    # A real edge anywhere in this inclusive shifted window suppresses all
    # coverage candidates for that role even if ordering later makes it unusable.
    indices = tuple(i for i, e in enumerate(edges)
                    if abs(microseconds(e.at - at)) <= POLICY_V5.edge_window_seconds * 1_000_000
                    and (e.kind != EdgeKind.CUE or e.at in cue_times))
    if any(edges[i].kind in (EdgeKind.FREEZE, EdgeKind.GAP, EdgeKind.CUE) for i in indices):
        return tuple(i for i in indices if edges[i].kind != EdgeKind.COVERAGE)
    return indices


class _WindowedEdges(tuple[Edge, ...]):
    """Per-call eligibility adapter for the frozen v2 alignment interface.

    V2 enumerates each role once per talk to select indices, then indexes the
    original tuple for scoring and output. Enumeration masks ineligible edges
    with a timestamp outside that talk's window; indexing retains real times.
    Each evaluate call owns fresh views, so cursors never escape or affect replay.
    This keeps the actual DP, scoring, shared strength, fallbacks and ties in v2.
    """

    def __new__(cls, edges: tuple[Edge, ...], plans: tuple[datetime, ...],
                cue_times: frozenset[datetime]) -> "_WindowedEdges":
        return super().__new__(cls, edges)

    def __init__(self, edges: tuple[Edge, ...], plans: tuple[datetime, ...],
                 cue_times: frozenset[datetime]) -> None:
        self._edges = edges
        self._plans = iter(plans)
        self._cue_times = cue_times

    def __iter__(self) -> Iterator[Edge]:
        at = next(self._plans)
        eligible = frozenset(eligible_edges(self._edges, at, self._cue_times))
        distant = (datetime(1, 1, 1, tzinfo=UTC) if at.year > 5000
                   else datetime(9999, 12, 31, tzinfo=UTC))
        return iter(e if i in eligible else replace(e, at=distant)
                    for i, e in enumerate(self._edges))


def align(planned: tuple[ProgramExpectation, ...],
          changes: tuple[WeightedChangeover, ...],
          start_edges: tuple[Edge, ...], end_edges: tuple[Edge, ...],
          start_support: tuple[Fraction, ...], end_support: tuple[Fraction, ...],
          start_cues: frozenset[datetime], end_cues: frozenset[datetime],
          ) -> tuple[tuple[Edge, Edge], ...]:
    starts = tuple(p.planned_start for p in planned if p.planned_start is not None)
    ends = tuple(p.planned_end for p in planned if p.planned_end is not None)
    # v2 annotates counts as ints, but only multiplies by the frozen unit cue
    # bonus and adds to a Fraction score. Passing Fractions preserves exactness.
    return align_v2(planned, changes,
                    _WindowedEdges(start_edges, starts, start_cues),
                    _WindowedEdges(end_edges, ends, end_cues),
                    cast(tuple[int, ...], start_support), cast(tuple[int, ...], end_support))


def evaluate(snapshot: InputSnapshot, override: ScheduleOffsetSetting | None = None
             ) -> PolicyResultV3:
    p = POLICY_V5
    current = tuple(replace(
        x, planned_start=None if x.planned_start is None else x.planned_start.astimezone(UTC),
        planned_end=None if x.planned_end is None else x.planned_end.astimezone(UTC),
    ) for x in snapshot.expectations if x.lifecycle_state == ProgramExpectationLifecycle.CURRENT)
    planned = tuple(sorted(
        (x for x in current if x.planned_start is not None and x.planned_end is not None),
        key=lambda x: (x.planned_start, x.id.value),
    ))
    skips = dict.fromkeys(SkipCountsV5.__dataclass_fields__, 0)
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
    printed = {x.id: x for x in planned}
    blocks, offsets = schedule_blocks(planned, weighted, override)
    planned = tuple(replace(x,
        planned_start=x.planned_start + timedelta(seconds=offsets[x.id].schedule_offset_seconds),
        planned_end=x.planned_end + timedelta(seconds=offsets[x.id].schedule_offset_seconds),
    ) for x in planned if x.planned_start is not None and x.planned_end is not None)
    # Estimation above deliberately sees exactly v3 weights and no cue edges.
    program_start = min((x.planned_start for x in planned if x.planned_start is not None),
                        default=None)
    program_end = max((x.planned_end for x in planned if x.planned_end is not None), default=None)
    start_cues = tuple(t for x in used for t in x.start_cues)
    end_cues = tuple(t for x in used for t in x.end_cues)

    specific_starts = tuple(t for x in used for t in x.specific_start_cues)
    specific_ends = tuple(t for x in used for t in x.specific_end_cues)
    start_only = cue_edges(start_cues, specific_starts, tuple(changes), True)
    end_only = cue_edges(end_cues, specific_ends, tuple(changes), False)
    changes.extend(Changeover(t, t, EdgeKind.CUE) for t in sorted(set(start_only + end_only)))
    changes.sort(key=lambda x: (x.start, x.end, x.kind))
    weighted = tuple(
        WeightedChangeover(c, Fraction(p.cue_edge_strength), Fraction(0))
        if c.kind == EdgeKind.CUE else
        WeightedChangeover(c, Fraction(p.coverage_strength), Fraction(0))
        if c.kind == EdgeKind.COVERAGE else weight(c, silence_union) for c in changes)
    changeover_cues = tuple(t for x in used for t in x.changeover_cues)
    start_counts = tuple(cue_support(c.end, start_cues + (
        changeover_cues if c.kind in (EdgeKind.FREEZE, EdgeKind.GAP) else ())) for c in changes)
    end_counts = tuple(cue_support(c.start, end_cues + (
        changeover_cues if c.kind in (EdgeKind.FREEZE, EdgeKind.GAP) else ())) for c in changes)

    def edge(index: int, start: bool) -> Edge:
        c = weighted[index]
        return Edge(c.span.end if start else c.span.start, c.span.kind,
                    c.silent_share >= Fraction(str(p.silence_support_share)),
                    (start_counts if start else end_counts)[index] > 0)

    def candidate(expectation: ProgramExpectation | None, a: Edge, b: Edge,
                  overlap: bool = False) -> Candidate:
        weak = expectation is None or overlap or EdgeKind.SCHEDULE in (a.kind, b.kind)
        support = (EdgeKind.CUE not in (a.kind, b.kind)
                   and (a.silence or b.silence or a.cue or b.cue))
        block = None if expectation is None else offsets[expectation.id]
        expectation = None if expectation is None else printed[expectation.id]
        return CandidateV3(
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
            0 if block is None else block.schedule_offset_seconds,
            ScheduleOffsetSource.NONE if block is None else block.schedule_offset_source,
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
                    tuple(edge(i, False) for i in range(len(changes))), start_counts, end_counts,
                    frozenset(start_only), frozenset(end_only))
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
                if (program_start is not None and program_end is not None
                        and (span.start > program_end + timedelta(seconds=p.outside_program_margin)
                             or span.end < program_start
                             - timedelta(seconds=p.outside_program_margin))):
                    skips["outside_program"] += 1
                    continue
                a = next((edge(i, True) for i, c in enumerate(changes) if c.end == span.start
                          and (c.kind != EdgeKind.CUE or c.end in start_only)),
                         Edge(span.start, EdgeKind.SCHEDULE, False, False))
                b = next((edge(i, False) for i, c in enumerate(changes) if c.start == span.end
                          and (c.kind != EdgeKind.CUE or c.start in end_only)),
                         Edge(span.end, EdgeKind.SCHEDULE, False, False))
                candidates.append(candidate(None, a, b))
    return PolicyResultV3(tuple(sorted(candidates, key=lambda x: (
        x.span.start, x.span.end, "" if x.expectation is None else x.expectation.id.value,
    ))), SkipCountsV5(**skips), blocks)
