# StageFlow Architecture Baseline Review — Disposition

**Review disposition date:** 2026-07-22
**Source review:** `docs/reviews/architecture-baseline-review.md`
**Source review commit:** `e75b1a4`

## Purpose

This document records the project-level disposition of the findings and recommendations in the StageFlow Architecture Baseline and Consistency Review.

The source review is an evidence-based analysis artifact. It does not independently establish StageFlow architecture or authorize implementation.

This disposition records which findings are:

* Accepted
* Accepted with qualification
* Deferred
* Rejected
* Requiring additional evidence
* Requiring a product or architecture decision
* Intentionally protected from unnecessary refactoring

Future Codex tasks must use this disposition, applicable ADRs, and approved architecture documents rather than treating the source review as direct implementation authority.

---

# Executive disposition

The review’s central assessment is accepted:

StageFlow currently provides a strong, well-tested domain-contract and policy foundation. It does not yet provide a composed, durable, restart-safe event media workflow.

This is consistent with the project’s current development stage.

The immediate objective is not to implement the entire intended StageFlow system. The objective is to establish sufficient architectural authority and contract consistency to begin composing a narrow event-mode operational kernel safely.

The following existing characteristics are explicitly protected:

* Backend-first and UI-independent domain design
* Modular-monolith architecture
* Provider-neutral core contracts
* Local-first and offline-compatible direction
* Segment-based shared-storage ingest
* Separation between discovery, resource observation, readiness, and completed-media meaning
* Deterministic policies and explicit ports
* Immutable snapshots and typed outcomes
* Human authority over editorial and verification decisions
* Avoidance of premature microservices, brokers, and provider integrations
* Small, independently reviewable Engineering Directive increments

---

# Finding dispositions

## ABR-001 — Production behavior is not composed or durable

**Disposition:** Accepted with qualification
**Classification:** Current-state capability boundary, not a current defect
**Priority:** Architecture foundation; operational implementation required before event use

The running application does not compose the Production runtime, and meaningful state remains process-local. This is accepted as an accurate description of the current implementation.

The absence of a composed operational runtime is not considered a defect in the current contract-foundation phase. It becomes a blocking reliability issue when StageFlow begins automatically ingesting or processing event media.

### Approved direction

* Define a narrow application composition root.
* Introduce durable operational state before continuous ingest.
* Add startup reconciliation before relying on watchers or background loops.
* Keep the implementation within the modular monolith.
* Do not move domain logic into FastAPI route handlers or application startup code.
* Do not compose every existing conceptual package merely because it exists.

### Implementation status

Not yet authorized as one large implementation task. Dependent architecture decisions must be recorded first.

---

## ABR-002 — Session is not yet an implemented authoritative aggregate

**Disposition:** Accepted
**Classification:** Architectural gap requiring a formal decision
**Priority:** Architecture foundation before durable Session-dependent work

The review correctly identifies that Session-related values, windows, state subjects, and policies do not yet constitute an authoritative Session aggregate.

### Approved direction

StageFlow will treat Session as a first-class durable domain concept.

The eventual Session model must distinguish:

* Stable StageFlow Session identity
* Scheduled activity references
* Observed Session candidates
* Verified timeline or Session-window products
* Operational state
* Media-set completeness
* Editorial finality
* Packaging state
* Publication and delivery state

Operational State must remain a projection or accepted state assertion. It must not silently become the Session aggregate itself.

### Still requiring confirmation

* Exact Session creation authority
* Reconciliation between scheduled and observed Session identity
* Event and Stage ownership
* Operator creation and override behavior
* Late-media and reopening semantics

---

## ABR-003 — Legacy ingress identity is not replay-stable

**Disposition:** Accepted
**Classification:** Reliability risk
**Priority:** Correct before durable ingress composition

Repeated conversion of equivalent source facts must not generate unrelated durable ingress records merely because a new runtime invocation occurred.

### Approved direction

* Introduce stable ingress identity.
* Prefer trustworthy source-provided event identity when available.
* Otherwise use a versioned canonical fingerprint of authoritative source facts.
* Persist an ingress operation or source-event record before interpretation.
* Preserve the distinction between source identity, ingress identity, Production Event identity, and downstream Observation identity.
* Do not use mutable metadata in identity derivation.
* Do not rely on process-local replay maps for restart safety.

