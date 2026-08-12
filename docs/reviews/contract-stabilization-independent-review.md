# Independent phase review — Contract-Boundary Stabilization

**Review date:** 2026-08-07

**Reviewer role:** Independent Codex review

**Repository baseline:** `c3b490341939656986790f305c00107fdc1799f9` (`HEAD`, `origin/main`)

**Reviewed state:** the complete working tree relative to that baseline

**Recommendation:** **ARCHITECTURE ESCALATION — implementation exposed a Yellow/Red decision**

This report is an analysis artifact. It does not change architecture and no production
code, tests, dependencies, schemas, migrations, or runtime configuration were modified
during this review.

## Executive conclusion

The worktree does not contain a completed six-item stabilization phase. It contains four
implemented corrections, two correctly blocked plans, and additional uncommitted
governance/documentation work:

| Stabilization item | Plan | Actual state | Overall assessment |
| --- | --- | --- | --- |
| Dispatcher / Observation Interpreter compatibility | [`dispatcher-interpreter-compatibility.md`](../plans/dispatcher-interpreter-compatibility.md) | Implemented | **Partially satisfied** — core bridge is strong; two fail-closed/aggregate defects remain |
| Stable ingress identity | [`stable-ingress-identity.md`](../plans/stable-ingress-identity.md) | Plan only; explicitly blocked | **Not satisfied** |
| Timestamp authority and legacy timestamp invariants | [`production-timestamp-invariants.md`](../plans/production-timestamp-invariants.md) | Plan only; explicitly blocked | **Not satisfied** |
| Recursive metadata immutability | [`recursive-metadata-immutability.md`](../plans/recursive-metadata-immutability.md) | Implemented | **Satisfied** |
| Local filesystem discovery race hardening | [`local-filesystem-discovery-race-hardening.md`](../plans/local-filesystem-discovery-race-hardening.md) | Implemented | **Satisfied with documented platform limitations** |
| CI quality-matrix enforcement | [`ci-quality-matrix-enforcement.md`](../plans/ci-quality-matrix-enforcement.md) | Workflow implemented but uncommitted/unpublished | **Partially satisfied / remote execution unable to verify** |

There are no stabilization commits to identify. `HEAD` and `origin/main` are both
`c3b4903`; the reviewed state comprises 158 modified tracked files and 14 untracked files
before creation of this report. The six logical change groups exist only as a co-mingled
working-tree diff. Completion records use dates and internal review labels, not commit
identifiers.

The implemented dispatcher, metadata, filesystem, and CI designs are architecture-
contained and mostly strong. They do not introduce a database, runtime composition,
Session aggregate, worker, broker, provider, cloud dependency, schema, migration, or API
break. However, ADR-0019 stable ingress and ADR-0021 legacy time authority are explicitly
unimplemented. Both are phase requirements and both need Yellow decisions before full
correction. StageFlow therefore must not declare Contract-Boundary Stabilization accepted
or begin Durable Event-Mode Kernel implementation.

It is appropriate to begin the **architecture/design decisions** for the Durable
Event-Mode Kernel now, specifically the D-02 relational store/transaction boundary that
unblocks stable ingress and the timestamp compatibility transition. Design may proceed;
implementation of the durable kernel should wait for those decisions and the High
findings below.

## Authority and reviewed change groups

The review applied the Product Constitution, root `AGENTS.md`,
[`PROJECT_BRIEF.md`](../PROJECT_BRIEF.md), all current architecture documents, the ADR
index and ADR-0019 through ADR-0021, ADR-0011 and ADR-0015 in
`ARCHITECTURE_DECISIONS.md`, the architecture-baseline review as evidence, its
authoritative disposition, the six plans, and relevant Engineering Directives including
ED-0013 through ED-0030, ED-0043, and ED-0053.

The logical production/test change groups are:

1. **Dispatcher compatibility:** new dispatcher structural protocol, adapter, aggregate
   status, status mapping, exception/result aggregation, common Event-lineage extraction,
   public exports/READMEs, and dispatcher/all-six-interpreter tests.
