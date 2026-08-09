# Durable Event-Mode Kernel correction evidence

**Correction date:** 2026-08-09

**Implementation revision:** `b6deafc` (`fix: close durable kernel review findings`)

**Scope:** Targeted correction of DKR-001 through DKR-007 from the
[independent phase review](durable-event-mode-kernel-independent-review.md)

**Disposition:** All seven findings are **RESOLVED** in the implementation candidate.
The Kernel phase remains unaccepted pending fresh targeted independent correction
verification. This artifact is implementation and validation evidence, not an acceptance
or production/event-readiness decision.

## Finding dispositions

| Finding | Status | Correction and evidence |
| --- | --- | --- |
| DKR-001 | **RESOLVED** | Interval-less assets consider both a presentation-active Session and prior ended Sessions whose package remains assembling. A lone active Session remains automatically eligible; same-Stage turnover is unresolved; trustworthy media intervals can select only the prior or current Session; contradiction remains conflict. The real `BoundedMediaCycle` filesystem path and replay are covered in `test_kernel_composition_and_status.py` and association cases in `test_durable_event_mode_kernel.py`. |
| DKR-002 | **RESOLVED** | One association transaction locks the current association and affected Sessions, detects actual old/new membership change, and reopens every completed source/target Session exactly once at a new package revision. Completion decisions and approved asset-membership snapshots remain append-only and reconstructable. The four source/target lifecycle combinations, replay, snapshot preservation, and induced-history-failure rollback pass in memory and real PostgreSQL. |
| DKR-003 | **RESOLVED** | Observed PostgreSQL loss sets a composition-local recovery-required gate. Reachability returning does not clear it; only a fresh successful bounded reconciliation does. Source/reconciliation failure remains recovering and not ready. The same live process was exercised through two real PostgreSQL stop/restart cycles without requiring process restart. |
| DKR-004 | **RESOLVED** | Deterministic associations persist `stageflow.kernel.media-association` policy identity/version and typed input references to the asset, candidate revision, source binding, considered Session revisions, and supplied contradiction inputs. Evidence IDs remain empty when no standalone evidence record exists. Human declarations retain actor/operation identity and no deterministic policy claim. PostgreSQL and API reconstruction tests pass. |
| DKR-005 | **RESOLVED** | PostgreSQL assembling and recent Session queries fetch at most 21 rows and return at most 20 with explicit truncation flags. Recent completed package state, latest approved completion identity/actor/time, and linked Program Expectation identity/title/revision/planned interval are exposed without flattening expectation into Session truth. API redaction tests confirm DSNs, raw source paths, and environment secrets remain absent. |
| DKR-006 | **RESOLVED** | Boundary correction, media assignment/reassignment, and package completion require operation identities and canonical semantic digests. Exact retry replays the durable result without duplicate history/revision; conflicting or cross-command key reuse fails. Migration `0004` adds the narrow command ledger, operation foreign keys, association/history enum/shape/actor/policy/JSON/referential checks, and completion-membership constraints. Direct invalid SQL is rejected. |
| DKR-007 | **RESOLVED** | Current-facing project brief, architecture index/context, persistence/operations guidance, lifecycle/glossary documents, ADR index, and Kernel plans now describe the implemented and corrected candidate. The historical independent review and earlier Razer qualification remain unchanged historical evidence. |

## Focused correction validation

Executed from `backend/` with
`STAGEFLOW_TEST_POSTGRES_DSN=postgresql://stageflow_test@127.0.0.1:55435/stageflow_corrections`:

```text
uv run pytest -p no:cacheprovider tests/test_durable_event_mode_kernel.py tests/test_kernel_composition_and_status.py
38 passed, 1 warning in 5.35s
```

The warning is the existing Starlette `TestClient`/httpx deprecation warning. The focused
suite includes the actual Windows local-filesystem interval-less turnover path, temporal
selection, unresolved/conflict/replay behavior, the completed source/target matrix,
approved-membership reconstruction, transaction rollback, recovery-gate unit behavior,
provenance, bounded Producer projections, command replay/conflict, and invalid direct SQL.

