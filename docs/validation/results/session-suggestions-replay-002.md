# Session Suggestions - Live Replay Run 002 (real day morning, transcription in the chain)

## Status and authority boundary

**COMPLETED, ON THE THIRD ATTEMPT. D5 IS NOT MET AS WRITTEN. THE CAUSE IS v5'S END EDGES, NOT
TRANSCRIPT LATENESS.**

- **Chain.** The ED-0121 replay drove the full live chain with no failure on one real event day's
  morning, at 1×:
  - growing-file arrival;
  - discovery;
  - timing, segmentation and **transcription**;
  - a suggestion run after every block.
- **Totals:**
  - 19 of 19 blocks registered and settled, over 19 runs;
  - 0 transcription failures, 0 partial transcripts;
  - every transcript was available about 2 minutes after its block closed.
- **Live policy (v3):** final recall **0.40** (2 of 5 talks), with median start and end errors of
  45 s and 22 s.
- **Offline v5** (Option B constants), using only the evidence available at each run's time:
  - **Recall:** it finds **all 5 talks**.
  - **Starts:** much better at time of use, with a median start error at +5 min of about 10 s
    against 183 s.
  - **Ends:** worse on 3 of 5 talks. On one talk the end error is 420 s against v3's 131 s.
- **The D5 rule** ("v5's accuracy at +5 min is at least v3's for each talk") fails on at least one
  talk. Under the plan, that failure blocks ED-0118 pending an owner decision.

This is the Live Replay Run 002 protocol (D4) and the D5 evaluation in the
[live-chain plan](../../plans/live-chain-validation.md). It is not an accuracy qualification
of the event-day target, and it is not evidence of Event readiness.

- **Scope:** a single host, a provisional profile (`dev.v1`, the development machine, not the
  appliance), a demo database, and one real morning.
- **Not committed:** media, names, titles, schedules, timestamps, paths and raw output. Only the
  sanitized values below are.

## Setup

- **Code:** `main` at 88b13c8 (ED-0121 with the PR #190 cue-group fix; ED-0122 present but not
  selected). The live policy is v3, the service default.
- **Media:** one real event day's main-stage morning: 19 consecutive 10-minute recorder blocks of
  1080p H.264 with AAC. That is the whole morning run, from recording start to the lunch break.
- **Schedule:** that day's real published schedule (8 entries), anonymized.
- **Truth:** the 5 talks in the morning, decoded from the event's edit (as in Qualification Run
  001).
- **Cue lists:** composed by the replay from the Conference stage profile and its groups.
- **Transcription:** the current faster-whisper adapter (large-v3-turbo, CUDA `float16`), enabled
  for the Event, enqueued on arrival (ED-0120).
- **Replay:** `--pace real --arrival growing --transcription --run-every 1 --profile-label dev.v1`,
  with the default 600 s phase timeout.
- **Discovery:** `minimum_stable_seconds` at the default of 5 s, and a 5 s reconciliation interval.

## Attempts

| Attempt | Result | Cause |
| --- | --- | --- |
| a | Stopped (exit 3) after 9 blocks | Discovery registered block 10 at about 1.3 of 2.4 GB, while it was still being written. The host had entered Modern Standby at that moment and throttled the writer. |
| b | Stopped (exit 3) after 5 blocks | `minimum_stable_seconds` was raised to 30. The host entered Modern Standby, suspended every process for 4.5 h, then woke. |
| c | **Completed** | Back on the default 5 s stability window, with a keep-awake request held during the run. No standby occurred. |

- **Attempt a, environment.** Unattended, the laptop enters Modern Standby about 30 minutes after
  waking, so long replays need a keep-awake request.
- **Attempt a, product exposure.** Readiness uses the stability route only:
  - `require_inactive_write_when_available` is off, and no write-state adapter exists;
  - so a writer pause of 5 s or more registers an incomplete file.
  - The owner approved a fix on 2026-10-01: a 30 s default and a write-state follow-up (see the
    [media readiness hardening plan](../../plans/media-readiness-hardening.md)).
- **Attempt c** showed no mid-write registration while the host stayed awake.
- **Attempt b, a useful measurement.** It measured registration at about 38 s median after close
  with 30 s, against 15 s with 5 s.

## Results (attempt c)

**Pipeline latency.** Media seconds from a block's close (the end of its write) to each stage:

| Stage | Median | p95 |
| --- | --- | --- |
| Registered | 15 | 25 |
| Timing settled | 25 | 36 |
| Segmentation settled | 90 | 112 |
| Transcript available (complete) | 123 | 150 |
| Next suggestion run includes the block | 125 | 151 |

The replay drives the stages one after another, so these timings are a lower bound on contention.
No render ran concurrently.

**Live v3, per talk.**
- Errors are absolute start / end, in seconds.
- "+5" and "+15" mean the latest matching suggestion at or before the talk's end +300 s or +900 s.
- "First" is the time from the talk's end to its first matching suggestion.

