# Durable Event-Mode Kernel architecture

**Status:** Accepted design. ADR-0023 fixes Session semantics and ADR-0024 resolves the
Kernel bootstrap, realization, association, and persistence decisions.

## Purpose

The first Durable Event-Mode Kernel proves that StageFlow can operate as a local-first,
restart-safe modular monolith on an event node. It composes the existing Production
contracts around PostgreSQL, explicit source bindings, bounded media cycles, durable
reconciliation, and an operator-readable query boundary. It does not add transcription,
editorial AI, rendering, publishing, cloud processing, or a message broker.

## Implementation-candidate delta

The current working implementation adds the versioned TOML/secret boundary, explicit
Event/Stage bootstrap, Program Expectations, human-authorized realized Sessions,
normalized PostgreSQL current state and typed history, durable candidate/observation/
readiness/asset/association records, stable asset ingress, conservative Session
association, a fully validated existing `StageFlowRuntime` graph, bounded configured
filesystem cycles, reconciliation records, startup source gating, advisory Session
boundary proposals, and bounded read-only Producer detail. PostgreSQL is authoritative
and the in-memory repository is test-only.

Fresh reference-node backup/restore, process/dependency/storage recovery, bounded
endurance/coexistence qualification, and the full validation matrix executed on
2026-08-09. After commit and clean-worktree closure, the candidate is eligible for fresh
independent phase-completion review. The executed workload is not conference-duration,
the coexistence workload is a proxy, and neither establishes event readiness. The
verified-current-state map below is retained as the pre-implementation Contract
Stabilization baseline rather than rewritten as if those gaps never existed.

## Verified current-state map

The classifications below describe the repository at the 2026-08-08 Contract
Stabilization baseline. “Usable” refers to semantic reuse, not current deployment
readiness.

| Concern | Existing evidence | Classification | Kernel treatment |
| --- | --- | --- | --- |
| Application startup/composition | `app.main`, minimal lifespan, reserved `app.bootstrap` | Incomplete for kernel needs | Add one narrow composition root, owned connection lifecycle, startup gates, reconciliation, and shutdown |
| Service settings | `core.config.Settings` exposes four shell/environment values | Incomplete for kernel needs | Retain shell metadata; introduce one validated deployment-config loader that constructs existing Runtime contracts |
| PostgreSQL | Psycopg ingress repository and numbered `0001_ingress` migration | Usable with bounded extension | Reuse driver, explicit SQL/migration style, error taxonomy, and transaction discipline; add separately approved stores/migrations |
| Stable ingress | `production.ingress` source-key/fingerprint contracts and repository protocol | Usable as-is | Use after Completed Media Asset registration to emit the stable asset-registration Production Event |
| Production Events and dispatch | `production_event`, dispatcher/interpreter compatibility, strict lineage | Usable as-is | Compose synchronously; do not turn dispatch into a queue hop |
| Business Event aggregate | `contexts.events` placeholder; glossary only | Future placeholder | Add a StageFlow-owned durable Business Event only after bootstrap/schema decisions |
| Stage aggregate | Stage IDs/context in Runtime, Evidence, observations, and assets | Absent | Add StageFlow-owned durable Stage and binding relationships; reuse existing IDs as references |
| Planned program input | `ScheduledActivity` and schedule adapter contracts | Usable with bounded extension | Preserve adapter contracts; normalize durable revisions into Program Expectations |
| Session authority | Session window/product contracts, candidates, boundary Evidence, transition policy, Operational State projections | Legacy/incompatible as aggregate | Reuse as proposals/evidence where semantics fit; do not promote any into the Session aggregate |
| Operational State | immutable taxonomy, acceptance, repository protocol, process-local concrete repository | Usable with bounded extension | Keep projection semantics; add durable projection storage only for kernel states that have an authoritative subject/history |
| Runtime graph | immutable `StageFlowRuntime`, configuration, capabilities, targets, policies | Usable with bounded extension | Build and validate it from effective deployment config; do not duplicate its media/runtime declarations |
| Software Agent lifecycle | explicit synchronous, thread-safe, process-local lifecycle | Incomplete for kernel needs | Reuse conservative permission semantics if composition needs them; PostgreSQL remains authority and restart source |
| Media collection coordinator | explicit bounded discovery/observation cycle, process-local accumulation/replay | Incomplete for kernel needs | Reuse port/cycle semantics; move durable candidate/fact authority to repositories and make cycles reconstructable |
| Local filesystem discovery | bounded, shallow, read-only, symlink/race-aware adapter | Usable as-is | Invoke only for configured bindings; preserve per-cycle bounds and Windows identity limitations |
| Media Resource Observation collection | explicit ports and immutable observation contracts | Incomplete for kernel needs | Implement bounded concrete collectors and durable fact registration; no continuous implicit watcher |
| Readiness | conservative deterministic policy and typed outcomes | Usable as-is | Evaluate persisted objective facts synchronously with explicit policy identity/version |
| Completed Media Asset | immutable contracts, validation, manifest/provenance meanings | Usable as-is | Add assembler and registry around the existing contract; do not weaken it to fit candidates |
| Clocks/time | injected `SystemClock`/`FixedClock`, strict aware validation | Usable as-is | Inject at composition; store aware instants and keep timestamp meanings separate |
| Repositories | ingress PostgreSQL; Operational State and coordinator stores process-local | Incomplete for kernel needs | Keep protocols/test doubles; add approved PostgreSQL repositories without authoritative memory fallback |
| Health and routes | liveness-only `GET /api/v1/health` | Incomplete for kernel needs | Keep liveness; add readiness and read-only event/stage/media/recovery status routes |
| Operation/job/work | process-local operation IDs in Agent/coordinator only | Absent as a durable abstraction | Do not add a generic operation table in the first Kernel; use explicit synchronous cycles and reconciliation runs |
| Node implementation | Runtime profile/host contracts, no Node service | Future placeholder | Treat the current Windows Razer as a reference environment, not a Windows-specific domain tier |

No current component owns a composed, durable candidate-to-Session workflow. Process-local
Agent, coordinator, or Operational State history is not restart authority.

## First coherent operational slice

```mermaid
flowchart LR
    Config[Versioned deployment config] --> Validate[Validate effective config and Runtime]
    Validate --> DB[Connect to local PostgreSQL]
    DB --> Context[Load Business Event and Stages]
    Context --> Reconcile[Startup reconstruction and source reconciliation]
    Reconcile --> Ready[Event readiness]
    Ready --> Cycle[Explicit bounded media cycle]
    Cycle --> Discover[Discover candidates]
    Discover --> Candidate[Durable candidate registry]
    Candidate --> Facts[Durable resource observations]
    Facts --> Evaluate[Deterministic readiness evaluation]
    Evaluate --> Asset[Assemble and register Completed Media Asset]
    Asset --> Ingress[Stable asset-registration Production Event ingress]
    Ingress --> Association[Session association / unresolved / conflict]
    Association --> Projection[Durable domain projections and status]
    Projection --> Query[Read-only Producer query boundary]
```

The timer or operator action that starts a media cycle is a process-local trigger, not
authoritative state. Each durable boundary is idempotent and a restarted process
re-enters the same flow from PostgreSQL plus a new bounded source reconciliation.

### Startup and shutdown ownership

The composition root should:

1. parse defaults, versioned config, non-secret environment overrides, opaque secret
   references, and controlled command overrides;
2. validate the full effective configuration and construct/validate `StageFlowRuntime`;
3. create the PostgreSQL connection owner and verify connectivity and schema
   compatibility;
4. load the selected Business Event, Stages, bindings, and current projections;
5. create a durable reconciliation-run record, scan configured sources within bounds,
   reconcile candidates/assets/associations, and complete or fail that run visibly;
6. declare event readiness only after required reconstruction/reconciliation succeeds;
7. expose liveness, readiness, and read-only status; and
8. stop accepting new cycles, finish or roll back the current database transaction, and
   release infrastructure resources on shutdown.

No source is modified, mounted, controlled, or deleted. Recording and livestream systems
remain independent and higher priority.

## Minimal authority model

The Event Management context owns Business Event, Stage, and Program Expectation
reference authority. The Production context owns the realized Session aggregate and its
production-media association/package state, consistent with ADR-0002. They relate by
immutable IDs and repository/application ports; neither context embeds or mutates the
other's aggregate.

### Business Event

The Python/domain name should remain `BusinessEvent` to avoid collision with
`ProductionEvent`. Its minimum durable facts are a StageFlow-owned immutable ID, display
name, lifecycle/mode suitable for event operation, active deployment reference, and
versioned external event/program references. Deployment configuration selects the
Business Event by StageFlow ID; it does not replace durable identity.

### Stage

A Stage has one immutable StageFlow ID, one Business Event ID, a stable operator-facing
name, versioned external Stage references, and references to configured source/storage
bindings. Binding configuration is deployment-specific; Stage identity is not a path,
host, recorder, or Runtime target.

At most one realized Session may be projected `presentation_active` for one Stage at a
time. Enforce the invariant in the Session transaction boundary, not only in UI code.
A competing active Session or observed source Stage that contradicts declared Session
Stage creates a durable conflict; unrelated Stages continue.

### Program Expectation

A Program Expectation has a StageFlow-owned immutable identity and append-only revisions
containing:

- Business Event ID and expected Stage ID when known;
- planned start/end with source timezone meaning preserved;
- title, speakers, format/status, and other approved planned-world fields;
- external source identity, source record/version, retrieval/receipt time; and
- optional links to zero or more realized Sessions.

It is produced from a `ScheduledActivity` or an authorized operator declaration. It is
external/declared context, not observed Session truth. One expectation can remain
unrealized; a realized Session can have no expectation; reconciliation can link them
without merging their identities.

### Session

The minimal aggregate owns:

- immutable Session, Business Event, and fixed realized Stage identities;
- current aggregate revision and creation/realization authority;
- references to Program Expectations without importing their claims as facts;
- machine boundary proposals with evidence/policy/model lineage;
- append-only human boundary decisions and the current authoritative projection;
- presentation-activity and media-package lifecycle projections as distinct meanings;
- asset-association decision IDs and current categorical outcomes;
- package revision membership and missing/unresolved/conflict prerequisites;
- attributable human completion decisions for a specific package revision; and
- correlation, reason, provenance, and distinct aware timestamps.

The Session stores associations to registered assets, not media content. It does not own
editorial clips, publication packages, deliveries, or archives in the first Kernel.

## Media association semantics

### Evidence and constraints

Association uses typed evidence, not one confidence score:

| Category | Examples | Kernel role |
| --- | --- | --- |
| Structural | asset source binding resolves to Stage; Session fixed Stage; Business Event match | Hard constraint; contradictory structural facts produce conflict |
| Deterministic temporal | unique active Session on that Stage; media occurrence/continuity overlaps declared or observed activity | Candidate for explainable automatic rule after Yellow approval |
| Observed production | presentation/recording activity and media arrival facts | Durable evidence; never sufficient when structural facts contradict |
| External expectation | planned Stage/time/title/speakers from Program Expectation | Context only; never sole authority |
| Inferred | speaker/content/model boundary output | Deferred initially; advisory evidence only |
| Declared | operator assigns/reassigns asset or resolves conflict | Authoritative, append-only, and attributable |

The first Kernel records `associated`, `unresolved`, or `conflict`, along with categorical
reason codes and evidence references. Unresolved and conflict do not block asset
registration or other safe asset-level processing.

Before completion, a new deterministic result can enrich unresolved evidence but must
not automatically move an already human-associated asset. Human reassignment appends a
new association decision. After completion, any new relevant asset or reassignment
creates a new package revision/correction-required projection; the earlier association
and completion records remain historical.

