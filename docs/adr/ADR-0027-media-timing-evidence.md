# ADR-0027: Durable advisory Media Timing Evidence

## Status

Accepted

## Date

2026-08-12

## Context

Run 004 reconnaissance found recorder/container timestamps and measured duration that can
produce reproducible candidate intervals, but it did not qualify embedded vMix
`creation_time` as exact captured-content start. Completed Media Asset is immutable
completion/readiness authority and generic Semantic Evidence references interpreted
Observations; neither owns revisable inspection facts, derivation lineage, recorder-profile
qualification, or sanitized inspection provenance.

MTE-001 through MTE-005 were explicitly approved to resolve ownership, qualification
scope, execution, authorized consumption, and retention/disclosure.

## Decision

StageFlow introduces a separate durable, immutable, append-only, revisioned
`MediaTimingEvidence` aggregate linked to one Completed Media Asset and manifest identity.
Multiple revisions and different inspection sources/profiles are permitted. Mutable
authoritative content-start/end fields are not added to Completed Media Asset.

Recorder qualification is scoped to an explicit recorder/source profile and revision.
Raw vMix observations may be retained while unqualified; no vMix/MP4-global timing claim
is made. Normalized raw observations, original representation where necessary, precision,
timezone facts, provider/tool identity and version, derivation rule/version, derived
candidate interval, qualification status, and limitations are retained. Arbitrary provider
diagnostic dumps, credentials, private paths, and unnecessary filenames are prohibited.

Application of already-inspected results is a provider-neutral synchronous boundary with
durable idempotency and revision semantics. V1 selects no watcher, scheduler, broker,
worker, or production inspection provider. Long-running production inspection remains
behind ADR-0025's Yellow worker decision.

MTE v1 is advisory only. It may be displayed or consumed by future proposal, transcript,
Editorial, diagnostic, and qualification workflows. It cannot mutate Session boundaries,
membership, ADR-0024 association behavior, or package authority. Observed, Derived,
Inferred, Declared, and External meanings remain explicit.

Evidence revisions are retained for the durable life of their asset. V1 selects no
automatic compaction/deletion policy.

## Alternatives

- Extending Completed Media Asset was rejected because a finalized asset must not acquire
  mutable/revisable interpretation fields.
- Specializing generic Semantic Evidence was rejected because MTE owns inspection and
  qualification lineage rather than references to interpreted Production Observations.
- Global MP4/vMix qualification was rejected because recorder configuration/version and
  independent calibration determine semantics.
- Automatic association consumption was rejected because it would silently change
  ADR-0024 and Run 004 did not qualify content correctness.
- Persisting raw FFmpeg output was rejected because it is unnecessary, unstable, and may
  disclose private paths or diagnostic material.

## Consequences

- PostgreSQL gains additive MTE parent/observation/derivation/idempotency tables.
- Exact replay returns the original revision; reprocessing under a new operation appends
  and links the next asset-scoped revision.
- Existing assets can have no MTE and require no backfill.
- UI and future consumers must label candidate intervals advisory and show qualification
  and limitations.
- Recorder-profile qualification, worker execution, and automatic authority remain
  separate future decisions.

## Validation

- Contract tests enforce aware time, raw/derived separation, lineage, recursive
  immutability, and sanitized values.
- Repository tests cover asset linkage, exact/conflicting replay, revision ordering,
  reconstruction, migration reversal, and storage unavailability.
- Application/API tests prove no Session association, boundary, or package mutation and
  verify bounded sanitized projections.
- Frontend tests verify MTE appears only in relevant drill-down and never ordinary
  Producer Attention.

## Related documents

- [Media Timing Evidence architecture](../architecture/media-timing-evidence.md)
- [MTE v1 implementation plan](../plans/media-timing-evidence-v1.md)
- [ADR-0024](ADR-0024-durable-kernel-authority-and-persistence.md)
- [ADR-0025](ADR-0025-postgresql-durable-operations-and-workers.md)
- [vMix reconnaissance](../validation/vmix-media-timing-reconnaissance.md)
