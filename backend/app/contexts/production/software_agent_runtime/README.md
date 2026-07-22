# Software Agent Runtime

ED-0051 introduces `SoftwareAgentRuntime`. It is the first executable Runtime profile.
It is a synchronous, in-process lifecycle shell around the immutable ED-0050
`StageFlowRuntime`. It implements lifecycle only: construction retains the Runtime,
explicit dependencies, Agent instance identity, and caller-supplied creation time. It
does not validate, start work, invoke ports, read a clock, or create a background
thread.

## Explicit startup and authority

`prepare()` verifies request identities and revision, runs ED-0050
`validate_runtime()`, checks the execution profile and dependencies, and records
`created -> validated -> ready`. After aggregate validation, the embedded
`RuntimeConfiguration` is the authoritative execution configuration. Any drift between
the aggregate's top-level declarations and that configuration blocks startup.

The Agent profile is accepted. Development requires the request's explicit permission.
Node, external-compatible, and unknown profiles are rejected by this Agent adapter;
that rejection is an execution-placement decision, not a trust or media-semantics
judgment. Disabled configuration or disabled event mode produces the non-error
`disabled` lifecycle, not `failed`.

`start()` is separately explicit and consumes a caller-supplied, timezone-aware
pressure declaration:

- normal enters `running` with normal permission;
- elevated enters `yielding` with reduced permission;
- critical, recording-safety-uncertain, or unknown enters `suspended` with no
  permission.

The complete lifecycle vocabulary is `created`, `validated`, `ready`, `running`,
`yielding`, `suspended`, `stopping`, `stopped`, `failed`, and `disabled`. The recorded
transition graph is:

```text
created -> validated -> ready -> running | yielding | suspended
created -> disabled | failed | stopped
validated -> ready | failed | stopping
ready -> running | yielding | suspended | stopping
running -> yielding | suspended | stopping
yielding -> running | suspended | stopping
suspended -> running | yielding | stopping
failed | disabled -> stopping
stopping -> stopped
```

Pressure updates may record a same-state transition. Elevated pressure yields;
critical, uncertain, and unknown pressure suspend. Favorable pressure never
automatically resumes a suspended Agent. `resume()` is explicit: normal permits
running, elevated permits yielding, and unsafe or unknown pressure is rejected.
Explicit resume is required after suspension.
Execution permission (`none`, `essential_only`, `reduced`, or `normal`) is first-class
and is `none` before start, while suspended, during shutdown, after cancellation, and
in terminal states.

## State, synchronization, and notifications

One private `RLock` protects immutable copy-and-swap state. Snapshots and transition
history are append-only values with monotonic revisions. Caller-supplied operation IDs
are idempotent within one instance: an exact replay returns the original authoritative
snapshots, transitions, and timestamp as `already_applied`; conflicting reuse is an
operation conflict. Expected revisions prevent stale operations from overwriting a
newer state. This index and all lifecycle state are process-local and are not persisted
or shared across instances.

Stop and cancellation are synchronous. `created` stops directly; all other
non-stopped states record `stopping -> stopped`. No background drain or process signal
exists. A stopped instance is terminal and cannot restart; construct a new instance
for a new execution epoch. Because `stopping` is committed in the same synchronous
operation as `stopped`, it is retained in lineage rather than exposed as a waiting
phase.

For each committed transition, notification order is lifecycle, health, availability.
The implementation commits an immutable lifecycle result basis and pending operation
record under the lifecycle lock, releases that lock, and only then invokes injected
sinks. It briefly reacquires the same lock after delivery to retain the completed
notification status without changing the snapshot, revision, history, health, or
availability. A concurrent exact replay waits for that completed delivery result while
unrelated lifecycle operations remain free to commit. Sink failures are typed as
`applied_with_notification_failure`; they do not roll back lifecycle state and are not
retried or republished on replay. Read-only sink callbacks may inspect the fully
committed snapshot, history, and summary; lifecycle mutation from a sink callback is
not a supported port behavior. These notifications are lifecycle diagnostics, not
Production Events.
The Agent lifecycle itself is not a Production Event.

Health, availability, and configuration validity stay distinct. Created health is
unknown. Valid ready/running health is healthy; yielding and precautionary suspension
are degraded; failed is unhealthy. Stopping and stopped preserve the prior health
assessment while availability becomes unavailable. Ready/running availability is
available, yielding is limited, suspended/failed/stopping/stopped is unavailable, and
disabled is disabled. All timestamps come from explicit aware request or construction
values; the package never reads the wall clock.

## Mission and strict boundary

Production recording and livestream work remains authoritative and always has
priority. ED-0051 consumes supplied pressure; it does not measure pressure or enforce
resource budgets. It is safe for borrowed production hardware because it performs no
filesystem or media access, GPU work, recorder inspection/control, process inspection,
networking, source writes, monitoring, polling, scheduling, or service installation.

There is no candidate discovery, resource observation collection, ED-0049 readiness
execution, ED-0048 asset assembly, checksum or probe, transfer, queue, persistence,
Production Event, semantic Observation, Evidence, Operational State, repository,
Session identity, AI, API, worker, or frontend behavior. Recording remains externally
owned. A future Node adapter can reuse the ED-0050 Runtime and these lifecycle concepts
without changing common media semantics.

ED-0052 implements the next narrow boundary separately. A read-only execution-state
port exposes the current immutable Agent snapshot to one explicit synchronous media
collection coordinator. The coordinator rechecks permission between bounded external
calls; it does not resume, stop, pressure-update, or otherwise mutate this lifecycle.
Normal permission permits configured collection, reduced permission prioritizes
required observations and skips optional work, and essential-only or none permits no
media collection. Candidate discovery and objective observation behavior remain
injected, lock-free port calls. ED-0052 adds no background loop, filesystem/recorder
implementation, readiness execution, asset assembly, transfer, queue, or persistence.

ED-0053 supplies one such discovery-port implementation without changing Agent
lifecycle. The adapter trusts only the permission value carried by ED-0052's request;
it never queries, resumes, stops, pressure-updates, or publishes this lifecycle. Normal
and explicitly allowed reduced cycles may invoke one bounded discovery call. None or
essential-only permission is blocked before filesystem access, and ED-0052 still owns
the before/after permission checkpoints and all recurrence decisions.
