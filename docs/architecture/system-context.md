# StageFlow system context

**Baseline:** Accepted Durable Event-Mode Kernel operational foundation after targeted
verification and Green follow-up closure

## System purpose

StageFlow is intended to observe live-event recorded media and supporting production
signals, preserve explainable reasoning and human authority, and eventually coordinate
durable production, editorial, packaging, and delivery workflows. At the current
baseline, it includes a bounded durable Event/Stage/Session/media Kernel and the first
human-declared Editorial Candidate Moment slice behind the existing shell. That
foundation is closure-validated but is not event-ready software.

## External actors and systems

| Actor or system | Current interaction | Accepted or proposed future boundary |
| --- | --- | --- |
| Developer/operator | Loads validated Kernel configuration, explicitly bootstraps Event/Stages, and invokes application commands | Uses a future authenticated setup/control surface |
| Technical producer/event operations | Reads Kernel Event/Stage/Session/media/recovery status through an API; no UI | Uses future Mission Control and bounded Work Queue workflows from a worker-independent client |
| Editorial reviewer | Can read bounded declared, unreviewed Candidate Moment state; no review-decision workflow | Reviews explainable Editorial Candidate Moments and creates human-approved Editorial Clips |
| Marketing user | No implemented workflow | Consumes approved clips, assembled outputs, metadata, and delivery state rather than raw candidate intelligence |
| AI/media Event Worker | No implementation | Claims approved PostgreSQL-backed work for transcription, analysis, vision, proxy, or rendering without owning Session/media authority |
| Recording/shared-storage system | Files may be inspected only by an explicit one-shot local discovery call | Remains source of media; StageFlow registers completed assets by reference |
| Schedule/conference system | Optional bounded Devcon public-program read reconciles one configured Event/room into External Program Expectations | Remains source of planned conference data and external identifiers |
| Transcript/vision providers | Adapter/interpreter contracts only | Optional providers behind adapters; unavailable service must not stop local event work |
| Publishing/delivery destinations | Guarded Demo controller can perform one explicitly confirmed Devcon transcript/duration enrichment write | Future provider-neutral durable operations with idempotency and reconciliation |

An application caller can create a durable human-authorized Session, register media
through the Kernel service, and declare an unreviewed Editorial Candidate Moment. The
bounded Demo controller can explicitly publish approved transcript/duration enrichment
to one matched Devcon Session under ADR-0028; it is not a general publication or
delivery workflow and cannot control a recorder. No actor can create an Editorial review
decision or Clip, publish editorial output, or deliver an output through this slice.

## Current runtime components

| Component | Current responsibility | State/durability |
| --- | --- | --- |
| FastAPI application | Preserve liveness; optionally load Kernel configuration, verify schema, reconcile, and serve bounded read-only Kernel/MTE projections | PostgreSQL authority; process state is composition only |
| Next.js application | Render the read-only Producer operational UI and minimum Editorial shell from explicit fixtures or Kernel/MTE projections | No frontend authority or durable workflow state |
| Shared contracts | IDs, errors, results, clocks, and time ranges | Pure/in-memory values |
| Production Events/adapters | Provider-neutral source event contracts plus stable ingress identity | Completed-asset ingress is composed in the bounded Kernel cycle; general dispatcher paths remain caller-created |
| Dispatcher/interpreters | One structural routing protocol and concrete Event-to-Observation adapters | Caller-created; deterministic synchronous dispatch |
| PostgreSQL ingress adapter | Transactional source-key/fingerprint registration and stable Production Event identity | Durable and freshly validated with isolated PostgreSQL 17.10; deployment remains unapproved |
| Durable Kernel repository | Event/Stage, Program Expectation, Session, media registry/association, completion snapshots, reconciliation, human-command replay, and typed history | Normalized PostgreSQL current state plus typed append-only history |
| Media Timing Evidence repository | Append/retrieve immutable asset-linked Observed facts, Derived intervals, qualification state, and exact application replay | Additive PostgreSQL revision/history authority; advisory only |
| Durable Kernel service | Explicit bootstrap, idempotent human Session boundaries/assignment/completion, readiness/asset adapters, stable ingress, and provenance-bearing categorical association | Direct synchronous application boundary |
| Devcon integration | Optional bounded public-program read/reconciliation plus one guarded human-confirmed transcript/duration enrichment write and separated durability/cache verification | Devcon remains external authority; network failure does not replace local Kernel state |
| Editorial Candidate Moment repository/service | Idempotent declared Candidate creation, bounded per-Session reads, and append-only boundary-conflict evaluation | PostgreSQL declaration and location-history authority; no in-memory runtime fallback |
| Evidence/reasoning/state policies | Deterministic transformation and transition contracts | Caller-invoked; no orchestrator or durable lineage store |
| In-memory Operational State repository | Atomic accepted Recording/Session state, lineage, revision, and operation replay | Thread-safe and explicitly process-local |
| StageFlow Runtime and Software Agent | Immutable deployment description and explicit synchronous lifecycle | Runtime graph is constructed after Event/Stage authority; lifecycle remains process-local |
| Media collection coordinator | One bounded caller-driven cycle over injected discovery/observation ports | Thread-safe and process-local |
| Bounded Kernel media cycle | Configured discovery, durable resource observations, readiness, asset registration, stable ingress, and association/reconciliation | Explicit synchronous startup or caller-triggered cycle; PostgreSQL is authority |
| Local filesystem discovery adapter | Read-only, shallow, bounded candidate discovery for one explicit binding | Stateless and composed into the Kernel media cycle |
| Readiness and Completed Media Asset contracts | Evaluate supplied objective facts and validate immutable assets; Kernel adapters persist decisions/assets | Callable policy plus durable Kernel registry |

