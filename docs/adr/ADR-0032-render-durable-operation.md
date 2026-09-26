# ADR-0032: Render Durable Operation and Rendered Output identity

## Status

Accepted (owner, 2026-09-25): additive generalization of the ADR-0025 substrate;
video-only first slice without overlays; configured render output root.

## Date

2026-09-25

## Context

StageFlow can now approve an exact Session Assembly revision (ED-0077): pinned completion
membership in timeline order, bound Packaging Asset revisions for each slot, and a frozen
metadata snapshot, with operator overrides planned under ED-0086. Nothing turns an approved
revision into a playable file. ADR-0029 selected NVENC, and it made rendering a GPU-worker
capability. ED-0078 and ED-0085 measured the native FFmpeg pipeline on the reference GPU:

- one CUDA-decode → NVENC encode runs at about 13.4× real time;
- aggregate throughput stays flat for 1 to 4 simultaneous encodes, because one encode
  saturates NVENC;
- outputs are deterministic and byte-identical.

On 2026-09-25 the owner approved these defaults for the first render capability:

- a human-authorized render of exactly one approved Assembly revision;
- a single output profile;
- output stored outside PostgreSQL with identity and hash recorded, following the ADR-0030
  pattern;
- an operator-installed LGPL FFmpeg CLI, supplied by explicit path, never as a repository
  dependency;
- reuse of the ADR-0025 operation and worker model;
- human-only authority (ADR-0026 activates nothing).

**Repository finding that makes this an architecture decision.** The ADR-0025 substrate
is transcription-specific in both contracts and storage:

- `DurableOperation.input` is typed `TranscriptionOperationInput`
  (`backend/app/contexts/work_execution/contracts.py`).
- Migration `0007` constrains `work_operation.operation_kind` and
  `work_worker_capability.operation_kind` to `'transcription'`.
- `work_operation.asset_id` is required and references a Completed Media Asset.

A render has no single source asset. It consumes an Assembly revision.

## Decision

1. **Render is a Durable Operation.** It is long-running, GPU-bound, retryable, and
   externally dependent (FFmpeg), so it meets the AGENTS.md bar for durable at-least-once
   work. The work key is the approved Assembly revision plus the render profile ID and
   version, so rendering is idempotent per revision and profile.
2. **Generalize the ADR-0025 substrate additively rather than duplicate it.** One
   migration:
   - widens the two `operation_kind` checks to `IN ('transcription', 'render')`;
   - makes `work_operation.asset_id` nullable, with a check requiring it when
     `operation_kind = 'transcription'`;
   - adds a `render_operation_input` table keyed by operation ID (Assembly revision, profile
     ID and version, output target token).

   Lease, attempt, fencing, cancellation, retry, and worker presence stay one
   implementation. In code, the operation input becomes a closed, tagged union
   (`TranscriptionOperationInput | RenderOperationInput`). Transcription behaviour and rows
   are unchanged. The reverse migration restores the original checks and is valid only while
   no render rows exist; this is stated in the migration.
3. **Worker capability.** A render capability is a `WorkerCapability` with
   `operation_kind = 'render'`, an execution profile for the render profile, and a runtime
   ID and version for the FFmpeg CLI's version and SHA-256. It also declares NVENC
   availability. The transcription-specific capability fields stay `false` or `null` for
   render.
   - Default claim capacity is **one render lease per GPU worker**. ED-0085 showed that
     concurrency adds no throughput on the reference GPU and only lengthens each render.
4. **Rendered Output identity** is a new aggregate in the `rendering` context, which is
   currently reserved and empty.
   - It holds: output ID, source Assembly revision, profile ID and version, opaque content
     key (never a filesystem path, as in ADR-0030), SHA-256, byte size, media type, duration,
     frame count, the FFmpeg identity used, the producing operation or attempt, and a
     timezone-aware `produced_at`.
   - Bytes live under an operator-configured render output root outside PostgreSQL and
     outside the repository. They are written to a temporary name, hashed, then atomically
     renamed.
   - A Rendered Output is immutable. Re-rendering produces a new output.
5. **First render profile.** The measured ED-0078 settings: H.264 via `h264_nvenc`, preset
   p4, VBR 8 Mbit/s, GOP 60, 1080p, MP4, CUDA decode.
   - First slice: **video only, no audio**. Audio is a follow-up profile decision.
   - Slots are rendered in template order: bound video Packaging Assets, then the Session's
     completion membership in timeline order.
   - **The first slice burns in no overlays.** The metadata snapshot (title, participants)
     goes into a sidecar manifest recorded with the Rendered Output. Burned-in title cards
     and text overlays are follow-ups.
   - Non-video Packaging Assets, such as still images, make the render ineligible with a
     typed reason rather than being silently skipped.
