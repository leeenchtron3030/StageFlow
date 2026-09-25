# Demo 2 generalization and remaining-criteria rehearsal

## Status

*Status note 2026-09-25:* Completed; PR #71 merged to `main` (`085e01f`, 2026-09-25).
Merge evidence: commit `085e01f`.

Completed (2026-09-25). Implemented on draft PR #71 and rehearsed on the reference host.
ED-0071 criteria 4, 6, and 7 qualified; the PostgreSQL-outage leg was not exercised live.
Merging PR #71 awaits the owner's explicit approval. See
[Run 002](../validation/results/demo2-hardware-rehearsal-002.md) and the completion record.

## Execution authority

- Classification: Green autonomous. The owner resolved the plan's Yellow decisions on
  2026-09-25 (see "Owner decisions" below).
- Authority evidence:
  - [ADR-0031](../adr/ADR-0031-white-label-identity-and-provider-neutral-program-sources.md)
    names "a later directive generalizing Demo 2" and states Demo 2 "must be generalized
    to the port before its remaining rehearsal criteria can be exercised against a
    neutral source".
  - The [ED-0079 plan](provider-neutral-program-source.md) makes its Devcon compatibility
    aliases "removable once the Demo 2 branch no longer calls them".
  - The [ED-0071 plan](demo2-hardware-rehearsal.md) and its
    [Run 001 result](../validation/results/demo2-hardware-rehearsal-001.md) leave
    criteria 4, 6, and 7 not qualified and name "a follow-up run exercising only
    criteria 4, 6, and 7" as the remaining work.
  - The [ED-0063 plan](demo2-rebase-and-coordinator-safety-net.md) defines the safety
    net that criterion 6 must prove live.
- Implementation-ready: Yes.
- Required escalation or approval, if any: merging PR #71 to `main` requires the owner's
  explicit approval after the result is reviewed. Stop and escalate if the merge of `main`
  reveals a semantic conflict beyond the conflicts listed below, if generalization appears
  to require a schema, migration, or dependency change, or if any step would need an
  external provider API.

## Owner decisions (2026-09-25)

1. **Integration: merge `main` into the PR #71 branch.** The branch is not rebased and
   nothing is force-pushed. Conflicts are resolved in favour of `main`'s accepted
   white-label and publication-freeze decisions. The branch followed the same approach on
   2026-08-24.
2. **Promotion: merge after owner review.** If criteria 4, 6, and 7 qualify, Demo 2
   becomes promotion-qualified. The owner reviews the result and explicitly approves the
   merge of PR #71 to `main`.
3. **Rehearsal: this host, replayed blocks.** The rehearsal runs on the reference host
   alone, with no Mac UI. Recorded blocks are copied into the watched folder on a
   cadence, and a local schedule file uses a placeholder identity. No external provider
   API is used (ADR-0031 decision 6).
4. **Criterion 6: fault hook plus database outage.**
   - A rehearsal-only, default-off fault-injection setting proves ED-0063's catch-all
     live.
   - A brief PostgreSQL outage proves the realistic outage path.
   - This decision replaced an initial choice of "media folder unavailable". Review found
     that a missing folder raises an anticipated `OSError`, which `run_media_cycle`
     handles itself without setting `degraded`, so it cannot reach the ED-0063 path.
5. **Degraded recovery: fix it.** After the catch-all sets `degraded`, a later successful
   cycle returns the coordinator to `running`. The last failure code and time stay
   visible.

## Related findings or ADRs

- ADR-0031 (white-label, provider-neutral program sources, publication freeze); ADR-0028
  (Devcon adapter boundary, narrowed); ADR-0025 (worker capability model behind the
  worker projection).
- ED-0063 (coordinator safety net), ED-0071 (Demo 2 hardware rehearsal), ED-0074 (ED-0071
  closure), ED-0079 (provider-neutral program source), ED-0080 (white-label presentation
  and publication freeze).
- Engineering Directive: **ED-0081**. The repository owner delegated ED numbering; ED-0081
  is the next free number after ED-0080.

## Problem statement

Demo 2 is the Autonomous Event Node: a process-owned coordinator that reconciles media
and the Program schedule on its own timers. It lives only on draft PR #71
(`codex/demo2-autonomous-event-node`). It is not promotion-qualified, because ED-0071
criteria 4 (worker projection), 6 (safety net under induced failure), and 7 (restart
reconstruction) were never exercised.

