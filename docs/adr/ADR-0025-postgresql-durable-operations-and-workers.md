# ADR-0025: PostgreSQL durable operations and worker coordination

## Status

Proposed

## Date

2026-08-09

## Context

The accepted Durable Event-Mode Kernel deliberately excluded a generic Job/Operation
framework. Its concrete media discovery, readiness, registration, ingress, association,
and reconciliation path is a bounded synchronous cycle and did not justify asynchronous
infrastructure.

The post-Kernel capability layer introduces a concrete different need. Transcription may
run for minutes, consume a dedicated GPU Node, survive application and worker restarts,
retry after provider or resource failure, defer cloud-dependent work during Event Mode,
and commit one idempotent versioned transcript artifact. Model analysis and rendering
have similar execution properties later. Process-local Agent lifecycle and collection
coordination cannot provide multi-process claims, restart recovery, or durable attempt
history.

ADR-0022 already makes PostgreSQL the authoritative operational store and permits future
workers/nodes to share it. StageFlow remains a modular monolith, local-first Event
operation must not require a broker or Internet access, and deterministic domain policy
calls must remain synchronous.

The decision is Yellow because it introduces durable execution identity, concurrency,
failure/retry, and worker ownership semantics that will shape multiple future consumers.

## Decision

If accepted, StageFlow will introduce a minimal PostgreSQL-backed Durable Operation and
Worker coordination boundary, proved first by one local transcription consumer.

### Operation and attempt

A Durable Operation is a typed, persisted request for genuinely asynchronous,
long-running, retryable, or externally dependent work. It has stable StageFlow identity,
operation kind and schema version, Event/deployment scope, subject and immutable input
revision/manifest references, priority, idempotency key, eligibility time, lifecycle
state, cancellation intent, created/updated times, and an optional terminal result
reference.

An append-only Operation Attempt records worker identity, claim generation/fencing token,
lease start/expiry, execution start/end, outcome, retryability, reason code, and bounded
diagnostic summary. Provider payloads and large media/results do not live in these rows.

The initial lifecycle must distinguish at least pending/eligible, leased/running,
deferred/blocked, succeeded, terminal failure, cancel requested, and cancelled. Exact
storage enum names and transition layout are implementation-plan details so long as
those meanings remain explicit and history is preserved.

### Claims, leases, and time

Workers claim eligible operations transactionally in PostgreSQL using bounded polling
and backoff. Claims use time-bounded renewable leases. Database time determines lease
ordering and expiry; all recorded domain/infrastructure times remain timezone-aware.
Every claim increments a fencing generation. A late or partitioned worker cannot commit
an authoritative result after its lease/generation is stale.

Lease expiry does not itself mean the external side effect did not occur. Reconciliation
examines result/idempotency state before retrying. Worker heartbeat/presence and attempt
lease are separate: presence helps operations, while the lease owns a specific attempt.

### At-least-once and result ownership

Execution is at least once. Exactly-once processing is not claimed. Operation handlers
must use a stable work key and commit idempotent output into the owning domain repository.
The domain result and the operation's terminal result reference are committed in one
transaction when they share PostgreSQL. A transactional outbox is not introduced until
an externally meaningful durable message has a concrete consumer.

Retries are bounded and policy-driven by operation kind. Outcomes distinguish retryable,
terminal, deferred by Event Mode/network policy, blocked by missing dependency, and
cancelled. Cancellation is cooperative; it records intent and fences later result commit
but does not claim to terminate an external process instantly.

### Worker identity and capabilities

A Worker has stable StageFlow identity, Node/deployment identity, Event assignment where
configured, enabled/draining state, and versioned declared processing capabilities.
Capabilities identify operation kinds, provider/model/runtime versions, and configured
eligibility; they do not grant semantic authority.

Heartbeat, last-seen, capacity, resource pressure, and provider health are time-sensitive
observations with expiry/unknown semantics. Work in progress derives from leases and
attempts. Raw GPU telemetry is diagnostic. Producer projections show operational meaning
such as lag, backlog, deferred reason, and capability unavailability.

### Deployment and Event Mode

The first deployment remains one modular backend/control plane plus one or more worker
processes sharing PostgreSQL over a local network. No microservice ownership split or
broker is required. Provider adapters remain behind worker execution ports.

