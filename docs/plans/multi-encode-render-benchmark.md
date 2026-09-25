# Multi-encode render benchmark

## Status

Completed (2026-09-25). See the [result](../validation/results/render-benchmark-003.md).

## Execution authority

- Classification: Green autonomous. Qualification tooling only, with no production code.
- Authority evidence:
  - [ADR-0029](../adr/ADR-0029-nvenc-rendering-and-gpu-worker-requirement.md) selects
    NVENC and makes render-fleet sizing depend on GPU evidence.
  - The [ED-0078 result](../validation/results/render-benchmark-002.md), "Limitations":
    "multiple simultaneous encodes on one GPU, including NVENC session limits and how
    throughput scales per GPU. Fleet sizing needs this next".
  - The 2026-09-25 `roadmap-scout` ranking, which confirmed this as the next Green
    candidate and noted that it feeds the render Durable Operation's lease capacity.
- Implementation-ready: Yes.
- Required escalation: stop if this appears to need production render code, a Worker
  Capability change, a repository dependency, or an output-format decision.
- Engineering Directive: **ED-0085**. The owner delegated ED numbering; ED-0085 is the
  next free number.

## Problem statement

ED-0078 measured one native CUDA-decode → NVENC encode: 48.91 s for 657.39 s of source,
13.4× real time. A render worker that holds several render leases on one GPU needs to know
three things:

- whether several simultaneous encodes share the GPU's NVENC capacity or scale;
- where the GPU refuses more sessions;
- whether concurrency changes the output.

Nothing measures this yet.

## Verified current behavior

- `backend/tests/qualification/render_benchmark.py` (harness 1.1) provides the ED-0078
  building blocks:
  - `identify_ffmpeg` (explicit path, version, SHA-256, GPL refusal);
  - `build_native_command`;
  - `encode_native_video`, including `cuda_decode_fallback`;
  - `native_variance`, `native_output_paths`, and `native_report`;
  - `run_native_arm`, and `run_native_concurrent_arm` with barrier and overlap
    arithmetic;
  - external-path safety and atomic sanitized reports.
- ED-0078 established that native outputs are **byte-identical** across decode paths,
  repetitions, and a concurrent CUDA transcription load. An output hash is therefore an
  exact, cheap quality check for further native encodes, in place of about 500 s of
  SSIM/PSNR per output.
- The reference host has one RTX 3080 Ti Laptop GPU, driver 581.57, and the LGPL FFmpeg
  8.1.2 CLI. The corpus has fingerprint `29fe9035…`: 11 blocks and 657.39 s of source.

## Desired behavior

A `native-parallel` harness arm runs N simultaneous native CUDA-decode → NVENC encodes of
the corpus for each requested N. It reports per-encode and aggregate throughput, scaling
efficiency against N = 1, any session refusal, and whether every output is byte-identical
to the single-encode reference.

## In scope

1. A new `native-parallel` subcommand sharing the native arguments: `--ffmpeg`, corpus,
   output, report, bitrate, and GOP.
   - `--parallelism` takes a bounded list; the default is `1,2,3,4` and the maximum is 8.
   - `--repetitions` defaults to 2 and is bounded to 1-5.
2. For each N and repetition:
   - Start N `native-cuda-nvenc` encodes behind one barrier, one thread per FFmpeg
     process, each with its own output.
   - Record each process's start, end, wall clock, exit status, encoded frame count, and
     output size.
   - Record the aggregate window, from the first start to the last end.
   - Compute aggregate source speed as (N × source seconds) ÷ aggregate wall, and scaling
     efficiency as aggregate speed ÷ (N × mean N = 1 speed).
3. **Session refusal and failures.** An encode that fails is recorded with a typed code,
   never retried or hidden. A recognisable NVENC session or resource refusal in stderr
   (for example `OpenEncodeSessionEx failed` or `No capable devices found`) gets the code
   `nvenc_session_unavailable`. The CUDA fallback guard still applies. The arm continues
   to the next N, so the refusal point is measured.
4. **Output identity.** Hash every output with SHA-256 and compare it with the N = 1
   reference output of the same run.
   - Identical: the output is recorded as quality-equivalent.
   - Different: run the existing SSIM/PSNR measurement on that output and record it.
   - With `--discard-verified-outputs`, only outputs this arm wrote and that were verified
     identical are deleted after hashing. Sources are never deleted.
5. Report the variance of aggregate wall and speed per N (population SD, as in ED-0078),
   plus the FFmpeg identity, the corpus fingerprint, and the limitations.
6. Focused tests that need no GPU or FFmpeg, using the existing fake-executable and
   monkeypatch patterns:
   - `--parallelism` and `--repetitions` parsing and bounds;
   - barrier start and aggregate-window arithmetic;
   - efficiency arithmetic;
   - a session-refusal stderr producing `nvenc_session_unavailable` while other N values
     continue;
   - hash identity versus SSIM fallback;
   - discarding only verified, self-written outputs;
   - external-path and repository-output refusal.
