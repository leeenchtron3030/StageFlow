# Post-Kernel capability layer

## Status and purpose

**Status:** Proposed architecture. Accepted product direction is distinguished below
from consequential decisions that still require approval.

This document defines the first capability layer above the accepted Durable Event-Mode
Kernel. It covers live Session intelligence, bounded AI/media worker execution, Session
Assembly, and progressive approval automation. It remains planning authority for those
broader capabilities. Only the bounded transcription Work Execution and evidence slice
explicitly authorized by ADR-0025 and its implementation-ready plan is currently
implemented. ED-0067 also implements the bounded Phase 1 human-declared Editorial
Candidate Moment slice; review decisions, Clips, and machine-origin candidates remain
future work.

The Kernel remains the protected operational foundation. New capabilities reference its
Business Event, Stage, Program Expectation, realized Session, media registration,
association, package revision, completion, reconciliation, time, and PostgreSQL
authority. They do not create parallel versions of those concepts.

Related authority includes the Product Constitution, ADR-0001, ADR-0002, ADR-0009,
ADR-0012, ADR-0013, ADR-0022 through ADR-0025, the current domain glossary, and the
Durable Event-Mode Kernel architecture and closure record. ADR-0025 accepts the bounded
first-transcription-worker execution model; proposed ADR-0026 retains the unresolved
automation-authority decision.

## Protected Kernel boundary

The following remain authoritative and are inputs to this layer:

- a Business Event owns its Stages and Program Expectations;
- a realized Session has one Stage and human/authoritative boundaries;
- discovery, readiness, Completed Media Asset registration, and Session association
  retain separate meanings;
- associated, unresolved, and conflict outcomes remain explicit;
- package revision and human completion authority remain Kernel concerns;
- PostgreSQL is the operational authority, with explicit migrations and reconciliation;
- strict aware time and injected infrastructure clocks remain required;
- local-first Event Mode and the modular monolith remain protected; and
- worker or intelligence failure cannot rewrite or invalidate Session/media authority.

Session Package answers what happened on stage and whether the authoritative deliverable
set is correct. Session Assembly answers how an eligible package should be presented
downstream. Editorial intelligence answers what may be worth reviewing. None substitutes
for another.

## Product and role direction

The Producer owns Event operation, Session authority, media completeness, exceptions,
and package correctness. The Producer surface may run on a lightweight workstation and
must not depend on local GPU execution.

Dedicated Event Nodes may run transcription, model analysis, vision, candidate
generation, proxy creation, and rendering. A Node is an execution placement, not a
semantic authority or trust tier. Worker loss ordinarily defers intelligence and exposes
lag or an operational exception; it does not stop Session/media operations.

Editorial owns detailed candidate review and the decision to create an Editorial Clip.
Marketing consumes approved editorial or assembled outputs rather than raw intelligence.
Machine brand, operating system, and model provider remain adapter/deployment details.

The companion
[Cross-Role Session Experience specification](../ux/cross-role-session-experience.md)
preserves one authoritative Session ID while showing Production, Intelligence,
Editorial, Assembly, Rendering, and Marketing as independent workflow dimensions. No
role receives a parallel Session identity or one ambiguous master `complete` status.
Role-owned objects reference the Session and the package revision or other authoritative
basis they actually used. Later upstream corrections preserve historical downstream
decisions and produce typed revalidation/exception projections rather than rewriting
history.

Cross-role requests preserve authority: Editorial may request Production review,
Marketing may request Editorial review, and Producer may declare a Candidate through
`Mark Moment`. A request never silently performs the other role's authoritative command.
Shared navigation carries the same Session identity across workspaces while each role
sees only the detail needed for its responsibilities.

The shared interaction grammar is defined by the
[Shared UX State & Component Language](../ux/shared-state-component-language.md) and
[Visual Design System & Interaction Density](../ux/visual-design-system-interaction-density.md),
with the [Connected Low-Fidelity Wireframes](../ux/connected-low-fidelity-wireframes.md)
providing the interaction model. Healthy state is quiet; health, impact, attention,
proposal, and authority remain separate. Operational meaning precedes workflow detail,
evidence/provenance, and technical telemetry. Program Expectations remain visually
External, Session-relative and wall-clock time remain labeled and distinct, and color or
animation cannot be the only state carrier.

