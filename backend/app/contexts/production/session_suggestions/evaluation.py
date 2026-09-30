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


def match_intervals(
    suggestions: Sequence[Span | Candidate | SessionSuggestion], ground_truth: Sequence[Span],
) -> tuple[tuple[int, int], ...]:
    """Return immutable (truth index, suggestion index) pairs in chronological order.

    Indices refer to the original input sequences. Match one Stage at IoU >= 0.5,
    maximizing one-to-one count then minimizing total absolute edge error. Exact ties
    retain earlier intervals; identical spans retain their input order.
    O(G*S) time and space for G truth and S suggested intervals.
    """
    if len(suggestions) > MAX_INPUTS or len(ground_truth) > MAX_INPUTS:
        raise ValueError("evaluation_input_limit")
    spans = tuple(s if isinstance(s, Span) else s.span if isinstance(s, Candidate)
                  else s.candidate.span for s in suggestions)
    prediction_order = sorted(range(len(spans)), key=lambda i: (spans[i].start, spans[i].end))
    truth_order = sorted(range(len(ground_truth)),
                         key=lambda i: (ground_truth[i].start, ground_truth[i].end))
    predicted = [spans[i] for i in prediction_order]
    truth = [ground_truth[i] for i in truth_order]
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
    pairs: list[tuple[int, int]] = []
    i, j = len(truth), len(predicted)
    while i and j:
        action = paths[i - 1][j]
        if action == 3:
            pairs.append((truth_order[i - 1], prediction_order[j - 1]))
            i, j = i - 1, j - 1
        elif action == 2:
            j -= 1
        else:
            i -= 1
    return tuple(reversed(pairs))


def evaluate_accuracy(
    suggestions: Sequence[Span | Candidate | SessionSuggestion], ground_truth: Sequence[Span],
    *, planned_span: Span | None = None,
) -> AccuracyMetrics:
    """Evaluate one Stage using match_intervals' chronological one-to-one matching.

    Recall is matched/truth (0 for no truth). Errors describe matched pairs only;
    p95 uses nearest rank (ceil(0.95*n)). Within-60 requires BOTH edges <=60 seconds.
    Legacy metrics match all suggestions. Precision separately matches scheduled
    suggestions (bare Spans count as scheduled); inclusive precision uses all matches.
    Wrong-day counts either edge outside the planned span expanded by 12 hours,
    inclusive at the margin. None means no planned span was supplied, not a pass.
    """
    pairs = match_intervals(suggestions, ground_truth)
    predicted = tuple(s if isinstance(s, Span) else s.span if isinstance(s, Candidate)
                      else s.candidate.span for s in suggestions)
    truth = ground_truth
    starts = [abs((predicted[j].start - truth[i].start).total_seconds()) for i, j in pairs]
    ends = [abs((predicted[j].end - truth[i].end).total_seconds()) for i, j in pairs]
    matched_count = len(pairs)
    scheduled = tuple(s for s in suggestions if isinstance(s, Span) or (
        s if isinstance(s, Candidate) else s.candidate).expectation is not None)
    unscheduled_count = len(suggestions) - len(scheduled)
    scheduled_matches = (len(match_intervals(scheduled, ground_truth))
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
