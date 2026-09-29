# Session Suggestions - Accuracy Run 003 (policy v3, schedule offset)

## Status and authority boundary

**PASSED. EVERY NUMERIC TARGET IS MET, AND THE OVERRIDE CRITERION HAS ONE EXPLAINED
EXCEPTION.**

- Policy `boundary-suggestion` v3 (ED-0106, merged at `main` `1e54ff4`) meets every
  approved Run 003 target.
  - **Whole-day lateness:** recall 0.93 and worst-seed medians of 29 s or less up to
    ±15 min. At ±30 min, recall is 0.89 and medians are 30 s or less.
  - **Two-part lateness:** recall 0.93 and medians of 36 s or less up to ±15 min.
  - **Independent drift of ±5 min:** recall 0.89, and medians of 37 s / 41 s.
- **Override criterion:** entering the true lateness as a producer override reproduces
  the matched zero-offset results within 1.1 s in 7 of 8 cases.
  - The exception is two-part lateness at ±30 min, which misses by 7 s, with recall
    0.04 lower in one seed.
  - Cause: on one simulated day, the planned lunch break shrank to 15 min. The schedule
    then formed a single block, and an override entry cannot split a block (see
    Findings).
- **Known limitation, as planned:** under independent per-edge drift of ±10 min or more,
  v3 is worse than v2.

This is the owner acceptance step for ED-0106. It is not the Phase 5 qualification run,
nor evidence of Event readiness. It covers a single event, stage and host, with
simulated schedules. The real-event media, ground truth, transcripts and scripts stay
outside the repository. Only anonymous statistics are recorded.

## Setup

- **Corpus, ground truth, segmentation, transcripts and cue lists:** the same as
  [Run 002](session-suggestions-accuracy-002.md). Two day-2 talks share identical in and
  out points, so recall cannot exceed 0.96.
- **Policies:** the merged `policy_v2.evaluate` and `policy_v3.evaluate`, unmodified.
- **Evaluator:** the merged ED-0105 `evaluate_accuracy` (IoU ≥ 0.5, one-to-one matching),
  run over all three days as one chronological sequence.
- **Simulated schedules:** five seeds per drift, and the worst seed is reported.
  - **Whole-day:** one offset per day in ±D, plus ±60 s of jitter per edge.
  - **Two-part:** a separate offset after the day's largest planned break, plus the same
    jitter.
  - **Independent:** Run 002's drift model, up to ±D per edge.
  - D = 0, 5, 10, 15 and 30 min.
- **Override check:**
  - The whole-day case uses one entry covering the day. The two-part case adds a second
    entry at the first post-break talk.
  - Each entry carries the negated true offset, rounded to whole seconds.
  - Each result is compared with the same seeds and jitter, the offsets removed, and a
    producer override of 0.

## Results (worst of five seeds)

Cells show minimum recall, then the worst-seed median start / end error. The
override column appears only for the whole-day and two-part models.

| Model | Drift | v2 | v3 | v3 + cues | v3 + true-offset override |
| --- | --- | --- | --- | --- | --- |
| Whole-day | 0 | 0.93, 22 s / 29 s | 0.93, 22 s / 29 s | 0.93, 19 s / 24 s | 0.93, 22 s / 29 s |
| Whole-day | ±5 min | 0.89, 47 s / 66 s | 0.93, 29 s / 33 s | 0.93, 29 s / 29 s | 0.93, 22 s / 29 s |
| Whole-day | ±10 min | 0.75, 150 s / 143 s | 0.93, 25 s / 30 s | 0.93, 25 s / 30 s | 0.93, 29 s / 24 s |
| Whole-day | ±15 min | 0.71, 148 s / 125 s | 0.93, 29 s / 29 s | 0.93, 29 s / 29 s | 0.93, 22 s / 19 s |
| Whole-day | ±30 min | 0.57, 280 s / 64 s | 0.89, 22 s / 30 s | 0.89, 22 s / 30 s | 0.93, 22 s / 30 s |
| Two-part | 0 | 0.93, 25 s / 24 s | 0.93, 25 s / 24 s | 0.93, 25 s / 24 s | 0.93, 25 s / 24 s |
| Two-part | ±5 min | 0.86, 30 s / 44 s | 0.93, 29 s / 24 s | 0.93, 29 s / 21 s | 0.93, 22 s / 20 s |
| Two-part | ±10 min | 0.79, 99 s / 104 s | 0.93, 25 s / 36 s | 0.93, 24 s / 24 s | 0.93, 21 s / 29 s |
| Two-part | ±15 min | 0.68, 213 s / 182 s | 0.93, 29 s / 33 s | 0.93, 29 s / 24 s | 0.93, 20 s / 25 s |
| Two-part | ±30 min | 0.54, 79 s / 66 s | 0.79, 29 s / 33 s | 0.82, 29 s / 29 s | 0.89, 26 s / 24 s |
| Independent | 0 | 0.93, 14 s / 18 s | 0.93, 14 s / 18 s | 0.93, 14 s / 18 s | — |
| Independent | ±5 min | 0.89, 30 s / 56 s | 0.89, 37 s / 41 s | 0.89, 30 s / 41 s | — |
| Independent | ±10 min | 0.86, 182 s / 143 s | 0.57, 47 s / 66 s | 0.57, 47 s / 66 s | — |
| Independent | ±15 min | 0.57, 121 s / 79 s | 0.50, 178 s / 66 s | 0.50, 112 s / 115 s | — |
| Independent | ±30 min | 0.39, 130 s / 464 s | 0.39, 213 s / 151 s | 0.39, 213 s / 151 s | — |