The [Event-Day UX Scenario Validation specification](../ux/event-day-scenario-validation.md)
is the shared pressure-test contract for these requirements. It covers concurrent Stage
turnover, Producer/Editorial overlap, worker and database degradation/recovery, stale and
multi-operator clients, package revision impact, candidate floods, Assembly/automation
exceptions, scale, offline Event Mode, and safe closeout. It is future acceptance input,
not evidence that the UI or supporting capabilities currently pass those scenarios.
Staffing mix, Producer-mark urgency, near-live target, Mission Control intelligence
density, and exact venue-exit blockers remain operational calibration questions; they do
not create new authority semantics at this planning boundary.

## Capability boundaries

| Boundary | Owns | Must not own |
| --- | --- | --- |
| Kernel Production | Event, Stage, Program Expectation, Session, registered media, association, package revision/completion | Editorial value, worker leases, branding presentation, publication |
| Editorial Intelligence | Editorial Candidate Moments, source/provenance, review decisions, bounded Editorial projections | Session realization, package completeness, automatic publication |
| Work Execution | Durable Operations, attempts, leases, worker presence/capability, retry/defer state | Domain truth in opaque job payloads, Session authority, provider-specific semantics |
| Assembly | Assembly Template, Session Assembly and revision, validation, approval, packaging-asset references | Session boundaries, package revision, source-media readiness |
| Automation Policy | Versioned policy activation and authority evaluation per decision type | Evidence production, silent self-escalation, a global automation switch |
| Operational Read Models | Bounded Producer/Editorial/worker projections and work items | New authoritative workflow state inferred only from display needs |

Direct synchronous calls remain correct for deterministic domain decisions. Durable
Operations are reserved for work that is actually asynchronous, long-running, retryable,
or externally dependent.

## Existing abstraction inventory

| Existing boundary | Classification | Post-Kernel use |
| --- | --- | --- |
| `EntityId`, strict-aware time helpers, recursive immutable metadata | Reusable | Identity, timestamps, and immutable contracts |
| Kernel Session/media repositories, command replay, typed history, bounded status | Reusable | Authoritative references and implementation patterns; do not import editorial state into Kernel tables |
| Production Event, Semantic Observation, Evidence, Hypothesis, Finding, Verification, Operational Product | Reusable with bounded composition | Explainable input and review lineage; a candidate is a specialized Editorial aggregate, not an Observation or generic Operational State |
| Transcript/Vision Source Adapters and interpreters | Requires bounded extension | Accept provider-neutral output availability after execution; they do not perform transcription or inference |
| Operator Source Adapter | Requires bounded extension only for observed operator input | `Mark Moment` is an authoritative application command and durable declaration, not merely an untrusted operator Observation |
| Runtime capability, Event Mode, resource policy, and availability contracts | Reusable as declarative input | Seed worker configuration and Event Mode constraints; current Runtime enums are not a worker registry or scheduler |
| Software Agent Runtime lifecycle | Reusable concepts, not reusable coordination state | Conservative pause/resume and permission vocabulary; current state is synchronous and process-local, so it is not a durable worker/lease system |
| Media collection coordinator and Runtime asset assembly plan | Not applicable to editorial execution/Session Assembly | The coordinator is a bounded synchronous discovery cycle; the existing assembly plan maps Completed Media Asset manifests, not downstream branding |
| Program Expectation `speakers: Sequence[str]` | Requires bounded extension | Supplies provisional display names only; it has no participant identity, role, affiliation, ordering authority, or observed-presence meaning |
| In-memory Operational State repository | Legacy for durable capability authority | Useful policy evidence only; restart-safe candidate, worker, approval, and assembly state belongs in PostgreSQL |
| Foundational broad Candidate Moment/Clip documents | Reusable business meaning, legacy implementation detail | Preserve Candidate → Clip and Hot urgency semantics; do not copy unapproved lifecycle/event shapes mechanically |
| Transcription/vision execution provider interfaces | Bounded transcription port implemented | Provider-neutral transcription port and durable normalized evidence exist; no provider SDK/model runtime, FFmpeg boundary, or vision execution port is selected |

Provider request/response contracts must be isolated behind capability-specific ports.
Provider/model output becomes a versioned analysis artifact with provenance before a
domain policy uses it; raw provider payloads do not become authoritative domain state.

## Live Session intelligence

### Canonical terms and flow

The current glossary already establishes the durable business-language path:

```text
observed facts / transcript / deterministic signals / model artifacts / human mark
  -> Editorial Candidate Moment
  -> append-only Editorial review decision
  -> Editorial Clip when approved
  -> future export/content workflow
```

`Hot Moment` remains an urgency designation on a candidate or work projection. It does
not name an approved aggregate, change editorial tier, or grant approval. A second
“approved Moment” aggregate is not justified for the first slice.

### Smallest coherent candidate

The first durable `EditorialCandidateMoment` needs only:

- stable StageFlow-owned candidate ID and immutable Session ID;
- a versioned Session-timeline location: start position and optional end position,
  together with the Session revision/boundary basis used to interpret it;
- created/updated times and the actor or producer identity;
- epistemic origin: `observed`, `derived`, `inferred`, or `declared`;
- categorical source kind and stable source references;
- reason codes and a concise rationale;
- evidence/provenance references, when the source supplies them;
- policy and model identity/version only when applicable;
- optional score, rank, confidence, participant context, topic context, and notes;
- current review projection derived from append-only review decisions; and
- an optional superseded-by reference. Merge/split graphs are deferred until a real
  Editorial workflow requires them.

Behavior-driving facts are first-class. Metadata is reserved for secondary descriptive
detail and remains recursively immutable. Confidence is optional and advisory; it is
never approval authority.

### Epistemic provenance and source artifacts

The four origins preserve different claims:

- **Observed:** a source reports a phenomenon; this does not itself assert editorial
  value.
- **Derived:** a deterministic, versioned rule produced the candidate from explicit
  inputs.
- **Inferred:** a named/versioned model produced an advisory result.
- **Declared:** a human intentionally marked a possible moment.

`Mark Moment` creates a declared Editorial Candidate Moment through an idempotent
application command carrying actor, operation ID, Session ID, expected Session revision,
timeline position/range, declaration time, and optional note. It does not create an
approval decision or Editorial Clip.

Machine-produced candidates reference immutable analysis-artifact identity plus the
Observation/Evidence/transcript/media inputs available to the policy. The existing
reasoning contracts may contribute lineage, but every model output need not be forced
through Hypothesis/Finding/Verification when it is only an editorial suggestion.

### Time semantics

Candidate location is authoritative on the logical Session timeline, not on an assembled
or rendered output. A first version records integer timeline units, the Session revision
and authoritative boundary basis, and source anchors sufficient to re-evaluate location
after a boundary correction. A stale-revision command fails rather than silently moving
the mark.

Boundary correction does not silently delete a candidate. If the new Session range
excludes or partially excludes the location, the candidate becomes an explicit conflict
in a projection and the Producer receives a correction warning. Opening/closing branding
changes only derived output-relative timing in a later render manifest.

### Review boundary

An `EditorialMomentReviewDecision` is append-only and identifies candidate revision,
actor, decision time, action, notes/reason, and any adjusted Session-timeline range.
Minimum actions are approve-and-create-clip, reject, revise/range-adjust, and defer.
The current review state is a projection; prior decisions remain visible.

Approval creates an Editorial Clip with its own identity, approved range, candidate and
decision lineage, and revision. It does not render, publish, complete a package, or
alter Session boundaries. Merge/split, assignment, richer tagging, transcript playback,
and clip/export state can be added behind this boundary later.

## Producer and Editorial projections

### Producer Moment awareness

Mission Control should expose, per active Session, bounded candidate count, latest
candidate time, intelligence lag, generation state (`healthy`, `deferred`, `blocked`, or
`unknown`), and the highest consequential failure reason. Stage Detail may add a bounded
recent-candidate list and timeline markers. Session Package Review may show candidate
markers and warn when a proposed boundary correction would exclude one.

Candidate existence alone is not Producer Attention. An intelligence issue becomes
Producer information or work only when policy says it threatens an expected service
level, blocks a requested deliverable, or requires an operational decision. Raw GPU
telemetry stays diagnostic.

### Editorial projection

The future Editorial read boundary returns a bounded queue ordered by urgency and age,
candidate location and media context, transcript excerpt where available, rationale,
reason codes, evidence/provenance, source/model/policy identity, notes/tags, and review
history. It supports optimistic revision checks and cursor pagination. It does not expose
provider payloads or require the Producer projection to carry Editorial detail.