The first Kernel has no AI dependency. Model-derived association and boundary evidence
is deferred until its model/version/provenance and review behavior are separately
implemented.

## Operator epistemic state

The repository already distinguishes Production Event, Observation, Evidence,
Verification, and Operational State meanings. The Kernel should not add a generic
“fact” aggregate or generic fact table. It should add one small shared vocabulary for
query provenance while domain records remain typed:

- **Observed:** directly measured source fact.
- **Derived:** deterministic conclusion with rule/policy version and input references.
- **Inferred:** probabilistic or model conclusion with model/version, evidence, and
  confidence representation.
- **Declared:** authoritative human/operator action with actor and reason.
- **External:** claim from a named outside system and source revision.

Each exposed item carries only applicable first-class fields: kind, domain record ID,
source/actor, source/effective time, recorded time, rule/model/version, evidence/input
references, and supersession/current-revision information. Behavior-driving provenance
must not be hidden in metadata.

Observed resource facts, external expectation revisions, declared decisions, inferred
outputs used in decisions, and derived decisions that affect workflow are durable.
Ephemeral UI groupings and deterministic summaries are reconstructable. `Last media
arrived at 14:22:19` is observed; `source appears inactive` is derived; `Session probably
ended` is inferred; `producer confirmed the end` is declared; scheduled end is external.

## Deployment configuration

Use one schema-versioned TOML deployment file parsed by Python's standard `tomllib`.
This is a bounded, reversible implementation choice and adds no dependency. Apply the
accepted precedence: code/schema defaults, versioned deployment configuration,
environment-specific non-secret overrides, infrastructure-resolved secret references,
then explicit controlled command overrides. Expose a redacted effective summary with
each value's source.

Minimum configuration sections are:

- deployment/config schema identity and selected Business Event ID;
- immutable node/Runtime identity and role/profile;
- StageFlow Stage IDs plus descriptive validation fields;
- Runtime capabilities, collection plans, explicit source/storage bindings, readiness
  policies, resource budgets, and production-subordinate pressure behavior;
- PostgreSQL DSN **secret-reference name**, never the DSN/credential itself;
- event-mode and network policy; and
- optional schedule-adapter/source references.

| Kind | Examples | Authority rule |
| --- | --- | --- |
| Deployment fact | node ID, Runtime profile, binding location, adapter capability | Versioned configuration; changes produce a new effective config |
| Operator choice | selected Business Event, enabled Stage bindings, budgets, policy selection | Configuration/controlled override with source shown |
| External reference | schedule source/event/stage IDs | Versioned reference only, never StageFlow identity |
| Runtime-observed fact | database reachability, source presence, byte size, last media arrival, pressure | Measured at runtime; configuration cannot override it |

Configuration validation rejects credential-bearing source references, unknown IDs,
duplicate/conflicting bindings, event-mode network requirements, invalid Runtime graphs,
and secrets that cannot be resolved. Liveness may remain up for diagnostics, but event
readiness stays false.

## Persistence and transaction boundaries

ADR-0022 fixes PostgreSQL and media-by-reference. The initial schema shape remains Yellow.
Regardless of the chosen physical schema:

- aggregate changes and their decision/history record commit atomically;
- candidate/resource/asset identities use database uniqueness and exact replay/conflict
  handling;
- asset registry commit precedes stable asset-registration Production Event ingress;
- Session association never occurs before the asset is registered;
- current projections are rebuildable from durable aggregate/history records;
- source absence never deletes a candidate or asset automatically; and
- there is no authoritative process-memory fallback.

Use the existing explicit numbered forward/reversal migration style. Each migration
requires isolated forward/reverse tests, reconstruction tests, identity/lineage
preservation, and an operator-controlled reversal scope. Backup/restore qualification is
required before event deployment, not merely before unit development.

