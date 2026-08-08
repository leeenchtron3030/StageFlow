# StageFlow Master Project Brief

**Status:** Working project baseline

**Purpose:** Concise, human-readable orientation to StageFlow's product intent,
operating model, architecture, current maturity, development workflow, and near-term
direction.

## Authority and use

This brief is a project-level orientation document. It summarizes accepted architecture,
verified current implementation, and current direction; it does not replace the detailed
sources that govern StageFlow.

- The [Product Constitution](../PRODUCT_CONSTITUTION.md), specific
  [architecture documents](architecture/README.md), and accepted
  [Architecture Decision Records](adr/README.md) take precedence where they are more
  specific.
- [Implementation plans](plans/README.md) govern approved bounded changes. A plan does
  not decide unresolved architecture.
- [Reviews](reviews/README.md) are analysis artifacts unless their findings are accepted
  through a disposition. The
  [architecture-baseline disposition](reviews/architecture-baseline-disposition.md), not
  the source review alone, records the accepted outcome of that review.
- [Engineering Directives](../ENGINEERING_DIRECTIVES.md) authorize bounded implementation
  scope without silently revising higher-level decisions.
- This brief should change when the project-level story changes, not for every Engineering
  Directive.

The status labels below are deliberate:

- **Implemented today:** verified repository behavior or contracts.
- **Accepted direction:** approved architecture that may not be implemented.
- **Planned future capability:** expected work still requiring an approved bounded plan.
- **Open decision:** product or architecture judgment remains unresolved.

## 1. What StageFlow is

StageFlow is a local-first observational intelligence and media-workflow system for
conferences, live events, and multi-stage productions.

Its purpose is to turn continuously arriving event media and supporting production
signals into structured, explainable production information while an event is still in
progress. StageFlow is intended to help production teams:

- monitor Stages, recording systems, media arrival, and processing state;
- ingest completed media segments safely from shared storage;
- incrementally create transcripts, analysis, and editorial candidates;
- preserve identity, time, context, and provenance throughout the workflow;
- assist human editorial and marketing teams without replacing their authority;
- produce reviewable media, metadata, packaging, and delivery outputs; and
- continue event-critical work when Internet connectivity is limited or unavailable.

StageFlow is not the primary video-production system. Existing production tools continue
to record and livestream the Business Event while StageFlow observes and processes their
outputs.

## 2. Event operating model

### Production comes first

Production networks, recording, livestreaming, intercom, show control, and other
mission-critical systems have priority over StageFlow processing and cloud access.

The **accepted direction** is local-first event-mode operation:

- the event-critical path does not require continuous Internet access;
- network-dependent work is explicit, observable, bounded, and deferrable where
  approved;
- cloud capabilities may enhance the workflow but may not become hidden dependencies;
- deterministic domain decisions use direct synchronous calls; and
- long-running, retryable, compute-heavy, or external work becomes a Durable Operation
  only when that operational need exists.

**Implemented today:** current contracts make no cloud calls and the bounded filesystem
adapter is local and read-only. This is not a complete offline event workflow: no composed
production runtime currently exists.

## 3. Media ingest model

The preferred ingest path uses completed media files written to shared storage rather
than requiring StageFlow to consume continuous NDI/SDI video feeds.

An event deployment may choose relatively small recorder source segments—roughly one
minute is a practical starting point—but segment duration is not an identity rule,
readiness proof, or architectural invariant.

The **accepted media flow** is:

```text
Shared storage
  -> Media Asset Candidate
  -> persisted candidate identity and provenance
  -> Media Resource Observations
  -> readiness evaluation
  -> immutable Completed Media Asset assembly
  -> durable media registration
  -> stable asset-registration Production Event
  -> authoritative Session association or review state
  -> approved Durable Operations
  -> transcript / analysis / editorial outputs
  -> human review and decisions
  -> Session finalization
  -> packaging / delivery / archive
```

These distinctions are protected:

> Discovery is not readiness.
>
> Readiness is not registration.
>
> Registration is not Session association.
>
> Session activity ending is not final publication.