The companion
[Editorial Event Queue & Live Triage specification](../ux/editorial-event-queue-live-triage.md)
defines Live Triage and post-Session Review Queue as two views over the same Editorial
state. Cross-Session priority may use Producer marks, explicit Session/track policy,
candidate strength, deadlines, age, and diversity; AI score alone cannot monopolize the
queue. Producer marks normally outrank ordinary inferred candidates but remain
unapproved Editorial Candidate Moments.

The primary v1 UX operating assumption, recorded in
[Editorial Live vs Post-Session](../ux/editorial-live-post-session-operating-model.md),
is a small Editorial team covering multiple concurrent Sessions from structured
intelligence. Dedicated Stage editors remain compatible but are not required by the
architecture. Live Triage asks what deserves attention next; post-Session review asks
what should be preserved or used. Both operate on the same Candidate, review, Session,
and package-revision basis.

Editorial-compute lag and human review lag remain separate. Queue updates must not force
an editor to the live edge, interrupt current playback, or constantly reorder an active
selection. New work enters at controlled boundaries with an explicit refresh/reorder
signal. Presentation may cluster overlapping signals without merging durable candidate
identity.

The future Temporal Workspace supports transcript-first and media-first review against
one Session-relative temporal grammar. Neither the transcript nor a media-player cursor
becomes Session identity or review authority. Playback, seeking, and transcript-follow
behavior remain low-risk navigation; review decisions remain explicit commands.

Fast approve/reject/defer actions require enough context and the same optimistic
revision/append-only decision behavior as deep review. Multiple editors must not silently
overwrite one another; optional soft claiming remains deferred. `Review complete` is a
reserved future policy-governed declaration, not an inferred consequence of a displayed
count.

## UX-to-capability traceability

The UX drafts constrain later behavior without claiming implementation. The following
status map keeps the boundary explicit:

| UX requirement | Current authoritative basis | Proposed capability requirement | Status |
| --- | --- | --- | --- |
| One shared Session ID, Event, Stage, boundaries, package revision, and Program Expectation link | Kernel Session and bounded operational projection | Role-specific projections reference the same IDs/revisions | Kernel basis implemented; role projections future |
| Producer Sessions list and unresolved-human Work Queue | Kernel exposes bounded Stage/recent Session/media/package status | Separate bounded All Sessions and Work Item projections with cursor pagination and stale-state markers | Proposed read models; no frontend/API workflow |
| Editorial Live Triage and Review Queue | No Editorial workflow implementation | Bounded cross-Session Candidate queue with stable ordering, mode, cursor, counts, selection continuity, and freshness | Proposed read model |
| Candidate, Producer-mark, unreviewed, and approved counts per Session | Durable declared Candidate store plus bounded count/latest/conflict projection; no review decisions | Candidate/review projection derived from authoritative candidate and append-only decision records | Phase 1 declared count implemented; reviewed/approved counts future |
| Producer-mark priority | Idempotent authenticated `Mark Moment` command persists declared, unreviewed Candidates | Declared Candidate provenance plus explicit priority signal; never automatic Editorial approval | Phase 1 implemented; cross-Session priority future |
| Candidate rationale and provenance | Observation/Evidence provenance and epistemic vocabulary exist | Candidate source/input, policy/model, actor, reason, and evidence references become first-class | Accepted semantic direction; persistence future |
| Intelligence-processing lag | Transcription Operation timestamps and bounded status projection implemented | Operation/artifact timestamps and backlog projected as transcript/Moment lag | First-worker basis implemented; product read model and calibration remain future |
| Human Editorial review lag | No Editorial queue implementation | Derived age of the oldest eligible priority Candidate, separate from compute lag | Proposed read-model calculation |
| Selected review position versus live edge | Timeline contracts exist but no Editorial playback state | Preserve Session-relative review/playback position independently from current live position; expose explicit behind-live and return-to-live state | Proposed frontend/read-model contract |
| Stable queue interaction | No Editorial queue implementation | Preserve selected Candidate, mode, filters, ordering generation, and return position while arrivals accumulate behind an explicit refresh signal | Proposed frontend/read-model contract |
| Package-revision basis and downstream impact | Kernel package revision/history and late-media reopening are implemented | Candidate/Clip/Assembly/output references retain their historical basis and expose unaffected, revalidate, outside-boundary, or missing-source impact | Historical-basis requirement accepted; impact policy future |
| Cross-role review/request attention | No cross-role request workflow | Typed request/attention projection names required authority and affected Session/revision; it does not perform the target command | Proposed capability; generic task assignment deferred |
| Evidence/provenance inspector | Epistemic/provenance contracts exist | Provide domain-qualified meaning, source, policy/model/actor, evidence, history, and technical detail in progressive-disclosure order | Accepted UX constraint; projection future |
| Shared state/revision components | Kernel exposes package revision and recovery state; Assembly absent | Distinguish health/impact/attention, stale/recovering/available, authoritative/proposed, package/Assembly revision, and read-only history | Proposed shared frontend language; no new domain authority |
| Shared visual system and density | No shared frontend component/design-token system exists | Stable dark-capable surface hierarchy, dense aligned rows, restrained semantic color, provenance/timeline grammar, visible keyboard focus, accessible redundant state cues, and role-specific composition over shared primitives | UX/frontend requirement; no architecture decision or implementation |
| Responsive operational layout | Current frontend is a static shell | MacBook layouts preserve identity/state/action and collapse secondary context; external displays add simultaneous context rather than scaling typography | Future frontend requirement |
| Stale-state action gating | Kernel commands support expected revisions; no control frontend | Mark projections stale, disable authoritative actions, explain why, refresh current revision, and reject stale multi-operator commands | Accepted safety requirement; UI/API composition future |
| Bounded collections | Kernel status is bounded; no Editorial/Work Queue APIs | Cursor, limit, ordering/freshness token, reliable count semantics, explicit truncation, and continuation | Proposed read-model/API requirement |
| Assembly state and approval provenance | Kernel package state is implemented; Assembly is not | Independent Assembly revision/status projection and scoped approval decision | Packaging identity and ADR-0026 remain Yellow-gated where applicable |
| Marketing-ready outputs | No Marketing/render/publish workflow | Consume Editorial-approved, rendered, provenance-bearing outputs without raw Candidate authority | Deferred |

