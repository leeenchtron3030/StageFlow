# Producer Work Queue — Kernel-derived first slice

## Status

Approved

## Execution authority

- Classification: Green autonomous
- Authority evidence: [Post-Kernel capability layer architecture](../architecture/post-kernel-capability-layer.md)
  `## Producer Work Queue` section defines the Work Queue as "a bounded read model
  answering which Producer decisions or approvals are waiting," explicitly listing
  "unresolved/conflicting association" and "package review or reopening" as expected item
  types — both already fully authoritative in the existing Kernel with no new decision
  required. Explicit 2026-08-22 user directive to queue independent new-capability work
  alongside ED-0067 (Editorial Candidate Moment Phase 1), which is already in progress.
- Implementation-ready: Yes
- Required escalation or approval, if any: None. This slice deliberately excludes every
  item type that depends on unimplemented or Yellow-gated capability (Assembly approval,
  auto-approval-withheld, policy/configuration exceptions) — see Out of scope.

## Related findings or ADRs

- Finding/disposition: Post-Kernel capability layer architecture, `## Producer Work
  Queue` section; companion
  [Producer Sessions & Work Queue UX specification](../ux/producer-sessions-work-queue.md).
- ADR: None required — this is a read-only composition over existing authoritative Kernel
  state; it creates no new domain authority.
- Engineering Directive: ED-0068.

## Problem statement

The Producer currently has no single bounded answer to "which of my Sessions need a human
decision right now." Package-ready and package-correction-required Sessions, and
unresolved/conflicting media associations, are all already durable Kernel facts, but a
Producer must currently know to look in the right per-Session or per-Stage place to find
them. This slice makes that queue durable-data-derived and explicit, with zero new
persisted state.

## Verified current behavior

- `backend/app/contexts/production/event_mode_kernel/contracts.py`: `SessionPackageState`
  is `ASSEMBLING | READY_FOR_REVIEW | IN_REVIEW | COMPLETE | CORRECTION_REQUIRED`;
  `AssociationStatus` is `ASSOCIATED | UNRESOLVED | CONFLICT`.
- `EventModeKernelRepository` (repository.py) currently exposes `list_stages(event_id)`,
  `list_sessions_for_stage(stage_id)`, and `get_association(asset_id)` (single-asset
  lookup only) — there is no existing bounded query that lists associations by status, or
  Sessions by package state, across a Stage or Event. This slice adds those bounded
  queries; it does not require a new migration, since it reads existing tables.
- `backend/app/api/v1/kernel_status.py` already composes bounded per-Event projections
  from repository reads (the ED-0055/ED-0063 review confirmed this pattern); the Work
  Queue projection should follow the same composition style, not a parallel status
  endpoint.
- No `editorial` package, no Work Queue table, and no Work Queue API route currently
  exist. This slice is independent of ED-0067's in-progress `editorial` bounded context —
  it touches only Kernel repository/API files, not `backend/app/contexts/editorial/`.

## Desired behavior

A bounded, paginated Work Queue read model returns, per Event scope: Sessions whose
package is `READY_FOR_REVIEW` or `CORRECTION_REQUIRED`, and media associations whose
status is `UNRESOLVED` or `CONFLICT`. Each item carries stable identity, a decision-type
code, the subject's ID/revision, Event/Stage/Session context, and a link/reference the
Producer can act on. No new durable state is introduced; the queue is computed from
existing Kernel authority at read time.

## In scope

- New bounded repository queries on `EventModeKernelRepository` (or a read-only
  composition over existing queries, whichever is the better fit found during
  implementation): associations filtered by `status in {UNRESOLVED, CONFLICT}` for a
  Stage/Event, and Sessions filtered by `package_state in {READY_FOR_REVIEW,
  CORRECTION_REQUIRED}` for a Stage/Event.
