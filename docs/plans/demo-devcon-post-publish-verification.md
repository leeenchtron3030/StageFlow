# Demo Devcon Post-Publish Verification Correction

## Status

Completed

## Execution authority

- Classification: Green, explicitly authorized by the 2026-08-19 post-publication verification
  directive.
- Authority evidence: the accepted guarded Devcon publication boundary; the durable upstream
  commit `6e90615077f1348cf0d96ef991947d142bdb4350`; the completed Devcon request-contract
  correction; and the Demo rehearsal/controller plans.
- Implementation-ready: Yes. This corrects verification of an accepted write without changing
  publication fields, authority, credentials, or the one-PUT rule.
- Escalation boundary: any additional Devcon write, new published field, automatic PUT retry,
  schema, migration, dependency, authority change, or trust-boundary change remains out of scope.

## Evidence and root cause

The second guarded PUT returned HTTP 204 and upstream Git commit
`6e90615077f1348cf0d96ef991947d142bdb4350` durably changed exactly
`devcon-api/data/sessions/test-devcon-8/a-dacc-vision-for-decentralized-ai.json`. The upstream
Session GET is wrapped in `publicCache(60)`, whose cache policy includes
`stale-while-revalidate=120`. The controller incorrectly treated its immediate cached GET as both
write and durability authority.

## In scope

- Represent write acceptance, Git-backed durability, and public-API convergence separately.
- Verify the exact upstream event/session JSON file with a cache-bypassing, credential-free GET.
- Poll the public API with bounded GET-only attempts across the documented cache window.
- Preserve fail-closed PUT rejection, identity mismatch, and durable-file mismatch behavior.
- Update focused tests, the guarded controller output/runbook, and factual rehearsal evidence.

## Out of scope

- Any live or test Devcon PUT, PUT retry, compensation, new field, dependency, schema, migration,
  runtime configuration, frontend behavior, package authority, or controller redesign.

## Acceptance criteria

- [x] HTTP 204 is recorded as write accepted and never retried because a GET is stale.
- [x] Exact Git-backed event/session content must match expected transcript and duration.
- [x] Matching durable state plus stale public GET returns `published_durable_api_stale`.
- [x] Later bounded public-API convergence returns fully verified status.
- [x] PUT rejection runs no durability or convergence verification.
- [x] Results and diagnostics contain no credential or transcript content.
- [x] The 2026-08-19 rehearsal record identifies the live write as durably successful.

## Rollback

Revert the verifier, focused tests, controller rendering/runbook, and this evidence correction. Do
not issue another Devcon write and do not alter the already-persisted upstream file.

## Completion record

- Implemented revision: working tree on `codex/devcon-post-publish-verification`. The controller
  records write acceptance, exact Git-backed durability, and public-API convergence separately;
  its public checks are capped at four GETs and 195 seconds, and no read result can invoke a PUT.
- Validation: focused publication/controller suite: 33 passed; full backend suite: 1,777 passed,
  5 skipped; Ruff: passed; Pyright: 0 errors and 0 warnings; PowerShell AST parsing and
  `git diff --check`: passed. Privacy review found no credential values or transcript content in
  results, scripts, reports, or documentation.
- Live result: no live Devcon request was executed during this milestone. Preserved evidence shows
  the 2026-08-19 guarded PUT was accepted with HTTP 204 and persisted by upstream commit
  `6e90615077f1348cf0d96ef991947d142bdb4350`; the immediate public GET mismatch was cached
  convergence lag, not publication failure.
- Warnings and remaining work: the backend suite retains one existing Starlette/httpx deprecation
  warning. Public convergence may remain stale after bounded GET polling without changing the
  durable success result. Any later external write still requires a separate guarded human action.