This correction should be implemented before filesystem events, recorder events, or provider events are wired into an at-least-once runtime.

---

## ABR-004 — Dispatcher and concrete Observation Interpreter contracts are incompatible

**Disposition:** Accepted
**Classification:** Confirmed architectural inconsistency
**Priority:** Correct before runtime composition

The repository should expose one small dispatcher-facing interpreter protocol.

### Approved direction

* Adapt the existing dispatcher or concrete interpreters through a narrow compatibility boundary.
* Preserve batch interpretation only where it has demonstrated semantic value.
* Avoid duplicating dispatchers for each interpreter generation.
* Do not rename or reorganize all interpreter packages solely for stylistic consistency.
* Add contract tests routing every supported Production Event through the real dispatcher-facing boundary.

This is a bounded correction and may be an appropriate early implementation plan after architecture bootstrap.

---

## ABR-005 — Timestamp authority is inconsistent

**Disposition:** Accepted
**Classification:** Reliability and replay risk
**Priority:** Correct before durable serialization or external ingress

### Approved direction

* External and persisted domain timestamps must be timezone-aware.
* Naive timestamps must be rejected or handled through an explicit source-specific normalization policy.
* The system must not silently attach UTC to an ambiguous timestamp.
* Domain/request times should be supplied explicitly.
* Runtime receipt, evaluation, attempt, acceptance, and commit times should be created through an injected infrastructure clock.
* Semantically distinct timestamps must remain distinct.
* Original source time may be preserved alongside normalized UTC and receipt time where required.

Existing newer contracts that already follow these rules should be treated as the preferred pattern.

---

## ABR-006 — Frozen legacy contracts expose mutable nested metadata

**Disposition:** Accepted
**Classification:** Contract reliability risk
**Priority:** Correct before these values become durable or externally supplied

### Approved direction

* Adopt recursive immutability at domain and persistence boundaries.
* Reuse the deep-freeze approach already present in newer StageFlow contracts where suitable.
* Define accepted metadata value types.
* Keep authoritative identity, provenance, and behavior-driving fields out of supplementary metadata.
* Do not introduce a large generic serialization framework solely to solve this issue.
* Preserve intentional compatibility with non-JSON values only where evidence demonstrates a requirement.

The correction should be incremental and test-driven rather than a repository-wide aesthetic rewrite.

---

## ABR-007 — Filesystem discovery path replacement race

**Disposition:** Accepted with qualification
**Classification:** Confirmed technical race; deployment risk depends on environment
**Priority:** Correct before StageFlow trusts writable or externally controlled event storage

### Approved direction

* Preserve shallow, bounded, read-only discovery.
* Bind enumeration and child inspection to the validated directory object where supported.
* Otherwise capture and revalidate filesystem object identity before returning candidates.
* Reject results when the target changes during enumeration.
* Document supported operating systems and filesystem limitations.
* Add a fault-injection test for directory replacement between validation and enumeration.
* Independently protect later content access; discovery hardening alone must not grant future processing authority.

This finding does not justify broadening filesystem permissions or introducing recursive scanning.

---

## ABR-008 — Media flow ends before durable completed-asset registration

**Disposition:** Accepted
**Classification:** Expected future capability gap
**Priority:** Feature-enabling work after architecture foundation

The existing separation between candidate discovery, resource observation, readiness evaluation, and Completed Media Asset meaning is correct and should be preserved.

### Approved future sequence

1. Concrete one-shot resource snapshot observation
2. Repeated observation ownership
3. Explicit readiness evaluation
4. Deterministic Completed Media Asset assembly
5. Durable media registry
6. Stable asset-registration Production Event
7. Authoritative Session association
8. Restart reconciliation
9. Incremental downstream processing

Do not implement these steps as one stateful watcher-manager.

Each boundary should remain testable and independently reviewable.

---

## ABR-009 — Durable jobs, claims, attempts, and retries do not exist

**Disposition:** Accepted with qualification
**Classification:** Future operational requirement, not current defect
**Priority:** Architecture foundation before asynchronous or provider-dependent processing

### Approved direction