- A `WorkQueueItem` response contract (in `response_models.py` or a new
  `work_queue_models.py`, matching existing conventions) with: stable projection identity
  (derivable from the subject's own ID — no new identity space required), a decision-type
  code (`package_ready_for_review`, `package_correction_required`,
  `association_unresolved`, `association_conflict`), subject ID and revision, Event/Stage/
  Session context IDs, and created/updated-at derived from the subject's own timestamps.
- A new bounded, paginated API route (e.g. `GET .../work-queue`) included behind the
  existing ED-0055 shared-secret dependency, with explicit Event scope, deterministic
  ordering (e.g. oldest-first within type, or by operational consequence if a simple rule
  is obvious — do not invent a scoring model), cursor pagination, and an explicit maximum
  limit with truncation signaling.
- Tests: bounded query correctness (each of the four item types appears/disappears as the
  underlying Session/association state changes), pagination/limit/truncation, Event-scope
  isolation (an item from a different Event never appears), and no item type beyond the
  four listed above is fabricated.

## Out of scope

- Assembly approval, auto-approval-withheld, and policy/configuration-exception item
  types — all depend on capability that doesn't exist yet (Assembly, ADR-0026 automation).
  Do not stub these as always-empty categories; simply do not model them until their
  underlying capability exists.
- "Session-boundary review" as its own item type — the architecture document names it but
  does not define its exact trigger condition precisely enough to implement without
  guessing at unspecified semantics. Leave it for a follow-up slice once that trigger is
  explicitly defined, rather than inventing one here.
- Any frontend Producer UI beyond whatever minimal surface is needed to prove the API
  contract — a full Work Queue UI treatment is a separate, later scoped frontend task.
- Any change to Session, association, or package authority, or to any existing Kernel
  repository method's existing behavior.
- Formal task assignment, claiming, or generic task-detail aggregates — explicitly
  deferred by the architecture document itself.

## Constraints

- Architecture and terminology constraints: a Work Queue item is a read-model projection,
  not a new authoritative aggregate; it must reference the subject's real ID/revision, not
  invent a parallel identity.
- Compatibility constraints: no existing repository method, contract, or route changes
  signature or behavior.
- Offline/Event Mode constraints: the Work Queue must be computable purely from local
  PostgreSQL state; no external dependency.
- Security/data-handling constraints: projections omit raw media paths, DSNs, and
  unbounded diagnostic detail, consistent with existing Kernel projection conventions.

## Implementation approach

1. Add the two new bounded repository queries (or compose existing `list_stages`/
   `list_sessions_for_stage` results with in-application filtering if that proves simpler
   and equally correct at current expected event scale — either is acceptable, prefer
   whichever avoids N+1 query cost at the Devcon-scale ~11-stage/room ceiling mentioned in
   prior Demo planning).
2. Add the `WorkQueueItem` contract and a pure function that maps qualifying
   Sessions/associations into typed items.
3. Add the API route, included behind the existing shared-secret dependency, with cursor
   pagination and an explicit limit.
4. Add tests per the Test strategy below.
5. Run full backend suite, Ruff, Pyright.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `backend/app/contexts/production/event_mode_kernel/repository.py` | Add bounded association-by-status and Session-by-package-state queries |
| `backend/app/api/v1/response_models.py` (or new `work_queue_models.py`) | New `WorkQueueItem` response contract |
| `backend/app/api/v1/kernel_status.py` (or a new `work_queue.py` router, whichever fits existing composition conventions better) | New bounded, paginated Work Queue endpoint |
| `backend/app/api/v1/router.py` | Include the new route behind the ED-0055 auth dependency, if added as a separate router |
| `backend/tests/` | New query, projection, pagination, and Event-scope-isolation tests |
| `docs/architecture/post-kernel-capability-layer.md` | Mark the Work Queue's Kernel-derived item types as implemented (first slice) in the UX-to-capability traceability table, if a future doc-sync pass covers it — not required for this plan's own completion |

## Data or migration considerations

None. No new table, no migration. This slice is a read-only composition over existing
`Session` and `MediaAssociation` Kernel state.

## Failure and recovery considerations

The Work Queue is fully re-derivable from current PostgreSQL state at any time — there is
no queue-specific failure mode beyond the Kernel's own existing PostgreSQL-unavailability
handling, which this slice must not weaken or bypass.

## Observability requirements

Each Work Queue item must carry enough context (decision type, subject ID/revision,
Event/Stage/Session) for an operator to understand why it appeared without needing to
cross-reference a separate system. Truncation (when more items exist than the bounded
limit returns) must be explicit, not silent.

## Test strategy

- Query/projection tests: a Session entering/leaving `READY_FOR_REVIEW`/
  `CORRECTION_REQUIRED` and an association entering/leaving `UNRESOLVED`/`CONFLICT`
  correctly appears/disappears from the queue.
- Pagination tests: cursor continuation, explicit limit, truncation signaling.
- Event-scope isolation: an item belonging to a different Event never appears in a
  scoped query.
- Negative test: no item type beyond the four in scope is ever produced.
- Full quality commands: `uv run pytest`, `uv run ruff check .`, `uv run pyright`,
  `git diff --check`.

## Acceptance criteria

- [ ] Bounded queries correctly identify Sessions in `READY_FOR_REVIEW`/
  `CORRECTION_REQUIRED` and associations in `UNRESOLVED`/`CONFLICT`, scoped to one Event.
- [ ] The Work Queue API route is paginated, ordered deterministically, bounded by an
  explicit limit, and included behind the existing ED-0055 shared-secret dependency.
- [ ] No new persisted table or migration is introduced.
- [ ] No existing Kernel repository method, contract, or route changed behavior.
- [ ] Full backend suite, Ruff, and Pyright pass; `git diff --check` passes.

## Rollback or reversal

Remove the new repository queries, contract, and route. No data or schema change to
reverse — this slice never persists anything new.

## Open questions

- Whether the association/Session queries are best served by new repository methods or by
  in-application composition of existing ones is left to implementation judgment; either
  satisfies this plan's acceptance criteria as long as query cost stays reasonable at
  current expected event scale.

## Completion record

_(To be filled in by whoever implements this plan.)_
