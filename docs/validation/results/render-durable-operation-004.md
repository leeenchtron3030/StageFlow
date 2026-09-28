# Render Durable Operation - Real-GPU validation Run 004 (render quality per Event)

## Status and authority boundary

**PASSED WITH ONE CRITERION NOT MET AS WRITTEN.**

- Every preset and adjustment rendered with the expected resolution and stream set. Each
  output kept the ED-0098 audio and video guarantees, and video bitrate came within 5% of
  its target.
- The exception is audio: the **1080p High 320 kbit/s audio choice measured 261 kbit/s**.
  FFmpeg's native AAC encoder did not reach the requested rate. All other audio choices
  measured within 4 kbit/s of nominal.

This is the owner's real-GPU step for ED-0099, under
[ADR-0032](../../adr/ADR-0032-render-durable-operation.md) amendment 4B and the
[approved plan](../../plans/event-render-quality.md). It follows
[Run 003](render-durable-operation-003.md).

It is **not** evidence of Event readiness or a throughput guarantee. It is a single run on
a single host. No media path, filename, username, connection string, or FFmpeg log text is
recorded here.

## Setup

- **Host, FFmpeg and ffprobe:** the same as Runs 001–003.
- **Code:** `main` at `6133fa4`, which includes ED-0099 and the ED-0098 audio-length fix.
- **Database:** the demo database was backed up with `pg_dump`, then migrated forward to
  `0020`.
- **Settings:** chosen on the validation Event in this order. The first two were chosen
  through the Producer interface during the UX checkpoint; the rest used the rendering
  settings repository with `expected_version`.
  1. 1080p High at 16 Mbit/s (not rendered);
  2. 720p Compact at its defaults;
  3. 1080p High at its defaults;
  4. 1080p High at 20 Mbit/s video and 320 kbit/s audio (the upper bounds);
  5. 720p Compact at 3 Mbit/s video and 96 kbit/s audio (the lower bounds).
- **Revisions:** for each rendered setting, one render request each for:
  - the approved **real-media** revision: the Run 002/003 media, a silent synthetic bumper
    plus eleven recorder blocks, 662.5 s of output;
  - the **synthetic sync** revision from Run 003: the silent bumper plus flash/beep clips
    at 48 kHz stereo, 44.1 kHz mono, and 25 fps.

  Each request carried the setting version it expected, and each operation froze its
  preset and adjustments.
- **Standard defaults:** measured in Run 003 on the same revisions; listed below for
  comparison.

## Results

Real-media revision:

| Setting | Resolution | Video target → measured average | Audio target → measured | Attempt |
| --- | --- | --- | --- | --- |
| 1080p Standard (Run 003) | 1920×1080 | 8 → 7.89 Mbit/s | 192 → 191 kbit/s | 88.1 s |
| 720p Compact | 1280×720 | 4 → 3.83 Mbit/s | 128 → 127 kbit/s | 78.3 s |
| 1080p High | 1920×1080 | 14 → 13.35 Mbit/s | 256 → 252 kbit/s | 90.8 s |
| 1080p High, 20 Mbit/s / 320 kbit/s | 1920×1080 | 20 → 19.10 Mbit/s | **320 → 261 kbit/s** | 98.2 s |
| 720p Compact, 3 Mbit/s / 96 kbit/s | 1280×720 | 3 → 2.92 Mbit/s | 96 → 96 kbit/s | 76.3 s |

Every output, real and synthetic, at every setting:

| Check | Result |
| --- | --- |
| Operation | succeeded, one attempt |
| Identity | content and sidecar SHA-256 match their rows |
| Temporary area after success | empty |
| Frozen inputs | operation inputs record the adjustments: 20,000,000/320,000 and 3,000,000/96,000 for the bound cases, none for defaults |
| Streams | H.264, nominal and average 30000/1001; AAC-LC 48 kHz stereo |
| Audio − video duration | **0.0 ms** |
| Irregular frame steps / duplicate PTS | **0 / 0** |
| Full decode | exit 0, 0 warning lines |
| Synthetic flash-to-beep offsets, 11 markers | identical to Run 003 at every setting; maximum 18.1 ms |
| Silent bumper span | peak −inf dB |

Throughput on the real media ranged from 76.3 s (720p, 3 Mbit/s) to 98.2 s (1080p,
20 Mbit/s), about 6.7–8.7× real time. Lower resolution and bitrate were faster.

## Interpretation

- **Measured:**
  - Every catalog preset and both adjustment bounds render with the configured resolution.
  - Video bitrate lands within −1.4% to −4.6% of its VBR target.
  - Sync, constant frame rate, silence handling and decode quality are independent of the
    preset.
  - Operations freeze the setting that was current when they were requested.
- **Audio at 320 kbit/s:** the native `aac` encoder produced 261 kbit/s on speech-heavy
  recordings when asked for 320 kbit/s. It came within 1–4 kbit/s at 96, 128, 192 and
  256 kbit/s. The encoder treats the rate as a target it may undershoot, not a constant
  rate.
  - The native `aac` encoder is fixed by ADR-0032 amendment 4A to keep the LGPL posture, so
    a different encoder is not an option within current authority.
  - **Owner decision (2026-09-27):** keep the 320 kbit/s choice, labelled "up to 320
    kbit/s" (ED-0100). There is no catalog change.
- **The Run 004 plan criterion** ("the nominal audio bitrate") is met for every other case.
- **Limits:** a single run, host and media set. Synthetic clips are mostly silence, so
  their audio bitrates (5–8 kbit/s) are not meaningful.

## Not run

- Deterministic re-rendering was not repeated per preset. Run 003 showed it for the
  pipeline, and presets only change validated integer parameters.
- No longer recorder corpus was rendered.
