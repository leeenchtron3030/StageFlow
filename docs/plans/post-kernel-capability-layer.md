# Post-Kernel capability layer

## Status

Proposed

## Subsequent authority

On 2026-08-17 the operator accepted ADR-0025's bounded first-transcription-worker
PostgreSQL Operation/Attempt/lease/Worker model. This resolves the worker-topology Yellow
decision but does not make this multi-phase plan implementation-ready. The transcript
evidence aggregate/persistence plan, provider/model/dependency selection, migration,
runtime composition, and first-worker validation still require separate bounded scope.
ADR-0026 and Packaging Asset identity remain unresolved Yellow decisions.

This is a phased architecture/implementation plan. It is not implementation authority
for the Yellow decisions or for a combined four-capability delivery.

## Execution authority

- **Classification:** Explicit approval required
- **Authority evidence:** Product Constitution; accepted ADR-0001, ADR-0002, ADR-0009,
  ADR-0012, ADR-0013, and ADR-0022 through ADR-0024; accepted Durable Event-Mode Kernel
  architecture and closure; current domain glossary; user-authorized post-Kernel
  product direction.
- **Implementation-ready:** No, as a whole. The human-declared Moment slice can be
  extracted into a Green implementation plan. Accepted ADR-0025 permits a separate
  bounded first-worker plan; automatic authority requires ADR-0026 acceptance; Assembly
  persistence requires packaging-asset identity approval.
- **Required escalation or approval:** Acceptance of the proposed transcript evidence
  persistence/consumer boundary and any consequential provider/model/dependency;
  architecture acceptance of ADR-0026 for automatic authority; explicit packaging-asset
  identity decision before Assembly persistence; approval of each selected bounded
  implementation plan and schema/migration behavior.

## Related findings or ADRs

- **Finding/disposition:** Architecture baseline disposition D-01 through D-10; Durable
  Event-Mode Kernel independent review, corrections, targeted verification, and Green
  closure DKR-001 through DKR-007 and DKV-001 through DKV-004.
- **Accepted ADR:** ADR-0001, ADR-0002, ADR-0005, ADR-0009, ADR-0012, ADR-0013,
  ADR-0019 through ADR-0025.
- **Proposed ADR:** ADR-0026 (policy-scoped automatic authority).
- **Engineering Directive or other authority:** ED-0006 through ED-0011, ED-0013,
  ED-0020 through ED-0023, ED-0043 through ED-0053, and the root bounded-autonomy policy.
- **UX specifications:** [UX specification index](../ux/README.md), containing Producer,
  Editorial, and shared exact Draft v0.1 documents plus explicitly labeled recovered
  Producer design summaries. These record product direction, not implemented behavior.

## Problem statement

The accepted Kernel now preserves restart-safe Event, Stage, Session, media, package,
and reconciliation authority. StageFlow does not yet provide live editorial intelligence,
run long-lived media/AI work, describe downstream Session presentation, or grant
automatic decisions through explicit policy. Building any of those directly against
provider payloads or UI needs would risk duplicating Kernel authority and prematurely
creating generic infrastructure.

The next phase must establish clear bounded contexts, reuse the existing observation and
runtime contracts appropriately, choose the smallest product-bearing slice, and isolate
the genuinely consequential worker, asset, and automation decisions before code begins.

## Verified current behavior

- PostgreSQL durably owns Kernel Event/Stage/Program Expectation/Session/media/package
  authority and typed history through explicit migrations `0001` through `0005`.
- The Kernel uses direct synchronous application commands, stable operation replay,
  deterministic media association, startup reconciliation, and bounded status
  projections.
- Production Event, Semantic Observation, Evidence, Hypothesis, Finding, Verification,
  Operational Product, strict-time, and recursive-immutability contracts exist.
- Transcript and vision adapters report source-output availability; they explicitly do
  not transcribe, infer, persist provider results, or run models.
- Runtime/Event Mode/resource policy contracts are immutable declarations. The Software
  Agent Runtime is a synchronous process-local lifecycle and not a durable worker.
- The media collection coordinator is a caller-driven bounded cycle; the Runtime asset
  assembly plan concerns Completed Media Asset manifests, not downstream Session
  presentation.
- Program Expectation contains title and speaker display strings but no participant
  identity, ordering, role, affiliation, or observed-attendance authority.
