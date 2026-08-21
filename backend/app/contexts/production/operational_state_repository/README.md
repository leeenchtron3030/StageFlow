# Operational State Repository

ED-0046 defines the backend-only, infrastructure-neutral persistence boundary for
StageFlow's accepted Operational State. ED-0047 proves that contract with exactly one
`InMemoryOperationalStateRepository`. It stores answers that policy and Operational
State Acceptance have already justified. It never decides or executes a transition.

The implementation is a **development and contract-validation repository** within one
process. It is not production persistence: all state disappears with the repository
instance or process. There is no database, SQL, filesystem persistence, Redis, network
service, retry, queue, worker, API, event publication, or frontend behavior.

## In-memory proof implementation

`InMemoryOperationalStateRepository` owns one immutable internal-state snapshot and one
private `RLock`. Each commit captures the current snapshot, validates the request in a
fixed order, builds all replacement records and indexes locally, and performs one
copy-and-swap state assignment. Queries briefly use the same synchronization boundary,
so they observe either the complete prior state or the complete committed state.

Rejected commits, stale commits, conflicts, and duplicate replays never replace the
internal snapshot. Initial and successor commits remain separate. A successful
successor commit replaces the persisted predecessor record with a new immutable
`superseded` record, stores one current successor, appends history, records Evaluation
and acceptance identities, and increments the subject-kind revision together.

Exact Evaluation or acceptance replay returns `already_committed` and references the
original commit. Reusing either identity with different successor or lineage returns
`lineage_conflict`; it is not treated as a harmless duplicate. A supplied expected
revision is optional, per subject-kind, and must match when present.

Commit outcome precedence is deterministic. Validation proceeds through request and
accepted-result shape; successor status, kind, family, subject, and value; lineage,
basis, and Evidence-context consistency; Evaluation replay; acceptance replay; state-ID
reuse; initial-versus-successor and supersession shape; actual current state; and the
optional revision before any new record, commit ID, or replacement snapshot is
published. Metadata and mapping iteration order do not select an outcome.

Repository instances are isolated. The implementation has no module-level mutable
indexes or singleton state and provides synchronization only within one instance and
process. It is not an asset queue or Runtime coordinator. Agent, Node, and future
deployment provenance may remain upstream metadata, but deployment profile is never a
repository key, lifecycle selector, or source of priority.

## Boundary and supported state

`OperationalStateRepository` accepts exactly one
`OperationalStateRepositoryCommitRequest`, which contains exactly one existing
`OperationalStateAcceptanceResult`. The repository must reject a non-accepted or
internally inconsistent result with a typed no-change outcome. It must not invoke the
acceptance component, a transition policy, or Evidence interpretation, and it must not
repair or reconstruct a missing successor.

ED-0046 supports only `recording_state` and `session_state`. The authoritative current
key is one `OperationalStateSubject` plus one `OperationalStateKind`; context,
Evaluation identity, and acceptance identity never become part of that key. At most one
current record may exist for a key. Detecting multiple current records is an explicit
integrity conflict, never an invitation to select an arbitrary winner.

## Queries

The interface provides:

- `get_current_state(subject, state_kind)`
- `get_state(state_id)`
- `list_state_history(subject, state_kind)`
- `has_committed_evaluation(evaluation_id)`
- `get_commit_by_evaluation(evaluation_id)`
- `commit_acceptance(request)`

Repository lookups return immutable typed results that distinguish `found`, `not_found`,
`invalid_query`, `current_state_conflict`, and `unknown`. Routine absence is not an
exception and unexpected infrastructure failure is not disguised as absence. State-ID
lookup includes current and superseded records; the Evaluation-commit check returns a
typed boolean value or typed failure.

## Atomic commit

One successful initial commit atomically records a new Evaluation ID and acceptance ID,
stores the accepted successor, starts ordered history, and establishes the current
pointer only when the subject-kind key has no current state. An existing current state
produces `current_state_conflict` and no change.

One successful successor commit atomically verifies the expected predecessor, records
new Evaluation and acceptance identities, persists the predecessor as `superseded`,
stores the successor as the sole `current` record, appends both lineage and history, and
moves the current pointer. No partial-success result shape exists and no subset may be
visible as committed.

The acceptance result's expected predecessor and supersession description must agree
with each other and with the request. If the valid expectation no longer matches stored
current state, the outcome is `stale_predecessor`; a stale commit never overwrites newer
state. Optional monotonic repository revisions may strengthen concurrency checks but do
not replace mandatory state-ID comparison.

## Idempotency and lineage

Within one repository, one Transition Evaluation ID and one acceptance ID may each be
committed at most once. Duplicate submission returns `already_committed`, makes no
storage change, and may identify the original commit. This repository-scoped guarantee
is authoritative and separate from ED-0044's caller-supplied known-history check.

`OperationalStateRepositoryRecord` wraps the accepted immutable state and separately
records its authoritative persisted status. Superseding a predecessor changes the
persisted record view; it never mutates the caller's `OperationalState`, whose proposal
status remains `current`. A current record cannot reference a successor. A superseded
record must reference the successor that replaced it.

Each record retains acceptance ID, Evaluation ID, acceptance rule ID, acceptance time,
the complete ED-0044 ID-only lineage, state basis, and first-class Evidence context. That
lineage
includes policy and transition-rule IDs; EvidenceSet, EvidenceItem, Observation,
Production Event, interpreter, and interpretation-rule references; Evidence Signals;
subject; context; timestamps; and predecessor/successor references. No raw Event,
Observation, Evidence, policy, evaluation, Session, or infrastructure object is stored.

## History and time

History is isolated by subject-kind key, append-only from the caller's perspective, and
ordered oldest committed state to newest. Prior values, Evaluation lineage, acceptance
lineage, and supersession links cannot be rewritten or silently removed.

Repository persisted and commit timestamps must be timezone-aware. Event, Observation,
Evidence, organizational anchor, Evaluation, state-derived, acceptance, and repository
commit times remain distinct. Commit time says only when accepted understanding was
atomically stored; it is not a media boundary and does not verify a Session boundary.
The accepted successor retains its Transition Evaluation time as
`observed_or_derived_at`; the acceptance result's `accepted_at` is stored separately as
the record's `accepted_at`; and the ED-0046 request's explicit `commit_at` becomes both
the record's `persisted_at` and the successful result's `committed_at`. The repository
does not read a clock. An exact replay returns the original result's `committed_at`, not
the replay request's proposed `commit_at`.

## Current status relative to the Durable Event-Mode Kernel

This module remains exactly what ED-0046/ED-0047 defined it as: a contract-validation
proof, not production persistence (see above). The later Durable Event-Mode Kernel
(ADR-0022/ADR-0024) established a separate PostgreSQL-backed persistence path for actual
Session/Recording authority; it did not build on or replace this module. Nothing outside
this package's own test suite imports `operational_state_repository` — it is superseded
foundation-era scaffolding, not a live gap awaiting a Postgres implementation. A prior
due-diligence review flagged its in-memory-only state as a finding; that reading did not
account for this module's own explicit "not production persistence" scope above. No
Postgres backing is planned for this module.

## Mission boundary

A committed `paused` Recording state does not pause a recorder. A committed `ending`
Session state does not end a Session. Commit does not create Session aggregates,
scheduled-activity bindings, clips, packages, notifications, or any other Operational
Product. The repository stores StageFlow's accepted understanding of recorded reality;
it does not control physical reality or broaden StageFlow into general production
monitoring.