UI-friendly `Moment Candidate` labels map to canonical `Editorial Candidate Moment`.
Approval creates or references an `Editorial Clip`; it does not turn “Hot” urgency into a
separate aggregate. Accepted Kernel facts remain authoritative inputs, proposed domain
and read-model records require later implementation plans, and deferred/Yellow behavior
must remain visibly qualified in UI specifications.

Lag components must name the delayed workflow, comparison anchor, measurement time,
freshness, and operational consequence. Media arrival/readiness lag, transcript or
Moment intelligence lag, and human Editorial review lag cannot substitute for one
another. `LIVE` reports the Session presentation condition only; it does not imply that
media, intelligence, or Editorial review is caught up.

Live Editorial approval accepts editorial value and creates or references the Editorial
Clip boundary; it need not require production-perfect final trimming during time-critical
triage. Exact Clip range revision semantics remain a future bounded design. Falling
behind preserves Candidates and never authorizes automatic rejection, approval, or
discard. Session end changes priority/context rather than moving work to a separate
product.

## Durable execution and workers

Transcription is the first concrete consumer that is long-running, retryable, and may
outlive a process. The Kernel's earlier deferral of a generic Job was correct because its
bounded media cycle is synchronous; that reasoning no longer covers transcription,
model inference, or rendering. Accepted ADR-0025 therefore establishes a minimal
PostgreSQL-backed Durable Operation and Worker coordination boundary.

The minimal model contains:

- a typed operation with stable identity, subject/input revision, priority, availability
  time, Event/deployment scope, idempotency key, and terminal result reference;
- append-only attempts with worker, claim generation/fencing token, start/end, outcome,
  retryability, reason, and diagnostic summary;
- a time-bounded lease using database time, renewable heartbeat, explicit expiry, and
  stale-attempt fencing;
- bounded retry/backoff and first-class deferred/blocked/cancel-requested outcomes;
- idempotent result commit in the domain owner's transaction; and
- startup/periodic reconciliation of expired leases and incomplete commits.

Workers poll PostgreSQL with bounded backoff; no broker is required. Migration 0007 and
the provider-neutral first transcription consumer now prove one operation kind, durable
attempts, database-time leases/fencing, bounded retry/defer, and atomic evidence commit.
Deterministic policies do not become operations, and generalization remains deferred.

### Worker capability and state

Durable facts:

- Worker and Node identities, deployment/Event assignment, enabled/draining state;
- declared processing roles and versioned capability descriptors;
- configured provider/model availability and Event Mode eligibility; and
- attempt history and the operation work actually accepted.

