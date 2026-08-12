# Final independent verification — Contract Stabilization

**Review date:** 2026-08-08

**Reviewer role:** Fresh independent Codex review

**Reviewed branch:** `main` at `ee23004011eae462b3ced40b22b31221226b94d5`

**Comparison baseline:** `origin/main` and `c3b490341939656986790f305c00107fdc1799f9`

**Phase recommendation:** **ACCEPT WITH GREEN FOLLOW-UP**

This is a review artifact, not architectural authority. No production code, dependency,
schema, migration, runtime configuration, public API, or frontend source was changed by
this review.

## Executive conclusion

The current `HEAD` implementation satisfies the reliability behavior required by
CSR-001 through CSR-005. In particular, an isolated real PostgreSQL 17.10 instance on
the Windows/Razer reference node proved durable reconstruction, separate-process replay,
genuinely concurrent first registration through independent connections, conflict
preservation, versioned fingerprint fallback, transactional rollback, typed live
unavailability, and the actual schema/migration behavior.

CSR-006 is only **PARTIALLY RESOLVED**. The work is now committed in forward-only thematic
groups, but three intermediate commits are not independently buildable:

- `e0ffb55` imports `app.shared.metadata` and strict shared-time functions that are not
  present at that commit;
- `695e825` has the same forward dependencies, including in its new ingress code;
- `db75290` supplies `app.shared.metadata` but still depends on the time implementation
  added by `e6f264a`.

The final branch is clean and passes the complete matrix. The commit-topology issue is a
reviewability/governance defect, not a current runtime, architecture, or PostgreSQL
reliability defect. It does not justify rewriting unpublished history during this review.

StageFlow may formally close Contract-Boundary Stabilization with the Green follow-ups
below and may enter Durable Event-Mode Kernel architecture/design and bounded
implementation planning. This does not mean StageFlow is a composed, restart-safe event
workflow or is ready for production/event deployment.

## 1. Authority and scope reviewed

The review read and applied:

- `AGENTS.md`, `PRODUCT_CONSTITUTION.md`, `docs/PROJECT_BRIEF.md`, and
  `ENGINEERING_DIRECTIVES.md`;
- the architecture index and all current documents under `docs/architecture/`;
- the ADR index and ADR-0019 through ADR-0022 under `docs/adr/`;
- the architecture-baseline review as evidence and its disposition as decision
  authority;
- the prior Contract Stabilization independent review and correction-status report; and
- the completed/in-progress Contract Stabilization plans under `docs/plans/`.

The accepted authority is consistent: ADR-0019 requires durable replay identity;
ADR-0021 requires explicit aware time; ADR-0022 selects PostgreSQL as the authoritative
local/offline-capable operational store; and the architecture disposition protects the
modular monolith, synchronous deterministic boundaries, and explicit separation from
future Session/media/worker composition.

## 2. Commit and worktree integrity

### Verified facts

- The worktree was clean before this artifact was created.
- `main` was exactly eight commits ahead of `origin/main`.
- `origin/main`/`c3b4903` is the merge base and an ancestor of `HEAD`.
- Reflog evidence shows a fast-forward pull to `c3b4903` followed by the eight listed
  commits in order, with no reset, rebase, amend, or other local history rewrite.
- No force push or published-history rewrite is evidenced. The eight commits were still
  unpublished relative to the locally observed `origin/main` reference.
- Aggregate scope is 223 paths, 7,488 insertions, and 655 deletions relative to
  `c3b4903`.
- No frontend source, public HTTP API, deployment configuration, credential, provider,
  Session implementation, worker/broker, runtime composition, or media-blob storage was
  added.

### Commit order and thematic scope

| Commit | Observed scope | Assessment |
| --- | --- | --- |
| `2902277` | Governance, project brief, plans, prior review, accepted ADR/architecture baseline | Thematically scoped; includes the explicitly reported governance baseline |
| `ce4f79a` | GitHub Actions quality matrix and CI documentation | Scoped |
| `8419b40` | Filesystem race hardening, portability tests, local package documentation | Scoped |
| `e0ffb55` | Dispatcher/interpreter protocol, lineage, aggregation, diagnostics, tests | Thematic, but forward-dependent and not independently buildable |
| `695e825` | PostgreSQL ingress contracts, adapter, migration, dependency/lockfile, tests | Thematic, but forward-dependent and not independently buildable |
| `db75290` | Recursive metadata freezer and affected contracts/tests | Thematic, but still forward-dependent on the later time helper |
| `e6f264a` | Strict aware-time transition, shared validation, affected contracts/tests | Scoped; supplies the final missing forward dependency |
| `ee23004` | Correction-status and plan evidence | Scoped, but overstates CSR-006 as fully resolved |

