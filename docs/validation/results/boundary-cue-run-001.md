# Boundary cue presets - Cue Run 001 (composed Conference-stage lists)

## Status and authority boundary

**PASSED ON THE TARGETS. THE PER-CELL COMPARISON IS MIXED, AND EVERY DIFFERENCE IS
SMALL.**

- Policy v3 with cue lists composed from the *Conference stage* profile (ED-0107,
  catalog v1) meets every approved Run 003 target, as the untuned lists did.
- Measured cell by cell against the untuned Run 002 lists, the composed lists:
  - are better or equal in 12 of 15 cells;
  - are worse in 3 cells, by at most 3.3 s of median error, or one talk of recall in a
    cell that is not a target.
- **Criterion:** the plan requires the composed lists to be "no worse … on any reported
  target".
  - Read against the Run 003 targets, it is **met**.
  - Read as a strict cell-by-cell comparison, it is **not met in 3 cells** (listed
    below).

This is the owner acceptance step for ED-0107. It covers a single event, stage and host,
with simulated schedules. Only anonymous statistics are recorded.

## Setup

- **Corpus, ground truth, transcripts, evaluator, drift models and seeds:** the same as
  [Accuracy Run 003](session-suggestions-accuracy-003.md). Five seeds; the worst seed is
  reported.
- **Policy:** the merged `policy_v3.evaluate` with cues.
- **Untuned lists:** the Run 002 phrase lists, 12 start and 8 end phrases.
- **Composed lists:** the merged `compose()` on the *Conference stage* profile with its
  defaults. Its 4 groups give 32 start and 32 end phrases, including changeover phrases
  in both lists, and no segment phrases. No custom phrases were added and nothing was
  tuned to the corpus.

## Results

Cells show minimum recall, then the worst-seed median start / end error. Where the two
lists differ, the untuned result comes first.

| Model | Drift | Untuned | Composed | Change |
| --- | --- | --- | --- | --- |
| Whole-day | 0 | 0.93, 19 s / 24 s | 0.93, 19 s / 24 s | equal |
| Whole-day | ±5 min | 0.93, 29 s / 29 s | 0.93, 22 s / 29 s | start −7 s |
| Whole-day | ±10 min | 0.93, 25 s / 30 s | 0.93, 25 s / 24 s | end −6 s |
| Whole-day | ±15 min | 0.93, 29 s / 29 s | 0.93, 29 s / 30 s | end +0.5 s |
| Whole-day | ±30 min | 0.89, 22 s / 30 s | 0.89, 22 s / 29 s | end −1 s |
| Two-part | 0 | 0.93, 25 s / 24 s | 0.93, 25 s / 24 s | equal |
| Two-part | ±5 min | 0.93, 29 s / 21 s | 0.93, 29 s / 24 s | end +3.3 s |
| Two-part | ±10 min | 0.93, 24 s / 24 s | 0.93, 24 s / 24 s | equal; both edges ≤ 60 s: 13 → 14 |
| Two-part | ±15 min | 0.93, 29 s / 24 s | 0.93, 29 s / 24 s | equal |
| Two-part | ±30 min | 0.82, 29 s / 29 s | 0.79, 29 s / 25 s | recall −0.04 (one talk), end −4 s |
| Independent | 0 | 0.93, 14 s / 18 s | 0.93, 14 s / 18 s | equal |
| Independent | ±5 min | 0.89, 30 s / 41 s | 0.89, 30 s / 41 s | equal |
| Independent | ±10 min | 0.57, 47 s / 66 s | 0.57, 30 s / 66 s | start −17 s |
| Independent | ±15 min | 0.50, 112 s / 115 s | 0.54, 112 s / 56 s | recall +0.04, end −59 s |
| Independent | ±30 min | 0.39, 213 s / 151 s | 0.39, 202 s / 151 s | start −11 s |

**Run 003 targets with the composed lists:**

- zero drift: 0.93, 14 s / 18 s;
- whole-day lateness up to ±15 min: 0.93, 30 s or less;
- whole-day lateness of ±30 min: 0.89, 22 s / 29 s;
- two-part lateness up to ±15 min: 0.93, 29 s or less;
- independent drift of ±5 min: 0.89, 30 s / 41 s.

All are met.

## Interpretation

- **Measured:**
  - The default *Conference stage* composition is a drop-in replacement for hand-picked
    lists. It meets every target, and helps most where the schedule is worst: end error
    under independent ±15 min drift halves.
  - The 3 worse cells are within noise for a single corpus:
    - +0.5 s and +3.3 s of median end error, both inside targets;
    - one talk of recall in the untargeted two-part ±30 min case.
- **Why cues matter little under v3:** cues are a bonus on changeover edges. They cannot
  create edges, so a richer list mostly changes tie-breaks. Larger gains need cue edges
  (policy v4, Phase 2d-2).
- **Limits:**
  - one English-language conference, one stage;
  - simulated schedules;
  - only the Conference profile tested (no corpus exists for the other profiles);
  - the catalog's measured precision comes from this same corpus, so this run is not an
    independent test of the phrase choice.
