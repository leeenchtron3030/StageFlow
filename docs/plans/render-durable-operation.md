# Render Durable Operation (first slice)

## Status

Completed (2026-09-25).

## Execution authority

- Classification: Green autonomous, under accepted
  [ADR-0032](../adr/ADR-0032-render-durable-operation.md). The owner accepted it on
  2026-09-25, together with the owner's approved defaults for render.
- Authority evidence:
  - ADR-0032, including its decisions on substrate generalization, the first slice,
    output storage, and authority;
  - ADR-0025 (Durable Operations), ADR-0029 (NVENC), ADR-0030 (identity pattern), and
    ADR-0031 (publication frozen);
  - ED-0077 (approved Assembly revisions), ED-0086 (metadata overrides), and ED-0078 and
    ED-0085 (render evidence).
- Implementation-ready: Yes.
- Required escalation: stop if this would change transcription behaviour or rows,
  alter any existing table beyond the `0007` constraint changes ADR-0032 names, add a
  repository dependency, add audio, overlays, or publication, or allow automatic render
  authority.
- Engineering Directive: **ED-0087**. The owner delegated ED numbering.

## Preserved accepted decisions

This plan reads Assembly and Kernel state and changes none of their semantics.

- **ED-0077:** it renders only an **approved, non-stale** revision. It uses the revision's
  pinned completion membership in timeline order and its bound Packaging Asset revisions
  exactly as frozen. Staleness stays derived (decision 7, as preserved by ED-0086).
- **ED-0086:** it uses the revision's frozen metadata snapshot, including override
  provenance, and never re-resolves metadata at render time.
- **ADR-0025:** idempotency by work key, attempt fencing, lease expiry, retry and backoff,
  cancellation, and worker presence stay a single implementation, shared with
  transcription.
- **ADR-0030:** Rendered Output identity follows the opaque key plus SHA-256 pattern, and
  never records a filesystem path.
- **ADR-0031:** there is no publication or delivery path.

If any existing test assertion would have to change, stop and report it rather than
changing the assertion.

## Problem statement

An approved Session Assembly revision cannot yet become a playable file. This slice
closes the capture → Assembly → rendered-file chain on one GPU node.

## Verified current behavior

- `backend/app/contexts/work_execution/contracts.py`: `DurableOperation.input` is
  `TranscriptionOperationInput`, and `WorkerCapability` carries transcription-shaped fields.
- `backend/app/infrastructure/postgres/sql/0007_transcription_worker_forward.sql`:
  `operation_kind` is checked as `'transcription'` on both `work_operation` and
  `work_worker_capability`, and `work_operation.asset_id` is `NOT NULL`, referencing
  `completed_media_asset_registry`.
- `backend/app/infrastructure/postgres/transcription_work_repository.py` implements claim,
  lease, fence, attempt, retry, and presence. `backend/app/demo/worker.py` composes the
  transcription worker with `KernelMediaPathResolver`.
- `backend/app/contexts/rendering/` exists but is empty and reserved.
- Packaging Asset content is an opaque `content_key` plus SHA-256, size, and media type,
  or a Completed Media Asset reference. There is no resolver from key to bytes today.
- `backend/tests/qualification/render_benchmark.py` holds the proven FFmpeg command
  construction, identity and GPL check, concat quoting, frame parsing, and fallback guard.
  It is qualification tooling; production code must not import tests.

## Desired behavior

A human requests a render of an approved, non-stale Assembly revision. A render worker
with NVENC and an operator-installed LGPL FFmpeg claims it, renders the slots in template
order to one H.264 NVENC 1080p MP4 (video only, no overlays), and registers an immutable
Rendered Output with an opaque key, SHA-256, size, duration, frame count, the FFmpeg
identity, and a sidecar metadata manifest. Failures are typed and retried under ADR-0025,
and a partial output is never registered.

## In scope

1. **Migration `0015`.**
   - Widen the `0007` `operation_kind` checks to `IN ('transcription','render')`.
   - Make `work_operation.asset_id` nullable, with a check that requires it when the kind
     is `transcription`.
   - Add `render_operation_input` (operation ID, Assembly revision ID, profile ID and
     version, output token).
   - Add a `rendered_output` table: append-only, with the immutability trigger, and the
     fields in ADR-0032 decision 4.
   - The reverse restores the checks and fails with a clear error if render rows exist.
     Forward, reverse, and reapply tests are required.
