# Durable Event-Mode Kernel

## Status

Completed - implementation candidate; targeted correction verification pending

## Execution authority

- Classification: Green autonomous.
- Authority evidence: Product Constitution; ADR-0001, ADR-0002, ADR-0004, ADR-0012,
  ADR-0013, ADR-0019 through ADR-0023; architecture-baseline disposition D-01 through
  D-08; and the accepted Contract Stabilization final verification.
- Implementation-ready: Yes.
- Required escalation or approval, if any: None within ADR-0024 and this bounded plan.

## Related findings or ADRs

- Finding/disposition: ABR-001/002/008/009/010/011/012 and approved D-01 through D-08 in
  the [architecture-baseline disposition](../reviews/architecture-baseline-disposition.md).
- Phase gate: [Contract Stabilization final verification](../reviews/contract-stabilization-final-verification.md)
  accepts phase entry with only non-blocking Green follow-up.
- ADR: [ADR-0019](../adr/ADR-0019-stable-ingress-and-interpreter-boundary.md),
  [ADR-0020](../adr/ADR-0020-canonical-media-to-event-path.md),
  [ADR-0021](../adr/ADR-0021-time-authority.md),
  [ADR-0022](../adr/ADR-0022-postgresql-authoritative-operational-store.md), and
  [ADR-0023](../adr/ADR-0023-session-authority-and-completion.md), and
  [ADR-0024](../adr/ADR-0024-durable-kernel-authority-and-persistence.md).
- Architecture design: [Durable Event-Mode Kernel](../architecture/durable-event-mode-kernel.md).
- Relevant completed/in-progress plans: stable ingress identity, dispatcher/interpreter
  compatibility, production timestamp invariants, recursive metadata immutability, and
  local-filesystem discovery race hardening.

## Problem statement

StageFlow has a verified health shell, static frontend, stable PostgreSQL ingress, and a
broad set of deterministic Production contracts. It does not compose them into a
durable, restart-safe event-media workflow. An event operator cannot select one Business
Event, load Stages and source bindings, durably discover and register completed media,
resolve Session association, recover after restart, or query event-oriented status.

The first Kernel must prove those local-first operational properties without expanding
into transcription, editorial AI, publishing, rendering, cloud execution, distributed
workers, or production deployment.

## Verified current behavior

Repository inspection at the 2026-08-08 baseline established:

- `app.main` composes only shell settings, logging, a minimal lifespan, and liveness;
  `app.bootstrap` is reserved and has no behavior.
- `core.config.Settings` has four environment-backed service fields and no Event, Stage,
  storage, database, Runtime, or secret-reference configuration.
- ADR-0022's Psycopg repository and `0001_ingress` are the sole durable implementation;
  no connection owner is composed at startup.
- Production Event ingress/dispatch and concrete interpreters are synchronous and
  deterministic but caller-created.
- the Business Event context is a placeholder and no Stage aggregate exists.
- `ScheduledActivity` models planned information only; no durable Program Expectation
  store exists.
- Session window/product contracts, boundary Evidence, transition policies,
  Verification, and Operational State are proposals/projections, not a Session aggregate.
- the concrete Operational State repository, Software Agent lifecycle, and media
  collection coordinator are process-local.
- local filesystem discovery is bounded and read-only; concrete resource observers,
  durable candidate/observation stores, asset assembler, and asset registry are absent.
- readiness policy and Completed Media Asset contracts are implemented but uncomposed.
- strict aware time and injected clocks are implemented.
- `/api/v1/health` is the only route and reports liveness, not database/source/Event
  readiness.
- no durable Operation/Job, worker, outbox, broker, or Node service exists.

