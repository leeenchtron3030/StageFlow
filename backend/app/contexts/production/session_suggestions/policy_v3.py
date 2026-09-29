"""Pure v3 schedule offsets followed by the unchanged v2 joint alignment.

The evidence preparation and candidate construction mirror v2 to preserve printed-plan
clock filtering and order. Alignment and exact changeover weights are shared with v2.
For T talks and C changeovers, estimation costs O(134*T*C) time and O(T+C)
space; alignment remains O(T*C**3) time and O(T*C) backpointer space.
"""
from dataclasses import replace
from datetime import UTC, timedelta
from fractions import Fraction

from app.contexts.events import ProgramExpectation, ProgramExpectationLifecycle
from app.shared.ids import EntityId

from .contracts import (
    POLICY_V3,
    AssetInput,
    Candidate,
    CandidateV3,
    EdgeKind,
    InputSnapshot,
    PolicyResultV3,
    Reference,
    ScheduleBlock,
    ScheduleOffsetSetting,
    ScheduleOffsetSource,
    SkipCounts,
    Span,
    Strength,
)
from .policy import Changeover, Edge, subtract, union
from .policy_v2 import WeightedChangeover, align, microseconds, weight


def support_score(planned: tuple[ProgramExpectation, ...],
                  changes: tuple[WeightedChangeover, ...], offset: int) -> Fraction:
    p = POLICY_V3
    tolerance = p.offset_support_seconds * 1_000_000
    score = -Fraction(abs(offset), p.offset_penalty_seconds)
    for talk in planned:
        assert talk.planned_start is not None and talk.planned_end is not None
        for at, start in ((talk.planned_start, True), (talk.planned_end, False)):
            shifted = at + timedelta(seconds=offset)
            best = Fraction(0)
            for change in changes:
                edge = change.span.end if start else change.span.start
                distance = abs(microseconds(edge - shifted))
                if distance <= tolerance:
                    best = max(best, change.strength * Fraction(tolerance - distance, tolerance))
            score += best
    return score


def estimate_offset(planned: tuple[ProgramExpectation, ...],
                    changes: tuple[WeightedChangeover, ...]) -> tuple[int, Fraction]:
    p = POLICY_V3
    if not planned or not changes:
        return 0, Fraction(0)
    scores: dict[int, Fraction] = {}

    def key(offset: int) -> tuple[Fraction, int, int]:
        if offset not in scores:
            scores[offset] = support_score(planned, changes, offset)
        return -scores[offset], abs(offset), offset

    best = min(range(-p.offset_limit_seconds, p.offset_limit_seconds + 1,
                     p.offset_grid_seconds), key=key)
    best = min(range(max(-p.offset_limit_seconds, best - p.offset_grid_seconds),
                     min(p.offset_limit_seconds, best + p.offset_grid_seconds) + 1,
                     p.offset_refine_seconds), key=key)
    margin = scores[best] - scores[0]
    return best, margin


def schedule_blocks(planned: tuple[ProgramExpectation, ...],
                    changes: tuple[WeightedChangeover, ...],
                    override: ScheduleOffsetSetting | None,
                    ) -> tuple[tuple[ScheduleBlock, ...], dict[EntityId, ScheduleBlock]]:
    groups: list[list[ProgramExpectation]] = []
    for talk in planned:
        assert talk.planned_start is not None and talk.planned_end is not None
        previous_end = groups[-1][-1].planned_end if groups else None
        if previous_end is None or microseconds(talk.planned_start - previous_end) >= (
                POLICY_V3.block_gap_seconds * 1_000_000):
            groups.append([])
        groups[-1].append(talk)
    blocks: list[ScheduleBlock] = []
    offsets: dict[EntityId, ScheduleBlock] = {}
    for ordinal, group in enumerate(groups):
        first, last = group[0].planned_start, group[-1].planned_start
        assert first is not None and last is not None
        estimated, margin = estimate_offset(tuple(group), changes)
        entry = None if override is None else next((e for e in reversed(override.entries)
                                                    if e.effective_from <= first), None)
        version = None
        if entry is not None:
            assert override is not None
            offset, source = entry.offset_seconds, ScheduleOffsetSource.PRODUCER
            version = override.version
        elif margin >= POLICY_V3.offset_gate_per_talk * len(group):
            offset, source = estimated, ScheduleOffsetSource.ESTIMATED
        else:
            offset, source = 0, ScheduleOffsetSource.NONE
        block = ScheduleBlock(ordinal, first, last, len(group), offset, source,
                              float(margin), version)
        blocks.append(block)
        offsets.update((talk.id, block) for talk in group)
    return tuple(blocks), offsets


def evaluate(snapshot: InputSnapshot, override: ScheduleOffsetSetting | None = None
             ) -> PolicyResultV3:
    p = POLICY_V3
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
    printed = {x.id: x for x in planned}
    blocks, offsets = schedule_blocks(planned, weighted, override)
    planned = tuple(replace(x,
        planned_start=x.planned_start + timedelta(seconds=offsets[x.id].schedule_offset_seconds),
        planned_end=x.planned_end + timedelta(seconds=offsets[x.id].schedule_offset_seconds),
    ) for x in planned if x.planned_start is not None and x.planned_end is not None)
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
    return PolicyResultV3(tuple(sorted(candidates, key=lambda x: (
        x.span.start, x.span.end, "" if x.expectation is None else x.expectation.id.value,
    ))), SkipCounts(**skips), blocks)