- **Offset sources:**
  - At zero drift, every v3 suggestion had source `none`. The gate held with an exact
    schedule, and the results equal v2's.
  - Under whole-day lateness of ±10 min or more, 72–97% of linked suggestions used an
    `estimated` offset.
- **Suggestions:** v3 returned 33–36 suggestions on the whole-day and two-part models,
  against v2's 34–39.
- **95th percentile:** the worst-seed start / end 95th percentile under whole-day
  lateness fell from v2's 572–1,364 s to v3's 280–421 s.

## Target check

| Approved target | Result | Met |
| --- | --- | --- |
| Zero drift (independent): recall ≥ 0.90, medians ≤ 30 s | 0.93, 14 s / 18 s | Yes |
| Whole-day lateness up to ±15 min: recall ≥ 0.90, medians ≤ 45 s | 0.93, ≤ 29 s / 33 s | Yes |
| Whole-day lateness of ±30 min: recall ≥ 0.85, medians ≤ 45 s | 0.89, 22 s / 30 s | Yes |
| Two-part lateness up to ±15 min: recall ≥ 0.90, medians ≤ 45 s | 0.93, ≤ 29 s / 36 s | Yes |
| Independent drift of ±5 min: recall ≥ 0.85, medians ≤ 60 s | 0.89, 37 s / 41 s | Yes |
| Independent drift of ±10 and ±15 min: reported only | See the table | — |
| True-offset override reproduces the zero-offset results within 5 s | ≤ 1.1 s in 7 of 8 cases; two-part ±30 min: 7.0 s and recall −0.04 | Not met as written, in 1 case (explained) |

## Findings

- **An override entry cannot split a schedule block.**
  - Blocks come only from planned breaks of 20 min or more. A block takes the latest
    entry that is effective at or before its first planned start.
  - When a printed break is shorter than 20 min, an entry placed after that break is
    ignored for the rest of that block. In this run, the lunch gap shrank to 15 min under
    ±30 min drift.
  - A producer who types "from 13:00, +20 min" expects it to apply from 13:00. A follow-up
    should consider making override entries block boundaries too. That changes the policy,
    so it needs a new version, and it is not needed for acceptance.
- **Cues:** they help modestly under v3. The worst-seed end medians improve by up to
  12 s, and two-part recall at ±30 min rises from 0.79 to 0.82. Cues cannot fix a wrong
  offset.
- **Independent drift:** as recorded in the plan, one offset per block cannot fit
  schedules whose talk **durations** are wrong by 20–30 min. A producer override of 0
  gives v2's behaviour.

## Interpretation

- **Measured:**
  - v3 meets every approved numeric target.
  - It removes the lateness failure mode that Run 002 found, and it matches v2 exactly
    at zero drift.
  - The producer override does what it should wherever its entry starts a block.
- **Next:** ED-0106 is Completed. The candidates, for owner prioritization, are:
  - the override-splits-blocks follow-up above;
  - Phase 2d-1 (phrase presets);
  - Phases 3–5;
  - the ADR-0035 marker plans.
- **Limits:**
  - one event and one stage;
  - simulated schedules, with no published schedule;
  - untuned cue lists;
  - an unqualified clock;
  - one duplicated ground-truth interval.