## Current data flow

```mermaid
flowchart LR
    HTTP[FastAPI process] --> Health[GET /api/v1/health]

    HTTP --> Status[GET /api/v1/kernel/status]
    Config[Validated TOML + secret reference] --> Bootstrap[Explicit Event/Stage bootstrap]
    Bootstrap --> DB[(PostgreSQL authority)]
    Config --> Runtime[StageFlow Runtime]
    Caller[Startup or explicit bounded caller] --> Cycle[Bounded Kernel media cycle]
    Runtime --> Cycle
    Cycle --> Discovery[Bounded local filesystem discovery]
    Discovery --> Candidate[Media Asset Candidate]
    Candidate --> ResourceFacts[Durable Resource Observations]
    ResourceFacts --> Readiness[Readiness evaluation]
    Readiness --> Asset[Completed Media Asset]
    Asset --> Registry[Durable media registry]
    Registry --> AssetIngress[Stable asset ingress]
    Registry --> Association[Session association / unresolved / conflict]
    Registry --> Timing[Optional advisory Media Timing Evidence]
    Association --> DB
    AssetIngress --> DB
    Status --> DB

    Source[Other source fact] --> GeneralIngress[Durable ingress repository]
    GeneralIngress --> ProductionEvent[Stable Production Event]
    ProductionEvent -. other caller-created paths .-> Dispatcher[Dispatcher]
    Dispatcher --> Interpreter[Concrete Observation Interpreter adapter]
    Interpreter --> Observation[Semantic Observation]
    Observation --> Evidence[Evidence]
    Evidence --> Reasoning[Hypothesis / Finding / Verification / Product]
    Evidence --> State[Transition evaluation / acceptance]
    State --> MemoryRepo[In-memory repository]
```

Solid arrows are directly callable or composed in the bounded Kernel. Dashed arrows mark
other accepted or caller-created reasoning paths that are not composed into the Kernel.
There is no watcher, broker, worker, or uncontrolled loop.

## Current persistence and side effects

- PostgreSQL ingress and normalized Kernel tables, repositories, typed history, and
  explicit forward/reversal migrations exist. No queue, worker, lease, or outbox exists.
- PostgreSQL also preserves immutable human-declared Editorial Candidate Moments and
  append-only Session-boundary location evaluations through migrations 0008 and 0010.
- Loss of PostgreSQL invalidates reconciliation freshness for the live process; restored
  reachability remains recovering/not ready until a fresh bounded reconciliation succeeds.
- Operational State, Agent history, collection history, and operation replay are in
  memory and disappear on process termination.
- The composed path performs `stat`/`lstat`/`scandir`-style inspection plus one bounded
  open/read access check. It does not decode media, watch, poll, recurse, transfer, alter,
  or delete source media.
- No provider SDK is present. The bounded Devcon adapters use the standard-library HTTP
  client for optional program GETs and the explicitly invoked guarded enrichment PUT;
  they do not participate in the local event-critical media path. The selected local
  transcription adapter uses separately documented model/media dependencies. No FFmpeg,
  model execution, or delivery side effect exists in the Editorial Candidate Moment slice.
- HTTP exposes process liveness, read-only Kernel operational status, bounded
  asset-specific MTE history, and an authenticated idempotent `Mark Moment` command plus
  bounded Editorial reads; authoritative mutation remains an application boundary rather
  than a public control API. Review, Clip, and publication authority remain absent.

## Known deployment assumptions

- Python 3.13 with `uv`; FastAPI/Uvicorn for the backend.
- Node/npm with Next.js for the frontend.
- Current shared mutable components coordinate threads in one process only.
- Discovery requires an explicitly configured local-file or mounted-volume binding in the
  caller's filesystem namespace.
- The Kernel configuration and durable path do not require Internet access; physical
  event qualification and deployment remain unapproved.
- PostgreSQL is the accepted authoritative store and Psycopg is a current backend
  dependency; Redis, workers, FFmpeg, transcription models, containers, and provider
  services remain absent.

## Accepted future boundaries

The implemented direction is one modular monolith with one relational durable store, media
content outside the database by reference, a narrow composition root, startup
reconciliation, and database-backed at-least-once operations only where asynchronous or
external work needs them. The accepted media path is documented in
[segment-lifecycle.md](segment-lifecycle.md). Session authority is documented in
[session-lifecycle.md](session-lifecycle.md). The accepted first operational slice,
component reuse map, and resolved decisions are documented in the
[Durable Event-Mode Kernel architecture](durable-event-mode-kernel.md).
The proposed layer above that foundation, including live intelligence, worker execution,
Session Assembly, scoped approval policy, sequencing, and remaining Yellow decisions, is
documented in the
[Post-Kernel capability architecture](post-kernel-capability-layer.md).

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

Operational deployment, full hardware/media behavior, multi-process concurrency,
provider failure, authentication, retention, and conference-scale performance remain
unverified because their corresponding implementations or environments do not exist.
