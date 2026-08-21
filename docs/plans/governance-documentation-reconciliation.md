# Governance and documentation reconciliation

## Status

Approved

## Execution authority

- Classification: Green autonomous
- Authority evidence: Acquisition-style due-diligence audit (2026-08-20, commit `42e71c2`),
  Major findings "The project's own governance process was dropped for the highest-risk
  recent work" and "Documentation materially understates what's actually built," plus
  Minor finding "README contradicts the repo's own LICENSE"; explicit 2026-08-21 user
  directive to proceed with structural fortification.
- Implementation-ready: Yes
- Required escalation or approval, if any: None. This is documentation-only work with no
  product-semantic decision embedded; where a genuine governance choice exists (retire vs.
  backfill the ED convention) this plan records the decision taken rather than deferring it.

## Related findings or ADRs

- Finding/disposition: Due-diligence audit Major findings — `ENGINEERING_DIRECTIVES.md`
  index ends at ED-0054 while PRs #58-72 shipped the durable kernel, transcription worker,
  and Demo/Devcon integration outside the `ed/<number>` convention; `README.md` stale by a
  dozen-plus PRs; `AGENTS.md` still asserts durability/frontend-test claims that are now
  false; `CHANGELOG.md`/`ROADMAP.md` both 1 byte, unchanged since initial commit; README's
  license section says "To be determined" while a complete MIT `LICENSE` file exists;
  README's structure section omits `backend/` and `frontend/`.
- ADR: None required.
- Engineering Directive: ED-0058.

## Problem statement

A prospective evaluator (or a new engineer) reading this repository's own governance and
orientation documents would materially undercount what is actually built and would not
know that recent high-risk work (durable Postgres kernel, transcription worker, Demo/Devcon
integration) proceeded outside the project's own stated implementation-authority
convention. The documentation gap is itself evidence the convention needs either an
explicit resumption or an explicit, honest retirement — silence is the wrong answer either
way.

## Verified current behavior

- `ENGINEERING_DIRECTIVES.md` index ends at ED-0054; ED-0055 onward are introduced by this
  same remediation effort (see ED-0055 through ED-0059, this file's own sibling plans).
- `README.md`, `AGENTS.md` predate the durable kernel, transcription worker, and Demo/Devcon
  work; `AGENTS.md` contains at least two now-false claims (no restart-safe workflow, no
  frontend test runner).
- `CHANGELOG.md` and `ROADMAP.md` are each 1 byte (unchanged since their initial commit).
- `README.md`'s license section says "To be determined"; `LICENSE` at repo root is a
  complete MIT license. `README.md`'s structure section does not mention `backend/` or
  `frontend/`, the two directories containing all real source.

## Desired behavior

`README.md`, `AGENTS.md`, `CHANGELOG.md`, and `ROADMAP.md` accurately reflect the
repository's current, verifiable state as of this reconciliation. The Engineering
Directive convention is explicitly resumed for all work going forward (this remediation
effort's own plans are the first proof), with a clear, honest note that PRs #58-72
proceeded via informal dated directives and completed plan documents instead of ED numbers,
rather than silently backfilling thirteen-plus retroactive ED entries of low evidentiary
value.

## In scope

- Update `README.md`: current build/architecture summary, correct license section
  (reference the existing MIT `LICENSE`, do not restate license terms), add `backend/` and
  `frontend/` to the structure section.
- Update `AGENTS.md`: remove or correct the now-false "not yet a composed, durable,
  restart-safe workflow" and "no frontend test runner is configured" claims (or any
  successor wording carrying the same false claims), replacing with a currently-accurate
  statement or a pointer to the authoritative architecture docs instead of a duplicated
  claim that will go stale again.
- Populate `CHANGELOG.md` with entries covering at least the merged PRs since the last
  real changelog content (or since project start if none exists), following whatever
  changelog convention is idiomatic for this repo (Keep a Changelog style is a reasonable
  default if none is already established).
- Populate `ROADMAP.md` with the currently known near-term items (Demo 2 live rehearsal
  gate, due-diligence remediation items tracked by this plan and its siblings, and any
  other explicitly known upcoming work) — write only what is currently true; do not
  speculate beyond what's already been discussed.
- Add a short, explicit governance note (in `ENGINEERING_DIRECTIVES.md` itself, near the
  index) stating: the index resumes at ED-0055; PRs #58-72 proceeded via dated informal
  directives and `docs/plans/` completion records instead of ED numbers; that gap is
  acknowledged here rather than retroactively filled.

## Out of scope

- Rewriting or reinterpreting historical evidence to make past work look more or less
  disciplined than it was — the governance note above must be accurate, not flattering.
- Any code, schema, or behavior change.
- Retroactively authoring ED-0001-style detailed entries for PRs #58-72 — explicitly
  rejected in favor of the honest-gap-acknowledgment approach above, given the low
  evidentiary value of retroactive paperwork versus the cost of producing thirteen-plus
  entries for already-shipped, already-plan-documented work.
- Deciding whether independent code review becomes mandatory going forward — that is a
  separate governance/process decision for the repository owner, not a documentation fix;
  note it as an open question below rather than deciding it here.

## Constraints

- Architecture and terminology constraints: use only currently-verifiable claims; do not
  copy forward any status claim without checking it against current `main`.
- Compatibility constraints: none — documentation only.

## Implementation approach

1. Diff `README.md` and `AGENTS.md` against current `main` behavior (recent PRs, current
   test/tooling state, current architecture docs) and correct every claim shown false by
   direct inspection.
2. Add the `ed/<number>` convention-resumption note to `ENGINEERING_DIRECTIVES.md`.
3. Write `CHANGELOG.md` entries from `git log`/merged-PR history.
4. Write `ROADMAP.md` from currently known, already-discussed near-term items only.
5. Run `git diff --check` and a plain read-through for internal consistency (no document
   should contradict another after this change).

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `README.md` | Current-state summary, corrected license section, backend/frontend in structure |
| `AGENTS.md` | Remove/correct now-false durability and frontend-test-runner claims |
| `CHANGELOG.md` | Populate with real entries |
| `ROADMAP.md` | Populate with currently known near-term items |
| `ENGINEERING_DIRECTIVES.md` | Add ED-0055 through ED-0059 index rows; add convention-resumption governance note |
| `docs/plans/README.md` | Add this plan's and its siblings' index rows |

## Data or migration considerations

None.

## Failure and recovery considerations

Not applicable — documentation only.

## Observability requirements

Not applicable.

## Test strategy

- `git diff --check`.
- Manual cross-read: confirm no remaining document contradicts current `main` behavior or
  another document after this change.

## Acceptance criteria

- [ ] `README.md` license section references the actual MIT `LICENSE` file; structure
  section includes `backend/` and `frontend/`.
- [ ] `AGENTS.md` no longer asserts the durability or frontend-test-runner claims shown
  false by this plan's verification step.
- [ ] `CHANGELOG.md` and `ROADMAP.md` are no longer empty placeholders and reflect real,
  currently-true content.
- [ ] `ENGINEERING_DIRECTIVES.md` documents the resumption of ED numbering at ED-0055 and
  honestly notes the PR #58-72 gap rather than silently ignoring or retroactively
  fabricating it.
- [ ] No claim in any updated document is contradicted by direct inspection of current
  `main`.

## Rollback or reversal

Revert the documentation changes. No code, schema, or data effect to reverse.

## Open questions

- Whether mandatory independent review becomes a going-forward requirement is a
  repository-owner governance decision, not resolved by this plan — flagged for the
  repository owner, not silently decided here.

## Completion record

_(To be filled in by whoever implements this plan.)_