**Implemented today:** one explicit, synchronous, shallow, bounded filesystem discovery
call can return Media Asset Candidates. Contracts and deterministic policy exist for
supplied Media Resource Observations, readiness evaluation, and Completed Media Assets.

**Not implemented:** repeated observation ownership, readiness orchestration, asset
assembly, a durable media registry, asset-registration Event emission, Session
association, restart reconciliation, or automatic downstream scheduling.

## 4. Session

Session is an **accepted future first-class durable StageFlow concept** representing the
complete logical media package for one actual on-stage substantive presentation or
discussion, including Q&A when it is part of the presentation. Multiple files may
contribute to one Session. It is not a file, directory, recording process, planned
program record, Session Candidate, Timeline Window Candidate, Session Window Product, or
Operational State.

The accepted identity direction is:

- StageFlow assigns one immutable Session ID.
- Schedule-platform, recorder, and other provider IDs are versioned external references.
- A Program Expectation preserves planned-world information separately from actual
  observed Session activity; expectation does not silently create authority.
- Substantive presentation/discussion activity, not introduction or schedule time,
  determines normal observed boundaries.
- Once activity begins, the Session belongs to one Business Event and exactly one fixed
  Stage.
- Operational State remains an assertion or projection about a subject, not the Session
  aggregate.
- Media association is evidence-driven with associated, unresolved, and conflict
  outcomes; human assignment/correction is authoritative.

A future Session may connect a Business Event, Stage, scheduled activity, observed
timing, Recording Blocks, media, speakers, transcript revisions, analysis, editorial
decisions, final assets, packages, and delivery operations.

**Implemented today:** independent Session-related windows, products, transition policy,
acceptance contracts, and a process-local Operational State repository exist. There is
no authoritative Session entity, creation command, durable repository, schema, or API.

### Session finality is multi-dimensional

The **accepted direction** distinguishes planned expectation, presentation activity,
media assembly, and human review. Human approval of one Session package revision is
required before the Session is complete. Apparent activity end, recording stop,
inactivity, or grace expiration is insufficient.

Later concerns remain separate:

- editorially final;
- publication package complete;
- published or delivered; and
- archived.

These are milestone meanings, not implemented enum names. Analysis reconciliation may
also be tracked by future workflows, but its exact ownership and relationship to these
accepted milestones remain to be designed.

Late valid media preserves the earlier completion decision and returns the current
Session package to correction/review. Post-publication behavior and grace defaults remain
open.

## 5. Incremental intelligence and human authority

StageFlow should produce useful information as soon as sufficient facts exist rather
than waiting for a whole Session to finish. Planned capabilities include:

- partial transcripts;
- speaker and content metadata;
- chapters and topic boundaries;
- Semantic Observations and explainable reasoning;
- Editorial Candidate Moments and candidate clips;
- quality-control signals; and
- searchable Session metadata.

Later media may extend, supersede, merge, re-rank, or reconcile earlier machine outputs
without destroying their provenance or reasoning history.

Machine analysis is advisory. Human editorial and verification decisions remain
authoritative for selection and publication.

**Implemented today:** contracts and deterministic policies exist from Production Events
through Semantic Observations, Evidence, reasoning values, verification, Operational
Products, transition evaluation, and acceptance. No durable orchestrator, transcript
runtime, AI analysis runtime, editorial workflow, or publication workflow invokes and
persists this chain.

## 6. Human operational roles

StageFlow is designed around operational personas that may use different interfaces over
the same domain and APIs.

### Producer

The future Producer experience is mission control rather than a media editor. It should
show source and recording status, active Sessions, segment arrival, readiness, storage,
processing, worker/GPU utilization, network-dependent work, retries, failures,
finalization safety, and delivery state. It should make required intervention obvious.

### Editorial

The future Editorial experience should combine Session media, transcripts, search,
chapters, AI-supported moments, source timestamps, confidence and provenance, human
approval/rejection, clip creation, and metadata refinement. It assists editorial judgment
rather than replacing an editor.

### Marketing

The future Marketing experience should consume approved editorial outputs and Session
context: clips, images, speaker details, summaries, suggested copy, campaign metadata,
publishing status, and delivery coordination.

**Implemented today:** none of these workflow interfaces or APIs exists. The Next.js
application is a static shell and FastAPI exposes process liveness only.

## 7. Backend and deployment philosophy

StageFlow is backend-first and UI-independent. The accepted architecture is a modular
monolith with explicit internal boundaries.

Core behavior belongs in domain contracts, application services, commands, repositories,
and explicit ports—not inside FastAPI routes, startup code, or role-specific interfaces.
Direct calls are appropriate for simple deterministic decisions. Events and Durable
Operations are introduced for concrete needs such as replay, recovery, multiple
consumers, long-running execution, external side effects, or auditing—not for
architectural style.

The initial operational system remains one modular backend. Microservices, a broker, and
a distributed internal topology require measured evidence before adoption.

## 8. Persistence and recovery direction

StageFlow assumes processes crash, machines restart, notifications repeat, files arrive
out of order, providers time out, workers disappear, connectivity fails, and late media
arrives.

The **accepted direction** is one relational durable store inside the modular monolith.
Media content remains outside the database and is referenced by durable records.
Append-oriented records or ledgers are used where lineage, replay, idempotency, and human
decision history require them; full event sourcing is not required.

Future durable state must reconstruct Sessions, registered media, operations and
attempts, analysis outputs, editorial candidates, human decisions, finalization,
packages, delivery attempts, and archive/retention state. At-least-once execution,
idempotent commits, and startup reconciliation are preferred over exactly-once claims.

**Implemented today:** PostgreSQL is selected as authority and one durable ingress
schema/repository with explicit forward/reversal migration exists. It is not composed
into application startup. No durable media registry, operation store, outbox, or restart
reconciliation exists; other repositories and runtime histories remain process-local.

## 9. Workers, providers, and configuration

### Workers and AI processing

Future Durable Operations are appropriate for transcription, model analysis, vision,
rendering, clip generation, upload, and external delivery. The first worker model should
remain database-backed inside the modular monolith with stable operation identity,
claims or leases, attempt history, bounded retry, offline deferral, idempotent result
commit, and operator-visible state.

**Not implemented:** workers, claims, leases, attempts, retry scheduling, GPU scheduling,
transcription, model inference, rendering, and delivery execution.

### Provider isolation

StageFlow's core must not structurally depend on a specific LLM, transcription engine,
vision model, cloud platform, conference system, storage provider, or publishing service.
Provider request/response formats remain behind adapters. This permits local processing
during an event and optional cloud processing later without redefining the domain.

### Configuration

The accepted configuration precedence is:

1. code and schema defaults;
2. versioned deployment configuration;
3. environment-specific non-secret overrides;
4. infrastructure-resolved secret references; and
5. explicit controlled command overrides where justified.

Runtime-observed facts cannot be overwritten by configuration preference. Operators
should be able to inspect the effective non-sensitive configuration.

**Open decisions:** file format, secret resolution, schema lifecycle, and deployment
distribution. No authoritative production configuration loader currently composes a
Runtime graph.

## 10. Current repository maturity

The architecture-baseline review accurately characterized StageFlow as a strong
domain-contract and deterministic-policy foundation rather than a composed operational
event system. No Critical or High current-code defect was confirmed at that baseline.

The review's **1,461 passing backend tests plus clean Ruff, Pyright, and frontend checks**
are historical evidence for reviewed commit `e75b1a4`, not a permanent current-suite
count or a claim of event-operational readiness. Current validation belongs in the
relevant implementation plan, review, CI result, or change report.

### Implemented today

- Python 3.13/FastAPI health shell and a static Next.js shell.
- UI-independent modular backend contracts and deterministic policies.
- Provider-neutral Production Event and adapter contracts.
- Stable source-key/versioned-fingerprint ingress contracts and a PostgreSQL repository
  foundation, not yet application-composed.
