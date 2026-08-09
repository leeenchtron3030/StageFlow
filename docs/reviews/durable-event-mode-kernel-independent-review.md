# Independent phase-completion review — Durable Event-Mode Kernel

**Review date:** 2026-08-09

**Reviewer role:** Fresh independent Codex reviewer

**Reviewed baseline:** `33a7d11` (`main`), 17 commits ahead of `origin/main`

**Review mode:** Review only; no production code, tests, schema, migration,
configuration, dependency, or architecture document was changed

**Recommendation:** **DO NOT ACCEPT**

This artifact is review evidence, not architecture authority. The recommendation applies
only to completion of the first Durable Event-Mode Kernel phase. It is not a production-
readiness or event-readiness decision.

## Executive conclusion

The branch contains a coherent, architecture-contained local-first Kernel candidate and
substantial credible validation. PostgreSQL authority, explicit bootstrap, bounded media
cycles, conservative file inspection, durable replay, advisory boundary proposals, and
the absence of premature workers/brokers are particularly strong.

The phase cannot yet be accepted because three High correctness defects remain:

1. the real filesystem pipeline supplies no media interval, yet same-Stage turnover can
   automatically associate that ambiguous media to the newly active Session;
2. human reassignment away from a completed Session changes its package membership while
   leaving the old package `complete` at the approved revision; and
3. a live process that observes PostgreSQL loss reports `ready` immediately after the
   database returns by reusing the pre-outage completed reconciliation.

Four bounded Medium/Low findings concern association provenance, Producer projection
completeness/boundedness, human-command replay/history constraints, and stale current-
state documentation. The recommended corrections are Green under the already accepted
ADRs and Kernel plan. No new Yellow/Red product or architecture decision is required.

## 1. Actual review scope

The initial worktree and index were clean. No Git lock existed. The reviewed range was
`origin/main..33a7d11`, comprising the completed Contract Stabilization work and Durable
Kernel commits through:

- `05c2641 feat: add durable event-mode kernel foundation`
- `4077446 test: verify durable kernel contracts and recovery`
- `17a1992 test: cover kernel status dependency failures`
- `8671251 feat: compose validated StageFlow runtime`
- `e008b15 feat: complete bounded durable kernel workflow`
- `4638ac2 test: add durable kernel qualification harness`
- `33a7d11 docs: record durable kernel qualification closure`

The aggregate range changes 254 files because Contract Stabilization is part of the
branch. The detailed Kernel review covered deployment configuration, runtime composition,
Event/Stage/Program Expectation contracts, Session/media services, in-memory and
PostgreSQL repositories, migrations `0001` through `0003`, lifecycle ownership, the
status API, Kernel tests, the qualification harness, and completion evidence.

Authority reviewed included the Product Constitution, Engineering Directives,
`docs/PROJECT_BRIEF.md`, the architecture index and relevant lifecycle/persistence
documents, ADR-0019 through ADR-0024, the Durable Kernel plan, Contract Stabilization
review/disposition records, and the Razer qualification report.

## 2. Workstream acceptance map

| Workstream | Classification | Independent conclusion |
| --- | --- | --- |
| WS0 — resolved Kernel decisions | **Satisfied** | ADR-0024 clearly fixes bootstrap, human Session realization, deterministic association, and normalized state/history. |
| WS1 — configuration and composition | **Satisfied** | TOML parsing is non-mutating, secret resolution is infrastructural, Runtime construction is explicit after bootstrap, and HTTP/non-HTTP paths share the same composition. |
| WS2 — aggregate and persistence foundation | **Partially satisfied** | Event/Stage/Expectation/Session authority and PostgreSQL constraints are coherent, but package membership and human-decision replay/history integrity are incomplete. |
| WS3 — durable media observation and registry | **Satisfied** | Candidate, observation, readiness, asset, ingress, and association boundaries remain distinct; replay is durable and registered candidate state is monotonic on rediscovery. |
| WS4 — association, boundaries, package revision, completion | **Not satisfied** | DKR-001 and DKR-002 violate accepted turnover ambiguity and package-revision authority. DKR-004 weakens association provenance. |
| WS5 — startup recovery and reconciliation | **Partially satisfied** | Fresh-process reconstruction and source recovery are strong, but DKR-003 violates live PostgreSQL recovery readiness semantics. |
| WS6 — Producer query boundary | **Partially satisfied** | The route is read-only, redacted, and partly bounded, but DKR-005 prevents it from fully answering completion/provenance questions at a bounded cost. |
| WS7 — reference-node qualification | **Satisfied for phase-review evidence** | The report and harness are credible and honestly bounded. They do not establish conference-duration, vMix, production, or event readiness. |

