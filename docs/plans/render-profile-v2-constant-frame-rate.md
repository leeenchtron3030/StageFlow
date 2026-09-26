# Render profile v2: constant output frame rate

## Status

Completed (2026-09-26).

## Execution authority

- Classification: Green autonomous, under the owner's decision of 2026-09-26 and ADR-0032
  amendment 3.
- Authority evidence:
  - The owner decided on 2026-09-26, on the Yellow escalation "mixed input frame rates",
    to adopt a **profile v2 with a constant output frame rate**. The change needs a small
    ADR-0032 amendment and a throughput re-check. v1 stays recorded.
  - [ADR-0032](../adr/ADR-0032-render-durable-operation.md) decision 5 and amendment 3.
  - Evidence: [render validation Run 001](../validation/results/render-durable-operation-001.md),
    finding 1.
- Implementation-ready: Yes.
- Required escalation: stop if this would change any setting other than the output frame
  rate mode, add audio, overlays, or profiles beyond v2, change migrations, or change
  Assembly semantics.
- Engineering Directive: **ED-0089**. The owner delegated ED numbering.

## Preserved accepted decisions

- ADR-0032:
  - one current profile;
  - video only, with no overlays;
  - H.264 `h264_nvenc`, preset p4, VBR at 8 Mbit/s, GOP 60, 1080p, MP4, CUDA decode;
  - the opaque key plus SHA-256 identity;
  - one lease per GPU;
  - human-only authority.
- ED-0087 decision (a): the work key is the revision plus the profile ID and version, so
  a **v2 request for a revision already rendered with v1 is a new operation**. This is the
  intended way to re-render existing revisions under v2.
- Rendered Outputs recorded under v1 stay valid and readable. Their profile identity is
  never rewritten.

## Problem statement

Profile v1 uses `-fps_mode passthrough`. When inputs have slightly different frame rates,
for example a 30000/1001 bumper next to 2997/100 recordings, the output contains duplicate
presentation timestamps. Run 001 had 22 of them in 19,850 frames, and a player drops those
frames. Real bumpers almost always differ slightly from the recorder's rate.

## Verified current behavior

- `backend/app/contexts/rendering/contracts.py`:
  - `RenderProfile` defaults to ID `h264-nvenc-1080p-video`, version `"1"`;
  - `require_profile` accepts only `FIRST_RENDER_PROFILE`.
- `backend/app/infrastructure/rendering/ffmpeg.py:106` passes
  `-fps_mode passthrough` and has no output rate.
- `backend/app/api/v1/rendering.py:33-34`: the request model has
  `profile_version: Literal["1"] = "1"`.
- The render worker declares a capability for `FIRST_RENDER_PROFILE`, and claims match on
  the execution profile ID and version.
- Run 001, confirmed in isolation: mismatched rates gave 6 duplicates over three blocks,
  and matched rates gave 0.

## Desired behavior

- The current profile becomes **version `"2"`**:
  - identical to v1 except for the output frame rate: a constant `30000/1001`, set with
    `-fps_mode cfr -r 30000/1001` (or the equivalent `fps` filter kept on the GPU path if
    that is required);
  - the profile contract records the output frame rate as a first-class field.
- A new `request_render` uses v2 by default.
- A request that names v1 fails with the existing typed `render_profile_unsupported`, and
  the API returns it as a bounded error instead of a validation crash.
- Workers declare and claim only v2. Any v1 operation still pending when the upgrade
  happens stays visible and is never claimed, leased, or attempted by a v2 worker. The
  shared ADR-0025 substrate may still promote it from `pending` to `eligible`, as it does
  for all due work (owner clarification during implementation). The deployment has
  none.
- Rendered Outputs record `render_profile_version = "2"`. The sidecar manifest carries the
  profile version, as it already does.

## In scope

1. Rendering contracts:
   - add `output_frame_rate` to `RenderProfile` (a `Fraction` or a numerator/denominator
     pair, immutable);
   - `FIRST_RENDER_PROFILE` is renamed or aliased to `CURRENT_RENDER_PROFILE` = v2;
   - keep a `RENDER_PROFILE_V1` constant only as a recorded identity. It cannot be
     requested.
2. FFmpeg adapter: constant-frame-rate output at the profile rate. Frame-count parsing and
   the CUDA-fallback guard are unchanged.
3. API: `profile_version` defaults to `"2"`. The literal widens to `"1" | "2"` so that a
   v1 request reaches the typed `render_profile_unsupported` refusal.
