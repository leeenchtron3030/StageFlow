# ADR-0019: Stable ingress identity and interpreter boundary

## Status

Accepted

## Date

2026-07-22

## Context

Equivalent legacy source facts currently receive fresh Production Event and Observation
IDs when converted or interpreted again. Process-local replay records cannot protect a
future at-least-once ingress path across restart. Separately, the existing dispatcher
protocol and concrete Observation Interpreter protocol differ in method names, contexts,
and result types.

The architecture-baseline disposition accepts ABR-003 and ABR-004 and fully approves D-04.

## Decision

StageFlow will create a durable ingress record keyed by:

1. stable source identity; and
2. trustworthy source event identity when available, otherwise a versioned canonical
   fingerprint of authoritative source facts.

Source identity, ingress identity, Production Event identity, and downstream Semantic
Observation identity remain distinct. Mutable metadata does not participate in identity.

Supported ingress routes through one small dispatcher-facing interpreter protocol. A
narrow adapter may reconcile current contract generations. Batch interpretation is
preserved only when an implementation plan demonstrates semantic value.

This decision precedes continuous filesystem, recorder, or provider-event composition.

## Alternatives

- **Fresh IDs on every invocation:** rejected because repeat delivery becomes unrelated
  durable lineage.
- **Process-local replay only:** rejected because it does not survive restart or
  coordinate processes.
- **Hash the entire payload/metadata:** rejected because metadata may be mutable,
  supplementary, or provider-specific.
- **Bypass the dispatcher for concrete interpreters:** rejected as a general architecture
  because it leaves two competing ingress boundaries.
- **Duplicate dispatchers per interpreter generation:** rejected as unnecessary
  architectural divergence.

## Consequences

- Ingress persistence and uniqueness precede interpretation in a durable runtime.
- Canonical fingerprints require explicit versioning and collision/error policy.
- Source-provided IDs are preferred only when their stability and scope are trustworthy.
- Existing adapters/interpreters need a bounded, compatibility-aware correction rather
  than a repository-wide rename.
- Repeated delivery can return/reuse the original ingress result and lineage.

## Validation

Before runtime composition, tests must:

- deliver equivalent source facts repeatedly and across a reconstructed store;
- prove one durable ingress identity and no duplicate downstream effect;
- distinguish source, ingress, Production Event, and Observation IDs;
- prove identity excludes mutable metadata;
- route every supported Production Event through the real dispatcher-facing protocol;
- return typed unsupported/no-match and interpreter-failure results.

## Related documents

- [Architecture baseline disposition](../reviews/architecture-baseline-disposition.md),
  ABR-003, ABR-004, and D-04
- [Architecture principles](../architecture/principles.md)
- [System context](../architecture/system-context.md)
- ADR-0011 and ADR-0015 in [Architecture Decisions](../../ARCHITECTURE_DECISIONS.md)
