# Targeted independent correction verification — Durable Event-Mode Kernel

**Verification date:** 2026-08-09

**Reviewer role:** Fresh independent Codex reviewer

**Reviewed baseline:** `708f446` (`main`), including correction commits `a587ff2`,
`b6deafc`, and `708f446`

**Review mode:** Targeted correction verification. No production code, test, schema,
migration, configuration, dependency, or existing documentation was changed. This is
the only created artifact.

**Final recommendation:** **ACCEPT WITH GREEN FOLLOW-UP**

This artifact is review evidence, not architecture authority. It accepts the Durable
Event-Mode Kernel as StageFlow's completed operational-foundation phase with bounded
non-blocking Green corrections. It does **not** establish production readiness, event
readiness, deployment approval, or reference-node certification.

## Executive conclusion

The three original High findings are independently resolved:

- real interval-less same-Stage turnover media remains registered and unresolved;
- runtime reassignment atomically reopens every materially changed completed source or
  target package while retaining the approved membership snapshot; and
- a live process cannot reuse pre-outage reconciliation after observed PostgreSQL loss.

No new Critical or High defect was found. The Kernel remains architecture-contained and
the full real-PostgreSQL backend and frontend quality matrix passes.

Four bounded findings remain:

1. migration `0004` does not backfill an approved membership snapshot for a pre-`0004`
   completion that is already reopened;
2. PostgreSQL boundary/completion command replay suppresses duplicate effects but returns
   the current Session after later changes rather than the original durable result;
3. the status API reports `configured=false` when supplied configuration failed during
   startup; and
4. current-facing architecture principles and one Project Brief section still describe
   implemented Kernel behavior as absent or open.

These are Medium/Low, Green, and non-blocking. DKR-001 through DKR-004 are verified
resolved; DKR-005 through DKR-007 are partially resolved for the bounded reasons below.

## Scope and authority

The verification reviewed the Product Constitution, Engineering Directives,
`docs/PROJECT_BRIEF.md`, the architecture index, Durable Kernel design, operations,
persistence, Session/media lifecycle, glossary, system-context, and architecture
principles; ADR-0022 through ADR-0024; both Kernel plans; the original independent
review; correction evidence; and the Razer qualification report.

The aggregate correction range changes the expected Kernel contracts/service,
PostgreSQL repository, composition recovery gate, status API, migration runner, new
`0004` forward/reverse SQL, targeted tests/qualification harness, and current-facing
documentation. No dependency manifest, lockfile, frontend source, deployment
configuration, credential, production data, or unrelated domain was changed. The work
remains bounded to DKR-001 through DKR-007.

## Correction dispositions

| Finding | Disposition | Independent conclusion |
| --- | --- | --- |
| DKR-001 | **VERIFIED RESOLVED** | Lone-active interval-less association remains useful; turnover ambiguity, temporal selection, contradiction, preservation, and replay follow ADR-0024. |
| DKR-002 | **VERIFIED RESOLVED** | New runtime reassignment handles all incomplete/completed source-target combinations atomically and idempotently. DKV-001 is a distinct legacy migration-backfill gap. |
| DKR-003 | **VERIFIED RESOLVED** | Observed PostgreSQL loss gates the live composition until a distinct fresh reconciliation succeeds; failed reconciliation remains not ready. |
| DKR-004 | **VERIFIED RESOLVED** | New deterministic decisions preserve policy/version and truthful durable input references; human authority remains distinct and no evidence IDs are invented. |
| DKR-005 | **PARTIALLY RESOLVED** | Session projections are bounded and operationally useful, with completion and Program Expectation context and redaction. DKV-003 leaves one startup truthfulness defect. |
| DKR-006 | **PARTIALLY RESOLVED** | Duplicate effects/history are prevented and conflicts are typed, but DKV-002 violates original-result replay parity after later state changes. |
| DKR-007 | **PARTIALLY RESOLVED** | Most targeted documents are corrected, but DKV-004 identifies stale current-facing Project Brief and architecture-principles statements. |

## DKR-001 — Session-turnover association safety

### Verified behavior

- One active Session, no plausible prior assembling Session, and interval-less media:
  deterministic association remains allowed.
- Previous ended/assembling Session plus next active Session on the same Stage and no
  interval: unresolved with `multiple_eligible_sessions`.
- An interval overlapping only the previous Session selects the previous Session.
- An interval compatible only with the current Session selects the current Session.
- An interval overlapping both remains unresolved.
- Contradictory Session evidence produces conflict while preserving the asset.
- Exact asset processing replay preserves asset and association identity and does not
  append another association revision.

The focused suite exercised the real Windows local-filesystem `BoundedMediaCycle` with
an interval-less synthetic file. A separate executable contradiction/replay probe
returned `conflict`, retained the registered asset, and replayed the same association.

### Invariant conclusion

**Ambiguity reduces automation, never preservation.** Satisfied.

## DKR-002 — Package integrity under reassignment

### Verified runtime matrix

| Source | Target | Result |
| --- | --- | --- |
| Incomplete | Incomplete | Membership changes without inappropriate package-revision or completion changes. |
| Complete | Incomplete | Source approval/snapshot remains; source advances once and requires correction. |
| Incomplete | Complete | Target approval remains; target advances once and requires correction. |
| Complete | Complete | Both approvals remain; both advance exactly once and require correction. |

Exact operation replay does not add another association history row or package revision.
Approved historical membership remains queryable for new post-`0004` completions. A
forced association-history uniqueness failure rolled back source, target, current
association, history, and command reservation together on real PostgreSQL.

### Invariant conclusion

**A completed Session approves a specific package revision; material membership change
invalidates only the current revision and preserves historical approval.** Satisfied for
runtime operations. See DKV-001 for the pre-`0004` upgrade backfill.

## DKR-003 — PostgreSQL outage recovery readiness

A fresh disposable PostgreSQL 17.10 database was exercised in one live Python process:

1. startup reconciliation R1 completed and status was ready;
2. PostgreSQL was stopped and `KernelStorageUnavailableError` was observed;
3. PostgreSQL returned, but status remained `ready=false`, `recovering=true`, retaining
   R1 only as pre-outage history;
4. fresh recovery reconciliation R2 completed with a distinct durable identity; and
5. readiness returned only after R2.

The successful split probe exited with all assertions passing. Durable rows show R1
`463331c1-8927-48cc-a763-69aef43bd3a8` and R2
`6c80f301-dc10-465a-aaa7-14589ac5ec8e`. A separate real-PostgreSQL recovery attempt
against an absent configured source persisted failed run
`5292bdcf-193d-4812-a087-eeaddb81a7b3` and returned `ready=false`,
`recovering=true`.

An earlier combined two-cycle probe was deliberately not counted after it was terminated
during its second server shutdown; the database log showed its first clean stop/return,
and the shorter replacement probes completed successfully.

### Invariant conclusion

**Dependency availability returning is not authoritative operational recovery.**
Satisfied without process restart or an in-memory authority fallback.

## DKR-004 — Association provenance

New deterministic association history preserves:

- policy `stageflow.kernel.media-association`, version `1.1.0`;
- registered asset identity;
- candidate identity and revision;
- Stage source-binding key;
- considered Session identities and revisions;
- explicit contradictory-Session inputs when supplied; and
- the immutable media interval through the referenced registered asset.

Fresh PostgreSQL repository reconstruction returns the same deterministic association
and input references. Evidence IDs remain empty when no standalone evidence record
exists. Human assignments carry actor and operation identity, omit deterministic policy
claims, and remain `Declared` rather than appearing machine-derived.

Migration backfill uses policy version `1.0.0` and only references that can be supported
truthfully by the old schema; it does not fabricate evidence or historical revisions.
No universal Fact/event architecture was introduced.

### Invariant conclusion

Consequential new automatic association decisions remain explainable after restart.
Satisfied.

## DKR-005 — Producer operational projection

PostgreSQL fetches at most 21 assembling and 21 recent Session rows per Stage, returns at
most 20, exposes `session_limit=20`, and reports truncation when a 21st row exists. A
22-Session test verified both bounds and truncation flags.

The projection exposes active/current, assembling/correction-required, and recent
completed Sessions; package state/revision; latest approved completion decision,
actor, and time; Program Expectation identity, title, revision, and planned interval;
media counts and recent identities; unresolved/conflict state; dependency/reconciliation
state; and association provenance. `program_expectation_*` and `planned_*` fields keep
external planned context visibly separate from the realized Session.

