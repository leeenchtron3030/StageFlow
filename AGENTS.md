# StageFlow repository instructions

These instructions apply to the entire repository. More specific `AGENTS.md` files may
supplement them only when a directory has distinct, non-duplicative needs.

## Start here

StageFlow is an observational intelligence system for live-event media. The repository
currently implements a Python/FastAPI health shell, a static Next.js shell, and a broad
set of backend Production-domain contracts, deterministic policies, explicit ports, and
process-local coordinators. It does **not** yet implement a composed, durable,
restart-safe event-media workflow.

Before architectural or domain work, read:

- `PRODUCT_CONSTITUTION.md`
- `docs/architecture/README.md`
- the relevant files indexed by that document
- `docs/adr/README.md`
- `ENGINEERING_DIRECTIVES.md`

The architecture-baseline review is evidence, not decision authority. Its disposition
is the authority for accepted, deferred, rejected, and open review outcomes.

## Repository orientation

- `backend/`: Python 3.13 FastAPI application and backend tests.
- `frontend/`: Next.js/TypeScript application shell.
- `docs/architecture/`: current implementation and accepted architecture guidance.
- `docs/adr/`: accepted decisions and unresolved ADR candidates.
- `docs/reviews/`: evidence-based reviews and their dispositions.
- `docs/plans/`: approved implementation-plan process and template.
- `ARCHITECTURE_DECISIONS.md`: preserved ADR-0001 through ADR-0018.
- `ENGINEERING_DIRECTIVES.md`: implementation-scope authority.

## Setup and verified checks

Backend setup:

```bash
cd backend
uv sync --dev
```

Backend quality checks:

```bash
cd backend
uv run pytest
uv run ruff check .
uv run pyright
```

Frontend setup:

```bash
cd frontend
npm ci
```

Frontend quality checks:

```bash
cd frontend
npm run build
npm run lint
npm run typecheck
```

Repository whitespace check:

```bash
git diff --check
```

No repository-wide formatter or frontend test runner is currently configured. Do not
claim that either ran, and do not introduce or bulk-run one without approved scope.

Run checks in proportion to the change. Report only commands actually run, their
results, and any skipped checks with a reason. A passing contract suite is not evidence
of deployed event-operational readiness.

## Working rules

- Keep changes small, independently reviewable, and within the approved directive or
  plan. Do not implement adjacent audit findings without authorization.
- Distinguish verified current behavior from assumptions, accepted future direction,
  and open decisions. Cite repository evidence for material claims.
- If a task conflicts with the Constitution, an accepted ADR, the architecture index,
  the disposition, or an Engineering Directive, stop and report the conflict. Do not
  silently choose one interpretation.
- Preserve user changes and unrelated work. Do not rewrite historical documents to
  make them appear consistent with current implementation.
- Keep core domain and workflows independent of FastAPI, Next.js, provider SDKs, and
  deployment details. Do not move domain decisions into routes, startup code, or UI.
- Preserve event-mode operation without continuous Internet connectivity. Network work
  must be explicitly classified, deferrable where approved, and isolated by adapters.
- Preserve the modular monolith. Do not introduce microservices, a broker, or an event
  hop without demonstrated reliability, concurrency, recovery, or consumer need.
- Use direct synchronous calls for deterministic domain decisions. Durable at-least-once
  operations are reserved for genuinely asynchronous, long-running, retryable, or
  externally dependent work.
- Preserve discovery, resource observation, readiness evaluation, Completed Media Asset
  registration, and Session association as separate meanings.
- New externally supplied or persisted domain timestamps must be timezone-aware.
  Infrastructure-created times use an injected clock, and distinct timestamp meanings
  must not be collapsed.
- New immutable contracts must recursively protect nested metadata. Authoritative
  identity, provenance, and behavior-driving facts must be first-class, not metadata.
- Do not silently change canonical terminology. Update the domain glossary first and
  plan compatibility for public contracts, storage, or APIs.

## Bounded autonomous execution

Classify consequential Codex work as Green, Yellow, or Red before implementation. This
classification governs execution approval; it does not change the repository authority
hierarchy, expand task scope, or bypass environment/tool approval requirements.

### Green — autonomous execution

Codex may investigate, plan, implement, validate, self-review, and complete work without
an additional human approval turn only when all of the following are true:

- The objective is already authorized by an accepted architecture document, ADR,
  disposition, approved backlog item, or Engineering Directive.
- No unresolved product or architecture decision is required.
- Accepted StageFlow semantics do not materially change.
- No intentional public compatibility break is required.
- No new external infrastructure service is required.
- No destructive data migration is required.
- No security or trust boundary is materially changed.
- Objective acceptance criteria and required validation can be identified.
- The implementation remains reasonably reversible.

For Green work, Codex is authorized to:

- inspect repository code, history, architecture, reviews, and prior plans;
- investigate and verify current behavior;
- create or update a required implementation plan, classify it as Green, and mark it
  implementation-ready when all decisions are already resolved;
- select the smallest clear implementation details that conform to accepted architecture;
- modify in-scope production code, tests, and directly affected documentation;
- add internal modules or types required by the authorized design;
- refactor directly affected code when needed for correctness or maintainability;
- run non-destructive tests, linters, type checks, builds, and other validation;
- diagnose and correct failures introduced by the task without asking whether to proceed;
- update the plan completion record and deliberately self-review the final diff;
- create logically isolated local or approved feature-branch commits when useful and
  permitted by the active environment; and
- continue to the next explicitly approved Green task without another architecture
  review.

Ordinary implementation ambiguity is not an escalation. Choose the smallest, clearest,
reversible solution consistent with current authority and document the choice.

### Yellow — escalation required

Stop before implementing the affected work and request architectural or human review
when the task requires or unexpectedly reveals:

- a new or changed architecture decision or an unaccepted ADR decision;
- a conflict among the Constitution, accepted ADRs, architecture documents,
  dispositions, or Engineering Directives;
- a material change to Session, Business Event, Stage, Segment/media, editorial, or
  lifecycle semantics;
- an intentional public API, storage, or serialization compatibility break;
- a new production dependency with architectural consequences;
- selection of a database, queue/broker, external service, or deployment topology not
  already approved;
- a new schema architecture or materially consequential migration;
- a material change to authentication, authorization, trust, identity, or secret
  handling;
- an unresolved retention/deletion, late-media, finality, or product decision;
- material expansion beyond the authorized scope; or
- evidence that the approved plan or architecture is incorrect.

An escalation must state the decision required, repository evidence, available options,
tradeoffs, recommended default, blocked work, and independent work that may safely
continue. Do not request approval for implementation details that do not meet a Yellow
or Red condition.

### Red — explicit action approval required

Never perform the following without explicit authorization for the specific action:

- destructive production-data operations;
- production deployment;
- deletion or irreversible migration of important data;
- force pushes or repository-history rewrites;
- exposure, creation, rotation, or transmission of real credentials or secrets outside
  an already approved secret workflow;
- irreversible external side effects;
- merging consequential architecture changes directly into a protected primary branch
  where project workflow requires review; or
- disabling meaningful safety, validation, or test controls merely to make a change
  pass.

### Green planning, validation, and review

- Plans remain required by the existing plan triggers. A separate human plan-approval
  turn is not required for Green work.
- A Green plan must record its execution classification, authority evidence, objective
  acceptance criteria, bounded scope, identifiable tests, and implementation-ready
  status before implementation begins.
- Codex owns proportionate validation and continues correcting in-scope defects until
  required checks pass or a Yellow/Red condition appears.
- Classify failures as caused by the change, pre-existing, environmental/tooling, or an
  architecture conflict. Correct in-scope failures automatically; document unrelated
  failures and continue when they do not compromise confidence.
- Never claim a check passed unless it ran.
- Every Green implementation receives implementation-time tests/static validation and a
  deliberate diff/self-review.
- Fresh independent Codex review is expected at the end of a higher-risk Green task or a
  logical batch of related Green tasks, not necessarily after every Green increment.
- Human review normally occurs at architecture decisions, phase boundaries,
  release/event-readiness milestones, and Yellow or Red escalations.

Autonomy does not authorize opportunistic expansion. Record and classify unrelated
findings; fix them immediately only when they directly block the authorized task and the
correction itself remains Green.

## Data, compatibility, and dependencies

- Schema or data migrations require an approved plan, explicit forward and reversal
  behavior, identity/lineage preservation, and migration tests. Never rewrite deployed
  state implicitly.
- Preserve backward compatibility unless an accepted decision and plan explicitly
  authorize a break. Document compatibility aliases and removal criteria.
- A new dependency requires a concrete need, license/security consideration, offline
  impact, ownership boundary, and lockfile update. Provider-specific dependencies must
  remain behind adapters and out of the core domain.
- Never use real event recordings, transcripts, credentials, or customer data in tests.

## Tests and documentation

- Add behavior-first tests at the changed boundary, including failure, replay,
  ordering, and immutability cases where relevant.
- Source/name exclusion tests may supplement but not replace behavioral tests.
- Add restart, multi-process, storage-fault, provider-fault, and late-media tests only
  with the durable components that make those behaviors real.
- Update current architecture documents when an accepted decision or implemented
  boundary changes. Reviews remain historical evidence; plans become historical after
  their completion record is filled.

## Final response

State the files changed, behavior or documentation outcome, commands actually run,
results and warnings, skipped checks, open decisions, and whether production code,
dependencies, schemas, migrations, or runtime configuration changed.
