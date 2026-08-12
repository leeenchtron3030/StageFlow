# Durable Event-Mode Kernel independent-review corrections

## Status

Completed — targeted independent correction verification accepted and Green follow-up closed

## Execution authority

- Classification: Green autonomous.
- Authority evidence: Product Constitution principles 8, 9, 15, 17, 19, and 23;
  ADR-0022 PostgreSQL authority and dependency recovery; ADR-0023 conservative media
  association and human package-completion authority; ADR-0024 deterministic turnover
  association plus normalized current state and typed history; the approved Durable
  Event-Mode Kernel architecture and plan; and DKR-001 through DKR-007 in the independent
  phase-completion review.
- Implementation-ready: Yes.
- Required escalation or approval, if any: None. Stop if implementation requires changed
  Session/package semantics, a public compatibility break, a new service or dependency,
  destructive migration, or another Yellow/Red condition.

## Related findings or ADRs

- Finding: DKR-001 through DKR-007 in the
  [independent review](../reviews/durable-event-mode-kernel-independent-review.md).
- ADR: [ADR-0022](../adr/ADR-0022-postgresql-authoritative-operational-store.md),
  [ADR-0023](../adr/ADR-0023-session-authority-and-completion.md), and
  [ADR-0024](../adr/ADR-0024-durable-kernel-authority-and-persistence.md).
- Architecture and prior plan:
  [Durable Event-Mode Kernel](../architecture/durable-event-mode-kernel.md) and
  [implementation plan](durable-event-mode-kernel.md).

## Problem statement

The independent phase review found three High correctness defects and four bounded
Medium/Low gaps in the otherwise coherent Kernel candidate. Interval-less filesystem
media can be guessed into the newly active Session during same-Stage turnover;
reassignment can leave the source Session's changed package falsely complete; a live
process can reuse pre-outage reconciliation after PostgreSQL returns; deterministic
association provenance cannot be reconstructed; Producer Session projections are both
unbounded and incomplete; human decision retries can duplicate history/revisions while
typed history constraints are weaker than current state; and current-facing
documentation still describes implemented Kernel boundaries as absent or open.

## Verified current behavior

- `BoundedMediaCycle._assemble` truthfully supplies no recorded media interval for the
  filesystem path. `DurableEventModeKernel._temporally_eligible` treats interval-less
  media as eligible for an active Session but not a prior ended/assembling Session.
- Both `InMemoryEventModeKernelRepository.put_association` and
  `PostgresEventModeKernelRepository.put_association` reopen only a completed target,
  not a completed source from which membership is removed.
- `KernelComponents.status` has no dependency continuity state and repository readiness
  accepts any latest completed reconciliation, including one completed before an
  observed PostgreSQL outage.
- `MediaAssociation` persists reason/evidence arrays but has no deterministic policy
  identity/version or truthful structural input references; automatic evidence IDs are
  empty.
- PostgreSQL status reads every assembling/correction-required Session without a limit,
  while completed Sessions and Program Expectation context are absent from the response.
- Session start/bootstrap have operation identities and digests. Boundary correction,
  assignment/reassignment, and package completion do not; their typed history tables do
  not consistently enforce current-state enum, ownership, actor, and shape constraints.
- Current-facing project, lifecycle, glossary, ADR-index, and plan statements retain
  pre-Kernel absence/open-decision language.

## Desired behavior

1. Automatic association occurs only when exactly one Session is safely eligible from
   actual durable evidence. Interval-less media remains automatic for a lone obvious
   active Session, but is unresolved during active/previous-assembling turnover.
2. An authoritative membership change atomically reopens every completed source or
   target Session it materially changes, increments each affected package revision,
   preserves prior completion history and approved membership, and remains replay-safe.
3. An observed PostgreSQL loss invalidates reconciliation freshness for the live
   composition. Database return remains recovering/not ready until a fresh persisted
   reconciliation succeeds; failure remains not ready.
4. Deterministic associations persist policy identity/version plus truthful references
   to the durable asset/candidate/Session projections and structural inputs actually
   used. Human association remains distinctly Declared.
5. Producer status exposes explicit bounded assembling and recent Session projections,
   recent completion authority/package state, Program Expectation linkage/context, and
   truthful truncation without exposing secrets or raw paths.
6. Boundary correction, assignment/reassignment, and completion require narrow command
   idempotency identities. Exact semantic replay creates no new history/revision;
   conflicting reuse fails. Database typed history protects material identity, enum,
   ownership, actor, timestamp, and referential invariants.
7. Current-facing documentation reflects the validated Kernel and correction truth
   while historical reviews remain unchanged.

## In scope

- Domain/application contracts and one coherent association/package/idempotency rule.
- In-memory test repository and PostgreSQL repository parity.
- One additive/reversible `0004` correction migration and migration runner update.
- Composition-level PostgreSQL continuity/recovery gating without a background worker or
  generic infrastructure framework.
