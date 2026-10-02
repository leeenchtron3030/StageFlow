# Transcription evidence readiness

## Status

**Accepted bounded provider-neutral architecture; first-worker substrate implemented.**

This document defines the first transcription evidence boundary requested by the
recorder-calibration/transcription-readiness milestone. It specializes the accepted
post-Kernel direction and accepted ADR-0025. Migration 0007 and the bounded internal
contracts/repository implement the provider-neutral evidence and operation substrate.
When local transcription is configured, Demo media reconciliation enqueues transcription
for registered Completed Media Assets across the Event, including unassociated assets.
The bounded, default-off Demo 2 coordinator invokes this reconciliation automatically
(`backend/app/demo/autonomous.py`); coordinator activation defaults are unchanged.
ED-0123, following the owner-approved D5 parity result, makes transcription GPL-free
and part of the default install under ADR-0036. The worker composes
`CTranslate2WhisperExecutionAdapter` behind the unchanged provider-neutral Work Execution
port. Existing transcripts remain readable with their recorded provider identity;
removing the legacy engine changes no transcript contract, schema or migration.

`Transcript Evidence Revision` is the accepted internal asset/manifest-scoped evidence
term. Session Transcript composition and broader transcript APIs remain unresolved.

## Default local engine (ED-0122 / ED-0123)

`CTranslate2WhisperExecutionAdapter`, in
`backend/app/infrastructure/transcription/ctranslate2_whisper/`, provides the
`stageflow-ctranslate2-whisper` identity, provider version `1.0`, execution revision
`stageflow-ctranslate2-whisper-adapter-1.0`, and execution tool `ctranslate2` 4.8.1.
The MIT faster-whisper 1.2.1 inference subset is ported locally: numeric features,
tokenizer, sequential 30-second windows, temperature fallback, prior-text conditioning,
and native word alignment with reference word-merging/timing rules. English is fixed
under ADR-0036 decision 5, including when `requested_language` is `None`; there is no
automatic language detection, and explicit non-English requests are refused.
VAD, batching, translation and model downloads are absent. Infrastructure owns all
NumPy and CTranslate2 use; domain contracts and persistence are unchanged.

CTranslate2 4.8.1, tokenizers 0.23.1 and NumPy 2.5.2 are default dependencies;
the `transcription` and `transcription-core` groups and legacy adapter are removed.
CTranslate2's version-pinned native extension is loaded directly because
its public package initializer imports conversion helpers that attempt to import
`huggingface_hub`. The new inference path loads none of PyAV, faster-whisper,
huggingface_hub, onnxruntime or tqdm. Synthetic tests exercise this in a clean process.

Absent `[local_transcription].ffmpeg_path` inherits
`[local_media_segmentation].ffmpeg_path`; without either path configuration refuses with
`local_transcription_ffmpeg_path_required`. Invalid explicit paths are never replaced.
Preflight checks the model directory and `tokenizer.json`, FFmpeg file and CTranslate2
inference import with closed `local_transcription_model_unavailable`,
`local_transcription_ffmpeg_unavailable`, and `local_transcription_runtime_unavailable`
codes, then exercises synthetic inference.

The decoder uses explicit-path operator LGPL FFmpeg and sibling ffprobe, checks
their versions/build flags and hashes, probes the first audio stream, and averages
1–8 channels explicitly. It produces s16le at 16 kHz, converted to float32 by
32768. Output is capped at the probed duration plus one second; decode time is bounded
to 30–600 seconds and inputs over four hours are refused. Probe output is capped at
64 KiB. Lease callbacks run during subprocess waits and once per inference window,
including silent windows. Decode failures are retryable `media_decode_failed`;
missing/refused tools, tokenizer, model and runtime are non-retryable. An iteration
failure after retained segments produces partial evidence, except `IndexError`, which
raises retryable `provider_execution_failed` even after a segment was retained.
Worker startup JSON reports first-class decode/probe tool names, versions and SHA-256
hashes alongside `device`, `compute_type` and `execution_profile`, without paths.
These disclosures do not enter persisted transcript evidence or its `limitations`.
A first-class decode provenance field in transcript evidence is deferred to a later
contract plan; ED-0122 does not change that contract.

Supported execution pairs are CUDA/float16 (default) and CPU/int8 (explicit).
The default provider is `stageflow-ctranslate2-whisper` and the default profile is
`ct2-whisper-large-v3-turbo-cuda-float16` version `1.0`. CPU uses a distinct profile
such as `ct2-whisper-large-v3-turbo-cpu-int8`. Worker capabilities report the configured
profile and provider. Legacy `provider = "faster-whisper"` is refused with actionable
migration guidance, never silently remapped. Every `faster-whisper*` profile id is refused.

Under D6, use distinct profile identities for different engines/devices/compute types,
switch between Events and keep each existing Event's profile for its lifetime.
A deliberate profile change on an existing Event re-transcribes every registered asset
through ED-0120; earlier evidence remains readable and immutable with its own provider
identity. Pending legacy-profile work requires the prior installation or a deliberate
profile switch. The [owner D5 parity gate passed](../validation/results/transcription-engine-parity-001.md)
before ED-0123. Synthetic tests establish implementation behavior, not event readiness.

## Trigger scope and replay

