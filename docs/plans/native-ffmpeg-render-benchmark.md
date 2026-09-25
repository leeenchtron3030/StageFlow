# Native FFmpeg render benchmark

## Status

Completed (2026-09-25). Harness implemented and sandbox-validated; all measurement arms
executed on the reference host. See the [result](../validation/results/render-benchmark-002.md)
and the completion record.

## Execution authority

- Classification: Green autonomous — qualification tooling only, no production code.
- Authority evidence: [ADR-0029](../adr/ADR-0029-nvenc-rendering-and-gpu-worker-requirement.md),
  which selects NVENC and names a bounded rendering benchmark as the next evidence step;
  the [ED-0073 result](../validation/results/render-benchmark-001.md), whose own
  interpretation and dated review note state that its harness measured Python/PyAV frame
  iteration rather than NVENC, and that "a native FFmpeg pipeline arm … is required before
  any encode-throughput or fleet-sizing figure is derived"; the owner's 2026-09-24 choice to
  install a standalone FFmpeg CLI for qualification.
- Implementation-ready: Yes.
- Required escalation or approval, if any: none for a measurement harness. Stop and
  escalate if this appears to require production render code, a Render Durable Operation,
  a Worker Capability change, a repository dependency, or a product decision about output
  format, bitrate ladder, or audio.

## Related findings or ADRs

- ADR: ADR-0029 (NVENC), ADR-0025 (worker/capability model a renderer will later use).
- Finding: ED-0073 established NVENC availability and negligible quality cost, but its
  throughput figures are harness-bound and unusable for fleet sizing.
- Security/licensing: the [SBOM decision record](../security/dependency-license-sbom-2026-08-21.md)
  names an LGPL-only FFmpeg build as the intended direction for any distributed artifact.
- Engineering Directive: ED-0078. Follows ED-0073. (ED-0077 is reserved for Session
  Assembly.)

## Problem statement

StageFlow still has no usable measurement of how fast it can render. ED-0073 timed a
per-frame Python loop — software decode, per-frame `reformat()`, then encode — so its
435-second NVENC result reflects the harness, not the encoder. Packaging speed is a stated
product priority, and render-fleet sizing depends on a real throughput number.

## Verified current behavior

- `backend/tests/qualification/render_benchmark.py` (ED-0073) provides corpus discovery,
  probing, SSIM/PSNR quality measurement, external-path safety, and sanitized reporting,
  all through PyAV. It has no native FFmpeg path.
- A standalone FFmpeg CLI was installed on the reference host on 2026-09-24 via winget
  package `BtbN.FFmpeg.LGPL.8.1`: version `n8.1.2`, configured without `--enable-gpl` and
  with `--disable-libx264` and `--disable-libx265`, providing `h264_nvenc`, `hevc_nvenc`,
  `av1_nvenc`, and the `cuda` hardware accelerator. It is a machine tool, not a repository
  dependency.
- Its FFmpeg version, 8.1.2, matches the libraries bundled inside PyAV, so native and ED-0073
  results differ in pipeline, not FFmpeg version.
- The Demo 2 recorded-block corpus used by ED-0073 remains available outside the
  repository.
- **Corpus (confirmed 2026-09-25).** The corpus is the Demo 2 **live-run** recording of
  2026-08-26: eleven closed, continuous blocks of about one minute each, which matches
  ED-0073's eleven-block, 19,700-frame corpus, so results are directly comparable with
  ED-0073. The live-run folder has since acquired one unrelated later recording
  (2026-09-21); it must be excluded so the corpus is exactly the eleven blocks. A
  dress-rehearsal corpus was briefly selected and then withdrawn by the owner in favour of
  this one. The absolute path stays out of the repository and is supplied to the
  implementer directly.

## Desired behavior

The harness measures real NVENC render throughput through FFmpeg's native pipeline, with
decode, scaling, and encode kept inside FFmpeg, and records a sanitized result usable as
first-order input to render-fleet sizing.

## In scope

- Extend `render_benchmark.py` with native subcommands that invoke FFmpeg through
  `subprocess` using an **explicit `--ffmpeg` executable path** argument — never a bare
  `ffmpeg` resolved from `PATH` — and that record the binary's version string, SHA-256, and
  whether its configuration contains `--enable-gpl`.