Since the branch diverged on 2026-08-24, `main` has made StageFlow white-label and
provider-neutral. Demo 2 still polls Devcon through compatibility aliases, catches a
Devcon-specific error, ships a Devcon-identity example, and conflicts with `main` in seven
files. It cannot be rehearsed against a neutral source, and `main` cannot drop the
aliases, until Demo 2 is generalized.

## Verified current behavior

Checked on 2026-09-25 against `origin/main` at `f8a3783` and branch head `1433bea`.

**Branch divergence.**

- The branch is 11 commits ahead of `main` and 45 behind; the merge base is `0faf541`
  (2026-08-24). It changes 34 files (+2,731/−128).
- It is checked out in the worktree `C:/Dev/StageFlow/tmp/demo2-worktree`.

**Merge simulation.** `git merge-tree --write-tree origin/main <branch>` reports seven
conflicts:

- `backend/app/bootstrap/event_mode_kernel.py`
- `scripts/demo/StageFlow-Demo.ps1`
- `scripts/demo/README.md`
- `ENGINEERING_DIRECTIVES.md`
- `docs/plans/README.md`
- `docs/plans/demo2-hardware-rehearsal.md`
- `docs/validation/results/demo2-hardware-rehearsal-001.md` (add/add)

The branch's frontend changes auto-merge.

**Provider coupling in the branch's own code.**

- `backend/app/demo/autonomous.py` calls `components.sync_devcon_program()` and catches
  `DevconReadError` in `run_program_refresh`.
- `backend/app/demo/cli.py` and `backend/app/api/v1/demo.py` call
  `devcon_program_sync` / `sync_devcon_program()`.
- `examples/demo2-autonomous-event-node.toml.example` hardcodes `[devcon_read]`,
  `test-devcon-8`, `razer-demo2`, `razer-event-node`, and Devcon external-reference keys.
- The branch still exposes `publish-devcon` in `scripts/demo/StageFlow-Demo.ps1` and its
  README. On `main` that action is frozen under ADR-0031.

**`main`'s neutral surface.**

- `backend/app/bootstrap/event_mode_kernel.py` provides `program_source` and
  `sync_program()`. It keeps `devcon_program_sync` (constructor argument and property) and
  `sync_devcon_program()` as compatibility aliases, commented "Remove this compatibility
  constructor once Demo 2 no longer calls the alias".
- The neutral error is `ProgramSourceUnavailableError` in
  `backend/app/contexts/integration/program_source.py`.
- On `main`, only those definitions and `backend/tests/test_provider_neutral_program_source.py`
  (lines 354-373) use the aliases.

**Result-record collision.**

- On the branch, `docs/validation/results/demo2-hardware-rehearsal-001.md` is the
  2026-08-24 preflight stop. On `main`, the same path holds the 2026-08-26 ED-0071 Run 001
  partial qualification.
- The branch also holds `-002` and `-003` (2026-08-25). Those runs report durable restart
  reconstruction and two guarded Devcon test PUTs. They have never been recorded on
  `main`, and they predate ED-0071's requirement for a fresh rehearsal.

**Coordinator failure semantics** (`autonomous.py` on the branch).

- `_run_owned` wraps each cycle in the ED-0063 catch-all. Any exception that escapes
  `run_media_cycle` or `run_program_refresh` sets `state="degraded"` with
  `unexpected_cycle_failure`, and scheduling continues.
- `run_media_cycle` itself handles storage errors and `OSError`, `RuntimeError`, and
  `ValueError`. It records `postgresql_unavailable` or `media_reconciliation_failed` and
  does not change the state.
- A PostgreSQL connection failure in the outer `_run` loop sets `degraded` with
  `postgresql_unavailable`. It returns to `running` when the advisory lock is
  re-acquired.
- No path returns the state from `degraded` to `running` after the catch-all fires, even
  when later cycles succeed.

**Worker projection and white-label guards.**

- The branch's `backend/app/demo/service.py` projects worker `available`, `capacity`, and
  `gpu_transcription` readiness from durable worker rows.
- `backend/tests/test_white_label_presentation.py` guards
  `examples/demo-single-stage.toml.example`.
- `frontend/src/experience/white-label.test.ts` rejects Devcon, Razer, and similar
  identity strings in operator-facing modules.

## Desired behavior

