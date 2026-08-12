# Accepted architecture principles

This document records only principles accepted by the Product Constitution, existing
ADRs, or the authoritative architecture-baseline disposition. “Accepted” does not mean
“implemented”; each principle states its current alignment.

## 1. Backend-first, UI-independent domain

- **Statement:** Core domain facts, policies, and workflows do not depend on a specific
  UI, HTTP framework, provider, or deployment surface.
- **Operational rationale:** Technical producers, event operations, editorial,
  marketing, machine management, and administration need different interfaces over the
  same stable behavior.
- **Implications:** FastAPI and Next.js remain adapters/interfaces. Domain decisions live
  in backend context/application boundaries and expose stable contracts or durable state.
- **Non-goals:** A headless-only product or a ban on workflow-specific UI composition.
- **Current alignment:** **Aligned.** Production packages do not depend on FastAPI or the
  frontend; the frontend is currently only a static shell.
- **Related decisions:** Product Constitution; ADR-0001; ABR-016 disposition.

## 2. Modular monolith before distributed services

- **Statement:** StageFlow remains one modular backend with explicit internal boundaries
  until measured operational evidence justifies a distributed boundary.
- **Operational rationale:** A modular monolith provides transactions, simpler recovery,
  and lower event-day operating complexity.
- **Implications:** Use direct synchronous calls for deterministic domain decisions. Add
  durable asynchronous operations only for long-running, retryable, or external work.
- **Non-goals:** Microservices, a message broker, or replacing every direct call with an
  event.
- **Current alignment:** **Aligned.** The backend is one application; no broker or remote
  internal service exists.
- **Related decisions:** ADR-0001; ADR-0022; disposition D-02 and D-03. Worker details
  remain open.

## 3. Event-mode operation is locally capable

- **Statement:** The event-critical production path must operate without continuous
  Internet access, and network-dependent work must be explicit, visible, and deferrable
  where approved.
- **Operational rationale:** Conference networks and external providers are unreliable;
  local production must continue under degraded connectivity.
- **Implications:** Local media ingest and durable state cannot require cloud services.
  Provider work records retry/defer state when introduced.
- **Non-goals:** A claim that the current bounded Kernel is a complete offline
  event workflow, or a ban on optional cloud enhancement.
- **Current alignment:** **Partially aligned.** The composed Kernel loads local
  configuration, uses PostgreSQL authority, runs bounded filesystem media cycles and
  source/restart reconciliation, and exposes status without cloud calls. Continuous
  ingest and downstream processing/delivery workflows are not implemented.
- **Related decisions:** Product Constitution principles 9–11; ABR-017 disposition.

## 4. Session is a first-class durable concept

- **Statement:** StageFlow owns an immutable Session ID and treats Session as a durable
  domain concept, while external schedule/recorder IDs remain versioned references.
- **Operational rationale:** Media, transcript, editorial decisions, finalization, and
  delivery need one stable workflow identity that survives external corrections.
- **Implications:** Scheduled activity, observed Session Candidate, Timeline Window
  Candidate, Session Window Product, Operational State, media completeness, editorial
  finality, packaging, and delivery remain distinct concepts.
- **Non-goals:** Treating a directory, schedule record, observed candidate, or Operational
  State as the Session aggregate.
- **Current alignment:** **Implemented for the bounded Kernel.** StageFlow-owned Session
  identity, Event/Stage ownership, authoritative boundaries, package revision/completion
  history, approved asset membership, human-command replay, and restart reconstruction
  are durable in PostgreSQL. Editorial finality, delivery, and broader late-media policy
  remain outside the implemented slice.
- **Related decisions:** ADR-0002, ADR-0023, and ADR-0024; disposition D-01 and D-06.

## 5. Segment-based ingest preserves semantic boundaries

- **Statement:** Shared-storage media is handled in small source segments, while
  discovery, objective resource observation, readiness, completed-asset registration,
  Session association, and editorial meaning remain separate.
- **Operational rationale:** A file may be visible before it is complete; storage
  boundaries must not become editorial boundaries.
- **Implications:** A Media Asset Candidate is not a Completed Media Asset. Readiness has
  one explicit policy authority. Incomplete or merely discovered files do not emit
  completed-segment Events.
- **Non-goals:** Recursive scanning, a stateful watcher-manager, fixed 60-second identity,
  or exposing source files as Editorial Clips.
- **Current alignment:** **Implemented for bounded explicit cycles.** Shallow read-only
  discovery, objective observations, readiness, Completed Media Asset registration,
  stable ingress, conservative Session association, persistence, and reconciliation are
  composed as separate boundaries. Continuous watching and downstream editorial work
  remain absent.
- **Related decisions:** ADR-0003, ADR-0020, disposition D-05, ABR-008/016.

## 6. Operational state is durable before automation

- **Statement:** Continuous ingest or background processing must not rely on process
  memory for identity, progress, replay, or recovery.
- **Operational rationale:** Processes, machines, storage, and providers fail during live
  events; predictable reconstruction matters more than clever runtime abstractions.