- Native arms, all over the same corpus, video-only, at ED-0073's bitrate and GOP settings
  for comparability:
  1. **CPU decode → NVENC**, using the FFmpeg concat demuxer.
  2. **CUDA decode → NVENC**, with frames kept on the GPU (`-hwaccel cuda
     -hwaccel_output_format cuda`, GPU scaling only if needed).
  3. **Repeat** each of the above three times to report variance, not a single sample.
  4. **Concurrency**: arm 2 run while a real CUDA transcription job runs, reporting the
     actual overlap window.
- **Same-run PyAV baseline:** re-run ED-0073's existing PyAV NVENC arm over the same
  corpus, once. The corpus matches ED-0073's, so this controls only for environment drift
  since ED-0073 (driver, thermal state, background load) and lets native and PyAV
  throughput be compared within one run. Report it alongside ED-0073's figures.
- Quality: SSIM and PSNR of each native output against the source blocks, using the
  existing ED-0073 measurement for comparability.
- Optional **long-corpus arm** if the operator supplies a full-Session block folder:
  arm 2 repeated over it, to observe sustained behaviour. Not required for completion.
- A sanitized result, `docs/validation/results/render-benchmark-002.md`, comparing the
  native arms with ED-0073's PyAV arm, and focused harness tests.

## Out of scope

- Production rendering code, a `RenderRequest` Durable Operation, a Worker Capability,
  Assembly, or delivery.
- Adding FFmpeg, or any package, as a repository or runtime dependency.
- libx264 or any GPL encoder. The installed build deliberately omits them, and ADR-0029
  already selected NVENC.
- Audio encoding, output format, container, bitrate-ladder, or quality-tier decisions.
- NAS transfer measurement; resolving the PyAV/FFmpeg distribution question.

## Constraints

- Offline measurement tooling: never run during live capture.
- Real media stays outside Git; no media, media paths, or transcript content in results.
- The harness must not depend on `PATH` or on this machine's install location; the FFmpeg
  path is an explicit argument, recorded only by version and hash, never by path.
- Honesty: single-machine, single-corpus measurement is first-order sizing input, not a
  throughput guarantee or hardware qualification. Report every repetition, including
  outliers.

## Implementation approach

1. Add FFmpeg-binary identification: version, configuration GPL check, SHA-256.
2. Add native encode subcommands for arms 1 and 2 that build the concat list and FFmpeg
   command, time the whole FFmpeg process, and parse its reported frame count.
3. Add a repetition driver and variance summary.
4. Add the native concurrency arm, reusing ED-0073's transcription job and barrier.
5. Reuse the ED-0073 quality measurement on native outputs.
6. Add focused tests that do not require a GPU or FFmpeg: command construction, explicit
   path handling, GPL-flag detection, frame-count parsing, variance arithmetic, and
   repository-output refusal.
7. Run the arms on the reference host and write the sanitized result.

Real-corpus arms need GPU access. If a sandboxed implementer cannot reach the GPU, the
harness and tests may be implemented in the sandbox and the measurement arms executed by
the owner outside it; the result must say which.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `backend/tests/qualification/render_benchmark.py` | Native FFmpeg subcommands |
| `backend/tests/qualification/test_render_benchmark.py` | Focused tests for the native path |
| `docs/validation/results/render-benchmark-002.md` | Sanitized result (new) |
| `docs/validation/README.md` | Index the new result |

No production package, repository dependency, schema, migration, or runtime configuration
change.

## Data or migration considerations

None.

## Failure and recovery considerations

- If CUDA decode or NVENC fails, record the exact failure and do not fall back silently.
- A failed repetition is reported, not discarded.
- The harness never modifies or deletes source blocks.

## Observability requirements

Record per run: arm, FFmpeg version and hash, input block count and duration, encoder
settings, wall-clock time, real-time factor, encoded frame count, output size, and
quality. GPU samples, if captured, are diagnostic only.

## Test strategy

- Focused tests without a GPU or FFmpeg, as listed above.
- Real-corpus runs on the reference host produce the measurements.
- Ruff and Pyright on the changed tooling; full backend suite for regressions.

## Acceptance criteria

- [x] Native subcommands invoke FFmpeg through an explicit path and record its version,
  SHA-256, and GPL-configuration status; no `PATH` dependency.
- [x] Arms 1 and 2 are each measured three times over the Demo 2 corpus, with wall-clock
  time, real-time factor, frame count, output size, and SSIM/PSNR recorded.
- [x] The concurrency arm is measured with its actual overlap window reported.
- [x] The corpus is exactly the eleven 2026-08-26 live-run blocks; the unrelated later
  recording is excluded.
