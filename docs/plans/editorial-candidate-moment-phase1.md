# Editorial Candidate Moment — Phase 1 human-declared slice

## Status

Completed

## Execution authority

- Classification: Green autonomous
- Authority evidence: [Post-Kernel capability layer architecture](../architecture/post-kernel-capability-layer.md)
  explicitly classifies exactly this scope as "Green once a bounded implementation plan is
  approved" (its own "Recommended delivery sequence" step 1 and "Decision classification"
  section). [Post-Kernel capability layer plan](post-kernel-capability-layer.md) records
  this as its own required next step ("Extract Phase 1 into a small Green plan...",
  acceptance criterion "Phase 1 is extracted into a Green implementation-ready plan").
  Explicit 2026-08-22 user directive to move from due-diligence remediation to new
  capability work.
- Implementation-ready: Yes
- Required escalation or approval, if any: None for this slice. Machine-origin candidates
  (derived/inferred), review decisions, Editorial Clip creation, and any worker/model
  selection remain out of scope and Yellow-gated by their own later phases — do not expand
  into them here.

## Related findings or ADRs

- Finding/disposition: Post-Kernel capability layer plan, Phase 1 (`## Implementation
  approach > Phase 1 — human-declared Moment slice`).
- ADR: None required for this slice. ADR-0026 (automatic authority) and the Packaging
  Asset identity decision remain unresolved Yellow items unrelated to this human-declared,
  non-automatic slice.
- Engineering Directive: ED-0067.

## Problem statement

The original plan framed the problem as if the Kernel-era repository had no durable way
for a human to mark a Session-timeline moment. That planning premise was inaccurate.
Demo 1 had already shipped an end-to-end, PostgreSQL-backed human Mark Moment path.

The actual gap was that this authority still lived in a Demo-oriented module/API shape
and lacked append-only Session-boundary location evaluation plus bounded Producer
projections. ED-0067 therefore needed to preserve and promote the existing declaration
authority, not create a second Editorial aggregate.

## Planning-time investigation and corrective record

The following bullets preserve what the plan established correctly and make the planning
miss explicit rather than rewriting history to imply the original investigation was
accurate:

- `backend/app/contexts/production/event_mode_kernel/`: `contracts.py`, `repository.py`,
  `service.py` establish this repo's bounded-context pattern (typed frozen contracts +
  repository protocol + application-service orchestration). New Editorial code should
  follow the same shape in a sibling `backend/app/contexts/editorial/` package, not extend
  the Kernel package.
- `backend/app/infrastructure/postgres/migrations.py`: migrations are sequentially
  numbered `NNNN_name_forward.sql`/`NNNN_name_reverse.sql` under
  `app/infrastructure/postgres/sql/`, applied via `_execute_if_missing`/`_execute_if_present`
  keyed by a `version` string in `stageflow.schema_migration`. Current highest is `0009`
  (`program_expectation_reconciliation`); this slice is `0010`.
- `DurableEventModeKernel.correct_session_boundary` (service.py) already handles Session
  boundary correction with idempotent request digests and stale-revision protection. The
  new candidate-location revalidation on boundary correction must observe this existing
  path (e.g. via a read-only reference to the corrected boundary), not modify it.
- `backend/app/api/v1/` routes are thin FastAPI routers (`demo.py`, `kernel_status.py`)
  that call into application services; `router.py` applies the ED-0055 shared-secret
  dependency at include level. Any new Editorial route must be included the same way.
- **Incorrect planning-time conclusion:** the plan stated that no
  `backend/app/contexts/editorial/` package, Editorial migration, or `Mark Moment`
  command existed. Repository-grounded implementation found that Demo 1 already
  contained the `editorial` package, migration `0008_demo_vertical_slice`'s durable
  `editorial_candidate_moment` table, the PostgreSQL declaration repository/service,
  `/demo/moments/*` API wiring, idempotent human-command replay, and tests.
- **Actual missing scope:** canonical bounded-context contracts/repository/service
  modules, append-only Session-boundary location-evaluation history, authenticated
  `/editorial/*` exposure, and bounded per-Session projections.

## Desired behavior

A Producer (or, later, any authorized actor) can durably declare a Candidate Moment at a
specific point or range on a Session's timeline. The declaration is idempotent, survives
restart, is never silently moved or deleted by a later Session boundary correction
(instead surfacing an explicit conflict), and is visible through bounded count/latest-
activity/generation-state projections. No review, approval, Clip, model, or worker
capability is introduced by this slice.

## In scope

The bullets below preserve the original intended capability shape. During implementation,
the declaration portions were satisfied by refactoring and retaining Demo 1 authority;
only the genuinely missing history/projection surface was added as new durable behavior.

