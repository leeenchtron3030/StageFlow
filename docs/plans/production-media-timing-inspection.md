# Production media timing inspection

## Status

Approved

## Execution authority

- Classification: Green autonomous under accepted ADR-0033.
- Authority evidence:
  - The owner decided on 2026-09-26, on the "derived Editorial placement" escalation,
    that media timing comes first: a new Durable Operation kind using an operator-installed
    LGPL `ffprobe` by explicit path, recording observed `creation_time` and duration as
    advisory MTE.
  - [ADR-0033](../adr/ADR-0033-production-media-timing-inspection.md), accepted by
    the owner on 2026-09-26.
  - ADR-0027 (MTE is advisory; the application boundary exists), ADR-0025, and ADR-0032
    with amendment 2 (the kind-aware constraint rule).
  - ED-0087 (the substrate generalization and the FFmpeg identity pattern).
- Implementation-ready: Yes.
- Required escalation: stop if this would:
  - write `media_started_at`, Session boundaries, association, membership, or package
    state;
  - qualify a recorder profile;
  - change transcription or render behaviour;
  - alter an existing constraint's meaning for the existing kinds;
  - add a repository dependency;
  - make MTE authoritative.
- Engineering Directive: **ED-0090**. The owner delegated ED numbering.

## Preserved accepted decisions

- **ADR-0027:**
  - MTE stays immutable, append-only, revisioned, and advisory.
  - Observed and Derived meanings stay explicit.
  - Nothing mutates Session, membership, association, or package authority.
  - The existing `MediaTimingEvidenceApplication.apply` boundary, with its idempotency and
    revisions, is the only write path.
- **ADR-0025 / ADR-0032:**
  - There is one lease, fencing, retry, and presence implementation.
  - Every existing `0007` and `0015` constraint keeps its meaning for `transcription` and
    `render`.
  - Transcription and render claims, listings, and projections are unchanged. ED-0087
    decision (b) extends: transcription-facing and render-facing views filter out
    `media_timing`.
- **ED-0088:** Assembly ordering is **not** changed in this directive. Consuming MTE for
  ordering is a follow-up directive.

If an existing assertion would have to change, stop and report it. The two exceptions,
authorized in advance, are:
- inserting `0017` into the migration-order expectation lists;
- mechanical updates that add fields to constructors, keeping the existing values.

## Problem statement

Discovered media has no start time, so transcript matches cannot be placed on the Session
timeline, and Assembly can only fall back to registration-time ordering. ADR-0027's MTE
aggregate exists with no production producer.

## Verified current behavior

- `backend/app/contexts/production/media_timing_evidence/`:
  - contracts for provenance, Observations, Derivations, recorder qualification, and the
    inspection result;
  - `MediaTimingInspectionPort` (a protocol with no production adapter);
  - `MediaTimingEvidenceApplication.apply` (idempotent, revisioned);
  - a PostgreSQL repository (`0006`).
- `0015` allows `operation_kind IN ('transcription','render')` on `work_operation` and
  `work_worker_capability`, with kind-aware nullability and terminal-result checks.
- `backend/app/demo/service.py` (~lines 160–205) enqueues transcription for newly
  registered assets during reconciliation.
- `KernelMediaPathResolver` resolves a registered asset to a contained regular file.
- `backend/app/infrastructure/rendering/ffmpeg.py` holds the explicit-path, SHA-256, and
  GPL/nonfree identity checks for FFmpeg.
- `backend/tests/qualification/media_timing_probe.py` parses `ffmpeg -i` header text. It
  is qualification-only, and production code must not import it.

## Desired behavior

ADR-0033 decisions 1–6: a `media_timing` Durable Operation per registered asset. A worker
runs the operator's `ffprobe` and records Observed `creation_time` and durations plus one
Derived `creation_time_plus_duration` v1 interval as `unqualified` MTE, through the
existing application boundary.

## In scope

**Phase A — substrate:**

1. Migration `0017`:
   - Widen both `operation_kind` checks to add `'media_timing'`.
   - Make the asset and manifest requirement kind-aware, so it applies to `transcription`
     and to `media_timing`.
   - Add `terminal_result_media_timing_evidence_id` (a foreign key to
     `media_timing_evidence`), and make the succeeded-requires-result check kind-aware.
   - Add `media_timing_operation_input` if the transcription-shaped columns cannot carry
     the inspection profile. Prefer reusing the existing asset, manifest, and profile
     columns when they fit, and state the choice.
   - The reverse restores `0015`'s constraints and is refused while `media_timing` rows
     exist.
   - Forward, reverse, and reapply tests.
2. Work execution:
   - Add a `MediaTimingOperationInput` to the closed, tagged input union.
   - Claims filter by kind and capability.
   - A typed repository view for `media_timing`.
   - Isolation tests: transcription and render never claim or list `media_timing` work,
     and the reverse holds.

**Phase B — inspection:**

