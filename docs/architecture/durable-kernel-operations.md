# Durable Kernel reference-node operations

## Scope

This is the developer/reference-node procedure for the first Durable Event-Mode Kernel.
It is not an event-readiness certificate or a production-deployment runbook. The Kernel
does not control recorders, livestream systems, power settings, or source media.

## Configuration

Create a version `1.0` TOML file outside source control. Use stable operator keys; do not
put a PostgreSQL password or DSN in the file.

```toml
schema_version = "1.0"
deployment_id = "reference-event-node"
node_id = "razer-node"
node_role = "node"
event_mode = "event"
network_policy = "local_only"
postgres_dsn_secret_ref = "STAGEFLOW_KERNEL_DSN"

[event]
key = "reference-event"
name = "Reference Event"

[[event.stages]]
key = "main"
name = "Main Stage"

[[event.stages.sources]]
key = "main-recorder"
path = "D:/recordings/main"
maximum_candidates = 1000
```

Set `STAGEFLOW_KERNEL_CONFIG_PATH` to the TOML path and set the named secret environment
variable (`STAGEFLOW_KERNEL_DSN` above) at the process/service boundary. Effective
configuration summaries redact the resolved DSN. Loading the file validates only; it
does not create a Business Event, Stage, Session, or migration.

## Database and bootstrap

1. Provision a local or local-network PostgreSQL database independently of StageFlow.
2. Back it up before schema change when it contains operational data.
3. Run the explicit `0001_ingress` and `0002_event_mode_kernel` forward migrations with
   `PostgresMigrationRunner.apply_event_mode_kernel_v1()` in an isolated maintenance
   step.
4. Start the shell and confirm `/api/v1/health` remains live.
5. Invoke `KernelComponents.explicit_bootstrap(...)` from an authorized setup boundary.
   Equivalent repeats resolve the same StageFlow IDs; structural removal/conflict is
   rejected.
6. Restart StageFlow. Startup reconstructs PostgreSQL state and records a typed startup
   reconciliation before Kernel readiness.

The application never auto-migrates or auto-bootstraps on configuration parsing or
ordinary startup. PostgreSQL failure makes Kernel status unavailable; there is no
in-memory authority fallback.

## Operational status and recovery

`GET /api/v1/kernel/status` reports the selected Event, each Stage's source availability,
active/assembling Session and package revision/state, media-state counts, latest media
arrival, reconciliation state, and attention codes. A database outage returns HTTP 503
with `postgresql_unavailable`. Source paths and the PostgreSQL DSN are not returned.

For source loss, preserve the durable records, restore the same configured binding, and
run startup reconciliation again. Absence never implies deletion, Session end, package
completion, or reassociation. For database loss, stop authoritative writes, restore
connectivity, verify both migrations, reconstruct through a new repository/process, and
reconcile sources before treating the Kernel as ready.

## Reversal and backup limitations

`reverse_event_mode_kernel_v1()` removes only `0002_event_mode_kernel` objects and its
ledger row; it preserves `0001_ingress` and the shared `stageflow` schema. It is suitable
only for an isolated database or an operator-approved rollback after operational lineage
has been exported/preserved. It is not an automatic recovery action.

Reference-node qualification must separately cover backup/restore, a representative
event-length workload, recording/livestream coexistence, and deliberate sleep/power-plan
configuration. Developer tests and short synthetic runs do not establish those facts.
