# ADR-0021: Domain and infrastructure time authority

## Status

Accepted

## Date

2026-07-22

## Context

Newer Runtime, readiness, asset, acceptance, and repository contracts require explicit
timezone-aware timestamps and preserve distinct semantic times. Older Event,
Observation, Evidence, and transition contracts accept naive values or create wall-clock
time implicitly. That inconsistency threatens deterministic ordering and replay across
hosts.

The architecture-baseline disposition accepts ABR-005 and fully approves D-07.

## Decision

- Externally supplied and persisted domain timestamps are timezone-aware.
- Ambiguous naive timestamps are rejected unless an explicit source-specific
  normalization policy provides the missing authority. UTC is never silently attached.
- Domain/request times are supplied explicitly.
- Infrastructure receipt, evaluation, attempt, acceptance, and commit times are created
  through an injected clock at the owning infrastructure boundary.
- Original source time, normalized source time, receipt time, evaluation time, acceptance
  time, attempt time, commit time, and organizational anchors remain separate wherever
  their meanings differ.
- UTC is the canonical normalized storage representation, not a substitute for unknown
  source timezone information.

## Alternatives

- **Permit mixed naive and aware values:** rejected because comparison and replay become
  host/locale dependent.
- **Silently label naive input as UTC:** rejected because it invents source information.
- **Call the wall clock inside domain values/policies:** rejected because construction and
  replay are no longer explicit.
- **Use one timestamp for every lifecycle boundary:** rejected because evaluation,
  acceptance, persistence, and organizational time have different meanings.

## Consequences

- A deliberate breaking internal transition to explicit aware timestamps is approved
  before operational runtime, durable schemas, or external consumers depend on legacy
  optional/defaulted Python timestamp behavior. No prolonged compatibility wrapper is
  required solely to preserve ambiguity.
- Source adapters may need explicit normalization policy and preservation of original
  representations.
- Tests use injected/fixed clocks and deliberately different semantic timestamps.
- Persisted schemas must name timestamp authority clearly rather than rely on generic
  `created_at` for unrelated meanings.

## Validation

Tests must cover naive rejection, explicit source normalization, mixed offsets, DST
boundaries, backward infrastructure clocks, serialization round trips, and preservation
of distinct evaluation/acceptance/commit/anchor values. Replay with a different current
clock must retain original persisted times.

## Related documents

- [Architecture baseline disposition](../reviews/architecture-baseline-disposition.md),
  ABR-005 and D-07
- [Architecture principles](../architecture/principles.md)
- [Session lifecycle](../architecture/session-lifecycle.md)
- [Segment lifecycle](../architecture/segment-lifecycle.md)