## 3. Findings

### Critical

None.

### High

#### DKR-001 — Interval-less turnover media is assigned to the new Session

- **Severity:** High
- **Files/symbols:** `backend/app/bootstrap/media_cycle.py::_assemble`;
  `backend/app/contexts/production/event_mode_kernel/service.py::_temporally_eligible`
  and `_automatic_association`
- **Evidence:** The configured filesystem path never supplies
  `CompletedMediaAsset.recorded_start_at` or `recorded_end_at`. `_temporally_eligible`
  treats an active Session as eligible whenever `media_ended_at is None`, while an ended
  assembling Session is ineligible when both interval values are absent. An independent
  executable probe ended Session A, started Session B on the same Stage, registered a
  ready asset with no interval, and observed `associated` to the active Session rather
  than `unresolved`.
- **Failure scenario:** A segment from Session A is finalized/discovered after Session B
  begins. With no trustworthy media interval, arrival order cannot distinguish the two,
  yet the Kernel grants Session B identity automatically.
- **Governing invariant:** ADR-0024 requires ambiguous delayed turnover media to remain
  unresolved; ambiguity reduces automation, no timestamp is invented, and exactly one
  Session must be safe rather than merely active. ADR-0023 rejects directory/arrival
  context as independent Session authority.
- **Recommended correction:** Treat missing interval evidence as insufficient during
  same-Stage turnover whenever a prior Session is still assembling. Preserve the asset
  as registered/unresolved and record categorical reasons. Add behavior tests through
  the real `BoundedMediaCycle`, not only synthetic assets with injected intervals.
- **Green:** Yes. The accepted association rule already determines the correction.

#### DKR-002 — Reassignment can invalidate a completed package without reopening it

- **Severity:** High
- **Files/symbols:**
  `event_mode_kernel/repository.py::InMemoryEventModeKernelRepository.put_association`;
  `infrastructure/postgres/event_mode_kernel_repository.py::put_association`;
  `service.py::assign_asset`
- **Evidence:** Both repositories inspect only the new target Session. They increment a
  revision when that target is complete, but never lock or reopen the previous completed
  Session whose asset membership is being removed. An independent executable probe
  completed Session A at package revision 1, started Session B, reassigned A's asset to
  B, and reconstructed A as `complete`, package revision 1.
- **Failure scenario:** A human corrects an asset from approved package A to Session B.
  Package A no longer contains what its approval represented but continues to claim
  human-approved completion.
- **Governing invariant:** ADR-0023 applies completion to a specific package revision and
  requires relevant late/corrected media to preserve prior approval while returning the
  current package to correction/review. ADR-0024 requires current state and typed history
  to change atomically.
- **Recommended correction:** In one transaction, lock the current association and every
  affected Session. Any membership addition, removal, or reassignment affecting a
  completed package must increment that package revision, project
  `correction_required`, and retain the prior completion and association history. Add
  explicit package-revision membership/history sufficient to identify what was approved,
  plus in-memory and real-PostgreSQL reassignment/concurrency/replay tests.
- **Green:** Yes. Package correction semantics are already accepted; an additive,
  planned migration may implement them.

#### DKR-003 — Live PostgreSQL recovery reuses stale readiness

- **Severity:** High
- **Files/symbols:** `backend/app/bootstrap/event_mode_kernel.py::KernelComponents.status`;
  `backend/app/infrastructure/postgres/event_mode_kernel_repository.py::operational_status`;
  `backend/app/core/lifecycle/lifespan.py::lifespan`
- **Evidence:** `operational_status` declares ready whenever the latest durable
  reconciliation is `completed`; it has no knowledge that the database was unavailable
  after that run. `KernelComponents.status` performs no recovery transition or new
  reconciliation. In an independent same-process real-PostgreSQL probe, status was ready
  after startup reconciliation, failed with `KernelStorageUnavailableError` while the
  database was stopped, and after restart returned ready using the same pre-outage
  reconciliation ID. The assertion-based probe exited successfully; no new
  reconciliation row was created after recovery.
