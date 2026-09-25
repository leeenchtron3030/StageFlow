---
name: stageflow-directive
description: Run one approved StageFlow Engineering Directive end to end through the headless Codex workflow — verify state, prepare the Codex worktree branch, build and launch the directive, independent review with directive-reviewer, host validation with the mandatory full-suite gate, commit, push, PR, CI, and owner-approved merge and resync. Use after a directive's plan is merged; not for drafting plans (use stageflow-plan) or for exploratory work.
---

# StageFlow Directive

Runs one approved Engineering Directive through Codex in the sandboxed worktree, with the
owner (Claude, acting for the repository owner) doing everything Git, host, and review
related. Each gate below exists because skipping it caused a real defect. Do not skip one
without saying so in the final report.

## Fixed facts

- **Owner tree:** `C:\Dev\StageFlow`. Never Codex's.
- **Codex worktree:** `C:\Dev\StageFlow-codex`. Codex edits only; Claude commits.
- **Codex CLI:** glob `$USERPROFILE/.vscode/extensions/openai.chatgpt-*-win32-x64/bin/windows-x86_64/codex.exe`.
- **Always pass:**
  `-m gpt-6-astra -c 'model_reasoning_effort="high"' -s workspace-write -c 'windows.sandbox="unelevated"' --color never -o <report.md> - < <directive.md>`.
  Run it with the Bash `run_in_background` flag. Confirm the `model:` and
  `reasoning effort:` lines at the top of the run log.
- **Host backend validation**, from `<worktree>/backend`:
  `env -u STAGEFLOW_API_SHARED_SECRET -u VIRTUAL_ENV uv run --no-sync pytest -p no:cacheprovider -q --tb=line`.
  Count outcomes from the progress lines only. Never use plain `uv run`, which strips the
  transcription group.
- **Known host failures:** none since ED-0083; the Windows host suite is fully green.
  `test_devcon_session_publish.py::test_devcon_no_body_response_maps_to_bounded_reason_without_retry`
  is intermittent; rerun it in isolation before calling it a regression. Anything else is new
  until proven otherwise.
- **Codex sandbox PATH:** if PowerShell 7 is installed as a Windows app, sandboxed shell calls fail
  with `CreateProcessAsUserW failed: 5`. Launch `codex exec` with `WindowsApps` removed from
  `PATH`. To test whether the sandbox works, run `echo probe-ok` with `--skip-git-repo-check` in
  an empty folder.
- **Tests that run PowerShell:** they use `pwsh` 7 when it is present, as CI on Linux does.
  PowerShell 7 re-renders ISO-date-shaped strings in `ConvertFrom-Json`, so fixtures that
  should pass through unchanged must not be date-shaped.

## Procedure

1. **Verify state.** `git fetch`, then `git status -sb` in both trees, `gh pr list`, and
   the ED row and plan status. The plan must be merged and Approved. ED numbers come
   from the owner.
2. **Prepare the branch** as a separate command:
   `git -C C:/Dev/StageFlow-codex checkout -b codex/ed-NNNN-slug origin/main`. Then verify
   the branch name and a clean tree. If the branch is in use by another worktree,
   detach that worktree first; never remove a worktree with local changes.
   - **Merge-based directives:** start `git merge --no-ff --no-commit origin/main`
     yourself, and have Codex resolve the conflicts by editing files only.
3. **Build the directive.** Copy the previous directive file from the scratchpad and
   replace the task-identity head: objective, hard constraints, and what the owner does
   versus Codex. Keep the standard sections: workspace (no Git writes; during a merge,
   no merge, add, rm, or checkout), environment (`--no-sync`, clear the secret,
   `TMP`/`TEMP` under `.codex-tmp`), known failures, change discipline, and final report.
   Codex must not allocate ED numbers or write owner-only records such as results that
   need host runs, completion records, or status cells.
4. **Launch Codex** and wait for the notification. Do not poll.
5. **Review.** Launch the `directive-reviewer` agent with the plan path, worktree, base
   ref, and report path, plus the specific risks you want checked.
   - FIX-FIRST: send the findings back to Codex as a fix directive, then re-review with
     the same agent using SendMessage, so it keeps its context.
   - ESCALATE: decide within delegated authority (for example, ED numbering) or ask the
     owner.
6. **Self-check** what reviews tend to miss:
   - stale current-state wording, such as "pending", "sandbox limitation", or aliases
     that no longer exist;
   - private details: usernames, machine paths, media names, or IP addresses;
   - white-label leaks;
   - that the docs referenced by the index rows exist.
7. **Clean up.**
   - Delete `.codex-tmp`.
   - Remove an empty, stale `.git/worktrees/StageFlow-codex/index.lock`, and only after
     confirming no Git process is running.
   - Restore `frontend/next-env.d.ts`, and remove generated `frontend/AGENTS.md` and
     `frontend/CLAUDE.md` if `next dev` ran.
8. **Host validation.** Run the full backend suite and, if anything under `frontend/`
   or anything the frontend consumes changed, `npm run test`, `build`, `lint`, and
   `typecheck`.
9. **Full-suite gate.** After *any* change made after step 8, including a one-line fix,
   a comment, or a doc touching code-adjacent files, **rerun the full backend suite**
   before pushing. Contract tests read source text; a comment once broke CI.
10. **Commit on Codex's behalf** with a descriptive message and the attribution trailer
    from the current system reminder. Use `git rebase origin/main` only for an unpushed
    branch, and never force-push a published branch.
11. **Push, open the PR, and wait for CI** (`gh pr checks --watch`). If CI fails, read
    `gh run view --log-failed`, fix the cause, and return to step 9.
12. **Ask the owner** for explicit approval to merge that specific PR. A general
    "proceed" is not enough. After approval: merge, `git pull --ff-only` in the owner
    tree, detach the Codex worktree at `origin/main`, delete the merged local branch,
    and update the project-state memory.

## Final report

Follow the `AGENTS.md` final-response template. Include:

- the PR link and the CI result;
- the reviewer's verdicts, in order;
- exact host counts, with known failures named;
- any gate that was skipped, and why;
- the open decisions;
- whether production code, dependencies, schemas, migrations, or runtime configuration
  changed.
