# StageFlow — Claude session handoff

Written 2026-08-21. Purpose: carry context between machines/sessions (this Mac →
Razer PC in VS Code) and double as the state-evaluation input for coordinating with
Codex before any implementation resumes. Nothing described below has been implemented
— this is a status snapshot, not a completed changelog.

## What's happened so far

1. **Acquisition-style due-diligence audit.** Six read-only categories (security/
   secrets, dependencies/licensing, test coverage/CI, architecture consistency, code
   quality, docs/git hygiene) audited against `main`. Mid-review the checkout was found
   55 commits behind `origin/main` and fast-forwarded (clean, no conflicts) to `42e71c2`;
   five of six categories were re-run against that HEAD. Full report published as an
   Artifact ("StageFlow Due Diligence", 🔍):
   https://claude.ai/code/artifact/449b25e1-4d97-49c5-851f-ef0e17ef212e

   Headline: **1 blocker** (no authentication anywhere in the new API layer, including
   endpoints that mutate durable session/kernel state), **5 major** (CI real but not
   enforced — no branch protection, Postgres durability tests skipped in CI, frontend
   test suite not wired in; governance/ED-directive process dropped for the newest work,
   zero independent review across the repo's entire history; docs materially lag the
   codebase — AGENTS.md/README/CHANGELOG/ROADMAP all stale; likely GPL-2.0 codec
   exposure via the `faster-whisper`/PyAV dependency chain, needs counsel confirmation;
   a 2,072-line unrefactored coordinator with silent-failure exception handling and
   logging that's configured but never called), **9 minor**, **9 areas confirmed
   genuinely solid** (clean secret/SQL hygiene, zero-suppression static analysis, clean
   dependency management, strong Devcon boundary-validation code).

   **No findings have been approved for remediation yet.**

2. **Context that revised the read of those findings.** The post-ED-0053 commit range
   (durable Postgres kernel, transcription worker, `api/v1/demo.py` /
   `kernel_status.py` / `media_timing_evidence.py`, Devcon publishing integration) was
   built to let the **DevCon 8 team evaluate StageFlow for real use at their event** —
   Mumbai, this year, 3 Main ("Lotus") stages, 2 secondary ("Jasmine") stages, 5
   workshop rooms, 1 music performance stage (11 concurrent stage/room contexts). This
   is a live prospective-customer evaluation, not an internal-only demo.

   Practical effect: the Devcon integration is very likely **core product surface, not
   disposable demo scaffolding** — an earlier "probably strip this" guess was wrong and
   has been corrected. What (if anything) actually gets stripped vs. hardened-and-kept
   from that commit range is **still an open decision**, last framed as "partial keep,
   triage piece by piece" — not yet finalized.

3. **Tooling built for this repo** (project-level, in `.claude/`, currently untracked
   in git — commit/push if you want it available via a plain clone on another machine):
   - `agents/acquisition-auditor.md` — read-only, one risk category per invocation,
     severity-rated findings with file:line evidence. Never edits files.
   - `skills/acquisition-audit/SKILL.md` — fans `acquisition-auditor` out across all six
     categories, synthesizes one report. Used to produce the audit above.
   - `agents/stageflow-engineer.md` — read/write, implements one already-scoped task,
     classifies it Green/Yellow/Red per this repo's own AGENTS.md before touching
     anything, stops and escalates on Yellow/Red instead of guessing, reports using
     AGENTS.md's own Final Response template.
   - `skills/stageflow-cleanup/SKILL.md` — chains an approved finding through
     `stageflow-engineer`, independently checked by the built-in `code-review` skill,
     with an optional re-`acquisition-audit` to confirm the fix actually closed the gap.
   - **Neither `stageflow-engineer` nor `stageflow-cleanup` has been run yet.**

## Explicitly not yet decided

- Final keep/strip split for the post-ED-0053 vertical-slice code.
- Which due-diligence findings are approved for remediation.
- How to reconcile work with Codex, which is an existing active contributor to this
  repo (visible via `codex/*` branches in git history; AGENTS.md's "Bounded autonomous
  execution" section is written to address Codex by name). The user is getting a clean
  handoff document and state evaluation from Codex before authorizing any Claude
  implementation work, specifically to avoid the two agents crossing streams on the
  same repo.

## Current instruction standing

Do not run `stageflow-engineer` or `stageflow-cleanup`, and do not otherwise edit the
working tree for remediation purposes, until the Codex coordination above is resolved.
Read-only work (further audits, exploration, discussion) is fine.
