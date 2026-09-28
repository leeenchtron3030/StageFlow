# Render profile v3: audio

## Status

Approved (2026-09-27).

## Execution authority

- Classification: Green autonomous, under the owner's decision of 2026-09-27 and ADR-0032
  amendment 4A.
- Authority evidence:
  - The owner selected "render with audio" from the 2026-09-27 roadmap shortlist and
    accepted the recommended audio settings: AAC-LC from FFmpeg's native encoder, 48 kHz,
    stereo, 192 kbit/s, silence for inputs without audio, and loudness normalization
    deferred.
  - [ADR-0032](../adr/ADR-0032-render-durable-operation.md) decision 5 ("audio is a
    follow-up profile decision") and amendment 4A.
  - [Run 002](../validation/results/render-durable-operation-002.md), duration finding:
    joining inputs lost 0.334 s across twelve inputs, which is why sync may not depend on
    the joins.
- Implementation-ready: Yes.
- Required escalation: stop if this needs a migration or a new dependency, changes any
  video setting of v2, adds per-Event selection, presets, or adjustments (those are
  ED-0099), changes Assembly semantics, or cannot meet the sync criteria without
  re-encoding video twice.
- Engineering Directive: **ED-0098**. The owner delegated ED numbering, and ED-0098 was
  the next free number in `ENGINEERING_DIRECTIVES.md`.

## Preserved accepted decisions

- ADR-0032:
  - human-only authority;
  - one lease per GPU;
  - the operator-installed LGPL FFmpeg given by explicit path, with the identity check
    that refuses `--enable-gpl` and `--enable-nonfree` builds;
  - the opaque key plus SHA-256 identity;
  - no overlays;
  - a partial output is never registered, and stderr is never stored.
- v2 video settings, unchanged: CUDA decode, `scale_cuda` to 1920×1080 NV12, H.264
  `h264_nvenc` p4, VBR 8 Mbit/s, GOP 60, constant 30000/1001, MP4.
- ED-0087 decision (a): the work key is the revision plus the profile ID and version, so
  a v3 request for a revision already rendered with v2 is a new operation.
- v1 and v2 Rendered Outputs stay readable. Their profile identity is never rewritten.
- ADR-0033: `ffprobe` is an operator-installed LGPL binary given by explicit path, with an
  identity check, no shell, and a demuxer allowlist.

## Problem statement

Every Rendered Output is video only (`-an`), so no render can be used as a finished talk
video. Two facts make "just map the audio" unsafe:

- The concat demuxer needs each input to have the same streams. A silent bumper next to
  recordings with audio either fails or misaligns everything after it.
- Joining inputs shifts their timestamps. Run 002 lost 0.334 s across twelve inputs. If
  audio were joined separately from video, it would drift out of sync by roughly that
  much by the end.

## Verified current behavior

- `backend/app/contexts/rendering/contracts.py:42-64`:
  - `RenderProfile` has `audio: Literal[False]`.
  - `CURRENT_RENDER_PROFILE` is `h264-nvenc-1080p-video` v2.
  - `RENDER_PROFILE_V1` is kept only as a recorded identity.
  - `FIRST_RENDER_PROFILE` is an alias of the current profile.
  - `require_profile` accepts only the current profile.
- `backend/app/infrastructure/rendering/ffmpeg.py:103-115` runs one FFmpeg pass. It uses
  the concat demuxer, maps `0:v:0`, passes `-an`, and writes MP4.
  `RENDER_INPUT_FORMATS` is the per-file demuxer allowlist.
- `backend/app/infrastructure/rendering/execution.py:51` calls `ffmpeg.render` once per
  plan. The sidecar manifest records the profile ID and version (`:61-62`).
- `backend/app/api/v1/rendering.py:33-34`:
  - `profile_version: Literal["1", "2"] = "2"`;
  - a v1 request is refused with a bounded 409.
- `frontend/src/experience/output-actions.ts:58` hardcodes `profile_version: "2"`.
  - Once the backend refuses v2, this breaks the Producer render action, so this
    directive must change it.
  - `frontend/src/experience/ui-labels.ts:53-55` labels the profile "1080p (vN)".
- `backend/app/demo/render_worker.py:78-83`: the worker declares and runs
  `CURRENT_RENDER_PROFILE`.
- `backend/app/core/config/deployment.py:113-121`: `LocalRenderConfiguration` has
  `ffmpeg_path`, `output_root`, and `packaging_content_root`, and no `ffprobe_path`.
  `LocalMediaTimingConfiguration` already validates an explicit `ffprobe_path` (`:140`).
- `backend/app/infrastructure/media_timing/ffprobe.py`: `FFprobeAdapter` runs
  `-show_format -show_streams` with an identity check. It reads only the video stream
  today.
- Profile identity is stored as text in `render_operation_input` and `rendered_output`,
  where the checks require only non-blank values (`0015_render_durable_operation_forward.sql`).
  No migration is needed. Verify this during implementation.

## Desired behavior

- The current profile becomes **version `"3"`**:
  - v2 video settings;
  - one audio stream, recorded as first-class profile fields: codec `aac` (FFmpeg
    native), 48,000 Hz, 2 channels, 192,000 bit/s.
- New renders use v3. A v1 or v2 request is refused with the typed
  `render_profile_unsupported` code, returned by the API as a bounded 409.
- For each input, the audio source is the first audio stream, resampled to 48 kHz
  stereo, with no gain, normalization, or mixing. An input without an audio stream
  contributes digital silence for its full video duration.
- Per input, the audio is padded or trimmed to that input's rendered video duration, so
  sync never depends on how inputs are joined.
- The registered output must contain exactly one H.264 video stream and one AAC audio
  stream. Otherwise the render fails with `render_output_invalid` and the output is not
  registered.
- Workers declare and claim only v3. Pending v1 or v2 work is never claimed, as under
  ED-0089.
- The Producer render action requests v3, and the profile label shows that audio is
  present.

## In scope

1. Contracts:
   - replace `audio: Literal[False]` with first-class audio fields: codec, sample rate,
     channels, and bit rate. A v1/v2 value records "no audio";
   - `CURRENT_RENDER_PROFILE` becomes v3;
   - add `RENDER_PROFILE_V2` as a recorded identity;
   - remove the `FIRST_RENDER_PROFILE` alias and move its test callers to
     `CURRENT_RENDER_PROFILE`. This is the ED-0089 remaining work, and its removal
     condition is under our control.
2. Configuration: an optional `[local_render] ffprobe_path`, validated like the existing
   path fields.
   - The render worker refuses to start with a bounded configuration message when it is
     absent. The API and other workers are unaffected.
   - Existing configuration files stay valid.
3. Input audio facts: the render execution checks each resolved input with `FFprobeAdapter`
   (or a small extension of it that also reports whether an audio stream exists) before
   encoding. The same demuxer allowlist as the FFmpeg inputs applies. A probe failure is
   a typed `input_missing` or `render_internal_error`, never a silent "no audio".
4. FFmpeg adapter: two stages, with the video encoded exactly once.
   - **Stage 1, per input:**
     - Video: CUDA decode → `scale_cuda` → constant 30000/1001 → `h264_nvenc` with the v2
       settings.
     - Audio: `[k:a:0]` → `aresample=48000` → stereo `aformat`, or an `anullsrc` 48 kHz
       stereo source for an input without audio. Either is padded and trimmed to the
       segment's video duration (`apad` with `-shortest`, or an explicit `atrim`).
     - The audio is written as 16-bit PCM into an intermediate MOV or Matroska file in
       the store's temp directory.
   - **Stage 2:**
     - The concat demuxer over the intermediates, with `-c:v copy` and one native `aac`
       encode at 192 kbit/s. This avoids a priming gap at every join. Output is MP4.
   - Every stage keeps the existing guarantees: the identity check, `shell=False`,
     argument lists built only from constants and validated integers, heartbeats during
     every stage, the CUDA-fallback and NVENC failure mapping, and intermediates deleted
     on success and failure.
   - Frame count and duration are read from stage 2. The adapter confirms one video
     stream and one audio stream in the output, using ffprobe, before registration.
5. API: `profile_version` accepts `"1" | "2" | "3"` and defaults to `"3"`. v1 and v2 are
   refused as above.
6. Worker capability and claims use v3.
7. Frontend:
   - `output-actions.ts` sends `profile_version: "3"`;
   - `renderProfileLabel` shows audio for v3, for example "1080p with audio (v3)", with
     the wording in `ui-labels.ts`;
   - v1 and v2 history still shows the video-only label.
8. Tests: see Test strategy.
9. Documentation:
   - the rendering README and `post-kernel-capability-layer.md` render section (profile
     v3 and the two-stage encode);
   - the glossary Render Profile entry (v3, audio) and the "UI wording" table row;
   - `backend/app/core/config/README.md` (`ffprobe_path`).
10. **Owner step:** render validation Run 003 on the reference GPU. See Acceptance
    criteria.

## Out of scope

- Per-Event quality selection, presets, and bitrate adjustments (ED-0099).
- Loudness normalization, gain, audio mixing, choosing a track other than the first,
  multi-language audio, surround output, and overlays.
- Other video settings. Migrating, rewriting, or deleting v1 or v2 outputs or operations.
- Changes to the media timing worker or its evidence.

## Constraints

- No dependency and no migration. Offline. No paths, stderr, or media content stored or
  logged.
- The FFmpeg identity check is unchanged. No encoder other than the native `aac` is named.
- Contracts are immutable. White-label naming.
- No existing assertion changes, except where a test pins the *current default* version
  `"2"` or asserts `-an`. List each changed assertion in the report.

## Implementation approach

1. Contracts, config, and the alias removal, with unit tests.
2. The input audio-facts probe, with fake-ffprobe tests.
3. The two-stage adapter, with fake-FFmpeg argument tests for:
   - inputs with and without audio;
   - mixed sample rates and layouts;
   - cleanup on failure in either stage.
4. API, worker, and frontend switch to v3 together, so the UI and API never disagree.
5. Documentation.

Each step can be reverted on its own until step 4.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `backend/app/contexts/rendering/contracts.py` | Audio fields, v3 current, v2 recorded, alias removed |
| `backend/app/core/config/deployment.py` (+ README) | Optional `[local_render] ffprobe_path` |
| `backend/app/infrastructure/media_timing/ffprobe.py` or `infrastructure/rendering/` | Audio-stream presence and output stream check |
| `backend/app/infrastructure/rendering/ffmpeg.py`, `execution.py` | Two-stage encode, intermediates, output stream check |
| `backend/app/api/v1/rendering.py` | v3 default; v1 and v2 refused |
| `backend/app/demo/render_worker.py` | v3 capability; ffprobe required at startup |
| `backend/tests/test_render_profile_v3.py` (new), existing render tests | See Test strategy |
| `frontend/src/experience/output-actions.ts`, `ui-labels.ts` (+ tests) | Request v3; label |
| Rendering README, capability layer, glossary | Profile v3 |

## Data or migration considerations

None. Profile identity is text, and the checks accept any non-blank token. Verify this,
and stop if any check pins `"1"` or `"2"`. The sidecar manifest shape is unchanged: it
already records the profile ID and version, and the version now implies audio.

## Failure and recovery considerations

- A stage 1 or stage 2 failure is a typed attempt outcome under the existing codes:
  `ffmpeg_exit_nonzero` (retryable), `cuda_decode_fallback`, `nvenc_unavailable`, and
  `render_output_invalid`. A new code is added only if a failure cannot map to these;
  record any such addition.
- Intermediates live only in the store's temp directory. They are removed on success,
  failure, and cancellation, and are never registered. A worker restart leaves at most
  temp files, which the existing temp handling covers. Verify this, and extend the
  cleanup to intermediates if needed.
- Temp disk use is about twice the output size during stage 2. Record this in the
  rendering README as an operator note.

## Observability requirements

- API listings and the sidecar manifest show profile v3.
- Failure reason codes stay bounded.
- The worker's startup refusal names the missing `ffprobe_path` setting without printing
  any path.

## Test strategy

- Contracts:
  - v3 fields;
  - v1 and v2 are recorded but refused;
  - audio fields are immutable and of the exact type.
- Config:
  - `ffprobe_path` is optional and validated;
  - the worker refuses to start without it, and the API still starts.
- Adapter, with fake binaries:
  - stage 1 arguments for an input with audio and an input without (`anullsrc`), padding
    to the video duration, 48 kHz stereo;
  - stage 2 uses `-c:v copy` and `aac` at 192 kbit/s;
  - no `-an`;
  - heartbeats run in every stage;
  - intermediates are cleaned up on stage 1 failure, stage 2 failure, and cancellation;
  - an output without an audio stream is `render_output_invalid` and is not registered;
  - no caller text reaches the arguments.
- Service and API:
  - the default is v3;
  - v1 and v2 requests get a bounded 409;
  - v3 on a revision rendered at v2 creates a new operation;
  - v1 and v2 outputs still list.
- Worker: v3 capability and claim matching. v2 pending work is not claimed.
- Frontend:
  - the render action body carries `"3"`;
  - the label for v3 and for v1/v2 history.
- Quality gate:
  - the full host backend suite, Ruff, and Pyright;
  - frontend build, lint, typecheck, and test;
  - `git diff --check`.

## Acceptance criteria

- [ ] New renders use v3. v1 and v2 are refused with a typed error, and their history
  still reads.
- [ ] The Producer render action works end to end against v3.
- [ ] All required checks pass. No migration and no dependency were added.
- [ ] **Run 003** on the reference GPU. Media must be synthetic or already-approved
  validation media, and no media paths or names are recorded.
  - Revision A: synthetic inputs generated with FFmpeg `lavfi`. Each carries a timed
    beep and a white flash at the same instants. The set includes one input with no
    audio and one input at 44.1 kHz mono.
  - Revision B: the Run 002 validation revision.
  - A must show:
    - exactly one H.264 video stream and one AAC-LC 48 kHz stereo audio stream;
    - audio and video onsets within **±40 ms** at every marker, including after the
      last join;
    - digital silence across the silent input.
  - B must show:
    - audio duration within ±40 ms of video duration;
    - a full decode without warnings;
    - 0 duplicate timestamps.
  - Both: re-rendering the same revision produces a byte-identical SHA-256, which keeps
    ED-0078 determinism.
  - Throughput is recorded against Run 002, with any change explained.

## Rollback or reversal

- Revert the code. There is no data change.
- v3 outputs stay readable as recorded history.
- The optional `ffprobe_path` setting is ignored by older code only if it is removed from
  configuration first. The configuration model forbids extra keys, so remove it before
  rolling back.

## Open questions

- None. The ±40 ms sync tolerance is a validation threshold chosen by this plan. It is
  about one video frame plus one AAC frame. It is not an owner decision; tighten it if
  Run 003 shows room.

## Completion record

- Implemented revision:
- Files and migrations actually changed:
- Commands and tests actually run:
- Results and warnings:
- Execution authority used:
- Approved deviations:
- Rollback status:
- Remaining work:
