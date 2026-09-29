"""Pure recorder-clock policy. Version 1 constants are immutable run lineage."""
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from app.contexts.events import ProgramExpectation, ProgramExpectationLifecycle

from .contracts import (
    POLICY_V1,
    AssetInput,
    Candidate,
    EdgeKind,
    InputSnapshot,
    PolicyResult,
    Reference,
    SkipCounts,
    Span,
    Strength,
)


@dataclass(frozen=True)
class Changeover:
    start: datetime
    end: datetime
    kind: EdgeKind


@dataclass(frozen=True)
class Edge:
    at: datetime
    kind: EdgeKind
    silence: bool
    cue: bool


def union(spans: tuple[Span, ...], gap: int = 0) -> tuple[Span, ...]:
    result: list[Span] = []
    for span in sorted(spans, key=lambda x: (x.start, x.end)):
        if result and span.start <= result[-1].end + timedelta(seconds=gap):
            result[-1] = Span(result[-1].start, max(result[-1].end, span.end))
        else:
            result.append(span)
    return tuple(result)


def subtract(span: Span, excluded: tuple[Span, ...]) -> tuple[Span, ...]:
    pieces = [span]
    for other in excluded:
        result: list[Span] = []
        for item in pieces:
            if other.end <= item.start or other.start >= item.end:
                result.append(item)
            else:
                if item.start < other.start:
                    result.append(Span(item.start, other.start))
                if other.end < item.end:
                    result.append(Span(other.end, item.end))
        pieces = result
    return tuple(pieces)


def evaluate(snapshot: InputSnapshot) -> PolicyResult:
    p = POLICY_V1
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
    changeovers = [Changeover(x.start, x.end, EdgeKind.FREEZE)
                   for x in union(tuple(freezes), p.freeze_merge_seconds)
                   if (x.end - x.start).total_seconds() >= p.changeover_seconds]
    changeovers.extend(Changeover(a.end, b.start, EdgeKind.GAP)
                       for a, b in zip(coverage, coverage[1:], strict=False)
                       if (b.start - a.end).total_seconds() >= p.changeover_seconds)
    # Coverage bounds are zero-width edges; short gaps do not become changeovers.
    if coverage:
        changeovers.extend((Changeover(coverage[0].start, coverage[0].start, EdgeKind.COVERAGE),
                            Changeover(coverage[-1].end, coverage[-1].end, EdgeKind.COVERAGE)))
    changeovers.sort(key=lambda x: (x.start, x.end, x.kind))
    start_cues = tuple(t for x in used for t in x.start_cues)
    end_cues = tuple(t for x in used for t in x.end_cues)

    def edge(c: Changeover, start: bool) -> Edge:
        at = c.end if start else c.start
        before = p.start_cue_before_seconds if start else p.end_cue_before_seconds
        after = p.start_cue_after_seconds if start else p.end_cue_after_seconds
        return Edge(at, c.kind,
                    any((s.start < c.end and s.end > c.start) if c.start < c.end
                        else s.start <= at <= s.end for s in silences),
                    any(-before <= (t - at).total_seconds() <= after
                        for t in (start_cues if start else end_cues)))

    def pick(at: datetime, start: bool, after: datetime | None = None) -> Edge | None:
        window = timedelta(seconds=p.edge_window_seconds)
        available = tuple(x for x in coverage if x.start <= at + window and x.end >= at - window)
        if not available:
            return None
        candidates = [edge(c, start) for c in changeovers
                      if abs(((c.end if start else c.start) - at).total_seconds())
                      <= p.edge_window_seconds
                      and (after is None or (c.start - after).total_seconds()
                           > p.minimum_session_seconds)]
        if candidates:
            nearest = min(candidates, key=lambda e: (
                abs((e.at - at).total_seconds()), e.at, e.kind))
            tied = [e for e in candidates if abs((e.at - nearest.at).total_seconds())
                    <= p.cue_tie_seconds]
            return min(tied, key=lambda e: (
                not e.cue, abs((e.at - at).total_seconds()), e.at, e.kind))
        clipped = min((max(x.start, min(at, x.end)) for x in available),
                      key=lambda t: (abs((t - at).total_seconds()), t))
        if after is not None and (clipped - after).total_seconds() <= p.minimum_session_seconds:
            return None
        return Edge(clipped, EdgeKind.SCHEDULE, False, False)

    def candidate(expectation: ProgramExpectation | None, a: Edge, b: Edge,
                  overlap: bool = False) -> Candidate:
        weak = expectation is None or overlap or EdgeKind.SCHEDULE in (a.kind, b.kind)
        support = a.silence or b.silence or a.cue or b.cue
        return Candidate(
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

    matched: list[tuple[ProgramExpectation, Edge, Edge, bool]] = []
    for expectation in planned:
        assert expectation.planned_start is not None and expectation.planned_end is not None
        a = pick(expectation.planned_start, True)
        b = None if a is None else pick(expectation.planned_end, False, a.at)
        if a is None or b is None:
            skips["no_coverage"] += 1
            continue
        matched.append((expectation, a, b, False))
    for i in range(1, len(matched)):
        prev, a, b, conflict = matched[i - 1]
        curr, c, d, current_conflict = matched[i]
        if b.at <= c.at:
            continue
        shared = [x for x in changeovers if x.kind != EdgeKind.COVERAGE
                  and (x.start - a.at).total_seconds() > p.minimum_session_seconds
                  and (d.at - x.end).total_seconds() > p.minimum_session_seconds
                  and c.at <= x.end and x.start <= b.at]
        if shared:
            assert prev.planned_end is not None and curr.planned_start is not None
            center = prev.planned_end + (curr.planned_start - prev.planned_end) / 2
            chosen = min(shared, key=lambda x: (abs((x.start - center).total_seconds()), x.start))
            matched[i - 1] = prev, a, edge(chosen, False), conflict
            matched[i] = curr, edge(chosen, True), d, current_conflict
        else:
            matched[i - 1] = prev, a, b, True
            matched[i] = curr, c, d, True
    candidates = [candidate(*m) for m in matched]
    # Re-evaluate conflicts after shared-edge adjustments, preserving explicit overlap.
    for i, a in enumerate(candidates):
        if any(i != j and a.span.start < b.span.end and b.span.start < a.span.end
               for j, b in enumerate(candidates)):
            candidates[i] = replace(a, overlap=True, strength=Strength.WEAK)
    excluded = tuple(x.span for x in candidates) + tuple(
        Span(x.start, x.end) for x in changeovers if x.start < x.end)
    for covered in coverage:
        for span in subtract(covered, excluded):
            if (span.end - span.start).total_seconds() >= p.unscheduled_seconds:
                a = next((edge(c, True) for c in changeovers if c.end == span.start),
                         Edge(span.start, EdgeKind.SCHEDULE, False, False))
                b = next((edge(c, False) for c in changeovers if c.start == span.end),
                         Edge(span.end, EdgeKind.SCHEDULE, False, False))
                candidates.append(candidate(None, a, b))
    return PolicyResult(tuple(sorted(candidates, key=lambda x: (
        x.span.start, x.span.end, "" if x.expectation is None else x.expectation.id.value,
    ))), SkipCounts(**skips))