2. **Work execution generalization.** A closed, tagged operation input union. The existing
   repository, claim, lease, fence, and retry logic handles both kinds, and claims filter
   by kind and capability. Transcription behaviour is unchanged. The existing
   transcription test suites must pass without weakening, and new tests assert that
   transcription rows and claims are unaffected.
3. **Rendering context** (`backend/app/contexts/rendering/`):
   - `RenderProfile`: the constant first profile, with an ID and version;
   - `RenderRequest` input;
   - `RenderedOutput`;
   - a pure **render plan** builder. From an approved Assembly revision plus resolved
     inputs, it produces an ordered list of video inputs and a sidecar manifest. Image or
     otherwise non-video Packaging Assets yield a typed `render_input_not_video`
     ineligibility.
4. **Application command.** `request_render(assembly_revision_id, profile, actor,
   command_id)`: human-only, idempotent, and only for an approved, non-stale revision. The
   work key is the revision plus the profile ID and version.
5. **Infrastructure adapters** (`backend/app/infrastructure/rendering/`):
   - A production FFmpeg render adapter. It takes an explicit FFmpeg path, checks version,
     SHA-256, and that the build is not GPL, and builds an argument list with no shell and
     `-nostdin`. It writes a concat list to a temporary file, and uses CUDA decode with
     `h264_nvenc` at the profile settings. It parses the frame count and applies the CUDA
     fallback guard.
     - Port the needed logic from the qualification harness into production code; do not
       import from tests.
   - A packaging content resolver. It maps a `content_key` to a file under a configured
     packaging content root, using containment checks, refusing links, and verifying
     SHA-256 and size before use.
   - Session media resolution reuses `KernelMediaPathResolver`.
   - An output store. It writes to a temporary name inside the configured render output
     root, hashes, and atomically renames. The key is opaque, and the path is never
     recorded.
6. **Render worker.** Launched with `python -m app.demo.render_worker`, and composed like
   `app/demo/worker.py`.
   - It declares a render `WorkerCapability`: the profile, FFmpeg version and hash as the
     runtime, and NVENC availability.
   - It claims one lease at a time (ED-0085). Heartbeats and fencing follow ADR-0025.
   - Configuration: a new optional, default-off `[local_render]` section with
     `ffmpeg_path`, `output_root`, and `packaging_content_root`, all absolute, outside the
     repository, and validated.
7. **API.**
   - `POST /api/v1/rendering/requests`: authenticated, idempotent, human-only.
   - `GET` endpoints, bounded and paginated, for render operations and Rendered Outputs,
     scoped to Event and Session. Responses carry no filesystem paths.
8. **Tests.** A fake-FFmpeg executable that writes deterministic bytes, plus:
   - claim, lease, and fence for render, with transcription isolation;
   - retry and typed failures: FFmpeg exit, fallback, NVENC refusal, and an input hash
     mismatch;
   - no partial registration;
   - idempotency;
   - stale or unapproved revision refusal;
   - non-video ineligibility;
   - output-root containment;
   - migration forward, reverse, and reapply, including the refused reverse when render
     rows exist;
   - real-PostgreSQL persistence and reconstruction;
   - API authentication and bounds;
   - no path leakage.
9. **Documentation.** Commit ADR-0032, and update:
   - the glossary (Render Profile, Render Request, Rendered Output);
   - the persistence document (`0015`);
   - the capability layer and system context;
   - the configuration README (`[local_render]`).
10. **Owner step.** A real-GPU host render of an approved Assembly revision from the
    rehearsal data, checking the output hash, frame count, and playability (FFprobe). The
    result is recorded as a sanitized validation result, and a `/security-review` pass is
    run on the PR.

## Owner amendment

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

## Out of scope

- Audio, overlays, burned-in titles, image slots, extra profiles, and bitrate ladders.
- Publication or delivery (ADR-0031), and automatic or ADR-0026 authority.
- Frontend UI; that is a separate directive.
- Scheduling across multiple GPUs, and more than one lease per GPU.

