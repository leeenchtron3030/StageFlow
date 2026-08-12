# Media Timing Evidence v1 production slice

## Status

Completed

## Execution authority

- **Classification:** Green autonomous.
- **Authority evidence:** Operator-approved MTE-001 through MTE-005; accepted ADR-0027;
  Product Constitution principles 2, 12, 15, 19, 22, 23, and 24; ADR-0021 through
  ADR-0024; bounded-autonomy policy.
- **Implementation-ready:** Yes. Ownership, schema authority, advisory consumers,
  retention, and execution exclusions are resolved.
- **Escalation:** Only recorder qualification, automatic association/authority,
  ADR-0025 worker execution, or consequential provider/dependency selection.

## Objective

Implement the smallest durable provider-neutral Media Timing Evidence v1 model,
application/repository boundary, PostgreSQL migration, sanitized read API, and relevant
Producer drill-down while preserving Completed Media Asset and Session/package authority.

## Scope

- Immutable evidence, observation, derivation, provenance, and qualification contracts.
- Append-only asset-scoped revisions and exact/conflicting idempotent application.
- PostgreSQL persistence/reconstruction with additive forward/reversal migration.
- Provider-neutral inspection-result application seam; no production inspection runtime.
- Bounded read-only API and advisory media-detail UI.
- Focused authority-safety, restart, migration, API, and frontend tests.

Out of scope: recorder qualification acceptance, FFmpeg/provider adapter, watcher,
scheduler, broker, worker/lease implementation, transcription execution/provider,
automatic association, Session/package mutation, and MTE-driven Producer Attention.

## Acceptance criteria

- [x] Dedicated MTE revisions link to registered Completed Media Asset and manifest identity.
- [x] Raw Observed facts and Derived candidate intervals remain structurally distinct.
- [x] Exact replay returns the original revision; conflicting replay fails; reprocessing
  appends a linked revision.
- [x] PostgreSQL reconstructs complete evidence history after a new repository instance.
- [x] Projection/API expose provenance, qualification, limitations, and advisory use with
  no paths, filenames, credentials, or provider dumps.
- [x] MTE application changes no Session boundary, association, or package state.
- [x] Relevant Producer drill-down displays MTE without changing Mission Control/Attention.
- [x] Focused/broader backend checks, migration validation, frontend checks, documentation
  validation, and `git diff --check` pass or are explicitly classified.

## Data and migration

Migration `0006_media_timing_evidence` is additive and MTE-owned. Forward application
requires existing Kernel tables and creates evidence, observation, derivation, derivation
input, and application-idempotency tables plus the ledger row. Reversal drops those
objects in dependency order and deletes only the MTE ledger row. Pre-existing assets
remain valid with empty MTE history. No data backfill or media mutation occurs.

## Failure and recovery

No in-memory fallback is authoritative. Storage unavailability is typed. A transaction
commits the evidence parent, children, and idempotency result together. Exact replay is
safe after process restart; identity/digest conflicts and revision races fail visibly.
Provider inspection is not executed by this slice.

## Test strategy

- Contract invariants: aware time, normalization, lineage, qualification, sanitization.
- In-memory behavior: replay/conflict/reprocessing and authority non-mutation.
- PostgreSQL SQL/migration structure plus gated clean-database forward/reversal/restart.
- API unconfigured, empty, populated, sanitized, and unavailable behavior.
- Frontend adapter/view behavior and production build/lint/typecheck.
- Documentation UTF-8/relative links and whitespace review.

## Completion record

- **Implemented revision:** Uncommitted work based on `74f23b4`; pre-existing and
  unrelated worktree changes were preserved.
- **Files/migrations:** Added the Production MTE contracts, application/repository and
  projection boundaries, in-memory compliance double, PostgreSQL adapter, API route,
  Producer projection/panel, architecture/ADR/directive records, and focused tests.
  Additive migration `0006_media_timing_evidence` owns only MTE evidence, observation,
  derivation, derivation-input, and application-idempotency tables.
- **Commands/results:** Focused MTE tests passed (11 passed, 1 PostgreSQL test skipped
  without a DSN). MTE plus Kernel integration passed (58 passed). The full backend suite
  passed (1679 passed, 13 skipped), Ruff passed, and Pyright reported zero errors or
  warnings. The gated migration/repository test passed against a disposable PostgreSQL
  17.10 cluster, including forward, reconstruction, replay, revision, reversal, and
  reapplication. Frontend tests passed (12 of 12), with lint, typecheck, and production
  build passing. Local browser qualification passed at desktop and 768-pixel widths.
  Documentation UTF-8/relative-link validation and `git diff --check` passed.
- **Warnings:** The backend suite reports the existing Starlette `TestClient`/httpx
  deprecation warning. Initial broad-suite attempts used an unsuitable repository-local
  pytest temporary root; rerunning with an external temporary root passed. The real
  PostgreSQL fixture was corrected to satisfy the existing Stage source-binding schema.
- **Deviations:** No product or architecture deviation. No production inspection adapter,
  worker, recorder qualification, automatic association, or authority mutation was added.
- **Rollback:** Reverse migration removes only MTE-owned tables and its ledger row; the
  disposable validation cluster was stopped and removed.
- **Remaining work:** Recorder-profile qualification, automatic association/authority,
  durable worker execution under ADR-0025, and consequential provider/dependency choices
  remain explicit Yellow work.