Kernel operational truth consists of the typed aggregate/registry records plus their
current projections. Where the existing Operational State acceptance lineage is used,
add a backward-compatible realized-Session subject and a PostgreSQL implementation of
its repository protocol. That repository persists an explainable projection; it does
not own Session lifecycle or replace the Session aggregate.

## Failure behavior

The status words describe different scopes and should not become one universal enum:
`degraded` means useful work continues with reduced capability; `unavailable` means a
dependency cannot currently serve; `blocked` means a specific required transition cannot
proceed; `deferred` means work is intentionally postponed; `unresolved` is domain
ambiguity; and `operator_action_required` identifies a safe workflow that needs human
authority.

| Condition | Required first-Kernel behavior |
| --- | --- |
| PostgreSQL unavailable | Keep process liveness/diagnostics where possible; set event readiness unavailable; stop authoritative cycles/writes; never fall back to memory; recording remains untouched |
| PostgreSQL returns | Reconnect, verify schema, reconstruct state, run durable reconciliation, and remain recovering/not ready until required reconciliation completes |
| Shared storage unavailable | Mark binding unavailable and affected discovery deferred; preserve prior candidates/assets; do not infer deletion or Session end; other bindings continue |
| Shared storage returns | Start a bounded reconciliation for that binding; deduplicate discoveries and expose recovery progress |
| Watched/configured source disappears | Record an observed absence/unavailable fact; preserve history and retry only under bounded policy; no source mutation |
| Stage media stops arriving | Record last-arrival fact and optionally derive inactivity; do not infer Session end, settling, or completion from silence |
| Duplicate media event/discovery | Resolve through durable identity to replay; do not duplicate candidate, asset, Event, association, or downstream effect |
| File replaced during inspection | Return the existing typed transient replacement/conflict outcome, commit no misleading observation/readiness result, and defer to a later bounded cycle |
| StageFlow restarts | PostgreSQL is authority; reconstruct, create a reconciliation run, rescan configured sources, and expose not-ready/recovering until coherent |
| Program expectation conflicts with observed Stage | Preserve both claims and a conflict; keep media registered/processing; require operator action for the affected Session only |

## Minimum Producer query model

Read-only queries should answer domain questions without becoming a system-monitoring
platform:

- **Event status:** selected Business Event, event mode, overall ready/degraded/
  unavailable/recovering projection, configuration revision, and attention count.
- **Stage status:** binding health, current active Session projection, last observed media
  arrival, candidate/readiness/registered counts, and current conflicts.
- **Session status:** Program Expectation links, proposed/declared boundaries, activity
  projection, package revision/state, associated/unresolved/conflicting asset counts,
  completion authority, and required actions.
- **Media status:** candidate identity, last observation, readiness policy/result,
  Completed Media Asset registration, association outcome/reasons, and provenance.
- **Dependency status:** PostgreSQL and configured source reachability expressed in terms
  of blocked/deferred workflow impact.
- **Recovery status:** startup/reconciliation run identity, start/end, scope, progress,
  outcome, last error category, and whether readiness was restored.
- **Attention feed:** unresolved associations, structural/schedule conflicts, unavailable
  bindings, correction-required packages, and failed reconciliation, ordered by domain
  urgency and time.

The existing liveness endpoint remains separate. Readiness/status routes must not expose
secrets or raw credential-bearing locations.

## Operations/jobs recommendation

Do **not** introduce a generic durable Operation/Job model in the first Kernel. Discovery,
observation registration, readiness evaluation, asset assembly/registration, synchronous
Production Event dispatch, and deterministic association evaluation are bounded direct
calls whose durable effects commit at their owning repositories. A process timer only
requests the next cycle.

Persist a narrow `ReconciliationRun` with identity, scope/binding, state, start/end,
checkpoint/progress, result, and error category because restart recovery is itself an
operator-visible Kernel behavior. It is not a general leased work queue.

Create a durable Operation ADR only when the first genuinely long-running, retryable, or
externally dependent consumer exists, such as transcription, rendering, transfer, or
delivery. At that point evaluate identity, target, attempts, claim/lease, retry timing,
cancellation, results, and an outbox against the real consumer. Do not add a broker by
default.

