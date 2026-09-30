"""Anonymous interval evaluation, independent of policy, storage and file IO."""
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from math import ceil
from statistics import median

from .contracts import MAX_INPUTS, Candidate, SessionSuggestion, Span


@dataclass(frozen=True, slots=True)
class AccuracyMetrics:
    truth_count: int
    suggestion_count: int
    matched_count: int
    recall: float
    median_start_error_seconds: float | None
    p95_start_error_seconds: float | None
    median_end_error_seconds: float | None
    p95_end_error_seconds: float | None
    count_within_60_seconds: int
    precision: float
    unscheduled_count: int
    precision_including_unscheduled: float
    wrong_day_count: int | None


def evaluate_accuracy(
    suggestions: Sequence[Span | Candidate | SessionSuggestion], ground_truth: Sequence[Span],
    *, planned_span: Span | None = None,
) -> AccuracyMetrics:
    """Match one Stage's intervals in chronological order at IoU >= 0.5.

    Maximize one-to-one match count, then minimize total absolute edge error;
    exact ties prefer earlier intervals. Recall is matched/truth (0 for no truth).
    Errors describe matched pairs only; p95 uses nearest rank (ceil(0.95*n)).
    Within-60 requires BOTH edges within 60 seconds, inclusive.
    Legacy metrics still match all suggestions. Precision separately matches scheduled
    suggestions (bare Spans count as scheduled); inclusive precision uses all matches.
    Wrong-day counts either edge outside the planned span expanded by 12 hours,
    inclusive at the margin. None means no planned span was supplied, not a pass.
    O(G*S) time and space for G truth and S suggested intervals.
    """
    if len(suggestions) > MAX_INPUTS or len(ground_truth) > MAX_INPUTS:
        raise ValueError("evaluation_input_limit")
    predicted = sorted((s if isinstance(s, Span) else s.span if isinstance(s, Candidate)
                        else s.candidate.span for s in suggestions), key=lambda s: (s.start, s.end))
    truth = sorted(ground_truth, key=lambda s: (s.start, s.end))
    # Rolling objective rows plus byte-sized backpointers. No path copying.
    prior = [(0, 0)] * (len(predicted) + 1)
    paths: list[bytearray] = []
    for target in truth:
        row = [(0, 0)]
        path = bytearray(len(predicted) + 1)
        for j, candidate in enumerate(predicted, 1):
            best, action = prior[j], 1
            if row[j - 1] >= best:
                best, action = row[j - 1], 2
            intersection = max(target.start, candidate.start), min(target.end, candidate.end)
            overlap = max(0, (intersection[1] - intersection[0]) // _MICROSECOND)
            union = ((target.end - target.start) + (candidate.end - candidate.start))
            union_us = union // _MICROSECOND - overlap
            if 2 * overlap >= union_us:
                error = (abs(candidate.start - target.start)
                         + abs(candidate.end - target.end)) // _MICROSECOND
                matched = prior[j - 1][0] + 1, prior[j - 1][1] - error
                if matched > best:
                    best, action = matched, 3
            row.append(best)
            path[j] = action
        prior = row
        paths.append(path)
    starts: list[float] = []
    ends: list[float] = []
    i, j = len(truth), len(predicted)
    while i and j:
        action = paths[i - 1][j]
        if action == 3:
            starts.append(abs((predicted[j - 1].start - truth[i - 1].start).total_seconds()))
            ends.append(abs((predicted[j - 1].end - truth[i - 1].end).total_seconds()))
            i, j = i - 1, j - 1
        elif action == 2:
            j -= 1
        else:
            i -= 1
    matched_count = len(starts)
    scheduled = tuple(s for s in suggestions if isinstance(s, Span) or (
        s if isinstance(s, Candidate) else s.candidate).expectation is not None)
    unscheduled_count = len(suggestions) - len(scheduled)
    scheduled_matches = (evaluate_accuracy(scheduled, ground_truth).matched_count
                         if unscheduled_count else matched_count)
    margin = timedelta(hours=12)
    wrong_day_count = None if planned_span is None else sum(
        s.start - planned_span.start < -margin or s.end - planned_span.end > margin
        for s in predicted)

    def p95(values: list[float]) -> float | None:
        return sorted(values)[ceil(0.95 * len(values)) - 1] if values else None

    return AccuracyMetrics(
        len(truth), len(predicted), matched_count,
        matched_count / len(truth) if truth else 0.0,
        float(median(starts)) if starts else None, p95(starts),
        float(median(ends)) if ends else None, p95(ends),
        sum(a <= 60 and b <= 60 for a, b in zip(starts, ends, strict=True)),
        scheduled_matches / len(scheduled) if scheduled else 0.0,
        unscheduled_count,
        matched_count / len(predicted) if predicted else 0.0,
        wrong_day_count,
    )

_MICROSECOND = timedelta(microseconds=1)
