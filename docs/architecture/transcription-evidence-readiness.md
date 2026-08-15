# Transcription evidence readiness

## Status

**Proposed provider-neutral architecture; no production implementation authority.**

This document prepares the first transcription evidence boundary requested by the
recorder-calibration/transcription-readiness milestone. It specializes the accepted
post-Kernel direction without accepting proposed ADR-0025, selecting a provider/model,
adding persistence, or claiming transcription execution exists.

`Transcript Evidence Revision` is a provisional qualified term. It remains visibly
unresolved in the domain glossary until the persistence/consumer design is accepted.

## Evidence and authority boundary

A transcript result is evidence about the audible content of one immutable Completed
Media Asset manifest revision. It is not the Session Transcript described by the
foundational product model, a Session boundary, media-membership authority, an Editorial
Candidate Moment, an Editorial approval, or package state.

The first boundary preserves these epistemic meanings:

- provider text, language, offsets, word timing, labels, and known-semantics scores are
  **Observed provider result**;
- speaker diarization labels and language detection are **provider/inference-derived**,
  not verified participant identity;
- wall-clock intervals calculated from asset-relative offsets and Media Timing Evidence
  are **Derived advisory evidence**;
- a human correction or approval is a later explicit **Declared** decision; and
- Session boundaries/membership remain separate authoritative state.

Provider execution and Durable Operation state answer whether/how work ran. Transcript
Evidence answers what immutable provider result StageFlow retained. Neither substitutes
for the other.

## Smallest coherent revision

```text
TranscriptEvidenceRevision (provisional)
  stable transcript-evidence identity
  asset-scoped revision + predecessor revision identity
  Completed Media Asset identity
  manifest identity + manifest version
  result status: partial | complete | failed
  requested/observed language facts
  provider identity + adapter version
  model identity + model version/revision
  execution tool/runtime identity + version
  operation/attempt/work-key provenance when execution is durable
  requested/started/provider-completed/received/applied timestamps
  configuration profile/fingerprint (sanitized; no secrets)
  transcript segments[]
  failure reason/phase when partial or failed
  limitations[]
  reprocessing reason + predecessor identity
```

Each segment contains:

- stable identity within its evidence revision and deterministic order;
- exact provider text as retained by the adapter;
- non-negative asset-relative start and end offsets with explicit precision;
- optional provider segment identity;
- optional language fact when it differs from the result-level language;
- optional provider/inference-derived speaker label with explicit label origin;
- optional word items carrying text, asset-relative start/end, and speaker label only
  when supplied; and
- optional score facts only through the known-semantics structure below.

Segments must not overlap their own word bounds inconsistently, end before they start,
or extend past the asset duration beyond an explicit provider/measurement tolerance.
Provider ordering is preserved as an Observed fact; StageFlow may also retain a
deterministic normalized order, but it does not rewrite the provider representation.

### Confidence and probability

A bare `confidence: float` is prohibited in the durable result. Every retained score
must name:

- scope (`result`, `segment`, `word`, `language`, `speaker_label`, or another accepted
  bounded value);
- provider field/semantic name;
- numeric value and scale/range;
- direction (`higher_is_better`, `lower_is_better`, or provider-defined);
- calibration/interpretation statement when known; and
- an explicit limitation when the value is not comparable across models or versions.

Unknown-semantics scores may remain in an external/raw provider artifact under its data
handling policy, but they are not normalized into durable StageFlow confidence.

### Partial and failed results

`partial` means a bounded usable subset of segments is retained while omissions,
provider truncation, cancellation, or a later processing failure is explicit. `failed`
contains no successful transcript claim but retains bounded provenance, failure phase,
retry classification reference, time, and limitations. It does not copy raw stderr,
stack traces, source paths, credentials, or provider payloads.

Durable Operation failure/retry status remains in Work Execution. A partial/failed
evidence revision is appended only when retaining that provider result has domain value;
an infrastructure failure before any provider result need not manufacture transcript
evidence.

### Revision and replay

- Exact application replay by stable operation/work key and input/result digest returns
  the existing evidence revision.
- Conflicting replay fails visibly.
- Reprocessing appends the next asset-scoped revision and links its immediate predecessor.
- Changing provider, model, execution version, language mode, diarization mode, or
  behavior-driving configuration creates a new revision rather than rewriting history.
- Replacing the Completed Media Asset manifest creates a different input identity; no
  result crosses manifests implicitly.
- Earlier revisions remain available for lineage and reproducibility. No automatic
  deletion/compaction policy is selected here.

## Provider-neutral execution port

The provider port is a worker-side execution boundary, not a Production ingress adapter.
Its minimum conceptual request/response is:

```text
TranscriptionExecutionPort.execute(request, cancellation)

request
  stable work key + operation/attempt/fencing context
  Completed Media Asset + manifest identity/version
  adapter-owned readable resource handle (not a domain filesystem path)
  requested language/detection mode
  requested timing/word/diarization capabilities
  provider/model/configuration profile identity/version
  bounded telemetry and output limits

response
  complete | partial | failed provider result
  provider/model/execution identity/version
  observed language facts
  ordered asset-relative segments/words
  provider/inference-derived labels
  known-semantics score facts only
  sanitized limitations/failure facts
  processing timestamps and bounded performance telemetry
```

The port must expose capabilities rather than promise unsupported values. Required
adapter reconnaissance before selection:

| Requirement | Adapter obligation |
| --- | --- |
| Local/offline | Declare whether model acquisition and execution work with no Internet |
| GPU | Declare runtime/device requirements and safe CPU fallback or no-fallback behavior |
| Asset formats | Declare accepted container/audio codecs and adapter-owned conversion need |
| Timestamps | Declare segment/word availability, unit, precision, and boundary semantics |
| Diarization | Declare availability and preserve labels as inferred/provider-derived |
| Language | Separate requested, detected, and provider-reported language plus score semantics |
| Replay | Declare deterministic guarantees/known variance for the same model/config/input |
| Partial failure | Return usable bounded output plus explicit omitted range/failure phase |
| Cancellation | Cooperatively observe cancellation and report whether an external call may continue |
| Telemetry | Report bounded duration/resource/provider facts without payloads, secrets, or paths |

No provider or model is selected by this document. Local and cloud adapters must satisfy
the same domain result boundary. A cloud adapter remains deferrable in Event Mode.

## Media Timing Evidence alignment

The original asset-relative result is immutable and remains the primary transcript
timing observation:

```text
Observed provider segment: [23.420 s, 28.100 s) relative to asset start
MTE derivation: candidate asset start T
Derived advisory alignment: [T + 23.420 s, T + 28.100 s)
```

`WallClockTranscriptAlignment` is a separate proposed Derived evidence revision linked
to all of:

- Transcript Evidence identity/revision and segment identities;
- Media Timing Evidence identity/revision and selected derivation identity;
- Completed Media Asset/manifest identity;
- deterministic alignment rule identity/version;
- recorder-profile qualification state observed at derivation time;
- derived wall-clock segment intervals and precision; and
- limitations, including source offset precision and MTE qualification/tolerance.

The alignment rule is exact arithmetic over explicit inputs. It never overwrites
asset-relative offsets. Missing/naive MTE anchors produce no wall-clock interval.
Unqualified MTE may produce an explicitly unqualified candidate alignment for diagnostic
or qualification display; a consumer requiring qualified timing must reject it.

A new transcript or MTE revision produces a new alignment revision. Existing alignments
remain historical evidence. Alignment can support future Editorial navigation,
diagnostics, and proposals, but cannot directly alter Session boundaries, Session
membership, ADR-0024 association, package state, Producer authority, or publishing.

## Persistence and transaction candidate

After the model and ADR-0025 are accepted, the smallest PostgreSQL ownership is one
append-only transcript-evidence parent plus typed segment, optional word/score, and
idempotency rows. Alignment uses a separate parent/interval set because its inputs and
revision cadence differ from transcript output. Large raw provider artifacts and media
remain outside these rows behind explicit manifests and retention policy.

When the Operation and evidence share PostgreSQL, applying the transcript revision and
marking the Operation succeeded with its terminal result reference occur in one
transaction. Stale fencing generation rejects both. No in-memory authoritative fallback
or outbox is required for the first local consumer.

Exact table names, migration, storage limits, raw-artifact retention, public API shape,
and Session Transcript composition remain implementation-plan decisions after the
Yellow gates.

## Required validation after acceptance

- strict aware-time, non-negative range, end ordering, asset-duration tolerance, and
  recursive immutability contract tests;
- exact/conflicting replay, predecessor/revision, manifest replacement, and concurrent
  append tests;
- partial/failed/reprocessed result and provider/model/configuration lineage tests;
- provider label and score-semantic preservation tests;
- alignment arithmetic, precision propagation, missing/naive anchor, revised input,
  qualified/unqualified MTE, and no-authority-side-effect tests;
- stale fencing, duplicate execution, crash-before/after provider return, and atomic
  Operation/result commit tests after ADR-0025; and
- sanitized projection tests proving paths, secrets, raw payloads, and unbounded transcript
  data do not leak into Producer status.

## Deferred decisions

- acceptance and canonical naming of Transcript Evidence/Alignment aggregates;
- raw provider artifact retention/deletion and encryption policy;
- first provider/model/dependency and local GPU runtime;
- Session Transcript stitching across asset revisions and overlapping media;
- human transcript correction/review ownership;
- diarization-to-participant identity resolution;
- first Editorial Candidate policy and any automatic AI authority; and
- public APIs, UI pagination/search, and export/caption formats.

None of these may be inferred from provider output or implemented through metadata.