- No provider SDK, LLM/transcription execution port, FFmpeg boundary, Durable Operation,
  attempt, lease, worker registry, Editorial persistence, Assembly persistence, or
  automation-policy persistence exists.
- The current glossary already defines Editorial Candidate Moment, Editorial Clip, and
  Hot Moment as an urgency designation.

Evidence was gathered from `backend/app/contexts/production/`,
`backend/app/contexts/events/kernel_contracts.py`, `backend/app/infrastructure/postgres/`,
the architecture/ADR/plan indexes, and the Kernel closure documents. The planning task
does not claim deployment or event readiness.

## Desired behavior

StageFlow gains independently deliverable capability slices that:

- durably preserve human- and machine-origin Editorial Candidate Moments on the
  authoritative Session timeline with explainable provenance;
- let Producer projections show bounded Moment activity and intelligence lag without
  turning every candidate into Producer work;
- support future Editorial review and Editorial Clip creation without coupling to the
  Producer UI;
- execute concrete long-running transcription/model/render work through minimal,
  provider-neutral, restart-safe coordination after the relevant ADR is accepted;
- model downstream Session presentation independently from package correctness; and
- grant automatic authority only through explicit, scoped, versioned policy activation
  with durable decision provenance.

## In scope

- Domain boundaries and first-version contracts for Editorial Candidate Moment,
  provenance, review, and bounded projections.
- Analysis and proposed architecture for Durable Operation, attempts, worker
  capabilities/presence, leases, retry, deferral, and idempotent outputs.
- Event Mode responsibility split among configuration, policy, scheduler, and Producer
  controls.
- Domain boundaries for Assembly templates/revisions/validation/approval and reusable
  packaging assets.
- Policy-scoped approval levels, activation, evaluation, and automatic-decision lineage.
- Producer Work Queue requirements, first-slice sequence, and future Razer/reference
  worker qualification.
- Architecture, glossary/index, ADR, and implementation-plan documentation only in this
  planning task.

## Out of scope

- Production code, database schemas/migrations, dependencies, provider/model selection,
  frontend work, rendering, publishing, delivery, deployment, or machine changes.
- Kernel redesign, Session split/merge, package-finality changes, broker/microservice
  introduction, or automatic recorder/OS control.
- Full Editorial/Marketing workflow, speaker diarization, authoritative participant
  master data, candidate merge/split, and production/Event readiness qualification.

## Constraints

- **Architecture and terminology:** Preserve Kernel authority and use Editorial Candidate
  Moment -> Editorial Clip; Hot is urgency, not approval. Direct deterministic decisions
  remain synchronous.
- **Compatibility:** New records reference current IDs/revisions. Any future public or
  serialized rename needs an explicit compatibility plan. Existing Kernel schemas and
  contracts are not rewritten.
- **Offline/Event Mode:** Core Event operation must remain local-network/offline capable.
  Cloud work is deferrable and workers remain subordinate to production.
- **Security/data handling:** No real event media or customer data in tests. Provider
  secrets stay behind infrastructure-resolved references. Public projections omit raw
  paths, provider payloads, and sensitive diagnostics.

## Implementation approach

### Phase 0 — decisions and slice extraction

1. Review and accept/revise the capability architecture.
2. Accept or reject ADR-0025 before worker persistence; accept or reject ADR-0026 before
   any automatic-authority implementation.
3. Decide Packaging Asset ownership/reuse before Assembly persistence.
4. Extract Phase 1 into a small Green plan with exact contracts, tables, forward/reversal
   migration, repository ownership, and API/application boundaries.

### Phase 1 — human-declared Moment slice

1. Add an Editorial bounded-context contract for `EditorialCandidateMoment`, versioned
   Session-timeline location, provenance/source, and a minimal review projection.
2. Add an idempotent `Mark Moment` application command requiring actor, operation ID,
   Session ID, expected Session revision, declared time, and position/range.
3. Persist candidates and append-only declaration/history in PostgreSQL through an
   explicit forward/reversal migration. Do not add an in-memory authoritative fallback.
4. Add bounded repository queries and Producer projections: count, latest activity,
   generation state, and boundary-exclusion warning.
5. Preserve candidate history across boundary changes; surface excluded/partial-range
   conflict instead of silently deleting or moving the candidate.

### Phase 2 — Editorial review foundation

