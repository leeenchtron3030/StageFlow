# Media Timing Evidence v1 architecture

## Status

**Accepted and implemented by the completed Green Media Timing Evidence v1 plan.**

This document records the provider-neutral production boundary approved by MTE-001
through MTE-005 and [ADR-0027](../adr/ADR-0027-media-timing-evidence.md). It does not
qualify any recorder profile or authorize automatic association. ADR-0033 now supplies
the production inspection worker/provider described below.

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

- `MediaTimingInspectionPort.inspect(request)` retains the original provider-neutral
  execution seam. The production inspection worker uses the typed `TimingInspector`
  boundary and an operator-installed local `ffprobe` adapter under ADR-0033.
- `MediaTimingEvidenceApplication.apply(request)` validates and commits already
  inspected evidence synchronously and idempotently.
- `MediaTimingEvidenceRepository.append/get_active/history` owns durable evidence only.
- qualification tooling may continue synchronous local inspection outside production.

Production inspection uses the shared ADR-0025 lease, retry, fencing, capability, and
presence substrate with the `media_timing` operation kind. The optional, default-off
`[local_media_timing]` configuration enables enqueue during Demo reconciliation for newly
registered assets. Existing assets require an explicit bounded human enqueue command.
Neither path depends on Session association. The separate CPU worker
`python -m app.demo.media_timing_worker` defaults to two concurrent inspections (maximum
eight). Transcription and render capabilities and views remain isolated.

The `container-creation-time` v1 inspection profile runs the rule
`creation_time_plus_duration` v1. The adapter checks an explicit absolute local binary
path, version and SHA-256, refuses GPL/nonfree configuration and shell wrappers, and
rechecks identity before every inspection. It invokes JSON format/stream inspection with
stdin and stderr connected to `DEVNULL`, a file-only protocol whitelist, a 1 MiB stdout
cap, and a 30-second timeout per invocation. Raw JSON and stderr are never retained.
Only container creation time/duration and the first video stream's start/duration are
projected. Signed stream start is a relative numeric observation, not an absolute time.
Naive, invalid, missing, or unsafe creation-time text produces an explicit limitation;
no timezone is guessed. An interval requires valid aware creation time and valid duration.
Recorder qualification remains `unqualified`, with explicit recording-start/file-open
and captured-content-duration limitations.

Evidence is applied exclusively through `MediaTimingEvidenceApplication.apply` using a
transaction-bound PostgreSQL repository. The active lease fence, evidence application,
attempt finalization, and terminal MTE reference share one transaction. Expiry recovery
recognizes already committed asset/manifest-matching MTE results. Typed failures release
leases with bounded reason codes; unexpected exception messages are never persisted.
Resolver errors preserve their retryability. Definite apply-time storage failures
schedule a retry; an ambiguous commit leaves the attempt for reconciliation.

Authenticated `/api/v1/media-timing/events/{event_id}/requests` accepts human-confirmed
asset pages (1–100, `after` asset ID) and idempotently enqueues by asset/manifest/profile.
`GET .../events/{event_id}/operations` pages by operation ID with the same limit bounds.
`GET .../assets/{asset_id}/latest` returns one bounded advisory summary: revision,
qualification, limitations, and candidate interval. Reads remain available when enqueue
is disabled. These responses expose no source paths or raw tool output.

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
- automatic AI authority or a new consequential inspection/provider dependency beyond
  ADR-0033's operator-installed ffprobe.

Host comparison against live-run reconnaissance and the owner's security review remain
separate qualification steps; contract and persistence tests do not establish event readiness.
