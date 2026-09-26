# Persistence boundary

## Accepted authority

PostgreSQL is StageFlow's authoritative durable operational store under ADR-0022. It is
deployable on the local event network, must not require Internet connectivity for the
event-critical path, and may be shared by future StageFlow nodes. Media content remains
outside PostgreSQL and is referenced by durable records. PostgreSQL unavailability must
never redirect authoritative writes into process memory.

## Current implementation

The current branch implements stable ingress, the bounded Durable Event-Mode Kernel,
Media Timing Evidence, and the first bounded transcription-worker persistence slice:

- repository-neutral stable ingress contracts under `production.ingress`;
- a synchronous Psycopg 3 PostgreSQL adapter under `infrastructure.postgres`;
- one explicit `stageflow.production_event_ingress` table with database uniqueness for
  stable source identity plus source key or versioned canonical fingerprint;
- stable ingress and Production Event IDs, exact replay/conflict outcomes, first/last
  receipt evidence, and a delivery count;
- explicit numbered forward and reversal SQL plus a narrow migration runner; and
- a process-local repository that is labeled and used only as a non-durable test double.

`0002_event_mode_kernel` adds normalized Business Event, Stage/source binding, Program
Expectation, realized Session, media candidate/observation/asset/association, completion,
and reconciliation tables. Typed append-only revision/history tables preserve bootstrap,
Program Expectation, Session boundary, association, and completion authority. Current
state and consequential history change in the same Psycopg transaction. There is no
generic event store, Job table, media blob, or event-sourcing projection rebuild.

`0003_kernel_projections` adds only append-only advisory Session-boundary proposals,
including evidence, epistemic kind, proposer, policy, optional model lineage, and aware
proposal/boundary times. It does not update the authoritative Session projection; human
boundary decisions remain in `session_boundary_history` and the Session transaction.

`0004_kernel_review_corrections` adds narrow human-command idempotency, deterministic
association policy/input provenance, completion-membership snapshots, operation identity
on consequential history, and stronger history constraints. Association membership and
every materially affected completed Session now change in one transaction; earlier
completion decisions and their approved asset sets remain reconstructable.

`0005_kernel_follow_up_closure` classifies completion membership as recorded,
deterministically reconstructed, or unresolved. It reconstructs legacy reopened
completion membership only from strictly prior association history and records equal-time
ambiguity without fabricating membership. It also stores versioned original Session
result snapshots for new consequential human commands so delayed PostgreSQL replay
matches the original operation after later state changes.

`0006_media_timing_evidence` adds a dedicated append-only advisory evidence parent,
typed Observed timing rows, typed Derived candidate-interval rows with explicit input
lineage, and exact application-idempotency records linked to Completed Media Asset.
Asset-scoped revisions preserve earlier interpretations. The schema stores sanitized
normalized facts/provenance/limitations rather than private paths or provider dumps and
does not update Session, association, or package tables.

`0007_transcription_worker` adds durable transcription Operations, retained Attempts,
durable Worker identity and effective-dated capability declarations, one replaceable
expiring Worker Presence observation, and normalized Transcript Evidence revision,
segment, word, and optional advisory MTE-alignment rows. Claims, renewal, expiry,
reconciliation, and result application use PostgreSQL coordination and database time.
Attempt history and evidence are durable; live health/capacity/pressure expire, and
current utilization derives from valid leases rather than a durable utilization field.
The schema does not select a provider/model, enqueue automatically, or change Session,
media, package, Editorial, recorder-profile, or AI authority.

`0008_demo_vertical_slice` introduced the immutable human-declared Editorial Candidate
Moment declaration record and command replay used by Demo 1.
`0010_editorial_candidate_moment` adds only append-only Session-boundary location
evaluations, preserving the declaration record while making contained, partially
excluded, and excluded locations restart-safe and queryable. It does not alter Kernel
Session tables or add review, Clip, worker, model, or automatic authority.
`0011_editorial_review_foundation` adds append-only human review decisions with
digest-based exact/conflicting replay, deterministic append ordering, and immutable
Editorial Clips created only by approval. Current review state and the bounded
Event-scoped queue derive from decision history; no Session, package, render, export, or
publishing state is added.

`0012_packaging_asset_foundation` adds only Assembly-owned Packaging Asset identities,
immutable content revisions, append-only human approval decisions, and command receipts.
It reuses the canonical human-command digest mechanism with a capability-local receipt
table, as existing command-kind constraints remain unchanged. Registration/revision/
approval receipts and results commit atomically; exact replay returns the original
immutable result even after later activity. A per-asset row lock serializes revision
numbering and decision ordering; stale expected revisions fail explicitly. Revision and
decision tables additionally reject updates/deletes with append-only triggers.

