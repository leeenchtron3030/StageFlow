---
name: stageflow-plan
description: Decision-grade StageFlow writing at high reasoning effort — drafting an implementation plan from docs/plans/TEMPLATE.md, an ADR candidate, an Engineering Directive's scope, a Yellow escalation, or the interpretation section of a validation result. Use when the output decides or records what StageFlow should do, not for routine orchestration, git, or validation steps.
model: opus
effort: high
---

# StageFlow Plan

Use this skill for work that decides what StageFlow should do next or records what
evidence means. Routine directive execution, git housekeeping, and test runs stay in the
main session.

## Before writing

1. Read `AGENTS.md`, `PRODUCT_CONSTITUTION.md`, `docs/architecture/README.md`,
   `docs/adr/README.md`, and `ENGINEERING_DIRECTIVES.md`, then the documents they index
   that bear on the topic.
2. Verify the current state in the repository itself (code, migrations, tests, index
   rows) rather than trusting memory, handoff notes, or another agent's report.
3. Classify the work Green, Yellow, or Red under `AGENTS.md`. If it is Yellow or Red,
   the output is an escalation, not a plan marked implementation-ready.

## By output type

- **Implementation plan**: start from `docs/plans/TEMPLATE.md`. Record the execution
  classification, authority evidence, verified current behavior with citations, bounded
  in-scope and out-of-scope lists, hard constraints, objective acceptance criteria,
  identifiable tests, rollback, and open questions. Mark it implementation-ready only
  when no decision remains open.
- **ADR candidate**: state the decision required, the forces, the options with their
  tradeoffs, and a recommended default. Leave acceptance to the owner.
- **Yellow escalation**: state the decision required, repository evidence, the options,
  tradeoffs, the recommended default, the work that is blocked, and the independent work
  that may continue.
- **Validation result interpretation**: report every measurement, including outliers and
  failures. Separate what was measured from what it implies. Name the limits (single
  machine, single corpus, sandbox versus host). Never present qualification evidence as
  a throughput guarantee or event readiness. Keep media paths, filenames, usernames, and
  transcript content out.

## Boundaries

- Do not allocate an Engineering Directive number unless the owner has delegated
  numbering for this task; say which number you used and why.
- Do not rewrite historical documents (reviews, completed plans, dated results) to match
  the current implementation.
- Do not merge or approve your own output. Hand it to the owner.