Repository evidence does not identify unrelated product work in the aggregate diff.
Absolute authorship/provenance cannot be proven from Git alone, but the clean pulled
baseline, forward reflog, thematic file groups, and absence of unrelated capability are
consistent with the reported stabilization batch.

### Integrity finding FV-001

**Low — intermediate commits are not independently buildable.** This is the unexpected
cross-commit dependency described in the executive conclusion. The current final tree is
valid, but the correction-status claim that CSR-006 is fully resolved is not.

## 3. Real PostgreSQL environment

No PostgreSQL service, `psql`, Docker, Podman, or installer/runtime was initially
available on the Razer node. The review therefore used the authorized third setup route:

- official EDB advanced-user Windows binary archive for PostgreSQL 17.10;
- archive URL:
  `https://get.enterprisedb.com/postgresql/postgresql-17.10-1-windows-x64-binaries.zip`;
- downloaded archive SHA-256:
  `F9AAFCA58E7026A1EF2CAEEE711ACF761671E57904D430ADC85F468374F5A821`;
- portable binaries and cluster located only under
  `C:\Users\jmsln\AppData\Local\Temp`;
- cluster initialized as Windows user `jmsln`, locale `C`, UTF-8, trust authentication,
  and no data checksums;
- PostgreSQL role `stageflow_test` and database
  `stageflow_contract_verification`;
- loopback-only listener `127.0.0.1:55432`;
- test DSN supplied through `STAGEFLOW_TEST_POSTGRES_DSN`;
- server reported PostgreSQL 17.10, 64-bit, and server timezone
  `America/Los_Angeles`.

No service was installed, no external/cloud database was used, no real credential was
created, and no production data was accessed. After verification the server was stopped
cleanly and the downloaded archive, extracted binaries, cluster data, and log created by
this review were deleted from the checked temp paths.

## 4. Real PostgreSQL behavior results

The repository-gated command

```text
uv run pytest -p no:cacheprovider -q -rs tests/test_postgres_ingress_contracts.py
```

ran with the real DSN and passed all three tests with no PostgreSQL skip.

Additional non-repository diagnostic probes exercised the requirements more directly:

| Scenario | Real-database result |
| --- | --- |
| Initial registration | `created`; exactly one row; one ingress UUID and one Production Event UUID committed |
| Exact replay | `replayed`; same ingress/Event IDs; one row; delivery count advanced |
| Reconstructed repository object | `replayed`; same durable IDs after a fresh adapter instance and connection |
| Separate OS-process reconstruction | first Python process returned `created`; second process returned `replayed`; ingress/Event IDs were identical; delivery count became 2 |
| Concurrent unseen registration | two threads synchronized before registration; each constructed a fresh repository and connection; results were exactly one `created` and one `replayed`; one row, one ingress ID, one Event ID, delivery count 2 |
| Source-key conflict | `conflict` with `ingress_identity_conflict`; original payload and delivery count remained unchanged; no second row |
| Fingerprint fallback | offset-equivalent time, reordered mappings, later receipt, and changed correlation replayed the same `stageflow-ingress-v1` identity; changed authoritative source facts produced a distinct identity/row |
| Supplementary metadata | registration contract exposes no `metadata` parameter; supplementary metadata cannot enter identity through this boundary |
| Forced transactional error | a temporary test trigger raised during insert; the adapter surfaced the database exception; zero partial rows remained; trigger/function were removed |
| Live unavailable endpoint | connection to closed loopback port returned `storage_unavailable`, no record, and `postgresql_ingress_unavailable`; no in-memory authority appeared |

The stronger concurrent probe matters: the checked-in integration test creates the row
before starting its concurrent replays, while the review probe raced two first attempts.
The database uniqueness and transaction behavior, not a process-local map, selected the
single winner.

## 5. PostgreSQL schema and migration conclusion

Direct catalog inspection found only:

- `stageflow.schema_migration`; and
- `stageflow.production_event_ingress`.

The ingress table has:

- UUID primary ingress identity and a unique UUID Production Event identity;
- the composite unique constraint
  `(source_namespace, source_identifier, identity_kind, identity_value)`;
- B-tree indexes materialized by that unique constraint, the ingress primary key, and
  Production Event uniqueness;
- `jsonb` payload and authoritative source-fact columns;
- `timestamptz` occurrence, first-receipt, and last-receipt columns;
- positive delivery-count and identity-route shape checks; and
- no foreign keys because no second domain table exists in this bounded migration.

There are no `bytea`/large-object columns, media blobs, Session tables, media-registry
tables, runtime tables, worker/operation tables, or outbox tables.

Migration behavior was executed, not inferred:

- forward migration applied twice successfully;
- reversal removed the ingress table and only its `0001_ingress` ledger row;
- a separately created sentinel table in the shared schema survived reversal;
- the shared schema and migration ledger table survived;
- forward migration reapplied successfully after reversal.