1. Add bounded, paginated Editorial candidate queries with rationale and provenance.
2. Add append-only review decisions with optimistic revision checks.
3. Allow approval to create an Editorial Clip contract with candidate/decision lineage.
4. Defer clip export, rendering, publishing, assignment, and merge/split.

### Phase 3 — one concrete transcription worker

1. Under accepted ADR-0025 and a separate bounded implementation-ready plan, add only
   the typed Durable Operation, attempt, lease, worker, and reconciliation fields needed
   for local transcription.
2. Define a provider-neutral transcription execution port and a versioned transcript
   artifact/result boundary. Provider-specific formats remain in adapters.
3. Enqueue from an explicit application boundary after eligible Session media exists;
   use stable work/input revision identity and idempotent result commit.
4. Implement bounded PostgreSQL claim/lease polling, database-time expiry, fencing,
   retry/defer/cancel behavior, worker disappearance recovery, and lag/status projection.
5. Compose transcript output availability through the existing transcript ingress
   boundary without turning adapter output into Session/editorial authority.

### Phase 4 — machine candidate generation

1. Add a deterministic candidate policy against versioned transcript/observation inputs.
2. Add inferred model candidates only behind a provider port with model/version,
   analysis-artifact, and evidence lineage.
3. Commit candidates idempotently using source input/policy/model identity.
4. Expose health/deferred/lag operational meaning; keep raw hardware data diagnostic.

### Phase 5 — Assembly foundation

1. After the asset decision, add Packaging Asset identity/content revisions and approval
   lineage without storing blobs in PostgreSQL.
2. Add Assembly Template, Session Assembly, independent Assembly revisions, frozen
   metadata snapshots, validation, and manual approval.
3. Reference a fixed Session package revision and preserve independent revision rules.
4. Defer render execution until a concrete Durable Operation consumer is planned.

### Phase 6 — progressive automation

1. After ADR-0026 acceptance, persist scoped policy identity/version/activation and
   evaluate Evidence -> Policy -> Authority.
2. Begin with one measured, low-risk decision type; keep other types Manual/Assisted.
3. Persist every automatic decision's inputs, policy/model lineage, reason, time, and
   result; preserve later human correction.
4. Add Producer Work Queue items for withheld/exception outcomes, not ordinary candidates.

Every phase receives its own bounded implementation-ready plan. A later phase does not
authorize unfinished earlier infrastructure to become generic.

## Files or modules expected to change

| Path or module | Expected future change |
| --- | --- |
| `backend/app/contexts/editorial/` | Candidate, location/provenance, review, and Clip boundaries |
| `backend/app/contexts/production/event_mode_kernel/` | Read-only references/projections or application composition only; no broad Kernel refactor |
| `backend/app/contexts/work_execution/` (provisional) | Durable Operation, attempt, worker, lease, policy, and ports after ADR-0025 |
| `backend/app/contexts/assembly/` (provisional) | Packaging Asset, template, Assembly/revision, validation, approval after identity decision |
| `backend/app/contexts/automation/` (provisional) | Policy activation/evaluation and automatic-decision provenance after ADR-0026 |
| `backend/app/infrastructure/postgres/` | Explicit repositories and migrations per approved slice |
| `backend/app/api/` | Later bounded read/command adapters; routes do not own decisions |
| `backend/tests/` | Contract, repository, replay, migration, recovery, concurrency, fault, and projection tests |
| `docs/architecture/`, `docs/adr/`, `docs/plans/` | Current-state and completion updates per slice |
| `docs/ux/` | Role-specific bounded interaction and stale/multi-operator behavior specifications |

Provisional package names are planning aids, not authorized public names.

## Data or migration considerations

No schema or migration is added by this planning task.

Each future durable slice requires an approved forward/reversal migration, explicit
backup/restore impact, stable identity and idempotency rules, no implicit rewrite of
Kernel history, strict-aware timestamps, foreign-key/reference behavior that preserves
historical lineage, and migration tests on isolated PostgreSQL. Media/provider blobs
remain outside PostgreSQL. Reversal may remove only the new isolated capability in a
non-production/operator-approved context and must not delete Kernel authority.

Likely future records include candidate/current projection/history; review decisions and
Clip lineage; operation/attempt/worker/presence; transcript/analysis artifact manifest;
packaging asset/content revision; Assembly/revision/approval; and automation policy
activation/decision history. Exact schemas are deliberately deferred to their accepted
slice plans.

## Failure and recovery considerations