- Six concrete Observation Interpreters and extensive reasoning/state contracts.
- Process-local Runtime, Software Agent, collection coordinator, and in-memory
  Operational State repository.
- One synchronous, stateless, bounded local-filesystem candidate-discovery adapter.
- Readiness policy and Completed Media Asset contracts without operational assembly or
  persistence.
- Dispatcher/Observation Interpreter compatibility implementation completed and accepted
  by fresh independent Codex review; phase-level human acceptance remains pending.
- Recursive metadata immutability completed across the legacy shallow-freeze boundary
  and accepted by fresh independent review.
- Local-filesystem discovery race hardening completed with descriptor-relative binding
  where supported, bounded fallback revalidation, and fresh independent acceptance.

### Not implemented today

- A composed Production runtime or application composition root.
- Durable production persistence beyond ingress, application composition, or restart
  recovery.
- An authoritative Session repository.
- Continuous ingest, filesystem watching, or repeated resource observation.
- Operational workers, Durable Operation persistence, retries, or reconciliation.
- Transcription, AI analysis, Editorial, Marketing, packaging, publishing, distribution,
  archive, or retention runtimes.
- Producer, Editorial, or Marketing workflow APIs and interfaces.

## 11. Current engineering phases

### Phase 1 — Development-flow foundation

The repository now contains the root instructions, architecture index and principles,
system context, domain glossary, Session and media lifecycle documents, ADR framework,
review/disposition framework, and implementation-plan framework. The configured Linux CI
workflow enforces the existing backend pytest/Ruff/Pyright and frontend
build/lint/typecheck matrix; it does not prove event-operational behavior or Windows
support.

### Phase 2 — Contract-boundary stabilization

The accepted independent corrections are:

1. stable ingress identity;
2. Dispatcher/Observation Interpreter compatibility;
3. timestamp invariants;
4. recursive metadata immutability; and
5. filesystem discovery race hardening.

The Dispatcher/Observation Interpreter compatibility implementation and final hardening
are recorded as **Completed — independent review accepted**. Recursive metadata
immutability, local-filesystem discovery race hardening, and CI quality-matrix
enforcement are also completed and independently accepted. Durable ingress identity and
the strict-aware timestamp transition are implemented under the approved PostgreSQL and
time decisions. Final independent verification accepts phase entry with one non-blocking
commit-reviewability limitation. Runtime composition is still absent.

### Phase 3 — Durable event-mode kernel

Architecture/design is captured in the Durable Event-Mode Kernel architecture and plan.
The implementation candidate includes deployment configuration, persistence beyond ingress, Event/
Stage/Session authority, a durable media registry, startup reconciliation, an application
composition root, readiness/dependency health, and minimal operator status APIs. A
generic durable Operation system is deferred until a genuinely asynchronous/external
consumer exists. ADR-0024 resolves the four former Yellow decisions. Deployment Runtime
construction, automatic startup discovery/observation composition, and full reference-
node qualification remain Green work before independent phase acceptance.

### Phase 4 — First operational media slice

A suitable first vertical workflow is explicit shared-storage discovery through durable
candidate registration, repeated resource observation, readiness, Completed Media Asset
registration, stable Production Event emission, Session association or review state,
durable reconciliation status, restart recovery, and operator visibility.

This slice does not need transcription, editorial analysis, packaging, or publishing to
prove the architecture.

## 12. Development workflow

The repository is StageFlow's long-term project memory. Significant work normally follows:

```text
Product or architecture discussion
  -> accepted decision
  -> architecture document or ADR
  -> repository-grounded investigation
  -> implementation plan
  -> execution-authority validation
  -> implementation
  -> automated validation and deliberate diff/self-review
  -> independent review when task or batch risk warrants
  -> human review at decision, phase, or readiness gates
  -> commit / pull request
```