- **Failure scenario:** PostgreSQL restarts while Uvicorn remains alive. The first status
  request after return reports Event Mode ready before configured sources and durable
  state have been reconstructed/reconciled for the recovered dependency epoch.
- **Governing invariant:** ADR-0022 and the Kernel plan require database return to verify
  schema, reconstruct, reconcile, and remain recovering/not ready until reconciliation
  completes. Process-local state cannot be assumed authoritative across dependency loss.
- **Recommended correction:** Detect the unavailable→available dependency transition,
  make readiness false/recovering, and require one explicit bounded recovery
  reconciliation before ready can return. Persist the reconciliation result; any local
  dependency-state flag must remain diagnostic and non-authoritative. Add a live-process
  database stop/start API test that proves the reconciliation ID advances.
- **Green:** Yes. This is the already accepted recovery behavior, not a new retry system.

### Medium

#### DKR-004 — Deterministic association provenance is not reconstructable

- **Severity:** Medium
- **Files/symbols:** `service.py::_automatic_association`;
  `contracts.py::MediaAssociation`; `0002_event_mode_kernel_forward.sql`;
  `kernel_status.py`
- **Evidence:** Automatic decisions always write `evidence_ids=()`. Association records
  have categorical reason codes but no association policy ID/version or durable reference
  to the binding revision, eligible Session/boundary state, or inputs that made the rule
  safe. The API reports association authority and aggregate epistemic kinds but omits
  declared boundary actor/reason and Program Expectation provenance.
- **Failure scenario:** After a binding, boundary, or Session projection changes, an
  operator/reviewer cannot reconstruct why an earlier automatic association was safe or
  distinguish all displayed declared/external inputs from current state.
- **Governing invariant:** ADR-0023 requires association evidence and categorical reasons;
  ADR-0024 requires the rule and inputs to be recorded; the plan requires
  Observed/Derived/Inferred/Declared/External provenance not to be flattened.
- **Recommended correction:** Persist first-class association policy identity/version
  and immutable input/evidence references, and expose applicable declared/external
  provenance in bounded Session/media projections. Do not create a universal Fact table.
- **Green:** Yes.

#### DKR-005 — Producer status is simultaneously unbounded and incomplete for Sessions

- **Severity:** Medium
- **Files/symbols:**
  `PostgresEventModeKernelRepository.operational_status`; `StageOperationalStatus`;
  `backend/app/api/v1/kernel_status.py`
- **Evidence:** Per Stage, every assembling/correction-required Session is fetched with
  no limit or pagination. Conversely, presentation-ended complete Sessions are excluded
  from both the selected Session and assembling list, so their package/completion state,
  expectation link, and completion authority disappear from the Session projection.
  Recent media and proposals are capped at 100, but the Session portion is not.
- **Failure scenario:** A long-running Event with accumulated incomplete Sessions grows
  the status response without bound, while an operator cannot use the same API to answer
  which recently completed package/revision was human-approved.
- **Governing invariant:** The plan requires a bounded operator read model answering
  active, assembling, package/completion, expectation, boundary, and attention questions.
- **Recommended correction:** Define a bounded current/recent Session projection with an
  explicit limit or pagination, include recent completed Sessions and Program Expectation
  links, and expose completion authority/decision identity without returning an
  unbounded catalog.
- **Green:** Yes.

#### DKR-006 — Human decision retries are not idempotent and history constraints are weak

- **Severity:** Medium
- **Files/symbols:** `DurableEventModeKernel.assign_asset`,
  `correct_session_boundary`, `complete_package`, `propose_session_boundary`;
  `stageflow.media_association_history` and `stageflow.session_boundary_history`
- **Evidence:** Bootstrap and Session start have operation IDs/digests, but human
  association/boundary commands do not. Repeating an identical assignment appends a new
  association revision/history row; repeating a boundary correction appends another
  decision. The association-history table does not constrain status/authority shape,
  actor requirements, or `session_id` with the same rigor as current state.
- **Failure scenario:** A UI/network retry of one authorized human action becomes two
  accepted revisions, obscuring whether two decisions occurred and weakening exact replay
  guarantees. A future writer can also persist malformed typed history that current-state
  constraints would reject.
- **Governing invariant:** ADR-0023/0024 and the plan require replay not to duplicate
  association decisions and require typed, append-oriented authoritative history.