## Full validation matrix

| Gate | Result |
| --- | --- |
| `uv run pytest` with real PostgreSQL enabled | **PASS** — 1,617 passed, 5 skipped, 1 warning in 9.88s |
| `uv run ruff check .` | **PASS** — all checks passed |
| `uv run pyright` | **PASS** — 0 errors, 0 warnings, 0 informations |
| clean frontend `npm ci` | **PASS** — 587 packages installed from lockfile; audit findings below |
| `npm run build` | **PASS** — Next.js 16.2.10 optimized static build |
| `npm run lint` | **PASS** |
| `npm run typecheck` | **PASS** |
| `git diff --check` | **PASS** |
| configured documentation checks | None are configured in repository scripts or CI |

The five backend skips are existing capability/platform-gated tests. No frontend source,
dependency manifest, or lockfile changed. The first sandboxed Ruff/Pyright attempt could
not execute files in `.venv`; the approved rerun passed. The first `npm ci` attempt used
an absolute npm executable without its sibling `node` on `PATH` and failed during a
postinstall; the clean rerun with that local Node runtime on `PATH` passed.

### npm audit (reported separately)

Read-only `npm audit` exited 1 with 12 findings: 3 moderate and 9 high. Affected dependency
families reported by npm were `@hono/node-server`/`hono`, `brace-expansion`, `fast-uri`,
`ip-address`, `js-yaml`, `nanoid`, `next`, `postcss`, `sharp`, and `undici`. `npm ci` also
reported that `sharp` and `unrs-resolver` install scripts are not covered by npm's
`allowScripts` configuration. No audit fix, package update, dependency change, or
allow-list change was performed because those actions are outside this correction scope.

## Real PostgreSQL and migration evidence

- Official EDB PostgreSQL 17.10 Windows binaries ran as a disposable loopback cluster on
  `127.0.0.1:55435`; the downloaded archive SHA-256 was
  `F9AAFCA58E7026A1EF2CAEEE711ACF761671E57904D430ADC85F468374F5A821`.
- The full suite used the disposable `stageflow_corrections` database and exercised real
  persistence, reconstruction, idempotency, association history, completed-package
  source/target reopening, approved-membership snapshots, direct constraints, and atomic
  rollback.
- Isolated database `stageflow_correction_migration_0809` applied migrations `0001`
  through `0004`, reversed the Kernel, and retained only `0001_ingress` plus its ingress
  table while Session, human-command, and completion-asset objects were absent. Reapply
  restored ledger versions `0001` through `0004` and all expected correction objects.
- Migration reversal was limited to the explicitly disposable database. It did not touch
  production data or any configured external service.

## Affected Razer/reference-node validation

Only correction-affected behavior was rerun; the prior backup/restore and bounded
endurance/coexistence evidence was not repeated.

- DKR-001: the focused test invoked the real Windows `BoundedMediaCycle` and local
  filesystem adapter with an interval-less file during same-Stage turnover and obtained
  an unresolved durable association.
- DKR-002/DKR-004/DKR-006: real PostgreSQL tests reconstructed association policy/input
  provenance and approved membership, reopened both completed source/target Sessions,
  replayed the command without duplication, rejected invalid history, and rolled back an
  induced history collision atomically.
- DKR-003: `postgresql-recovery-correction` produced distinct reconciliation identities.
  Before fresh reconciliation: `ready=false`, `recovering=true`; after an intentionally
  failed reconciliation: `ready=false`, `recovering=true`; after source restoration and
  a fresh successful reconciliation: `ready=true`.

## Scope and remaining decision state

No new dependency, external service, schema architecture, migration strategy, public
compatibility break, trust boundary, or Session/product semantic decision was introduced.
Production code and schema changed; runtime configuration, credentials, frontend code,
dependencies, and production data did not. No Green review finding remains open and no
Yellow or Red condition was encountered.

The branch is prepared only for a short fresh targeted independent correction
verification. It does not claim Kernel phase acceptance, deployment readiness,
production readiness, or event readiness.
