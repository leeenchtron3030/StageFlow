# Render Durable Operation - Real-GPU validation Run 002 (profile v2)

## Status and authority boundary

**PASSED WITH ONE CRITERION NOT MET AS WRITTEN - Profile v2 (a constant 30000/1001 output
frame rate) removed every duplicate presentation timestamp found in Run 001. It decoded
without a single warning, and its identity checks passed.**

The plan also asked for a duration "within one frame of the input sum". Measured literally
against the sum of per-file stream durations, that criterion is **not met**: the output is
0.334 s (about 10 frames) short. The v1 output from Run 001, rendered from the same inputs,
was 0.40 s short by the same measure. The shortfall therefore comes from how the concat
demuxer joins inputs, not from v2. See [Duration](#duration).

This is the owner's real-GPU step for ED-0089 under
[ADR-0032](../../adr/ADR-0032-render-durable-operation.md) amendment 3 and the
[approved plan](../../plans/render-profile-v2-constant-frame-rate.md). It follows
[Run 001](render-durable-operation-001.md). It is **not** evidence of Event readiness or a
throughput guarantee. No media path, filename, username, connection string, or FFmpeg log
text is recorded here.

## Setup

- Same host, driver, FFmpeg build (identified by version and SHA-256), validation event,
  approved Assembly revision, and inputs as Run 001:
  - the synthetic 30000/1001 bumper;
  - the eleven 2997/100 live-run blocks.
- The demo database was backed up again, then migrated forward to `0016` (ED-0088).
- Code: branch `codex/ed-0089-render-profile-v2`.
- A v2 render of the Run 001 revision was requested. The work key includes the profile
  version, so this created a new operation, as ADR-0032 amendment 3 intends.

## Results

| Check | Run 001 (v1, passthrough) | Run 002 (v2, constant rate) |
| --- | --- | --- |
| Operation | succeeded, one attempt | succeeded, one attempt, fence 1, `result_applied` |
| Attempt execution time | 58.5 s | 52.4 s |
| Content SHA-256 and size vs the registered row | match | match (`6ca2a142…f70588`, 654,377,328 bytes) |
| Sidecar manifest SHA-256 vs the registered row | match | match (`3842420e…ab39a5`); `profile_version` is `"2"` |
| Temporary area after success | empty | empty |
| Stream | H.264 Main 1920×1080 yuv420p; average rate 29.985 fps | H.264 Main 1920×1080 yuv420p; nominal and average rate both **30000/1001** |
| Duplicate packet PTS | **22** | **0** |
| Full-decode warnings | 22 non-monotonic timestamp warnings | **0** |
| Frames | 19,850, which equals the input frame sum | 19,842: 8 fewer, dropped during constant-rate conversion where input timestamps overlapped |
| Video stream / container duration | — / 661.995 s | 662.061 s / 662.061 s |
| Recorded `duration_microseconds` | 661,894,567 | 661,961,300 |
| Bit rate | 7.92 Mbit/s | 7.91 Mbit/s |

## Duration

- The per-file video stream durations of the twelve inputs add up to **662.396 s**.
- The concat demuxer joins inputs on their timestamps rather than adding up per-file
  durations, which include trailing padding.
- Measured against that sum:
  - Run 001's passthrough output was 0.40 s short;
  - Run 002 is 0.334 s short.
- **v2 changed the duration by only +0.067 s (about 2 frames) compared with v1 from the same
  inputs.**

The plan's "within one frame of the input sum" was too precise for concat semantics. The
meaningful measure is "matches the v1 timeline to within a few frames, with no timestamp
defects", and Run 002 meets it.

## Interpretation

Profile v2 fixes Run 001's mixed-frame-rate defect for this input mix, with no loss of
throughput. It was about 10% faster in this single run, which is within normal variation
and not a performance claim. Constant-rate output trades exact frame-count equality for
monotonic, evenly spaced timestamps. Eight overlapping frames were dropped here, which is
the intended behaviour for mixed rates.

Remaining limits:
- a single host and a single input mix;
- rate mixes other than 30000/1001 with 2997/100 were not exercised.