| Talk | First (s) | +5 | +15 | Edge changes > 1 s |
| --- | --- | --- | --- | --- |
| 1 | 76 | 717 / 68 | 717 / 532 | 7 |
| 2 | 0 | 150 / 261 | 11 / 340 | 5 |
| 3 | 0 | 79 / 107 | 79 / 107 | 5 |
| 4 | never matched | - | - | 0 |
| 5 | 0 | 217 / 131 | 10 / 37 | 2 |

- **Final run:** 5 suggestions, 2 matched (recall 0.40), with median errors of 45 s and 22 s.
- **`no_coverage` skips** fell from 8 to 4 as blocks arrived. The remaining skips are the
  afternoon entries.

**D5 offline evaluation.**
- **Method.** At each of the 19 run times, the day's corpus manifest was truncated to:
  - the blocks whose segmentation had been observed by then;
  - the cues of blocks whose complete transcript had been observed by then (from the replay's
    evidence availability timeline).

  v3 and v5 (Option B: radius 60, weight 20, cue-edge strength 1, gap 60) were then evaluated
  offline on the same input.
- **Check.** Offline v3 reproduces the live v3 values above exactly, for every talk at +5 and +15.

| Talk | v3 +5 | v5 +5 | v3 +15 | v5 +15 | v5 last match |
| --- | --- | --- | --- | --- | --- |
| 1 | 717 / 68 | **0.5** / 143 | 717 / 532 | 717 / **15** | 717 / 15 |
| 2 | 150 / 261 | **11** / 267 | 11 / 340 | 11 / **46** | 11 / 46 |
| 3 | 79 / 107 | 79 / **8** | 79 / 107 | 79 / **8** | 79 / 8 |
| 4 | none | none | none | **7** / 536 | 7 / 536 |
| 5 | 217 / 131 | **10** / 420 | 10 / 37 | 10 / 420 | 10 / 420 |

- **Recall at +15:** v5 5 of 5; v3 4 of 5. v3 never matches talk 4.
- **Median start error at +5** (matched talks): v5 about 10 s; v3 about 183 s.
- **Median end error at +5:** v5 about 205 s; v3 about 119 s.
- **Ends are where v5 loses.** It is worse at +5 on talks 1, 2 (by 6 s) and 5, and its final end
  errors on talks 4 and 5 (536 s and 420 s) are well above the 30 s target.
- **Talk 1's start regressed in v5** between +5 and +15, from 0.5 s to 717 s.

## Findings

1. **The live chain works at 1× on real media.** Transcript evidence is available about 2 minutes
   after each block closes (p95 2.5 minutes), and the next suggestion run includes it. This
   answers D5's latency question: **transcription is not late.** Every talk's cues were available
   by +5 min.
2. **v3 remains weak on this day:** recall 0.40, consistent with Qualification Run 001's day-3
   result. Its starts drift by minutes because the real error is per talk.
3. **v5 fixes recall and starts but not ends.** With cue evidence, v5 matches every talk and
   places most starts within about 10 s, but several end edges land minutes away. Talk 1 also
   shows that a start can jump to a worse edge as later evidence arrives.
4. **D5 as written is not met.** The cause is v5's end-edge choice (and one start instability),
   not transcript timing. The lever is therefore v5's end-edge rules, not engine speed (ED-0119).
5. **Readiness exposure.** In-place recorder files can register mid-write when the writer pauses
   for 5 s or more. A fix is approved (ED-0124) and a follow-up is proposed (ED-0125).

## Interpretation and decision needed

The plan says a D5 failure blocks ED-0118 pending an owner decision. The options:

- **A. Proceed with ED-0118 as planned** (freeze v5 with Option B and make it the default).
  - **Gain:** final recall rises from 0.40 to 1.00 on this morning, and starts are far better.
  - **Cost:** the end-edge regressions ship, and they need a later v6.
- **B. Hold ED-0118 for a small v5 end-edge revision first** (recommended).
  - Investigate talks 1, 4 and 5 offline, with the harness and this run's availability timeline.
  - Adjust end-edge selection, for example end cues against changeover edges, or a coverage end
    fallback.
  - Re-evaluate on all three days, then freeze.
  - **Cost:** one more pure-policy directive before the freeze. The evaluation pipeline is ready,
    so it can be repeated offline without another 3-hour replay.
- **C. Amend D5** to judge accuracy per talk on the sum of the start and end errors.
  - Under C, 4 of 5 talks pass; talk 5 fails (430 s against 347 s).
  - That alone does not justify a freeze.

**Owner decision (2026-10-01): B.** ED-0118 is held. A small v5 end-edge revision comes
first, evaluated offline, and then the freeze follows.

**Limits.** These are one morning (5 talks) on one machine with a provisional profile, the
current transcription engine and no concurrent render. They are not a throughput guarantee or
qualification evidence.
