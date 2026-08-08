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
- **Approved:** scope and acceptance criteria are authorized for implementation through
  recorded Green autonomous authority or explicit human/architecture approval.
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
- Yellow/Red work and unresolved architecture require explicit human or architecture
  approval. A generated draft cannot resolve or approve those decisions.
- Green work under the root
  [bounded autonomous execution policy](../../AGENTS.md#bounded-autonomous-execution)
  does not require a separate human plan-approval turn. Codex may investigate, create or
  update the plan, validate it against existing authority, record the Green
  classification, mark it implementation-ready, and proceed.

## Execution authority

Every new implementation plan must record one of:

- **Green autonomous:** all architecture decisions are already resolved, the scope and
  acceptance criteria are bounded and objective, required tests are identifiable, and
  the work satisfies every Green condition in `AGENTS.md`.
- **Explicit approval required/granted:** a Yellow/Red condition or another project gate
  requires a named human/architecture decision before implementation.

Green classification is execution authority, not architecture authority. It cannot
accept a review recommendation, decide an ADR, change product semantics, or expand the
plan. Historical plans do not need retroactive classification.

## Relationship to Codex tasks

A Codex task may create or execute a plan only within the user's objective and existing
repository authority. Codex must follow the implementation-ready plan, report Yellow/Red
conditions, preserve unrelated changes, and avoid implementing adjacent findings. If no
plan exists for work that requires one, create and classify the plan first rather than
using the task conversation as hidden architecture.

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

| Plan | Status | Owner | Related decision/finding |
| --- | --- | --- | --- |
| [Dispatcher and Observation Interpreter compatibility](dispatcher-interpreter-compatibility.md) | Completed — independent review accepted | StageFlow Architecture / Backend | ADR-0019; ABR-003; ABR-004; D-04; DIC-001–DIC-004; DIC-RR-001–DIC-RR-003 |
| [Stable ingress identity](stable-ingress-identity.md) | In progress — implementation complete; real PostgreSQL execution pending | StageFlow Architecture / Backend | ADR-0019; ADR-0022; ABR-003; D-02; D-04 |
| [Production timestamp invariants](production-timestamp-invariants.md) | Completed — fresh phase verification pending | StageFlow Architecture / Backend | ADR-0021; ABR-005; D-07 |
| [Recursive metadata immutability](recursive-metadata-immutability.md) | Completed — independent review accepted | StageFlow Backend | ABR-006 |
| [Local filesystem discovery race hardening](local-filesystem-discovery-race-hardening.md) | Completed — independent review accepted | StageFlow Backend | ABR-007; ED-0053 |
| [CI quality-matrix enforcement](ci-quality-matrix-enforcement.md) | Completed — independent review accepted | StageFlow Engineering | ABR-015 |
| [Durable Event-Mode Kernel](durable-event-mode-kernel.md) | Approved — Green autonomous implementation | StageFlow Architecture / Backend | ADR-0019–ADR-0024; D-01–D-08 |