The real database matched the unit-test assumptions for uniqueness, UUIDs, JSONB,
transactions, and timezone-aware instants.

Two non-blocking hardening opportunities remain: the redundant identity columns could
have stricter database equality/non-empty checks, and `CREATE TABLE IF NOT EXISTS` does
not detect drift in an already-present table definition. Neither affected the adapter's
verified contract or this isolated migration sequence.

## 6. Timestamp conclusion — CSR-002

CSR-002 is **RESOLVED**.

- Independent production-code search found exactly one `datetime.now` call:
  `SystemClock.now()`.
- No production `datetime.utcnow()` or `replace(tzinfo=...)` was found.
- The 91-test focused timestamp/Event/Observation/Evidence/transition set passed.
- Tests cover explicit required timestamps, naive rejection, aware non-UTC offsets,
  equal-instant comparison, DST fold distinction, fixed-clock rejection, parser
  fail-closed behavior, and sole wall-clock ownership.
- The real PostgreSQL table uses `timestamptz`. A value supplied as `18:00Z` was returned
  as `11:00-07:00` under the server session timezone and converted back to
  `18:00` at UTC, proving instant preservation. PostgreSQL stores the instant; textual
  offset rendering follows the session timezone.
- Occurrence, first receipt, and last receipt remained distinct columns/meanings.
- Naive values fail before canonical hashing or storage, and offset-equivalent instants
  produce the same canonical fingerprint.

## 7. Dispatcher conclusion — CSR-003 and CSR-004

CSR-003 and CSR-004 are **RESOLVED** for the actual dispatch boundary.

- The 101-test focused dispatcher/compatibility/legacy-interpreter set passed.
- `DispatchResult` canonicalizes explicit, per-result, and support-failure warnings.
- Warning, degraded, and experimental success cannot become clean success.
- Failure precedence is deterministic: no result/no support failure -> `no_match`;
  failures without successes -> `total_failure`; mixed -> `partial_failure`; otherwise
  warning/degraded/experimental -> `success_with_warnings`; otherwise `success`.
- Predicate exceptions become ordered `InterpreterSupportFailure` diagnostics with
  sanitized codes; later registrations continue.
- Invocation exceptions become typed failed results; later successful Observations
  survive.
- Non-survivable/unknown/future statuses cannot release aggregate Observations.
- The concrete adapter validates Event, correlation, interpreter, provenance, context,
  source reference, producer, and ordered one-to-many lineage atomically.

### Dispatcher finding FV-002

**Low — unused helper does not isolate support exceptions.** The public
`ProductionEventDispatcher.matching_interpreters()` helper still calls
`can_interpret()` in an unguarded comprehension. Repository search found no caller, and
`dispatch()` does not use it, so it does not weaken the verified runtime boundary. A
future Green correction should remove/internalize it or align it with the typed support
evaluation contract before a caller adopts it.

## 8. Metadata conclusion

Recursive metadata immutability remains sound.

- All 11 focused recursive-metadata tests passed.
- Retained caller mappings, nested lists, sets, and combinations were snapshotted to
  mapping proxies, tuples, and frozensets.
- Representative Event, Observation context, and Interpreter context boundaries were
  exercised.
- Cycles, non-string keys, naive datetimes, non-finite floats, mutable external enums,
  and unsupported active/mutable objects fail closed.
- Frozen StageFlow values are accepted only after their nested state is validated.
- The real fingerprint probe confirmed identity depends on explicitly authoritative
  canonical facts, not receipt time, correlation, mapping order, or supplementary
  metadata.

An explicit nesting-depth bound remains reasonable defense-in-depth before untrusted
metadata expands; it is not a current phase criterion.

## 9. Windows/Razer filesystem conclusion

The supported Windows suite collected 58 tests and produced **53 passed, 5 skipped**.

Exact command:

```text
uv run pytest -p no:cacheprovider -q -rs \
  tests/test_local_filesystem_discovery_adapter.py \
  tests/test_local_filesystem_discovery_bounds_and_security.py \
  tests/test_local_filesystem_discovery_contracts.py \
  tests/test_local_filesystem_discovery_deployment_and_architecture.py \
  tests/test_local_filesystem_discovery_identity.py
```

Skips were exactly:

- three symlink cases: Windows symlink creation privilege unavailable (`WinError 1314`);
- one POSIX FIFO creation case; and
- one POSIX descriptor-bound `scandir` case.

The real Windows directory-replacement tests before enumeration and during child
inspection ran and passed. Windows correctly uses the accepted pre/post object-identity
fallback rather than POSIX descriptor traversal. The documented transient
swap-and-restore and weak-filesystem-identity limitations remain; later content access
must independently revalidate authority and identity. No new limitation blocks this
Razer from the currently approved bounded discovery role.

