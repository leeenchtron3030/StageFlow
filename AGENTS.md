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
