# Session Suggestions - Qualification Run 001 (policy v3, corpus harness)

## Status and authority boundary

**TARGET NOT MET: 0 OF 3 EVENT DAYS PASS ON THE REAL PUBLISHED SCHEDULE. THE HARNESS
REPRODUCTION CHECK PASSES.**

- **Reproduction:** the merged ED-0114 harness reproduces the Run 003 zero-drift numbers
  exactly on the same corpus. That meets the remaining ED-0114 acceptance criterion.
- **Real published schedule:** with the Conference stage cue lists, policy
  `boundary-suggestion` v3 misses the ADR-0034 v1 target on every event day. The target
  is recall ≥ 0.90, median start and end errors ≤ 30 s, and no wrong-day suggestion.
  - **Day 1:** recall 1.00, but the start median is 30.4 s.
  - **Day 2:** recall 0.91, but the end median is 55 s.
  - **Day 3:** recall 0.50.
- **Wrong day:** there are **no wrong-day suggestions** in any cell of the matrix.
- **Simulated whole-day and two-part lateness:**
  - Day 1 passes every cell up to ±30 min.
  - Days 2 and 3 fail even at zero drift. Each day has one talk the policy misses or
    places badly, and on a day of 8–11 talks one talk moves the recall or a median past
    the target.
- **No tuning:** measurement did not change the policy, as the plan requires. The policy
  follow-up is named under Findings.

This is the Phase 5 qualification step (D4) for ADR-0034. It is not evidence of Event
readiness. It covers one event and one stage on a single host. The recorder clock is
unqualified, and the published schedule is the one captured before the event. The
real-event media, ground truth, transcripts, schedule, manifests and scripts stay outside
the repository. Only anonymous statistics are recorded.

## Setup

- **Code:** `main` `65cd54a`. The harness and CLI are from ED-0114, run unmodified, with
  policies v2 and v3.
- **Corpus:** the same as Runs 002 and 003 and Cue Run 001:
  - 112 main-stage recorder blocks over three days (46, 35 and 31 per day);
  - the cached segmentation;
  - the editor's in and out points for 28 talks (9, 11 and 8 per day).
  - Two day-2 talks share identical in and out points, so day 2 recall cannot exceed
    10/11 (0.91).
- **Schedule:**
  - **Published:** the event's pre-event agenda for the main stage, used as is. It has
    28 planned talks (10, 10 and 8 per day), so the planned and actual talk counts differ
    on days 1 and 2.
  - **Drift:** the harness drift models (whole-day, two-part, independent) at D = 0, 5,
    10, 15 and 30 min, with seeds 1–5.
- **Cues:** word timestamps from the GPU transcripts, matched against the lists
  composed from the Conference stage profile (32 start and 32 end phrases), as in Cue
  Run 001. The result was 133 start cues and 115 end cues.
- **Manifests:** two, built outside the repository:
  - **Per-day:** one Stage entry per event day. This follows the owner decision of
    2026-09-30, so the ±12 h wrong-day window applies to each day. It is the
    qualification form.
  - **Pooled:** one Stage for all three days, as Run 003 evaluated. It is used only for
    the reproduction check and the comparison.
- **Target (harness):**
  - recall ≥ 0.90;
  - worst-seed median start and end errors ≤ 30 s;
  - wrong-day count 0, for each Stage (event day) and seed.
  - Precision is reported, with no threshold.

## Reproduction check (pooled)

The independent model at D = 0 involves no random draws, so it must equal Run 003 exactly.

| Policy | Run 003 | Harness | Match |
| --- | --- | --- | --- |
| v2 | 0.93, 14 s / 18 s | 0.93 (26/28), 14 s / 18 s, 16 within 60 s | Yes |
| v3 | 0.93, 14 s / 18 s | 0.93 (26/28), 14 s / 18 s, 16 within 60 s | Yes |
| v3 + cues | 0.93, 14 s / 18 s (Cue Run 001: 16 within 60 s) | 0.93 (26/28), 14 s / 18 s, 16 within 60 s | Yes |