2. **Stable ingress identity:** no production or test change; only a blocked plan and
   status documentation.
3. **Timestamp invariants:** no production or test change directed at legacy timestamp
   fields; only a blocked plan and status documentation. Metadata datetimes now receive
   aware-time validation as part of the separate metadata correction.
4. **Recursive metadata:** new shared recursive freezer, mechanical replacement of 124
   legacy shallow freezes across Production/shared contracts, focused tests, and directly
   affected documentation.
5. **Filesystem hardening:** directory descriptor binding where supported, fallback
   identity checkpoints, typed target-change outcomes, Windows-portable race tests, and
   package/lifecycle documentation.
6. **CI enforcement:** new `.github/workflows/ci.yml` plus repository automation/status
   documentation.

## Findings

### Critical

None.

### High

#### CSR-001 — Stable ingress identity is not implemented

- **Severity:** High
- **Files/symbols:** `recording_session_event.py::to_production_event`,
  `scheduled_activity.py::to_production_event`, `media_artifact_event.py::to_production_event`,
  `clock_event.py::to_production_event`, `transcript_segment_event.py::to_production_event`,
  `visual_detection_event.py::to_production_event`, `operator_event.py::to_production_event`,
  all six concrete Observation constructors, and
  [`stable-ingress-identity.md`](../plans/stable-ingress-identity.md)
- **Evidence:** every source conversion still calls `EntityId.new()` for its Production
  Event, every concrete interpreter still calls `EntityId.new()` for Observations, and no
  ingress record, repository, store adapter, uniqueness constraint, canonical fingerprint,
  collision policy, or reconstructed-store test exists. The plan is explicitly `Blocked`
  and its completion record says only the plan changed.
- **Failure scenario:** the same source fact is delivered twice or replayed after restart.
  It becomes unrelated Production Events and Observations, so duplicate evidence or
  downstream effects cannot be distinguished from independent facts.
- **Governing plan/ADR/invariant:** ADR-0019; ABR-003; disposition D-02 and D-04;
  architecture principle 8; segment-lifecycle invariants 7 and 10.
- **Recommended correction:** decide the initial relational store, schema/migration
  tooling, ingress transaction/uniqueness boundary, trustworthy source-ID rules,
  versioned canonical fingerprint, and collision/conflict policy; then implement one
  durable ingress record before interpretation and prove reconstructed-store and
  concurrent replay behavior.
- **Green under autonomous policy:** **No.** The complete correction is Yellow because it
  selects unresolved database/schema/migration/transaction architecture. A storage-neutral
  key value could be Green but would not satisfy this finding.

#### CSR-002 — Legacy timestamp authority remains inconsistent and unsafe for durable ingress

- **Severity:** High
- **Files/symbols:** legacy Event, Observation, Evidence, dispatcher/interpreter context,
  policy/evaluation, adapter conversion, Operational State, product, timeline, and parsing
  boundaries enumerated by [`production-timestamp-invariants.md`](../plans/production-timestamp-invariants.md)
- **Evidence:** the independent scan found 27 direct `datetime.now(UTC)` defaults/calls
  outside the shared Clock boundary, including `DispatchContext`, `InterpreterContext`,
  `ProductionEvent.received_at`, `Observation.observed_at`, evidence/finding/hypothesis
  creation, adapter `to_production_event` methods, policy evaluation, and product/timeline
  constructors. `session_boundary_evidence_builder.py` and
  `session_transition_policy.py` still attach UTC to parsed naive values. The plan is
  explicitly `Blocked`; no legacy timestamp implementation or focused transition tests
  were added.
- **Failure scenario:** an ambiguous local source time is silently labeled UTC, or aware
  and naive values reach a comparison. Ordering either becomes semantically wrong or
  raises host/path-dependent `TypeError`; replay at a later current time can allocate new
  receipt/evaluation facts.