- Backward-compatible additive Producer status fields and explicit response bounds.
- Behavior-first unit, API, real-filesystem, real-PostgreSQL, migration, replay,
  rollback, and affected Razer qualification tests.
- Directly affected current-facing documentation and a correction-verification artifact.

## Out of scope

- Kernel redesign, generic Jobs/commands/workers, broker, outbox, AI, transcription,
  editorial/publication workflows, authentication redesign, cloud/provider work, or
  production deployment.
- Invented timestamps, grace windows, filename/schedule authority, or synthetic evidence
  identifiers.
- Session split/merge, post-publication late-media policy, unrelated endurance/proxy
  qualification, power-policy changes, npm audit fixes, or historical-review rewrites.
- Kernel phase acceptance or production/event-readiness claims.

## Constraints

- Preserve Program Expectation versus realized Session, Session versus file, and
  discovery/readiness/asset/association boundaries.
- Preserve PostgreSQL as sole composed authority and fail closed across dependency loss.
- Add schema changes only through explicit forward/reversal SQL; keep `0001` through
  `0003` compatible and retain operational lineage on normal forward migration.
- Keep new supplied/persisted timestamps aware and infrastructure times clock-injected.
- Keep behavior-driving provenance first-class and immutable; do not invent evidence or
  create a universal Fact table.
- Keep status read-only, bounded, redacted, and operational rather than historical-catalog
  shaped.

## Implementation approach

1. Refine eligibility so an interval-less ended Session remains plausible only while its
   package is assembling; exact temporal intervals retain existing overlap behavior.
   Persist association policy/version and immutable typed input references.
2. Centralize association transaction semantics in repository contracts: detect old and
   new membership, lock all affected Sessions, reopen every materially changed completed
   package once, append current/history atomically, and snapshot membership when a human
   approves a package revision.
3. Add a narrow typed human-command idempotency ledger used only by boundary correction,
   association/reassignment, and completion. Store a canonical semantic digest and typed
   result identity; replay or conflict before mutation.
4. Add composition-local PostgreSQL recovery-required state. An unavailable observation
   invalidates readiness; a subsequent read remains recovering until an explicit bounded
   media/reconciliation pass completes successfully and persists a newer reconciliation.
5. Add fixed first-Kernel Session limits, explicit truncation, recent completed Session
   projections, completion authority, and Program Expectation context to repository and
   API read models.
6. Apply/reverse/reapply `0004` against isolated PostgreSQL; test direct invalid history
   writes, rollback after injected history failure, reconstruction, and same-process
   outage/recovery.
7. Run focused and full matrices, rerun only materially affected Razer cases, update
   current-facing docs/correction evidence, and deliberately self-review the final diff.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `backend/app/contexts/production/event_mode_kernel/` | Association provenance, command identities, package/replay rules, bounded projections |
| `backend/app/infrastructure/postgres/event_mode_kernel_repository.py` | Atomic source/target reopening, idempotent human commands, bounded joins/projections |
| `backend/app/infrastructure/postgres/sql/0004_*` | Additive provenance/idempotency/membership/history constraints and reversal |
| `backend/app/infrastructure/postgres/migrations.py` | Apply/reverse `0004` in order |
| `backend/app/bootstrap/event_mode_kernel.py` | Same-process PostgreSQL continuity/recovery gate |
| `backend/app/api/v1/kernel_status.py` | Additive bounded recent Session and provenance responses |
| `backend/tests/` and `backend/tests/qualification/` | Focused behavioral, real PostgreSQL, filesystem, migration, and affected Razer checks |
| `docs/PROJECT_BRIEF.md`, `docs/architecture/`, `docs/adr/`, `docs/plans/` | Current-state and completion/correction evidence |

## Data or migration considerations

`0004` is additive. It adds association policy/input provenance, a narrow human-command
idempotency ledger, operation references on typed history, and approved package-membership
snapshots. Existing deterministic decisions receive the known Kernel v1 policy identity;
legacy decisions receive truthful typed references reconstructed from their existing
asset, candidate, binding, and associated-Session records without invented evidence IDs
or historical revisions. Existing human history receives migration-scoped operation
identities that do not pretend an original client key existed. Reversal removes only
`0004` objects/columns/constraints after explicit isolated-database verification and
preserves `0001` through `0003`.

## Failure and recovery considerations

- Association and every affected Session projection/history update share one transaction;
  any failure rolls all of them back.
- Exact command replay returns the existing durable result without another association,
  boundary, completion, package revision, or membership snapshot. Conflicting reuse
  fails before mutation.
- PostgreSQL outage invalidation is composition-local diagnostic state; readiness is
  restored only by a newly persisted reconciliation. Failed recovery retains the gate.
- Source/media failures remain isolated and do not discard registered media or block
  unrelated Stages.

## Observability requirements

- Operators can see recovery-required/reconciling/failed versus ready and a newer
  reconciliation identity after dependency recovery.
- Media projections expose deterministic policy/version, truthful input/evidence
  references, and distinct human authority.