3. A production `ffprobe` adapter (`backend/app/infrastructure/media_timing/`):
   - explicit path, version and SHA-256 identity, GPL/nonfree refusal, no shell, and
     explicit stdin handling;
   - the invocation is `-v error -print_format json -show_format -show_streams <file>`;
   - bounded stdout size and a timeout;
   - JSON parsing that keeps only the fields the ADR names;
   - naive or unparseable timestamps become limitations, never guessed zones (ADR-0021);
   - stderr and raw JSON are never stored.
4. An `InspectionProfile`: ID and version, the rule `creation_time_plus_duration` v1, and a
   tool ID. It produces a `MediaTimingInspectionResult`:
   - Observations: `creation_time` (original and normalized), container duration, and the
     primary video stream's start and duration;
   - Derivation: present only when both `creation_time` and the duration are present and
     valid;
   - qualification `unqualified`, with limitations naming the unqualified semantics.
5. A worker, `python -m app.demo.media_timing_worker`:
   - declares a CPU capability;
   - bounded concurrency, with a default of 2;
   - claims, resolves through `KernelMediaPathResolver`, inspects, then applies through
     `MediaTimingEvidenceApplication` and records the terminal result under fencing, in one
     transaction;
   - failures are typed outcomes that release the lease, as in ED-0087 decision (c):
     `media_timing_tool_unavailable`, `media_timing_tool_refused`,
     `media_timing_output_invalid`, `media_timing_timeout`, and `input_missing`.
6. Enqueue:
   - When `[local_media_timing]` is enabled (`ffprobe_path`; optional; off by default), the
     Demo reconciliation enqueues one `media_timing` operation per newly registered asset,
     next to transcription. It is idempotent by work key.
   - An explicit, human, bounded, idempotent command and route enqueue existing registered
     assets for an Event.
7. API: authenticated, bounded, paginated `GET`s for media timing operations and, per
   asset, the latest MTE summary. The summary gives the candidate interval, qualification,
   limitations, and evidence revision. There are no paths and no raw output.
8. Tests:
   - migration forward, reverse, and reapply, including a refused reverse;
   - kind isolation, both ways;
   - claim, lease, fence, and retry for `media_timing`;
   - with a fake `ffprobe` (a Python script behind an explicit wrapper): valid output,
     missing `creation_time` (observations only), naive timestamp (limitation), malformed
     JSON, oversized output, timeout, non-zero exit, and GPL refusal;
   - MTE application round trip and idempotent replay;
   - enqueue idempotency;
   - real-PostgreSQL persistence;
   - API authentication and bounds, with no paths.
9. Documentation:
   - the glossary (media timing inspection);
   - the persistence document (`0017`);
   - the capability layer and system context;
   - the configuration README (`[local_media_timing]`);
   - the MTE architecture document (the production inspector now exists and stays
     advisory).
10. **Owner step:**
    - Run the worker on the host over the live-run recordings (the 2026-08-26 blocks)
      registered in the demo database.
    - Compare the derived intervals with the vMix reconnaissance: 60 s spacing and aware
      UTC.
    - Record a sanitized validation result.
    - Run `/security-review` on the branch.

## Out of scope

- Consuming MTE in Assembly ordering or Editorial placement (the follow-up directives).
- Recorder profile qualification, Session boundary or association changes, and writing
  `media_started_at`.
- Frontend UI, cloud or network inspection, and other derivation rules.

## Constraints

- No repository dependency. Offline. Timezone-aware times, with ADR-0021 normalization
  rules.
- Immutable contracts. White-label naming.
- No paths, stderr, or raw tool output in records, logs, API responses, or documentation.

## Data or migration considerations

`0017` changes the `0007`/`0015` constraints additively under ADR-0032 amendment 2, and
adds a terminal-result reference. There is no backfill. The reverse is conditional on no
`media_timing` rows existing.

## Failure and recovery considerations

Failures and retries follow ADR-0025 with typed codes. The MTE application is idempotent
by operation. Replaying an enqueue returns the existing operation.

## Observability requirements

- Operation state and attempt outcomes are visible through the new `GET`s.
- The per-asset MTE summary shows qualification and limitations, so consumers can label
  unqualified timing.

## Test strategy

The tests are listed under In scope, item 8. The quality gate is the full host backend
suite, Ruff, and Pyright. The owner's host run and security review are item 10.

## Acceptance criteria

- [ ] `0017` and kind isolation are in place. Transcription and render suites pass
  unchanged.
- [ ] The adapter, profile, worker, enqueue, command, and API are implemented with the
  listed tests.
- [ ] MTE is written only through the existing application boundary, and it is advisory
  and `unqualified`.
- [ ] The full host backend suite, Ruff, and Pyright pass, and the frontend is unchanged.
- [ ] The owner's host run records derived intervals consistent with the reconnaissance,
  and `/security-review` finds nothing unresolved.

## Rollback

Revert the code, and apply the `0017` reverse (only while no `media_timing` rows exist).
MTE rows written stay as history; ADR-0027 sets no deletion policy.

## Completion record

_(Filled in on completion.)_