The first sandboxed focused attempt was invalidated before tests executed because pytest
could not access its shared user-temp root. The same command was rerun with normal
repository-environment access and produced the results above.

## 10. Full validation matrix

| Command/check | Fresh result |
| --- | --- |
| `STAGEFLOW_TEST_POSTGRES_DSN=... uv run pytest -p no:cacheprovider -q -rs` | Passed: 1,583 collected; 1,578 passed; 5 Windows platform/privilege skips; real PostgreSQL test ran; one existing Starlette/httpx deprecation warning |
| `uv run ruff check .` | Passed: `All checks passed!` |
| `uv run pyright` | Passed: 0 errors, 0 warnings, 0 information messages |
| portable `node.exe --version` | `v22.23.2` |
| portable `npm.cmd --version` | `10.9.8` |
| `npm ci` | Passed: 592 packages installed from the lockfile |
| `npm run build` | Passed: Next.js 16.2.10; static `/` and `/_not-found` generated |
| `npm run lint` | Passed |
| `npm run typecheck` | Passed |
| `git diff --check` before artifact creation | Passed with no output |
| Documentation/link checks | Not run: no documentation/Markdown link checker is configured in repository scripts or CI |

The first parallel backend-matrix attempt was invalid because the Windows sandbox denied
spawning Ruff; the full backend matrix was rerun sequentially with normal
repository-environment access. The first frontend attempt selected blocked `npm.ps1` and
did not execute npm; it was discarded and rerun with explicit `npm.cmd`, producing the
results above.

### Dependency audit, reported separately

Fresh read-only `npm audit --audit-level=low` reported **12 vulnerabilities: 3 moderate
and 9 high**. The stabilization aggregate does not modify any frontend source,
`package.json`, or `package-lock.json`, so these findings were not introduced or worsened
by this batch. No `npm audit fix`, package update, or lockfile mutation was performed.

## 11. CSR disposition

| Finding | Disposition | Independent evidence |
| --- | --- | --- |
| CSR-001 | **RESOLVED** | Real PostgreSQL initial create, exact replay, reconstructed object, separate OS process, concurrent unseen registration, conflict, fingerprint, rollback, migration, and unavailable behavior all passed |
| CSR-002 | **RESOLVED** | Strict aware-time focused suite passed; production search found only `SystemClock` reading wall time; real `timestamptz` behavior preserved instants and meanings |
| CSR-003 | **RESOLVED** | Canonical warnings and deterministic aggregate precedence passed focused and full suites; no false clean success observed |
| CSR-004 | **RESOLVED** | Actual dispatch catches support-predicate exceptions into ordered typed diagnostics and continues later participants; successful output survives partial failure |
| CSR-005 | **RESOLVED** | Dispatcher plan acceptance checklist and completion evidence match current dispatch behavior |
| CSR-006 | **PARTIALLY RESOLVED** | Clean forward commit sequence exists, but `e0ffb55`, `695e825`, and `db75290` are not independently buildable because they depend on helpers introduced later |

## 12. Remaining Green findings and escalation

Bounded non-blocking follow-up:

1. Correct the CSR-006 status/completion evidence to disclose the forward dependency
   among the dispatcher, ingress, metadata, and timestamp commits. Do not rewrite history
   merely to improve aesthetics.
2. Remove/internalize `matching_interpreters()` or make its support evaluation obey the
   typed failure contract before it gains a caller.
3. Strengthen the checked-in gated PostgreSQL test to preserve the review evidence:
   race two unseen first registrations, assert one `created`/one `replayed` and one row,
   and add real conflict/fingerprint/rollback/schema checks where maintainable.
4. Consider stricter database identity-shape equality/non-empty constraints and explicit
   migration drift detection before more schemas or writers exist.

No Yellow architecture decision or Red operational action blocks phase closure. Making
the intermediate commits independently buildable would require a local history rewrite,
which is a Red action under repository policy and was neither authorized nor performed.
It is not recommended as a prerequisite because the final tree is correct, clean, and
unpublished relative to the observed remote baseline; truthful documentation is the
safer follow-up.

## 13. Phase entry decision

**Yes.** StageFlow may formally enter Durable Event-Mode Kernel architecture/design and
bounded implementation planning under the accepted ADRs and architecture disposition.
CSR-001's real reconstruction/concurrency gate is now satisfied. The remaining findings
are Green, non-blocking hardening/governance items.

This acceptance does not authorize opportunistic kernel scope, production deployment,
or event-readiness claims. The repository still lacks a composed durable event-media
workflow, Session aggregate, durable media registry, operations/workers, startup
reconciliation, backup/restore procedure, service-account/secret workflow, and operator
readiness visibility.
