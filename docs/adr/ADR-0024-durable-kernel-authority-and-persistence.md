# ADR-0024: Durable Kernel bootstrap, Session realization, association, and persistence

## Status

Accepted

## Date

2026-08-08

## Context

ADR-0023 fixes Session semantics but deliberately left four implementation-blocking
authority decisions open for the Durable Event-Mode Kernel: Business Event/Stage
bootstrap, realized Session creation, deterministic media association, and relational
state/history ownership. The Kernel cannot implement identity, transactions, recovery,
or operator commands until those boundaries are explicit.

## Decision

### Explicit idempotent Business Event and Stage bootstrap

An explicit operator bootstrap operation consumes validated deployment definitions.
Parsing configuration never mutates business state. The operation resolves stable
operator/deployment keys to StageFlow-owned immutable Business Event and Stage IDs and
makes PostgreSQL authoritative once committed.

Equivalent replay resolves the same records. Immutable key, Business Event ownership,
or Stage ownership conflicts fail visibly. Mutable descriptive fields can change only
through explicit bootstrap reconciliation and retain an update revision; external
program/provider IDs remain references rather than StageFlow identity.

### Human-authorized Session realization

Kernel v1 realizes a Session only through one authorized human/operator application
operation. Create/start atomically allocates a StageFlow Session ID, fixes Business Event
and Stage ownership, optionally references a Program Expectation, and records the
human-declared authoritative start boundary. Ad hoc Sessions require no Program
Expectation. Machine proposals remain separate evidence. A started Session cannot move
or span Stages.

### Conservative deterministic media association

A Completed Media Asset may be automatically associated only when its structural
source/Stage identity matches, available temporal/context evidence is compatible, no
material contradiction exists, and exactly one eligible Session is safe. Eligibility
includes an active Session and may include a recently ended Session whose package is
assembling when the asset facts remain compatible. If another Session has begun and a
delayed asset is ambiguous, the outcome is unresolved. Structural or authoritative
contradiction produces conflict.

No timestamp is invented. Ambiguity reduces automation, not preservation. Unresolved or
conflicting assets remain registered. Human association/correction is authoritative,
append-oriented, and attributable. No AI or opaque confidence score participates in
Kernel v1 authority.

### Normalized current state and typed append-only history

PostgreSQL uses normalized current/aggregate tables for ordinary operational queries and
typed append-only tables for consequential boundary, association, package, completion,
and reconciliation history needed by Kernel v1. This is not event sourcing and there is
no generic catch-all event table.

An authoritative transition updates current state and writes its typed history
atomically. Relational constraints own immutable identity, structural ownership,
revision concurrency, and one active Session per Stage. Current projections remain
directly queryable and history remains provenance rather than a substitute projection.
Migrations follow the existing explicit numbered forward/reversal discipline.

## Alternatives

- Configuration-time implicit bootstrap was rejected because parsing must not silently
  create authority and future nodes may share PostgreSQL.
- Schedule-created Sessions were rejected because planned reality cannot create observed
  truth.
- Strictly-active-only automatic association was rejected because compatible trailing
  media may complete after presentation end.
- Human-only association was not selected for unambiguous deterministic cases because it
  creates avoidable event-time work without improving authority.
- Confidence-threshold/AI association was rejected for Kernel v1.
- Full event sourcing, generic history, and JSON-document aggregate storage were rejected
  as unnecessary complexity and weaker relational authority for this slice.

## Consequences

- Configuration needs stable bootstrap keys distinct from internal IDs and external IDs.
- Application commands, not startup parsing, own bootstrap and Session realization.
- Association needs explicit structural, temporal, contradictory, and human evidence
  categories plus `associated`, `unresolved`, and `conflict` outcomes.
- Current tables and typed history must share transactions and reconstruction tests.
- Later automated Session realization must invoke the same authoritative boundary.
- Generic workers, leases, outbox, broker, and AI remain outside the Kernel.

## Validation

- Equivalent and concurrent bootstrap returns one Event/Stage identity; material
  conflicts do not mutate the existing records.
- Human create/start supports expected and ad hoc Sessions, records the authoritative
  start, and enforces one fixed Stage and one active Session per Stage.
- Active and compatible trailing assets can associate; ambiguous delayed media is
  unresolved; structural contradiction is conflict; human correction wins.
- Current state and typed history commit or roll back together and reconstruct after a
  new process/repository instance.
- Real PostgreSQL migration, replay, concurrency, restart, and unavailability tests pass.

## Related documents

- [ADR-0023](ADR-0023-session-authority-and-completion.md)
- [ADR-0022](ADR-0022-postgresql-authoritative-operational-store.md)
- [Durable Event-Mode Kernel architecture](../architecture/durable-event-mode-kernel.md)
- [Durable Event-Mode Kernel plan](../plans/durable-event-mode-kernel.md)
