# Persistence boundary

## Accepted authority

PostgreSQL is StageFlow's authoritative durable operational store under ADR-0022. It is
deployable on the local event network, must not require Internet connectivity for the
event-critical path, and may be shared by future StageFlow nodes. Media content remains
outside PostgreSQL and is referenced by durable records. PostgreSQL unavailability must
never redirect authoritative writes into process memory.

## Current implementation

The current branch implements only the first durable boundary:

- repository-neutral stable ingress contracts under `production.ingress`;
- a synchronous Psycopg 3 PostgreSQL adapter under `infrastructure.postgres`;
- one explicit `stageflow.production_event_ingress` table with database uniqueness for
  stable source identity plus source key or versioned canonical fingerprint;
- stable ingress and Production Event IDs, exact replay/conflict outcomes, first/last
  receipt evidence, and a delivery count;
- explicit numbered forward and reversal SQL plus a narrow migration runner; and
- a process-local repository that is labeled and used only as a non-durable test double.

Registration is at least once and idempotent. It does not claim exactly-once delivery.
Only a newly created ingress record is eligible for the included dispatcher path; an
exact replay does not repeat that caller-visible dispatch path. Downstream durable
effects, an outbox, operations, Sessions, media registration, retries, reconciliation,
and runtime composition remain outside this implementation.

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

`0001_ingress_forward.sql` creates the `stageflow` schema, a migration ledger, and the
ingress table. `0001_ingress_reverse.sql` removes only the ingress table and its ledger
entry; it deliberately does not drop the shared schema. Reversal is an explicit operator
action for an isolated development database and is never automatic.

## Windows reference-node validation

Psycopg's binary distribution installed and the Python contract/static suite ran on the
Windows Razer development node. This machine had no `psql`, PostgreSQL server, Docker,
or Podman available, so a real database run was not practical in this change. The real
integration test is gated by `STAGEFLOW_TEST_POSTGRES_DSN` and exercises migration,
adapter reconstruction, concurrent replay, stable Event identity, and conflict behavior
when an isolated PostgreSQL test database is supplied.

Before operational deployment, StageFlow still needs a documented PostgreSQL service
account/secret workflow, connection configuration, backup/restore procedure, health and
operator visibility, and reference-node recovery exercise. None is inferred by the
presence of the repository adapter.
