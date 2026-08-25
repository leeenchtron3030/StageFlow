# ED-0063–ED-0067 consistency closure and PR #79 review

## Status

Completed on 2026-08-22 as a Green, non-destructive repository reconciliation.

This is review and execution evidence, not new architecture authority and not a
production/event-readiness claim.

## Scope and authority

The user supplied and authorized execution of a consistency-closure directive covering
ED-0063 through ED-0067, PR #71, PR #79, and the publication state of ED-0064 through
ED-0066. The work was bounded to repository inspection, historical correction,
independent diff review, compatibility documentation, and validation.

No deployment, merge, force-push, shared-history rewrite, dependency change, schema
change, runtime-configuration change, Devcon write, or product-authority decision was
authorized or performed.

### Directive identifier note

The supplied directive is titled ED-0069. Repository inspection also found remote branch
`docs/ed-0069-frontend-dependency-security` at
`cbd1f6685c6a5f1925f5582a73195e39a34e8638`, which independently allocates ED-0069 to
frontend dependency security remediation. That branch is not on main and had no open PR
at this review. This closure does not silently choose between the duplicate identifiers
and does not add an ED-0069 row to `ENGINEERING_DIRECTIVES.md`. The identifier collision
requires later governance reconciliation before either proposal is registered on main.

## Exact review baselines

| Subject | Base / current-main evidence | Head / branch evidence | Review use |
| --- | --- | --- | --- |
| PR #79 / ED-0067 | GitHub base SHA and current main: `e81b60944b4068e4589c9d1a03e985d9cdaadc02` | `ccb1283242b6563c3b890574ecde895951b71ec5` | Exact base-to-head diff review before closure edits |
| PR #71 / ED-0063 | GitHub reported base SHA `99185b04825b9c2250644b3d28fb4167c2b5d57f`; current main `e81b609…`; current merge base `271f0b7a5154fb1d60754ab13b5275efa1bab775` | `9c176d47e3c1eb62d5e6b1bdab4204b006f18e3c` | Worktree/remote identity, safety-net review, and current-main merge simulation |
| PR #76 / ED-0064–ED-0066 | GitHub reported base SHA `99185b04825b9c2250644b3d28fb4167c2b5d57f` | `c4120fe8ded9697292f065d441c5355f9243b896` | Publication-state and current-main conflict reconciliation |

GitHub reported PR #79 open/non-draft and PR #71 open/draft. Both required quality-matrix
checks were successful on each exact head. PR #76 was open with both checks successful,
but a local current-main merge simulation found documentation conflicts as recorded
below.

## ED-0067 historical correction

The approved [ED-0067 plan](../plans/editorial-candidate-moment-phase1.md) originally
concluded that no Editorial package, Candidate Moment migration, or Mark Moment command
existed. That conclusion was false. Demo 1 already contained:

- the `app.contexts.editorial` package and compatibility import surface;
- durable `stageflow.editorial_candidate_moment` declaration storage from migration
  `0008_demo_vertical_slice`;
- PostgreSQL declaration and human-command idempotency behavior;
- `/api/v1/demo/moments/*` routes; and
- end-to-end human Mark Moment tests.

Repository-grounded ED-0067 implementation preserved that aggregate and authority,
refactored it into canonical contracts/repository/service modules, retained compatible
Demo imports and routes, and added the genuinely missing migration `0010` append-only
Session-boundary location evaluations plus bounded projections and canonical
`/api/v1/editorial/*` routes. It introduced no duplicate aggregate and replaced no
existing human declaration authority.

The plan now retains the incorrect original premise as an explicit planning-quality
correction rather than rewriting history to make the miss invisible.

## Independent PR #79 diff review

### Method

The review began from the clean main worktree and inspected
`e81b60944b4068e4589c9d1a03e985d9cdaadc02...ccb1283242b6563c3b890574ecde895951b71ec5`
before any closure edit. It reviewed the actual diff, migrations, tests, route
composition, and PostgreSQL transaction boundaries rather than inferring behavior from
the final tree alone.

### Findings by severity

- **Blocker:** none.
- **Critical:** none.
- **Major:** none.
- **Minor C-001 — closed in this change:** the ED-0067 planning section still presented
  the false no-Editorial baseline under “Verified current behavior.” The plan now
  preserves and corrects that historical miss explicitly.
