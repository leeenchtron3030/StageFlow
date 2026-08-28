# Editorial review foundation

## Status

Approved

## Execution authority

- Classification: Green autonomous
- Authority evidence: step 2 of the accepted delivery sequence in the
  [post-Kernel capability layer](../architecture/post-kernel-capability-layer.md)
  ("Editorial review foundation: bounded candidate query and append-only review decision
  that can create an Editorial Clip contract. No export/publishing."); the same
  document's "Review boundary" section, which already specifies the decision record's
  required fields, the four minimum actions, projection-not-mutation review state, and
  exactly what Clip creation may and may not do; ED-0067's implemented
  `editorial` bounded context and migration `0010`; ADR-0023 (Session authority) and
  ADR-0024 (durable Kernel authority/persistence).
- Implementation-ready: Yes. Every contract shape, action, and prohibition is already
  resolved in accepted architecture. No unresolved product or architecture decision is
  required.
- Required escalation or approval, if any: none for this slice. Stop and escalate if the
  work appears to require altering Session boundary authority, package completion,
  publishing/export, machine-origin candidates, or the still-unresolved packaging-asset
  identity decision — none of which are in scope here.

## Related findings or ADRs

- ADR: ADR-0023, ADR-0024. Packaging-asset identity and ADR-0026 (policy-scoped automatic
  authority) are explicitly **not** required by this slice and remain unresolved.
- Engineering Directive: ED-0072. Follows ED-0067 (Editorial Candidate Moment Phase 1).

## Problem statement

ED-0067 made human-declared Editorial Candidate Moments durable, but nothing can act on
them. `EditorialReviewState` currently contains exactly one member, `UNREVIEWED`, and
there is no way to record that a human reviewed a candidate, no Editorial Clip concept,
and no queue an Editorial reviewer could read. The declared-Moment slice therefore
produces durable records with no downstream consumer, which is the smallest gap standing
between StageFlow and a usable editorial loop.

## Verified current behavior

- `backend/app/contexts/editorial/contracts.py` defines `EditorialCandidateOrigin`,
  `EditorialCandidateSourceKind`, `EditorialReviewState` (only `UNREVIEWED`),
  `EditorialGenerationState`, `EditorialLocationConflictReason`,
  `EditorialCandidateLocation`, `DeclareEditorialMoment`, `EditorialCandidateMoment`, and
  `EditorialSessionCandidateProjection`.
- `repository.py` and `service.py` implement idempotent declaration, bounded per-Session
  reads, and append-only boundary-conflict location history over PostgreSQL migration
  `0010`.
- `backend/app/api/v1/editorial.py` exposes the authenticated `Mark Moment` command and
  bounded reads behind the ED-0055 shared-secret router dependency.
- No review decision, Clip, or reviewer-facing queue exists anywhere in the codebase.

## Desired behavior

An Editorial reviewer can read a bounded queue of candidates and record an append-only
review decision against a specific candidate revision. Approving creates an Editorial
Clip with its own durable identity and lineage. Prior decisions remain visible; the
current review state is a derived projection, never a destructive overwrite.

## In scope

- `EditorialMomentReviewDecision`: append-only record carrying candidate identity and
  **candidate revision**, actor, decision time, action, notes/reason, and an optional
  adjusted Session-timeline range.
- The four minimum actions named in the architecture: approve-and-create-clip, reject,
  revise/range-adjust, defer.
- Extending `EditorialReviewState` with the states the projection needs, derived from the
  decision history rather than stored as mutable candidate state.
- `EditorialClip`: stable identity, approved Session-timeline range, candidate and
  decision lineage, and its own revision.
- An idempotent review-decision application command reusing ED-0067's existing
  human-command idempotency mechanism, with stale-candidate-revision rejection.
- One additive PostgreSQL migration (`0011`) for the decision and Clip tables, forward and
  reverse, following migration `0010`'s established additive pattern.
- A bounded, paginated Editorial review queue read model, and authenticated API routes
  under the existing `/api/v1/editorial` router.
- Behavior-first tests at the changed boundary, including replay/idempotency, stale
  revision, restart reconstruction, and migration reverse/reapply.

## Out of scope

- Rendering, export, publishing, or delivery of any kind.
- Machine-origin candidates, model inference, or automatic review authority.
- Merge/split, assignment, richer tagging, transcript playback, and clip/export state —
  the architecture explicitly defers these behind this boundary.
- Any change to Session boundary authority, package completion/revision, or Kernel
  association policy. Clip creation must not touch any of them.
- Frontend implementation. This slice is backend contracts, persistence, and API only.
- Packaging-asset identity and ADR-0026 automation — neither is required or touched.

## Constraints

- Architecture and terminology constraints: a Clip is not a rendered output, a package, or
  a Session boundary change. Review decisions are append-only; the review state is a
  projection over them. A stale-revision command fails rather than silently moving a mark.
- Compatibility constraints: purely additive. ED-0067's declaration path, existing routes,
  Demo compatibility surface, and migration `0010` must all keep working unchanged.
- Human authority: approval is a human decision. Nothing in this slice may auto-approve,
  and no model output participates.

## Implementation approach

1. Add the review-decision and Clip contracts to `contracts.py`, following ED-0067's
   existing immutability and timezone-aware-timestamp conventions.
2. Extend `EditorialReviewState` with the derived states the projection requires.
3. Add additive migration `0011` (forward and reverse) for the decision and Clip tables.
4. Extend the repository with append-only decision writes, Clip creation, and the bounded
   queue query — avoiding N+1 reads in the queue projection, as ED-0067's batch projection
   already does.
5. Add the service-level review command with idempotency and stale-revision rejection,
   reusing the existing human-command idempotency digest mechanism.
6. Add authenticated routes to the existing `editorial` router, matching the established
   bounded-limit and explicit-truncation conventions used by ED-0068's Work Queue.
7. Add behavior-first tests at each changed boundary.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `backend/app/contexts/editorial/contracts.py` | Review decision, Clip, extended review state |
| `backend/app/contexts/editorial/repository.py` | Append-only decision writes, Clip creation, queue query |
| `backend/app/contexts/editorial/service.py` | Idempotent review command with stale-revision rejection |
| `backend/app/infrastructure/postgres/editorial_moment_repository.py` | PostgreSQL implementation |
| `backend/app/infrastructure/postgres/sql/0011_*.sql` | Additive forward/reverse migration |
| `backend/app/infrastructure/postgres/migrations.py` | Register migration `0011` |
| `backend/app/api/v1/editorial.py` | Authenticated review-decision and queue routes |
| `backend/tests/test_editorial_review_foundation.py` | Behavior-first tests (new) |

## Data or migration considerations

One additive migration `0011`, forward and reverse, creating only new tables and indexes.
It must not alter or drop anything created by migrations `0008` or `0010`. The runner must
reverse `0011` before `0010`, matching the existing ordering discipline.

## Failure and recovery considerations

- A review decision against a stale candidate revision must fail explicitly, never
  silently apply to a moved candidate.
- Exact command replay returns the original result; a conflicting replay with the same
  idempotency key raises the established conflict error.
- Decision write and Clip creation share one transaction; a failure rolls back both.
- A rejected or deferred candidate retains full decision history and can be reviewed again.

## Observability requirements

The bounded queue projection exposes counts, oldest-pending age, and current review state
per candidate without transcript content, media paths, or actor secrets.

## Test strategy

- Behavior-first tests at the changed boundary: each of the four actions; append-only
  history preservation; review-state projection derivation; stale-revision rejection;
  exact and conflicting replay; Clip lineage; queue ordering, bounds, and truncation.
- Real-PostgreSQL tests for persistence, restart reconstruction, and migration `0011`
  reverse/reapply.
- Full backend suite, Ruff, Pyright. Frontend unchanged, so frontend checks are not
  required.

## Acceptance criteria

- [ ] `EditorialMomentReviewDecision` is append-only and carries candidate identity and
  revision, actor, decision time, action, notes/reason, and optional adjusted range.
- [ ] All four minimum actions (approve-and-create-clip, reject, revise/range-adjust,
  defer) are implemented.
- [ ] Review state is a projection derived from decision history; prior decisions remain
  visible and are never overwritten.
- [ ] Approval creates an `EditorialClip` with its own identity, approved range,
  candidate and decision lineage, and revision.
- [ ] Clip creation does not render, publish, complete a package, or alter any Session
  boundary.
- [ ] A stale candidate revision is rejected explicitly.
- [ ] Migration `0011` is additive, reverses cleanly, and does not disturb `0008`/`0010`.
- [ ] New routes sit behind the existing ED-0055 shared-secret dependency.
- [ ] Full backend suite, Ruff, and Pyright pass.
- [ ] No machine-origin candidate, automatic approval, export, publishing, or
  packaging-asset behavior is introduced.

## Rollback or reversal

Additive and independently reversible: reverse migration `0011`, remove the new
contracts/routes/tests. ED-0067's declaration path is untouched and continues to work.

## Open questions

- Exact member names for the extended `EditorialReviewState` are an implementation detail;
  choose the smallest clear set that the projection actually requires and document it.

## Completion record

_(To be filled in by whoever implements this plan.)_
