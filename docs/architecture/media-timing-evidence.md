# Media Timing Evidence v1 architecture

## Status

**Accepted and implemented by the completed Green Media Timing Evidence v1 plan.**

This document records the provider-neutral production boundary approved by MTE-001
through MTE-005 and [ADR-0027](../adr/ADR-0027-media-timing-evidence.md). It does not
qualify any recorder profile, authorize automatic association, or select a production
inspection worker/provider.

## Evidence and epistemic boundary

The [vMix reconnaissance](../validation/vmix-media-timing-reconnaissance.md) found stable
embedded recorder metadata and reproducible candidate intervals but no independent
content-time ground truth. For current vMix evidence:

- embedded `creation_time` is **Observed**;
- measured media duration/timing is **Observed**;
- `creation_time + duration` candidate interval is **Derived**;
- exact captured-content-start semantics are not qualified; and
- human Session authority is **Declared**.

Observed, Derived, Inferred, Declared, and External meanings remain distinct. A derived
candidate interval never renders or persists as authoritative Session/content truth.

## Aggregate and invariants

`MediaTimingEvidence` is a dedicated, immutable, durable, revisioned aggregate linked to
one Completed Media Asset and its manifest identity. It does not add mutable timing fields
to the Completed Media Asset and does not specialize generic Semantic Evidence.

```text
MediaTimingEvidence
  evidence identity + asset-scoped revision
  Completed Media Asset identity + manifest identity/version
  inspection provenance
    provider/tool identity and version
    recorder/source profile identity and revision
    inspected/applied time + reprocessing identity
  raw observations[]
    observation kind, normalized value, original representation
    precision, timezone normalization, source field, stream selector
  derivations[]
    rule/version, input observation identities, candidate interval
  recorder-profile qualification status
  limitations + revision predecessor
```

Required invariants:

- all supplied/persisted timestamps are timezone-aware;
- observations are explicitly Observed and derivations explicitly Derived;
- raw values are immutable and never rewritten as a later interpretation;
- every derivation names its complete input set and deterministic rule/version;
- naive or invalid timestamp material may retain a sanitized original representation but
  cannot become a normalized absolute timestamp or candidate interval;
- qualification is recorder/source-profile scoped and never generalized to all MP4/vMix;
- revision `n > 1` links to the immediately preceding evidence identity;
- an exact application replay returns the original revision; conflicting replay fails;
- asset and manifest identity prevent evidence crossing a replaced/reprocessed asset;
- limitations are explicit, immutable, and non-authoritative; and
- arbitrary provider diagnostics, credentials, private paths, and unnecessary filenames
  are prohibited from the durable model and read projection.

## Persistence and revision semantics

PostgreSQL owns one append-only evidence table plus typed child observation and derivation
tables. Asset-scoped revision is unique. Observation and derivation identities are unique
within their parent revision; derivation inputs reference observations from that same
revision. A separate idempotency row preserves exact application replay and request digest.

The active revision is the highest committed revision for an asset. Earlier revisions are
retained for the durable life of the asset. V1 selects no automatic compaction or deletion
policy and performs no backfill for pre-existing assets.

Forward migration is additive. Reversal removes only MTE-owned rows/tables and its schema
ledger entry; it never changes Completed Media Asset, Session, association, or package
state. Reversal remains an explicit isolated-database operator action.

## Application and inspection boundaries

- `MediaTimingInspectionPort.inspect(request)` is a future provider-neutral execution
  seam. No production adapter, watcher, scheduler, queue, broker, or worker is selected.
- `MediaTimingEvidenceApplication.apply(request, result)` validates and commits already
  inspected evidence synchronously and idempotently.
- `MediaTimingEvidenceRepository.append/get_active/history` owns durable evidence only.
- qualification tooling may continue synchronous local inspection outside production.

Actual long-running production inspection must use the durable worker boundary only after
ADR-0025 reaches its existing Yellow gate. Transcription remains the intended first
durable worker consumer and no provider/model is selected by MTE v1.

## Qualification representation

V1 preserves recorder-profile qualification state as `unqualified`, `qualified`,
`rejected`, or `expired`, with profile identity/revision and explicit limitations. The
current vMix profile remains `unqualified`. Accepting any recorder profile as qualified
content-time evidence is a later Yellow decision supported by controlled calibration.

Qualification status does not grant Session, membership, package, or publishing authority.
There is no confidence-to-authority promotion system.

## Authorized consumers

MTE v1 is advisory evidence. Narrow consumers may display it, align transcript evidence,
produce Session-boundary proposals or association suggestions, support later Editorial
timing, and assist diagnostics/qualification.

MTE v1 cannot directly mutate authoritative Session Start, Presentation End, Session
membership, ADR-0024 association semantics, Package Ready, Package Complete, or any other
authority-bearing state. Producer Attention remains unchanged by ordinary MTE presence.

## Read projection and disclosure

The read projection exposes asset/evidence/revision identity, observed facts, derived
candidate intervals, sanitized provenance, qualification state, limitations, and advisory
use. It omits source paths, filenames, credentials, raw FFmpeg stdout/stderr, and arbitrary
diagnostics. Missing evidence is a normal empty history, not a failure or authority fact.

## Transcription relationship

```text
Completed Media Asset
  -> Media Timing Evidence (advisory)
  -> future transcription input/job
  -> asset-relative transcript evidence
  -> optional derived wall-clock-aligned transcript evidence
```

Transcript evidence remains separate and non-authoritative Session evidence.

## Remaining Yellow boundaries

- qualifying a concrete recorder/source profile and calibration thresholds;
- allowing MTE to change automatic Session association or eligibility;
- accepting ADR-0025 worker/lease execution for production inspection/transcription;
- automatic AI authority or a consequential inspection/provider dependency.
