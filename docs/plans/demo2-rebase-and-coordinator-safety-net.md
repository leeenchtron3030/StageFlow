# Demo 2 rebase onto main and coordinator exception safety net

## Status

Approved

## Execution authority

- Classification: Green autonomous
- Authority evidence: Independent review of PR #71 (2026-08-21) found the branch now
  conflicts with `main` due to duplicated independent implementation of the same Package
  Approval feature (resolved on `main` via PR #72 before PR #71's conflict was noticed),
  and identified an untested exception-handling gap in the autonomous coordinator. Both
  findings were posted to PR #71 as review comments. Explicit 2026-08-21 user directive to
  continue directing Codex on StageFlow's structural work.
- Implementation-ready: Yes
- Required escalation or approval, if any: None — the merge-conflict resolution has only
  one correct answer (main's already-merged implementation is canonical; Demo 2's
  functionally-equivalent duplicate is dropped), and the exception-safety fix is
  additive-only observability, matching the already-accepted pattern from ED-0057.

## Related findings or ADRs

- Finding/disposition: PR #71 review comment (2026-08-21,
  https://github.com/leeenchtron3030/StageFlow/pull/71#issuecomment-5372343997) —
  confirmed merge conflict in `backend/app/api/v1/demo.py` and
  `backend/app/contexts/production/event_mode_kernel/service.py`; confirmed via
  `git merge-tree` and by running `test_package_approval_requires_reviewable_exact_revision_and_is_idempotent`
  against the Demo 2 branch that both implementations are behaviorally equivalent (the
  actual revision-conflict guard lives in the untouched `repository.py`, not either
  branch's `service.py`). Separately, `backend/app/demo/autonomous.py`'s `_run_owned`
  cycle loop only catches `KernelStorageUnavailableError`,
  `WorkExecutionStorageUnavailableError`, `OSError`/`RuntimeError`/`ValueError`, and
  `DevconReadError`; any other exception silently kills the coordinator thread while
  `_started` stays `True` (so `start()` never restarts it) and status freezes at its last
  value, misreporting automation health. No test exercises this path.
- ADR: None required.
- Engineering Directive: ED-0063.

## Problem statement

PR #71 (`codex/demo2-autonomous-event-node`) cannot merge as-is: it duplicates the Package
Approval feature that already landed on `main` via PR #72, producing a real git conflict
in two files. Separately, the coordinator's exception handling has a real but narrow gap
that should close before any live two-machine rehearsal, since that's exactly the
environment most likely to surface an exception type nobody enumerated in advance.

## Verified current behavior

- `git merge-base main origin/codex/demo2-autonomous-event-node` → `504b325` (both
  branches diverged from the same point before PR #72 landed).
- `git merge-tree --write-tree main origin/codex/demo2-autonomous-event-node` reports
  `CONFLICT (content)` in exactly `backend/app/api/v1/demo.py` and
  `backend/app/contexts/production/event_mode_kernel/service.py`. All other files
  (including `backend/tests/test_demo_api.py`, which is byte-identical on both branches)
  merge cleanly.
- Demo 2's `complete_package` in `service.py` omits the explicit revision-mismatch guard
  that main's version has, but both behave identically in practice because the actual
  guard is enforced by `repository.py`'s `complete_session` (`decision.package_revision
  != session.package_revision → KernelConflictError`), which neither branch modified.
  Confirmed by running the test directly against the Demo 2 worktree: it passes.
- `backend/app/demo/autonomous.py`'s `run_media_cycle`/`run_program_refresh` each already
  catch their own anticipated exception types and return early on failure; the gap is one
  level up, in `_run_owned`'s loop, which calls these methods with no enclosing catch-all.

## Desired behavior

`codex/demo2-autonomous-event-node` rebases cleanly onto current `main`, keeping exactly
one copy of the Package Approval implementation (main's, since it is already merged,
tested, and in production) plus Demo 2's unique, unrelated additions in the same files
(`operations_enqueued`, `enqueue_failure_codes`, `WorkExecutionStorageUnavailableError`
handling in `demo.py`; the association-reevaluation logic in `service.py`, which does not
conflict). The coordinator's cycle loop gains a catch-all that logs and marks the cycle
degraded instead of letting an unanticipated exception kill the thread silently.

## In scope

- Rebase (or merge `main` into) `codex/demo2-autonomous-event-node`, resolving the two
  conflicting files by keeping main's `ApprovePackageCommand`/`approve_package`/
  `complete_package`-with-`expected_package_revision` implementation verbatim, and
  retaining Demo 2's unrelated additions in the same files unchanged.
- Add a catch-all `except Exception` in `AutonomousEventNodeCoordinator._run_owned`'s
  per-cycle invocation (wrapping the calls to `run_media_cycle`/`run_program_refresh`,
  not replacing their existing internal exception handling) that logs the exception type
  and cycle context, sets the coordinator status to `degraded` with a bounded failure
  code (e.g. `unexpected_cycle_failure`), and continues the loop rather than letting the
  thread die.
- A test proving: (a) the rebase preserves every existing passing test on both the
  Demo-2-specific suite and the shared `demo.py`/kernel service tests; (b) an injected
  unexpected exception type in a cycle no longer kills the coordinator thread — the
  coordinator survives, reports `degraded`, and continues attempting subsequent cycles.

## Out of scope

- Any change to Package Approval semantics, Session/package authority, or the
  association-reevaluation Yellow-approved extension's scope.
- The coordinator's `stop()` optimistic `owner=False` status nit noted in the same PR #71
  review — cosmetic, not required for this directive; may be folded in opportunistically
  if trivial, but is not a blocking acceptance criterion here.
- Anything from the still-pending live two-machine rehearsal gate — this directive is
  about mergeability and safety-net correctness, not promotion readiness.

## Constraints

- Architecture and terminology constraints: no change to Session, package, or association
  authority semantics.
- Compatibility constraints: PR #71 must remain **draft** after this work — it is still
  gated on the live rehearsal, per its own plan's explicit "must not merge before the live
  promotion gate."

## Implementation approach

1. Rebase `codex/demo2-autonomous-event-node` onto current `main` (or merge `main` into
   it, whichever preserves the branch's own commit history conventions).
2. Resolve the two conflicting files by taking main's side for the Package Approval
   overlap and Demo 2's side for its unique additions in the same files — do not
   hand-merge a third variant.
3. Add the catch-all exception handling to `_run_owned`'s cycle-invocation loop.
4. Add a test that injects an unexpected exception into a cycle and asserts the
   coordinator reports `degraded` and keeps running rather than dying.
5. Run the full backend and frontend suites, Ruff, Pyright, and the Demo-2-specific
   focused suite to confirm nothing regressed from the rebase.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `backend/app/api/v1/demo.py` | Conflict resolved to main's canonical implementation + Demo 2's unique additions |
| `backend/app/contexts/production/event_mode_kernel/service.py` | Conflict resolved to main's canonical implementation + Demo 2's association-reevaluation logic |
| `backend/app/demo/autonomous.py` | Add catch-all exception handling in `_run_owned` |
| `backend/tests/test_demo_autonomous_event_node.py` | Add coordinator-survives-unexpected-exception test |

## Data or migration considerations

None.

## Failure and recovery considerations

The entire point of this directive's second half is a failure/recovery improvement: an
unanticipated exception must degrade the coordinator visibly and let it keep retrying,
not die silently while reporting stale "healthy" status.

## Observability requirements

An unexpected cycle failure must be visible in the coordinator's status projection
(`degraded` state, a bounded failure-reason code) — not just a dead thread with frozen
"running" status.

## Test strategy

- Rebase correctness: full backend + frontend suites, Ruff, Pyright pass identically to
  their pre-rebase state on both `main` and the Demo-2-specific test files.
- New test: inject an exception type not in the existing enumerated catches into a cycle;
  assert the coordinator's `status()` reports `degraded` with a failure code, and that a
  subsequent cycle still attempts to run (thread did not die).

## Acceptance criteria

- [ ] `codex/demo2-autonomous-event-node` merges cleanly against current `main` with no
  conflicts.
- [ ] Exactly one implementation of Package Approval exists post-rebase (main's).
- [ ] All of Demo 2's unique, previously-reviewed functionality (association
  reevaluation, autonomous coordinator, worker/deployment projection, package approval
  integration) is preserved unchanged.
- [ ] An unexpected exception type in a coordinator cycle no longer kills the background
  thread; status reports `degraded` and the coordinator keeps attempting cycles.
- [ ] PR #71 remains in draft status after this work.
- [ ] Full backend/frontend suites, Ruff, Pyright pass.

## Rollback or reversal

Revert the rebase (force-push the branch back to `2280ed0` if needed, with explicit user
authorization given the destructive nature of that action) or simply close and reopen
from a fresh rebase attempt. No data or schema change to reverse.

## Open questions

None blocking.

## Completion record

_(To be filled in by whoever implements this plan.)_