6. **Authority.** Only a human may request a render, through an idempotent command and only
   for an approved, non-stale Assembly revision. No automatic render, and no publication or
   delivery; ADR-0031 keeps publication frozen.
7. **Failure semantics.** FFmpeg failures, a CUDA-decode fallback, NVENC refusal, and a
   missing or changed input become typed attempt outcomes under ADR-0025 retry rules. A
   partial output is never registered. Stderr is never stored, only bounded codes.

## Amendment

*Owner amendment 2026-09-25 (during ED-0087 implementation):* the same kind-conditional
nullability applies to every transcription-source column that `0007` makes required on
`work_operation` or `work_worker_capability`: `asset_id`, `manifest_id`,
`manifest_version`, `asset_format`, and any other such column the implementation finds.
Checks still require these columns for transcription, and the reverse restores `NOT NULL`.

*Owner amendment 2, 2026-09-25 (general kind-aware rule):*
- Every `0007` constraint that assumes transcription stays exactly as it is for
  transcription rows.
- Render gets its own column or reference instead. For example, a
  `terminal_result_rendered_output_id` foreign key to `rendered_output`, with the
  succeeded-requires-result check made kind-aware.
- No existing foreign key is dropped, and no placeholder data is used.
- The reverse restores the originals, and only while no render rows exist.
- Every changed constraint is listed in the implementation report and verified in review.

*Owner amendment 3, 2026-09-26 (render profile v2 — constant output frame rate):*
- Real-GPU validation Run 001 showed that `-fps_mode passthrough` produces duplicate
  presentation timestamps when inputs have slightly different frame rates (for example a
  30000/1001 bumper with 2997/100 recordings).
- The current render profile therefore becomes **version 2**. It is identical to
  decision 5's settings except for its output frame rate, which is a constant 30000/1001.
- Version 1 remains a recorded identity for existing Rendered Outputs. It cannot be
  requested for new renders.
- A v2 request for a revision already rendered under v1 is a new operation, because the
  work key includes the profile version.
- Implemented under ED-0089.

## Alternatives

- **A separate render-only operation substrate** (new operation, attempt, and worker tables
  mirroring `0007`). This leaves the transcription tables untouched, but duplicates the
  lease, fencing, and claim logic, which is the most correctness-sensitive code in the
  system, and splits worker status projections. Rejected as the default because two
  fencing implementations are riskier than one additive generalization.
- **Rendering inside the API process or the Demo coordinator.** Rejected: rendering is
  long-running, GPU-bound, and must survive restarts.
- **PyAV in-process encoding.** Rejected by ED-0078: about 8.5× slower than native FFmpeg,
  with GPL exposure in PyAV's bundled build.
- **Burned-in overlays in the first slice.** Deferred. It needs text-rendering decisions
  (fonts, layout, localization) and FFmpeg filter support validation, and it isn't needed
  to prove the capture-to-file chain.

## Consequences

- StageFlow gains its first end-to-end output: approved Assembly revision → playable file,
  with durable identity.
- Migration `0015` touches `0007` constraints additively. Transcription tests must prove
  unchanged behaviour. The reverse is conditional on no render rows existing.
- Render workers need NVENC GPUs (ADR-0029) and an operator-installed LGPL FFmpeg CLI. The
  distribution posture does not change (ED-0075 and the SBOM decision).
- This is the first production code that launches an external binary and writes media
  files. It needs a dedicated security review of path handling, argument construction (no
  shell), and output-root containment.
- Delivery and publication stay out of scope until a provider-neutral Delivery context
  exists.

## Validation

None yet. The implementing plan must include:

- migration forward, reverse, and reapply tests;
- unchanged transcription behaviour;
- claim, lease, fence, and retry tests for render;
- a fake-FFmpeg test suite;
- a real-GPU host render of an approved Assembly revision, with output hash identity and
  playability checks;
- a `/security-review` pass.

## Related documents

- ADR-0025 (Durable Operations and workers), ADR-0026 (automation stays inactive),
  ADR-0029 (NVENC), ADR-0030 (identity pattern), ADR-0031 (publication frozen).
- ED-0077 (Session Assembly), ED-0078 and ED-0085 (render evidence), ED-0086 (metadata
  overrides).
