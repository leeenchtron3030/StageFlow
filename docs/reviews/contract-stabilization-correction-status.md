# Contract Stabilization correction status

**Status date:** 2026-08-08

**Prepared by:** implementing Codex self-review

**Branch:** `main`

**Implementation baseline:** `e6f264a` after the seven logical stabilization commits

**Purpose:** implementation evidence for a short fresh independent verification

This status report does not accept the Contract Stabilization phase. It reviews the six
CSR findings against the corrected implementation and records the evidence and remaining
validation gap.

## Finding status

| Finding | Status | Evidence and remaining work |
| --- | --- | --- |
| CSR-001 - Stable ingress identity is not implemented | **PARTIALLY RESOLVED** | The repository now contains stable source identity, source-key and versioned canonical-fingerprint routes, one durable ingress/Production Event identity, typed create/replay/conflict/unavailable outcomes, PostgreSQL uniqueness and transaction behavior, explicit migrations, a non-authoritative in-memory test double, and create-only dispatcher handoff. Repository-neutral replay, conflict, concurrency, canonicalization, backward-clock, and no-repeat-dispatch tests pass. The real PostgreSQL reconstruction/concurrency test is present but skipped because this Windows node has no configured `STAGEFLOW_TEST_POSTGRES_DSN`, PostgreSQL server, `psql`, Docker, or Podman. The two environment-backed acceptance criteria remain unchecked. |
| CSR-002 - Legacy timestamp authority remains inconsistent | **RESOLVED** | Shared aware-only validation/parsing/UTC normalization is in place; all 27 inventoried Production/shared implicit wall-clock reads were removed; `SystemClock` is the only production `datetime.now` reader; affected authoritative boundaries reject naive values; occurrence, receipt, evaluation, acceptance, commit, and other timestamp meanings remain separate. Offset, DST-fold, naive-rejection, canonicalization, parser, and replay tests pass. |
| CSR-003 - Top-level dispatch warnings can produce false clean success | **RESOLVED** | `DispatchResult` canonicalizes top-level and interpreter warnings, and aggregate precedence treats any surviving warning/degraded/experimental condition as `SUCCESS_WITH_WARNINGS` unless failure precedence produces partial or total failure. Successful Observations remain available when another interpreter warns or fails according to the approved status rules. Focused behavior tests pass. |
| CSR-004 - `can_interpret` exceptions escape and abort dispatch | **RESOLVED** | The dispatcher catches exceptions only at the support-predicate boundary, records an ordered typed `InterpreterSupportFailure` with sanitized diagnostics, does not count the event as a normal decline, and continues evaluating later registrations. Focused behavior tests pass. |
| CSR-005 - Dispatcher plan retains unchecked acceptance criteria | **RESOLVED** | The dispatcher plan checklist and completion record are reconciled with implementation and test evidence. The distinct ingress plan correctly retains two unchecked real-PostgreSQL criteria rather than overstating completion. |
| CSR-006 - Stabilization work lacks clean reviewable commit boundaries | **RESOLVED** | The previously mixed worktree is preserved and committed as seven forward-only logical groups listed below. No published history was rewritten. |

## Architecture and persistence outcome

- ADR-0021 records the approved breaking transition to strict timezone-aware internal
  timestamps.
- ADR-0022 records PostgreSQL as the authoritative local/offline-capable operational
  store. Media blobs remain outside PostgreSQL and are referenced by durable records.
- `docs/architecture/persistence.md`, the architecture index, principles, system
  context, project brief, plan index, and affected plans reflect those decisions.
- The bounded schema contains only a migration ledger and
  `stageflow.production_event_ingress`. It uses UUID identities, `jsonb` payload/source
  facts, `timestamptz` values, and a uniqueness constraint over stable source identity
  plus identity route/value.
