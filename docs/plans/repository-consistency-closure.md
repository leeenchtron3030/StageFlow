# Repository consistency closure — ED-0063 through ED-0069 status reconciliation

## Status

Completed

## Execution authority

- Classification: Green autonomous
- Authority evidence: 2026-08-22 external review by the user's ChatGPT "Virtual Technical
  Producer" agent (an outside-review/alignment collaborator on this project, alongside
  Codex and Claude) audited the ED-0063 through ED-0067 cycle and found the architecture
  on-path, with one process defect already self-corrected by Codex on PR #79 (ED-0067's
  plan wrongly claimed no Editorial package/migration/command existed; implementation
  discovered and preserved the existing Demo 1 slice instead of duplicating it). Direct
  inspection of the live repository during this directive's own drafting (`git`, `gh`)
  found several further, previously unflagged consistency gaps of the same class,
  enumerated below. Explicit 2026-08-22 user directive to close this round with a
  "targeted governance correction, not a redesign."
- Implementation-ready: Yes
- Required escalation or approval, if any: None for the reconciliation and PR-hygiene
  items below — each has only one correct answer and changes no product behavior. The
  merge of PR #79 additionally requires the fresh independent review named in scope
  below before that merge happens; this directive authorizes requesting that review, not
  the review outcome itself.

## Related findings or ADRs

- Finding/disposition: ChatGPT "Virtual Technical Producer" review (2026-08-22) of the
  ED-0063–ED-0067 cycle; PR #79's own body ("Important correction to my own plan:
  ED-0067's plan claimed no editorial/moment system existed. That was wrong...").