7. **Owner step:** run the arm on the reference host and write
   `docs/validation/results/render-benchmark-003.md`, then index it.

## Out of scope

- Production render code, `RenderRequest`, Worker Capability or lease changes. This is
  input for the render Durable Operation plan, not that plan.
- Mixed workloads beyond ED-0078's concurrent-transcription arm, audio, containers, and
  bitrate ladders.
- Other GPUs, and a long-corpus or sustained-thermal arm.

## Constraints

- An explicit FFmpeg path only; no `PATH` lookup; the binary is identified by version and
  hash, never by path.
- No media, media paths, or usernames in reports or results. The harness never modifies or
  deletes source blocks.
- Offline measurement tooling, never run during live capture.
- Results are first-order sizing input for this one laptop GPU and driver. They are not a
  throughput guarantee or hardware qualification.

## Implementation approach

Reuse `encode_native_video`, the ED-0078 barrier and thread pattern, `native_variance`,
`identify_ffmpeg`, and `measure_quality`. Add the arm, the report shape (harness version
1.2; earlier arms and reports unchanged), and the tests. The owner runs N = 1..4 with two
repetitions on the host after independent review and host validation.

## Files or modules expected to change

| Path | Change |
| --- | --- |
| `backend/tests/qualification/render_benchmark.py` | `native-parallel` arm |
| `backend/tests/qualification/test_render_benchmark.py` | Focused tests |
| `docs/validation/results/render-benchmark-003.md` | Result (owner) |
| `docs/validation/README.md`, plan and ED index rows | Index and status (owner) |

## Data or migration considerations

None.

## Failure and recovery considerations

- Failed or refused encodes are recorded, not retried.
- A thread or process exception is captured per encode, and the other encodes finish.
- Report writes are atomic and never overwrite an existing report.

## Observability requirements

Per N, the report shows:

- per-encode timings, exits, frames, sizes, and hashes;
- the aggregate window and speed;
- the efficiency;
- failures with typed codes;
- output identity versus the reference.

GPU telemetry samples may be captured by the owner as diagnostics.

## Test strategy

Focused tests as in scope item 6; Ruff and Pyright; the full backend suite on the host;
and the real-GPU run by the owner.

## Acceptance criteria

- [x] `native-parallel` exists with bounded `--parallelism` and `--repetitions`, reusing the
  ED-0078 identity, GPL refusal, and fallback guard. Earlier arms and reports are unchanged.
- [x] Per-encode and aggregate timing, speed, efficiency, and variance are reported for each
  N.
- [x] Session refusal is recorded as `nvenc_session_unavailable`, and the arm continues.
- [x] Outputs are hash-verified against the N = 1 reference, with SSIM only on mismatch.
  Discarding covers only verified, self-written outputs.
- [x] Focused tests pass without a GPU; Ruff, Pyright, and the full backend suite pass on
  the host.
- [x] The host run covers N = 1..4 × 2 over the ED-0078 corpus (same fingerprint), and
  `render-benchmark-003.md` reports every run, including refusals and outliers, as
  first-order sizing input.

## Rollback

Remove the arm, its tests, and the result.

## Open questions

- None blocking. If the GPU accepts all N ≤ 4, whether to probe up to N = 8 is an owner
  choice at run time. `--parallelism` allows it.

## Completion record

- **Implemented revision:** branch `codex/ed-0085-multi-encode-render-benchmark`, harness
  commit `c686fd0` plus the result and records commit. Codex built the harness in the
  sandbox, and the owner committed it.
- **Files changed:** `backend/tests/qualification/render_benchmark.py`,
  `backend/tests/qualification/test_render_benchmark.py`, the result
  `render-benchmark-003.md`, and the index and plan rows. No production code,
  dependency, schema, migration, or configuration change.
- **Review:**
  - The `directive-reviewer` first returned FIX-FIRST because
    `--discard-verified-outputs` could delete the reference output.
  - Fixed: the reference is kept and marked `is_reference`, specific `BenchmarkError`
    codes are preserved, and the barrier has a 60 s timeout.
  - The re-review returned APPROVE, with 124 focused tests passing.
- **Host checks:**
  - A real-FFmpeg smoke test on synthetic clips, for N = 1..3.
  - The full host suite: **2,169 passed, 2 skipped, 1 failed**. The failure was the
    known intermittent `test_devcon_session_publish.py` local-HTTP case, which passed when
    rerun in isolation. Ruff and Pyright were clean.
- **Measurement (owner, reference host, outside any sandbox):** N = 1..4 × 2 over the
  ED-0078 corpus, with the same fingerprint.
  - All 20 encodes succeeded, and all outputs were byte-identical to the reference.
  - Aggregate speed was flat at about 13.6× real time, with NVENC saturated at 99.6%.
  - No session was refused up to N = 4.
- **Deviations:** none.
- **Remaining work:** none for this plan. The finding feeds the render Durable Operation
  plan: one render lease per GPU gives the lowest latency at the same total throughput.
