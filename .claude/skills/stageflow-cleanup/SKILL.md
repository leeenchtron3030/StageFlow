---
name: stageflow-cleanup
description: Remediate approved findings in the StageFlow repo one at a time, following the repo's own AGENTS.md governance (Green/Yellow/Red classification, small reversible changes) via the stageflow-engineer agent, independently checked by the code-review skill, and optionally re-verified with acquisition-audit. Use for working through a due-diligence or code-review backlog efficiently without losing this repo's process discipline.
---

# StageFlow Cleanup

Chains this repo's audit and remediation tooling into one repeatable workflow:
`acquisition-audit` (find) → user approval → `stageflow-engineer` (fix, one item at a
time) → `code-review` (independently verify the diff) → optional re-`acquisition-audit`
(confirm closure). Use this whenever working through a backlog of approved findings,
not just after a fresh acquisition audit — the same chain applies to any StageFlow
cleanup backlog (a code-review pass, a manual punch list, etc.).

## Preconditions

Only remediate findings the user has explicitly approved for fixing. Do not treat a
findings report as a to-do list to clear autonomously — each item (or an explicitly
approved batch) needs a go-ahead, per this repo's own "do not implement adjacent audit
findings without authorization" rule.

## Per-finding loop

For each approved finding, run these steps in order — do not batch unrelated findings
into one change:

1. **Scope it.** State in one or two sentences what the fix is and is not. If the
   finding as written is too vague to scope (e.g. "clean up the god-file" without
   specifying what "clean up" means), ask before dispatching — don't let the engineer
   agent guess at scope.
2. **Dispatch to `stageflow-engineer`** with: the finding's summary and evidence
   (file:line), the one-sentence scope from step 1, and an explicit instruction that
   this task is pre-approved (so it can classify Green and proceed, unless the work
   itself reveals a Yellow/Red condition the auditor didn't know about).
3. **If the agent escalates (Yellow/Red)**, stop that item and surface the escalation to
   the user verbatim — do not attempt to resolve it yourself or route it back for
   another try. Move on to the next approved finding while it waits.
4. **If it completes**, run the `code-review` skill (medium effort is usually enough
   for a single scoped fix; use high for anything touching auth, persistence, or
   external integrations) against the resulting diff as an independent check before
   calling the item done.
5. **Report per item**: what changed, what code-review found (and whether it was
   applied or deferred), and the engineer's own Final Response summary. Keep reports
   per-item, not batched into one wall of text, so the user can approve/reject
   individually.

## After a batch

Once a batch of approved findings is done, offer — don't auto-run — a fresh
`acquisition-audit` pass scoped to the same categories as the original findings, to
confirm they're actually closed rather than just believed closed. This is especially
worth doing for the security/auth and license findings, where "the code changed" and
"the risk is gone" are not the same claim.