Configuration supplies network/role/resource/concurrency ceilings. Versioned policy
decides priority, eligibility, defer/retry class, and Event Mode behavior. The claimer
enforces those decisions. Producer commands may explicitly pause/resume/defer StageFlow
work within allowed scope. StageFlow does not manage unrelated processes, recorder
software, OS resources, or power settings.

The implementation must begin with the minimum schema and code for transcription. New
operation kinds are added only with a concrete owner, input/result contract,
idempotency/reconciliation design, and tests.

## Alternatives

### Keep all processing synchronous in the control-plane request/process

This is simplest and remains correct for deterministic policies. It is rejected for
transcription because process restart, long duration, dedicated worker placement,
bounded retry, cancellation visibility, and backlog recovery are real requirements.
It would also couple the Producer/control-plane process to GPU availability.

### Reuse the current Software Agent Runtime and media collection coordinator

Those contracts provide valuable lifecycle and conservative permission concepts, but
their state and replay are process-local and their work is explicitly synchronous and
caller-driven. Extending them into a durable multi-process queue would blur accepted
boundaries and risk redesigning the Kernel. Rejected as the coordination store; concepts
may be reused.

### Use a message broker first

A broker can improve wake-up latency and high-throughput distribution but adds another
service, operational dependency, delivery/reconciliation boundary, and offline/Event
Mode burden. PostgreSQL already owns durable authority and expected first-stage volume
does not demonstrate broker need. Deferred until measured contention/latency or a real
consumer requires it.

### Use a provider-specific queue or cloud job service

This can simplify one provider integration but makes Event operation depend on network
and provider semantics, weakens local portability, and leaks provider identity into core
execution. Rejected.

### Build a generic distributed-compute platform before a consumer

This might anticipate rendering and vision workloads but would decide scheduling,
resource discovery, data transfer, and topology without evidence. Rejected. The first
transcription consumer must prove the minimal boundary.

## Consequences

### Positive

- Transcription and later qualifying work survive process/worker restart with visible
  attempt history and bounded recovery.
- The Producer/control plane remains independent of an individual GPU worker.
- PostgreSQL preserves one local-first operational authority without a broker.
- Fencing and idempotent result ownership make at-least-once execution explicit.
- Provider and machine details remain outside domain authority.

### Negative and risks

- Lease, retry, cancellation, and reconciliation correctness add substantial concurrency
  and operational complexity.
- PostgreSQL polling and heartbeats add write load and require measurement/backoff.
- A database outage stops new claims/authoritative result commits; no memory fallback is
  permitted.
- A leased operation may execute externally after apparent expiry, so handlers must
  design idempotency and reconciliation rather than trust lease state alone.
- The initial schema may need additive evolution as rendering/vision requirements become
  concrete; the first slice must avoid pretending to be a universal scheduler.

## Validation

Acceptance and implementation plans must require:

- exact/conflicting enqueue replay and stable work-key tests;
- concurrent claim uniqueness and deterministic priority ordering;
- database-time lease renewal/expiry, fencing, and stale-result rejection;
- worker kill/disappearance/restart and bounded reclaim;
- retryable/terminal/deferred/blocked/cancel outcomes and retry limits;
- idempotent transcript artifact/result commit and crash between execution and commit;
- PostgreSQL outage/recovery and startup reconciliation;
- Event Mode local-only/cloud-defer, pressure, pause/resume, and backlog-bound tests;
- multi-process isolated-PostgreSQL integration tests plus migration forward/reversal and
  backup/restore evidence; and
- bounded status/lag projections that omit secrets, source paths, and provider payloads.

A short synthetic benchmark does not establish Event readiness. Reference-worker
qualification must separately cover representative duration and coexistence.

## Related documents

- [Post-Kernel capability layer](../architecture/post-kernel-capability-layer.md)
- [Post-Kernel capability implementation plan](../plans/post-kernel-capability-layer.md)
- [ADR-0022: PostgreSQL authoritative operational store](ADR-0022-postgresql-authoritative-operational-store.md)
- [ADR-0024: Durable Kernel authority and persistence](ADR-0024-durable-kernel-authority-and-persistence.md)
- [Durable Event-Mode Kernel](../architecture/durable-event-mode-kernel.md)
- [Persistence boundary](../architecture/persistence.md)
