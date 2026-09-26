# Render Durable Operation - Real-GPU validation Run 001

## Status and authority boundary

**PASSED - An approved, non-stale Session Assembly revision was rendered end to end by the
ED-0087 render worker on the reference GPU. The registered Rendered Output matches its
bytes (SHA-256 and size), its sidecar manifest matches its recorded SHA-256, the output
decodes completely, and its frame count equals the sum of its inputs exactly. One
follow-up was found: inputs at different frame rates produce duplicate presentation
timestamps (see [Findings](#findings)).**

This is the owner's real-GPU validation step for ED-0087 under
[ADR-0032](../../adr/ADR-0032-render-durable-operation.md) and the
[approved plan](../../plans/render-durable-operation.md) (in-scope item 10). It is **not**
evidence of Event readiness, a throughput guarantee, or a hardware qualification.

The run took place on 2026-09-25. No media path, filename, username, connection string,
or FFmpeg log text is recorded here.

## Setup

- **Host:** the reference host from render benchmark Runs 001–003: NVIDIA GeForce RTX 3080
  Ti Laptop GPU, driver 581.57, Windows 11.
- **FFmpeg:** operator-installed LGPL build `n8.1.2-50-g1a748fe2cd-20260831`, supplied by
  explicit path in an optional `[local_render]` configuration and identified by version and
  SHA-256 `9c60da6c…1e7cea`. The worker's GPL/nonfree refusal and NVENC probe passed.
- **Database:** the local demo database, backed up with `pg_dump` first, then migrated
  forward through `0014` and `0015`.
- **Code:** branch `codex/ed-0087-render-durable-operation` at the Phase B commit.

### Validation event and the media-timing gap

Rendering requires an **approved** Assembly revision. No Session from the recorded live
run could supply one:

- Discovery never sets a recorded start time on Completed Media Assets (the asset built in
  `backend/app/bootstrap/media_cycle.py` leaves it unset), so `media_started_at` is empty for
  every registered asset in the demo database before this run (0 of 57 completion members).
- ED-0077 deliberately makes unknown media timing invalid (`media_timing_unavailable`), so
  every proposal built from discovered media is invalid and cannot be approved.

This gap predates ED-0087 and is outside its scope; it is recorded as a follow-up. With the
owner's approval, the run used a clearly labelled **validation event** instead:

- The eleven real 2026-08-26 live-run recording blocks (the same corpus as benchmark Runs
  001–003) were registered to one Session through the Kernel's repository and command
  methods, in the same way as the automated test fixtures.
- Each block's media start time came from **its own recorder-written container
  `creation_time`** and its duration from the container, not from invented values.
- The Session package was completed through the normal Kernel commands.
- One approved **video** Packaging Asset was bound to an opening-bumper slot: a synthetic
  five-second 1920×1080 H.264 test-pattern clip generated with NVENC, resolved through the
  packaging content root with SHA-256 and size verification.

The resulting proposal validated `valid` with no issues: eleven completion members and one
bound packaging revision. It was approved by a human command, and a render was requested
through `RenderingService.request_render` with the first render profile.

## Method

1. Start `python -m app.demo.render_worker --once` against the validation configuration.
2. Read back the operation, its attempt, and the Rendered Output row.
3. Hash the stored output and sidecar manifest, and compare them with the registered row.
4. Probe the output with `ffprobe` and decode it fully with FFmpeg to a null sink.
5. Compare the output frame count with the sum of input frame counts.

## Results

| Check | Result |
| --- | --- |
| Operation outcome | `succeeded` after one attempt; terminal result is the Rendered Output; lease released |
| Attempt | `result_applied`, fence generation 1 |
| Render wall time (attempt execution) | 58.5 s for 661.99 s of output (~11.3× real time, including input verification, hashing, and commit) |
| Content SHA-256 and size vs registered row | match (`6a464ae2…376dd5`, 655,138,122 bytes) |
| Sidecar manifest SHA-256 vs registered row | match (`cccbb579…f20d82`) |
| Manifest content | schema `stageflow.render-manifest.v1`: Assembly revision, Event, Session, profile ID and version, frozen metadata (empty; the template required none); no paths |
| Temporary area after success | empty |
| Stream | H.264 Main, 1920×1080, yuv420p, 30000/1001 fps nominal, video only (no audio stream), ~7.92 Mbit/s against the 8 Mbit/s VBR target |
| Full decode | completed, exit status 0 |
| Frame count | 19,850 registered and probed = 150 (intro) + 19,700 (eleven blocks, as in Runs 001–003): **exact** |
| Recorded duration | 661.894567 s; container duration 661.994667 s |

## Findings

1. **Mixed input frame rates produce duplicate presentation timestamps (follow-up).**
   The full decode reported 22 duplicate frame PTS values, about one every 33 s. Packet
   DTS values are all unique.
   - Cause: the synthetic intro is 30000/1001 fps, while the recordings are 2997/100 fps.
     The first profile uses `-fps_mode passthrough`, so the recordings' timestamps are
     rescaled into the intro's time base and some pairs round onto the same value.
   - Confirmed in isolation with the same FFmpeg arguments: intro plus three blocks gave 6
     duplicates with the mismatched intro and **0** with a rate-matched (2997/100) intro.
     The Run 003 reference output (the blocks alone) has 0 duplicates.
   - Impact: a player drops the duplicated frame (22 of 19,850 here). Inputs at a single
     frame rate are unaffected.
   - Options for a later profile decision: normalize to a constant output frame rate in a
     new profile version, or make a frame-rate mismatch a typed ineligibility.
2. **Discovery does not supply media start times (pre-existing, follow-up).** Described
   under [Validation event](#validation-event-and-the-media-timing-gap). Until it is
   resolved, no Session built from discovered media can produce an approvable Assembly
   revision, so it cannot be rendered.

## Interpretation

The capture → Assembly → rendered-file chain works on the reference GPU for an approved
revision. Identity is recorded correctly: the key is opaque, the SHA-256 and size match,
the sidecar manifest is hashed, and the FFmpeg identity is recorded. Nothing partial was
left behind, and the lease and fencing behaved as specified. ADR-0032's real-GPU
validation criterion is met for inputs at a single frame rate. The two findings are
bounded follow-ups rather than regressions of the accepted design.
