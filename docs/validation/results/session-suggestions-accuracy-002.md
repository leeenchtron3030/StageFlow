# Session Suggestions - Accuracy Run 002 (policy v1 vs v2)

## Status and authority boundary

**ACCEPTANCE NOT MET BEYOND ±5 MIN OF DRIFT.**

- Policy `boundary-suggestion` v2 (ED-0105, merged at `main` `6a3b8a4`) meets the
  zero-drift target: recall 0.93 and median start / end errors of 14 s / 18 s.
- At ±5 min it is borderline. Without cues, the worst seed has an end median of 66 s and
  recall of 0.89. With transcript cues, every seed is within 60 s.
- At ±10 and ±15 min it fails. Recall drops to 0.68–0.86, and the worst-seed medians
  reach minutes.
- v2 is better than v1 at every drift, but it does not reproduce the prototype's
  drift robustness from [accuracy check 001](session-suggestions-accuracy-001.md).
  The main cause is the ±20 min candidate cap, which the prototype did not have (see
  Diagnosis).

This is the owner acceptance step for ED-0105. It is not the Phase 5 qualification run,
nor evidence of Event readiness. It covers a single event, stage and host. The real-event
media, ground truth, transcripts and scripts stay outside the repository. Only anonymous
statistics are recorded.

## Setup

- **Corpus and ground truth:** the same as check 001. 112 main-stage recorder blocks over
  three days, and the editor's in and out points for 28 talks on the unqualified
  recorder clock. The segmentation cached for check 001 was reused.
- **Ground-truth caveat:** two talks on day 2 have identical in and out points in the
  decoded edit. With one-to-one matching, recall cannot exceed 27/28 (0.96).
- **Policies:** the merged `policy.evaluate` (v1) and `policy_v2.evaluate` (v2), with no
  modifications.
- **Evaluator:** the merged ED-0105 `evaluate_accuracy`, run over all three days as one
  chronological sequence (the days do not overlap). A match needs IoU of at least 0.5,
  and recall counts one-to-one matches. Error medians and 95th percentiles cover matched
  pairs only.
- **Transcript cues:**
  - The GPU transcripts of all 112 blocks were scanned for fixed phrase lists: 12 start
    phrases (for example "please welcome", "my name is") and 8 end phrases (for example
    "thank you very much", "any questions").
  - Word timestamps became `start_cues` and `end_cues` on each asset.
  - The lists are the untuned lists from the cue analysis.
- **Simulated schedule:**
  - As in check 001, planned edges are the true edges plus independent uniform drift of up
    to ±D per edge, for D = 0, 5, 10 and 15 min. Each planned talk lasts at least 120 s.
  - Five seeds per non-zero drift. Tables report the worst seed unless marked otherwise.
  - A correlated variant shifts each day's whole schedule by one offset in ±D, plus ±60 s
    of jitter per edge.

## Results

### Official evaluator (independent drift, worst of five seeds)

| Policy | Drift | Recall (min) | Median start / end error | 95th percentile start / end | Both edges ≤ 60 s |
| --- | --- | --- | --- | --- | --- |
| v1 | 0 | 0.86 | 14 s / 18 s | 717 s / 197 s | 15 |
| v1 | ±5 min | 0.82 | 47 s / 55 s | 717 s / 417 s | 7–9 |
| v1 | ±10 min | 0.75 | 234 s / 95 s | 797 s / 541 s | 4–6 |
| v1 | ±15 min | 0.61 | 215 s / 210 s | 797 s / 886 s | 1–4 |
| v2 | 0 | 0.93 | 14 s / 18 s | 280 s / 197 s | 16 |
| v2 | ±5 min | 0.89 | 30 s / 66 s | 421 s / 400 s | 7–11 |
| v2 | ±10 min | 0.82 | 133 s / 46 s | 713 s / 576 s | 4–9 |
| v2 | ±15 min | 0.68 | 47 s / 184 s | 765 s / 1213 s | 3–7 |
| v2 + cues | 0 | 0.93 | 14 s / 18 s | 280 s / 197 s | 16 |
| v2 + cues | ±5 min | 0.89 | 43 s / 47 s | 421 s / 400 s | 7–11 |
| v2 + cues | ±10 min | 0.86 | 47 s / 45 s | 713 s / 576 s | 6–9 |
| v2 + cues | ±15 min | 0.68 | 47 s / 184 s | 765 s / 1213 s | 4–7 |

- v2 returns fewer suggestions than v1: 34–38 against 41–50. The extra ones are
  unscheduled remainders.
- **Cues with v1:** they change strength labels only. v1's edge selection does not use
  cues, so its errors are identical.
- **Cues with v2:** they turn every `medium` suggestion into `strong`. They improve the
  ±5 and ±10 min medians, but do not change recall at ±15 min.

### Comparison with the prototype (per-talk errors, prototype drift seed)

Check 001 measured the prototype per talk: each talk's assigned interval, with errors
over all 28 talks. The same measure applied to the merged policies gives:

| Drift | v1 | v2 | v2 + cues | Prototype (re-run, reproduces check 001) |
| --- | --- | --- | --- | --- |
| 0 | 15 s / 24 s | 14 s / 24 s | 14 s / 24 s | 19 s / 30 s |
| ±5 min | 47 s / 64 s | 30 s / 47 s | 15 s / 45 s | 30 s / 45 s |
| ±10 min | 234 s / 220 s | 244 s / 160 s | 191 s / 104 s | 45 s / 47 s |
| ±15 min | 262 s / 216 s | 260 s / 190 s | 260 s / 190 s | 45 s / 47 s |

v2 has a suggestion linked to every one of the 28 talks at every drift, so recall
under check 001's definition is 28/28.

### Correlated drift (whole-day shift, worst of five seeds, official evaluator)

| Policy | 0 | ±5 min | ±10 min | ±15 min |
| --- | --- | --- | --- | --- |
| v1 | 0.86, 16 s / 30 s | 0.79, 30 s / 114 s | 0.61, 213 s / 420 s | 0.61, 73 s / 242 s |
| v2 | 0.93, 22 s / 25 s | 0.89, 47 s / 66 s | 0.75, 150 s / 143 s | 0.71, 133 s / 125 s |
| v2 + cues | 0.93, 19 s / 25 s | 0.89, 30 s / 66 s | 0.75, 150 s / 143 s | 0.75, 133 s / 66 s |

Cells show minimum recall, then the worst-seed median start / end error.

## Diagnosis

- **Candidate cap:**
  - v2 keeps v1's ±20 min candidate window (`edge_window_seconds` = 1200), as the plan
    specified. The prototype considered every changeover.
  - With the prototype drift seed, v2 used a schedule edge 11 times at ±10 min and 15
    times at ±15 min. The cause is that an earlier talk consumed the only in-window
    changeover.
  - An experiment in scratch code only, with the window widened and no repository change:

    | Window | ±10 min (per talk) | ±15 min (per talk) | ±15 min end median (official, worst seed) |
    | --- | --- | --- | --- |
    | 20 min (as built) | 244 s / 160 s | 260 s / 190 s | 184 s |
    | 40 min | — | — | 47 s |
    | 60 min | 122 s / 64 s | 45 s / 55 s | 63 s |
    | 12 h | 122 s / 64 s | 45 s / 64 s | 63 s |

  - Widening the window fixes the edge errors at ±15 min, but not recall. Recall
    stays at 0.68–0.71 for every window.
- **Planned order:**
  - The policy orders talks by planned start, as it must. The prototype kept the true
    order.
  - Independent ±10 min drift inverted 0–3 adjacent planned starts per run. At ±10 min
    on day 1, v2 found both true intervals of an inverted pair but assigned them to
    swapped expectations.
  - This is partly an artifact of the drift model: a 2.8 min talk followed by a 48 min
    talk.
- **Absolute plan distance:**
  - The alignment charges 1 point per 30 s of distance from the plan, against a strength
    cap of 30 points.
  - Under a uniform whole-day shift of 10 min or more, weaker in-talk freezes near the
    shifted plan outscore the true changeovers.
  - The alignment does not estimate a shared offset. That is why correlated drift, which
    is closer to how events run late, still fails at ±10 min.
- **Evidence ceiling (unchanged):** 21% of true edges have no freeze or gap within 30 s
  (check 001). Transcript cues help only where a changeover exists for them to support,
  because v2 uses cues as a bonus, not as edges.

## Interpretation

- **Measured:**
  - v2 meets the zero-drift target and improves recall over v1 (0.93 against 0.86).
  - With cues, it meets the ±5 min target.
  - It does not meet the ED-0105 criterion of 60 s or less and 90% recall at ±10 and
    ±15 min.
  - ED-0105 therefore stays **Approved**, not Completed, pending an owner decision.
- **Not a code defect:** the merged policy behaves as its plan specifies. The gap is
  between that specification and the prototype that motivated it.
- **Options for the owner:**
  - **A: accept v2 for close-to-real schedules and move on.** Record the ±10 and ±15 min
    limits. Operators confirm every suggestion anyway (ADR-0034), and ADR-0035 boundary
    markers give an evidence source that does not depend on the schedule.
  - **B: policy v3 with offset estimation.** Estimate a per-Stage (or rolling) schedule
    offset first, align against the shifted plan, and widen or remove the candidate cap.
    This needs a new version and a migration, because the `0023` constraints pin the v2
    constants.
  - **C: cues as edges.** Let strong transcript cues create candidate edges where no
    changeover exists. This addresses the 21% evidence ceiling. It is larger in scope,
    and the untuned phrase lists showed mid-talk false hits in check 001.
- **Limits:**
  - one event and one stage;
  - simulated drift, with no published schedule;
  - untuned cue lists;
  - an unqualified clock;
  - one duplicated ground-truth interval.