The root [bounded autonomous execution policy](../AGENTS.md#bounded-autonomous-execution)
allows Codex to investigate, plan, implement, validate, and self-review Green work when
all consequential decisions are already accepted. Green plans do not require a separate
human approval turn. Yellow and Red conditions stop at their affected boundary for the
required architectural, human, or action-specific approval.

Fresh independent review should occur after higher-risk Green work or a logical batch of
related Green changes. Human review normally occurs at architecture decisions, phase
boundaries, release/event-readiness milestones, and Yellow or Red escalations rather
than between every bounded Green implementation.

Every significant implementation report should identify files and behavior changed,
tests, exact commands and results, deviations, remaining risk, and deliberately excluded
work.

ChatGPT is useful for product reasoning, architecture exploration, synthesis, decision
framing, and converting accepted conclusions into durable text. Codex is useful for
repository investigation, planning, implementation, tests, static analysis, migrations,
and diff-based independent review. Neither should silently decide unresolved product
architecture merely because code requires an answer.

## 13. Hardware strategy

Hardware remains downstream of software architecture. StageFlow may eventually use
locally owned event compute for transcription, model inference, vision, rendering, proxy
generation, and other GPU workloads, but no manufacturer or machine class is an
architectural dependency.

The working principle is:

> Build the operational workflow, measure representative workloads, then size hardware.

## 14. Key open decisions

### Session

- Creation and promotion authority.
- Scheduled/observed reconciliation, corrections, split, merge, and reassignment.
- Business Event and Stage ownership/reference lifecycles.
- Operator override and late-media reopening rules.

### Persistence

- Schema expansion and a migration-tool threshold beyond the explicit ingress runner.
- Event deployment topology, connection/secret ownership, backup, and recovery.

### Work execution

- Durable Operation and attempt schema.
- Claim/lease, cancellation, retry, and worker deployment semantics.
- GPU resource ownership and scheduling.

### Media

- Canonical durable Source Segment/media-record terminology.
- Rename, alias, and multi-mount identity reconciliation.
- Snapshot-observation ownership and sampling policy.
- Media registry uniqueness/transactions and Session association authority.
- Grace-period defaults and late-media reopening/quarantine policy.

### Configuration and distribution

- Configuration format, secrets, schema lifecycle, and distribution mechanism.
- Package and delivery models, first external destination, outbox ownership, and detailed
  finalization/publication/archive state machines.

Open decisions must remain open until deliberately resolved through the applicable
architecture process.

## 15. Architectural non-goals

Unless evidence later justifies them, StageFlow avoids:

- premature microservices or a message broker;
- cloud-required event operation;
- mandatory direct NDI/SDI ingest;
- directories as Sessions or discovered files as completed media;
- Operational State as the Session aggregate;
- Session `ended` as a synonym for final delivery;
- operational truth held only in process memory;
- exactly-once assumptions;
- provider-specific core domain models;
- giant repository-wide refactors;
- generic abstractions without a concrete need;
- architecture encoded only in prompts; and
- AI automatically overruling human editorial decisions.

## 16. Definition of success

A successful StageFlow deployment lets an operator recover after a machine restart and
answer from durable evidence:

- What Business Event, Stages, and Sessions exist?
- What media arrived, remains active, is ready, and was registered?
- What is processing, completed, failed, retrying, or waiting for connectivity?
- Which Sessions appear ended, and is expected media settled?
- What did machine analysis identify and what did humans approve?
- What was packaged, delivered, or archived?
- What still requires intervention, and is finalization safe?

At the same time, Editorial can work with useful Session content while the event is in
progress, and Marketing can consume approved outputs without interfering with production
operations.

That combination—**operational reliability plus incremental production intelligence**—is
StageFlow's central objective.

## 17. Working project principle

StageFlow evolves through small, observable, reversible steps. Every new capability
should answer:

1. What durable fact does this introduce?
2. Who owns that fact?
3. Can StageFlow reconstruct it after a restart?
4. Can an operator understand what happened?

Clear answers allow the system to become more capable without losing reliability,
explainability, or human authority.