- **Implications:** The first operational kernel uses one relational durable store inside
  the modular monolith, media content by reference, durable ingress/operation records,
  idempotent commits, and startup reconciliation.
- **Non-goals:** Full event sourcing, exactly-once claims, or durable infrastructure before
  operational behavior needs it.
- **Current alignment:** **Implemented for Kernel authority.** PostgreSQL migrations
  `0001` through `0005` preserve ingress, Event/Stage/Session/media current state, typed
  history, completion membership, command replay, and reconciliation. Runtime
  composition, startup reconstruction, dependency recovery, and bounded backup/restore
  qualification exist; production deployment operations and generic workers do not.
- **Related decisions:** ADR-0019; ADR-0022; disposition D-02, D-03, and D-09.

## 7. Processing is incremental, explainable, and human-authorized

- **Statement:** Work begins when sufficient information exists, preserves the reasoning
  chain, and does not let machine suggestions bypass human editorial/verification
  authority.
- **Operational rationale:** Live production benefits from early results, but trust
  requires traceable observations, evidence, hypotheses, findings, and decisions.
- **Implications:** Production Events precede Semantic Observations; meaning begins after
  observation; Verification Decisions are append-only; Operational Products follow
  verified reasoning.
- **Non-goals:** Autonomous publication, opaque cross-domain inference in interpreters,
  or waiting for an entire Session when partial work is safe.
- **Current alignment:** **Partially aligned.** Contracts and policies exist; no durable
  orchestrated reasoning/editorial workflow exists.
- **Related decisions:** ADR-0009, ADR-0011, ADR-0015, Product Constitution principles
  4–6 and 22–25.

## 8. Identity, time, provenance, and immutability are explicit

- **Statement:** Authoritative facts are first-class, immutable, and replay-stable;
  supplementary metadata is not an authority substitute.
- **Operational rationale:** Repeated delivery and restart must reproduce the same lineage
  and ordering across machines.
- **Implications:** Stable source and ingress identities are distinct; external/persisted
  times are timezone-aware; infrastructure time uses an injected clock; semantically
  distinct times remain separate; nested metadata is recursively immutable.
- **Non-goals:** Hashing mutable metadata into identity, silently attaching UTC to naive
  time, or treating deployment profile as a trust/identity tier.
- **Current alignment:** **Aligned at implemented Kernel boundaries.** Stable ingress,
  durable domain identity/history, strict aware timestamps, recursive metadata
  protection, deterministic association provenance, approved membership snapshots, and
  original-result replay are implemented. Downstream editorial/delivery replay remains
  future work.
- **Related decisions:** ADR-0019, ADR-0021, ADR-0022, ABR-003/005/006/016 dispositions.

## 9. External systems remain behind provider-neutral adapters

- **Statement:** StageFlow owns workflow, while schedule, publication, storage, and other
  external systems retain their own data authority behind explicit adapters.
- **Operational rationale:** Conference and provider changes must not reshape the core
  domain or make live operation vendor-dependent.
- **Implications:** Provider identifiers are external references; adapters translate and
  report source facts; provider payloads do not become core models.
- **Non-goals:** Implementing placeholder integrations, hard-coding a conference, or
  rejecting all external services.
- **Current alignment:** **Aligned at the contract boundary.** No provider implementation
  or SDK is currently present.
- **Related decisions:** ADR-0004, ADR-0005, ADR-0011, ABR-017 disposition.

## 10. Operator visibility grows with operational capability

- **Statement:** Every operational workflow must expose durable, actionable state for
  activity, waiting, failure, retry, connectivity, intervention, and finalization safety.
- **Operational rationale:** A live operator must distinguish liveness from readiness and
  degraded operation from silent failure.
- **Implications:** Operator views derive primarily from durable domain/operation state;
  structured logs and metrics supplement rather than replace it.
- **Non-goals:** Building a complete producer UI before backend status exists, or
  interpreting an HTTP liveness response as event readiness.
- **Current alignment:** **Implemented for the bounded Kernel.** `/api/v1/health`
  remains liveness-only, while `/api/v1/kernel/status` separately reports configuration
  validity, composition, PostgreSQL/source availability, reconciliation/recovery,
  bounded Session/media projections, and readiness. Full operator workflow interfaces
  and future worker visibility remain unimplemented.
- **Related decisions:** ABR-011 disposition; D-02/D-03/D-08 dependencies.

## 11. Evolution is bounded, evidence-led, and reversible

- **Statement:** Architecture and implementation progress through small, independently
  reviewable decisions, plans, and Engineering Directives.
- **Operational rationale:** Narrow changes preserve confidence in a contract-heavy
  foundation and avoid turning future direction into accidental current requirements.
- **Implications:** Reviews require dispositions; unresolved decisions stay visible;
  migrations and dependencies require explicit plans; historical records are preserved.
- **Non-goals:** Repository-wide cleanup, aesthetic abstraction, or implementing every
  placeholder context.
- **Current alignment:** **Mostly aligned.** Directive increments and tests are strong;
  this framework closes the architecture/documentation navigation gap.
- **Related decisions:** Disposition D-10 and Phase 1; ABR-014/015/016.