- Finding/disposition (found while drafting this directive, verified directly against
  the live repository rather than the review transcript — see [[project memory:
  cross-agent repo grounding]]):
  - PR #76 (`codex/coordinator-decomposition-adr-sbom`, implements ED-0064 through
    ED-0066) is `CONFLICTING` against current `main`, two commits behind
    (`git log origin/main..origin/codex/coordinator-decomposition-adr-sbom` shows 1
    commit ahead; `origin/codex/coordinator-decomposition-adr-sbom..origin/main` shows 2
    commits it lacks). It has sat unmerged since before PR #77/#78 landed.
  - `docs/plans/demo2-rebase-and-coordinator-safety-net.md` (ED-0063) and
    `docs/plans/media-coordinator-decomposition.md` (ED-0064) both still say `Status:
    Approved` and `## Completion record` → `_(To be filled in by whoever implements this
    plan.)_`, even though ED-0063's implementation (commit `9c176d4`, "Implement ED-0063
    coordinator safety net") is already pushed to PR #71, and ED-0064's implementation is
    already on PR #76. This is the same "plan says not done, repository says otherwise"
    gap the ChatGPT review caught on ED-0067, just not yet caught on these two.
  - ED-0069 ("Frontend dependency security remediation": `npm audit fix`, no `--force`,
    reconciling the `@emnapi/*` lockfile mismatch ED-0066 flagged) exists only as a local
    commit (`cbd1f66`) on an unpushed/no-PR branch — not on `main`, not reviewable.
  - PR #78 (adds the ED-0068 directive text) is `MERGEABLE` and has been sitting open
    without action.
  - PR #79 (ED-0067 implementation) is `MERGEABLE`, both CI checks (`Backend / Python
    3.13`, `Frontend / Node 22`) are `SUCCESS`, and its own plan/directive-table
    self-correction is already complete — it does not need the plan/directive rewrite a
    naively-followed version of the ChatGPT review would have re-done.
  - PR #71 (`codex/demo2-autonomous-event-node`) already contains the ED-0063 rebase
    (`9c176d4` is reachable from `origin/codex/demo2-autonomous-event-node`) and correctly
    remains `DRAFT`, gated on the still-pending two-machine live rehearsal — unchanged by
    this directive.
- ADR: None required — no architecture decision is made by this directive.
- Engineering Directive: ED-0070.

## Problem statement

Multiple already-approved directives (ED-0063, ED-0064, ED-0069) have real, finished or
near-finished implementation work sitting in unmerged or unopened PRs, and two plan
documents currently misstate their own completion status relative to what's actually on
those branches. Left alone, this is exactly the failure mode the 2026-08-22 review
flagged on ED-0067: a future agent reading `ENGINEERING_DIRECTIVES.md` or a plan's Status
field would draw a wrong conclusion about what StageFlow has actually built, and might
redo already-finished work or build on a stale assumption. The repository, not any
agent's conversation history, is supposed to be the durable source of truth; this
directive brings the durable artifacts back in sync with reality before more work stacks
on top of the drift.

## Verified current behavior

- `gh pr view 76` → `state: OPEN`, `mergeable: CONFLICTING`.
- `gh pr view 78` → `state: OPEN`, `mergeable: MERGEABLE`.
- `gh pr view 79` → `state: OPEN`, `mergeable: MERGEABLE`, both quality-matrix checks
  `SUCCESS`.
- `gh pr view 71` → `state: OPEN`, `isDraft: true`; `git branch -r --contains 9c176d4`
  includes `origin/codex/demo2-autonomous-event-node`.
- `git merge-base --is-ancestor cbd1f66 main` → not an ancestor (ED-0069's commit is not
  on `main`); no open PR exists for it (`gh pr list --search
  "head:docs/ed-0069-frontend-dependency-security"` → empty).
- `docs/plans/demo2-rebase-and-coordinator-safety-net.md` and
  `docs/plans/media-coordinator-decomposition.md`: `Status: Approved`, unfilled
  Completion record, as quoted above.
- `ENGINEERING_DIRECTIVES.md` currently lists ED-0063 through ED-0067; no ED-0068 or
  ED-0069 row exists on `main` yet (both are approved only on their own unmerged
  branches).

## Desired behavior

- PR #76 merges cleanly against current `main`.
- ED-0063 and ED-0064's plan documents accurately reflect Completed status with real
  completion records once their implementing PRs (#71, #76) are merged.
- ED-0069 exists as an open, reviewable PR instead of an orphaned local commit.
- PR #78 (ED-0068 directive) is merged so the directive index on `main` is current.
- PR #79 (ED-0067) receives the one fresh independent review the 2026-08-22 alignment
  memo calls for, focused on migration/replay/boundary-reconciliation semantics and
  Demo-API compatibility, then merges — no further plan/directive rewriting needed on it.
- The duplicate `/demo/moments/mark` vs `/editorial/moments/mark` API surface and the
  PyAV/faster-whisper GPL-2.0 exposure remain explicitly tracked, open decisions — this
  directive records them, it does not resolve them.

## In scope

- Rebase `codex/coordinator-decomposition-adr-sbom` (PR #76) onto current `main`,
  resolving the conflict by keeping every already-merged `ENGINEERING_DIRECTIVES.md` row
  from `main` plus PR #76's own ED-0064/ED-0065/ED-0066 row and files, in the same
  "main's already-merged side is canonical, keep the other branch's unique additions"
  pattern ED-0063 already established — no hand-merged third variant, no behavior change.
- Push and open a pull request for the existing `docs/ed-0069-frontend-dependency-security`
  branch (commit `cbd1f66`) as-is, so ED-0069 becomes reviewable.
- Merge PR #78 (ED-0068 directive text) — it is already mergeable and adds no
  implementation, only the approved directive row.
- Once PR #71 and the rebased PR #76 are merged, update
  `docs/plans/demo2-rebase-and-coordinator-safety-net.md` and
  `docs/plans/media-coordinator-decomposition.md`: Status → `Completed`, and a real
  Completion record (implemented revision, files/migrations actually changed, commands
  and tests actually run, results) in the same format ED-0067's plan now uses.
- Request the fresh independent review of PR #79 named in the 2026-08-22 alignment memo
  (migration/replay/boundary-reconciliation semantics, Demo-API compatibility) before it
  merges; merge once that review and the existing green CI both hold.
- Add an ED-0070 row to `ENGINEERING_DIRECTIVES.md` and this plan's row to
  `docs/plans/README.md`'s index.

## Out of scope

- Deciding which of `/demo/moments/mark` / `/editorial/moments/mark` becomes canonical,
  or retiring either — record as an open item (below), decide later.
- Deciding the PyAV/faster-whisper GPL-2.0 remediation (custom LGPL-only FFmpeg build vs.
  accept pending counsel) — remains pending counsel per
  `docs/security/dependency-license-sbom-2026-08-21.md`; unchanged by this directive.
- Promoting PR #71 out of draft or past the two-machine live-rehearsal gate.
- Re-doing any correction PR #79 already made to the ED-0067 plan or directive-table
  language — it is already accurate; do not touch it beyond the merge itself.
- Any code behavior change beyond the mechanical conflict resolution in PR #76's rebase.

## Constraints

- Architecture and terminology constraints: none of this directive's actions change
  Session, Editorial, Kernel, or any other bounded-context authority.
- Compatibility constraints: PR #71 must remain in draft after this work, unchanged from
  its existing gate.

## Implementation approach

1. Rebase `codex/coordinator-decomposition-adr-sbom` onto current `main`; resolve the
   `ENGINEERING_DIRECTIVES.md` conflict (and any other conflicting file) by keeping both
   sides' additions rather than dropping either.
2. Push the rebased branch with `--force-with-lease` (not a blind `--force`); confirm CI
   is green; merge PR #76.
3. Push `docs/ed-0069-frontend-dependency-security` and open a PR against `main`.
4. Merge PR #78.
5. After #71 and the rebased #76 are merged, fill in the ED-0063 and ED-0064 plans'
   Status and Completion record sections from each PR's actual merged diff and test run.
6. Request a fresh independent review of PR #79 per the scope above; merge once it passes.
7. Confirm `ENGINEERING_DIRECTIVES.md` and `docs/plans/README.md` are internally
   consistent with `main` after every merge above (no stale "Approved"-but-actually-merged
   status left behind).

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `ENGINEERING_DIRECTIVES.md` | Add ED-0070 row; no other content change (ED-0068/ED-0069 rows arrive via their own PRs #78 and the newly-opened ED-0069 PR) |
| `docs/plans/repository-consistency-closure.md` | This plan (new) |
| `docs/plans/README.md` | Add this plan's index row |
| `docs/plans/demo2-rebase-and-coordinator-safety-net.md` | Status → Completed, real completion record, once PR #71 merges |
| `docs/plans/media-coordinator-decomposition.md` | Status → Completed, real completion record, once PR #76 merges |
| `codex/coordinator-decomposition-adr-sbom` branch (PR #76) | Rebased onto current `main`, conflict resolved |
| `docs/ed-0069-frontend-dependency-security` branch | Pushed; PR opened |

## Data or migration considerations

None — no schema or migration touched by this directive.

## Failure and recovery considerations

The rebase in scope item 1 is reversible (the pre-rebase branch tip remains reachable by
its commit SHA until garbage-collected); use `--force-with-lease` specifically so a
concurrent push to the same branch is never silently overwritten.

## Observability requirements

Not applicable — process/documentation closure only.

## Test strategy

- After the PR #76 rebase: full backend and frontend suites, Ruff, Pyright — same bar
  every prior ED in this cycle used, to confirm the conflict resolution introduced no
  behavior change.
- `git diff --check` on every documentation edit.
- Manual cross-read: after all merges, confirm no plan or directive row contradicts
  current `main`.

## Acceptance criteria

- [x] PR #76 merges cleanly against current `main` with all CI green.
- [x] `docs/ed-0069-frontend-dependency-security` has an open, reviewable PR.
- [x] PR #78 is merged.
- [x] ED-0064's plan document says `Completed` with an accurate completion record
  (already filled in by PR #76's own commit; verified unchanged by this closure). ED-0063's
  plan document is updated to reflect its actual state (implementation complete and
  pushed to PR #71's remote head) rather than claiming full completion, since PR #71
  itself intentionally remains unmerged pending the live-rehearsal gate.
- [x] PR #79 has received one fresh independent review focused on
  migration/replay/boundary-reconciliation semantics and Demo-API compatibility, and is
  merged.
- [x] The `/demo` vs `/editorial` moments API-surface question and the PyAV/FFmpeg GPL
  question are each recorded as an explicit open item somewhere durable (this plan's Open
  questions section qualifies), not silently dropped.
- [x] PR #71 remains in draft, unchanged by this directive.
- [x] No plan or directive-table status on `main` contradicts what's actually merged.

## Rollback or reversal

Each action is independently reversible: revert a documentation-only edit directly; the
PR #76 rebase can be reverted via `--force-with-lease` back to its pre-rebase tip SHA
(recorded in the PR's own history) with explicit user authorization, given the
destructive nature of that action. No data or schema effect to reverse.

## Open questions

- `/demo/moments/mark` vs `/editorial/moments/mark`: both are backed by the same service;
  PR #79 flags this as worth a future canonical-route decision. Not resolved here —
  flagged for a later directive.
- PyAV/faster-whisper GPL-2.0 exposure: remediation option (custom LGPL-only FFmpeg build
  vs. accept pending counsel) remains an explicit, unresolved release/distribution gate
  per `docs/security/dependency-license-sbom-2026-08-21.md`. Not resolved here.
- Who performs the fresh independent review of PR #79 is a human assignment decision, not
  made by this directive.

## Completion record

- **PR #78** (ED-0068 directive text) merged as-is: commit `79444c3`.
- **PR #80** opened for the previously-orphaned `docs/ed-0069-frontend-dependency-security`
  branch (commit `cbd1f66`, unchanged) and merged: commit `1d41228`.
- **PR #76** (ED-0064–ED-0066) rebased from `c4120fe` onto current `main`
  (`79444c3`, then again onto `1d41228` after PR #80 landed) with `--force-with-lease`,
  resolving the `ENGINEERING_DIRECTIVES.md`/`docs/plans/README.md` conflicts by keeping
  every already-merged row from `main` plus PR #76's own ED-0064/ED-0065/ED-0066 rows and
  files — no hand-merged third variant, no behavior change. Rebased head `c89334b`; full
  backend suite, Ruff, and Pyright passed (the same 4
  `test_validation_controller.py::test_turnover_boundaries_emit_exact_live_operation_checkpoints`
  failures present on unmodified `main` are a pre-existing local Windows
  PowerShell console-encoding artifact — em dash mangled to `�` — unrelated to this
  rebase; GitHub's Linux CI passed both required checks). Merged: commit `ccbe406`.
- **PR #79** (ED-0067 implementation, two commits: the implementation itself plus the
  independent consistency-closure review already completed and pushed by the prior
  session) rebased from `4b59f60`'s predecessor onto current `main` (`1d41228`, then again
  after PR #76 landed) with `--force-with-lease`, resolving conflicts in
  `ENGINEERING_DIRECTIVES.md`, `docs/plans/README.md`,
  `docs/architecture/system-context.md`, and `docs/plans/demo2-rebase-and-coordinator-safety-net.md`.
  Where the review commit's own content was more accurate than the plain placeholder it
  was rebased over (ED-0063's real state: implementation complete and pushed to PR #71's
  remote head, gated only on the live rehearsal, not on merge), the review's verified
  content was kept rather than reverted. `docs/architecture/system-context.md`'s Devcon
  and Editorial additions were combined rather than one replacing the other, since both
  are real, independently-merged capabilities. Rebased head `4b59f60`; full backend
  suite, Ruff, Pyright, and the ED-0067-focused suite
  (`test_editorial_candidate_moment_phase1.py`, `test_demo_api.py`,
  `test_api_authentication.py`, `test_kernel_composition_and_status.py`, 29 passed)
  reran clean; same 4 pre-existing Windows-only failures noted above, no new failures.
  Merged: commit `76888e7`.
- **This ED-0070 branch** was itself first created from the wrong base (PR #79's
  unmerged tip rather than `main`) in the interrupted prior session; that misbased local
  branch was deleted and this directive completed from the correctly-based worktree
  branch instead.
- **Deferred by design, not overlooked:** ED-0063's plan/directive-table status still
  reads "implementation complete on draft PR; live promotion gate pending" rather than
  `Completed`, because PR #71 itself intentionally remains unmerged (two-machine live
  rehearsal gate) — updating that plan's Status field to a full `Completed` would
  misstate reality worse than what this closure fixed on ED-0067.
- No schema, migration, dependency, runtime-configuration, or product-authority decision
  was made by this directive. Every action was a merge, a rebase-and-force-with-lease of
  an already-reviewed branch, or a documentation-accuracy correction.
