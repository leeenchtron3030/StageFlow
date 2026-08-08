# Implementation plans

## When a plan is required

Create a plan before work that crosses multiple architectural boundaries, changes a
public contract, introduces persistence or migrations, adds a dependency or provider,
alters identity/time/replay semantics, changes startup or recovery behavior, or implements
an accepted audit finding with meaningful sequencing risk.

A narrow documentation correction or isolated behavior-preserving fix may not require a
separate plan when its authority and acceptance criteria are already explicit.

Use [TEMPLATE.md](TEMPLATE.md). Keep each plan independently understandable and small
enough to review and reverse. One plan must not silently bundle unrelated findings.

## Statuses

- **Draft:** being investigated; not implementation authority.
- **Proposed:** ready for architecture/maintainer review.
- **Approved:** scope and acceptance criteria are authorized for implementation.
- **In progress:** approved work has started.
- **Blocked:** an explicit dependency or decision prevents progress.
- **Completed:** acceptance evidence and completion record are present.
- **Superseded:** replaced by a linked plan or decision.
- **Abandoned:** intentionally closed without implementation, with rationale.

## Review and approval

- Link every applicable finding, disposition, ADR, directive, and architecture document.
- Verify current behavior before proposing an implementation.
- Resolve architecture decisions before marking a dependent plan approved.
- Identify compatibility, migration, failure/recovery, observability, test, and rollback
  implications before implementation begins.
- Approval must be explicit. A generated draft is not self-approving.

## Relationship to Codex tasks

A Codex task may create or execute a plan only within the user's authorized scope. Codex
must follow the approved plan, report conflicts, preserve unrelated changes, and avoid
implementing adjacent findings. If no plan exists for work that requires one, create a
plan first rather than using the task conversation as hidden architecture.

## Deviations

Record a material deviation before or when it occurs. State:

- what changed from the approved plan;
- evidence that made the deviation necessary;
- scope, compatibility, migration, and risk impact;
- who approved it;
- whether the plan, ADR, or acceptance criteria must change.

Do not rewrite the original approach without retaining the decision history.

## Completion and history

A completed plan records the implemented revision, actual files and migrations, commands
and tests run, observed results, deviations, rollback status, and remaining work. Once
completed, it becomes historical implementation evidence. It does not supersede an ADR
or architecture document unless those documents are explicitly updated.

## Current plan index

No plans have been created under this framework yet. Add new plans here with status,
owner, related decision/finding, and a link.
