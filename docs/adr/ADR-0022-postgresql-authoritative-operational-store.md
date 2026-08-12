# ADR-0022: PostgreSQL authoritative operational store

## Status

Accepted

## Date

2026-08-07

## Context

ADR-0019 requires durable ingress identity and the accepted Durable Event-Mode Kernel
direction requires one relational authoritative store. The database technology,
migration boundary, and first reference topology were previously open under disposition
D-02.

## Decision

PostgreSQL is StageFlow's authoritative durable operational store. It must be deployable
on the local event network and the event-critical workflow must not require Internet or a
cloud database. Media content remains outside PostgreSQL and is referenced by durable
records.

PostgreSQL may hold ingress and Production Event lineage, Sessions, media registry,
operations and attempts, operational lineage, human/editorial decisions, and later
package/delivery metadata as those capabilities receive separate implementation scope.

The first reference deployment may colocate PostgreSQL and StageFlow on one Windows event
node. Multiple future workers/nodes may share the authoritative database. Database
unavailability must fail or pause new authoritative state; StageFlow must not silently
continue authoritatively in process memory. Existing recording/media systems remain
independent of StageFlow database availability.

Durable ingress uses database uniqueness and transactions for at-least-once idempotent
registration. This decision does not claim exactly-once delivery and does not authorize a
broker, microservices, cloud dependence, or full runtime composition.

## Alternatives

- **Embedded single-node database:** rejected as the authoritative direction because the
  approved future topology permits multiple nodes/workers sharing one store.
- **Generic ORM-first persistence:** not required; explicit repository/data-access code
  is preferred until demonstrated schema breadth justifies a framework.
- **Cloud-managed database:** rejected as an event-critical requirement.
- **Process-local authoritative fallback:** rejected because it fragments identity and
  cannot survive restart.
- **Message broker plus separate stores:** rejected for the first kernel as unnecessary
  operational complexity.

## Consequences

- PostgreSQL operation, backup/restore, schema evolution, and local event-node setup must
  be documented before operational deployment.
- Application dependencies remain behind infrastructure adapters and outside domain
  decision code.
- Schema migrations require explicit forward/reversal behavior and tests.
- In-memory repositories remain valid only for tests and explicitly non-durable uses.
- Loss of PostgreSQL reduces StageFlow capability but must not affect source recording.

## Validation

- Reconstructed-store and concurrent uniqueness tests for durable ingress.
- PostgreSQL unavailable/fault behavior without process-memory fallback.
- Windows reference-node setup validation when PostgreSQL is installed.
- Later backup/restore and migration tests as durable schemas expand.

## Related documents

- [ADR-0019](ADR-0019-stable-ingress-and-interpreter-boundary.md)
- [ADR-0021](ADR-0021-time-authority.md)
- [Architecture baseline disposition](../reviews/architecture-baseline-disposition.md), D-02
- [Stable ingress identity plan](../plans/stable-ingress-identity.md)
