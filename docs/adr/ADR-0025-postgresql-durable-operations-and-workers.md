# ADR-0025: PostgreSQL durable operations and worker coordination

## Status

Accepted

## Date

2026-08-17 (accepted; originally proposed 2026-08-09)

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

This decision was Yellow because it introduces durable execution identity, concurrency,
failure/retry, and worker ownership semantics that will shape multiple future consumers.
The operator accepted the first-transcription-worker package on 2026-08-17.

## Decision

StageFlow will introduce a minimal PostgreSQL-backed Durable Operation and
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

## First-transcription-worker decision package

This section records the accepted first-consumer scope. Acceptance is architecture
authority, not implementation authority; a bounded implementation-ready plan remains
required before schema or runtime work begins.

### Concrete topology

```text
Producer/browser clients
  -> modular FastAPI control plane
       -> PostgreSQL authoritative operation + transcript-evidence state
  <- bounded status/lag projections

one or more local worker processes
  -> bounded PostgreSQL claim/renew/complete polling
  -> provider-neutral TranscriptionExecutionPort
  -> local/offline adapter first when a later provider decision selects one
```

The control plane and workers are deployment roles in the same modular monolith/codebase,
not independently owned microservices. PostgreSQL is the only coordination authority.
There is no broker, Redis, cloud queue, continuous-Internet dependency, provider SDK in
the domain, or worker-to-Producer connection.

### Minimal durable entities

The first migration would add only these logical records; exact SQL names remain a
bounded implementation detail:

1. **Durable Operation** — stable operation identity; kind/schema version fixed to the
   first transcription contract; deployment/Event scope; Completed Media Asset and
   manifest identity/version; immutable input/configuration profile references; stable
   work/idempotency key; priority; eligibility time; current lifecycle state; attempt
   and fencing generation; cancellation intent/time; terminal result type/identity/
   revision; created/updated times; optimistic row revision.
2. **Operation Attempt** — stable attempt identity and number; operation/worker identity;
   fencing generation; claim/lease start/current expiry; execution start/end; finalized
   outcome; retryability; reason code; bounded sanitized diagnostic summary; created and
   finalized times. Attempts remain retained. An active attempt may renew its lease;
   after finalization its historical facts are immutable.
3. **Worker** — stable Worker, Node, and deployment identity; optional Event assignment;
   enabled/draining state; implementation version; created/updated times; optimistic
   revision.
4. **Worker Capability** — worker identity plus versioned operation/provider/model/runtime
   descriptor, local/cloud class, configured eligibility, and effective interval. It
   describes placement capability, not semantic authority.
5. **Worker Presence** — latest heartbeat observation with database-recorded time,
   expiry, capacity/concurrency declaration, and bounded health/pressure state. Presence
   is time-sensitive and replaceable; attempt leases remain work ownership.

Transcript Evidence Revision and its segments are owned by the transcription evidence
boundary, not opaque Operation payload columns. The proposed shape is documented in
[Transcription evidence readiness](../architecture/transcription-evidence-readiness.md)
and requires its own accepted implementation plan/migration detail.

### Lifecycle and assignment

The minimum lifecycle meanings are:

```text
pending -> eligible -> leased -> running -> succeeded
                    \-> retry_wait -> eligible
                    \-> deferred | blocked
                    \-> terminal_failed
                    \-> cancel_requested -> cancelled
```

`pending` may wait for an explicit eligibility time. `deferred` means policy currently
forbids otherwise valid work, such as cloud-dependent execution in Event Mode. `blocked`
means a required capability, readable asset revision, or dependency is absent and needs
operator/configuration resolution. Neither is silently counted as provider failure.

The claimer uses one PostgreSQL transaction, database time, deterministic priority and
age ordering, bounded candidate selection, row locking/skip-locked semantics, capability
and Event/deployment matching, and configured concurrency ceilings. It increments the
fencing generation and creates exactly one attempt before returning the claim. No
sticky worker assignment is required; eligible retries may run elsewhere.

### Lease, retry, and crash recovery

- Lease duration and renewal cadence are versioned operation-kind policy values.
- Renewal requires operation, attempt, worker, active state, and fencing generation to
  match; database time supplies the new expiry.
- A worker stops applying results immediately when renewal or fencing validation fails.
- Startup and periodic reconciliation finalize expired active attempts with a typed
  lease-loss outcome, inspect durable result/idempotency state, then either mark success,
  schedule bounded retry, defer/block, or terminally fail.