4. Worker capability and claims use v2.
5. Tests:
   - v2 argument construction, including CFR and the rate, with the fake FFmpeg;
   - v1 requests are refused with a typed error at both the service and the API;
   - replay idempotency per version: v2 on a revision rendered with v1 creates a new
     operation;
   - v1 outputs still hydrate and list;
   - worker capability and claim matching for v2.
6. Documentation:
   - the ADR-0032 amendment 3 (already in the plan PR);
   - the rendering README and capability layer (profile v2);
   - the glossary entry for Render Profile, if it names the version.
7. **Owner step:** re-render the Run 001 validation revision with v2 on the reference GPU.
   Record Run 002 with:
   - **0 duplicate PTS** and monotonic timestamps;
   - a full decode;
   - a duration within one frame of the input sum;
   - throughput compared with Run 001 (58.5 s wall for 662 s of output).

## Out of scope

- Audio, overlays, other frame rates, other resolutions, more profiles, per-Event profile
  selection, and changes to the bitrate ladder.
- Migrating, rewriting, or deleting any v1 Rendered Output or operation.

## Constraints

- No dependency. Offline. No paths or stderr stored.
- Contracts are immutable. White-label naming.
- No migration: profile ID and version are already stored as text columns.
- No existing assertion changes, except tests that pin the profile version literal `"1"`
  as the *current* default. Those may change to `"2"` only where they assert the default.
  List each one changed in the report.

## Data or migration considerations

None. Profile identity is stored as text, and the existing check constraints accept any
bounded token. Verify this during implementation, and stop if a check pins `"1"`.

## Failure and recovery considerations

The failure codes are unchanged. If constant-frame-rate filtering forces a CPU fallback,
that is covered by the existing CUDA-fallback guard and is a typed failure, not a silent
slowdown.

## Observability requirements

API listings and the sidecar manifest show each output's profile version.

## Test strategy

The tests are listed under In scope, item 5. The quality gate is the full host backend
suite, Ruff, and Pyright. The owner's GPU re-render is Run 002.

## Acceptance criteria

- [ ] New renders use v2 with a constant 30000/1001 output. v1 is refused with a typed
  error, and v1 history still reads.
- [ ] Tests pass. The full host backend suite, Ruff, and Pyright pass, and the frontend is
  unchanged.
- [ ] Run 002 on the reference GPU shows 0 duplicate PTS, a full decode, the expected
  duration, and throughput recorded against Run 001.

## Rollback

Revert the code. No data changes. v2 outputs stay readable as recorded history.

## Completion record

- **Implemented revision:** branch `codex/ed-0089-render-profile-v2`, stacked on ED-0088.
  Codex implemented it and the owner committed it.
- **Files changed:**
  - rendering contracts: `output_frame_rate`, `CURRENT_RENDER_PROFILE` v2,
    `RENDER_PROFILE_V1`, and a `FIRST_RENDER_PROFILE` alias used only by tests;
  - the FFmpeg adapter: `-fps_mode cfr -r 30000/1001`;
  - the API: v2 default, v1 refused with a bounded 409;
  - the render worker and repository: v2 capability and claims;
  - `tests/test_render_profile_v2.py` and additions to `tests/test_rendering_phase_b.py`;
  - the rendering README, the capability layer, and the glossary.
- **Plan clarification** (the owner's): Codex stopped Yellow because the shared ADR-0025
  substrate promotes due pending work to `eligible` before matching capabilities. The
  guarantee was restated: v1 work is never claimed, leased, or attempted by a v2 worker.
  The substrate is unchanged.
- **Review:** the `directive-reviewer` returned FIX-FIRST for two missing negative tests
  (non-Fraction rate; unknown output profile version). The owner added them, plus an
  assertion that `-r` is an output option. No existing assertion was changed.
- **Tests:** host full suite **2,337 passed, 0 failed, 2 skipped** before the added
  assertions. Afterwards the rendering files passed 51 of 51, and Ruff and Pyright are
  clean.
- **Owner real-GPU render:** see
  [Run 002](../validation/results/render-durable-operation-002.md).
  - 0 duplicate timestamps (Run 001 had 22), 0 decode warnings, and identity checks pass.
  - The literal "within one frame of the input sum" criterion is **not met**: the output
    is 0.334 s short of the naive per-file sum. v1 was 0.40 s short by the same measure,
    and v2 differs from v1 by +0.067 s. Run 002 explains this as concat timestamp joining.
- **Deviations:** the frame count is no longer equal to the input frame sum (19,842 against
  19,850). This is expected with constant-rate output.
- **Remaining work:** remove the `FIRST_RENDER_PROFILE` alias once the tests use the current
  name.