The API exposes source-binding keys but no PostgreSQL DSN, resolved environment secret,
or raw source path. Existing configuration and API tests verified redaction.

DKV-003 prevents a fully resolved disposition: when configuration is supplied but
startup fails before `KernelComponents` is retained, the response says
`configured=false` even while reporting `kernel_startup_failed`.

## DKR-006 — Human-command idempotency and history integrity

Boundary correction, media assignment/reassignment, package completion, and Session
start share the narrow human-command operation namespace. Verified behavior includes:

- immediate exact replay produces no duplicate history, package revision, or membership
  mutation;
- materially different reuse fails with `human_command_operation_id_conflict`;
- boundary-operation reuse for media assignment fails as a cross-command conflict; and
- a genuinely different operation ID can perform a later valid action.

Canonical digests sort keys, normalize datetimes to UTC, use stable Entity ID values,
and exclude generated result IDs and request receipt time.

Real PostgreSQL rejected representative invalid direct history writes with:

- `media_association_history_actor_operation_ck`;
- `media_association_history_session_fk`; and
- `session_boundary_history_operation_fk`.

The full integration suite also rejects invalid status and missing deterministic policy,
and verifies current/history/command atomic rollback.

DKV-002 prevents full resolution: delayed replay after a later valid state change does
not return the original PostgreSQL boundary/completion result, although it correctly
performs no new authoritative mutation.

## DKR-007 — Documentation truth

The correction accurately updates most current-facing Kernel material: the Project
Brief's main implementation/current-phase sections, architecture index and system
context, Durable Kernel design/operations/persistence, Session/media lifecycles,
glossary, ADR index, plans, and review index. Historical reviews remain historical and
were not rewritten.

DKV-004 prevents full resolution. The Project Brief configuration section still calls
the implemented TOML format, secret resolution, and Runtime-composing loader open, while
`docs/architecture/principles.md` still says the Session aggregate, Runtime composition,
reconciliation, durable records, and Producer status beyond liveness are unimplemented.

## New findings

### DKV-001 — Legacy reopened completions receive no `0004` membership snapshot

- **Severity:** Medium
- **File/symbol:**
  `backend/app/infrastructure/postgres/sql/0004_kernel_review_corrections_forward.sql:268`
- **Evidence:** A fresh database applied `0001` through `0003`, then received a valid
  approved package revision 1 followed by late media and current
  `correction_required` package revision 2. Applying `0004` backfilled policy and command
  records but produced zero `session_completion_asset` rows. The SQL joins only Sessions
  whose current state is still `complete` at the completion revision (lines 275-278).
- **Failure scenario:** An operator upgrades a pre-`0004` Kernel database after a valid
  completion has already been reopened. The additive migration creates the snapshot
  table but omits that historical approval's asset set. Association timestamps may
  sometimes permit inference, but equal injected/source times and absence of a package
  revision on association history make that reconstruction non-authoritative in the
  general case.
- **Violated invariant:** Approved historical package membership must remain
  reconstructable across additive migration.
- **Recommended correction:** Add a tested, truthful legacy backfill derived from the
  latest association revision per asset at each completion boundary, with an explicit
  ambiguity policy that fails or records a migration limitation rather than inventing
  membership. Preserve existing `0004` forward compatibility through a follow-on
  migration if `0004` has already been applied.
- **Execution classification:** Green if implemented additively without changing package
  semantics; escalate if an ambiguity policy requires a new product decision.

### DKV-002 — Delayed PostgreSQL replay returns current state, not original result

- **Severity:** Medium
- **File/symbol:**
  `backend/app/infrastructure/postgres/event_mode_kernel_repository.py:905` and
  `backend/app/infrastructure/postgres/event_mode_kernel_repository.py:1570`
- **Evidence:** After boundary operation A returned Session revision 2, a later valid
  boundary operation produced revision 3. Exact replay of A returned revision 3 and was
  unequal to A's original result. After completion returned `complete`, package revision
  1, a later correction reopened revision 2; exact completion replay returned
  `correction_required`, revision 2. The in-memory repository returns the original
  stored result in both cases.