- Provider calls are at least once. Retry count/backoff are bounded and classify timeout,
  provider/transient resource, invalid input, unsupported asset, cancellation, and
  terminal provider result separately.
- A PostgreSQL outage stops claims, lease authority, and result application. A worker may
  cooperatively stop an in-flight provider call, but it cannot commit to memory and sync
  later as authority.

The first implementation needs process kill/restart and crash-point tests before the
provider call, after provider return, during transcript-result application, and after
the shared result/Operation commit.

### Idempotent transcript result application

The work key binds operation kind/schema, Completed Media Asset/manifest identity,
provider/model/configuration profile, and requested transcript capabilities. Exact
enqueue replay returns the existing Operation; conflicting replay fails.

Provider output is normalized into an immutable proposed Transcript Evidence Revision.
Within one PostgreSQL transaction, the application:

1. locks and validates the Operation/attempt/fencing generation;
2. applies exact/conflicting transcript-result idempotency and appends the evidence
   revision when new;
3. records the stable result identity/revision on the Operation; and
4. finalizes the Attempt and Operation as succeeded.

A stale or expired worker can do none of these. Reconciliation first checks whether the
stable result already exists before scheduling another provider execution. Exactly-once
provider execution is not claimed.

### Cancellation

Cancellation is optional for the initial API surface but the schema/lifecycle preserves
intent. Before provider execution it transitions eligible work directly to cancelled.
During execution the worker receives a cooperative cancellation signal; a late result is
fenced from authoritative commit. Provider activity may continue externally and is
reported honestly. Cancellation never deletes a prior transcript evidence revision.

### GPU/capability routing and provider neutrality

Capability matching is categorical: supported operation schema, provider adapter,
model/runtime revision, local/cloud class, accepted asset formats, timing/word/
diarization capabilities, and configured device class. Raw GPU telemetry is not a claim
predicate except through a bounded, expiring effective-availability/pressure policy.

The first provider remains an independent Yellow dependency/model choice. ADR acceptance
does not select Whisper, a cloud API, FFmpeg, CUDA, or any package. A CPU-only worker may
be eligible only when the selected adapter/configuration declares that mode.

### Event Mode and what remains ephemeral

- Local/offline-capable transcription may be eligible within configured Event Mode
  ceilings and yields to capture/production pressure.
- Cloud-required work defaults to deferred unless the active versioned policy explicitly
  permits it.
- Resume uses bounded backoff and concurrency so accumulated work does not surge.
- PostgreSQL Operation, Attempt, Worker identity/capability, cancellation, and result
  references are durable.
- In-process provider handles, cancellation primitives, poll timers, current raw GPU
  samples, and short-lived telemetry buffers remain ephemeral.
- Worker loss affects intelligence lag/backlog only. It cannot change Session, media,
  package, Editorial approval, recorder, or OS authority.

### Failure and Attention semantics

Ordinary pending/running/retry-wait work is processing state, not Producer Attention.
Bounded projections expose transcript lag, backlog, oldest eligible age, deferred reason,
worker/capability availability, attempt count, and freshness without transcript content,
paths, provider payloads, or hardware-noise detail.

Attention is reserved for actionable operational consequences such as no eligible local
capability for Event-required work, terminal failure of configured-required intelligence,
stalled backlog beyond policy threshold, repeated lease loss, or explicit dependency/
configuration blockage. Even then, the consequence is “transcription unavailable or
delayed”; it does not make Session media/package authority false or incomplete.

### Smallest implementation unlocked by acceptance

Acceptance unlocks one bounded plan containing:

- the five logical Work Execution records above and forward/reversal migration;
- one transcription Operation kind/schema and deterministic enqueue application;
- PostgreSQL claim/renew/finalize/reconcile repository and local worker loop;
- the provider-neutral execution port with a deterministic fake adapter only;
- accepted Transcript Evidence contracts/repository/application and atomic result commit;
- bounded status/lag projections; and
- concurrency, replay, lease, crash/restart, Event Mode, outage, migration, and privacy
  tests.

It would **not** authorize a real provider/model/dependency, automatic enqueue policy,
Candidate generation, automatic AI/editorial authority, cloud service, production
deployment, or generalized rendering/vision scheduler.

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

Implementation plans must require:

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