- Candidate declaration and review commands are idempotent by operation identity and
  reject conflicting replay or stale Session/candidate revision.
- Boundary corrections retain candidates and surface location conflicts.
- Worker operations are at-least-once; attempts may repeat, but fenced/idempotent result
  commits prevent stale or duplicate authoritative outputs.
- Lease expiry uses database time; worker disappearance makes work eligible for bounded
  recovery without changing domain authority.
- Provider/network failure produces retryable, deferred, or terminal typed outcomes.
  Event Mode may defer cloud work without treating it as failure.
- PostgreSQL loss makes new durable capability authority unavailable; there is no
  process-local fallback. Recovery reconciles leases, incomplete result commits, and
  projection freshness before claiming readiness.
- Assembly references immutable package and asset revisions. A changed dependency makes
  a proposal stale and requires revalidation; it does not mutate old approvals.
- Human correction appends history after any automatic decision.

## Observability requirements

Operators must be able to determine:

- candidate count/latest activity and source origin per active Session;
- transcript/Moment processing health, lag, backlog, deferred reason, and data freshness;
- operation kind/state/attempt count/next eligibility without sensitive provider payloads;
- worker last seen, effective processing roles, enabled/draining/unknown state, and
  consequential capacity limitation;
- why a lease expired, retry occurred, output was rejected as stale, or work was deferred;
- Assembly package/template/asset revisions, validation failures, and approval authority;
- automation policy identity/version/scope/activation and why human review was or was not
  required; and
- Producer Work Queue freshness, truncation, and stable reason/attention codes.

Correlate operations, attempts, artifacts, candidates, decisions, and resulting records
by stable IDs. Do not expose DSNs, source paths, secrets, raw model prompts/responses, or
unbounded diagnostic telemetry in Producer projections.

## Test strategy

Planning validation for this task:

- documentation link/reference inspection;
- `git diff --check`;
- deliberate diff review confirming documentation-only scope.

Required validation for Phase 1:

- contract tests for identity, strict time, recursive immutability, source/provenance,
  optional range, and Hot urgency semantics;
- command/repository tests for exact replay, conflicting replay, stale Session revision,
  concurrency, restart reconstruction, and boundary-exclusion warning;
- isolated PostgreSQL forward/reversal and clean-restore tests;
- bounded projection pagination/limit/truncation tests;
- backend pytest, Ruff, Pyright, and `git diff --check`.

Required later validation:

- lease contention, database-time expiry, fencing, worker crash/reclaim, cancellation,
  retry classification, duplicate output, provider fault, PostgreSQL fault/recovery,
  Event Mode defer/resume, backlog bounds, and multi-process integration tests;
- Assembly revision independence, stale dependency, missing asset/binding, panels and
  optional affiliation, approval replay, and rendering-request idempotency tests;
- automation-scope isolation, policy activation/version, contradictory/missing evidence,
  confidence-only rejection, no self-escalation, automatic provenance, and human
  correction-history tests;
- synthetic reference-worker throughput/coexistence/endurance qualification only after
  implementation, with no real customer media or premature Event-readiness claim.
- scenario-driven UX validation against the
  [36 Event-day cases](../ux/event-day-scenario-validation.md) covering normal scale,
  concurrency, ambiguity, interruption/recovery, lag/backlog, revision propagation,
  offline deferral, cross-role continuity, and Event closeout before high-fidelity UI is
  treated as operationally validated.
- repeatable real-media and vMix evidence collected through the
  [Real-Event Playback Validation and UX Calibration](real-event-playback-validation.md)
  runbook, preserving current-Kernel measurements separately from future workflow
  latency, Moment evaluation, and worker/vMix coexistence qualification.

## Acceptance criteria

- [x] Protected Kernel authority and role separation are recorded.
- [x] Existing abstractions are classified as reusable, bounded extension, legacy, or
  not applicable.
- [x] Editorial Candidate Moment, Mark Moment, provenance, time, review, and Clip
  boundaries are defined without inventing a second approved-Moment authority.
- [x] Producer Moment awareness and Editorial projections are bounded and distinct.
- [x] A concrete transcription consumer justifies the proposed minimal worker model and
  alternatives are recorded in ADR-0025.
- [x] Worker durable versus time-sensitive facts and Event Mode ownership are defined.
- [x] Session Assembly/package revision independence, branding, metadata, and validation
  boundaries are defined.