Time-sensitive operational observations:

- heartbeat/last-seen, current availability, capacity declaration, resource pressure,
  and provider/model health, all with observation time and expiry/unknown semantics;
- work in progress derived from live leases; and
- processing lag/backlog derived from operations, not declared by the worker as truth.

VRAM, utilization, temperature, and similar hardware values are diagnostic observations.
They are not Producer authority. Producer projections prefer “transcription 41 seconds
behind live” or “Moment generation deferred” over hardware percentages.

Worker disappearance expires leases and defers/retries eligible operations. It cannot
change Session, media, package, editorial approval, or automation-policy authority.

## Event Mode execution policy

Responsibilities are deliberately separated:

| Owner | Responsibility |
| --- | --- |
| Versioned configuration | Network mode, worker enablement, role allow-list, resource ceilings, concurrency ceilings, provider/model allow-list |
| Deterministic policy | Priority, local/cloud eligibility, defer/pause rules, retry class, service-level thresholds |
| Worker scheduler/claimer | Enforce eligible kinds, priority, leases, concurrency, bandwidth class, and backoff |
| Producer command boundary | Explicit pause/resume/defer/enable controls within allowed scope; never direct OS/process manipulation |

Active Event Mode defaults cloud-dependent work to deferred unless explicitly allowed,
keeps local work within configured ceilings, prioritizes production-safe intelligence,
and allows optional processing to reduce or suspend under pressure. Backlog recovery is
bounded after Event Mode; it does not create an uncontrolled surge. StageFlow observes
or consumes supplied resource pressure and cooperatively limits its own workers. It does
not manage recorders, livestream software, unrelated processes, power settings, or
operating-system resources.

## Session Assembly

Session Assembly is a separate bounded context layered on an eligible Session Package
revision. It owns presentation instructions, not source truth.

Minimum concepts are:

- `AssemblyTemplate`: immutable/versioned ordered roles, placement rules, required
  bindings, applicability, and validation policy;
- `SessionAssembly`: stable ID, Session ID, fixed package-revision input, template
  identity/version, current assembly revision, status, and provenance;
- `AssemblyRevision`: ordered component placements, packaging-asset versions, Session
  media references, resolved metadata snapshot, validation result, and supersession;
- `AssemblyApprovalDecision`: append-only actor/policy authority, revision, reasons,
  evidence, and time; and
- future `RenderRequest`: a Durable Operation referencing one approved immutable
  Assembly revision.

A sponsor-card change creates a new Assembly revision without changing Session package
revision or reopening package completeness. A package revision change can make an
Assembly revision stale/ineligible and require a new proposal; the reverse is not true.
Opening bumper, title card, Session media, sponsor card, and outro are roles/placements,
not changes to the authoritative Session timeline.

### Packaging assets

Completed Media Asset and packaging identity have different meanings. A Completed Media
Asset proves finalized, safe-to-read production media. A packaging asset adds curated
role, applicability, version, approval/trust, and effective-context semantics.

The recommended Yellow decision is a separate `PackagingAsset` aggregate whose immutable
content revision references a stable media manifest or, when appropriate, a Completed
Media Asset. This composes existing resource/readiness semantics without pretending that
all registered production media is branding or that branding approval is media
completion. Media blobs remain outside PostgreSQL; raw filesystem paths are not product
identity.

Minimum packaging-asset facts are ID, name, role/category, content reference/version,
optional measured duration, Event/Stage/track applicability, effective interval,
approval/trust state and decision lineage. The exact aggregate ownership and whether all
content must first become a Completed Media Asset require explicit approval before the
Assembly persistence design.

### Metadata-driven graphics

An Assembly revision freezes a resolved `PresentationMetadataSnapshot` so rerendering is
reproducible. It may include Session title, Event/track labels, and an ordered list of
participant display records. Each value preserves its source and source revision.

The current Program Expectation supplies a title and an unordered set of speaker display
strings. That is enough only for optional first-pass display suggestions. It does not
model participant identity, order, role, affiliation, or observed participation.
Organization/affiliation and role remain optional descriptive facts. Panels require a
list, never a single-speaker field. A future authoritative participant-reference model
should be designed only when an importer/editor workflow supplies real ownership and
correction requirements. Missing descriptive metadata may block a template that declares
it required; it does not make the Session package incomplete.

