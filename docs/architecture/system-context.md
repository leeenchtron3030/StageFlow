# StageFlow system context

**Baseline:** Contract Stabilization correction branch, through the durable-ingress and
strict-aware timestamp foundations

## System purpose

StageFlow is intended to observe live-event recorded media and supporting production
signals, preserve explainable reasoning and human authority, and eventually coordinate
durable production, editorial, packaging, and delivery workflows. At the current
baseline, it is a contract-and-policy foundation rather than a composed operational
media system.

## External actors and systems

| Actor or system | Current interaction | Accepted future boundary |
| --- | --- | --- |
| Developer/operator | Starts backend/frontend and invokes contract components in tests or caller code | Configures and observes a composed event-mode runtime |
| Technical producer/event operations | No implemented workflow UI/API | Views Session, media, storage, operation, retry, and intervention state |
| Editorial/marketing reviewer | No implemented workflow | Reviews explainable Findings/Candidate Moments; humans retain approval authority |
| Recording/shared-storage system | Files may be inspected only by an explicit one-shot local discovery call | Remains source of media; StageFlow registers completed assets by reference |
| Schedule/conference system | Adapter contracts only | Remains source of planned conference data and external identifiers |
| Transcript/vision providers | Adapter/interpreter contracts only | Optional providers behind adapters; unavailable service must not stop local event work |
| Publishing/delivery destinations | No implementation | Provider-neutral durable operations with idempotency and reconciliation |

No current actor can create a durable Session, submit media through an application API,
claim a Job, run transcription, package a Session, or deliver an output.

## Current runtime components

| Component | Current responsibility | State/durability |
| --- | --- | --- |
| FastAPI application | Resolve four service-shell settings, configure logging, enter a minimal lifespan, serve `GET /api/v1/health` | Process state only; health is liveness |
| Next.js application | Render one static status page | No backend client or workflow state |
| Shared contracts | IDs, errors, results, clocks, and time ranges | Pure/in-memory values |
| Production Events/adapters | Provider-neutral source event contracts plus stable ingress identity | PostgreSQL ingress repository exists but is not composed into FastAPI/startup |
| Dispatcher/interpreters | One structural routing protocol and concrete Event-to-Observation adapters | Caller-created; deterministic synchronous dispatch |
| PostgreSQL ingress adapter | Transactional source-key/fingerprint registration and stable Production Event identity | Durable when used with PostgreSQL; real database validation remains environment-gated |
| Evidence/reasoning/state policies | Deterministic transformation and transition contracts | Caller-invoked; no orchestrator or durable lineage store |
| In-memory Operational State repository | Atomic accepted Recording/Session state, lineage, revision, and operation replay | Thread-safe and explicitly process-local |
| StageFlow Runtime and Software Agent | Immutable deployment description and explicit synchronous lifecycle | Thread-safe and process-local; not started by FastAPI |
| Media collection coordinator | One bounded caller-driven cycle over injected discovery/observation ports | Thread-safe and process-local |
| Local filesystem discovery adapter | Read-only, shallow, bounded candidate discovery for one explicit binding | Stateless; filesystem metadata side effects only |
| Readiness and Completed Media Asset contracts | Evaluate supplied objective facts and validate an immutable completed asset | Callable contracts; no observation executor, assembler, or registry |

## Current data flow

```mermaid
flowchart LR
    HTTP[FastAPI process] --> Health[GET /api/v1/health]

    Caller[Explicit caller or test] --> Runtime[StageFlow Runtime]
    Runtime --> Agent[Software Agent\nprocess-local]
    Agent --> Coordinator[Media collection coordinator\nprocess-local]
    Coordinator --> Discovery[Bounded local filesystem discovery]
    Discovery --> Candidate[Media Asset Candidate]
    Candidate -. no composed observer .-> ResourceFacts[Media Resource Observations]
    ResourceFacts -. caller-only policy .-> Readiness[Readiness evaluation]
    Readiness -. no assembler or registry .-> Asset[Completed Media Asset]

    Source[Source fact] --> Ingress[Durable ingress repository]
    Ingress --> ProductionEvent[Stable Production Event]
    ProductionEvent --> Dispatcher[Dispatcher]
    Dispatcher --> Interpreter[Concrete Observation Interpreter adapter]
    Interpreter --> Observation[Semantic Observation]
    Observation --> Evidence[Evidence]
    Evidence --> Reasoning[Hypothesis / Finding / Verification / Product]
    Evidence --> State[Transition evaluation / acceptance]
    State --> MemoryRepo[In-memory repository]
```

Solid arrows are directly callable. Dashed arrows mark accepted or structurally intended
boundaries that are not composed at this baseline. The ingress-to-dispatch route is
directly callable but is not wired into application startup or a continuous source.

## Current persistence and side effects

- One PostgreSQL ingress table, repository adapter, and forward/reversal migration exist;
  no composed connection ownership, durable queue, worker, outbox, or media registry
  exists.
- Operational State, Agent history, collection history, and operation replay are in
  memory and disappear on process termination.
- The local adapter performs `stat`/`lstat`/`scandir`-style metadata inspection only. It
  does not open media content, watch, poll, recurse, transfer, or delete.
- No provider SDK, outbound HTTP client, FFmpeg, model execution, or delivery side effect
  exists in production code.
- The only implemented HTTP endpoint is process liveness.

## Known deployment assumptions

- Python 3.13 with `uv`; FastAPI/Uvicorn for the backend.
- Node/npm with Next.js for the frontend.
- Current shared mutable components coordinate threads in one process only.
- Discovery requires an explicitly configured local-file or mounted-volume binding in the
  caller's filesystem namespace.
- Current contracts can run without Internet access, but there is no complete offline
  event workflow to deploy.
- PostgreSQL is the accepted authoritative store and Psycopg is a current backend
  dependency; Redis, workers, FFmpeg, transcription models, containers, and provider
  services remain absent.

## Accepted future boundaries

The accepted direction is one modular monolith with one relational durable store, media
content outside the database by reference, a narrow composition root, startup
reconciliation, and database-backed at-least-once operations only where asynchronous or
external work needs them. The accepted media path is documented in
[segment-lifecycle.md](segment-lifecycle.md). Session authority is documented in
[session-lifecycle.md](session-lifecycle.md), including remaining open decisions.

The following are explicitly not approved: microservices, a first-phase broker,
cloud-required event operation, direct live NDI/SDI capture, directories as Sessions,
discovered files as completed assets, Operational State as the Session aggregate, or
automatic machine editorial publication.

## Evidence sources

- [Architecture baseline review](../reviews/architecture-baseline-review.md)
- [Authoritative disposition](../reviews/architecture-baseline-disposition.md)
- [Engineering Directive index](../../ENGINEERING_DIRECTIVES.md)
- `backend/app/main.py`, `backend/app/core/`, and `backend/app/contexts/production/`
- `backend/pyproject.toml`, `frontend/package.json`, and application READMEs
- [Reasoning model](../05_Reasoning_Model.md)

Operational deployment, hardware/media behavior, multi-process recovery, provider
failure, authentication, retention, and conference-scale performance remain unverified
because their corresponding implementations or environments do not exist.