- Registration is one synchronous Psycopg transaction using insert-on-conflict,
  lock/read, exact canonical-fact comparison, and replay-only receipt/count mutation.
  PostgreSQL unavailability returns a typed unavailable outcome; it never falls back to
  process memory for authoritative state.
- This work does not claim exactly-once delivery and does not add a broker,
  microservice, watcher, Session association, worker, runtime composition, or media-blob
  storage.

## Dependency and migration record

The only new application dependency is Psycopg 3 with its Windows binary distribution:
`psycopg[binary]>=3.2,<4`, locked at 3.3.4. It was selected over SQLAlchemy and asyncpg
because this boundary needs a mature PostgreSQL-native synchronous driver while retaining
explicit SQL and transaction ownership. Installed package metadata declares
`LGPL-3.0-only`. Explicit `0001_ingress` forward and reversal SQL files were added; no
general migration framework was introduced.

## Validation evidence

Final validation on the Windows/Razer reference development node used Python 3.13, the
repository `uv` environment, and portable official Node.js 22.23.2 with npm 10.9.8.

| Command | Result |
| --- | --- |
| `uv run pytest -p no:cacheprovider -q -rs` | Passed: 1,578 tests; 6 skipped. Skips were three unavailable Windows symlink-privilege cases, one non-portable FIFO case, one POSIX descriptor-bound `scandir` case, and the real PostgreSQL test requiring `STAGEFLOW_TEST_POSTGRES_DSN`. One existing Starlette/httpx deprecation warning remained. |
| `uv run ruff check .` | Passed: `All checks passed!` |
| `uv run pyright` | Passed: 0 errors, 0 warnings, 0 information messages. |
| `npm ci` | Passed: 592 packages installed. npm reported 12 dependency-audit findings (3 moderate, 9 high); no unscoped dependency mutation or `npm audit fix` was performed. |
| `npm run build` | Passed with Next.js 16.2.10; static `/` and `/_not-found` routes generated. |
| `npm run lint` | Passed. |
| `npm run typecheck` | Passed. |
| Documentation/link checks | No documentation or Markdown link checker is configured in repository scripts or CI, so no such command was claimed. |
| `git diff --check` | Passed with no whitespace errors; Git emitted only LF-to-CRLF working-copy notices. |

The first final backend attempt inside the restricted sandbox could not read/execute
files in `.venv` and failed during collection/tool startup. The same command was rerun
with repository-environment access and passed as recorded above; this was an environment
permission failure, not a test failure.

## Logical commits

| Commit | Change group |
| --- | --- |
| `2902277` | Documentation and governance baseline, plans, independent-review evidence, and approved ADR/architecture updates |
| `ce4f79a` | CI quality-matrix workflow and CI documentation |
| `8419b40` | Local-filesystem discovery race and Windows portability hardening |
| `e0ffb55` | Dispatcher/Observation Interpreter compatibility, aggregation, lineage, and predicate-failure corrections |
| `695e825` | Durable PostgreSQL ingress identity, migration, repository, dependency, and focused tests |
| `db75290` | Recursive metadata immutability and focused tests |
| `e6f264a` | Strict timezone-aware timestamp transition and affected behavioral tests |

Metadata and timestamp changes overlapped in several immutable contracts. Metadata-only
files were committed separately; mixed time-bearing files were retained in the timestamp
group rather than rewriting or interactively splitting user work.

## Scope and readiness

Production backend code, one dependency and lockfile, and one bounded forward/reversal
database migration changed. Documentation and CI configuration changed. Frontend source
and dependencies, public HTTP APIs, deployment configuration, credentials, production
data, and source-media handling did not change.

No remaining Yellow or Red architecture decision was discovered within this authorized
scope. The outstanding real-PostgreSQL execution is a verification-environment gap, not
a request for a new architecture decision. The branch is ready for fresh Contract
Stabilization verification, with final phase acceptance contingent on that independent
review and, for full CSR-001 closure, execution of the configured real-PostgreSQL test.