## Windows Razer reference-node validation

The current Razer is the first physical Event Node reference environment, not a separate
semantic tier. Qualification should occur incrementally:

| Milestone | Real-machine validation |
| --- | --- |
| Composition/config | Service account context, TOML/env secret resolution, invalid config, redacted effective summary, controlled startup/shutdown |
| PostgreSQL stores/migrations | Local PostgreSQL startup/connectivity, forward/reverse on isolated data, concurrent identity, abrupt client termination, backup/restore rehearsal |
| Filesystem observation | Local/mounted/shared storage, disappearance/return, directory/file replacement, access denial, timestamp/identity limitations |
| Restart/reconciliation | Clean restart, forced process termination, database reconnect, source reconciliation, no duplicate assets/associations, readiness recovery |
| Event endurance | Event-length run with representative file cadence, bounded memory/handle growth, database/storage footprint, CPU/IO/GPU budgets |
| Production coexistence | Resource pressure and throttling/suspension without affecting primary recording/livestream workloads |
| Host behavior | Sleep/hibernate disabled for qualification, lid/power-plan and restart behavior documented, local-network loss/recovery simulated safely |

A future Event Node Qualification Suite should combine repository tests, fault-injection
scripts, a synthetic non-customer media fixture, runbook checklists, and retained result
evidence. Passing developer tests is not event-readiness certification.

## Green implementation boundaries

With ADR-0024 recorded, the following is Green within the approved,
implementation-ready plan:

- load and validate schema-versioned TOML using accepted precedence and opaque secret
  references;
- construct existing Runtime contracts and a narrow composition root;
- add explicit PostgreSQL repositories/migrations that implement the approved schema;
- reuse discovery, observation, readiness, Completed Media Asset, ingress, dispatch, and
  clock contracts without semantic weakening;
- add bounded collectors, assembler/registry, startup reconstruction, reconciliation,
  read models, and read-only status routes;
- add behavior-first unit, integration, migration, concurrency, replay, restart, fault,
  and Razer qualification tests; and
- update directly affected current architecture and completion records.

No Green boundary authorizes provider/cloud work, AI, editorial/publication workflows,
new infrastructure, public compatibility breaks, destructive migration, production
deployment, or opportunistic Contract Stabilization follow-ups.

## Resolved Yellow decisions

ADR-0024 accepts Y-K01 through Y-K04. The original evidence, options, and tradeoffs are
retained below as decision history; they are no longer blockers.

### Y-K01: Business Event and Stage bootstrap authority

**Question:** How are the first StageFlow-owned Business Event and Stage records created,
and what role does deployment configuration have after creation?

**Evidence:** ADR-0023 requires StageFlow-owned identities; configuration must select an
Event; no Event/Stage aggregate or command exists; multiple future nodes may share the
database, so node-local configuration cannot silently create competing authority.

**Options:**

1. **Explicit idempotent operator bootstrap command; config references existing IDs
   (recommended).** Clear authority and multi-node behavior; adds one deliberate setup
   step.
2. Versioned deployment config automatically upserts Event/Stages. Simple first-node
   setup, but configuration becomes shared-domain mutation authority and conflicts need
   resolution.
3. External schedule import creates Event/Stages. Convenient, but grants an external
   system authority rejected by ADR-0004/ADR-0023.

**Blocked work:** aggregate commands/repositories, startup selection, foreign-key
ownership, configuration validation, and multi-node bootstrap tests.

**Independent Green work:** configuration parsing/precedence/redaction and Runtime
validation can be designed/tested without making domain bootstrap authoritative.

### Y-K02: Realized Session creation authority

**Question:** What may create the first authoritative realized Session from a Program
Expectation or Session Candidate?

**Evidence:** The repository has deterministic boundary Evidence/policies but they only
propose Operational State. ADR-0023 requires explicit authority and human correction,
while schedule imports cannot create observed truth.