## Constraints

- No repository dependency. FFmpeg is an operator-installed binary, used by explicit path
  and never looked up on `PATH`.
- Offline. No network, and no media or paths in records or logs.
- Timestamps are timezone-aware and come from injected clocks.
- Immutable contracts.
- White-label.

## Data or migration considerations

`0015` changes the `0007` constraints additively and adds tables. There is no backfill.
Transcription rows are unchanged. The reverse is conditional on no render rows existing,
and this is documented.

## Acceptance criteria

- [ ] Migration `0015` is implemented as specified, with forward, reverse, and reapply
  tests, and a refused reverse when render rows exist.
- [ ] The operation input union is in place. The transcription suites pass unchanged, and
  transcription isolation is tested.
- [ ] The render plan builder, command, adapter, resolvers, output store, worker, and API
  are implemented with the listed tests.
- [ ] No partial output is registered. Outputs are identified by opaque key and SHA-256,
  with no paths.
- [ ] The full backend suite, Ruff, and Pyright pass on the host, and the frontend is
  unchanged.
- [ ] The owner's real-GPU render passes its identity and playability checks, and the
  `/security-review` finds nothing unresolved.

## Rollback

Revert the code, and apply the `0015` reverse (only while no render rows exist). Rendered
files stay in the operator's output root for manual removal.

## Completion record

- **Implemented revision:** branch `codex/ed-0087-render-durable-operation`, in two phases.
  Codex implemented both, and the owner committed them.
  - Phase A (`036dcb6`): migration `0015` and the tagged operation-input union with
    kind-isolated claims.
  - Phase B: the rendering context, render-plan builder, request command, FFmpeg adapter,
    packaging content resolver, output store, render worker, `[local_render]`
    configuration, `/api/v1/rendering` routes, and documentation.
- **Phase B decisions (owner defaults):**
  - (a) Replaying a request returns the existing operation in any state. Re-rendering the
    same revision and profile after a terminal failure is out of scope; the supported path
    is a new approved revision.
  - (b) Filtering by operation kind follows the repository's configured input types.
    Transcription-facing listings, attempts, status projections, and the Demo worker
    summary filter to transcription before counting or applying limits. Repositories
    explicitly configured for several kinds stay multi-kind.
  - (c) The render worker records a fenced, typed outcome and releases the lease for any
    error after the attempt is marked running. The transcription worker is unchanged.
- **Review:**
  - Codex's first Phase B run stopped Yellow because decision (b) was worded too broadly.
    The owner clarified it (the rule above), and Codex implemented it.
  - The `directive-reviewer` returned FIX-FIRST:
    - a Windows `fsync` on a read-only handle that broke every successful render on the
      host;
    - untested Session-media and PostgreSQL packaging-binding paths;
    - a vacuous path-leakage assertion;
    - orphaned files on definite failures;
    - a Demo worker-summary regression;
    - doc placement.
  - Codex fixed these. The re-review found one remaining issue: an unlisted error during
    commit was treated as definite, which could delete files a committed row references.
    The owner fixed it so that only known rollback codes (`40001`, `40P01`) are definite,
    added tests, and corrected one stale capability-layer line.
  - A branch security review, following the `/security-review` method, found no
    high-confidence vulnerabilities.
- **Tests:** host full suite **2,303 passed, 0 failed, 2 skipped** (POSIX-only); Ruff and
  Pyright are clean. No existing test assertion was changed in Phase B.
- **Owner real-GPU render:** passed; see
  [Run 001](../validation/results/render-durable-operation-001.md). It used a labelled
  validation event, because discovered media has no start times.
- **Execution authority:** Green, plus the owner's decisions above.
- **Deviations:** none from the ADR or this plan.
- **Remaining work:**
  - Discovery does not populate media start times, so Assemblies from discovered media are
    never approvable. This needs a timing-authority decision.
  - Inputs with mixed frame rates produce duplicate presentation timestamps under
    `-fps_mode passthrough`. The options are a profile-version change or a typed
    ineligibility.
  - The transcription worker does not record unexpected errors raised after an attempt is
    marked running.
  - Optional hardening: a per-input FFmpeg format whitelist.
  - Producer UI for rendering, in a later directive.