- **Recommended correction:** Add bounded command/idempotency identities and request
  digests for externally retried human decisions, return exact replay or typed conflict,
  and strengthen history-table checks/FKs. This is command deduplication, not a generic
  Job framework.
- **Green:** Yes.

### Low

#### DKR-007 — Current authority/status documentation still describes implemented Kernel work as absent

- **Severity:** Low
- **Files:** `docs/PROJECT_BRIEF.md`, `docs/adr/README.md`,
  `docs/architecture/session-lifecycle.md`, `segment-lifecycle.md`,
  `domain-glossary.md`, and the Durable Kernel plan checklist
- **Evidence:** Current-facing text still says Runtime composition, the durable media
  path, authoritative Session/Stage aggregates, and several resolved Kernel decisions are
  absent/open. The plan also leaves the validated Runtime criterion unchecked even though
  the composition exists and was independently exercised. Historical baseline sections
  are correctly retained, but these current-status statements are not consistently
  labeled historical.
- **Failure scenario:** A later contributor follows the architecture index and treats an
  implemented/accepted boundary as open or absent, causing duplicate design or incorrect
  scope decisions.
- **Governing invariant:** The architecture index requires current implementation,
  accepted direction, and historical evidence to remain distinguishable.
- **Recommended correction:** After the blocking corrections, align only current-status
  sections and plan checklists with verified implementation; preserve historical review
  evidence unchanged.
- **Green:** Yes.

## 4. Architecture containment

**Satisfied.** The Kernel remains one Python/FastAPI modular monolith using direct
synchronous calls and PostgreSQL repositories. No microservice, broker, generic durable
Job/worker, lease, outbox, cloud-required event path, AI execution, transcription
execution, Editorial workflow, rendering, delivery, recorder control, multi-node
coordination, or provider-specific core coupling was introduced. Existing transcript,
vision, and agent modules remain contracts/process-local foundations rather than composed
Kernel execution.

## 5. Runtime composition

**Satisfied, subject to DKR-003 recovery semantics.** Configuration parsing does not
bootstrap domain state. `explicit_bootstrap` owns Event/Stage mutation, then constructs
the existing immutable `StageFlowRuntime`. Clock authority is injected. Windows paths are
normalized in the composition adapter without entering domain semantics. FastAPI and
non-HTTP operation use `load_kernel_components_from_environment` / `KernelComponents`.
PostgreSQL repositories are the only composed operational authority; the in-memory
repository is test-only. Per-call Psycopg connections avoid hidden process-local database
state, and shutdown owns no persistent connection that it could leak.

## 6. Event, Stage, Program Expectation, and Session authority

**Mostly satisfied.** Business Event and Stage IDs are StageFlow-owned and immutable.
Stable keys, operation digests, uniqueness, source ownership, replay, source/Stage
removal conflicts, and explicit mutable-description reconciliation are implemented.
Configuration cannot silently replace durable identity. Program Expectations are
revisioned planned-world records and do not create Sessions. Human start supports linked
and ad hoc Sessions, fixes Event/Stage, appends a Declared start boundary, and PostgreSQL
prevents two presentation-active Sessions on a Stage.

The Program Expectation/realized Session distinction is clean. A planned Stage mismatch
is preserved structurally but is not adequately surfaced by the current Producer
projection, which contributes to DKR-004/DKR-005.

## 7. Session lifecycle and completion

**Not satisfied.** Presentation end, package state, human completion, boundary correction,
and package revision are modeled separately. Trailing media can associate, completion
requires human approval, a new association into a completed package reopens it, and
boundary proposals cannot overwrite declared boundaries. DKR-002 nevertheless permits
membership removal/reassignment to leave an invalid completed projection. The schema has
completion and association history but no explicit package-revision membership record
that directly identifies the approved membership set.

## 8. Media pipeline

**Satisfied except where it feeds DKR-001.** The implemented path preserves discovery →
durable candidate → objective observations → readiness → Completed Media Asset → stable
ingress → association. Discovery does not imply readiness. Stat/open/read/stat checks are
conservative; growth breaks the current stability run; configured scans are shallow and
bounded; per-candidate failure is isolated; source files are read-only. Candidate,
asset, ingress, and association replay is durable. Rediscovery no longer regresses a
registered candidate. Crash after asset commit but before ingress/association is
reconciled explicitly.

## 9. Association and turnover