- Demo 2 runs entirely on the provider-neutral program source.
- It contains no event, organizer, host, or provider identity outside adapters.
- It is current with `main` and keeps `main`'s publication freeze.
- A single-host, offline rehearsal qualifies or honestly fails ED-0071 criteria 4, 6, and
  7.
- With Demo 2 off the aliases, `main`'s Python compatibility aliases are removed.

## In scope

1. **Merge `main` into the branch** and resolve the seven conflicts:
   - Take `main`'s neutral composition in `event_mode_kernel.py`.
   - Take `main`'s frozen `publish-devcon` and neutral readiness output in the launcher
     script and README, keeping Demo 2's unique additions.
   - Take `main`'s executed text for `demo2-hardware-rehearsal.md`.
   - In both indexes, keep `main`'s rows and add the branch-only rows.
2. **Resolve the result collision without rewriting history.**
   - Keep `main`'s `demo2-hardware-rehearsal-001.md` unchanged.
   - Rename the branch's three records to dated names, with their content unchanged:
     `demo2-branch-rehearsal-2026-08-24.md`, `demo2-branch-rehearsal-2026-08-25-a.md`, and
     `demo2-branch-rehearsal-2026-08-25-b.md`.
   - Update links to them, and index them as pre-ED-0071, branch-only records.
3. **Move the Demo 2 code onto the neutral names.**
   - `autonomous.py`, `cli.py`, and `api/v1/demo.py` use `program_source` /
     `sync_program()`.
   - `run_program_refresh` catches `ProgramSourceUnavailableError` in place of
     `DevconReadError`. It keeps the bounded code `provider_refresh_unavailable`.
4. **White-label the example.**
   - Rewrite `examples/demo2-autonomous-event-node.toml.example` to use `[local_schedule]`
     with a matching placeholder local schedule, the placeholder identities used by
     `main`'s examples, and neutral external-reference keys.
   - Extend the white-label guard test to cover it.
5. **Degraded recovery.**
   - A successful media or program cycle after a catch-all failure returns the state from
     `degraded` to `running`.
   - The last failure code and time remain visible until the next failure of that cycle
     kind.
   - Outer-loop database recovery is unchanged.
6. **Rehearsal-only fault injection.**
   - A new setting in `[autonomous_event_node]` (for example,
     `rehearsal_fault_media_cycle`) is unset by default.
   - The configuration rejects it unless `event_mode = "rehearsal"`.
   - It names one media cycle number (for example, `rehearsal_fault_media_cycle = 6`).
     That cycle, and only that cycle, raises an exception type outside the anticipated
     handled set, reaching the ED-0063 catch-all. No new API or trigger endpoint is
     added.
   - Unit tests cover the default-off state, rejection outside rehearsal, one-shot
     behaviour, the resulting `degraded` state and code, and recovery.
7. **Remove `main`'s aliases.**
   - Delete the `devcon_program_sync` constructor argument and property and
     `sync_devcon_program()` from `KernelComponents`.
   - Remove or convert their tests.
   - Keep `[devcon_read]` configuration acceptance, which ADR-0031 keeps during the
     transition.
8. **Qualification tooling.** A small block-replay helper copies a supplied folder's
   recorded blocks into the watched folder at a fixed cadence. It lives in
   `backend/tests/qualification/` or `scripts/validation/`, outside production code, and
   has focused tests.
9. **Rehearsal on this host.** The owner runs it, covering criteria 4, 6, and 7 only, and
   records the sanitized result as
   `docs/validation/results/demo2-hardware-rehearsal-002.md` (ED-0071 follow-up Run 002).
10. **Documentation.** Update the ED-0081 rows, this plan's completion record, the ED-0063
    and ED-0071 status rows and plan statuses (reflecting the outcome), and the
    architecture text wherever it describes Demo 2's program source or coordinator
    status.

## Out of scope

- Merging PR #71 to `main`. That requires the owner's separate approval after review.
- Re-rehearsing ED-0071 criteria 1-3, 5, or 8-10, and any Mac UI or live vMix step.
- Any external provider API call. Any change to publication or Devcon PUT behaviour;
  publication stays frozen.
- Removing the Devcon adapter or `[devcon_read]` configuration acceptance. Changing
  migration `0009`.
- Schema, migration, or dependency changes. Changes to association, Session, package, or
  lifecycle semantics.
