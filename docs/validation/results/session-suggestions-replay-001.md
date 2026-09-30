# Session Suggestions - Live Replay Run 001 (synthetic day)

## Status and authority boundary

**COMPLETED. THE REPLAY RAN END TO END AND THE REPORT WAS RECORDED.**

- **Pipeline:** the ED-0115 replay tool drove the normal pipeline on a disposable review
  Event without failure: discovery, the timing and segmentation workers, and periodic
  suggestion runs.
  - All 24 blocks were registered and settled, over 6 suggestion runs.
  - The final run found all 5 talks exactly: recall 1.00, with a median start and end
    error of 0 s.
- **Time to first suggestion and stability:** reported below. Both are driven mostly by
  the run cadence and the pipeline lag at ×10 pace.

This is the owner check for ED-0115, and it meets the ED-0115 acceptance criterion in
the plan. It is **not** an accuracy qualification, since the content is a clean synthetic
day. It is not evidence of Event readiness. It covers a single host, a demo database,
generic synthetic media, and a schedule printed 8 min early. No media, configuration or
raw output is committed; only the sanitized report values below are.

## Setup

- **Code:** the ED-0115 branch, as merged in PR #172, with policy v3.
- **Media:** a generic synthetic stage day. It has 24 blocks of 5 min (the last one
  shorter), 6,990 s in total, containing 5 talks of 14–25 min between silent cards. This
  is the day generated for the ED-0110 review.
- **Schedule:** the 5 talks, printed 8 min earlier than they ran.
- **Truth:** the generator's own talk intervals.
- **Review Event:** a fresh disposable Event in the demo database, with one Stage and an
  empty watched folder. It was bootstrapped and its program synced with the normal demo
  CLI. The backend's automatic discovery runs every 5 s.
- **Replay:**
  - pace ×10;
  - a suggestion run every 4 blocks, plus a final run;
  - block durations from ffprobe;
  - a 900 s timeout for each phase.

## Results

**Runs**

`Media s` is the elapsed wall time × 10, so it includes pipeline lag.

| Run | Blocks copied | Media s | Suggestions | `no_coverage` skips |
| --- | --- | --- | --- | --- |
| 1 | 4 | 1,446 | 1 | 4 |
| 2 | 8 | 2,817 | 2 | 3 |
| 3 | 12 | 4,347 | 4 | 1 |
| 4 | 16 | 6,081 | 5 | 1 |
| 5 | 20 | 8,069 | 6 | 0 |
| 6 (final) | 24 | 10,260 | 5 | 0 |

- **Other skips:** every other skip counter was 0 in every run.
- **Elapsed time:** the replay took 1,026 s of wall time. At ×10 pace alone it would take
  699 s; the pipeline added about 47%.

**Talks**

| Talk | Time to first suggestion (media s) | Edge changes > 1 s | Largest edge move (s) |
| --- | --- | --- | --- |
| 1 | 0 | 1 | 360 |
| 2 | 57 | 1 | 360 |
| 3 | 1,671 | 0 | 0 |
| 4 | 591 | 1 | 150 |
| 5 | 1,199 | 1 | 330 |

- **Final accuracy:** 5 truth talks, 5 suggestions, 5 matched. Recall is 1.00, and the
  median start and end errors are 0 s.

## Findings

- **The cadence dominates latency.** Runs came every 4 blocks, which is 20 min of media
  plus lag. So a talk waits for the next run after its evidence arrives. Talk 1 matched
  on the first run, while it was still in progress, so its latency was clamped to 0.
  Talk 3 was first matched only on run 4, about 28 min after it ended. In live use,
  `--run-every 1` would show the latency the policy alone adds.
- **Early suggestions move once.** Four talks matched first with an edge up to 6 min
  off, while coverage was still partial. The next run corrected them, and nothing moved
  after that.
  - This is expected with partial coverage.
  - For the producer, an early suggestion on a talk still in progress is provisional.
    The UI already shows suggestions as proposals and never confirms them.
- **The pipeline kept up.** Every block registered and settled within its bounded
  phase. Lag grew from about 0 to 3,270 media s, and the tool delivered overdue blocks
  as soon as each cycle ended, as designed.
- **One extra suggestion before the final run.** Run 5 had 6 suggestions and the final
  run had 5, all of them matched. The report does not show why the sixth suggestion was
  not repeated in the final run.

## Interpretation

- **Measured:** the live pipeline produces the correct final suggestions on a clean day.
  Early suggestions are provisional, and they settle after one correction.
- **Next:** the policy follow-up from Qualification Run 001, a version that handles
  per-talk lateness, should be measured with this tool at `--run-every 1` on a synthetic
  day built from the real schedule's error pattern, as well as with the harness.
- **Limits:**
  - synthetic content with clean cards and tones;
  - one schedule shape;
  - ×10 pace on one host;
  - latency includes pipeline lag by definition.