**Not satisfied.** Clear active and timestamp-supported trailing cases work. Overlapping
timestamped turnover media becomes unresolved, structural contradictions become conflict,
and unresolved/conflicting assets remain registered. Human assignment is attributable
and current/history records are separated. The actual filesystem pipeline's lack of
media intervals exposes DKR-001, while DKR-002 and DKR-006 weaken correction and replay.
No AI or opaque confidence is required.

## 10. Epistemic provenance and boundary proposals

**Partially satisfied.** The shared vocabulary distinguishes Observed, Derived, Inferred,
Declared, and External. Resource observations and readiness evaluations are correctly
Observed/Derived. Human boundaries are Declared in history. Proposal schema and contracts
restrict machine proposals to advisory categories, require aware timestamps and evidence,
preserve proposer/policy/model lineage, and never mutate authoritative Session fields.
DKR-004 prevents full association/read-model provenance acceptance.

## 11. PostgreSQL schema and migrations

**Partially satisfied.** `0001` through `0003` form a normalized relational schema with
UUID identity, uniqueness, foreign keys, `timestamptz`, one-active-Session enforcement,
current-state/history separation, and no generic event store or media blobs. Migration
ordering and reversal are explicit. An independent clean database applied all three,
reversed Kernel migrations while retaining `0001_ingress`, and reapplied all three.
DKR-002 and DKR-006 show remaining package/history integrity gaps.

## 12. Reconciliation, restart, and failure semantics

**Partially satisfied.** Fresh repository/process reconstruction covers Event, Stage,
Expectation, Session, boundary, candidate, asset, ingress, association, proposal,
completion, and reconciliation state. Reconciliation is explicit, bounded by configured
sources/candidate counts, and replay-safe. Source loss degrades the affected binding,
preserves durable media, and recovers after restoration. PostgreSQL loss raises typed
storage errors without an authoritative memory fallback and never modifies source media.
DKR-003 blocks acceptance of live PostgreSQL return behavior.

## 13. Producer operational API

**Partially satisfied.** `/api/v1/kernel/status` is read-only, uses stable IDs, returns
structured 503 during database loss, separates configured/ready/recovering concerns,
redacts DSN and raw source paths, and caps recent media/proposals. It exposes Stage source
health, active/assembling state, media counts/identities, conflicts, unresolved items,
proposals, and reconciliation state. DKR-004/DKR-005 prevent complete provenance,
package/completion, and bounded-response acceptance. Startup failures can also report
`configured=false` after a configuration was supplied, a localized truthfulness issue
that should be handled with DKR-005 rather than treated as a separate phase blocker.

## 14. Qualification evidence audit

The Razer artifact is credible as bounded evidence and maps to callable repository
tooling:

- PostgreSQL 17.10 loopback setup and the recorded archive hash are reproducible.
- Force-kill/restart evidence plausibly exercises fresh-process reconstruction.
- HTTP 503 and fail-closed write behavior map to current exception/API paths.
- Source disappearance, backup/restore, and fresh-graph reconstruction map to the
  checked-in harness and repositories.
- The 197.626-second/26-segment run is explicitly described as short evidence, not
  conference-duration endurance.
- The approximately 180-second, 1,650-rotation, 13.8-GB write workload is correctly
  labeled a proxy, not vMix certification.
- Balanced power, AC/DC sleep, Modern Standby, Hibernate, wake timer, and Fast Startup
  observations are retained without claiming remediation. The unsafe unattended settings
  remain visible.

The artifact did not fabricate evidence, but its database-recovery procedure used an
explicit fresh graph/reconciliation after restart and therefore did not expose DKR-003.
Its turnover test used a deliberately unresolved/conflict Studio case rather than the
real interval-less same-Stage turnover path, and its package scenario did not reassign an
asset away from a completed Session. Qualification is evidence, not proof against those
unexercised cases.

## 15. Test-quality review

The suite is predominantly behavior-first and strong around immutable contracts,
bootstrap replay, source ownership, active-Session uniqueness, timestamp rules,
filesystem replacement, growth/stability reset, candidate failure isolation, stable
ingress, asset-effect crash recovery, proposal non-authority, real PostgreSQL
reconstruction, and API dependency failure.

The main gaps align directly with the findings:

- turnover tests inject media timestamps and do not run the actual interval-less media
  cycle during Stage turnover;