- [x] A same-run PyAV baseline is measured, and the result compares native arms with it and
  with ED-0073, and states whether the native pipeline changes the throughput conclusion.
- [x] The result states which arms were executed inside and outside any sandbox.
- [x] No production code, repository dependency, schema, migration, or runtime
  configuration changed.
- [x] The result explicitly states it is first-order sizing input, not a throughput
  guarantee or hardware qualification.

## Rollback or reversal

Remove the native subcommands, tests, and result document. The FFmpeg CLI can be removed
with `winget uninstall BtbN.FFmpeg.LGPL.8.1`; nothing in the repository depends on it.

## Open questions

- Whether the operator will supply a full-Session corpus for the optional long-corpus arm.
  *Resolved 2026-09-25:* none was supplied; the optional arm was not run.

## Completion record

Implemented 2026-09-25 under ED-0078, Green authority, on
`codex/ed-0078-native-ffmpeg-render-benchmark`.

**Harness (sandboxed implementer, no GPU, FFmpeg, or corpus access).**

- Extended `render_benchmark.py` with `native-cpu-nvenc`, `native-cuda-nvenc`, and
  `native-concurrent` subcommands. FFmpeg is invoked through an explicit `--ffmpeg` path
  as an argument list and identified by version, SHA-256, and GPL-configuration flag; GPL
  builds are refused and the path never reaches a report.
- Repetitions default to 3 (bounded 1-10). Each writes its own output and records wall
  clock, real-time factor, source speed, encoded frame count, output size, exit status,
  and SSIM/PSNR through the ED-0073 measurement; failed repetitions are kept with typed
  codes. Population variance is reported.
- `native-concurrent` reuses the ED-0073 transcription job, barrier, and overlap
  arithmetic, and rejects a baseline whose corpus, FFmpeg hash, bitrate, GOP, or GPU
  pixel-conversion setting differs.
- ED-0073 subcommands, defaults, and harness-1.0 reports are unchanged.

**Independent review and corrections.**

- An independent review returned FIX-FIRST with three findings:
  - a logged CUDA hwaccel failure could fall back to software decode while reporting
    success;
  - the concurrency baseline was only partly validated;
  - `real_time_factor` was inverted relative to ED-0073. The directive had stated the
    inverse formula, which was an owner error; the legacy meaning now applies.
- All three were fixed with tests, along with three minor items: LF concat lists,
  terminal-only FFmpeg stderr on failure, and transcription-settings parity. A re-review
  approved the result.
- The fallback guard is log-based; its limit is stated in the result.

**Validation.**

- Focused `tests/qualification/test_render_benchmark.py`: **84 passed** in the sandbox
  and on the host.
- Ruff passed, and Pyright reported 0 errors and 0 warnings.
- Host full suite, run with `STAGEFLOW_API_SHARED_SECRET` and `VIRTUAL_ENV` cleared and
  `uv run --no-sync`, before the review fixes: **2,024 passed, 5 failed, 2 skipped.**
  - Four failures are the known Windows console-encoding cases in
    `test_validation_controller.py::test_turnover_boundaries_emit_exact_live_operation_checkpoints`.
  - The fifth,
    `test_devcon_session_publish.py::test_devcon_no_body_response_maps_to_bounded_reason_without_retry`,
    is an intermittent local-HTTP-server test. It passed when rerun in isolation on both
    this branch and `main`.
  - The review fixes changed only the two qualification files, and the focused suite
    covers them.
- A real-FFmpeg smoke test on synthetic clips, in a folder whose path contains a space
  and a single quote, succeeded for both native arms before the corpus run.

**Measurement (owner, on the reference host outside any sandbox).**

- All arms ran over the eleven-block corpus. Its fingerprint matches ED-0073's exactly.
- Native CPU decode ran three times and native CUDA decode ran three times. The
  concurrency arm and the same-run PyAV baseline ran once each.
- Every arm succeeded, with no failed or discarded repetition and no fallback.
- The sanitized result is
  [render-benchmark-002](../validation/results/render-benchmark-002.md); the raw reports
  stay outside the repository and are identified by SHA-256.
- The optional long-corpus arm was not run.

**Scope and remaining decisions.**

- No production code, repository dependency, schema, migration, or runtime configuration
  changed. The FFmpeg CLI remains a machine tool.
- No product or architecture decision is open. The result names multi-encode
  per-GPU scaling as the next sizing evidence gap, but does not authorize that work.
