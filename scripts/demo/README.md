# Guarded Demo rehearsal controller

Use `StageFlow-Demo.ps1` for the local Demo rehearsal. It is a thin operator
controller around the existing Python Demo CLI, loopback APIs, and
`Start-StageFlowDemo.ps1`; it does not implement alternate application behavior.

Run the controller from PowerShell 7.3 or later (`pwsh`). `start` launches the stack
under the same PowerShell host, and the launcher requires 7.3+; under Windows PowerShell
5.1 it stops immediately with a version error.

## One-time external configuration

The controller never prints these values. It reads Process scope first and Windows User
scope second:

- `STAGEFLOW_DEMO_POSTGRES_DSN` — required secret; it must connect to exact database
  `stageflow_demo`. Test, validation, worker, qualification, or any other database is
  rejected before controller-triggered writes.
- `STAGEFLOW_DEMO_CONFIG_PATH` — optional explicit path to the external Demo TOML. If
  absent, the controller accepts exactly one TOML from the bounded `C:\StageFlowDemo`
  or `C:\StageFlowDemo\config` locations.
- `STAGEFLOW_DEMO_CUDA_RUNTIME_PATH` — optional explicit isolated CUDA runtime. The
  qualified `C:\StageFlowDemo\runtime\whisper-cuda-12.4\Release` location is the bounded
  fallback. PATH changes remain process-local and are restored.
- `STAGEFLOW_DEMO_OPERATOR_ID` — optional attributable operator UUID. When absent, the
  controller accepts exactly one actor already recorded for the unambiguous current
  Demo Session; it never invents authority.

Configuration, model, media, and CUDA directories remain external and uncommitted.
Start with [`demo-single-stage.toml.example`](../../examples/demo-single-stage.toml.example)
and copy [`local-schedule.example.json`](../../examples/local-schedule.example.json) to
its configured `[local_schedule].path`. Customize the placeholder Event identity and keep
the schedule's `event_key` and `stage_key` aligned with the configuration. This default
program source runs offline. Devcon is one optional read adapter: replace `[local_schedule]`
with the commented `[devcon_read]` alternative only when that source is explicitly wanted;
exactly one program source must be configured.

## Actions

```powershell
$demo = ".\scripts\demo\StageFlow-Demo.ps1"

& $demo prepare
& $demo start
& $demo status
& $demo diagnose
& $demo rehearsal-report
& $demo stop
```

`prepare` verifies the exact database, performs the existing real CUDA silent-inference
preflight, bootstraps idempotently, and performs the configured program-source read/cache
sync.
`start` re-verifies the database, launches the existing stack in an owned hidden process,
and waits for loopback health plus the neutral `StageFlow is ready at …` LAN-ready signal.
`stop` targets only the recorded launcher process tree. It does not delete database rows,
media, logs, models, or remote state.

`status` and `rehearsal-report` resolve Event, Stage, and current Session identities
without copy/paste. They summarize bounded media, Operations, worker presence,
Transcription Evidence provenance/counts, Moments, package state, and program cache state.
Reports omit transcript text, media/config paths, DSNs, credentials, tokens, raw provider
diagnostics, and API request bodies.

## Launch-scoped authority protection

Each `start` creates a new cryptographically random, process-only launch context for the
Producer UI. Mutating Demo authority requests must present that exact context; pages
from a prior launcher run and requests with no context fail closed at the Next.js proxy
before the loopback backend is contacted. Refresh the Producer page after restarting the
stack before issuing an explicit human command. GET and status projections are unchanged.

Normal output and reports never contain the launch context. Authority-request diagnosis
records only its short SHA-256 fingerprint plus bounded request attribution; it never
records request bodies, transcripts, credentials, DSNs, or the launch context itself.

## Publication status

External publication is frozen under
[ADR-0031](../../docs/adr/ADR-0031-white-label-identity-and-provider-neutral-program-sources.md)
until a provider-neutral Delivery context is designed. Publication is absent from the
supported action set. The retired publication action refuses with an ADR-0031 message
and a non-zero exit before configuration, credential access, or network calls. The backend
Devcon adapter remains dormant; no replacement delivery workflow is introduced.

## Demo 2 autonomous Event Node

Demo 2 uses the same guarded launcher and `demo-single-stage` application stack. Copy
`examples/demo2-autonomous-event-node.toml.example` to the controlled external Demo
configuration location, set unique Event/deployment values and the external recordings
path, and enable:

```toml
[autonomous_event_node]
enabled = true
media_reconciliation_interval_seconds = 5
program_refresh_interval_seconds = 120
```

The setting is default-off, non-secret, and does not alter Demo 1. The backend lifespan
owns one non-daemon coordinator thread. PostgreSQL advisory ownership prevents two
backend processes for the same deployment from running cycles concurrently. Shutdown
signals and joins that thread before readiness is cleared; process death releases the
database lock, and the next owned process reconstructs freshness and work from durable
state.

Healthy automatic operation stays quiet in the Producer UI. `status` reports bounded
cycle counts, last successful media/Program times, failure codes, enqueue totals, and
worker currentness/capacity without paths, transcripts, credentials, or DSNs. `Process
Media Now` and `Refresh Program` remain idempotent fallback/diagnostic actions. Automatic
operation never starts or ends a Session, marks a Moment, changes package authority, or
performs external publication.

Media registered before a safely eligible Session remains unresolved until the material
Session input set changes. Demo 2 then reevaluates only the existing deterministic
unresolved association through the accepted policy; unchanged inputs create no revision,
and human or conflict associations remain protected.

For offline qualification, copy `examples/local-schedule.example.json` to the external
schedule path in the Demo 2 example and customize its placeholder Event and Stage keys
together. The optional `rehearsal_fault_media_cycle = 6` setting belongs under
`[autonomous_event_node]` and requires `event_mode = "rehearsal"`. It injects one
unexpected failure on that media attempt per coordinator process. Subsequent successful
media or Program cycles restore `running`; status retains the last failure code and time.
The setting is absent by default and has no API trigger.

The qualification helper replays existing external blocks without changing their sources:

```powershell
cd backend
uv run --no-sync python tests/qualification/block_replay.py --source C:/ExampleCorpus/blocks --watched C:/ExampleRehearsal/recordings --count 10 --cadence-seconds 60
```

Both directories must already exist outside the repository and must not overlap. The
helper selects supported media files in name order, refuses existing destination names,
and publishes each complete copy by renaming a temporary file in the watched directory.
It accepts 1–1,000 blocks, 0.1–3,600 seconds between scheduled copies, and at most 24 hours
of scheduled replay. A failed copy leaves no partial media block; already published blocks
remain. These are qualification tools, not evidence that the owner-run gates have passed.
