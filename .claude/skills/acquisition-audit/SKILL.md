---
name: acquisition-audit
description: Run an acquisition-style due-diligence audit of a repository — maps structure, then fans out read-only auditor agents across security, dependencies/licensing, test coverage, architecture consistency, code-quality/amateur-signal, and docs/git-hygiene categories, and synthesizes one severity-ranked findings report. Read-only — produces a report for approval, does not fix anything.
---

# Acquisition Audit

Use this when the user wants a due-diligence style review of a codebase as though
evaluating it for acquisition — not an ordinary code review, and not a fix-it pass.
Runs in two phases; phase 2 requires explicit user approval before any code changes.

## Phase 1 — Audit (read-only, cheap agents)

1. If you don't already have a structural map of the target repo (languages, module
   boundaries, rough size, test setup, CI config, dependency manifests, and any
   repo-authored process docs like ADRs/directives/AGENTS.md), get one first — via the
   Explore agent for a quick/medium pass, not a full read of every file. Skip this step
   if the current conversation already has this context.
2. Fan out `acquisition-auditor` subagents in parallel (`run_in_background: true` on
   all of them, since none depend on each other), one per category, each told the repo
   root, the structural map, and exactly which category it owns:
   - **Security & secrets exposure** — hardcoded credentials, unsafe deserialization,
     auth gaps, `.env` handling, secrets committed to git history.
   - **Dependency & license health** — outdated/abandoned packages, known CVEs,
     license incompatibilities, lockfile drift.
   - **Test coverage & CI quality** — what's actually tested vs. claimed, flaky/skip
     patterns, whether CI gates match what the repo's own docs claim.
   - **Architecture consistency** — does the implementation match the project's own
     ADRs / directives / constitution, if any exist; drift between stated and actual
     design is itself a finding.
   - **Code quality / amateur signals** — dead code, TODO/FIXME density, inconsistent
     naming or error handling, copy-pasted blocks, god-objects/files, magic numbers,
     missing input validation at boundaries.
   - **Documentation & git hygiene** — README accuracy, commit message quality, branch
     strategy, whether docs describe reality or aspiration.
3. Each agent reports read-only findings with `file:line` evidence and a severity
   (BLOCKER/MAJOR/MINOR/NOTE) per the `acquisition-auditor` agent's rubric.

## Phase 2 — Synthesis (main thread, the "acquirer" conversation)

4. Merge all category reports into one findings document, deduplicated, most severe
   first. Frame each finding in acquirer terms: does it reduce valuation, require an
   escrow holdback, need a remediation plan before close, or is it just noise. Note
   NOTE-level positives too — the report should be honest in both directions, not just
   a list of complaints.
5. Present the synthesized report to the user and stop. Do not start fixing anything in
   the same pass — remediation is a separate, explicitly approved phase, per finding or
   per batch.

## Phase 3 — Remediation (only after explicit approval)

6. Once the user approves specific findings for fixing, implement them as normal scoped
   changes (small, reviewable, one concern at a time), following the repository's own
   contribution rules (e.g. `AGENTS.md`) if present.
