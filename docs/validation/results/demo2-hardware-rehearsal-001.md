# Demo 2 hardware rehearsal 001 - 2026-08-24

## Result

**UNQUALIFIED - guarded preflight stopped on preserved Demo database schema
drift. Demo 2 is not promotion-qualified.**

The rehearsal used current main at 0faf541 and a local-only rebase of
codex/demo2-autonomous-event-node at c0d7504. The rebase retained main's
merged capabilities and Demo 2's unique coordinator changes. A clean
git merge-tree --write-tree origin/main HEAD simulation produced tree
822e303ef9e033077191ba8f9660994e4ade5cc6.

PR #71 remained open, draft, unmerged, and at remote head 9c176d4. The
local rewritten history was not force-pushed, as required by ED-0071.

## Gate results

| Gate | Result | Evidence |
| --- | --- | --- |
| Local branch rebase and merge simulation | **PASS** | Local rebase completed; merge-tree simulation was conflict-free. |
| PR #71 remains draft and unmerged | **PASS** | GitHub reported OPEN, isDraft true, remote head 9c176d4; no push or merge occurred. |
| Qualified Demo 1 configuration reuse | **PASS (selection only)** | The controller ambiguity was resolved by the qualified non-secret deployment identity. An ephemeral copy added only the enabled 5-second media and 120-second Program reconciliation settings; the qualified source config was unchanged. |
| Exact Demo database identity | **PASS** | The guarded controller's read-only exact-stageflow_demo verification completed before preflight composition. |
| Current-main database readiness | **FAIL / STOP** | Composition returned the bounded code editorial_schema_migration_required. The preserved Demo database has the Demo 1 migration baseline but not current main's already-merged 0010_editorial_candidate_moment requirement. |
| GPU/CUDA inference diagnosis | **UNQUALIFIED** | An NVIDIA command was available, but guarded preflight stopped before the required real silent-audio CUDA inference. Availability is not inference evidence. |
| Devcon GET and autonomous Program reconciliation | **UNQUALIFIED** | The controller stopped before Devcon preflight and before stack startup. No PUT was attempted. |
| Razer stack, loopback backend/PostgreSQL, LAN UI, and Mac reachability | **UNQUALIFIED** | The stack was not started after the mandatory schema gate failed. |
| Autonomous vMix media progression | **UNQUALIFIED** | vMix was not running during prerequisite inventory and no recording run began. No manual cycle was substituted. |
| Automatic CUDA transcription | **UNQUALIFIED** | No rehearsal media Operation was created or executed. |
| Autonomous worker/deployment projection | **UNQUALIFIED** | No live coordinator/worker stack ran. |
| Mac-UI exact-revision Package Approval | **UNQUALIFIED** | No live Session/package revision was created; no API substitute was used. |
| ED-0063 induced-failure safety net | **UNQUALIFIED** | No live coordinator cycle ran, so no fault was induced. |
| Restart and durable reconstruction | **UNQUALIFIED** | No launcher-owned stack was started; a synthetic restart was not substituted. |

## Stop rationale

ED-0071 authorizes no schema or migration change and requires execution to stop when
the qualified database/schema differs. Applying migration
0010_editorial_candidate_moment, provisioning another database, bypassing the
schema check, or disabling current-main Editorial composition would all exceed this
rehearsal's authority. No such action was taken.

This is an environment-compatibility failure at the mandatory preflight boundary, not
evidence that the autonomous coordinator, CUDA path, Mac workflow, ED-0063 safety net,
or reconstruction behavior failed live. Those items remain unqualified.

## Commands and validation

- git fetch --prune origin; GitHub PR inspection; remote-ref inspection.
- git rebase origin/main in the existing Demo 2 worktree, with main-canonical
  conflict resolution in Kernel status/bootstrap composition.
- git merge-tree --write-tree origin/main HEAD and git diff --check
  origin/main...HEAD.
- Focused backend validation: 27 tests passed with one existing
  Starlette/httpx deprecation warning.
- Scoped Ruff passed; scoped Pyright reported zero errors and warnings.
- The first focused pytest command named one nonexistent test file and consequently ran
  no tests; the corrected command produced the 27-test result above.
- Guarded StageFlow-Demo.ps1 diagnose: first attempt failed closed on two
  unqualified TOML candidates; the explicit qualified Demo 1-derived attempt passed
  database identity verification and then stopped with
  editorial_schema_migration_required.

No backend/frontend stack, vMix recording, authority command, Devcon write, schema
change, migration, dependency change, production deployment, or cleanup of durable
Demo state occurred.

## Promotion disposition

**Demo 2 remains not promotion-qualified.** A separately authorized and
migration-planned upgrade of the preserved Demo database (or another explicitly
approved compatible rehearsal database decision) is required before ED-0071 can be
rerun. That follow-up must still preserve PR #71 as draft and unmerged unless the user
separately decides otherwise.