- **Failure scenario:** A delayed UI/network retry receives a materially different result
  for the same operation depending on repository adapter and intervening commands. No
  duplicate authority is created, but callers cannot rely on the documented
  existing-result replay contract.
- **Violated invariant:** Same operation ID plus the same semantic command returns the
  same durable result while producing no duplicate authority.
- **Recommended correction:** Reconstruct and return the historical operation result (or
  change the application result contract explicitly and make repository adapters
  identical). Add delayed-replay tests after intervening boundary, membership, and
  package changes.
- **Execution classification:** Green.

### DKV-003 — Supplied configuration can be reported as unconfigured after startup failure

- **Severity:** Low
- **File/symbol:** `backend/app/api/v1/kernel_status.py:315`
- **Evidence:** When `components is None`, the response hardcodes `configured=False` even
  if `kernel_startup_error` is present. The lifespan sets that error when configuration
  loading/schema/PostgreSQL startup fails.
- **Failure scenario:** An operator supplies valid Event configuration but PostgreSQL is
  unavailable or schema-incompatible at startup; status reports both
  `kernel_startup_failed` and `configured=false`, obscuring configuration versus
  dependency failure.
- **Violated invariant:** Producer status must distinguish configured state, dependency
  availability, and recovery truthfully.
- **Recommended correction:** Retain a non-sensitive configured/startup-attempt marker or
  validated redacted summary independently of composed components, and test the supplied
  configuration plus database/schema failure branches.
- **Execution classification:** Green.

### DKV-004 — Current-facing documentation still contains pre-Kernel state claims

- **Severity:** Low
- **Files:** `docs/PROJECT_BRIEF.md:310` and
  `docs/architecture/principles.md:62`, `:94`, and `:158`
- **Evidence:** These sections respectively call format/secret/Runtime configuration
  open, say no Session aggregate exists, say Runtime/durable records/reconciliation do
  not exist, and say operator status is only liveness. All are contradicted by the
  accepted current implementation and other corrected current-facing documents.
- **Failure scenario:** A contributor follows the architecture index and treats an
  implemented boundary as absent or open, duplicating design work or selecting incorrect
  scope.
- **Violated invariant:** Current implementation, accepted future direction, and
  historical baseline must remain distinguishable.
- **Recommended correction:** Update only the current-alignment/configuration statements;
  retain historical baseline maps and reviews unchanged.
- **Execution classification:** Green.

## Regression verification

The correction did not regress already accepted behavior:

- **Media pipeline:** discovery remains distinct from readiness and registration;
  candidate state remains monotonic; source replacement/security tests pass; candidate
  failures remain isolated; duplicate ingress/asset processing remains idempotent.
- **Session authority:** Program Expectation remains external/planned context; human
  start/end is authoritative; Sessions remain fixed to one Stage; genuinely unambiguous
  active and trailing media still associates.
- **Completion:** presentation end does not complete a package; authorized human
  completion remains explicit; new relevant media reopens the current revision while
  preserving prior approval.
- **PostgreSQL:** it remains the only composed authority; storage loss raises typed
  failure and no in-memory authority fallback appears.
- **Architecture containment:** no generic Job framework, worker/lease, outbox, broker,
  microservice, cloud requirement, AI execution, transcription, Editorial, rendering,
  publishing, delivery, recorder control, or provider dependency was introduced.

## Migration 0004 conclusion

Clean isolated migration verification passed:

- apply produced ledger versions `0001` through `0004` and the correction-owned tables,
  columns, foreign keys, and checks;
- reversal through the supported Kernel runner retained only `0001_ingress`,
  `production_event_ingress`, and the schema ledger;
- reapply restored `0001` through `0004` and both correction tables; and
- representative invalid history shapes and operation/session references were rejected.

`0004` is narrow rather than a generic event store. Its reversal explicitly discards
correction-owned operation/provenance/snapshot columns and is therefore appropriate only
for the documented isolated/operator-approved rollback boundary. DKV-001 is the sole
new migration correctness finding.

## PostgreSQL validation

- **Server:** official PostgreSQL 17.10 Windows x64 binaries, fresh disposable cluster,
  loopback `127.0.0.1:55436`, trust authentication, synthetic data only.
- **Databases:** separate full-suite, migration, outage, and pre-`0004` upgrade-probe
  databases.
- **Real suite:** all DSN-gated ingress/Kernel tests ran in the full suite.
- **Reconstruction:** fresh repositories reconstructed Session, asset, deterministic
  provenance, approved membership, operation ledger, and association state.
- **Outage:** same-process loss/return remained gated until a distinct reconciliation;
  real failed reconciliation remained not ready.
- **Constraints/atomicity:** invalid direct writes failed and induced history collision
  rolled back current state, affected Sessions, history, and command identity.

## Windows/Razer targeted validation

The focused suite ran on Windows and exercised the actual local-filesystem discovery and
bounded media cycle for interval-less turnover. Real PostgreSQL stop/return and
fresh-repository reconstruction covered the affected recovery/persistence behavior.

The prior unaffected backup/restore, short endurance, coexistence proxy, and power
observations were reviewed but not rerun for ceremony. No machine power policy was
changed. The prior evidence remains bounded and does not establish event readiness.

## Full validation matrix

| Gate | Independent result |
| --- | --- |
| Broader focused correction/filesystem/ingress suite with real PostgreSQL | **PASS** — 102 passed, 5 skipped, 1 warning in 9.90s |
| Full backend pytest with real PostgreSQL | **PASS** — 1,617 passed, 5 skipped, 1 warning in 21.96s |
| Ruff | **PASS** — all checks passed |
| Pyright | **PASS** — 0 errors, 0 warnings, 0 informations |
| Clean frontend `npm ci` | **PASS** — 592 packages installed from lockfile in 93.1s |
| Frontend build | **PASS** — Next.js 16.2.10 optimized static build |
| Frontend lint | **PASS** on rerun — initial 120.3s execution timed out without a result; rerun passed in 34.7s |
| Frontend typecheck | **PASS** — `tsc --noEmit` |
| `git diff --check` before artifact | **PASS** |
| Configured documentation checker | None is configured in repository scripts or CI |

The five skips are three unavailable Windows symlink-privilege cases (error 1314), one
non-portable FIFO case, and one POSIX descriptor-bound `scandir` path. They are not
counted as passes. The warning is the existing Starlette `TestClient`/httpx deprecation.

Initial sandboxed backend static/test attempts could not load `.venv` binaries; approved
reruns produced the reported results. One mistakenly named focused test path collected no
tests and was replaced with the correct broader selection. The first sandboxed npm audit
could not reach the registry; the approved read-only rerun completed.

### npm audit

Read-only `npm audit --json` reported 12 vulnerabilities: 3 moderate, 9 high, 0 low,
and 0 critical. Reported families were `@hono/node-server`,
`@modelcontextprotocol/sdk`, `brace-expansion`, `fast-uri`, `hono`, `ip-address`,
`js-yaml`, `nanoid`, `next`, `postcss`, `sharp`, and `undici`. No audit fix, package
update, manifest change, or lockfile change was performed.

## Architecture containment and decision state

Architecture containment is satisfied. The correction remains a direct synchronous
modular-monolith workflow with normalized PostgreSQL current state plus typed history.
There is no generic event sourcing, generic command/Job framework, asynchronous worker
system, or new infrastructure service.

No Yellow or Red decision is required by the verified runtime correction. DKV-001
remains Green only while a truthful additive backfill can be implemented without choosing
a new ambiguity/product policy; otherwise that narrow question must be escalated.

## Remaining Green corrections

1. Add a safe follow-on backfill for pre-`0004` reopened completion membership.
2. Make delayed PostgreSQL boundary/completion replay return the same durable result as
   the in-memory adapter and original operation.
3. Report supplied-but-failed startup configuration truthfully.
4. Correct the remaining current-facing Project Brief and architecture-principles text.

## Final Kernel recommendation

## ACCEPT WITH GREEN FOLLOW-UP

All original High findings are resolved, no new Critical/High defect exists, regression
and architecture-containment checks pass, and the remaining findings are bounded,
reversible Green corrections. The Durable Event-Mode Kernel may now be formally accepted
as StageFlow's completed operational foundation with those follow-ups tracked.

This is not production readiness or event readiness.
