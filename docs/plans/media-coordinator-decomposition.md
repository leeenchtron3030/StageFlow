# Media candidate collection coordinator decomposition

## Status

Completed

## Execution authority

- Classification: Green autonomous
- Authority evidence: Acquisition-style due-diligence audit (2026-08-20, commit `42e71c2`),
  Major finding "The busiest file in the codebase is unrefactored" — explicitly framed by
  the audit itself as "not deal-blocking... ordinary post-close backlog," deferred from
  [media-coordinator-failure-visibility.md](media-coordinator-failure-visibility.md)
  (ED-0057) by design. Explicit 2026-08-21 user directive to continue structural
  fortification now that the demo timeline allows it.
- Implementation-ready: Yes
- Required escalation or approval, if any: None for the decomposition itself (internal
  structure only, no public contract change). If decomposition reveals a genuine behavior
  question (e.g. two call sites subtly relying on incidental ordering), stop and report
  rather than guessing — do not silently change behavior to make the split easier.

## Related findings or ADRs

- Finding/disposition: Due-diligence audit Major finding —
  `media_candidate_collection_coordinator.py` at 2,072 lines / 43 methods.
- ADR: None required — internal decomposition, not a contract or architecture change. If
  the split reveals the file actually spans more than one coherent responsibility at the
  architecture level (not just length), stop and report rather than deciding a new module
  boundary unilaterally.
- Engineering Directive: ED-0064.

## Problem statement

The file is the hardest module in the codebase to safely change or onboard a new engineer
into. ED-0057 already made its failures visible (logging); this directive addresses the
underlying size/structure problem itself, now that doing so is lower-risk (failures are no
longer silent if something is disturbed during the split) and the demo timeline has more
room than it did during due-diligence remediation week.

## Verified current behavior

- `backend/app/contexts/production/media_collection/media_candidate_collection_coordinator.py`:
  2,072 lines, 43 methods on one class (`MediaCandidateCollectionCoordinator`), per the
  due-diligence audit's line count (reverify exact current count before starting, since
  ED-0057 added lines to this file already).
- Existing test coverage for this file is extensive (the due-diligence audit separately
  confirmed 1,745+ passing backend tests with clean Ruff/Pyright); this is the safety net
  the decomposition leans on.

## Desired behavior

The coordinator's responsibilities are split into cohesive, independently-testable units
(e.g. discovery orchestration, readiness/stability evaluation, association integration,
transcription enqueue, status/observability projection — exact seams to be determined by
reading the actual current method groupings, not prescribed here sight-unseen). External
behavior, the public method(s) other modules call, and every existing test's meaning are
unchanged. This is a structure-only change.

## In scope

- Read the current file in full and identify natural seams by actual responsibility
  (which methods share state/mutate the same fields, which are called from outside the
  class vs. only internally, which form a clear sub-pipeline).
- Extract cohesive groups into separate modules/classes within the same
  `media_collection` package, with the original coordinator composing them rather than
  implementing everything inline.
- Preserve every existing public entry point's signature and behavior exactly — this is
  a refactor, not a redesign.
- Keep the ED-0057 logging calls attached to the same logical operations after the split.
- Run the full existing test suite for this file (and anything that imports it) after
  each incremental extraction, not only at the end — do not do this as one giant
  unreviewable diff.

## Out of scope

- Any behavior, retry policy, timing, or observability change beyond what ED-0057 already
  added — if the decomposition seems to require a behavior change to make the split
  clean, stop and report rather than making it.
- Changing the module's public contract in a way that affects callers outside
  `media_collection` — if such a change seems necessary, that is a Yellow-level
  compatibility question, not something to decide here.
- Any change to Session, media, association, or package authority semantics.
- Renaming or restructuring sibling files in the same package unless directly necessary
  for the split.

## Constraints

- Architecture and terminology constraints: preserve existing domain vocabulary; do not
  introduce new architectural concepts not already present in the codebase.
