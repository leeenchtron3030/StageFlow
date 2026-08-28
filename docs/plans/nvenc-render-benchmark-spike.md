# NVENC render benchmark spike

## Status

Approved

## Execution authority

- Classification: Green autonomous — qualification tooling only, no production code.
- Authority evidence: [ADR-0029](../adr/ADR-0029-nvenc-rendering-and-gpu-worker-requirement.md)
  selects NVENC as StageFlow's rendering encode path and explicitly names "a future
  bounded rendering spike (concatenate real recorded blocks, measure NVENC wall-clock
  time and quality against libx264, and measure behavior concurrent with a live CUDA
  transcription job)" as the recommended next evidence step; the established
  qualification-tooling precedent under `backend/tests/qualification/`
  ([real-event playback validation](real-event-playback-validation.md),
  [transcription engine evaluation](transcription-engine-evaluation.md)), which added
  measurement harnesses without touching production packages.
- Implementation-ready: Yes.
- Required escalation or approval, if any: none for a measurement harness. Stop and
  escalate if this appears to require production render code, an Assembly contract, a
  dependency change, or a decision on the open PyAV/FFmpeg licensing question — none are
  in scope.

## Related findings or ADRs

- ADR: ADR-0029 (NVENC decision), ADR-0025 (durable worker/capability model this would
  eventually plug into).
- Finding: no rendering evidence of any kind exists. The project's stated packaging-speed
  priority currently rests on zero measured data, which is the gap this spike closes.
- Engineering Directive: ED-0073.

## Problem statement

ADR-0029 chose NVENC over libx264 on architectural and licensing grounds, but StageFlow
has never encoded a single frame. There is no measurement of how long it takes to produce
a rendered output from a Session's recording blocks, no comparison against the software
alternative, and no evidence about whether rendering can run concurrently with CUDA
transcription on one worker. Packaging speed is a stated product priority resting
entirely on assumption.

## Verified current behavior

- No rendering, concatenation, or encoding code exists anywhere in the repository.
- `h264_nvenc`, `hevc_nvenc`, `av1_nvenc`, and `libx264` are all already available in the
  installed PyAV/FFmpeg build (confirmed 2026-08-28), so both arms of the comparison are
  reachable without any dependency change.
- Real vMix-recorded rolling blocks from the Demo 1/Demo 2 rehearsals exist outside the
  repository on the reference host.
- The existing qualification harnesses establish the pattern: explicit finite CLI
  subcommands, run records written outside the repository, no production package changes.

## Desired behavior

A bounded, validation-only harness concatenates a real Session's recorded blocks and
encodes them with both NVENC and libx264, recording wall-clock time, output size, and a
comparable quality measure — plus one run performed concurrently with a CUDA
transcription job to observe contention. The result is StageFlow's first real rendering
evidence, recorded as a sanitized validation result.

## In scope

- One qualification-only module under `backend/tests/qualification/` with explicit finite
  subcommands, following the existing harness conventions.
- Measurement of: wall-clock encode time, real-time factor, output file size, and a
  quality measure for NVENC and libx264 over the same real input blocks. **The measure is
  SSIM, with PSNR secondary** — the installed FFmpeg build provides `ssim`, `psnr`, and
  `xpsnr` but not full `libvmaf` (verified 2026-08-28), so VMAF is unavailable.
- The reference for the quality measure is **the source vMix blocks themselves**. No
  pristine or unencoded master is required: StageFlow's real input is the vMix recording,
  so the operative question is how much fidelity is lost re-encoding what StageFlow
  actually receives.
- One concurrency run: encode while a CUDA transcription job runs, recording whether
  either degrades.
- A sanitized validation result under `docs/validation/results/`, containing no media
  paths, no media, and no transcript content.
- Focused tests for the harness itself, matching how existing qualification tooling is
  tested.

## Out of scope

- Any production rendering code, Assembly contract, `RenderRequest` Durable Operation, or
  Worker Capability change. This measures; it does not build the capability.
- Selecting output format, bitrate ladder, container, or branding/template semantics as
  product decisions. Benchmark parameters are measurement inputs, not accepted defaults.