`DemoApplication.reconcile_media` selects up to 500 registrations per Event cycle in
ascending `registered_at` order, with asset ID breaking ties. The PostgreSQL query selects
assets without matching transcription work, rather than the newest 500 media records.
Durable enqueues remove assets from subsequent batches. A process-local keyset cursor
advances past each full page, including enqueue failures, and wraps after a short or empty
page. This lets later registrations proceed even if 500 earlier assets persistently fail.
The cursor is selection progress only: restart resets it and safely rescans using durable
operation inputs. A backlog larger than 500 drains across cycles.
Timing and segmentation retain their existing independent enqueue paths and bounds.

Operation identity derives from deployment, Event, asset, manifest identity/version and
execution profile identity/version. The idempotency key uses that deterministic UUID to
stay within the existing identifier length bound. Session identity is absent. The existing
Session-scoped manual trigger retains its request/response shape and 500-asset bound;
it selects associated registrations in arrival order and reports their existing operations.
Later association or re-association does not create new transcription work.

Selection checks operation inputs across the full journal, including operations with old
Session-scoped keys. All statuses count as existing work. Retryable execution failures
remain on the original operation with its existing attempt limit and retry delay (three
attempts and 30 seconds for Demo enqueues); terminal failures are reported by the Session
trigger and are not automatically replaced. An enqueue failure that stored no operation
is eligible again on a later scan pass. A changed execution profile is distinct work.
Absence of local transcription still enqueues nothing and retains the existing
`local_transcription_not_configured` error; this does not change installation defaults.

Suggestion runs read the latest complete transcript reference per asset even before
association. Transcript arrival supplies evidence only; it grants no Session, association,
Editorial, or package authority. Synthetic memory and rolled-back PostgreSQL coverage is
in `backend/tests/test_event_asset_transcription.py`.

## Read-only asset availability

ED-0121's owner-approved deviation (2026-09-30) adds
`GET /api/v1/transcription/assets/{asset_id}/status`, protected by the existing API
shared-secret dependency. Its allowlisted response contains only `asset_id`,
`operation` (null or `state`, `execution_profile_id`, `execution_profile_version`),
`complete_evidence`, and `partial_evidence`. It exposes no transcript text, words,
paths, connection details, worker output, or diagnostics.

The operation read matches the current deployment, asset's Event, current manifest
(version `1.0`), and currently configured transcription profile. It reuses the legacy
operation-selection ordering from the Session trigger. Evidence availability is
asset-wide: complete means a latest `evidence_status='complete'` revision exists,
exactly as selected by suggestion snapshots. Later partial/failed revisions do not
hide it; partial is true only when partial evidence exists and complete evidence does
not. An operation's success alone does not imply complete evidence.

Unknown assets return 404 `completed_media_asset_not_found`; missing Kernel composition
returns 503 `kernel_not_configured`, absent transcription configuration returns 503
`local_transcription_not_configured`, and unavailable Kernel/work storage returns 503
`postgresql_unavailable`. This read does not enqueue work or change evidence, schema,
Session authority, or transcription installation defaults. Broader transcript APIs
remain deferred. Synthetic fake/memory and rolled-back PostgreSQL tests are in
`backend/tests/test_transcription_status_api.py`.

## Evidence and authority boundary

Editorial phrase derivation is now a read-only consumer of the latest complete revision
for each currently associated asset. Later partial or failed revisions do not replace
that complete input. Matching uses normalized word text and word ordinals within one
segment; it never bridges segments or manufactures word times from segment text.
Every derived candidate retains asset, evidence ID/revision, segment ID, first/last word
IDs and asset-relative offsets, plus the advisory MTE revision used for placement.
An operator publishes the phrase-list version and explicitly invokes the derivation run.
Neither transcript arrival nor a new evidence revision automatically generates candidates.
The existing human review and Clip creation remain the only Editorial approval path.

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
adapter reconnaissance for any further selection:

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

The accepted first local baseline is recorded in
`docs/validation/transcription-engine-evaluation.md:133`; the core execution port remains
provider-neutral (`backend/app/contexts/transcription_evidence/application.py:40`). Local
and cloud adapters must satisfy the same domain result boundary. A cloud adapter remains
deferrable in Event Mode.

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

The implemented smallest PostgreSQL ownership is one append-only transcript-evidence
parent plus typed segment, optional word/score, and operation idempotency rows. Alignment
uses separate typed rows because its inputs and revision cadence differ from transcript
output. Large raw provider artifacts and media remain outside these rows behind explicit
manifests and retention policy.

Because the Operation and evidence share PostgreSQL, applying the transcript revision and
marking the Operation succeeded with its terminal result reference occur in one
transaction. Stale fencing generation rejects both. No in-memory authoritative fallback
or outbox is required for the first local consumer.

Migration 0007 fixes the bounded internal table names and constraints. Raw-artifact
retention, public API shape, and Session Transcript composition remain later decisions.
No provider-specific storage or automatic downstream authority is implied.

## Validation contract

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
- broader production-provider/model qualification beyond the accepted first local baseline
  (`docs/validation/transcription-engine-evaluation.md:140`);
- Session Transcript stitching across asset revisions and overlapping media;
- human transcript correction/review ownership;
- diarization-to-participant identity resolution;
- first Editorial Candidate policy and any automatic AI authority; and
- broader transcript APIs, UI pagination/search, and export/caption formats.

None of these may be inferred from provider output or implemented through metadata.
