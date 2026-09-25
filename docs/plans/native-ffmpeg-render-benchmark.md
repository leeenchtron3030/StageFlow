# Native FFmpeg render benchmark

## Status

Approved

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
- **Corpus amendment (2026-09-25).** The owner selected the Demo 2 **dress-rehearsal**
  corpus (recorded 2026-08-25) rather than the live-run folder, which had since acquired an
  unrelated later recording. The dress corpus is five closed blocks — four full blocks plus
  a short final block, roughly four minutes of footage. Because it differs from ED-0073's
  eleven-block corpus, this plan adds a same-corpus PyAV baseline arm. The absolute path
  stays out of the repository and is supplied to the implementer directly.

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
- **Same-corpus PyAV baseline:** re-run ED-0073's existing PyAV NVENC arm over the same
  corpus, once, so native and PyAV throughput are compared like-for-like inside this run.
  ED-0073's own numbers are cited as context only, because they come from a different
  corpus.
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

- [ ] Native subcommands invoke FFmpeg through an explicit path and record its version,
  SHA-256, and GPL-configuration status; no `PATH` dependency.
- [ ] Arms 1 and 2 are each measured three times over the Demo 2 corpus, with wall-clock
  time, real-time factor, frame count, output size, and SSIM/PSNR recorded.
- [ ] The concurrency arm is measured with its actual overlap window reported.
- [ ] A same-corpus PyAV baseline is measured, and the result compares native arms with it,
  citing ED-0073 as different-corpus context, and states whether the native pipeline changes
  the throughput conclusion.
- [ ] The result states the corpus's roughly four-minute length as a limitation for the
  sustained-load and concurrency arms.
- [ ] The result states which arms were executed inside and outside any sandbox.
- [ ] No production code, repository dependency, schema, migration, or runtime
  configuration changed.
- [ ] The result explicitly states it is first-order sizing input, not a throughput
  guarantee or hardware qualification.

## Rollback or reversal

Remove the native subcommands, tests, and result document. The FFmpeg CLI can be removed
with `winget uninstall BtbN.FFmpeg.LGPL.8.1`; nothing in the repository depends on it.

## Open questions

- Whether the operator will supply a full-Session corpus for the optional long-corpus arm.

## Completion record

_(To be filled in by whoever implements this plan.)_