- Compatibility constraints: zero behavior change is the acceptance bar — a passing test
  suite before and after, with no test modified to accommodate new behavior (tests may be
  moved to new files alongside the code they test, but their assertions should not change).

## Implementation approach

1. Read the full current file and produce a short internal map of method groups by
   responsibility and mutual dependency before writing any code.
2. Extract the most independent/least-coupled group first, as its own module, with the
   coordinator delegating to it. Run the full test suite.
3. Repeat incrementally for each subsequent group, running the full suite after each step.
4. Do not attempt the entire decomposition as a single commit — land it as a reviewable
   sequence, or at minimum keep the working history such that each extraction step is
   independently inspectable even if squashed for the final PR.
5. After decomposition, confirm the original file's remaining size/method count and record
   the before/after numbers in the completion record.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `backend/app/contexts/production/media_collection/media_candidate_collection_coordinator.py` | Reduced to composition/orchestration; logic extracted |
| `backend/app/contexts/production/media_collection/` (new files, exact names TBD by actual seams found) | New cohesive modules extracted from the coordinator |
| Corresponding test files | Moved/reorganized alongside extracted code, assertions unchanged |

## Data or migration considerations

None.

## Failure and recovery considerations

No change to failure/recovery behavior — this directive is structure-only. The ED-0057
logging calls must remain attached to the same logical failure points after extraction.

## Observability requirements

Unchanged from ED-0057 — the same failures must remain visible after the split.

## Test strategy

- Full existing test suite for the coordinator and everything that imports it, run after
  every incremental extraction step, not only at the end.
- No new test assertions are required by this directive (behavior is unchanged), but
  moved/reorganized tests must retain their original assertions.
- Full quality commands: `uv run pytest`, `uv run ruff check .`, `uv run pyright`.

## Acceptance criteria

- [x] The original file's line count and method count are meaningfully reduced (record
  the before/after numbers).
- [x] Every existing test for this module and its callers passes unchanged (no test
  assertion modified to accommodate new behavior).
- [x] No public entry point's signature or behavior changed for callers outside
  `media_collection`.
- [x] ED-0057's logging calls remain attached to the same logical operations post-split.
- [x] Full backend quality commands pass.

## Rollback or reversal

Revert the extraction commits. No data or schema change to reverse; this is pure code
structure.

## Open questions

- Exact extraction seams are intentionally not prescribed here — they depend on reading
  the actual current method groupings, which may have shifted since the due-diligence
  audit's line-count snapshot. If reading the file suggests the 2,072-line count no longer
  matches current `main`, reverify before scoping the split further.

## Completion record

- Implemented in the ED-0063–ED-0066 working tree from main `271f0b7`.
- Verified current baseline was 2,105 lines and 43 coordinator methods, rather than the
  audit snapshot's 2,072 lines. After extraction the public coordinator is 1,496 lines
  and 29 methods: 609 lines (29%) and 14 methods (33%) moved behind internal seams.
- Added `_media_collection_state.py` for immutable coordinator/cycle state and
  deterministic identity/ordering helpers, `_media_collection_plan_validator.py` for
  Runtime/plan/dependency/Agent permission validation and checkpoints, and
  `_media_collection_ports.py` for bounded port invocation, ED-0057 exception visibility,
  and returned-contract normalization.
- The original coordinator still owns the public API, exact cycle ordering,
  candidate/observation merge semantics, conflict retention, replay, and atomic commit.
  No package export or caller signature changed, and no test assertion was modified.
- Incremental verification after extraction: 33 existing media-collection behavior and
  architecture tests passed; scoped Ruff and Pyright passed. Final backend validation:
  1,796 passed, 5 skipped; Ruff passed; Pyright reported 0 errors/0 warnings. One existing
  Starlette/httpx deprecation warning remains.
- No production behavior, dependency, schema, migration, runtime configuration, public
  contract, or external side effect changed. Rollback is deletion of the three internal
  modules plus restoration of the coordinator imports/method bodies.