- **Governing plan/ADR/invariant:** ADR-0021; ABR-005; disposition D-07; architecture
  principle 8; Session lifecycle invariants 4 and 5; segment lifecycle invariant 6.
- **Recommended correction:** approve the public compatibility transition, then reject
  ambiguous naive external/domain times, make domain/request time explicit, route
  infrastructure-created time through injected Clock ownership, remove silent UTC
  attachment, and add offset/DST/backward-clock/round-trip/replay tests while preserving
  distinct semantic timestamps.
- **Green under autonomous policy:** **No** for the full correction. Choosing immediate
  breakage versus staged compatibility wrappers/removal criteria is a Yellow public-
  compatibility decision. Validating already supplied values is Green but incomplete.

### Medium

#### CSR-003 — Top-level dispatch warnings can still produce false clean success

- **Severity:** Medium
- **Files/symbols:**
  `backend/app/contexts/production/dispatcher/dispatch_result.py::DispatchResult._aggregate_status`,
  `backend/app/contexts/production/dispatcher/dispatch_summary.py::DispatchSummary.from_dispatch_result`
- **Evidence:** `_aggregate_status()` checks per-interpreter warnings but never
  `DispatchResult.warnings`. A read-only probe constructed one ACTIVE result plus
  `warnings=("aggregate warning",)` and printed `success`. Conversely, direct construction
  can hold per-interpreter warnings while `DispatchSummary.warning_count` reports zero if
  the duplicate top-level tuple is empty. Existing tests cover status warnings but not
  divergence between the two public warning channels.
- **Failure scenario:** a caller reconstructs or directly creates the public result with
  an aggregate limitation only. Monitoring sees `SUCCESS`, contradicting the warning and
  the explicit no-false-clean-success invariant.
- **Governing plan/ADR/invariant:** dispatcher plan status/outcome table, aggregation
  step 6, acceptance criteria for warning/limited outcomes, ADR-0019 fail-closed boundary,
  and the review requirement that no warning/degraded/unknown/partial/failed state become
  false clean success.
- **Recommended correction:** establish one canonical warning aggregation invariant:
  derive aggregate warnings from results plus explicit dispatcher warnings, or validate
  the redundant inputs. Make status and summary consume the canonical collection and add
  direct-construction mismatch tests.
- **Green under autonomous policy:** **Yes.** This is a bounded, behavior-preserving
  fail-closed correction within the approved dispatcher plan.

#### CSR-004 — Interpreter match-predicate exceptions escape the fail-closed boundary

- **Severity:** Medium
- **Files/symbols:**
  `backend/app/contexts/production/dispatcher/production_event_dispatcher.py::matching_interpreters`
  and `::dispatch`
- **Evidence:** `matching_interpreters()` calls every `can_interpret(event)` inside a tuple
  comprehension before `dispatch()` enters its per-interpreter `try`. A read-only probe
  with a structurally valid participant whose predicate raised `RuntimeError` caused
  `dispatch()` itself to raise. Interpretation exceptions are sanitized and isolated;
  predicate exceptions are not. No focused test covers the predicate-failure path.
- **Failure scenario:** one registered interpreter has a predicate defect. It aborts the
  entire synchronous dispatch before later registrations are evaluated, so valid later
  results are lost and no typed failure is returned.
- **Governing plan/ADR/invariant:** dispatcher plan failure/recovery section and
  deterministic fan-out acceptance criteria; ADR-0019 typed interpreter-failure
  validation; Product Constitution reliability/recovery principles.
- **Recommended correction:** evaluate predicates in registration order inside an
  exception-isolating loop, retain a sanitized typed failure for a predicate exception,
  continue later participants, and define whether the failed predicate counts as invoked
  or separately failed. Add first/middle/last predicate-failure tests.
- **Green under autonomous policy:** **Yes.** The semantic requirement is already
  fail-closed continuation; the exact internal representation is a small reversible
  implementation detail.

### Low

#### CSR-005 — Completed dispatcher plan leaves every acceptance checkbox unchecked

- **Severity:** Low
- **Files/symbols:**
  [`dispatcher-interpreter-compatibility.md`](../plans/dispatcher-interpreter-compatibility.md),
  acceptance criteria and completion record
- **Evidence:** lines 377–401 retain twelve unchecked `[ ]` criteria while the status and
  completion record claim completion and independent acceptance. CSR-003 and CSR-004
  demonstrate that at least two of those criteria should not be checked yet.
- **Failure scenario:** a future reviewer or automation cannot distinguish intentionally
  pending acceptance from a stale checklist, weakening the plan's role as auditable
  implementation evidence.
- **Governing plan/ADR/invariant:** plan-process completion requirements and the root
  Green completion/self-review policy.
- **Recommended correction:** after code correction and revalidation, mark each criterion
  individually with evidence or leave it explicitly partial; do not retain an unqualified
  completion claim while criteria remain open.
- **Green under autonomous policy:** **Yes.** This is a directly affected completion-
  record correction after behavior is fixed.

#### CSR-006 — The phase has no independently reviewable commit/change-group boundaries

- **Severity:** Low
- **Files/symbols:** entire worktree; especially `AGENTS.md`, `docs/plans/TEMPLATE.md`,
  `docs/PROJECT_BRIEF.md`, the six plans, and the four implementation groups
- **Evidence:** `HEAD == origin/main == c3b4903`; all phase work is uncommitted. The
  worktree also contains a 109-line autonomous-execution governance addition and plan-
  process changes not listed in any stabilization plan's completion record. Without
  commits or a trusted pre-task snapshot, the review cannot prove whether those are phase
  scope or pre-existing user work.
- **Failure scenario:** correction, rollback, or later review must operate on one
  co-mingled 172-path state and can accidentally include governance changes or omit a
  production slice.
- **Governing plan/ADR/invariant:** disposition Phase 2 requirement for separate plans and
  independent review; architecture principle 11; root rule that changes remain small and
  independently reviewable.
- **Recommended correction:** preserve all current work, but partition the eventual
  commits by authorized logical group and explicitly attribute the governance/project-
  brief changes. Record commit IDs in plan completion records after review corrections.
- **Green under autonomous policy:** **Yes** for non-destructive commit partitioning and
  completion-record attribution when authorized by the active Git workflow. No history
  rewrite is recommended.

### Observations

#### CSR-OBS-001 — Windows uses a bounded fallback, not descriptor-bound traversal

- **Severity:** Observation
- **Files/symbols:** local filesystem adapter `_capture_directory_entries`,
  `_revalidate_directory_target`, architecture segment lifecycle, and Windows race tests
- **Evidence:** Windows lacks the POSIX `O_DIRECTORY`/`O_NOFOLLOW` plus descriptor-scandir
  path used here. The implementation captures and revalidates `(st_dev, st_ino, type)`
  after enumeration and child inspection. Actual directory replacement tests passed on
  this Windows host.
- **Failure scenario:** a target is swapped and restored entirely between fallback
  checkpoints, or the filesystem exposes weak/zero object identity. This can escape
  detection; the documentation accurately disclaims stronger safety.
- **Governing plan/ADR/invariant:** ABR-007 qualified disposition and filesystem plan.
- **Recommended correction:** none required for phase acceptance beyond retaining the
  documented limitation and independently revalidating later content opens.
- **Green under autonomous policy:** not applicable.

#### CSR-OBS-002 — Windows behavior is locally tested but not continuously enforced in CI

- **Severity:** Observation
- **Files/symbols:** `.github/workflows/ci.yml`; filesystem test suite
- **Evidence:** CI intentionally has Linux-only jobs. The current Windows focused suite
  passed 53 tests with 5 legitimate platform/privilege skips, including both actual
  replacement tests. POSIX descriptor behavior is skipped on Windows and is expected to
  run on Linux CI.
- **Failure scenario:** a later Linux-only change regresses the Windows fallback without
  a Windows hosted check.
- **Governing plan/ADR/invariant:** CI plan explicitly does not claim Windows support;
  ABR-007 requires Windows limitations to remain visible.
- **Recommended correction:** consider a separately scoped Windows backend job before
  StageFlow claims an event-node support matrix. It is not required by the current
  quality-matrix plan.
- **Green under autonomous policy:** a future bounded CI expansion could be Green, but it
  is outside this review's correction scope.

## Acceptance-criteria review

### 1. Dispatcher / Observation Interpreter compatibility

| Criterion | Classification | Evidence |
| --- | --- | --- |
| One dispatcher-facing structural protocol exists | Satisfied | `DispatcherInterpreter` contains only `id`, `can_interpret`, and `interpret`; dispatcher depends on it |
| Compatibility ownership is narrow and correctly placed | Satisfied | adapter is under dispatcher-owned `compatibility/`; no service locator or registry was added |
| `ProductionEventInterpreter` remains supported | Satisfied | public class/import remains; it structurally satisfies the protocol; focused legacy tests pass |
| Concrete batch APIs remain supported | Satisfied | concrete union/sequence signatures remain and all six contract suites pass; dispatcher invokes the one-Event form |
| Context mapping is lossless | Satisfied | all five fields are copied explicitly without defaults or wall-clock calls |
| Production Event lineage is preserved | Satisfied for the concrete adapter; Unable to verify for arbitrary structural participants | exact source Event/result/provenance/type/time checks exist for adapter output; general protocol participants are not lineage-validated |
| Correlation lineage is preserved | Satisfied | adapter validates Observation and ObservationContext correlation against the Event |
| One-to-many Observation behavior is preserved | Satisfied | ordered tuples are copied and flattened; malformed members fail atomically |
| Multiple matching interpreters remain deterministic | Satisfied | registration-order match, invoke, result, Observation, and warning tests pass |
| Exceptions fail closed | Partially satisfied | interpretation exceptions become typed failures and later matches continue; predicate exceptions escape (CSR-004) |
| Non-success statuses fail closed | Satisfied | centralized semantics suppress output and classify unknown/configured/failed/disabled/archived/future values as failures |
| No warning/degraded/unknown/partial/failed state becomes false clean success | Partially satisfied | status/per-result warning paths are correct; top-level-only warnings become `SUCCESS` (CSR-003) |
| Additive statuses preserve existing serialized/public values | Satisfied | existing enum strings are unchanged; new values are additive; no removal/deprecation found |
| No bridge-specific `Any`, unsafe cast, or type-ignore | Satisfied | adapter/protocol code contains none; scoped and full strict Pyright pass |

### 2. Stable ingress identity

| Criterion | Classification | Evidence |
| --- | --- | --- |
| Same logical source fact receives stable ingress identity | Not satisfied | no ingress identity or record exists; conversions allocate fresh IDs |
| Trustworthy source-provided IDs are used | Not satisfied | no source-ID ingress policy exists |
| Fallback fingerprint is canonical and versioned | Not satisfied | no fingerprint exists |
| Mutable supplementary metadata is excluded from identity | Unable to verify in an ingress implementation | ADR/plan require it, but there is no implementation |
| Source and Event identity remain distinct | Satisfied as architecture/absence of conflation | no attempted shortcut derives Event ID directly from source facts |
| Repeat conversion cannot look like independent evidence | Not satisfied | repeated conversion/interpretation allocates unrelated IDs |
| Collision/ambiguity is explicit and fail-safe | Not satisfied | no collision boundary exists |
| Process-local replay is not misrepresented as durable | Satisfied | plans/docs explicitly state durability is absent |
| No unauthorized database/runtime composition | Satisfied | none introduced |

### 3. Timestamp authority

| Criterion | Classification | Evidence |
| --- | --- | --- |
| External/persisted domain times require awareness | Partially satisfied | newer ED-0046–0053 contracts do; legacy boundaries still accept naive values |
| Naive handling matches accepted policy | Not satisfied | broad legacy validation is absent |
| UTC is not silently attached to ambiguous local time | Not satisfied | two parsers still use `replace(tzinfo=UTC)` |
| Runtime-generated time comes from Clock boundary | Not satisfied | 27 direct wall-clock defaults/calls remain outside Clock ownership |
| Distinct semantic times remain distinct | Partially satisfied | newer contracts preserve them; implicit legacy defaults remain |
| Serialization and ordering remain compatible | Unable to verify | no compatibility transition or round-trip suite was implemented |
| Mixed aware/naive comparisons cannot escape validation | Not satisfied | legacy inputs can escape validation into policy/comparison paths |
| Offset and boundary behavior is tested | Partially satisfied repository-wide; Not satisfied for this plan | newer suites have aware-time coverage; the blocked plan added no offset/DST/backward-clock/replay suite |

### 4. Recursive metadata immutability

| Criterion | Classification | Evidence |
| --- | --- | --- |
| Nested caller collections cannot mutate constructed values | Satisfied | mappings/lists/sets snapshot to proxy/tuple/frozenset; focused mutation tests pass |
| Approved metadata types are handled | Satisfied | finite scalars, aware datetimes, timedelta/UUID/IDs, StageFlow enums, and validated frozen StageFlow dataclasses are supported |
| Unsupported mutable/non-serializable structures fail predictably | Satisfied | typed `ValueError` covers keys, active objects, naive datetimes, non-finite numbers, external enums, mutable frozen-contract internals, and cycles |
| Authoritative facts were not moved into metadata | Satisfied | changes are freezer substitutions; first-class fields remain intact |
| Identity excludes mutable supplementary metadata | Satisfied for changed existing identities | no identity derivation was changed to consume metadata; stable ingress itself remains absent |
| Equality/replay behavior remains stable | Satisfied for implemented contracts | snapshot values are deterministic; focused and full suites pass |
| No oversized serialization framework | Satisfied | one dependency-free shared helper was introduced |

An explicit maximum nesting depth remains a reasonable non-blocking hardening item before
untrusted/durable metadata expands; it is not an accepted criterion and is not reported as
a defect here.

### 5. Local filesystem discovery race hardening

| Criterion | Classification | Evidence |
| --- | --- | --- |
| Shallow, bounded, read-only semantics remain | Satisfied | no recursion/content open/watch/write; independent entry and candidate bounds remain |
| Static symlink rejection remains | Satisfied | target/ancestor/child checks remain; privilege-dependent Windows symlink tests skip explicitly |
| Path traversal and scope protection remain | Satisfied | configuration/request security tests pass |
| Audit TOCTOU case is meaningfully mitigated | Satisfied with documented fallback limitation | descriptor binding on supported POSIX; pre/post object identity checks elsewhere |
| Windows and supported platform behavior matches claims | Satisfied with qualification | actual replacement tests pass on Windows; POSIX descriptor path is explicitly separate |
| Directory/object identity revalidation is correct | Satisfied for exposed stable identity | `(device, object, type)` comparison is performed at race-sensitive checkpoints |
| Identity change fails conservatively | Satisfied | typed BLOCKED result returns no candidates |
| Discovery grants no later content authority | Satisfied | code performs metadata inspection only; docs retain independent later-open requirement |
| Fault tests exercise real replacement | Satisfied | real rename/replacement during enumeration and child inspection, not only static symlinks |

### 6. CI quality enforcement

| Criterion | Classification | Evidence |
| --- | --- | --- |
| CI runs actual current quality commands | Satisfied structurally | workflow commands match root instructions/package scripts; backend sync adds `--locked` |
| Backend pytest, Ruff, Pyright enforced | Satisfied structurally and locally | all three are separate failing steps; local matrix passes |
| Frontend build, lint, typecheck enforced | Satisfied structurally; Unable to verify execution | all three steps exist after `npm ci`; Node/npm unavailable locally and workflow has not run remotely |
| Install steps are reproducible | Satisfied | `uv sync --dev --locked` with `uv.lock`; `npm ci` with `package-lock.json`; explicit Python 3.13/Node 22 |
| Caches cannot hide generated state | Satisfied | caches accelerate dependency retrieval; install commands still execute and no generated application state is restored |
| Failures propagate | Satisfied structurally | no `continue-on-error`; shell/action defaults fail each job step |
| CI avoids operational-readiness claims | Satisfied | workflow/docs explicitly limit the claim to development validation |
| Permissions are narrow | Satisfied | workflow-level `contents: read`; checkout credentials are not persisted |
| Action pin provenance independently verified | Unable to verify | actions use full commit SHAs, but remote tag lookup was unavailable in this review environment; no `actionlint` is installed |

