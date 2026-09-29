# Media Segmentation Evidence - real-FFmpeg validation Run 001

## Status and authority boundary

**PASSED.**

- The production segmentation adapter, run against the operator-installed LGPL FFmpeg
  8.1, produced freeze and silence intervals that match known synthetic spans and a
  manual command-line reference on real recorder material.
- It handled files ending in silence or in freeze, audio-only input and video-only input.

This is the owner's real-binary step for ED-0103 under
[ADR-0034](../../adr/ADR-0034-session-boundary-suggestions.md) and the
[plan](../../plans/session-boundary-suggestions.md). It is **not** evidence of boundary
detection accuracy (that is Phase 5) or of Event readiness. No media path, filename,
speaker, event name or FFmpeg log text is recorded here.

## Setup

- **Host:** the reference host from the render runs, with the same FFmpeg build.
- **Code:** branch `codex/ed-0103-media-segmentation`, including the review fixes.
- **Invocation:** `FFmpegSegmentationAdapter.inspect` called directly with profile v1:
  - video: `fps=5,scale=320:-2,freezedetect=n=0.003:d=4`;
  - audio: `silencedetect=n=-40dB:d=3`.
- No database was involved.
- **Inputs:**
  - synthetic clips generated with FFmpeg `lavfi`;
  - two 10-minute real recorder blocks, and 60-second and 14-second blocks from a
    real-media re-recording. All of these are kept outside the repository.

## Results

| Input | Known or reference spans | Adapter output |
| --- | --- | --- |
| Synthetic 30 s: frozen 10–20 s, silent 12–22 s | freeze 10–20 s; silence 12–22 s | freeze **10.000–20.000 s**; silence **12.011–22.016 s** (the offset is normal AAC encoder delay) |
| Synthetic 10 s, silent from 5 s to end of file | silence 5–10 s | silence **5.013–10.000 s**, closed at end of file with no error |
| Synthetic 11 s, frozen from 5 s to end of file | freeze 5–11 s | freeze **5.000–11.000 s** |
| Synthetic audio-only WAV, silent 3–7 s | silence 3–7 s | silence **3.008–7.019 s** |
| Synthetic video-only MP4, frozen from 4 s | freeze 4–10 s | freeze **4.000–10.000 s** |
| Real 10-minute recorder block containing a talk changeover | a manual FFmpeg run with the same filters | **identical** interval list, 12 intervals, including a freeze of 442.2–526.6 s over the between-talk title card |
| Real 60-second holding block | none (observation) | freeze for the full block; silence 0.02–42.5 s |
| Real 60-second changeover block | none (observation) | freeze for the full block; silence only 11.4–14.6 s |
| Real 14-second final block | none (observation) | one freeze, 4.2–9.6 s; no errors |

Heartbeats were observed during every inspection: 20 over the 10-minute block.

## Interpretation

- **Measured:**
  - The adapter parses the real FFmpeg 8.1 log format.
  - It closes open intervals at end of file.
  - It tolerates missing audio or video streams.
  - On real material it reproduces the command-line reference exactly.
- **For the Phase 2 policy (observation, not a result of this run):**
  - A changeover can carry audio. The real changeover block was frozen throughout but had
    only 3 s of silence.
  - Holding content can have music after an initial silence.
  - A long freeze should therefore be the primary changeover signal, with silence as
    supporting evidence.
  - Short freezes (4–7 s) also occur inside talks when slides are static, so the policy
    needs a minimum duration or corroboration.
- **Not covered:**
  - multi-track audio (only the first audio stream is analysed);
  - multi-hour files against the fixed 3600 s timeout;
  - GPU decode.