- Promoting the coordinator from the Demo application into a product capability or
  renaming the "Demo" surfaces. That is a separate product decision.

## Constraints

- **Architecture and terminology:** the coordinator stays a process-owned background loop
  over existing synchronous domain calls. No broker or event hop. Provider names appear
  only inside adapters.
- **Compatibility:** existing external configuration with `[devcon_read]` keeps loading.
  Removing the Python aliases is internal; no public API field or storage changes.
- **Offline/event mode:** the rehearsal and all tests run without Internet access. Fault
  injection cannot be enabled outside `event_mode = "rehearsal"`.
- **Security and data handling:**
  - No real recordings, transcripts, or media paths enter Git.
  - The replay corpus stays outside the repository and is supplied only in the
    directive.
  - Placeholder identities only.
  - The fault setting grants no new external capability.

## Implementation approach

1. **Owner:** release the branch from `tmp/demo2-worktree` and check it out in the Codex
   worktree. Start `git merge origin/main` and leave the conflicts in the working tree,
   because the sandbox cannot write Git metadata.
2. **Codex:** resolve the conflicts and complete in-scope items 2-8 as working-tree
   changes, with focused tests.
3. **Owner:** review with the `directive-reviewer` agent, then run host validation (the
   full backend suite, frontend build, lint, typecheck, and tests). Conclude the merge
   commit, commit the generalization separately, and push. Nothing is force-pushed.
4. **Owner:** run the single-host rehearsal:
   - Start the launcher-owned stack with the white-labelled Demo 2 configuration, a local
     schedule, `event_mode = "rehearsal"`, and the autonomous node enabled.
   - Replay recorded blocks into the watched folder.
   - **Criterion 4:** observe the worker projection's availability, capacity, and GPU
     readiness. Stop and restart the transcription worker, and confirm the projection
     follows.
   - **Criterion 6:** let the configured fault cycle fire once and observe `degraded` with
     `unexpected_cycle_failure`, continued cycles, and recovery to `running`. Stop
     PostgreSQL for at least two cycles and observe `degraded` with
     `postgresql_unavailable`, then recovery.
   - **Criterion 7:** stop and restart the launcher-owned stack. Confirm that coordinator
     ownership, Session, media, and package state, and the worker projection are
     reconstructed from durable state.
5. **Owner:** write `demo2-hardware-rehearsal-002.md` and update the status rows. Open or
   refresh PR #71 for review, and ask before merging.

Each step is independently reviewable. The merge commit and the generalization commit are
separate, so either can be reverted.

## Files or modules expected to change

On the branch unless marked `main`; all changes reach `main` only through PR #71.

| Path or module | Expected change |
| --- | --- |
| The seven conflicted files listed above | Merge resolution |
| `backend/app/demo/autonomous.py` | Neutral source and error; degraded recovery; one-shot fault hook |
| `backend/app/demo/cli.py`, `backend/app/api/v1/demo.py` | Neutral names |
| `backend/app/core/config/deployment.py` | Rehearsal-only fault setting and validation |
| `backend/app/bootstrap/event_mode_kernel.py` | Merge resolution; alias removal |
| `backend/tests/test_demo_autonomous_event_node.py` | Neutral source, recovery, and fault-hook tests |
| `backend/tests/test_provider_neutral_program_source.py` | Alias tests removed or converted |
| `backend/tests/test_white_label_presentation.py` | Guard extended to the Demo 2 example |
| `examples/demo2-autonomous-event-node.toml.example` and a matching local schedule example | White-labelled |
| `backend/tests/qualification/` or `scripts/validation/` | Block-replay helper and tests |
| `docs/validation/results/demo2-branch-rehearsal-*.md` | Renamed branch records, content unchanged |
| `docs/validation/results/demo2-hardware-rehearsal-002.md`, `docs/validation/README.md` | New result and index |
| `ENGINEERING_DIRECTIVES.md`, `docs/plans/README.md`, related plans and architecture text | Status and description updates |

## Data or migration considerations

None, verified by the merge simulation and the branch diff: there is no migration, schema,
or stored-format change. Rehearsal data goes to the rehearsal database under the existing
launcher's ownership, and only rehearsal-owned rows are cleaned up.

## Failure and recovery considerations

- The merge is committed separately from the generalization. If review rejects it, the
  branch can be reset to `1433bea` locally before push; after push, the merge is reverted
  without rewriting history.