## Cross-change consistency

The four implemented corrections do not create hidden runtime composition. Dispatcher
compatibility is synchronous and I/O-free; metadata freezing is a shared value-boundary
mechanism; filesystem hardening remains a stateless discovery adapter; CI is development
automation only.

The important interactions are:

- **Ingress identity versus frozen metadata:** no identity currently consumes metadata,
  so the freezer cannot destabilize identity. This is safe but does not validate the
  future ADR-0019 fingerprint rules.
- **Ingress identity versus time:** no canonical fingerprint exists, so time-normalization
  effects on hashing are not yet testable. The future design must decide exactly which
  authoritative source times participate and must version the rule.
- **Dispatcher lineage versus ingress identity:** the adapter preserves the supplied
  Production Event ID and exact Observation provenance, but it cannot make that ID stable;
  fresh IDs still enter and fresh Observation IDs still emerge.
- **Status/result semantics:** centralized status semantics substantially improve legacy
  and concrete consistency. CSR-003 is the remaining inconsistency between the duplicate
  top-level and per-result warning channels.
- **Metadata versus serialization:** tuples/proxies/frozensets and evidenced StageFlow
  values remain intentional Python contract compatibility, not a new generic serialized
  wire format. Full tests found no current regression. Future persistence/API schemas must
  still define explicit serialization rather than assuming arbitrary metadata is JSON.
- **Filesystem versus CI:** the POSIX descriptor path can run in Linux CI; Windows fallback
  behavior was validated locally but is not continuously enforced.

Conclusion: no completed change invalidates another completed change. The combined batch
is nevertheless incomplete because stable ingress and legacy time authority—the two
changes that govern future replay/hash semantics—are absent.

## Architecture containment and scope

Verified absent from production changes:

- durable database selection or implementation;
- schema or migration;
- application composition root or runtime startup wiring;
- Session aggregate/lifecycle implementation;
- worker topology, Durable Operation implementation, broker, or outbox;
- provider SDK/dependency or network call;
- cloud-required event operation;
- packaging/publishing architecture;
- public API/schema break;
- media content access, watcher, polling, or recursive discovery.

No application dependency or lockfile changed. No schema, migration, deployment, secret,
or runtime configuration changed. The broad recursive-freezer edit is mechanically wide
but directly authorized by ABR-006 and behaviorally bounded. The only material scope-
containment concern is CSR-006: unrelated/unattributed governance changes are co-mingled
with the uncommitted implementation batch.

## Positive verification

Strong choices that should be protected from unnecessary refactoring:

- The dispatcher uses one minimal structural protocol and keeps the concrete adapter at
  the consuming dispatcher boundary.
- Legacy `ProductionEventInterpreter` and concrete batch APIs remain supported without a
  broad rename or duplicate dispatcher.
- Status mapping is explicit and additive; centralized semantics suppress observations
  for fail-closed states and keep degraded/experimental output visibly non-clean.
- Concrete adapter lineage validation is atomic, sanitized, and covers Event ID/type/time,
  correlation, interpreter identity, context, provenance, producer, and one-to-many output.
- Recursive immutability is dependency-free, rejects cycles/non-finite values/external
  enums, and preserves evidence-backed immutable StageFlow contracts.
- Filesystem hardening binds POSIX inspection to a directory descriptor where available,
  retains conservative fallback checks, and uses real replacement fault tests on Windows.