- [x] Progressive approval and Evidence -> Policy -> Authority are recorded in ADR-0026.
- [x] Producer Work Queue and reference-worker/Producer-client requirements are defined.
- [x] Producer Sessions/Work Queue UX preserves state-versus-work separation, boundedness,
  stale-client behavior, contextual navigation, and Event-close semantics.
- [x] Editorial Event Queue UX preserves Live Triage versus completion review, stable
  prioritization, Producer-mark prominence without approval, lag separation, and
  multi-editor revision safety.
- [x] Cross-role UX preserves one Session identity, independent workflow dimensions,
  historical package-revision basis, and request-based authority handoffs.
- [x] UX requirements are mapped explicitly to accepted Kernel behavior, proposed
  domain/read-model requirements, Yellow-gated work, and deferred capabilities.
- [x] Small-team multi-Stage Editorial coverage, live/post-Session continuity, and shared
  consequence/provenance/state language are captured without claiming implementation.
- [x] Shared visual hierarchy, interaction density, responsive priority, timeline/state
  grammar, and accessibility requirements are captured without creating visual-design
  Yellow decisions or frontend implementation authority.
- [x] Event-day scenario validation captures realistic overlap, degradation, recovery,
  scale, and human-attention pressure plus future component/read-model requirements;
  it is not reported as executed UX qualification.
- [x] The smallest first slice and dependent delivery sequence are explicit.
- [x] ADR-0025 is accepted before worker implementation; implementation remains a
  separate bounded plan.
- [ ] ADR-0026 is accepted or rejected before automatic-authority implementation.
- [ ] Packaging Asset identity is approved before Assembly persistence.
- [ ] Phase 1 is extracted into a Green implementation-ready plan with exact schema,
  migration, acceptance tests, and rollback.

## Rollback or reversal

This task changes documentation only. It is reversible by reverting its documentation
diff; it does not modify runtime behavior or data.

Future slices must be reversible independently. Code/config rollback must stop new
writes before a schema reversal. Data-bearing reversals require operator approval and
lineage export/preservation; accepted candidate/review/automatic-decision history must
not be silently discarded. No plan may reverse Kernel migrations as part of a
post-Kernel capability rollback.

## Open questions

- **Resolved 2026-08-17:** ADR-0025's PostgreSQL
  Operation/attempt/lease/Worker model is accepted; no implementation or provider is
  selected by that acceptance.
- **Yellow:** Accept ADR-0026's scoped activation and automatic-authority provenance?
- **Yellow, deferred until Assembly:** Is Packaging Asset a separate aggregate composed
  with a Completed Media Asset/content manifest, as recommended?
- What service-level thresholds turn intelligence lag/defer state into Producer work?
  This is configuration/policy calibration unless it changes product authority.
- Which importer or editor owns participant identity, ordering, role, and affiliation?
  First-pass Assembly must treat current speaker strings as optional sourced display
  suggestions until that ownership is decided.

## Completion record

- **Implemented revision:** Not applicable; planning only.
- **Files and migrations actually changed:** `docs/PROJECT_BRIEF.md`, architecture/ADR/
  plan/UX indexes, `docs/architecture/system-context.md`,
  `docs/architecture/domain-glossary.md`, `docs/architecture/persistence.md`, this plan,
  the post-Kernel capability architecture, the indexed Producer, Editorial, and shared
  UX specification set, and proposed ADR-0025/ADR-0026. No production code, dependency,
  schema, migration, runtime configuration, or frontend changed.
- **Commands and tests actually run:** Repository inspection with `Get-Content`, `rg`,
  `git status`, and `git log`; changed-document relative-link validation with PowerShell
  `Test-Path`; `git diff --check`; final diff/status review.
- **Results and warnings:** Relative links resolve and `git diff --check` passes. Git
  reports the repository's normal LF-to-CRLF working-copy warning on existing tracked
  Markdown files. Backend/frontend quality suites were not run because the change is
  documentation-only.
- **Execution authority used:** Green documentation planning within the user-authorized
  objective; Yellow decisions remain proposed and unimplemented.
- **Approved deviations:** None.
- **Rollback status:** Documentation diff is reversible.
- **Remaining work:** Create the bounded first-worker/transcript evidence implementation
  plan; decide any consequential provider/model/dependency; review/decide ADR-0026 and
  Packaging Asset identity; extract and approve the Phase 1 Green implementation plan.
