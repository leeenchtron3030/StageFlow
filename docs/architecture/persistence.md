# Persistence boundary

## Accepted authority

PostgreSQL is StageFlow's authoritative durable operational store under ADR-0022. It is
deployable on the local event network, must not require Internet connectivity for the
event-critical path, and may be shared by future StageFlow nodes. Media content remains
outside PostgreSQL and is referenced by durable records. PostgreSQL unavailability must
never redirect authoritative writes into process memory.

## Current implementation

The current branch implements stable ingress plus the bounded Durable Event-Mode Kernel
persistence boundary:

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

Registration is at least once and idempotent. It does not claim exactly-once delivery.
Only a newly created ingress record is eligible for the included dispatcher path; an
exact replay does not repeat that caller-visible dispatch path. The asset-registration
bridge is stable and replay-safe, but it is a direct synchronous boundary rather than an
outbox. Generic asynchronous operations, workers, leases, retries, and brokers remain
outside this implementation.

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
table. `0002_event_mode_kernel_forward.sql`, `0003_kernel_projections_forward.sql`, and
`0004_kernel_review_corrections_forward.sql` add only Kernel-owned objects. Reversal
removes `0004`, `0003`, then `0002` and their ledger rows while preserving ingress and
the shared schema.
Reversal is an explicit operator action for an isolated database and is never automatic.

## Windows reference-node validation

The Windows Razer validation used an isolated PostgreSQL 17.10 cluster bound to
`127.0.0.1`, applied both migrations, exercised Event/Stage replay, Session reconstruction,
candidate/asset/ingress/association reconstruction, stopped and restarted PostgreSQL,
and reversed/reapplied `0002` while confirming `0001` ingress remained. The gated test
uses `STAGEFLOW_TEST_POSTGRES_DSN` so the same checks can run against another isolated
database.

A fresh 2026-08-09 Razer qualification also exercised `0003` reversal/reapply, a
custom-format backup and clean restore, a fresh application graph against the restore,
PostgreSQL stop/return, process-kill recovery, and a 197.626-second bounded workload.
Before operational deployment, StageFlow still needs environment-specific service
account/secret setup, conference-duration endurance, real recorder/livestream
coexistence, event-specific power policy, and independent event-readiness review. None
is inferred by the repository adapter or short developer qualification.