StageFlow should eventually use durable at-least-once work execution for tasks such as:

* Transcription
* Analysis
* Rendering
* Packaging
* Upload
* External delivery

The first implementation should favor a database-backed operation and worker model inside the modular monolith.

It should include:

* Stable operation identity
* Claim or lease ownership
* Attempt history
* Bounded retry
* Explicit retryability classification
* Deferred-until-online state
* Idempotent result commit
* Restart reconciliation
* Operator-visible status

An external queue broker or microservice architecture is not approved unless actual workload evidence later demonstrates the need.

---

## ABR-010 — Packaging, distribution, archive, and retention are placeholders

**Disposition:** Accepted and deferred
**Classification:** Future capability gap
**Priority:** Defer until durable Session, media, editorial, and job foundations exist

Do not implement these contexts merely to fill empty packages.

Before the first real destination integration, StageFlow must define provider-neutral:

* Package identity and revision
* Package manifest
* Deliverable completeness
* Destination
* Delivery operation and attempt
* Idempotency key
* Delivery result or receipt
* Archive record
* Retention and deletion authorization

Provider payloads must not become the core domain representation.

---

## ABR-011 — Operational visibility is limited to liveness

**Disposition:** Accepted
**Classification:** Operational readiness gap
**Priority:** Required incrementally before event use

### Approved direction

Retain simple liveness, but distinguish it from:

* Application readiness
* Runtime composition status
* Storage availability
* Reconciliation status
* Worker health
* Provider health
* Event-mode network status

Operator visibility should be derived primarily from durable domain and operation state, not from parsing logs.

Each new operational workflow must add sufficient visibility to answer:

* What is active?
* What is waiting?
* What failed?
* What is retrying?
* What requires connectivity?
* What requires operator intervention?
* Is finalization safe?

A complete producer UI is not required before the backend exposes this information.

---

## ABR-012 — Configuration lacks one production authority and precedence model

**Disposition:** Accepted
**Classification:** Open architecture decision with approved direction
**Priority:** Architecture foundation before composition root

### Approved direction

* Introduce one validated deployment configuration boundary.
* Build the immutable Runtime graph from that configuration.
* Use documented precedence.
* Expose a redacted effective-configuration summary.
* Keep secrets as opaque references and resolve them at infrastructure boundaries.
* Distinguish deployment configuration from runtime-observed facts.
* Version the configuration schema.
* Validate the entire configuration before declaring the application ready.

The exact file format and secret mechanism remain implementation choices to be planned separately.

---

## ABR-013 — Session and candidate vocabulary conflicts

**Disposition:** Accepted
**Classification:** Documentation and domain-language inconsistency
**Priority:** Resolve before persistence and public APIs

### Approved direction

Use qualified terms at architectural and serialized boundaries.

Preferred distinctions include:

* Business Event
* Production Event
* Session
* Session Candidate
* Timeline Window Candidate
* Session Window Product
* Media Asset Candidate
* Completed Media Asset
* Editorial Candidate Moment
* Operational State
* Media Resource Observation
* Semantic Observation
* Recording Block
* Source Segment or durable Segment record, once defined
* Editorial Clip, distinct from ingest media

No broad code rename is authorized yet.

Canonical terminology must be established in the domain glossary first, followed by compatibility-aware migration only where storage, APIs, or significant development ambiguity justify it.

---

## ABR-014 — Baseline documentation and visible release status are stale

**Disposition:** Accepted
**Classification:** Documentation mismatch
**Priority:** Correct during development-flow bootstrap

### Approved direction

* Update current-status documentation after architecture disposition is approved.
* Preserve historical documents.
* Mark material as:

  * Implemented
  * Approved direction
  * Open decision
  * Legacy
  * Superseded
* Make the Engineering Directive index and current architecture index easy to locate.
* Update the frontend’s displayed status separately from product workflow implementation.
* Remove or label unused `.env.example` values so they are not mistaken for active configuration.

Do not rewrite historical documents to imply they always matched the current implementation.

---

## ABR-015 — Strong tests are not enforced in CI and system-risk tests do not yet exist

**Disposition:** Split disposition

### Existing quality matrix

**Disposition:** Accepted for immediate implementation

Add CI that runs the currently verified commands:

* Backend tests
* Ruff
* Pyright
* Frontend build
* Frontend lint
* Frontend typecheck

CI should not claim to prove event-operational readiness.

### System and fault testing

**Disposition:** Accepted incrementally

Add restart, multi-process, storage-fault, provider-fault, late-media, and idempotency tests only as corresponding durable components are introduced.

Source and naming exclusion tests may remain as supplementary architecture tripwires, but they must not substitute for behavioral validation.

---

## ABR-016 — Newer runtime and media boundaries are conservative and coherent

**Disposition:** Accepted as a protected strength
**Classification:** Positive observation
**Priority:** Leave unchanged unless a concrete contradiction appears

Preserve:

* Explicit aware timestamps
* Deep-frozen metadata
* Typed outcomes
* Bounded calls
* Deterministic IDs and ordering
* Stale-revision checks
* Thread-safe snapshots
* Separation of evaluation, acceptance, commit, and publication
* Discovery/readiness/asset separation
* Deployment profile as provenance rather than trust or identity
* Explicit non-durable scope of in-memory components

Future composition should be built around these boundaries rather than collapsing them.

---

## ABR-017 — Provider isolation and current offline safety are strong

**Disposition:** Accepted as a protected strength
**Classification:** Positive observation
**Priority:** Leave unchanged

### Approved direction

* Keep the event-critical path independent of continuous internet access.
* Introduce external providers only behind explicit adapter boundaries.
* Classify network-dependent work as optional, deferred, or event-critical.
* Avoid provider-specific schemas in the core domain.
* Do not add cloud or queue dependencies simply because they appear in older architecture examples.
* Test loss of connectivity once an operational ingest kernel exists.

Current offline compatibility must not be described as a complete offline event workflow until that workflow exists.

---

# Architecture decision dispositions

## D-01 — Authoritative Session identity

**Disposition:** Approved direction; detailed lifecycle still requires an ADR

StageFlow should assign its own immutable Session ID.

Scheduled platform IDs, Pretalx IDs, recorder identifiers, and other external IDs should be stored as versioned references rather than used as the sole domain identity.

Observed Session candidates may propose association or creation, but must not silently become an authoritative Session without an explicit promotion or reconciliation decision.

### Still open

* Who may create or promote a Session
* How scheduled and observed Sessions reconcile
* Whether an operator can split, merge, or reassign Sessions
* Event and Stage ownership
* Handling of schedule corrections

---

## D-02 — Durable store and transaction boundary

**Disposition:** Approved architectural direction

Use one relational durable store within the modular monolith.

Media content should remain outside the database and be referenced through durable media records.

Use append-oriented records or operation ledgers where replay, lineage, and idempotency require them. Do not convert the entire system into event sourcing without demonstrated need.

### Still open

* Exact database technology
* Initial schema shape
* Migration tooling
* Development and event-deployment topology
* Backup and restore policy

---

## D-03 — Execution and delivery semantics

**Disposition:** Approved architectural direction

Use synchronous direct calls for deterministic domain decisions.

Introduce database-backed, at-least-once durable operations and workers only for work that is genuinely asynchronous, long-running, retryable, or externally dependent.

Do not introduce a broker in the first operational implementation unless measured requirements justify it.

---

## D-04 — Stable ingress identity and interpreter contract

**Disposition:** Approved

Create a durable ingress record keyed by:

* Stable source identity, and
* Source event identity when trustworthy, or
* A versioned canonical fingerprint of authoritative source facts

Route supported ingress through one dispatcher-facing interpreter protocol.

This decision should precede continuous media or recorder-event composition.

---

## D-05 — Canonical media-to-event path

**Disposition:** Approved

The intended flow is:

1. Discover Media Asset Candidate
2. Persist candidate identity and provenance
3. Record objective Media Resource Observations
4. Evaluate readiness
5. Assemble and register immutable Completed Media Asset
6. Emit a stable asset-registration Production Event
7. Associate the registered asset with authoritative Session identity
8. Schedule downstream work through durable operations

Incomplete or merely discovered files must not be represented as completed-segment events.

---

## D-06 — Session completion and late media

**Disposition:** Approved at principle level; policy details remain open

StageFlow should distinguish:

* Session activity ended
* Media grace period active
* Media set settled
* Editorially final
* Package complete
* Published or delivered
* Archived

Late media must not silently mutate previously published history.

The preferred direction is to create a reviewable revision, reopening action, or quarantine condition.

### Still open

* Default grace duration
* Automatic versus operator-approved reopening
* Rules for media arriving after packaging
* Rules for media arriving after publication
* Whether different event modes may use different policies

---

## D-07 — Time authority

**Disposition:** Approved

* Externally supplied domain timestamps must be timezone-aware.
* Ambiguous naive times must be rejected unless a source-specific normalization rule is explicitly configured.
* Infrastructure-created times must use an injected clock.
* Original source, normalized source, receipt, evaluation, acceptance, attempt, and commit times must remain distinct where their meanings differ.
* UTC is the canonical normalized storage representation, not a substitute for missing source timezone information.

---

## D-08 — Configuration ownership and precedence

**Disposition:** Approved direction

Use:

1. Code and schema defaults
2. Versioned deployment configuration
3. Environment-specific non-secret overrides
4. Secret references resolved through infrastructure
5. Explicit controlled command overrides where operationally justified

Runtime-observed facts must not be overridden by configuration preference.

Expose the effective non-sensitive configuration and its source.

---

## D-09 — Notification and outbox boundary

**Disposition:** Approved when durable external consumers are introduced

Keep best-effort local telemetry separate from externally meaningful notifications.

Externally meaningful messages should use a transactional outbox or equivalent durable publication boundary with:

* Stable message identity
* Commit-before-publication
* Retry state
* Delivery result
* Reconciliation

No outbox implementation is required before a durable store and real external consumer exist.

---

## D-10 — Architecture document scope and authority

**Disposition:** Approved

Architecture documentation must distinguish:

* Current implementation
* Accepted architecture
* Intended future direction
* Open decision
* Legacy or superseded material

Historical ADRs and Engineering Directives should remain available.

The architecture index, accepted ADRs, and disposition documents should define current authority and precedence.

---

# Implementation priority

## Phase 1 — Development-flow foundation

Create:

* Root `AGENTS.md`
* Architecture index and principles
* Current system context
* Domain glossary
* Session lifecycle document with unresolved decisions clearly marked
* Segment/media lifecycle document
* ADR index
* Reviews process
* Implementation-plan process
* CI for the existing quality matrix
* Updated current-status documentation

No production runtime composition should occur in this phase.

## Phase 2 — Contract-boundary stabilization

Create separate implementation plans for:

1. Stable ingress identity
2. Dispatcher/interpreter compatibility
3. Timestamp invariants
4. Recursive metadata immutability
5. Filesystem discovery race hardening

Each should be implemented and independently reviewed separately unless repository evidence demonstrates that two items cannot be safely separated.

## Phase 3 — Durable event-mode kernel

After the required ADRs are accepted:

1. Durable configuration loading
2. Initial relational persistence
3. Durable ingress and operation records
4. Durable media candidate registry
5. Startup reconciliation
6. Application composition root
7. Readiness and dependency health
8. Minimal operator status APIs

## Phase 4 — First operational media slice

Implement one complete vertical workflow:

1. Explicit one-shot shared-storage discovery
2. Durable candidate registration
3. Repeated resource snapshot observation
4. Readiness evaluation
5. Completed Media Asset registration
6. Stable Production Event emission
7. Session association or review queue
8. Durable operation status
9. Restart recovery
10. Operator visibility

Transcription, editorial analysis, packaging, and publishing should not be required for this first slice unless they are explicitly selected as part of the acceptance criteria.

---

# Prohibited interpretations

This disposition does not authorize:

* A repository-wide rewrite
* Microservices
* A message broker
* Cloud-required event operation
* Direct live NDI or SDI ingest
* Treating directories as Sessions
* Treating discovered files as completed assets
* Treating Operational State as the Session aggregate
* Automatically accepting machine editorial suggestions
* Implementing all placeholder bounded contexts
* Renaming all legacy contracts at once
* Moving domain logic into FastAPI
* Introducing generic abstractions without a demonstrated second implementation or operational need
* Treating the architecture audit as implementation authority without this disposition and applicable ADRs
