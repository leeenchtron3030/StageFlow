# Render Durable Operation - Real-GPU validation Run 003 (profile v3, audio)

## Status and authority boundary

**PASSED AFTER A DEFECT FIX.**

- On the merged ED-0098 code (`813144b`), the first v3 render produced a playable but
  **defective** file. Each input's audio overran its video by minutes, so stage 2 joined
  the inputs with gaps of 200–270 s.
- The cause is that `apad` combined with `-shortest` does not stop the audio at the end of
  the video on this FFmpeg 8 build. The fake-FFmpeg unit tests and the implementation
  review could not detect this.
- The fix fits each input's audio to an exact sample count derived from that input's
  stage-1 video frame count. On the fixed code, every Run 003 criterion passed.

This is the owner's real-GPU step for ED-0098, under
[ADR-0032](../../adr/ADR-0032-render-durable-operation.md) amendment 4A and the
[approved plan](../../plans/render-profile-v3-audio.md). It follows
[Run 002](render-durable-operation-002.md).

It is **not** evidence of Event readiness or a throughput guarantee. It is a single run on
a single host. No media path, filename, username, connection string, or FFmpeg log text is
recorded here.

## Setup

- **Host and FFmpeg:** the same host, driver, and operator-installed LGPL FFmpeg and
  ffprobe build as Runs 001–002. `[local_render] ffprobe_path` was added to the
  validation configuration and names the ffprobe from the same build.
- **Database:** the demo database was backed up with `pg_dump` before the run. There is no
  migration.
- **Revision B (real media):** the approved Run 002 validation Session: a synthetic
  30000/1001 video-only bumper plus eleven 2997/100 recorder blocks with AAC 48 kHz stereo
  audio.
  - The first render used Assembly revision 1.
  - The re-render used the already approved revision 2, which has the same media. v3 on
    revision 1 had already been recorded, so the idempotent work key would have returned
    that operation.
- **Revision A (synthetic sync):** a labelled validation Session holding three generated
  clips. Every clip has a full-frame white flash and a 1 kHz beep of 100 ms, both at
  2 s + 5k s:
  - clip 1: 30000/1001, 48 kHz stereo, 20 s;
  - clip 2: 2997/100, 44.1 kHz **mono**, 20 s;
  - clip 3: 25 fps, 48 kHz stereo, 15 s.

  The Assembly template binds the same **silent** synthetic bumper in front of them. The
  clips are registered under their own configured source, which was added to the stage
  with the idempotent bootstrap.

## Results

### Defect found: first v3 render on the merged code (Revision B, revision 1)

| Check | Result |
| --- | --- |
| Operation | succeeded, one attempt, 84.7 s |
| Identity (content and sidecar SHA-256 vs row), temporary area | match; empty |
| Streams | H.264 Main 1080p 30000/1001 + AAC-LC 48 kHz stereo |
| Video frames | 19,858, about 662 s of video |
| Stream durations | video **3,117.6 s**, audio **3,363.3 s** |
| Frame steps | **10 irregular**: 200–270 s gaps, one at each input join |

- **Cause:** reproduced on a 20 s input cut. Stage 1 with
  `aresample,aformat,apad` + `-shortest` wrote 20.02 s of video and **255.68 s** of audio.
  The concat demuxer offsets each next input by its longest stream.
- **Record:** this output stays in history as the registered v3 output of revision 1. It
  is validation data only; nothing was deployed.
- **Profile version:** the v3 definition did not change, only its implementation, so the
  profile version was not bumped.
- **Stale operation:** one attempt at Revision A is left in `retry_wait` with
  `input_missing`. Its clips were first registered under a source whose configured root
  does not contain them, and render input containment refused them, which is correct. It
  will reach its retry limit and fail; it has no effect on other work.

### Fixed pipeline

- Stage 1a now encodes each input's video only.
- Stage 1b copies that video and adds audio of exactly
  `round(frames × 1001/30000 × 48000)` samples:
  - anchored at time zero with `aresample=async=1:first_pts=0`;
  - padded and trimmed with `apad=whole_len` and `atrim=end_sample`;
  - taken from the resampled first audio stream, or from `anullsrc` when the input has no
    audio.
- Stage 2 is unchanged.

A three-input join on the 20 s cut gave identical audio and video durations and 1,800
equal frame steps.

| Check | Revision B re-render (real media) | Revision A (synthetic sync) |
| --- | --- | --- |
| Operation | succeeded, one attempt, **88.1 s** | succeeded, one attempt, 10.7 s |
| Identity (content and sidecar SHA-256), sidecar `profile_version` | match; `"3"` | match; `"3"` |
| Temporary area after success | empty | empty |
| Streams | H.264 Main 1920×1080, nominal and average 30000/1001; AAC-LC 48 kHz stereo | same |
| Audio − video duration | **0.0 ms** (662.595 s each) | **0.0 ms** (59.993 s each) |
| Irregular frame steps / duplicate PTS | **0 / 0** of 19,858 frames | **0 / 0** of 1,798 frames |
| Full decode | exit 0, 0 warning lines | exit 0, 0 warning lines |
| Flash-to-beep offset, 11 markers | — | max **18.1 ms**; each marker equals its source offset exactly for clips 1–2 (48 kHz stereo; 44.1 kHz mono); ≤ 12 ms change for clip 3 (25 → 30000/1001 fps) |
| Silent bumper span (first 5 s) | — | peak **−inf dB**: digital silence |
| Deterministic re-render | **byte-identical** SHA-256 (`d36f713b…`) through the production adapter on the final code, 76.0 s | **byte-identical** SHA-256 (`7abd1b6b…`) through the same adapter |

The rendered outputs came from the fix before its review follow-up. That follow-up only
frees each input's video-only temporary file earlier. The determinism re-renders ran on the
final code, and matched the registered outputs byte for byte.

The ±40 ms criterion is set by the plan. The source clips' own measured offsets span
−14.3 to +18.7 ms, which is the resolution of frame-quantized flashes and beep detection.
What matters is that the render **adds no drift** beyond frame-rate conversion.

## Interpretation

- **Measured:**
  - The fixed v3 pipeline keeps audio and video lengths identical per input and in the
    output.
  - It adds no measurable A/V offset for 48 kHz stereo and 44.1 kHz mono inputs.
  - It fills audio-less inputs with digital silence.
  - It keeps the output constant-rate, with no duplicate timestamps and a clean decode.
  - It is deterministic.
- **Duration:** the real-media output has 19,858 frames and runs 662.595 s. Run 002 (v2)
  had 19,842 frames and 662.061 s. Each input is now converted to constant rate
  separately, and its segment length is rounded to whole frames.
- **Throughput:** the attempt took **88.1 s**, against **52.4 s** for v2 in Run 002 on the
  same inputs, about 68% longer. This is expected from:
  - two FFmpeg processes per input;
  - an audio pass that re-reads each high-bitrate recording;
  - the final join.

  This is still about 7.5× real time. It is one measurement, not a guarantee.
- **Test gap:** fake-binary tests cannot prove FFmpeg filter semantics, and this defect
  passed unit tests, an independent review, and CI. Real-FFmpeg validation stays
  necessary for any render pipeline change.

## Not run

- The optional additional real-media revision (a longer recorder folder) was not rendered.