- late-media tests add an asset to a completed Session but do not remove/reassign existing
  completed-package membership;
- PostgreSQL recovery tests reconstruct a fresh repository/graph but do not require the
  same live process to advance reconciliation before ready;
- association tests accept empty evidence lineage and do not assert policy identity;
- status tests do not create completed Session history or prove a hard Session-response
  bound; and
- exact replay tests cover asset registration, not externally retried human decisions.

Some migration tests inspect SQL text, but the real PostgreSQL gate materially validates
the central tables and reconstruction behavior. The missing scenarios should be added at
the behavioral and real-database boundaries, not replaced by additional source/name
assertions.

## 16. Independent validation

Independent commands and results:

| Check | Result |
| --- | --- |
| Official PostgreSQL package | PostgreSQL 17.10 Windows x64; SHA-256 matched `F9AAFCA58E7026A1EF2CAEEE711ACF761671E57904D430ADC85F468374F5A821`; loopback port `55434` |
| Real migration apply/reverse/reapply | Passed; reversal left `0001_ingress` and `production_event_ingress`, removed Session tables, then reapply restored all three ledger rows |
| Full backend with real DSN | `1605 passed, 5 skipped, 1 warning in 9.07s` |
| Ruff | Passed: `All checks passed!` |
| Pyright | Passed: 0 errors, 0 warnings |
| Frontend clean `npm ci` | Passed; 592 packages installed |
| Frontend build/lint/typecheck | All passed; Next.js 16.2.10 production build generated `/` and `/_not-found` |
| npm audit output from clean install | 12 findings: 3 moderate, 9 high; no fix or dependency change |
| `git diff --check` before artifact | Passed |
| Documentation checks | Not run; no Markdown/link checker is configured in repository scripts or CI |

The five backend skips were three unavailable Windows symlink-privilege cases, one
non-portable FIFO case, and one POSIX descriptor-bound `scandir` path. They are not
treated as passes. One existing Starlette/httpx deprecation warning remains.

Independent real-PostgreSQL tests exercised migration application, stable ingress
concurrent replay, Kernel registration/replay, candidate monotonicity, boundary proposal
reconstruction, and fresh repository reconstruction. A separate database stop/restart
probe preserved a newly created Event and returned typed `postgresql_unavailable` while
stopped. The same-process status probe established DKR-003. Two non-mutating executable
probes established DKR-001 and DKR-002.

`frontend/package.json` and `frontend/package-lock.json` remained unchanged.

## 17. Positive verification

The following choices should be protected from unnecessary refactoring:

- PostgreSQL is the sole composed authoritative operational store; media stays by
  reference and recording is independent.
- Explicit bootstrap cleanly separates configuration parsing from domain mutation.
- Program Expectation and realized Session meanings are not collapsed.
- Session realization and authoritative boundaries remain human-declared.
- The local filesystem adapter and later content inspection both fail conservatively.
- Durable candidate state is monotonic across rediscovery/restart.
- Asset registration precedes stable ingress, and crash-window replay repairs downstream
  effects without duplicate association history.
- Ambiguous/conflicting outcomes preserve media rather than discarding it.
- Boundary proposals are genuinely advisory and preserve model/policy/evidence lineage.
- Bounded synchronous work avoids premature Jobs, leases, workers, outbox, broker, or
  microservice complexity.
- The qualification report is unusually careful about distinguishing short/proxy
  evidence from event readiness.

## 18. Correction authority and escalation

All DKR-001 through DKR-007 corrections are Green under ADR-0023, ADR-0024, and the
approved Durable Kernel plan. They are corrections to already decided semantics, not new
product behavior. Because this was explicitly review-only, none was implemented here.

No Yellow architecture decision or Red operational action is currently required. Stop
and escalate only if correction work discovers a need to change Session/package
semantics, authorize a different association rule, introduce a compatibility break, or
perform a destructive migration.

## 19. Phase recommendation

## DO NOT ACCEPT

The candidate is architecture-contained and close to a coherent first restart-safe
local Event-Mode system, but DKR-001, DKR-002, and DKR-003 are High operational
correctness defects under the accepted phase criteria. They must be corrected and
independently revalidated before formal phase completion.

The Durable Event-Mode Kernel may not yet be accepted as StageFlow's operational
foundation. This decision does not imply that the branch is production-ready or
event-ready after correction; those remain separate later gates.