**Options:**

1. **Authorized human create/start command for the first Kernel (recommended).** Machine
   proposals remain evidence; safest authority and simplest recovery, with added operator
   workload.
2. An accepted deterministic start policy automatically realizes a Session when
   structural and evidence rules pass. Faster operation, but changes human/system
   authority and needs conservative conflict/replay rules.
3. Import creates anticipated Sessions that become realized at planned time. Easy, but
   collapses planned and observed reality and is not compatible with ADR-0023.

**Blocked work:** Session creation command, initial lifecycle transition, one-active-
Session constraint transaction, and startup/current-Session reconstruction.

**Independent Green work:** existing boundary Evidence/transition behavior and the
accepted immutable Session value invariants can receive repository-neutral test design.

### Y-K03: Initial automatic media-association authority

**Question:** May the Kernel automatically associate a registered asset when deterministic
context identifies one Session, or must every first association be human-declared?

**Evidence:** ADR-0020 requires explicit association/review outcome; ADR-0023 permits
evidence-driven association, makes human correction authoritative, rejects opaque
probability, and fixes Stage as a structural constraint.

**Options:**

1. Human-only association; deterministic logic only proposes. Maximally conservative,
   but creates avoidable event-time workload.
2. **Automatic only when one active realized Session exists on the same structurally
   bound Stage, no structural/human conflict exists, and the categorical rule and inputs
   are recorded (recommended).** Useful without AI and explainable; requires precise
   transaction/replay tests.
3. Weighted or model confidence above a threshold. Flexible, but opaque/inference-heavy
   and inappropriate for the first AI-free Kernel.

**Blocked work:** association policy, current-outcome transaction, operator correction,
and associated/unresolved/conflict acceptance tests. Asset registration itself can
proceed independently.

**Independent Green work:** candidate/observation/readiness/asset registry work and the
typed association evidence/outcome contracts do not require an automatic-authority rule.

### Y-K04: Initial relational schema and transaction ownership

**Question:** What PostgreSQL representation owns Business Event/Stage/Expectation/
Session current state and append-oriented decisions while preserving reconstruction?

**Evidence:** ADR-0022 selects PostgreSQL and explicit repositories; ADR-0023 requires
immutable identities and history but not full event sourcing; only the ingress schema
exists. Repository policy treats a new schema architecture as Yellow.

**Options:**

1. **Normalized aggregate/current tables plus append-only expectation, boundary,
   association, package, completion, observation, and reconciliation records
   (recommended).** Clear constraints/querying and selective history, with more explicit
   migrations and transaction code.
2. Generic event-sourced ledger with projections. Complete replay narrative, but much
   larger execution/projection/compatibility burden without demonstrated need.
3. JSON document rows per aggregate plus a small history log. Fast initial modeling, but
   weaker relational constraints, conflict queries, and migration ergonomics.

**Blocked work:** migrations, repository interfaces/adapters, transaction boundaries,
reconstruction, read models, and backup/restore validation.

**Independent Green work:** repository-neutral aggregate contracts, failure taxonomy,
PostgreSQL environment inventory, and migration/test design can proceed without selecting
the physical schema.

After Y-K01 through Y-K04 are decided and recorded in accepted ADR/plan authority, no
other known architecture decision blocks the bounded first-Kernel implementation.

## Explicitly deferred

- transcript, vision/model inference, editorial selection, rendering, publication,
  delivery, archive, retention/deletion, and cloud/provider execution;
- generic Durable Operations, worker leases, transactional outbox, broker, or
  microservices;
- Session split/merge, cross-Stage movement, and AI-authoritative association;
- publication-era late-media policy, default grace durations, and full package manifests;
- multi-node work distribution, dedicated Node hardware semantics, and production
  deployment;
- authentication/authorization product design beyond an explicitly controlled local
  operator boundary; and
- full Producer UI, Grafana-style infrastructure monitoring, and general incident
  management.
