# Session Suggestions - early accuracy check 001 (policy v1)

## Status and authority boundary

**TARGET MET ONLY WITH AN EXACT SCHEDULE.**

- Policy `boundary-suggestion` v1 suggested 27–28 of 28 main-stage talks at every tested
  schedule drift, which meets the recall target.
- Median start and end errors were **15 s and 24 s with an exact schedule**, which meets
  the ADR-0034 target of 30 s or less. At ±5 min drift they grow to 47 s and 66 s, and
  beyond that to minutes.
- The dominant failure is snapping to long freezes **inside talks** (static slides or
  demos), which are more common than real changeovers.

This is an early, owner-requested check before Phase 3. It is not the Phase 5
qualification run, nor evidence of Event readiness. It is a single event, stage and
host. The real-event media, the decoded ground truth and the scripts stay outside the
repository. Only anonymous statistics are recorded: no names, filenames, paths or event
branding.

## Setup

- **Corpus:** three days of main-stage recorder blocks (112 ten-minute blocks, about
  19 hours). The ground truth is the editor's exact in and out points for 28 talks, on
  the recorder clock (unqualified).
- **Segmentation:**
  - The production `FFmpegSegmentationAdapter` (profile v1) ran on every block, using the
    operator-installed LGPL FFmpeg.
  - The first pass ran 6 blocks in parallel from an external drive. 6 high-bitrate blocks
    (30–64 Mbit/s) hit the adapter timeout.
  - Run alone, the same blocks finished in about 46 s each. The timeouts came from
    parallel I/O contention, not from the adapter or the files.
- **Policy:** the merged `evaluate()` from `session_suggestions/policy.py` at `main`
  `410339a`, fed real timing and segmentation inputs.
- **Program Expectations:** no published schedule was available. Planned times were the
  ground truth shifted by a deterministic, uniformly random drift of up to ±D per edge,
  for D = 0, 5, 10 and 15 min.
- **Transcripts:** none were available for the corpus, so cue support was not exercised.

## Results

### Policy v1 as merged

| Drift | Talks suggested | Median start / end error | 95th percentile start / end | Both edges ≤ 30 s |
| --- | --- | --- | --- | --- |
| 0 | 28/28 | **15 s / 24 s** | 1062 s / 890 s | 10/28 |
| ±5 min | 27/28 | 47 s / 66 s | 797 s / 430 s | 6/27 |
| ±10 min | 28/28 | 124 s / 188 s | 1062 s / 938 s | 3/28 |
| ±15 min | 28/28 | 328 s / 187 s | 1238 s / 818 s | 4/28 |

- At drift 0, 27 suggestions were `strong` and 1 was `medium`. Edges came from freezes
  (53), recording gaps (2) and coverage (1).
- The clock-plausibility and coverage skip counts were all 0, as expected for a
  single-stage corpus with a correct clock.
- **Content only (no schedule):** 11 of 28 talks were detected with IoU ≥ 0.5, from 44
  unscheduled suggestions.

### What separates real changeovers from in-talk freezes

Merged freezes of at least 30 s, compared with the ground truth:

| Class | Count | Median length (10th–90th pct) | Median silent share (90th pct) |
| --- | --- | --- | --- |
| At a true boundary (within 60 s) | 43 | **284 s** (59–779 s) | 0.18 (0.79) |
| Inside a talk | 72 | **56 s** (31–184 s) | **0.00** (0.03) |
| Between talks, not at an edge | 24 | 49 s (35–110 s) | 0.00 (0.05) |

In-talk freezes outnumber real changeovers. They are shorter and almost never silent.

### Threshold and selection experiments

These were run outside the repository and are not implemented.

- **Constants only, same "nearest to plan" rule:** the best combination was a changeover
  of at least 60 s, a merge gap of 15 s or less, and a ±10 min window.
  - drift 0: median errors 12 s / 18 s, 17 of 28 talks with both edges within 60 s;
  - ±5 min: 30 s / 44 s, 11 of 28;
  - ±10 min: 47 s / 76 s.
- **Selection rule:** choosing the *strongest* changeover in the window, weighted by
  length and silence and discounted by distance from the plan, with a ±10 min window:
  - drift 0: 15 s / 24 s;
  - ±5 min: 29 s / 45 s;
  - ±10 min: 45 s / 42 s;
  - ±15 min: 176 s / 190 s.
- No per-talk rule held 30 s or better beyond ±5 min of drift.
- **Joint day alignment (prototype):** a deterministic dynamic program assigns each day's
  talks to changeovers in order, so a talk's end and the next talk's start can share a
  changeover. It scores changeover strength against distance from the plan. With a
  changeover of at least 60 s and 30 s of distance per strength point:

  | Drift | Median start / end error | Talks with both edges ≤ 60 s | 95th percentile of the worse edge |
  | --- | --- | --- | --- |
  | 0 | 19 s / 30 s | 13/28 | 927 s |
  | ±5 min | 30 s / 45 s | 10/28 | 927 s |
  | ±10 min | 45 s / 47 s | 9/28 | 927 s |
  | ±15 min | 45 s / 47 s | 9/28 | 927 s |

  Accuracy holds as drift grows: at ±15 min the median is about 45 s, where per-edge
  rules reach 176–349 s. Accuracy with an exact schedule does not improve.
- **Ceiling of the freeze and gap evidence:** of the 56 true talk edges, only 35 have any
  freeze or gap edge within 30 s, and 44 within 60 s. The median distance is 15 s,
  whatever the minimum changeover length (4–60 s). About 21% of real boundaries have no
  nearby freeze or recording gap, so content changeovers alone cannot exceed about 79% of
  edges within 60 s.

## Interpretation

- **Measured:**
  - Recall meets the target.
  - Accuracy meets it only when the schedule is close to reality.
  - Policy v1's 30 s changeover minimum and "nearest edge" rule are too permissive,
    because in-talk freezes are frequent.
- **Next step (owner decision, 2026-09-29):** policy v2, with joint day alignment and
  strength-weighted changeovers of at least 60 s. The prototype shows it is robust to
  drift.
- **Also needed:**
  - **Transcript cues:** they are the only evidence that can lift the roughly 79%
    ceiling, because the missing edges fall where no freeze or gap exists. Transcribing
    the corpus would add introduction, thank-you and first-word signals, which were not
    exercised here.
  - **Real schedule drift:** the event's published schedule would replace simulated
    drift with the actual gap between planned and actual times.
- **Limits:** one event and one stage, simulated drift, no transcripts, and an
  unqualified clock.
