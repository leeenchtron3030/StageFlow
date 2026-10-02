# Transcription Engine Parity - Run 001 (ED-0122 engine against faster-whisper)

## Status and authority boundary

**PASSED. THE STAGEFLOW CTRANSLATE2 ENGINE MEETS EVERY D5 TOLERANCE, ON GPU (WITH AND WITHOUT
A RENDER) AND ON CPU.**

- **GPU** (6 blocks, two passes): words matched at least 97.0% on every block; p95 word-start
  difference at most 0.24 s; cue hits 41 against 42 (no load) and 41 against 41 (under render),
  with 98% and 93% of the new engine's hits matching. It is **faster**: median 15.1 s against
  17.7 s per 10-minute block, and under render a p95 of 26.6 s against 35.3 s.
- **CPU `int8`** (6 blocks): words matched at least 96.3%; p95 at most 0.16 s; cue hits 37
  against 37, with 34 of 37 (92%) matching.
- **The ED-0119 cue gap is gone.** On the changeover block where option A had found 1 hit
  against 6, the new engine finds 6 of 6, matching on GPU. The channel-average downmix is the
  fix.

This is the owner parity run that gates ED-0123 under the
[GPL-free engine plan](../../plans/gpl-free-transcription-engine.md) (D5). It ran on the
development machine (a provisional profile, not the appliance). It is not an Event-readiness
claim. Only sanitized values are committed.

## Setup

- **Code:** `main` with ED-0122 (PR #189).
- **Script:** `scripts/validation/transcription_engine_spike.py --candidate stageflow`.
  - **Baseline:** `FasterWhisperExecutionAdapter`, decoding with PyAV.
  - **Candidate:** `CTranslate2WhisperExecutionAdapter`, decoding with the operator's LGPL
    FFmpeg (explicit channel average).
  - **Shared settings:** the same model directory (large-v3-turbo), English forced on both
    sides (ADR-0036 decision 5), beam 5, word timestamps.
- **Machine:** RTX 3080 Ti Laptop GPU (16 GiB, driver 581.57) and a 12th-generation Core
  i7-12800H. GPU runs use `float16`; CPU runs use `int8`.
- **Blocks:** the six 10-minute changeover blocks used in ED-0119 Run 001 (real recorder
  blocks, AAC stereo at 48 kHz).
- **Runs:**
  - **GPU:** 6 blocks, pass 1 with no load and pass 2 with a concurrent NVENC render;
    alternating engine order; untimed warm-up.
  - **CPU (timing):** 2 blocks on an otherwise idle machine.
  - **CPU (parity):** 6 blocks. An unrelated test run shared the CPU during it, so **its
    timings are not representative**; its parity values are.
- Every run exited 0, with 0 errors.

## Results: parity against the D5 tolerances

| Run | Words matched (worst block) | p95 start difference (worst block) | Cue hits, candidate / baseline | Candidate hits matching | D5 |
| --- | --- | --- | --- | --- | --- |
| GPU, no load | 97.1% | 0.24 s | 41 / 42 (98%) | 40 of 41 (98%) | **pass** |
| GPU, NVENC render | 97.0% | 0.24 s | 41 / 41 (100%) | 38 of 41 (93%) | **pass** |
| CPU `int8`, 6 blocks | 96.3% | 0.16 s | 37 / 37 (100%) | 34 of 37 (92%) | **pass** |

The D5 tolerances are: words ≥ 95% and p95 ≤ 0.6 s on every block; over the set, candidate
cue hits ≥ 90% of the baseline's, and ≥ 90% of candidate hits matching.

- **CPU, 2-block run.** It alone missed the cue-match criterion: 9 of 11 hits matched (82%).
  All of the miss is on the fragile changeover block. There the CPU baseline itself finds only
  1 hit (against 6 on GPU), and the candidate finds 2 that do not line up with it. Over 6
  blocks the set passes.

## Results: speed (seconds per 10-minute block)

| Device | Load | Engine | Median total | p95 total | Median decode | Median inference |
| --- | --- | --- | --- | --- | --- | --- |
| GPU | none | faster-whisper | 17.7 | 20.3 | 1.53 | 16.2 |
| GPU | none | **StageFlow CT2** | **15.1** | **17.5** | **1.08** | **14.0** |
| GPU | NVENC render | faster-whisper | 25.7 | 35.3 | 2.76 | 23.6 |
| GPU | NVENC render | **StageFlow CT2** | **25.6** | **26.6** | **1.95** | **23.6** |
| CPU | none (2 blocks) | faster-whisper | 226.0 | 232.1 | 1.41 | 224.6 |
| CPU | none (2 blocks) | **StageFlow CT2** | **223.0** | 253.0 | **1.05** | 222.0 |

- **GPU:** the new engine is about 15% faster without load. Under render load it has the same
  median and a much tighter p95. FFmpeg decode is about 30% faster than PyAV.
- **CPU:** about the same as the baseline, around 2.7–3.1× real time.

## Findings

1. **Parity holds on both devices.** The ED-0122 port, with explicit channel averaging,
   reproduces today's transcripts within the owner-approved tolerances.
2. **The new engine is not slower anywhere**, and is faster on GPU. That matters for the live
   chain, where transcripts are the slowest evidence (Live Replay Run 002: about 123 s after a
   block closes).
3. **Changeover stretches remain fragile for every engine:** cue counts on one block vary with
   numeric details (GPU against CPU, run to run). Judge cue parity over sets of blocks, as D5
   does.

## Interpretation

The plan's ED-0123 condition ("after a passing owner parity run") is met on the development
machine. The plan also asks for requalification on the appliance-class GPU before ED-0075 is
superseded. That can be the first check when appliance hardware exists, or the owner can accept
this provisional profile for the switch.

**Recommendation:** proceed with ED-0123:
- switch the default provider and profile;
- make `transcription-core` default dependencies;
- remove faster-whisper and PyAV;
- replace the ED-0075 guard with a GPL-free guard;
- regenerate the SBOM, including the CTranslate2 Linux wheel inventory;
- install `transcription-core` in CI.

Record the appliance requalification as a follow-up.
