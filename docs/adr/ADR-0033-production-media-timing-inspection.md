# ADR-0033: Production media timing inspection

## Status

Accepted (owner, 2026-09-26). Drafted at the owner's direction after the owner selected
this path and its defaults on the 2026-09-26 escalation, "media timing first".

## Date

2026-09-26

## Context

Discovered media has no start time:
- Discovery builds every Completed Media Asset without a recorded start
  (`backend/app/bootstrap/media_cycle.py:570`), so `media_started_at` is NULL for every
  discovered asset.
- ED-0088 lets Assembly order such members by registration time. That is only an ordering
  fallback.
- Transcript words are timed relative to their media file, while Editorial candidates live
  on the Session timeline. Without a file start time, a transcript match cannot be placed on
  the Session timeline, which blocks derived Editorial candidates.

[ADR-0027](ADR-0027-media-timing-evidence.md) already defines the home for this fact:
- Media Timing Evidence (MTE) is an immutable, revisioned, advisory aggregate per Completed
  Media Asset, holding Observed facts, Derived candidate intervals, provenance, and recorder
  qualification status.
- MTE may be consumed by future proposal workflows.
- It deliberately selected no production inspection provider or worker. Long-running
  production inspection was left behind ADR-0025's worker boundary.

The MTE domain and its synchronous application boundary exist, with no production
inspector.

Since then:
- ADR-0025's substrate has been generalized to several operation kinds (ADR-0032,
  migration `0015`).
- Operators already install an LGPL FFmpeg build, which ships `ffprobe`, identified by
  explicit path and SHA-256 (ED-0087).
- vMix reconnaissance found that the embedded container `creation_time` is aware UTC and
  consistent across 60 s segments. Its meaning (recording start versus a file-open
  instant) is **unqualified**.

On 2026-09-26 the owner chose to build production media timing inspection first, with
these defaults:
- an operator-installed LGPL `ffprobe` by explicit path;
- a new Durable Operation kind;
- observed `creation_time` and duration recorded as advisory MTE.

## Decision

1. **Media timing inspection is a Durable Operation** of kind `media_timing`, on the shared
   ADR-0025/ADR-0032 substrate. It is externally dependent (a binary), retryable, and must
   survive restarts, and lease, fencing, retry, and presence stay a single implementation.
   - The work key is the Completed Media Asset and manifest identity plus the inspection
     profile ID and version.
   - A `0017` migration extends the kind checks additively, following ADR-0032 amendment 2:
     - every existing constraint keeps its meaning for the existing kinds;
     - a `media_timing` row requires the asset and manifest columns;
     - it records its terminal result through its own reference to the MTE row;
     - the reverse is refused while `media_timing` rows exist.
2. **Provider:** an operator-installed LGPL `ffprobe`, supplied by an explicit absolute path
   in an optional, default-off configuration section.
   - It is identified by version and SHA-256, and a GPL or nonfree build is refused.
   - It is never looked up on `PATH`, and never a repository dependency.
   - It runs with `-v error -print_format json -show_format -show_streams` on the registered
     resource resolved through the existing Kernel media path resolver. There is no shell,
     and any stdin handling is explicit.
   - Only bounded normalized fields are kept. Raw output and stderr are never stored.
3. **Evidence content** follows ADR-0027 exactly:
   - Observed facts: container `creation_time` in its original representation and
     normalized aware UTC, container duration, and the start time and duration of the
     primary video stream, when present.
   - One Derived candidate interval from the rule `creation_time_plus_duration` v1: start =
     `creation_time`, end = start + container duration, with inputs referenced.
   - Qualification is `unqualified` unless a recorder profile has been qualified through the
     existing calibration path. This ADR qualifies nothing.
   - A file with no `creation_time` yields evidence with observations and no derivation, not
     a failure.
4. **Enqueue.** When the section is enabled, each newly registered Completed Media Asset is
   enqueued once for inspection, from the same composition point that enqueues
   transcription.
   - This is evidence gathering, not authority, so ADR-0026 is not engaged.
   - Existing assets can be enqueued through an explicit, bounded, idempotent human command.
5. **Consumers remain advisory** (ADR-0027 unchanged):
   - MTE never writes `media_started_at`, Session boundaries, association, membership, or
     package state.
   - Proposal workflows may read the latest active Derived candidate interval, and must
     record which evidence revision and qualification status they used:
     - Assembly ordering, which upgrades ED-0088's fallback (a separate directive);
     - derived Editorial candidates placing transcript matches on the Session timeline (a
       separate directive).
   - A human still approves every consequential result.
6. **Worker.** `python -m app.demo.media_timing_worker` claims `media_timing` operations
   with a CPU-only capability and bounded concurrency. It resolves media through the Kernel
   resolver and applies results through the existing idempotent
   `MediaTimingEvidenceApplication`, committing the terminal result reference together with
   the evidence.

## Alternatives

- **Populate `recorded_start_at` at discovery from container metadata.** Rejected. It turns
  unqualified recorder metadata into a registry fact that feeds Kernel association
  (ADR-0027, and the ED-0088 escalation's option B).
- **Synchronous inspection inside discovery or registration.** Rejected. It puts an
  external binary in the media-cycle hot path, and ADR-0027 puts production inspection
  behind the worker boundary.
- **Parse `ffmpeg -i` header text,** as the qualification probe does. Rejected for
  production: `ffprobe` JSON is structured and stable. The probe stays qualification
  tooling.
- **Reuse the transcription worker process.** Rejected. Inspection is CPU-only and short,
  while transcription is GPU-bound, and a separate capability keeps claims and presence
  honest.

## Consequences

- Assembly ordering and derived Editorial placement get a real, advisory, provenance-bearing
  source for file start times, labelled `unqualified` until a recorder profile is qualified.
- A third operation kind extends the `0007` constraints again, additively. Transcription
  and render behaviour must be proven unchanged.
- Operators configure `ffprobe` alongside `ffmpeg`, and the distribution posture does not
  change (ED-0075).
- The new binary invocation needs the same security review as ED-0087: path handling, no
  shell, and bounded output parsing.

## Validation

The implementing plan must include:
- migration forward, reverse, and reapply tests;
- tests showing transcription and render are unchanged;
- claim, lease, fence, and retry tests for `media_timing`;
- fake-`ffprobe` tests, including missing or malformed fields, naive timestamps, and
  oversized output;
- an MTE application round trip;
- enqueue idempotency;
- a host run over real recordings from the live run, comparing the derived intervals with
  the vMix reconnaissance;
- a `/security-review` pass.

## Related documents

- ADR-0021 (time authority), ADR-0025 (Durable Operations), ADR-0026 (automation
  inactive), ADR-0027 (Media Timing Evidence), ADR-0032 (render and substrate
  generalization).
- ED-0087, ED-0088, and the vMix media timing reconnaissance and calibration documents.