Event and optional Stage foreign keys enforce applicability; a Completed Media Asset
reference must exist at write time. External content uses an opaque alphanumeric/hyphen/
underscore key, lowercase SHA-256, byte size, and declared media type; no path or media
blob is accepted or persisted. Effective endpoints are optional aware timestamps and,
when both are supplied, form a nonempty interval. ED-0077 resolves applicability using
start-inclusive, end-exclusive effective intervals.
Bounded Event-scoped asset and revision pages use batch SQL with a repeatable-read snapshot,
counts and explicit continuation/truncation. Approval derives from the latest append
sequence for each revision, independent of decision clock ordering. The in-memory
implementation is a non-durable test repository, never a runtime fallback.

`0013_session_assembly_foundation` adds only Assembly-owned template, revision, member,
binding, metadata snapshot, approval decision, and command receipt tables. Templates are
versioned within `(event_id, template_key)` and retain ordered slot configuration.
Revision columns pin Session, package revision, template version identity, supersession,
completion decision, validation, and actor/time. Child rows freeze completion membership
and association revisions in media-start order (asset ID breaks equal-time ties), exact
Packaging Asset revision references, and Program Expectation metadata source revisions.
Missing media start or unavailable completion membership produces typed invalidity.
No live association projection supplies proposal membership.

All seven new tables reject updates/deletes. Command receipts and append-only results
commit atomically. Event row locks serialize template versions; Session row locks
serialize proposals and decisions against Kernel package changes. Packaging root share
locks coordinate candidate/approval reads with ED-0076's decision/revision locks. These
locks do not mutate upstream rows. Exact replay reads the original result before current
eligibility checks; conflicting replay and stale expected revisions fail explicitly.
Decision concurrency guards count decisions for the target revision; decision sequence
numbers are Session-wide. Approval and staleness are read projections, never stored
status updates. Event-scoped template and per-Session revision reads use bounded keyset
pages and batch child queries in a repeatable-read transaction. Runtime composition
requires migration `0014`; no new configuration variable or dependency is introduced.

`0014_assembly_metadata_overrides` adds only `assembly_metadata_override` and
`assembly_metadata_override_snapshot`. Both reuse the existing Assembly immutability
trigger function to reject updates/deletes. The override row also owns its unique
operation ID and canonical human-command digest receipt, in a separate override command
namespace; the existing `assembly_command` kind constraint remains unchanged. Exact
replay returns the original entry, including its original injected-clock timestamp.
Transaction-scoped operation locks serialize replay and Session row locks serialize
override sequence checks against proposals and approval. These locks never write Kernel
state. Commands require an existing Assembly revision, reject stale Session-wide expected
sequences, and append human-only `set`/`clear` facts with actor and reason.

Program-sourced values still use `assembly_metadata_snapshot` without alteration.
Override-sourced snapshots reference immutable override IDs in the new snapshot table;
revision hydration combines both sources. Current resolution uses the latest sequence
per field, with `clear` falling back to Program Expectation. Metadata staleness is derived
at read and approval time only from which operator override governs each field; Program
Expectation refreshes never make a revision stale (ED-0077 design decision 7). Reversing
`0014` loses override history, and revisions proposed with an override are then rebuilt
without that override-sourced field.
Override history reads are Event-scoped, bounded to 1–100 entries, sequence-paginated,
and use repeatable-read transactions with total counts and explicit continuation.
There is no backfill, upstream write, participant model, or automatic authority.

`0015_render_durable_operation` adds pinned `render_operation_input` and immutable
`rendered_output` rows with Assembly, operation, attempt, opaque content, and FFmpeg
identity, plus a required opaque sidecar-manifest key and SHA-256 for the frozen metadata
snapshot. Render operations cannot set transcript-evidence terminal identity or revision.
It makes the `0007` operation-kind, transcription-source, capability-format,
and succeeded-result constraints kind-aware while retaining every existing foreign key.
Transcription still requires its four source columns and nonempty capability formats;
render can leave them null and uses `terminal_result_rendered_output_id` instead of the
transcript result reference. Both kinds share claims, leases, attempts, and fencing.
The render command, separate local worker, adapters and authenticated API now build on
these tables. New requests validate approved, non-stale Assembly state in the enqueue
transaction. Rendered Output and the operation's terminal output reference commit together
under the shared attempt fence; a failed attempt registers no partial output.
The work key remains revision plus profile ID and version. Exact replay returns the
existing operation with its current state, including terminal failure or cancellation;
conflicting command intent fails typed. Re-rendering the same revision/profile after
terminal failure is out of scope; a new approved revision is the supported path.
Transcription-facing operation listings and status projections filter by repository
input types before counts and limits; explicitly multi-kind repositories retain both kinds.
Render listings use a render-typed repository and Event/Session scope. Worker presence in
the Demo controller excludes workers whose capability rows are all render before its limit;
registered workers with no capability rows retain their previous classification.
Reversal runs before `0014` (and before direct `0007` reversal), restores the original
checks and nullability, and refuses while any render operations, inputs, outputs, or
capabilities exist. It deletes no render history and requires no backfill on reapply.