- Session projections expose a fixed limit, truncation truth, recent completion decision
  identity/actor/time, package revision/state, and Program Expectation identity/title/
  revision/planned interval without flattening it into observed truth.
- DSNs, secrets, environment values, and raw source paths remain absent.

## Test strategy

- Association: lone active interval-less media; real filesystem turnover ambiguity;
  exact temporal selection of old/current; ambiguous overlap; structural conflict;
  replay.
- Package integrity: incomplete/completed source-target matrix, approved membership
  snapshot, revision increments, replay, direct retry, and transaction rollback.
- Recovery: real PostgreSQL same-process ready -> unavailable -> recovery-required ->
  failed/successful fresh reconciliation -> ready with advanced run identity.
- Provenance/API: deterministic policy/version, durable input/evidence reconstruction,
  human distinction, expectation link, completion authority, boundedness/truncation, and
  redaction.
- Idempotency/history: exact replay, cross-command/key conflict, no duplicate revision,
  and invalid direct SQL rejection.
- Migration: clean apply, `0004` reverse preserving prior migrations, and reapply on an
  isolated real PostgreSQL database.
- Full closeout: backend pytest with real PostgreSQL, Ruff, Pyright, clean frontend
  `npm ci`, build, lint, typecheck, `git diff --check`, and configured documentation
  checks if present. Report npm audit separately; do not fix it.

## Acceptance criteria

- [x] DKR-001 through DKR-007 have evidence-backed RESOLVED/PARTIALLY RESOLVED/NOT
  RESOLVED dispositions in a correction artifact.
- [x] All interval-less and timestamped turnover cases follow ADR-0024 without invented
  evidence or timestamps.
- [x] Every materially affected completed source/target Session reopens atomically and
  the earlier approval plus approved membership remains reconstructable.
- [x] Same-process PostgreSQL recovery cannot report ready until a newer successful
  reconciliation completes; failure remains not ready.
- [x] Automatic association provenance and bounded Producer projections reconstruct
  through PostgreSQL and the API without secret/path disclosure.
- [x] Human boundary, assignment/reassignment, and completion retries are idempotent and
  conflicting key reuse is rejected.
- [x] Typed history constraints reject materially impossible direct persistence.
- [x] Focused, full, real-PostgreSQL, migration, and affected Razer checks pass, with
  skips/warnings reported exactly.
- [x] Documentation reflects current truth, working tree is clean, and no Yellow/Red
  condition remains.
- [x] Branch is prepared only for targeted independent correction verification; the
  Kernel is not self-accepted and no production/event-readiness claim is made.

## Rollback or reversal

- Code/API additions are reversible as one correction batch; preserve caller-visible
  additive status fields during ordinary forward operation.
- `0004` reversal is an explicit isolated/operator-approved action only. It drops only
  correction-owned constraints, columns, and tables and removes only its migration-ledger
  row; it does not reverse prior Kernel or ingress migrations.
- No source media, credentials, production data, machine policy, or external service is
  modified by this plan.

## Open questions

- None. Ordinary implementation choices remain bounded by the accepted ADRs and this
  plan.

## Completion record

- Implemented revision: `b6deafc` plus the containing documentation/evidence closure
  commit.
- Files and migrations actually changed: Kernel contracts/service/repositories,
  composition recovery gate, Producer status API, migration runner, new additive/reversible
  `0004_kernel_review_corrections` SQL, focused tests/qualification harness, and directly
  affected project/architecture/ADR/plan/review documentation.
- Commands and tests actually run: focused and full backend pytest with real PostgreSQL,
  Ruff, Pyright, clean frontend install/build/lint/typecheck, read-only npm audit,
  isolated PostgreSQL forward/reverse/reapply inspection, affected Razer recovery, and
  `git diff --check`. Exact results are in the linked
  [correction evidence](../reviews/durable-event-mode-kernel-correction-evidence.md).
- Results and warnings: All correctness/quality gates passed. Backend full suite: 1,617
  passed, 5 skipped, 1 existing deprecation warning. npm audit separately reports 12
  findings (3 moderate, 9 high); no fix was applied.
- Execution authority used: Green autonomous.
- Approved deviations: None.
- Rollback status: Verified on isolated real PostgreSQL; reverse preserved `0001` and
  removed Kernel/correction objects, and reapply restored `0001` through `0004`.
- Remaining work: Fresh targeted independent correction verification and an independent
  phase decision. No finding remains for this implementation task.

### 2026-08-09 targeted verification and Green closure

- The [targeted independent correction verification](../reviews/durable-event-mode-kernel-correction-verification.md)
  returned **ACCEPT WITH GREEN FOLLOW-UP** and identified DKV-001 through DKV-004.
- The separate [Green follow-up plan](durable-event-mode-kernel-green-follow-up-closure.md)
  implemented and validated all four findings. Its
  [closure evidence](../reviews/durable-event-mode-kernel-green-follow-up-closure.md)
  recommends **ACCEPT** for the bounded operational foundation.
- This closes the pending correction-verification work. It does not establish production
  or event readiness.