- **Other cells:**
  - Whole-day lateness at D = 0 also matches Cue Run 001 (19 s / 24 s).
  - Cells with random draws do not repeat the historical draws. The harness uses its own
    documented RNG convention.

## Results: real published schedule (per-day Stages)

Each cell shows recall (matched/truth), then the median start / end error, then the
scheduled precision.

| Policy | Day 1 | Day 2 | Day 3 | Wrong-day | Target |
| --- | --- | --- | --- | --- | --- |
| v2 | 0.89 (8/9), 23 s / 11 s, 0.70 | 0.91 (10/11), 37 s / 55 s, 1.00 | 0.88 (7/8), 213 s / 143 s, 0.88 | 0 | Not met |
| v3 | 1.00 (9/9), 30 s / 8 s, 0.80 | 0.91 (10/11), 27 s / 55 s, 1.00 | 0.50 (4/8), 215 s / 22 s, 0.43 | 0 | Not met |
| v3 + cues | 1.00 (9/9), 30 s / 8 s, 0.80 | 0.91 (10/11), 27 s / 55 s, 1.00 | 0.50 (4/8), 215 s / 22 s, 0.43 | 0 | Not met |

- **Precision including unscheduled suggestions** (v3 + cues): 0.60, 1.00 and 0.44 by
  day.
  - Day 1 produces 5 unscheduled suggestions. The day has 10 planned talks but 9 actual
    ones. The run did not diagnose these suggestions further.
- **Pooled reference** (v3 + cues on the published schedule): recall 0.75 (21/28),
  30 s / 29 s.

## Results: simulated drift, v3 + cues (per-day Stages, worst of five seeds)

| Model | Drift | Day 1 | Day 2 | Day 3 |
| --- | --- | --- | --- | --- |
| Whole-day | 0 | **1.00, 16 s / 8 s** | 0.91, 25 s / 45 s | 0.88, 79 s / 30 s |
| Whole-day | ±5 min | **1.00, 16 s / 8 s** | 0.91, 23 s / 38 s | 0.88, 79 s / 30 s |
| Whole-day | ±10 min | **1.00, 16 s / 8 s** | 0.91, 23 s / 38 s | 0.88, 79 s / 46 s |
| Whole-day | ±15 min | **1.00, 16 s / 8 s** | 0.91, 26 s / 37 s | 0.88, 150 s / 36 s |
| Whole-day | ±30 min | **1.00, 16 s / 8 s** | 0.64, 26 s / 37 s | 0.88, 79 s / 30 s |
| Two-part | 0 | **1.00, 16 s / 8 s** | 0.91, 25 s / 40 s | 0.88, 79 s / 30 s |
| Two-part | ±5 min | **1.00, 16 s / 8 s** | 0.82, 23 s / 47 s | 0.88, 79 s / 30 s |
| Two-part | ±10 min | **1.00, 16 s / 8 s** | 0.82, 26 s / 47 s | 0.88, 79 s / 30 s |
| Two-part | ±15 min | **1.00, 16 s / 8 s** | 0.82, 25 s / 47 s | 0.75, 45 s / 30 s |
| Two-part | ±30 min | **1.00, 16 s / 8 s** | 0.82, 26 s / 47 s | 0.75, 79 s / 30 s |
| Independent | 0 | **1.00, 16 s / 8 s** | 0.91, 12 s / 37 s | 0.88, 11 s / 30 s |
| Independent | ±5 min | 0.89, 31 s / 14 s | 0.64, 29 s / 66 s | 0.38, 165 s / 161 s |
| Independent | ±10 min | 0.67, 161 s / 105 s | 0.73, 34 s / 164 s | 0.38, 115 s / 184 s |
| Independent | ±15 min | 0.56, 70 s / 96 s | 0.55, 34 s / 63 s | 0.38, 114 s / 179 s |
| Independent | ±30 min | 0.33, 281 s / 625 s | 0.27, 30 s / 263 s | 0.25, 398 s / 97 s |

- **Bold cells** meet the target.
- **Wrong-day:** 0 in every cell.

## Comparison with Run 003 (pooled, worst of five seeds, v3 + cues)