### Proposal and approval

An Assembly proposal resolves the applicable template against a fixed package revision,
selects approved packaging-asset versions, snapshots metadata, and records provenance.
Validation checks references, versions, template resolution, required bindings, package
eligibility, and prohibited unresolved conditions. Approval then follows the scoped
automation policy. Rendering remains a separate future Durable Operation.

## Progressive approval automation

Automation is policy-scoped by decision type, Event/deployment, and version. It is never
a global Boolean. Proposed ADR-0026 defines the durable authority boundary.

The policy modes are:

- **Manual:** the policy may organize evidence but only a human decides.
- **Assisted:** StageFlow proposes a decision and a human confirms or changes it.
- **Exception-only:** the policy may authorize explicitly qualified cases and routes all
  contradictions, missing evidence, stale dependencies, and out-of-policy cases to a
  human.
- **Automatic:** a specifically named decision type may receive broader automatic
  authority under an explicitly activated policy; safety gates and audit lineage still
  apply.

Modes are configured independently for Session start, Session end, deterministic media
association, package completion, Assembly approval, rendering authorization, and future
publishing. Existing human-only Kernel commands do not gain automatic authority from this
document.

### Evidence -> Policy -> Authority

This layer adopts the following decision structure:

```text
Evidence: what is known, contradictory, absent, stale, or inferred?
  -> Policy: is that evidence sufficient under this scoped, versioned configuration?
  -> Authority: auto-authorize, propose for human review, require human action, or block/defer
```

A model score can be one policy input but never the sole grant of automatic authority.
Policy may consider deterministic invariants, evidence completeness and contradiction,
model/policy version, validation history, dependency health, reconciliation freshness,
and Event configuration.

Automation eligibility metrics may report reviewed count, unchanged acceptance,
correction rate, boundary adjustment, and association correction. StageFlow never
activates a stronger mode based on those metrics. A human/configuration authority must
activate a named policy version and scope.

Every automatic authoritative decision records policy identity/version, activation and
scope, evidence/input references and revisions, relevant model identity/version,
decision time, why human review was not required, actor/authority kind, and resulting
authoritative state/revision. Human correction appends history and preserves the prior
automatic decision. Full event sourcing is not required.

## Producer Work Queue

The Work Queue is a bounded read model answering which Producer decisions or approvals
are waiting. It derives from authoritative commands/decisions, association exceptions,
package state, Assembly approval state, and automation-policy exceptions.

The companion
[Producer Sessions & Work Queue UX specification](../ux/producer-sessions-work-queue.md)
distinguishes three questions: Mission Control asks what needs immediate attention, Work
Queue asks which human decisions/approvals are waiting, and All Sessions shows Event-wide
operational state. A Session is not a task, and ordinary waiting/processing state is not
a Work Item when no human action can advance it.

Each item has stable projection identity, decision type, subject ID/revision, Event and
Stage/Session context, reason and attention codes, priority, created/updated/due times,
blocking dependencies, requested actor role, and a link/command target. Queries require
Event scope, deterministic ordering, cursor pagination, a maximum limit, and explicit
truncation/lag freshness.

Expected items include Session-boundary review, unresolved/conflicting association,
package review or reopening, Assembly approval, auto-approval withheld, and policy or
configuration exceptions. Raw Editorial Candidate Moments are excluded unless a
separate operational consequence requires Producer action.

Priority follows operational consequence before age. Visible sections may distinguish
material intervention from non-urgent review; waiting dependencies and automated/resolved
activity remain state or collapsed evidence rather than manually cleared tasks. A Work
Item routes into its authoritative contextual workflow and does not duplicate that
workflow in a generic task-detail aggregate.

Multi-operator reads and actions require freshness/revision checks. A disconnected
Producer client marks counts and state stale and disables authoritative actions until a
refresh succeeds. If another operator resolves an item, the stale action is rejected and
the current Session/work projection is refreshed. Formal task assignment remains
deferred until event evidence justifies it.

Event close projections must distinguish safe shutdown of capture-critical operation
from completion of downstream transcription, Editorial, Assembly, or rendering work.
Only active/capture-risk, non-durable authority, critical unresolved media, or incomplete
reconciliation can contribute to a future safe-to-leave gate; ordinary downstream
backlog remains visible and non-blocking according to policy.

## Recommended delivery sequence

The earliest product value does not require constructing worker infrastructure first.
Use a bounded sequence C:

1. **Human-declared Moment slice (implemented by ED-0067):** durable Editorial Candidate Moment and append-only
   declaration lineage, `Mark Moment` application command, bounded Session/Stage
   projections, boundary-exclusion warning, and restart/replay tests. No model, worker,
   review UI, or clip rendering.
2. **Editorial review foundation:** bounded candidate query and append-only review
   decision that can create an Editorial Clip contract. No export/publishing.
3. **Concrete transcription execution (bounded substrate implemented):** migration 0007
   and its internal contracts/repository implement the Durable Operation/Attempt/Worker
   pieces, provider-neutral transcript evidence, and bounded status projection. A real
   provider/model and deployment qualification remain separate Yellow work.
4. **Machine candidate generation:** deterministic and then inferred candidates consume
   versioned transcript/analysis artifacts with provenance and idempotent outputs.
5. **Assembly foundation:** after packaging-asset identity is approved, add templates,
   proposals, independent revisions, validation, and manual approval.
6. **Scoped automation:** after ADR-0026 acceptance and sufficient measured evidence,
   enable one low-risk decision type at a time. Rendering and publishing remain later
   consumers.

This order validates the editorial domain and gives `Mark Moment` value before building
asynchronous infrastructure, while still tying the worker design to a real consumer.

## Reference-worker and Producer-client validation

The current Razer may later serve as one reference Event Worker, but qualification must
be hardware-neutral and use synthetic/non-customer media. Planned validation covers:

- capability declaration and GPU/VRAM diagnostic observation;
- transcription throughput, candidate latency, lag under parallel Sessions, and bounded
  backlog recovery;
- CPU/GPU/disk coexistence within configured ceilings;
- process kill/restart, lease expiry/reclaim, stale-attempt fencing, PostgreSQL outage,
  idempotent result replay, and worker disappearance;
- local-network isolation, offline/local provider behavior, cloud deferral, and bandwidth
  protection; and
- long-running stability representative of an Event, without claiming Event readiness
  from a short benchmark.

The Producer client communicates with the reachable StageFlow control plane, not an
individual worker. Worker restart, overload, disappearance, or backlog affects
intelligence status and eligible work only. Mission Control and authoritative
Session/media operations remain available while PostgreSQL/control-plane dependencies
are healthy.

## Decision classification

### Green once a bounded implementation plan is approved

- use the existing `Editorial Candidate Moment` -> `Editorial Clip` terminology and
  treat Hot as urgency;
- create declared candidates from `Mark Moment` without approval;
- use Session-relative time with strict revision checks and explicit boundary conflicts;
- preserve first-class provenance and immutable secondary metadata;
- add bounded, paginated Producer/Editorial projections;
- keep Producer, Editorial, and Marketing responsibilities separate;
- keep package and Assembly revisions independent;
- keep workers provider-neutral, local-first, and subordinate to Event production; and
- use PostgreSQL for new durable authority with explicit migrations, restart recovery,
  and no in-memory fallback.

Green classification does not authorize implementation from this proposed document by
itself. Each slice still needs a bounded implementation-ready plan and objective tests.

### Resolved decision

- **ADR-0025:** accepted on 2026-08-17 for the PostgreSQL Durable
  Operation/Attempt/lease/Worker model and its first transcription consumer. The bounded
  migration-0007 substrate is implemented; this does not select a real provider/model,
  authorize automatic enqueue, or expand Session/media/Editorial authority.

### Yellow decisions

1. **ADR-0026:** accept versioned, policy-scoped automatic decision authority and
   activation/provenance semantics.
2. **Packaging asset identity:** approve the recommended separate Packaging Asset
   aggregate and its composition with Completed Media Asset before Assembly persistence.

Moment naming is not Yellow at this baseline because the current qualified glossary
already establishes Editorial Candidate Moment, Editorial Clip, and Hot urgency. A
future change to those durable/public terms would be Yellow.

## Deferred capabilities and non-goals

Deferred work includes model/provider selection, speaker diarization and authoritative
participant identity, candidate merge/split, clip export, rendering, publishing,
delivery, cloud scheduling, a transactional outbox, broker adoption, cross-Event worker
federation, automatic OS/recorder control, and production hardware qualification.

This architecture does not authorize production code, dependencies, schemas,
migrations, frontend work, deployment, machine-setting changes, or event-readiness
claims.
