# Media Candidate Collection

ED-0052 adds StageFlow's first media-facing Agent execution boundary. The boundary is
one synchronous `MediaCandidateCollectionCoordinator`: callers explicitly submit one
bounded cycle, and the coordinator returns before the call completes. It never
schedules another cycle, polls, sleeps, creates a thread, or runs as a service.

## Authority and execution permission

The immutable ED-0050 `StageFlowRuntime` and its embedded `RuntimeConfiguration` are
authoritative. Runtime validation, aggregate-drift checks, plan and capability
relationships, dependencies, operation identity, and expected revision are checked
before media-facing work. ED-0051 Agent state is read through a narrow read-only port;
the coordinator never mutates Agent lifecycle.

Running with normal permission permits the configured bounded calls. Yielding with
reduced permission is accepted only when the request explicitly permits it, required
observation calls retain priority, and optional calls are deferred. `essential_only`,
`none`, cancellation, stopping, stopped, failed, disabled, or another non-runnable
state permits no new media-facing call. Permission is re-read before reservation,
before and after discovery, before each candidate observation group, before every
observation-port call, and before commit. A mid-cycle change finishes the active call,
retains its objective facts, and prevents disallowed later calls.

## Injected collection and bounded orchestration

Discovery and the five ED-0049 observation categories are supplied by synchronous
ports. This package contains no filesystem or recorder adapter. Candidate and
observation-call budgets are positive and explicit; remaining candidate budget is
passed to discovery. Candidate order is target ID, candidate ID, proposed asset ID,
then resource ID. Required observations precede optional observations, with the stable
per-category order presence, snapshot, finalization, write state, and read access.

Adapter exceptions become typed failed results and are never retried automatically.
Valid facts supplied before a failure, permission interruption, or budget boundary are
committed atomically. No external port is invoked under the coordinator's `RLock`.
Only one cycle per coordinator can invoke ports; competing or exact active requests
return immediately without queuing or waiting.

## Process-local facts, conflicts, and replay

Candidates are deduplicated by candidate, proposed-asset, and resource identity.
Exact rediscovery extends lineage without creating another record. Incompatible
candidate, asset, resource, target, discovery, or observation identity is retained as
a first-class immutable conflict; a prior valid candidate is never overwritten.

Objective ED-0049 observations accumulate across explicit cycles into one stable-ID
bundle per coherent candidate. Exact facts collapse, chronological facts remain, and a
conflicting observation ID does not create a misleading valid bundle. Accumulation
does not call the ED-0049 readiness policy, produce completion/readiness declarations,
or assemble an ED-0048 `CompletedMediaAsset`.

Committed operation IDs are idempotent in one instance. Exact completed replay returns
the original facts, snapshots, revision, and explicit timestamps as `already_applied`;
conflicting replay and stale revisions invoke no port. Cycle history is immutable,
oldest-to-newest, process-local, and contains only committed executed cycles. Typed
queries return `found` or `not_found` and invoke no port.

## Strict boundary

Recording and livestream workloads remain authoritative. The package does not watch
or access files, inspect handles, query or control a recorder, probe or process media,
evaluate readiness, assemble assets, transfer, queue, persist, use a network, create a
Production Event, create a semantic Observation or Evidence, mutate Operational State,
use its repository, infer Session identity, call AI, expose an API, run a worker, or add
frontend behavior. There is no global mutable state.

Agent is the first execution placement, not a different media-semantics tier. A future
Node adapter can supply the same discovery and observation port contracts. ED-0053
should add one bounded read-only local-filesystem candidate-discovery adapter while
preserving explicit cycles and avoiding watchers or continuous polling.