- **Minor C-002 — closed in this change:** the duplicate Demo and canonical Editorial
  HTTP surfaces were compatible in code but not explicitly classified. Package
  documentation now records `/editorial/*` as canonical and `/demo/moments/*` as
  transitional Demo compatibility over the same authority.
- **Non-blocking future cleanup:** deprecate/remove duplicate Demo exposure only through
  a separately approved bounded API cleanup after the Demo compatibility contract allows
  it. This is not a PR #79 merge blocker.

There are no unresolved blocking PR #79 findings.

### Semantic review

| Area | Evidence reviewed | Disposition |
| --- | --- | --- |
| Exact and conflicting replay | Digest-based `human_command_idempotency` insert uses `ON CONFLICT`; exact digest returns the original result and differing kind/digest raises the established conflict | Correct |
| Stale Session revision | Session row is locked/read in the declaration transaction and mismatched expected revision raises before candidate insertion | Correct |
| Concurrent declaration | Distinct operations commit independently; same-operation contention serializes through the unique idempotency key; PostgreSQL two-thread qualification passed | Correct |
| Transaction rollback | Idempotency reservation, Session validation, and candidate insertion share one connection transaction; exceptions roll back the reservation and candidate write together | Correct |
| Migration 0010 | Forward creates only `editorial_candidate_moment_location_history`, its index, and ledger row; reverse drops only that table/ledger entry; runner reverses it before migration 0008 | Correct and additive |
| Boundary classification | Original declaration basis reconstructs absolute point/range time; contained, partial, and excluded cases retain candidate identity/location. A missing candidate end is a point; an open-ended Session omits only the upper-bound test | Correct |
| Failure/retry composition | Kernel correction commits first; Editorial storage failure reports 503. Exact Kernel-command retry re-runs revalidation, preserving recoverability without rolling back or mutating Kernel authority | Correct |
| Restart/latest reconstruction | Reads select the highest evaluated Session revision, then evaluation time; unique candidate/revision history prevents duplicate evaluation authority | Correct |
| Demo/canonical compatibility | `moments.py` re-exports canonical contracts/service; both route families use one composed service/repository; existing Demo routes remain | Correct; transitional status now documented |
| Shared-secret protection | Editorial router is included with the same ED-0055 include-level dependency as other operational routers; authentication tests include the new route | Correct |
| Producer projections | Canonical list limit is 1–100 with explicit truncation; repository batch projection is bounded, avoids N+1 queries, and exposes count/latest/conflict plus only `healthy` or `unknown` generation state | Correct |
| Authority exclusions | No machine-origin producer, review decision, Clip, worker/model, automation, or Session/media/package authority was added | Correct |

## PR #71 / ED-0063 reconciliation

- The existing worktree was clean and matched remote head
  `9c176d47e3c1eb62d5e6b1bdab4204b006f18e3c`.
- The head contains rebased Demo 2 commit `eccb666` and safety-net commit `9c176d4`.
- A fresh merge simulation against current main completed without conflict and produced
  tree `e736e3cd680b71017f61a5bb28844acdd95a1253`.
- The autonomous loop catches unexpected program/media cycle exceptions, logs bounded
  context, marks the relevant projection degraded with
  `unexpected_cycle_failure`, advances scheduling in `finally`, and continues.
- The focused autonomous-node suite passed 9 tests; scoped Ruff and Pyright passed.
- GitHub reports PR #71 open and draft with both required checks successful.
- Demo 2 remains **not promotion-qualified** until the required fresh two-machine live
  rehearsal succeeds. CI, static checks, and mergeability do not satisfy that gate.
- No rebase, push, force-push, or history rewrite was performed by this closure. The
  earlier branch-local statement that remote head `2280ed0` remained stale is
  superseded by the verified remote head above.

No PR #71 shared-history action currently needs execution. Any future rewrite requires a
separate approval immediately before execution, an exact expected remote SHA, and
`git push --force-with-lease`; unguarded `--force` remains prohibited.

## ED-0064–ED-0066 publication state

All three outputs are committed and published on remote branch
`codex/coordinator-decomposition-adr-sbom` / open PR #76 at
`c4120fe8ded9697292f065d441c5355f9243b896`. They are not on main, not uncommitted,
not local-only, and not superseded.