| Model | Drift | Run 003 | Harness draws |
| --- | --- | --- | --- |
| Whole-day | ±5 min | 0.93, 29 s / 29 s | 0.93, 29 s / 29 s |
| Whole-day | ±10 min | 0.93, 25 s / 30 s | 0.93, 29 s / 29 s |
| Whole-day | ±15 min | 0.93, 29 s / 29 s | 0.86, 26 s / 24 s |
| Whole-day | ±30 min | 0.89, 22 s / 30 s | 0.89, 22 s / 24 s |
| Two-part | ±15 min | 0.93, 29 s / 24 s | 0.89, 30 s / 25 s |
| Two-part | ±30 min | 0.82, 29 s / 29 s | 0.82, 22 s / 19 s |
| Independent | ±5 min | 0.89, 30 s / 41 s | 0.79, 36 s / 36 s |

- **Run 003's pass was partly seed-dependent.** Under different draws at the same
  magnitudes, the worst-seed recall falls by one to three talks in several cells:
  - whole-day ±15 min: 0.93 → 0.86;
  - independent ±5 min: 0.89 → 0.79.
- **The medians hold.**

## Findings

- **The real schedule error is per talk, not per day.** The published schedule and the
  ground truth compare as follows:
  - **Talk durations:** actual durations differ from planned by up to 25 min. One talk
    planned at 60 min ran 35; a 25 min slot ran 12. On days 1 and 2, the planned and
    actual talk counts also differ.
  - **Day 3**, the only day with equal counts: start lateness ranges from −2.8 to
    +18.1 min, inside a single schedule block. There is no single day or block offset.
  - This is the independent-drift regime. Run 003 already recorded v3 as weaker there
    than v2, as a planned limitation. The real schedule sits in that regime rather than
    in the whole-day lateness regime that v3 was designed for.
- **Day 3 on the real schedule:** v3 estimates one offset per block. Its lateness
  varies by about 10 min within the block, and it drops or misplaces 4 of 8 talks. v2
  has no block offset, and matches 7 of 8, but with medians of minutes.
- **A per-day target on small days is strict.** With 8–11 talks per day, one missed talk
  gives 0.88–0.89, and day 2's duplicated ground truth caps it at 0.91. Even at zero
  drift, days 2 and 3 fail on one talk each. The plan does not say whether the ADR target
  applies per event day or per event. The qualification uses per day, which is the
  stricter reading.
- **Cues change nothing on the real schedule.** v3 and v3 + cues give identical results.
  Cues refine edges near a found boundary; they cannot recover a talk that the offset
  misplaced.
- **Wrong-day safety holds.** No cell placed a suggestion outside its day's ±12 h
  window.

## Interpretation

- **Measured:**
  - The harness is correct and repeatable against Run 003.
  - Policy v3 does **not** meet the ADR-0034 v1 target on this event's real published
    schedule. The dominant cause is per-talk duration and lateness error, which the
    one-offset-per-block model cannot represent.
  - Under simulated whole-day lateness, v3 remains robust: day 1 passes every cell.
- **Policy follow-up (named; not started; needs owner prioritization):** a new policy
  version that handles per-talk lateness. Options to evaluate with this harness:
  - **Sequential re-anchoring:** estimate each talk's offset from the end of the talk
    before it, rather than one offset per block.
  - **Duration-tolerant alignment:** plan durations act as soft priors, not as fixed
    lengths.
  - **Producer workflow:** rely on the producer confirming or correcting the first talk
    of each block, with the override made able to split blocks (the Run 003 follow-up).
  - Each option is a new policy version under the existing versioning. None changes
    current behavior.
- **Owner decision needed:**
  - whether the ADR target is judged per event day or per event;
  - whether the policy follow-up comes before or after ED-0115.
  - ED-0115 (live replay) does not depend on either answer.
- **Limits:**
  - one event and one stage;
  - one published schedule;
  - an unqualified recorder clock;
  - a duplicated ground-truth interval on day 2;
  - the real wrong-clock and recording-gap cases on other stages are not segmented. The
    synthetic scenario suite covers them.
