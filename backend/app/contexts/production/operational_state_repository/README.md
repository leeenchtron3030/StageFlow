# Operational State Repository

ED-0046 defines the backend-only, infrastructure-neutral persistence boundary for
StageFlow's accepted Operational State. It stores answers that policy and Operational
State Acceptance have already justified. It never decides or executes a transition.

The package contains contracts only. There is no in-memory store, database, SQL,
filesystem persistence, Redis integration, transaction implementation, lock, retry,
queue, worker, API, event publication, or frontend behavior.

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

## Mission boundary

A committed `paused` Recording state does not pause a recorder. A committed `ending`
Session state does not end a Session. Commit does not create Session aggregates,
scheduled-activity bindings, clips, packages, notifications, or any other Operational
Product. The repository stores StageFlow's accepted understanding of recorded reality;
it does not control physical reality or broaden StageFlow into general production
monitoring.