| Directive | Published artifact/state | Reconciliation |
| --- | --- | --- |
| ED-0064 | Coordinator decomposition into three internal modules plus the preserving coordinator facade | Branch/PR only; current-main merge simulation conflicts only in `ENGINEERING_DIRECTIVES.md` and `docs/plans/README.md`; no behavior conflict was reported |
| ED-0065 | Accepted ADR-0028 documenting the already-shipped bounded Devcon integration | Branch/PR only; remains documentary and grants no broader Devcon write authority |
| ED-0066 | License report plus backend/frontend CycloneDX and backend license artifacts | Branch/PR only; evidence remains current to its recorded baseline, not a dependency or legal decision |

PR #76 had both required GitHub checks successful at its head. It must be reconciled with
current main through its own reviewed branch update before merge; this closure does not
rewrite or merge that branch.

The PyAV/FFmpeg build and distribution provenance question remains explicitly unresolved.
No dependency, wheel, FFmpeg build, distribution model, or legal conclusion was selected.

## Behavior changed and deliberately preserved

This closure changes documentation only.

Preserved behavior includes all ED-0067 runtime contracts, declaration/idempotency
authority, migrations, route signatures, authentication, Session/media/package
authority, PR #71 loop behavior, and ED-0064–ED-0066 branch contents. It removes no Demo
route/import and performs no external integration write.

## Validation

Commands and results recorded during the closure:

- `git ls-remote origin refs/heads/main refs/pull/71/head refs/pull/71/merge refs/pull/79/head refs/pull/79/merge` — exact remote refs obtained.
- `gh pr view 71`, `gh pr view 76`, and `gh pr view 79` with JSON state/check fields — live PR state and required checks inspected.
- `git diff --check e81b609...ccb1283` — PR #79 diff clean.
- `uv run pytest -p no:cacheprovider --tb=short tests/test_editorial_candidate_moment_phase1.py tests/test_demo_api.py tests/test_api_authentication.py tests/test_kernel_composition_and_status.py` — 29 passed with one existing Starlette/httpx deprecation warning; PostgreSQL replay, concurrency, restart, and migration reverse/reapply tests ran rather than skipped.
- Scoped ED-0067 `uv run ruff check ...` — passed.
- Scoped ED-0067 `uv run pyright ...` — 0 errors and 0 warnings.
- PR #71 `git merge-tree --write-tree e81b609... 9c176d4...` — clean; tree `e736e3c...`.
- PR #71 focused pytest — 9 passed; scoped Ruff and Pyright passed.
- PR #76 current-main merge simulation — conflicts in
  `ENGINEERING_DIRECTIVES.md` and `docs/plans/README.md`; no branch mutation performed.
- Final `uv run pytest -p no:cacheprovider --tb=short` — 1,803 passed, 5 skipped,
  with the same existing Starlette/httpx deprecation warning.
- Final `uv run ruff check .` — passed.
- Final `uv run pyright` — 0 errors and 0 warnings. In the isolated worktree it also
  printed a non-failing notice that the worktree-local `.venv` directory was absent;
  the command used the existing synchronized project environment.
- Final closure `git diff --check` and deliberate diff review — run after the last
  documentation edit.

Frontend checks are not rerun locally because this closure changes no frontend file or
frontend-consumed API contract. GitHub's frontend quality check was successful on the
exact PR #79 head reviewed.

## Remaining risks and deferred work

- Resolve the duplicate ED-0069 identifier before registering either proposed directive
  on main.
- Reconcile PR #76's two documentation conflicts through its own branch workflow.
- Keep PR #71 draft until fresh two-machine live rehearsal evidence exists.
- Treat canonicalization/deprecation of `/demo/moments/*` as a separate bounded cleanup.
- Preserve the PyAV/FFmpeg provenance and distribution question for explicit
  product/legal/release disposition.
- Editorial review, Clip creation, machine candidates, workers/models, and automation
  remain later phases.

## Architecture confirmation

No architecture decision was made implicitly. StageFlow remains within the accepted
local-first, modular-monolith, durable-evidence, at-least-once, and human-authority
architecture. The closure improves repository memory without changing runtime authority.