- `backend/app/contexts/editorial/contracts.py`: frozen, immutable `EditorialCandidateMoment`
  contract per the architecture's "smallest coherent candidate" field list, restricted to
  fields meaningful without review/machine input:
  - stable candidate ID (`EntityId`), immutable Session ID;
  - versioned Session-timeline location: start position, optional end position, plus the
    Session revision/boundary basis used to interpret it at declaration time;
  - created/updated times (timezone-aware, injected `Clock`, not read directly);
  - actor ID (the declaring operator);
  - epistemic origin fixed to `declared` for this slice (the field exists per the
    architecture's four-origin model so Phase 4 can add `observed`/`derived`/`inferred`
    without a contract break, but only `declared` is producible here);
  - source kind fixed to a Producer/human declaration source reference;
  - optional concise rationale/note;
  - a minimal review-state field that always reports `unreviewed` in this slice (no
    command in this phase can change it — Phase 2 adds the actual review decision path);
  - a `location_conflict` flag/reason surfaced when a boundary correction has excluded the
    candidate's location (see below), never a silent deletion or move;
  - revision number for optimistic concurrency on any future correction to the candidate
    itself (not the Session).
- `backend/app/contexts/editorial/repository.py`: a persistence-neutral protocol (mirroring
  `EventModeKernelRepository`'s shape) plus a concrete PostgreSQL implementation:
  - `declare_candidate(...)`: idempotent by operation ID, rejects stale Session revision,
    persists an append-only declaration record;
  - `list_candidates_for_session(session_id)`, `count_candidates_for_session(session_id)`,
    `latest_candidate_activity(session_id)`: bounded read queries backing the Producer
    projection;
  - a mechanism invoked when a Session boundary correction occurs (read-only trigger from
    the Kernel side, e.g. the API/application layer calling both operations in sequence,
    not the Editorial repository reaching into Kernel internals) that re-evaluates each
    affected candidate's location against the new boundary and marks it as a location
    conflict rather than moving or deleting it.
- `backend/app/contexts/editorial/service.py`: an `EditorialApplicationService` (or
  similarly named) exposing `mark_moment(...)` as the idempotent application command
  (actor, operation ID, Session ID, expected Session revision, declared time,
  position/optional end position, optional note) and the bounded read operations above.
- Migration `0010_editorial_candidate_moment_forward.sql` /
  `0010_editorial_candidate_moment_reverse.sql`, wired into `PostgresMigrationRunner`
  following the existing `apply_*_v1`/`reverse_*_v1` + `_execute_if_missing`/
  `_execute_if_present` pattern. New tables only; no existing Kernel table altered.
- A new `backend/app/api/v1/editorial.py` router exposing `POST .../moments/mark` and a
  bounded read endpoint for Producer projection data, included in `router.py` behind the
  same ED-0055 shared-secret dependency as the other operational routers.
- Producer-facing projection additions: per-Session candidate count, latest candidate
  time, and a `generation_state` of `healthy` (has recent activity or none expected) —
  `unknown` is the only other state meaningful in this slice, since `deferred`/`blocked`
  require worker/model infrastructure that doesn't exist yet. Do not fabricate a
  `deferred`/`blocked` state this slice cannot actually produce.
- Tests: contract identity/immutability/strict-time tests; command replay (exact,
  conflicting, stale-Session-revision) tests; boundary-correction-produces-conflict (not
  silent move/delete) tests; restart/reconstruction tests; bounded-projection tests.

## Out of scope

- Any `observed`/`derived`/`inferred` candidate origin, machine/model candidate
  generation, or any worker/Durable Operation integration (Phase 3/4).
- Editorial review decisions, Editorial Clip creation, or any Editorial UI/queue (Phase 2).
- Assembly, Packaging Asset, or automation policy (Phases 5/6, Yellow-gated).
- Any change to Kernel Session/media/package authority, `correct_session_boundary`'s own
  behavior, or existing Kernel migrations.
- Frontend implementation beyond whatever minimal projection surface is needed to prove
  the API contract — a full Producer UI treatment for Moment awareness is a separate,
  later scoped frontend task, not required for this backend-durability slice to be
  acceptance-complete.

## Constraints

- Architecture and terminology constraints: use `Editorial Candidate Moment` (not
  "Moment" alone in code/API identifiers); `Hot` is urgency, never introduced as a
  separate aggregate or approval state in this slice; epistemic origin values must match
  the four-value vocabulary (`observed`/`derived`/`inferred`/`declared`) even though only
  `declared` is producible here.
- Compatibility constraints: no existing Kernel contract, repository method, migration,
  or API route changes signature or behavior. New tables/routes only.
- Offline/Event Mode constraints: candidate declaration must work fully local/offline,
  consistent with the rest of the Kernel; no cloud dependency introduced.
- Security/data-handling constraints: no real event media or customer data in tests;
  projections omit raw paths and unbounded diagnostic detail, consistent with existing
  Kernel projection conventions.

## Implementation approach

1. Add `backend/app/contexts/editorial/contracts.py` with the `EditorialCandidateMoment`
   contract and any small supporting value types (location, origin, review-state enum).
2. Add `backend/app/contexts/editorial/repository.py`: protocol + PostgreSQL
   implementation, following the Kernel repository's connection/transaction conventions.
3. Write migration `0010_editorial_candidate_moment_forward.sql` (new schema/table(s) under
   `stageflow.*`, indexed by Session ID) and its reverse, and wire both into
   `PostgresMigrationRunner` as `apply_editorial_candidate_moment_v1()`/
   `reverse_editorial_candidate_moment_v1()`, called from the existing
   `apply_event_mode_kernel_v1()`/`reverse_event_mode_kernel_v1()` chain in the same style
   as `0008`/`0009`.
4. Add `backend/app/contexts/editorial/service.py` with `mark_moment(...)` and the bounded
   read operations, plus the boundary-correction re-evaluation hook.
5. Add `backend/app/api/v1/editorial.py`, include it in `router.py` behind the existing
   shared-secret dependency.
6. Add the Producer projection fields (count/latest-activity/generation-state) to
   whatever existing Kernel-status or Session-workspace projection is the natural home
   (read from `kernel_status.py`'s existing composition pattern — do not invent a
   parallel status endpoint).
7. Write tests per the Test strategy below; run full backend suite, Ruff, Pyright.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `backend/app/contexts/editorial/contracts.py` | New: `EditorialCandidateMoment` and supporting types |
| `backend/app/contexts/editorial/repository.py` | New: protocol + PostgreSQL implementation |
| `backend/app/contexts/editorial/service.py` | New: `mark_moment` command + bounded reads |
| `backend/app/infrastructure/postgres/sql/0010_editorial_candidate_moment_forward.sql` | New migration |
| `backend/app/infrastructure/postgres/sql/0010_editorial_candidate_moment_reverse.sql` | New reversal |
| `backend/app/infrastructure/postgres/migrations.py` | Wire the new migration into the existing apply/reverse chain |
| `backend/app/api/v1/editorial.py` | New: `Mark Moment` command route + bounded read route |
| `backend/app/api/v1/router.py` | Include the new router behind the ED-0055 auth dependency |
| `backend/app/api/v1/kernel_status.py` (or equivalent) | Add bounded candidate count/latest-activity/generation-state projection fields |
| `backend/tests/` | New contract, repository, command-replay, boundary-conflict, and projection tests |
| `docs/plans/post-kernel-capability-layer.md` | Mark the Phase 1 extraction acceptance criterion complete, link this plan |

## Data or migration considerations

Migration `0010` is additive only and alters no existing table. It does not create the
candidate declaration authority: migration `0008_demo_vertical_slice` already owns the
immutable human declaration record. Migration `0010` adds only append-only location
evaluations keyed by candidate and Session revision. Reversal drops that history table
and its ledger entry while preserving the `0008` declaration table and every Kernel
table. The runner reverses `0010` before its `0008` dependency.

## Failure and recovery considerations

- `mark_moment` is idempotent by operation ID: exact replay returns the original result;
  conflicting replay (same operation ID, different content) is rejected; stale Session
  revision is rejected before any write.
- A Session boundary correction that excludes or partially excludes a candidate's location
  must never silently delete or move it — it becomes an explicit, queryable conflict.
- PostgreSQL unavailability makes candidate declaration/read unavailable; there is no
  in-memory authoritative fallback, matching the architecture's explicit requirement.
- Restart must reconstruct all candidate state and history from PostgreSQL with no data
  loss and no duplicate candidates from replayed startup logic.

## Observability requirements

Producer projections must expose, per active Session: candidate count, latest candidate
declaration time, and a `healthy`/`unknown` generation state (no `deferred`/`blocked`
claim this slice cannot back). A location-conflicted candidate must be distinguishable in
any read model that surfaces it, without requiring a raw diff against Session history.

## Test strategy

- Contract tests: identity, strict aware time, recursive immutability, epistemic-origin
  restricted to `declared` in this slice's command surface.
- Command/repository tests: exact replay, conflicting replay (`human_command_operation_id_conflict`-style
  rejection matching existing Kernel command conventions), stale Session revision
  rejection, concurrent declaration isolation.
- Boundary-correction tests: a correction that fully contains, partially excludes, and
  fully excludes a candidate's location, asserting conflict-surfacing rather than
  silent mutation/deletion in each case.
- Migration tests: forward/reverse/reapply against an isolated PostgreSQL instance,
  restart reconstruction, and confirmation that reversal touches no Kernel table.
- Bounded projection tests: pagination/limit where applicable, count and latest-activity
  correctness, generation-state values restricted to `healthy`/`unknown`.
- Full quality commands: `uv run pytest`, `uv run ruff check .`, `uv run pyright`,
  `git diff --check`.

## Acceptance criteria

- [x] `EditorialCandidateMoment` contract exists, is immutable, and uses the four-value
  epistemic-origin vocabulary while only `declared` is producible by this slice's command.
- [x] `mark_moment` is idempotent by operation ID with exact/conflicting-replay and
  stale-Session-revision behavior matching existing Kernel command conventions.
- [x] Candidates persist in PostgreSQL with append-only history; no in-memory
  authoritative fallback exists.
- [x] A Session boundary correction that excludes or partially excludes a candidate's
  location produces an explicit conflict, never a silent move or delete.
- [x] Bounded Producer projection exposes count, latest activity, and `healthy`/`unknown`
  generation state per Session.
- [x] The new API route is included behind the existing ED-0055 shared-secret dependency.
- [x] Demo 1's existing human declaration aggregate, idempotency authority, imports, and
  `/demo/moments/*` routes are preserved; no duplicate aggregate or replacement
  declaration authority was introduced.
- [x] The original planning miss and the repository-grounded correction remain explicit
  in this historical plan.
- [x] No existing Kernel contract, repository, migration, or route contract changed;
  the Demo boundary route additively composes Editorial revalidation after the unchanged
  Kernel correction.
- [x] Full backend suite, Ruff, and Pyright pass; `git diff --check` passes.
- [x] `docs/plans/post-kernel-capability-layer.md`'s Phase 1 extraction acceptance
  criterion is marked complete and linked to this plan.

## Rollback or reversal

Run the `0010` reversal migration (drops only the new location-history table), remove
the canonical Editorial additions while retaining the Demo 1 declaration compatibility
surface, remove the new API route/router inclusion, and revert the Producer projection
addition. No Kernel data, schema, or migration is touched by rollback.

## Open questions

- **Resolved:** per-Session count/latest/generation/conflict fields extend the existing
  bounded Kernel status Session projection, while the canonical Editorial router owns
  bounded candidate-list detail. Both reuse the same repository projection.

## Completion record

- **Implemented revision:** `ccb1283242b6563c3b890574ecde895951b71ec5` on
  `codex/ed-0067-editorial-candidate-moment`; the later consistency-closure commit
  corrects repository memory without changing that implementation.
- **Files and migrations actually changed:** canonical Editorial contracts, repository
  protocol, service, compatibility exports, PostgreSQL adapter, migration 0010
  forward/reverse and runner wiring, bootstrap boundary revalidation, authenticated
  Editorial API, Demo compatibility response, Kernel status projection, focused tests,
  and directly affected architecture/package/index documentation.
- **Commands and tests actually run:** focused Editorial/Demo/auth/status pytest plus
  Ruff/Pyright; isolated PostgreSQL replay, concurrency, restart, location-conflict, and
  0010 reverse/reapply qualification; full backend `uv run pytest -p no:cacheprovider`,
  `uv run ruff check .`, and `uv run pyright`; final `git diff --check` and diff review.
- **Results and warnings:** 1,803 backend tests passed, 5 skipped, with one existing
  Starlette/httpx deprecation warning; Ruff passed; Pyright reported zero errors and
  warnings. Migration 0010 reversed and reapplied successfully while preserving the
  migration-0008 candidate table.
- **Execution authority used:** Green autonomous ED-0067 scope.
- **Planning-quality correction / implemented deviation:** the original investigation
  incorrectly concluded that no Editorial package, Candidate Moment migration, or Mark
  Moment command existed. Repository-grounded implementation discovered Demo 1's
  durable human-declared Candidate Moment behavior and API wiring. ED-0067 preserved
  that authority, refactored it into the bounded contracts/repository/service shape,
  retained backward-compatible Demo imports/routes, and added only the genuinely
  missing append-only Session-boundary location-evaluation history and bounded
  projections. No duplicate Editorial aggregate was introduced and no existing human
  declaration authority was replaced. This is recorded as a planning miss, not concealed
  as if the original baseline had been accurate.
- **Independent closure review:** the exact PR #79 base-to-head diff and related PR
  state are recorded in
  [the ED-0063–ED-0067 consistency closure](../reviews/consistency-closure-ed-0063-ed-0067.md).
- **Rollback status:** qualified on the isolated PostgreSQL database; 0010 reversal drops
  only location history and leaves Kernel tables plus the 0008 declaration base intact.
- **Remaining work:** Editorial review decisions, Editorial Clip creation, machine-origin
  candidates, ranking/queue behavior, workers/models, and automation remain later phases.
