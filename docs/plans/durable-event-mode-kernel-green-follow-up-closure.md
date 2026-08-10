# Durable Event-Mode Kernel Green follow-up closure

## Status

Approved — Green autonomous, implementation-ready

## Execution authority

- Classification: Green autonomous
- Authority evidence: the accepted Durable Event-Mode Kernel architecture and
  ADR-0022 through ADR-0024, together with DKV-001 through DKV-004 in the targeted
  correction verification.
- Implementation-ready: Yes
- Required escalation or approval, if any: None. The user explicitly requested the
  four bounded follow-ups and logically isolated commits.

## Related findings or ADRs

- Finding/disposition:
  [Durable Event-Mode Kernel correction verification](../reviews/durable-event-mode-kernel-correction-verification.md),
  DKV-001 through DKV-004.
- ADR: ADR-0022 (durable PostgreSQL authority), ADR-0023 (durable human-command
  idempotency), ADR-0024 (process-local orchestration with durable state).
- Engineering Directive or other authority: the accepted kernel architecture and the
  bounded autonomous execution policy in `AGENTS.md`.

## Problem statement

The corrected kernel has four remaining Green gaps: migration 0004 cannot recover
legacy completion membership after a Session was reopened; PostgreSQL replay of a
delayed Session command returns the current Session rather than the command's original
result; startup status loses the fact that configuration was supplied and valid when
composition fails; and current-facing documentation understates implemented kernel
capabilities.

## Verified current behavior

- Migration 0004 only backfills completion membership when the current Session is still
  complete at the recorded package revision.
- PostgreSQL boundary and completion replay resolve the historical decision but reload
  the current Session row. Session-start replay also reloads current state.
- Lifespan retains a startup error but the status route derives `configured` only from
  composed components, so valid supplied configuration can appear absent.
- `docs/PROJECT_BRIEF.md` and `docs/architecture/principles.md` retain pre-kernel
  statements about Session persistence, composition, and readiness.

## Desired behavior

- Deterministically reconstruct unambiguous legacy completion membership and explicitly
  classify ambiguous snapshots without inventing membership.
- Preserve and replay the original Session result for newly recorded consequential
  human commands, including after later mutations and from a fresh repository instance.
- Report configuration supplied/valid, runtime composed, dependency availability, and
  operational readiness as distinct facts.
- Align current-facing documentation with implemented behavior without claiming
  production or event readiness.

## In scope

- One additive, versioned PostgreSQL migration after 0004, including reversal behavior.
- PostgreSQL command-result snapshot persistence and replay for Session start, boundary
  correction, and completion.
- Additive kernel startup/status truth and focused lifecycle tests.
- Current-facing architecture/project/status documentation and closure evidence.

## Out of scope

- New product semantics, public compatibility breaks, dependencies, services, or
  deployment topology.
- Fabricating historical facts when legacy ordering is ambiguous.
- Production deployment, production-data mutation, or an event-readiness claim.

## Constraints

- Architecture and terminology constraints: preserve Session, completion, boundary,
  association, and package meanings and the modular monolith.
- Compatibility constraints: schema and API changes are additive; old command rows with
  no result snapshot retain a truthful legacy fallback.
- Offline/event-mode constraints: all changes remain local PostgreSQL/process behavior
  and require no continuous Internet connection.
- Security and data-handling constraints: snapshots contain existing domain state only;
  tests use synthetic data.

## Implementation approach

1. Add migration 0005. Classify completion membership as recorded, reconstructed, or
   unresolved; reconstruct only the latest strictly-prior association for each asset;
   treat relevant equal-time history as ambiguous; tag reconstructed rows so reversal
   removes only 0005-created membership. Add a nullable JSON command-result snapshot.
2. Serialize the original Session result into the command ledger in the same transaction
   as each successful consequential command. Prefer that snapshot on replay; retain the
   existing current-row fallback for pre-0005 ledger entries that cannot be recreated
   safely.
3. Retain explicit startup progress across configuration parsing, database verification,
   runtime composition, source reconciliation, and readiness evaluation. Expose additive
   status fields while preserving the existing response contract.
4. Add focused unit/static tests and real-PostgreSQL migration, replay, reversal, restart,
   conflict, lifecycle failure, and recovery tests. Update current-facing documentation
   and record actual validation in the completion record.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `backend/app/infrastructure/postgres/migrations/0005_*` | Add forward/reverse migration |
| PostgreSQL migration runner/repository | Apply/verify 0005 and preserve replay results |
| kernel bootstrap/lifecycle/status API | Preserve and expose startup truth |
| backend tests | Add migration, replay, reversal, and lifecycle coverage |
| current architecture/project/review/plan docs | Align status and record closure evidence |

## Data or migration considerations

Migration 0005 is additive. It adds completion-snapshot classification/provenance and a
nullable command-result snapshot. Reconstructed membership preserves existing completion,
Session, asset, and association identities. Equal-time ambiguity is recorded as
unresolved and produces no invented membership. Reverse migration deletes only rows
tagged as 0005 reconstructions, removes the additive columns/constraints, and removes
the 0005 ledger record, leaving migrations 0001 through 0004 intact.

## Failure and recovery considerations

Migration application remains ledger-guarded and transactional. Command snapshots are
written in the command transaction, so a committed command cannot expose a partially
written new-format replay result. Reapplying an operation returns its stored result;
parameter mismatch remains a conflict. Startup progress is process-local diagnostic
state and is rebuilt on every process start.

## Observability requirements

Operators must be able to distinguish no configuration, invalid configuration, valid
configuration with unavailable PostgreSQL, composed runtime with unavailable sources,
and fully ready runtime. Migration classification must distinguish trustworthy,
reconstructed, and unresolved membership without exposing secrets.

## Test strategy

- Static migration ordering, forward/reverse, and schema-verification tests.
- Real PostgreSQL tests for representative legacy reopened and equal-time ambiguous
  completions, reversal/reapply, and migration ledger state.
- Immediate/delayed/fresh-repository replay and mismatched-parameter conflict tests.
- Lifecycle/status tests for absent, invalid, database-failed, source-failed, successful,
  and recovered startup.
- Full backend pytest, Ruff, and Pyright; frontend build, lint, and typecheck; repository
  whitespace check; and fresh real-PostgreSQL full backend execution.

## Acceptance criteria

- [ ] Unambiguous legacy reopened completion membership is reconstructed with provenance.
- [ ] Ambiguous legacy membership is explicitly unresolved and not fabricated.
- [ ] Reverse and reapply behavior is tested and migration ledger state is correct.
- [ ] Delayed replay returns the original Session result from a fresh repository instance.
- [ ] Idempotency conflicts remain fail-closed.
- [ ] Startup status preserves configuration and composition truth across all failure modes.
- [ ] Current-facing documentation reflects implemented behavior without readiness inflation.
- [ ] Required validation passes and closure evidence records only commands actually run.

## Rollback or reversal

Revert runtime code and run the 0005 reverse migration before returning to a 0004 binary.
The reverse migration deliberately removes 0005-reconstructed membership and snapshots;
all pre-existing identities and 0001-0004 data remain. No irreversible step is planned.

## Open questions

- None. Historical rows without a trustworthy result snapshot cannot be recreated; the
  accepted bounded behavior is an explicit legacy fallback rather than fabrication.

## Completion record

- Implemented revision: Pending
- Files and migrations actually changed: Pending
- Commands and tests actually run: Pending
- Results and warnings: Pending
- Execution authority used: Green autonomous plus explicit user request
- Approved deviations: None
- Rollback status: Not exercised yet
- Remaining work: Implementation, validation, independent verification, and closure record
