# ADR-0020: Canonical media candidate-to-Event path

## Status

Accepted

## Date

2026-07-22

## Context

StageFlow implements separate contracts for Media Asset Candidate discovery, objective
resource observations, readiness evaluation, and Completed Media Asset validation. It
does not yet compose or persist those stages. Collapsing them into a watcher would make a
visible or growing file appear completed and would obscure recovery ownership.

The architecture-baseline disposition accepts ABR-008, protects the current separation,
and fully approves D-05.

## Decision

The canonical flow is:

1. discover Media Asset Candidate;
2. persist candidate identity and provenance;
3. record objective Media Resource Observations;
4. evaluate readiness explicitly;
5. assemble and register immutable Completed Media Asset;
6. emit a stable asset-registration Production Event;
7. associate the registered asset with authoritative Session identity or an explicit
   review outcome;
8. schedule downstream work through durable operations.

Incomplete or merely discovered files never become completed-segment Events. Each
boundary remains independently testable and is not combined into one stateful
watcher-manager.

## Alternatives

- **Emit a completed Event at discovery:** rejected because discovery does not establish
  readiness or completion.
- **Treat a directory/file path as Session identity:** rejected because Session authority
  is separate and paths can change.
- **One watcher owns discovery through processing:** rejected because it obscures
  transaction, retry, recovery, and semantic boundaries.
- **Store media content in the relational database:** rejected as the default; durable
  media records reference external content.
- **Require transcription/editorial/package work in the first slice:** rejected; those
  are separate future operations.

## Consequences

- A durable media registry and transaction boundaries are required before continuous
  ingest.
- Resource observations remain objective facts and readiness retains one policy
  authority.
- Completed Media Asset registration becomes the stable media availability ingress
  point.
- Session association requires explicit authority and may use a review queue until
  Session reconciliation is resolved.
- Restart reconciliation re-enters the same stages rather than reconstructing truth from
  filenames alone.

## Validation

Each implementation slice must prove:

- active, growing, empty, unsupported, or conflicting resources do not register as
  completed;
- repeated discovery and restart preserve one durable candidate/asset identity;
- readiness evidence and finalization times remain explicit and aware;
- registration commits before stable Event publication;
- Session association is explicit and does not derive from directory naming;
- local registration remains operable without Internet connectivity.

## Related documents

- [Segment lifecycle](../architecture/segment-lifecycle.md)
- [Session lifecycle](../architecture/session-lifecycle.md)
- [Architecture baseline disposition](../reviews/architecture-baseline-disposition.md),
  ABR-008 and D-05
- ADR-0003 and ADR-0011 in [Architecture Decisions](../../ARCHITECTURE_DECISIONS.md)
