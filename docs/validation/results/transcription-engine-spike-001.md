# Transcription Engine Spike - Run 001

## Status and authority boundary

**MEASURED. OPTION A RECOMMENDED, PROVIDED THE PRODUCTION ADAPTER AVERAGES THE STEREO
DOWNMIX.**

- **Speed:** option A matches today's engine.
  - **GPU:** about 16 s per 10-minute block, and about 25 s while an NVENC render runs.
  - **CPU:** about 3.4–3.9 min per block.
- **Parity:** option A matches on five of the six blocks.
  - **Words:** 95–100% matched, with a p95 start difference of at most 0.57 s.
  - **Cue hits:** every option A hit on blocks 2–6 matches a baseline hit.
- **One cue divergence, now explained.** On block 1, option A found 1 cue hit against
  6, with none matching.
  - **Cause:** the FFmpeg command-line downmix `-ac 1` is exactly √2 (+3 dB) louder than
    the PyAV decode used today. Otherwise the audio is identical.
  - **Fix confirmed on that block:** averaging the two channels makes the PCM match PyAV
    to 16-bit rounding. With it, words matched 100% and cue hits were 6 against the
    baseline's 5.
- **Option B (whisper.cpp)** was not measured, because no binary was supplied. ADR-0036
  keeps B only as a fallback if A misses the latency budget, and A does not miss it here.

This is the ED-0119 measurement that gates [ADR-0036](../../adr/ADR-0036-core-transcription-gpl-free-engine.md)'s
engine switch. It records a recommendation; it does **not** qualify a GPL-free package.
The spike's option A still loads the model through faster-whisper, and the production
adapter is a later directive.

It ran on the development machine, which stands in for the appliance (a provisional
profile under [ADR-0037](../../adr/ADR-0037-owner-operated-gpu-appliance-baseline.md)).
It is not evidence of Event readiness. No media, transcript text, phrases, timestamps,
paths or configuration are committed; only the sanitized values below are.

## Setup

- **Code:** `scripts/validation/transcription_engine_spike.py` as merged in PR #183
  (`main` c050c39).
- **Machine:** Windows 11 laptop with an RTX 3080 Ti Laptop GPU (16 GiB, driver 581.57)
  and a 12th-generation Intel Core i7-12800H (20 logical processors).