`0016_assembly_media_order` adds only nullable `order_source` (text) and `order_key_at`
(`timestamptz`) to `assembly_member`, plus three checks: the closed source values
`media_timing`/`registration_time`, both fields NULL or both set, and a media-timing key
matching a non-null `media_started_at`. It changes no `0013` column or constraint and
performs no backfill or UPDATE. Existing immutability triggers stay active. Proposals
freeze the source and key with each position. Membership input and hydration read
`registered_at` from the existing registry; no third Assembly column duplicates it.

Legacy NULL pairs hydrate as `media_timing` with `order_key_at = media_started_at`,
preserving stored positions and validation. An untimed legacy invalid revision keeps
its null key and remains unapprovable and unrenderable. New revisions always have an
aware key, including registration-time fallback for untimed media. Migration `0016`
applies after `0015` and reverses before it. Its reverse locks `assembly_member` and
refuses with `assembly_media_order_reverse_requires_no_registration_time_members`
while any `registration_time` row exists; `media_timing` rows do not block reversal.
Allowed reversal drops only the two columns, three checks and ledger entry; timed
rows hydrate identically after reapply, which performs no backfill.

Registration is at least once and idempotent. It does not claim exactly-once delivery.
Only a newly created ingress record is eligible for the included dispatcher path; an
exact replay does not repeat that caller-visible dispatch path. The asset-registration
bridge is stable and replay-safe, but it is a direct synchronous boundary rather than an
outbox. A broker and general automatic enqueue remain outside this persistence slice.

## Identity and time

A source identity is `(namespace, identifier)`. A trustworthy non-empty source event key
is preferred. Where none exists, `stageflow-ingress-v1` hashes canonical JSON containing
the source identity, Event type/source, UTC-normalized aware occurrence time, payload,
and explicitly named authoritative source facts. Supplementary metadata and receipt time
are not fingerprint inputs.

Naive timestamps fail before hashing or storage. PostgreSQL uses `timestamptz` for
occurrence and receipt facts. Occurrence, first receipt, last receipt, and migration
application time remain separate fields.

## Migration and reversal

`0001_ingress_forward.sql` creates the shared schema, migration ledger, and ingress
table. `0002_event_mode_kernel_forward.sql`, `0003_kernel_projections_forward.sql`,
`0004_kernel_review_corrections_forward.sql`, and
`0005_kernel_follow_up_closure_forward.sql` and
`0006_media_timing_evidence_forward.sql` add bounded Production-owned objects.
`0007_transcription_worker_forward.sql` adds the bounded first Work Execution and
Transcript Evidence objects. `0008` adds the Demo declaration base, `0009` adds Program
Expectation reconciliation, `0010` adds Editorial location history, and `0011` adds
Editorial review and Clip history. `0012` adds Packaging Asset identity, revision,
approval, and command-receipt tables. `0014` adds Assembly metadata overrides and their
snapshot references and reverses before `0013`. Its reverse drops only its two tables
(including their triggers/indexes) and ledger entry; override history and override
snapshot references are lost, while all existing Program-sourced snapshots and upstream
history remain. Reapply creates empty override tables, without backfill.
`0013` adds Session Assembly and reverses before
`0012`, preserving upstream identities and history. Reversal drops `0012` and its own receipts before
`0011`, without modifying earlier tables or lineage. Reversal removes `0011` before `0010`,
then removes
`0010` before its `0008` dependency, followed by `0009`, `0008`, `0007`, `0006`,
`0005`, `0004`, `0003`, then `0002` and their ledger rows while preserving ingress and the shared
schema. The `0005` reverse removes only membership tagged as its legacy reconstruction
before dropping its additive columns.
Reversal is an explicit operator action for an isolated database and is never automatic.

## Windows reference-node validation

The initial Windows Razer validation used an isolated PostgreSQL 17.10 cluster bound to
`127.0.0.1`, applied the then-current migrations, exercised Event/Stage replay, Session
reconstruction,
candidate/asset/ingress/association reconstruction, stopped and restarted PostgreSQL,
and reversed/reapplied `0002` while confirming `0001` ingress remained. The gated test
uses `STAGEFLOW_TEST_POSTGRES_DSN` so the same checks can run against another isolated
database.

A fresh 2026-08-09 Razer qualification also exercised `0003` reversal/reapply, a
custom-format backup and clean restore, a fresh application graph against the restore,
PostgreSQL stop/return, process-kill recovery, and a 197.626-second bounded workload. The
later Green closure applied and exercised migrations through `0005` on a new empty
loopback PostgreSQL 17.10 database.

Before operational deployment, StageFlow still needs environment-specific service
account/secret setup, conference-duration endurance, real recorder/livestream
coexistence, event-specific power policy, and independent event-readiness review. None
is inferred by the repository adapter or short developer qualification.