The detailed classification and reuse treatment is authoritative design evidence in the
[Kernel architecture current-state map](../architecture/durable-event-mode-kernel.md#verified-current-state-map).

## Desired behavior

One modular-monolith process on a reference event node can:

1. load and validate one effective deployment configuration without embedding secrets;
2. connect to local-network-capable PostgreSQL and load one Business Event/Stage context;
3. reconstruct durable state and reconcile configured media sources before readiness;
4. run explicit bounded discovery/observation cycles subordinate to production load;
5. durably register candidates, objective observations, readiness decisions, and
   immutable Completed Media Assets;
6. publish the asset-registration Production Event through stable ingress;
7. record associated, unresolved, or conflict Session outcomes with provenance;
8. preserve human boundary and completion authority plus late-media revision history;
9. restart without duplicate identity/effects or process-memory authority; and
10. expose read-only Event/Stage/Session/media/dependency/recovery status for a future
    Producer Mission Control UI.

## In scope

- Versioned deployment configuration, validation, redacted effective summary, and
  Runtime construction.
- Narrow application composition root and owned PostgreSQL lifecycle.
- Approved minimal Business Event, Stage, Program Expectation, and Session contracts,
  commands, repositories, and migrations.
- Durable candidate, objective resource observation, readiness-result, Completed Media
  Asset, association/conflict, package revision/completion, and reconciliation records.
- Concrete bounded resource-observation adapters required by the configured local/
  mounted storage reference path.
- Completed Media Asset assembly/registry and stable asset-registration ingress bridge.
- Startup reconstruction, bounded reconciliation, conservative dependency recovery, and
  no authoritative process-memory fallback.
- Readiness plus read-only domain status/query routes.
- Behavior-first validation and incremental Windows/Razer reference-node qualification.
- Directly affected architecture, runbook/setup, and completion documentation.

## Out of scope

- Transcription, vision/model inference, editorial AI, clips, rendering, publication,
  delivery, archive, retention/deletion, and cloud/provider work.
- Generic Durable Operations/Jobs, workers, leases, transactional outbox, broker,
  microservices, or distributed scheduling.
- Full Producer UI, authentication product design, Grafana/system-monitoring platform,
  or incident-management system.
- Session split/merge, cross-Stage movement, AI-authoritative association, default grace
  duration, and post-publication late-media behavior.
- Multi-node work distribution, dedicated Node service, direct NDI/SDI capture, recorder
  control, media transfer, or media blobs in PostgreSQL.
- Production deployment, destructive production migration, or event-readiness claim.
- Unrelated Contract Stabilization Green follow-ups.

## Constraints

- Architecture and terminology: preserve Business Event versus Production Event,
  Program Expectation versus realized Session, candidate/observation/readiness/asset
  separation, Stage invariants, Operational State projection meaning, and ADR-0023 human
  authority.
- Compatibility: extend existing public contracts or add adapters; do not silently
  rename `ScheduledActivity`, `SessionWindow`, or other existing serialized/Python
  boundaries.
- Offline/event mode: local event-critical operation cannot require Internet; recording
  and livestream systems remain higher priority and independent of StageFlow failure.
- Data/security: media content stays outside PostgreSQL; versioned config contains no
  secret; secret values resolve only at infrastructure boundaries; tests use synthetic
  media/facts and isolated databases.
- Time: new supplied/persisted domain timestamps are aware; infrastructure times use an
  injected clock; source, occurrence, evaluation, decision, receipt, commit, and
  reconciliation meanings remain separate.
- Immutability/provenance: new immutable contracts recursively freeze metadata;
  behavior-driving identity, Stage, evidence, authority, policy/model, and provenance
  are first-class.

## Target architecture and ownership

The target flow is:

```text
effective config -> composition/startup -> PostgreSQL/context load
-> reconstruction/reconciliation -> bounded media cycle
-> candidate registry -> objective observations -> readiness
-> Completed Media Asset registry -> stable asset-registration Production Event
-> Session association/unresolved/conflict -> durable projections -> status queries
```

Direct synchronous calls own deterministic transformations. Repository transactions own
durable changes. A process timer/operator trigger requests bounded cycles but owns no
truth. PostgreSQL plus source reconciliation is restart authority.

The approved Session design uses separate lifecycle dimensions:

- Program Expectation: planned/external or declared reality;
- activity: imminent projection, presentation active, presentation ended;
- media package: assembling, ready for review, correction required;
- review: in review and human-approved complete for one package revision; and
- downstream editorial/publication/delivery/archive: excluded separate lifecycles.

## Workstreams and dependency order

### WS0 - Resolve and record Yellow decisions (completed)

1. Y-K01 through Y-K04 are accepted by explicit user authority.
2. ADR-0024 records the decisions without revising ADR-0023 semantics.
3. This plan is Approved and Green autonomous.

**Gate:** Satisfied on 2026-08-08.

### WS1 - Deployment configuration and composition foundations

1. Define a schema-versioned TOML contract and validation errors.
2. Apply accepted precedence and resolve a named PostgreSQL secret from the environment
   at the infrastructure boundary.
3. Build/validate the existing immutable `StageFlowRuntime` graph from configuration.
4. Expose a redacted effective-configuration summary with per-field source.
5. Add the narrow composition root, database connection owner, liveness/readiness split,
   and controlled shutdown.

Depends on Y-K01 for selected-ID/bootstrap validation. No domain mutations in startup.

### WS2 - Aggregate and persistence foundation

1. Add immutable Business Event, Stage, Program Expectation, and Session domain
   contracts plus approved idempotent command boundaries.
2. Implement Y-K04's repositories and numbered forward/reversal migrations.
3. Enforce immutable ownership, revision concurrency, one-active-Session-per-Stage, and
   append-oriented decision history in transactions.
4. Add a backward-compatible realized-Session Operational State subject and PostgreSQL
   repository implementation where the accepted transition/acceptance lineage is used;
   keep it a projection rather than aggregate authority.
5. Add reconstruction and query protocols; keep in-memory implementations test-only.

Depends on Y-K01, Y-K02, and Y-K04.

### WS3 - Durable media observation and registry

1. Add candidate and resource-observation repositories around existing contracts.
2. Implement the smallest concrete bounded local/mounted resource-observation adapters.
3. Adapt the process-local coordinator flow so durable repository state, not coordinator
   snapshot, owns deduplication/restart truth.
4. Invoke the existing conservative readiness policy with stored facts and explicit
   policy identity/version.
5. Assemble/validate/register the existing Completed Media Asset contract.
6. Emit/register the stable asset-registration Production Event after asset commit and
   dispatch synchronously.

Depends on WS1/WS2 persistence foundations. Can be reviewed separately from Session
association.

### WS4 - Session association, boundaries, package revision, and completion

1. Implement Y-K03's categorical deterministic association policy and evidence model.
2. Persist associated/unresolved/conflict current outcomes and append-only revisions.
3. Add operator commands for boundary declarations/corrections and asset assignment/
   reassignment.
4. Build package revisions from registered association membership and prerequisites.
5. Require an attributable human decision for completion of one revision.
6. On valid late media, preserve history and project correction/review required.

Depends on WS2/WS3 and Y-K02/Y-K03.

### WS5 - Startup recovery and reconciliation

1. Add narrow durable reconciliation-run identity, scope, state, progress, result, and
   failure category; do not create a generic Job table.
2. Reconstruct Event/Stage/Session/media current projections from PostgreSQL.
3. Reconcile each configured binding with bounded discovery/observation.
4. Prove duplicate/replacement/storage/database failure behavior and readiness gating.
5. Resume periodic bounded cycles only after required startup reconciliation completes.

Depends on WS1 through WS4.

### WS6 - Producer-oriented query boundary

1. Add Event, Stage, Session, media, dependency, recovery, and attention read models.
2. Preserve Observed/Derived/Inferred/Declared/External provenance in typed domain
   projections through a small shared query vocabulary, not a generic fact table.
3. Add read-only versioned routes and retain liveness separately from readiness.
4. Redact secret and sensitive source-location values.

Depends on repository/query boundaries and can grow incrementally with WS2 through WS5.

### WS7 - Reference-node qualification and operational evidence

1. Document Windows local PostgreSQL/service-account/secret setup and isolated migration
   workflow.
2. Exercise process kill/restart, database loss/return, storage loss/return, file/
   directory replacement, and recovery readiness.
3. Run an event-length synthetic workload and record CPU, memory, handles, I/O, database
   growth, and source impact against configured budgets.
4. Validate sleep/hibernate/power-plan assumptions and safe network-loss recovery.
5. Rehearse isolated backup/restore before any event-deployment recommendation.

Begins at each relevant milestone; final qualification follows WS5/WS6.

## Files or modules expected to change

Exact names are finalized after Y-K04; expected boundaries are:

| Path or module | Expected change |
| --- | --- |
| `backend/app/bootstrap/` and lifespan/main | Composition root, startup gates, reconstruction, shutdown |
| `backend/app/core/config/` | Versioned TOML/effective configuration, precedence, redaction, secret references |
| `backend/app/contexts/events/` | Business Event, Stage, and Program Expectation authorities/protocols |
| `backend/app/contexts/production/` | Session aggregate, bounded durable-cycle adapters, asset assembler/registry, association policy, read models |
| `backend/app/infrastructure/postgres/` | Approved repositories, connection ownership, errors, migrations |
| `backend/app/api/v1/` | Readiness and read-only Producer-oriented status routes |
| `backend/tests/` | Unit/contract/integration/migration/fault/restart/concurrency tests |
| `docs/architecture/`, `docs/adr/`, `docs/plans/` | Accepted decision, current implementation, and completion updates |
| future operations/runbook docs | Razer/PostgreSQL/configuration/recovery/backup qualification instructions |

The frontend is not expected to change in this plan.

## Data or migration considerations

This plan will introduce new durable schema after Y-K04 approval. Every migration must:

- state forward and explicit reversal behavior;
- preserve immutable StageFlow identities and external-reference versions;
- preserve proposal, declaration, association, package, and completion lineage;
- use aware PostgreSQL timestamps and distinct timestamp meanings;
- enforce uniqueness/revision/one-active-Session constraints at the owning transaction;
- avoid media/blob storage and credential fields;
- support reconstruction and exact replay/conflict tests;
- define rollback scope without automatically dropping shared schema or operational
  data; and
- receive isolated real-PostgreSQL forward/reverse and backup/restore evidence before
  event use.

There is no existing Session/media-registry production data to migrate. Existing ingress
rows and `0001_ingress` must remain compatible.

## Failure and recovery considerations

- PostgreSQL failure makes event readiness unavailable and stops authoritative writes;
  no memory fallback is permitted. Return requires schema verification, reconstruction,
  and reconciliation before ready.
- Source/storage failure marks affected work unavailable/deferred, preserves durable
  history, and does not infer deletion, Session end, or completion. Other Stage bindings
  continue.
- Duplicate candidate/Event/asset/association input resolves by durable identity to
  replay or typed conflict without duplicate effects.
- A replacement during inspection commits no misleading objective fact/readiness result
  and is retried by a later bounded reconciliation.
- Stage silence is an observed last-arrival fact and possibly a derived inactivity
  projection, never Session-completion authority.
- Program/Stage mismatch is unresolved/operator-action-required for the affected
  Session, while safe ingest/registration and unrelated workflow continue.
- Abrupt termination leaves transactions committed or rolled back; recovery reconstructs
  from PostgreSQL and configured sources rather than coordinator memory.

## Observability requirements

Operators and tests must be able to determine:

- selected Business Event/config revision and event readiness reason;
- PostgreSQL/source availability and exact workflow impact;
- each Stage's active Session projection and last media-arrival observation;
- candidate, stabilizing, ready, registered, unresolved, and conflict counts/identities;
- current Session boundary/package/completion revisions and human authority;
- reconciliation run identity, scope, progress, outcome, error, and recovery readiness;
- replay versus new effects and correlation across candidate, asset, ingress Event, and
  association; and
- whether each displayed claim is Observed, Derived, Inferred, Declared, or External.

Do not expose secrets, raw credentials, or unnecessary source paths. Generic CPU/system
metrics remain qualification evidence unless they directly explain production-domain
degradation.

## Test strategy

### Implementation-time tests

- Pure domain tests for identities, Stage ownership, lifecycle dimensions, boundary/
  completion revisions, epistemic provenance, and invalid construction.
- Contract tests for configuration precedence/redaction, Runtime construction, command
  idempotency, repository neutrality, exact replay/conflict, and recursive immutability.
- Real PostgreSQL integration tests for migrations, constraints, aggregate concurrency,
  reconstructed repositories, transaction rollback, and database unavailability.
- Media behavior tests for growing/empty/unsupported/replaced resources, observation
  accumulation, deterministic readiness, asset assembly/validation, registration-before-
  ingress, and no filename/path Session authority.
- Association tests for structural Stage match/mismatch, unique/ambiguous active
  Sessions, unresolved continuation, human correction, completion, and late media.
- Startup/system tests for clean and abrupt restart, database/source loss and return,
  reconciliation progress, no duplicate effects, and readiness gates.
- API tests for read-only Producer queries, provenance, attention conditions, redaction,
  liveness/readiness separation, and unavailable dependencies.

### Required quality commands

Run in proportion to each workstream and run the full closeout matrix:

```text
cd backend
uv run pytest -p no:cacheprovider
uv run ruff check .
uv run pyright
```

Run real PostgreSQL tests with an isolated `STAGEFLOW_TEST_POSTGRES_DSN`. The frontend
matrix is skipped unless frontend files or shared public API assumptions change. Run
`git diff --check` and a fresh independent Codex review for the higher-risk Green batch.
No repository-wide formatter or frontend test runner exists and neither may be claimed.

### Razer validation points

- WS1: configuration/secret/startup/shutdown.
- WS2: local PostgreSQL schema, concurrency, reversal, reconstruction, backup/restore.
- WS3: real filesystem/mounted storage behavior and resource pressure.
- WS5: process/database/storage termination and recovery.
- WS7: event-length endurance, network recovery, sleep/power, resource/coexistence
  evidence.

## Acceptance criteria

- [x] Y-K01 through Y-K04 are accepted in ADR-0024 and this plan is Approved/Green.
- [x] One valid config constructs one validated Runtime and resolves secrets only at the
  infrastructure boundary; invalid config never declares event readiness.
- [x] One Business Event and its Stages retain immutable StageFlow identities across
  restart and external schedule corrections.
- [x] Program Expectations remain revisioned planned-world records and never silently
  create or rewrite a realized Session.
- [x] A realized Session belongs to one Business Event/Stage; the database transaction
  prevents two active realized Sessions on one Stage under the approved rule.
- [x] Any persisted Operational State remains an explainable projection with durable
  acceptance lineage and cannot mutate or replace Session aggregate authority.
- [x] Candidate discovery, objective observations, readiness, Completed Media Asset
  registration, stable Event ingress, and association remain distinct durable boundaries.
- [x] Repeated discovery/Event delivery/restart produces one candidate/asset/Event/
  association effect or a typed conflict.
- [x] Unresolved/conflicting assets remain registered and processable; structural or
  schedule conflict is operator-visible and does not halt unrelated Stages.
- [x] Machine boundary proposals and successive human authoritative decisions remain
  queryable and attributable.
- [x] Session completion requires human approval for one package revision; late valid
  media preserves history and returns the current package to correction/review.
- [x] PostgreSQL/source failure and return follow the documented no-interference,
  no-memory-fallback, reconstruction, reconciliation, and readiness behavior.
- [x] Read-only queries answer the Kernel Producer status questions and preserve
  Observed/Derived/Inferred/Declared/External provenance.
- [x] No generic operation system, broker, AI, editorial/publication workflow, media
  blob storage, cloud requirement, or recorder control is introduced.
- [x] Required backend, real PostgreSQL, whitespace, restart/fault, and Razer milestone
  validation passes or any environmental limitation is explicitly reported.
- [ ] A deliberate diff/self-review and fresh independent review find no unresolved
  in-scope defect or Yellow/Red expansion.

## Rollback or reversal

- Deliver each workstream in independently reviewable commits with additive public
  boundaries and compatibility adapters where existing names remain public.
- Disable the composed Kernel through deployment configuration while retaining the
  liveness shell if an in-event rollback is needed.
- Application/config changes can be reverted without source-media mutation.
- Apply reversal SQL only to an isolated database after verifying exact schema and data
  scope; never drop shared schema or operational data automatically.
- Preserve existing ingress tables/records through new-schema rollback.
- Before operational data exists, full Kernel tables can be removed only through their
  documented operator-controlled reversal. After operational data exists, rollback must
  preserve/export identity and decision lineage and may require a forward corrective
  migration.
- No plan step deletes, rewrites, transfers, or modifies primary recording media.

## Green implementation authority

Once WS0 is complete, the accepted architecture directly authorizes the bounded
implementation choices in WS1 through WS7: modular monolith, PostgreSQL repositories,
direct synchronous deterministic calls, startup reconciliation, existing contract reuse,
TOML through `tomllib`, environment-resolved secret references, explicit bounded cycles,
narrow reconciliation runs, and read-only status. Ordinary module naming, SQL indexing,
query shape, transaction helper organization, and test-fixture details remain Green when
they preserve the accepted decisions and compatibility.

Stop and escalate if implementation reveals a need for a public compatibility break,
different aggregate/human authority, new service/dependency/topology, destructive
migration, changed failure semantics, generic operations/workers/outbox, or materially
expanded authentication/security boundary.

## Resolved Yellow decisions

The complete evidence/options/tradeoffs are retained in the
[Kernel architecture resolved-decision section](../architecture/durable-event-mode-kernel.md#resolved-yellow-decisions):

- **Y-K01:** accepted explicit idempotent operator bootstrap with stable configuration
  keys and PostgreSQL authority after commit.
- **Y-K02:** accepted human-authorized create/start for Kernel v1, including ad hoc
  Sessions and authoritative declared start boundaries.
- **Y-K03:** accepted conservative deterministic association with compatible trailing
  media, ambiguity reducing to unresolved, contradiction producing conflict, and human
  correction authoritative.
- **Y-K04:** accepted normalized current/aggregate tables plus typed append-only history;
  no event sourcing or generic history table.

## Completion record

- Implemented revision: local change groups `e55bf50`, `05c2641`, `4077446`, and
  `17a1992` on 2026-08-08.
- Files and migrations actually changed: configuration/composition/lifespan; Event/Stage
  contracts; durable Kernel contracts/service/repositories; PostgreSQL repository and
  `0002_event_mode_kernel` forward/reversal SQL; read-only status API; behavioral tests;
  ADR-0024, architecture, operations, and this plan.
- Commands and tests actually run: focused Ruff/Pyright/Pytest throughout; full
  `uv run pytest -p no:cacheprovider`, `uv run ruff check .`, and `uv run pyright`;
  gated real-PostgreSQL test with `STAGEFLOW_TEST_POSTGRES_DSN`; explicit `0002` reverse/
  reapply; PostgreSQL stop/start; focused Windows filesystem tests; `powercfg` and
  read-only host/process observations; `git diff --check` at handoff.
- Results and warnings: final backend matrix 1,600 passed and 5 existing capability/
  platform skips; Ruff passed; Pyright reported 0 errors. FastAPI's compatibility
  `TestClient` emitted one upstream Starlette deprecation warning. Isolated PostgreSQL
  17.10 migration/reconstruction/history/reversal/recovery passed.
- Execution authority used: Green implementation under ADR-0024 and this approved plan.
- Approved deviations: no architecture deviation. The existing process-local
  Operational State repository was not promoted because Kernel Session current tables
  directly own aggregate state and no accepted transition-policy lineage is used by the
  composed path; this follows WS2's conditional wording.
- Rollback status: `0002` reversal was exercised in an isolated database and preserved
  `0001` ingress; no repository or production data rollback was performed.
- Remaining Green qualification: build the deployment TOML into the pre-existing full
  `StageFlowRuntime` graph; compose the pre-existing local discovery adapter plus
  concrete resource observers into automatic startup cycles (the durable adapters and
  explicit reconciliation boundary are implemented); run backup/restore, representative
  event-length/coexistence qualification, and a fresh independent Codex phase review.
- Phase status: implementation candidate; not self-accepted and not an event-readiness
  claim.

### 2026-08-08 continuation

- Commit `8671251` constructs the validated existing `StageFlowRuntime` graph after
  explicit Event/Stage authority resolution.
- The current working tree adds the bounded configured discovery/observation/readiness/
  asset/ingress/association cycle, registered-effect replay reconciliation, bounded
  identifiable Producer projections, and non-authoritative boundary-proposal migration.
- New behavioral tests cover stable registration/association, replay, growth resetting
  the current stability window, proposal non-authority, query visibility, and real
  PostgreSQL proposal reconstruction. These tests were not executable in this
  continuation because the sandbox denied the backend virtual-environment executables
  and the escalation reviewer reported an exhausted tool-usage limit.
- Fresh Razer PostgreSQL/process/backup/endurance qualification could not proceed because
  PostgreSQL tooling was absent and the official portable download required the same
  unavailable escalation. The evidence-graded result is recorded in
  [the Razer qualification report](../reviews/durable-kernel-razer-qualification.md).
- `npm ci` was attempted with portable Node 22.23.2 and failed after 108.3 seconds with
  npm's `Exit handler never called` error. Downstream frontend checks were not claimed.
- A local implementation commit was attempted, but writing `.git/index.lock` required
  the unavailable escalation; the continuation remains an unstaged working-tree change.
- Current status: implementation drafted and deliberately self-reviewed, but not ready
  for independent phase-completion review until the required executable matrix and fresh
  qualification run complete. No production/event-readiness claim is made.

### 2026-08-09 validation and qualification closure

- Fresh execution corrected Windows path normalization, registered-candidate state
  preservation across post-registration diagnostics and PostgreSQL discovery replay,
  static typing/style defects, and missing failure-isolation/interrupted-effect tests.
- The full backend matrix ran with real PostgreSQL: 1,610 collected, 1,605 passed, five
  existing platform/capability skips; Ruff passed; Pyright reported zero errors.
- Portable Node 22.23.2/npm 10.9.8 completed clean `npm ci`, build, lint, and typecheck.
  The audit reported nine high and three moderate findings; dependencies were unchanged.
- Official PostgreSQL 17.10 on loopback applied `0001` through `0003`, reversed Kernel-
  owned migrations while preserving `0001`, reapplied, and passed the gated tests.
- A real two-Stage scenario, force-kill/restart, PostgreSQL stop/return, one-source
  disappearance/return, custom backup/clean restore, and fresh restored app graph passed.
- The accepted bounded workload ran 197.626 seconds and created 26 new segments while a
  separate 180.089-second rotating-write/hash proxy wrote 13,841,203,200 cumulative
  bytes. These are short/proxy results, not conference-duration or vMix certification.
- The Razer power posture remains unsafe for unattended Event Mode: Balanced plan, AC
  sleep 60 minutes, DC sleep 3 minutes, S0 Low Power Idle/Hibernate/Fast Startup
  available, AC wake timers enabled, and Fast Startup enabled. No policy was changed.
- Execution authority remained Green. No architecture deviation, public compatibility
  break, dependency, schema redesign, destructive migration, or Yellow/Red condition
  occurred. `0003_kernel_projections` is the approved additive migration.
- Remaining Green closure at this point is deliberate final diff/self-review, logically
  isolated commits, clean-worktree verification, and fresh independent phase-completion
  review. This plan does not self-accept the phase or claim production/event readiness.

### 2026-08-09 independent-review correction follow-up

- The fresh independent phase review returned **DO NOT ACCEPT** with DKR-001 through
  DKR-007. All findings are Green under ADR-0023/ADR-0024.
- Corrections and their new validation/evidence are governed by the separate
  [independent-review correction plan](durable-event-mode-kernel-review-corrections.md).
- This historical completion record does not self-accept the Kernel. Targeted fresh
  correction verification remains required.