- The fault hook is one-shot and rehearsal-only, so it cannot cause repeated failures.
  Configuration validation rejects it outside rehearsal mode.
- The degraded-recovery change touches only the coordinator's reported state. It does not
  change retry cadence or domain operations.
- The PostgreSQL outage is bounded and performed only on the local rehearsal instance.

## Observability requirements

Operators must be able to see:

- the coordinator's state (`running`, `degraded`, or `standby`);
- the last failure code and time for each cycle kind;
- cycle counts that keep advancing through and after a failure;
- the worker projection's availability, capacity, and GPU readiness;
- after restart, the ownership and state reconstructed from durable rows.

Logs keep the existing bounded `autonomous_event_node_cycle_failed` line with its cycle
kind and exception type. No media path or transcript text appears in logs or results.

## Test strategy

- Focused backend tests for:
  - neutral-source calls;
  - `ProgramSourceUnavailableError` mapping;
  - degraded recovery for both cycle kinds;
  - the fault hook's default-off state, rehearsal-only validation, and one-shot trigger;
  - alias removal;
  - the white-label guard on the Demo 2 example;
  - the replay helper.
- The existing Demo 2 autonomous, demo API, rehearsal-controller, and white-label test
  suites.
- Host checks: `uv run --no-sync pytest`, `ruff check .`, and `pyright`; in the frontend,
  `npm run build`, `npm run lint`, `npm run typecheck`, and `npm run test`;
  `git diff --check`.
- The live single-host rehearsal for criteria 4, 6, and 7.

## Acceptance criteria

- [x] `main` is merged into PR #71's branch without a force push; the seven conflicts are
  resolved in favor of `main`'s white-label and publication-freeze decisions.
- [x] `main`'s `demo2-hardware-rehearsal-001.md` is unchanged. The three branch records
  appear under dated names with unchanged content and working links.
- [x] Demo 2 code uses `program_source` / `sync_program()` and
  `ProgramSourceUnavailableError`. No Demo 2 code path references the Devcon aliases or
  Devcon errors.
- [x] The Demo 2 example uses a local schedule and placeholder identities, and the
  white-label guard covers it.
- [x] After a catch-all failure, a successful cycle returns the coordinator to `running`,
  with the last failure code and time still visible. This is tested.
- [x] The fault hook is default-off, rejected outside rehearsal mode, and one-shot. This
  is tested.
- [x] `main`'s Python Devcon aliases are removed, and `[devcon_read]` configuration still
  loads.
- [x] The full backend and frontend checks pass on the host, apart from documented
  pre-existing failures.
- [x] Criterion 4: the worker projection autonomously reflects real GPU readiness,
  capacity, and availability, including a worker stop and restart.
- [x] Criterion 6: the fault hook produces `degraded` with `unexpected_cycle_failure`,
  cycles continue, and the state recovers.
- [ ] *Not exercised live (owner skipped; needs an elevated shell):* a PostgreSQL outage
  produces `degraded` with `postgresql_unavailable`, and the state recovers. Covered by a
  unit test only.
- [x] Criterion 7: a restart of the launcher-owned stack reconstructs coordinator
  ownership, Session, media, and package state, and the worker projection from durable
  state.
- [x] `demo2-hardware-rehearsal-002.md` records each criterion honestly as qualified or
  not. It states that the run was single-host and offline, and that it is not Event
  certification.
- [x] No schema, migration, dependency, publication, or association-semantic change. No
  external provider API was called.
- [x] PR #71 is not merged without the owner's explicit approval.

## Rollback or reversal

- **Code:** revert the generalization commit, the merge commit, or both on the branch.
  None of it reaches `main` until PR #71 merges.
- **Alias removal:** reversible by revert.
- **Configuration:** the fault setting is default-off, so older configurations are
  unaffected.
- **Rehearsal:** stop only launcher-owned processes, and remove only rehearsal-owned rows
  and non-customer artifacts.
- **Irreversible steps:** none. No external writes occur.

## Open questions

- None blocking. The coordinator's long-term home, outside the Demo application and its
  "Demo" naming, is a separate product decision and not part of this plan.

## Completion record

