"""Pure v2 joint alignment; v1 remains in policy.py for exact replay.

For T planned talks and C changeovers, alignment takes O(T*C**3) time and
O(T*C) backpointer space. Cue support is precomputed; rank-based lexicographic
ties do not copy paths. The typical ~50 changeovers/day keeps this bounded DP
practical. Schedule fallback edges never advance the evidence cursor.
"""
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction

from app.contexts.events import ProgramExpectation, ProgramExpectationLifecycle

from .contracts import (
    POLICY_V2,
    AssetInput,
    Candidate,
    CandidateV2,
    EdgeKind,
    InputSnapshot,
    PolicyResult,
    Reference,
    SkipCounts,
    Span,
    Strength,
)
from .policy import Changeover, Edge, subtract, union


@dataclass(frozen=True)
class WeightedChangeover:
    span: Changeover
    strength: Fraction
    silent_share: Fraction


def microseconds(delta: timedelta) -> int:
    return delta // timedelta(microseconds=1)


def weight(changeover: Changeover, silences: tuple[Span, ...]) -> WeightedChangeover:
    p = POLICY_V2
    length = microseconds(changeover.end - changeover.start)
    overlap = sum(max(0, microseconds(min(s.end, changeover.end)
                                    - max(s.start, changeover.start))) for s in silences)
    share = Fraction(overlap, length) if length else Fraction(0)
    strength = Fraction(min(length, p.strength_cap_seconds * 1_000_000),
                        p.strength_unit_seconds * 1_000_000)
    if changeover.kind == EdgeKind.COVERAGE:
        strength = Fraction(p.coverage_strength)
    elif changeover.kind == EdgeKind.FREEZE:
        strength *= 1 + p.silence_multiplier * share
    return WeightedChangeover(changeover, strength, share)


@dataclass
class Alignment:
    score: Fraction
    # Changeover c has end position 2*c, then start position 2*c+1; -1 is unused.
    cursor: int
    parent: "Alignment | None"
    edges: tuple[Edge, Edge] | None
    rank: int = 0

    def tie_key(self) -> tuple[int, datetime, datetime]:
        assert self.parent is not None and self.edges is not None
        return self.parent.rank, self.edges[0].at, self.edges[1].at


def retain(following: dict[int, Alignment], node: Alignment) -> None:
    old = following.get(node.cursor)
    if (old is None or node.score > old.score
            or node.score == old.score and node.tie_key() < old.tie_key()):
        following[node.cursor] = node


def align(planned: tuple[ProgramExpectation, ...],
          changeovers: tuple[WeightedChangeover, ...],
          start_edges: tuple[Edge, ...], end_edges: tuple[Edge, ...],
          start_counts: tuple[int, ...], end_counts: tuple[int, ...],
          ) -> tuple[tuple[Edge, Edge], ...]:
    p = POLICY_V2
    states = {-1: Alignment(Fraction(0), -1, None, None)}
    for expectation in planned:
        assert expectation.planned_start is not None and expectation.planned_end is not None
        start, end = expectation.planned_start, expectation.planned_end
        starts = tuple(j for j, e in enumerate(start_edges)
                       if abs((e.at - start).total_seconds()) <= p.edge_window_seconds)
        ends = tuple(k for k, e in enumerate(end_edges)
                     if abs((e.at - end).total_seconds()) <= p.edge_window_seconds)
        following: dict[int, Alignment] = {}

        for previous in states.values():
            viable = False
            available_starts = tuple(j for j in starts if 2 * j + 1 > previous.cursor)
            for j in available_starts or (None,):
                a = (Edge(start, EdgeKind.SCHEDULE, False, False)
                     if j is None else start_edges[j])
                cursor = previous.cursor if j is None else 2 * j + 1
                available_ends = tuple(k for k in ends if 2 * k > cursor
                                       and (end_edges[k].at - a.at).total_seconds()
                                       >= p.minimum_session_seconds)
                for k in available_ends or (None,):
                    b = (Edge(end, EdgeKind.SCHEDULE, False, False)
                         if k is None else end_edges[k])
                    if (b.at - a.at).total_seconds() < p.minimum_session_seconds:
                        continue
                    viable = True
                    score = previous.score
                    last = previous.cursor
                    for pos, edge, plan, counts in (
                        (None if j is None else 2 * j + 1, a, start, start_counts),
                        (None if k is None else 2 * k, b, end, end_counts),
                    ):
                        if pos is not None:
                            index = pos // 2
                            if index != last // 2:
                                score += changeovers[index].strength
                            # Strength is counted once per changeover; cues belong to each
                            # observed edge, so a shared changeover's start and end both count.
                            score += p.cue_bonus * counts[index]
                            score -= Fraction(abs(microseconds(edge.at - plan)),
                                              p.plan_distance_seconds * 1_000_000)
                            last = pos
                    retain(following, Alignment(score, last, previous, (a, b)))
            if not viable:
                # Both planned edges are exempt from the evidence order. Keep
                # this predecessor even when other predecessors can use evidence.
                retain(following, Alignment(previous.score, previous.cursor, previous,
                    (Edge(start, EdgeKind.SCHEDULE, False, False),
                     Edge(end, EdgeKind.SCHEDULE, False, False))))
        for rank, node in enumerate(sorted(following.values(), key=lambda n: n.tie_key())):
            node.rank = rank
        states = following
    best = min(states.values(), key=lambda n: (-n.score, n.rank))
    result: list[tuple[Edge, Edge]] = []
    while best.parent is not None:
        assert best.edges is not None
        result.append(best.edges)
        best = best.parent
    return tuple(reversed(result))


def evaluate(snapshot: InputSnapshot) -> PolicyResult:
    p = POLICY_V2
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
        return CandidateV2(
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
                    tuple(edge(i, False) for i in range(len(changes))), start_counts, end_counts)
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
    return PolicyResult(tuple(sorted(candidates, key=lambda x: (
        x.span.start, x.span.end, "" if x.expectation is None else x.expectation.id.value,
    ))), SkipCounts(**skips))
