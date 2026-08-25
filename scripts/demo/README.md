# Guarded Demo rehearsal controller

Use `StageFlow-Demo.ps1` for the real Razer/Mac Demo rehearsal. It is a thin operator
controller around the existing Python Demo CLI, loopback APIs, and
`Start-StageFlowDemo.ps1`; it does not implement alternate application behavior.

## One-time external configuration

The controller never prints these values. It reads Process scope first and Windows User
scope second:

- `STAGEFLOW_DEMO_POSTGRES_DSN` — required secret; it must connect to exact database
  `stageflow_demo`. Test, validation, worker, qualification, or any other database is
  rejected before controller-triggered writes.
- `STAGEFLOW_API_SHARED_SECRET` — required for `start`, `status`, `rehearsal-report`,
  and `publish-devcon`; use a generated value of at least 32 characters. It is imported
  into Process scope for backend/frontend authentication and never printed.
- `STAGEFLOW_DEMO_CONFIG_PATH` — optional explicit path to the external Demo TOML. If
  absent, the controller accepts exactly one TOML from the bounded `C:\StageFlowDemo`
  or `C:\StageFlowDemo\config` locations.
- `STAGEFLOW_DEMO_CUDA_RUNTIME_PATH` — optional explicit isolated CUDA runtime. The
  qualified `C:\StageFlowDemo\runtime\whisper-cuda-12.4\Release` location is the bounded
  fallback. PATH changes remain process-local and are restored.
- `STAGEFLOW_DEMO_OPERATOR_ID` — optional attributable operator UUID. When absent, the
  controller accepts exactly one actor already recorded for the unambiguous current
  Demo Session; it never invents authority.
- `STAGEFLOW_DEMO_DEVCON_API_KEY` — required only for `publish-devcon`; its presence is
  reported, never its value.

Configuration, model, media, and CUDA directories remain external and uncommitted.

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
preflight, bootstraps idempotently, and performs the explicit Devcon GET/cache sync.
`start` re-verifies the database, launches the existing stack in an owned hidden process,
and waits for loopback health plus the LAN-ready signal. `stop` targets only the recorded
launcher process tree. It does not delete database rows, media, logs, models, or remote
state.

`status` and `rehearsal-report` resolve Event, Stage, and current Session identities
without copy/paste. They summarize bounded media, Operations, worker presence,
Transcription Evidence provenance/counts, Moments, package state, and Devcon cache state.
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

## Devcon publication

Publication is never automatic and never follows Session end. It is permitted only for
the current unambiguous Session when Presentation has ended, package state is `complete`,
the linked External Program Expectation resolves one remote Devcon Event/Session, and the
bounded transcript projection is complete and untruncated.

```powershell
& $demo publish-devcon
```

The controller performs a credential-free GET identity check and displays only the
Event, target Session, field names (`transcript_text` and `duration`), and YES/NO gates.
It does not display field values. The default interactive path asks:

```text
Publish this StageFlow enrichment to Devcon? [y/N]
```

Confirmation is bound to a SHA-256 digest of the exact candidate. Before the PUT, the
controller reconstructs current local state and rejects any digest change. It sends one
bounded PUT with exactly the two named fields. After HTTP 204, it verifies the exact
Git-backed devcon-api/data/sessions/{eventId}/{sessionId}.json file using credential-free,
cache-bypassing reads. A durable mismatch fails closed.

Public GET /sessions/:id is cache-sensitive (max-age=60,
stale-while-revalidate=120), so it is convergence evidence rather than durability
authority. The controller performs only bounded GET polling: one immediate check followed
by at most three 65-second waits. Matching durable Git state plus a still-stale public API
returns published_durable_api_stale, not publication failure. A later match returns
published_durable_api_converged. No read result can cause a second PUT.

-ConfirmHumanAuthority is available only when the human confirmation is already
explicitly captured by the invoking operator workflow. It does not bypass package,
identity, credential, digest, durable Git, or public-convergence gates.

This is Demo tooling, not a production publisher or a LAN-exposed Devcon write surface.

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
performs a Devcon PUT.

Media registered before a safely eligible Session currently remains unresolved because
the accepted Kernel does not reevaluate an existing deterministic association. The
strict Demo 2 acceptance test records that gap; changing this lifecycle semantic requires
the Yellow association-policy decision documented in the Demo 2 plan.