- **Implemented revision:** PR #71 branch `codex/demo2-autonomous-event-node`. Commits:
  - merge commit `9d63290`, with parents `1433bea` (branch) and `34a804e` (`main`);
  - launcher fixes `f48087f` and `4a0ec4f` (the second rewords a header comment that
    broke the launcher contract test in Linux CI);
  - the result and status commit that records this completion.

  Nothing was force-pushed.
- **Files and migrations actually changed:**
  - The 7 conflicts were resolved in favour of `main`.
  - `backend/app/demo/autonomous.py`: neutral source and error, per-kind degraded
    recovery under the state lock, and the one-shot `rehearsal_fault_media_cycle`.
  - `backend/app/core/config/deployment.py`: the rehearsal-only validation.
  - `backend/app/bootstrap/event_mode_kernel.py`: the aliases were removed.
  - The white-labelled Demo 2 example and its guard; `backend/tests/qualification/block_replay.py`
    and its tests; Demo 2, provider-neutral, and white-label tests; the frontend recovery
    projection.
  - The PowerShell 7.3 launcher requirement: `scripts/demo/Start-StageFlowDemo.ps1`,
    `scripts/demo/README.md`, and a test.
  - The three branch rehearsal records were moved byte-identical to
    `demo2-branch-rehearsal-*`; `main`'s Run 001 is unchanged.
  - Documentation: the result, indexes, and architecture and glossary wording.
  - No repository migration was added. On the local Demo database, `main`'s accepted
    migrations `0011`-`0013` were applied in place after a verified full backup, by owner
    decision. The ledger gained 3 rows, 13 empty tables were created, and all 33,211
    existing data rows were preserved.
- **Commands and tests actually run:**
  - Codex, in the sandbox: focused suites, Ruff, Pyright, frontend typecheck and lint.
  - Independent `directive-reviewer`: ESCALATE (ED-0072 numbering) plus three Green fixes.
    After the owner's decision and the fixes, it re-reviewed and returned APPROVE.
  - Host, on the committed merge: `uv run --no-sync pytest`, 2,117 passed, 4 failed,
    2 skipped. The 4 failures are the known Windows console-encoding cases in
    `test_validation_controller.py`. Frontend `npm run test` 60/60, `build`, `lint`, and
    `typecheck` passed.
  - After the launcher fix: the controller-script and white-label suites passed. The new
    PowerShell test fails without the guard.
  - The rehearsal is recorded in [Run 002](../validation/results/demo2-hardware-rehearsal-002.md).
- **Results and warnings:** criteria 4, 6, and 7 qualified; Demo 2 is promotion-qualified.
  Warnings:
  - legacy `devcon_*` field names remain in the preflight and status output;
  - `status` mixes time zones;
  - stale fault kinds survive outer-loop recovery by design.
- **Execution authority used:** Green, with the owner decisions recorded above, plus the
  owner's 2026-09-25 decisions to:
  - apply migrations in place;
  - install PowerShell 7 with winget;
  - skip the PostgreSQL outage.
- **Approved deviations:**
  1. The merge resolution and the generalization overlap in the same files, so they landed
     as one merge commit rather than two.
  2. The worker was stopped through a full launcher stop, because the launcher treats any
     child exit as fatal.
  3. The PostgreSQL-outage leg of criterion 6 was not exercised live.
  4. The fault setting stayed enabled across the criterion 7 restart. It fired again after
     the reconstruction checks; that let the 1-second poller capture `degraded` live, and
     it did not affect durable state.
  5. The launcher PowerShell requirement (`f48087f`) is a directly blocking Green
     correction outside the listed files.
  6. **Branch-local ED-0072 numbering.** On the branch, "ED-0072" named the Demo 2 Database
     Compatibility Upgrade and Write-Bearing Rehearsal, which collides with `main`'s ED-0072
     (Editorial Review Foundation). The ED-number owner decided not to assign a new number.
     The historical plan carries a dated note, and the index references read "branch-local
     ED-0072 (superseded numbering; see ED-0081)". `main`'s ED-0072 row is unchanged.
- **Rollback status:**
  - Nothing is merged to `main`.
  - The Demo database can be restored from the pre-ED-0081 backup, or reversed with the
    `0013`-`0011` reverse scripts.
  - PowerShell 7 can be removed with `winget uninstall Microsoft.PowerShell`.
- **Remaining work:**
  - the owner's review and explicit approval to merge PR #71;
  - optionally, a live PostgreSQL-outage exercise;
  - a later white-label alias for the legacy `devcon_*` status field names.