- CI uses lock-aware installs, pinned action SHAs, least privilege, no persisted checkout
  credentials, and makes no deployment or operational-readiness claim.
- All current backend behavior and strict typing remain clean across 1,543 tests.

## Validation evidence

| Command/check | Result |
| --- | --- |
| Dispatcher/all-six focused pytest | **Passed:** 216 tests |
| Recursive metadata representative focused pytest | **Passed:** 160 tests |
| Filesystem focused pytest on Windows | **Passed:** 53; **skipped:** 5 expected platform/privilege cases |
| Full backend `uv run pytest` | **Passed:** 1,543; **skipped:** 5; **warning:** 1 existing Starlette/httpx deprecation |
| Full backend `uv run ruff check .` | **Passed** |
| Full backend `uv run pyright` | **Passed:** 0 errors, 0 warnings, 0 information |
| `npm run build` | **Unable to run:** `npm`/Node not installed on this host |
| `npm run lint` | **Unable to run:** `npm`/Node not installed on this host |
| `npm run typecheck` | **Unable to run:** `npm`/Node not installed on this host |
| `git diff --check` | **Passed:** no whitespace errors; LF-to-CRLF working-copy warnings only |
| Untracked-file trailing-whitespace scan | **Passed** |
| CI structural command/permission/cache review | **Passed** |
| `actionlint` | **Not run:** tool not installed |
| Remote action-SHA/tag verification | **Unable to verify:** network escalation unavailable in this environment |
| Dispatch top-level warning probe | **Confirmed defect:** returned `success` |
| Dispatcher predicate-exception probe | **Confirmed defect:** `RuntimeError` escaped |

The first filesystem-focused attempt was invalidated before test execution because
pytest could not access its shared default temp root. It was rerun with an isolated temp
base and passed. The first full-suite attempt was sandbox-blocked while importing the
existing `anyio` installation. The approved full matrix was rerun outside that read
restriction and passed. These are environmental/tooling failures, not repository defects.

The five Windows skips were: three symlink-creation cases without Windows privilege
(`WinError 1314`), one POSIX FIFO case, and one POSIX descriptor-scandir case. The two
real directory-replacement tests ran and passed.

## Corrections and decisions

### Green corrections that may proceed autonomously

1. CSR-003: canonicalize/validate dispatch warnings and add direct-construction tests.
2. CSR-004: isolate match-predicate exceptions, retain a typed failure, continue later
   registrations, and add predicate-failure tests.
3. CSR-005: reconcile the dispatcher acceptance checklist/completion record after those
   behavior corrections pass.
4. CSR-006: partition non-destructive commits and attribute the co-mingled governance
   changes, subject to the active Git workflow.

The review did not implement any of these corrections.

### Yellow/Red decisions requiring human/architecture action

1. **Yellow — D-02 durable store/transaction boundary:** select the initial relational
   database technology, schema and migration tooling, topology, backup/restore position,
   and ingress uniqueness/transaction/collision boundary required by ADR-0019.
2. **Yellow — timestamp compatibility transition:** choose staged explicit-time
   replacements plus a named deprecation/removal milestone, or authorize immediate
   breaking hardening of the exported Python constructors/methods.
3. **Red:** none identified.

## Phase recommendation

**ARCHITECTURE ESCALATION — implementation exposed a Yellow/Red decision**

There are no Critical findings. CSR-001 and CSR-002 are High phase-completion blockers;
CSR-003 and CSR-004 are bounded Medium dispatcher defects. The phase architecture remains
coherent, but the phase is not complete and cannot be accepted through Green corrections
alone.

StageFlow is **ready to begin Durable Event-Mode Kernel architecture/design** in order to
resolve D-02 and the timestamp transition. It is **not ready to begin Durable Event-Mode
Kernel implementation**, to compose real ingress, or to claim restart-safe event
operation until the two Yellow decisions are resolved, ADR-0019/ADR-0021 corrections are
implemented and independently validated, the two dispatcher Medium findings are fixed,
and the full frontend/CI execution evidence is observed.
