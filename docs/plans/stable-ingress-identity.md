# Stable ingress identity

## Status

In progress - implementation complete; real PostgreSQL execution pending

## Execution authority

- Classification: Explicit approval granted; remaining implementation is Green within
  the approved decision.
- Authority evidence: ADR-0019, ADR-0022, accepted ABR-003, approved D-02/D-04, and the
  user-approved PostgreSQL durable-store decision dated 2026-08-07.
- Implementation-ready: Yes.
- Required escalation or approval, if any: None while this plan remains limited to the
  ingress repository boundary and does not compose the application runtime.

## Problem and verified current behavior

All seven source-event conversion paths allocate fresh Production Event IDs and all six
concrete Observation Interpreters allocate fresh Observation IDs. No durable ingress
record, uniqueness boundary, persistence adapter, or reconstructed-store test exists.

ADR-0019 requires one durable ingress record keyed by stable source identity plus a
trustworthy source event key or versioned canonical fingerprint. PostgreSQL is now
approved as the authoritative operational store and the strict aware-time transition is
approved before timestamp values participate in canonical identity.

## Intended outcome

Add the smallest synchronous durable-ingress foundation that:

- represents stable source identity separately from ingress and Production Event IDs;
- supports either a trustworthy source event key or a versioned SHA-256 fingerprint of
  explicitly supplied authoritative facts;
- excludes supplementary metadata from identity by contract;
- transactionally inserts or resolves one PostgreSQL ingress record;
- returns exact replay for the same key/facts and a typed conflict for the same key with
  different facts;
- allocates one Production Event ID on first registration and reuses it on replay;
- records first/last receipt time and delivery count without changing source occurrence
  time or the stable Production Event;
- exposes one repository-neutral registrar and one PostgreSQL adapter; and
- proves one real dispatcher-facing path without creating an application composition
  root.

## Dependency and migration choice

Use Psycopg 3 (`psycopg[binary]`) as the only new application dependency.

- **Psycopg 3:** selected. It is the maintained PostgreSQL-native driver, supports direct
  synchronous transactions, typed parameter binding, PostgreSQL JSON/UUID/timestamptz,
  and a Windows binary distribution. It keeps SQL and transaction ownership explicit.
  Installed version 3.3.4 declares `LGPL-3.0-only`; the dependency is isolated to the
  infrastructure adapter and its binary package supports offline runtime after install.
- **SQLAlchemy:** not selected. Its ORM/general database abstraction is unnecessary for
  one PostgreSQL-specific repository and would broaden the persistence framework.
- **asyncpg:** not selected. The current boundary is deliberately synchronous; adopting
  an async-only driver would change execution semantics without need.

Do not add Alembic for this first isolated schema. Use explicit numbered forward and
reversal SQL files plus a narrow Psycopg migration runner and migration ledger. Revisit a
general migration tool only when the durable schema grows enough to justify it.

## Data model and transaction behavior

Create a `stageflow` schema containing:

- `schema_migration(version, applied_at)`;
- `production_event_ingress` with UUID ingress/Event IDs, source namespace/identifier, identity
  route/value, optional source key/fingerprint version, canonical facts JSON, source
  facts digest, Event type/source/payload/correlation, aware occurrence/first receipt/last
  receipt times, and delivery count.

Enforce uniqueness on `(source_namespace, source_identifier, identity_kind,
identity_value)` and on Production Event ID. Check constraints require exactly the
declared identity route.

Registration uses one transaction:

1. validate/canonicalize the request before I/O;
2. attempt the insert with newly allocated ingress and Event IDs;
3. on uniqueness conflict, lock and load the existing row;
4. compare canonical facts and immutable Event facts exactly;
5. return `REPLAYED` and update only last receipt/delivery count when equal;
6. return `CONFLICT` without mutation when unequal; and
7. roll back and return/raise a typed storage failure without a process-local fallback.

This is at-least-once registration with idempotent durable resolution, not exactly-once
delivery or downstream-effect execution.

## Scope

- New ingress value contracts, canonicalizer, typed outcomes, repository protocol, and
  synchronous registrar.
- PostgreSQL schema/migration and adapter.
- A process-local repository implementation only for repository-neutral unit tests and
  explicit non-durable use; it must never claim restart safety.
- Focused canonicalization, replay, conflict, concurrency-contract, timestamp, migration,
  PostgreSQL integration (when configured), and dispatcher-path tests.
- ADR/architecture/plan documentation directly affected by the approved decision.

## Non-goals

- Application startup/composition, connection-pool ownership, continuous source
  watchers, Session/media association, workers, retries, broker/outbox, downstream
  effect persistence, provider adapters, or public APIs.
- Converting every legacy source adapter into a running ingress route in this slice.
- Exactly-once claims or using process memory as an authoritative fallback.

## Validation

- Focused ingress contract/repository/dispatcher tests.
- Migration forward/reversal structural tests.
- Real PostgreSQL reconstructed-adapter, replay, conflict, and concurrent registration
  tests when `STAGEFLOW_TEST_POSTGRES_DSN` is configured.
- Full backend pytest, Ruff, and Pyright.
- `git diff --check` and fresh independent verification.

## Acceptance criteria

- [x] Source-key and versioned-fingerprint routes are explicit and exclude mutable
  metadata.
- [ ] One PostgreSQL ingress identity and Production Event identity survive adapter/store
  reconstruction.
- [x] Same key/same facts reuses exact lineage; same key/conflicting facts fails closed.
- [ ] Concurrent delivery has one transactional winner and no duplicate ingress record.
- [x] Source, ingress, Production Event, and Observation identities remain distinct.
- [x] Naive identity timestamps fail before hashing or storage; offset-equivalent aware
  times canonicalize consistently.
- [x] Storage unavailability never falls back to authoritative process memory.
- [x] One registered Production Event traverses the real dispatcher-facing protocol.
- [x] Forward/reversal migration behavior and Windows setup limitations are documented.

## Rollback

Before runtime composition, revert the ingress contracts/adapter/dependency and apply the
documented reversal SQL only to an isolated development schema. No production data exists
under this plan. Never drop an operational schema automatically.

## Completion record

- Implemented repository-neutral ingress identity, records, typed outcomes, non-durable
  in-memory test double, and a create-only dispatcher path.
- Added synchronous Psycopg 3 registration with transactional insert/resolve, database
  uniqueness, exact replay evidence, source-key conflict detection, and fail-visible
  unavailability without a memory fallback.
- Added explicit `0001_ingress` forward/reversal SQL and migration ledger behavior.
- Unit/contract coverage passes for source keys, versioned fingerprints, offset
  canonicalization, naive rejection, replay, conflict, concurrent process-local
  registration, backward injected clocks, and no repeat dispatch on replay.
- A real PostgreSQL integration test covers migration, reconstructed adapters,
  concurrency, and stable Event identity when `STAGEFLOW_TEST_POSTGRES_DSN` is supplied.
  It was skipped on this Windows node because no PostgreSQL server, `psql`, Docker, or
  Podman was installed. The two PostgreSQL-only acceptance criteria therefore remain
  unchecked and the plan remains In progress for fresh environment-backed verification.
- No application composition, watcher, Session association, durable downstream effect,
  broker, worker, media blob storage, schema outside ingress, secret, or runtime
  configuration was added.