- Resolving the PyAV/FFmpeg licensing question. The spike may use the libx264 already
  present locally for comparison; that is local measurement, not distribution.
- NAS transfer measurement. ADR-0029 flags it as a separate unknown; keep it separate.
- Any change to dependencies, schema, migrations, or runtime configuration.

## Constraints

- Production priority: if run on a machine doing anything capture-critical, the harness
  must not be run during live capture. It is offline measurement tooling.
- Media handling: real recorded media stays outside Git; the result records measurements
  only.
- Honesty: report measured facts and their limits. A single-corpus, single-machine
  benchmark is not a throughput guarantee or a hardware qualification.

## Implementation approach

1. Add the qualification module with explicit subcommands for a NVENC run, a libx264 run,
   and a concurrent-with-transcription run.
2. Take input as an explicit external directory of already-closed blocks plus an explicit
   external output path; refuse to write results inside the repository, as the existing
   playback runner does.
3. Record per-run: input block count and total duration, encoder and settings, wall-clock
   time, real-time factor, output size, and the quality measure.
4. Run all three arms on real Demo-rehearsal blocks.
5. Write the sanitized result document and record limitations explicitly.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `backend/tests/qualification/render_benchmark.py` | Validation-only harness (new) |
| `backend/tests/qualification/test_render_benchmark.py` | Focused harness tests (new) |
| `docs/validation/results/render-benchmark-001.md` | Sanitized result (new) |
| `docs/validation/README.md` | Index the new result |

No production package, dependency, schema, migration, or runtime configuration changes.

## Data or migration considerations

None. No database is touched.

## Failure and recovery considerations

- If NVENC is unavailable or session-limited on the host, record that as a measured
  finding rather than falling back silently to software encoding.
- A failed encode records its exact failure and continues to the next arm where safe.
- The harness never deletes or modifies source blocks.

## Observability requirements

Each run records its own measurements and limitations. GPU utilization samples, if
captured, are diagnostic context and not a claim about sustained capacity.

## Test strategy

- Focused tests: argument/path handling, repository-output refusal, result recording
  shape, and failure recording. The tests do not require a GPU.
- Real runs on the reference host produce the measurements.
- Ruff and Pyright on the new tooling. Full backend suite to confirm no regression.

## Acceptance criteria

- [ ] The harness runs as explicit finite subcommands and refuses to write results inside
  the repository.
- [ ] NVENC and libx264 arms are measured over the same real input blocks with wall-clock
  time, real-time factor, output size, and a quality measure recorded for each.
- [ ] One concurrent-with-CUDA-transcription run is measured and any degradation recorded.
- [ ] A sanitized result document records measurements, settings, and explicit
  limitations, with no media, media paths, or transcript content.
- [ ] No production code, dependency, schema, migration, or runtime configuration changed.
- [ ] The result explicitly states that it is single-corpus, single-machine measurement
  and not a throughput guarantee or hardware qualification.

## Rollback or reversal

Delete the harness, its tests, and the result document. Nothing in production is touched.

## Open questions

Both original open questions were resolved on 2026-08-28 and are recorded above:
the quality measure is SSIM (PSNR secondary) because `libvmaf` is absent from the
installed build, and the source vMix blocks serve as their own reference.

The corpus question resolved as follows. A **semantically complete Session is not
required** — Session start/end is a domain concern for Kernel association and package
completion; the encoder decodes and re-encodes frames and is indifferent to it. The
existing Demo 2 recorded-block folder (11 blocks, approximately 11 minutes) is therefore
valid input for the NVENC-versus-libx264 comparison, and is the corpus for this run.

One measurement caveat to record rather than resolve: at roughly 11 minutes of footage,
the encode completes well inside a minute, which is short of thermal steady state on a
laptop GPU, and the concurrent-transcription arm has only a narrow overlap window
(transcription of 11 minutes completes in roughly 13 seconds at the measured RTF). Results
for the sustained-load and concurrency arms must be reported with that limitation stated
explicitly. A longer full-Session corpus is the better input for those two arms
specifically and may be measured in a follow-up run; it does not block this one.

## Completion record

_(To be filled in by whoever implements this plan.)_