- **Model:** the configured local large-v3-turbo model, English, beam size 5, word
  timestamps, no VAD, conditioned on previous text (the adapter's settings).
  - **GPU:** `float16`, with the operator's CUDA 12.4 runtime on `PATH`.
  - **CPU:** `int8`. The configured `float16` is GPU-only, and CTranslate2 refuses it on
    CPU, so the first CPU attempt failed at warm-up. The README's documented route was
    used: a separate CPU config.
- **Decode:**
  - **Baseline:** PyAV, the current path.
  - **Option A:** the operator's LGPL FFmpeg 8.1 build, `-ac 1 -ar 16000`, as 32-bit float
    PCM.
- **Blocks:** six 10-minute recorder blocks (600.03 s each, AAC stereo at 48 kHz) from
  the local legacy corpus, chosen to include stage changeovers.
- **Cue lists:** the composed Conference stage profile.
- **Runs:**
  - **GPU:** all six blocks, two passes. Pass 1 had no load; pass 2 ran a concurrent
    NVENC render. Engine order alternated per block, and warm-up was untimed.
  - **CPU:** the first two blocks, one pass with no render, and a 3,600 s deadline per
    engine.
- Both runs exited 0, with 0 errors and 0 failures.

## Results: speed

Seconds per 10-minute block.

| Device | Load | Engine | Median total | p95 total | Median decode | Median inference | Median × real time |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GPU | none | baseline | 15.6 | 20.4 | 1.44 | 14.2 | 38.6 |
| GPU | none | option A | 16.4 | 20.5 | 0.76 | 15.6 | 37.3 |
| GPU | NVENC render | baseline | 24.6 | 35.8 | 2.78 | 22.4 | 24.7 |
| GPU | NVENC render | option A | 26.0 | 31.8 | 1.33 | 24.9 | 23.1 |
| CPU | none | baseline | 225.8 | 233.7 | 1.3 | 224.5 | 2.7 |
| CPU | none | option A | 203.8 | 206.3 | 0.8 | 203.0 | 2.9 |

- **Decode:** the FFmpeg binary decodes about twice as fast as PyAV.
  - The inference difference on GPU (+1.4 s median) is within the spread between blocks.
    Per block, the two engines alternate as the faster one.
- **Render load** adds about 9–10 s per block to both engines.
  - The two engines' p95 values differ in direction: option A's p95 is lower.
- **CPU** stays ahead of real time, at about 3× on this processor. That is enough for a
  fallback that keeps up with 10-minute blocks, but not for fast cue evidence.

## Results: parity with the baseline

Per block, GPU pass 1. Pass 2 matches it to within ±0.7 points on words, and the cue
values are identical.

| Block | Words (baseline / A) | Words matched | p95 start difference (s) | Cue hits (baseline / A) | A hits matching baseline |
| --- | --- | --- | --- | --- | --- |
| 1 | 1,267 / 1,247 | 97.2% | 0.12 | 6 / 1 | 0 |
| 2 | 1,240 / 1,227 | 97.3% | 0.28 | 9 / 9 | 9 |
| 3 | 1,246 / 1,224 | 94.8% | 0.57 | 8 / 7 | 7 |
| 4 | 1,561 / 1,560 | 99.7% | 0.04 | 7 / 7 | 7 |
| 5 | 1,174 / 1,192 | 99.5% | 0.06 | 6 / 5 | 5 |
| 6 | 1,441 / 1,442 | 98.8% | 0.10 | 6 / 5 | 5 |

- **Words:** a median of 98% matched. The median start difference is 0.00–0.01 s on every
  block.
- **Cue hits:** 42 for the baseline against 34 for option A.
  - **Blocks 2–6:** 36 against 33, and all 33 option A hits match a baseline hit.
  - **Block 1:** all of the remaining difference.
- **CPU (blocks 1–2):**
  - **Block 1:** words 98.3% matched; cue hits 1 for the baseline against 3 for option A,
    with 1 matching.
  - **Block 2:** words 99.6% matched; cue hits 9 against 9, all matching.
  - On block 1 the direction flipped from the GPU run.

## Block 1 investigation

The spike's smoke run had already shown this block diverging: 5 cue hits against 1.

- **PCM comparison, same block.** The decoded audio from PyAV and from the FFmpeg command
  line has:
  - the same length (9,600,000 samples);
  - a lag of 0;
  - a correlation of 1.000000.

  Their RMS ratio is exactly 1.4142 (√2). The command-line `-ac 1` downmix of this stereo
  stream is +3 dB louder than PyAV's.
  - A `soxr` resampler leaves the difference unchanged.
  - **Averaging the channels removes it.** With `pan=mono|c0=0.5*c0+0.5*c1`, or a
    division by √2, the difference falls to an RMS of 0.000009 and a maximum of
    0.00002. That is 16-bit rounding: PyAV's path produces 16-bit samples.
- **Effect on the transcript, GPU, block 1, one run each:**

  | Option A decode | Words matched | Cue hits (baseline / A) | Matching |
  | --- | --- | --- | --- |
  | `-ac 1` (as in the spike) | 97.9% | 5 / 1 | 0 |
  | channel average | 100.0% | 5 / 6 | 4 |

- **Interpretation:**
  - Whisper's log-mel features are close to level-invariant, but not exactly. Their
    floor is clamped relative to the loudest frame.
  - With conditioning on previous text, a small feature difference can send decoding
    down a different path on a fragile stretch. Block 1's changeover is such a stretch:
    - **The baseline moves too.** It found 6 cue hits in Run 001 and 5 in this rerun on
      the same GPU, and only 1 on CPU.
    - Cue counts on this block are sensitive to any small numerical difference, not only
      to the decoder.
  - A matched downmix removes the systematic difference. What remains is run-to-run
    variation of the same size as the baseline's own.

## Findings

1. **Option A meets the latency side of the ADR-0036 gate on this machine.** It is
   equivalent to the baseline on GPU, with and without a render, and faster on CPU and in
   decode.
2. **Option A meets the parity side once the downmix matches.**
   - With channel averaging, the only systematic decoder difference disappears.
   - Parity values (words ≥ 95% matched, p95 start difference ≤ 0.6 s, cue hits matching
     one-to-one outside the fragile block) are of the same size as the baseline's own
     run-to-run variation.
3. **Changeover cue hits on fragile stretches are unstable for every engine.** This is a
   property of the model with `condition_on_previous_text`, not of option A. ADR-0034's
   cue evidence already treats hits as advisory support; Live Replay Run 002 will
   measure their effect on suggestions.
4. **A CPU fallback must not inherit a GPU-only compute type.** The configured `float16`
   fails on CPU. A production adapter or profile must choose a CPU-valid type such as
   `int8`, and record it in the execution profile.
5. **Option B was not measured.** It is not needed under ADR-0036 unless A misses the
   appliance latency budget.

## Interpretation and recommendation

**Build the production GPL-free adapter as option A**, a StageFlow-owned CTranslate2
adapter fed by the operator's LGPL FFmpeg binary. Its plan should carry these
requirements from this run:

- **Downmix:** average the channels explicitly (for example
  `pan=mono|c0=0.5*c0+0.5*c1`, or gain-match to PyAV). Do not rely on `-ac 1`.
  Include a PCM equivalence test against a stereo fixture.
- **Parity tolerances for the switch:** propose the values measured here, for owner
  confirmation in that plan:
  - words matched ≥ 95% per block;
  - p95 word start difference ≤ 0.6 s;
  - cue hits judged in total across a multi-block set, not per block.
- **Compute types per device:** `float16` on GPU and a CPU-valid type on CPU, each part
  of the execution profile identity.
- **Requalify on the appliance:** rerun this spike, or the adapter's own parity run, on
  the appliance-class GPU before ED-0075 is superseded and the SBOM regenerated.

Live Replay Run 002 (ED-0121) proceeds on the current engine. The adapter switch does not
block it.
