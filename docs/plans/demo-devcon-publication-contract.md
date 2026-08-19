# Demo Devcon Publication Contract Correction

## Status

Completed

## Execution authority

- Classification: Green, explicitly authorized by the 2026-08-19 Devcon publication contract
  directive.
- Authority evidence: the accepted guarded `publish-devcon` workflow, the existing approved
  package publication boundary, and current upstream `efdevcon/monorepo` source at commit
  `e797785f5af3a2c01b7b6b4ea96188561673b208`.
- Implementation-ready: Yes. The failure is a compatibility defect in the existing adapter, not a
  new authority, persistence, or lifecycle decision.
- Escalation boundary: any new published fields, automatic retry, live retry, new credential
  mechanism, broader Devcon write scope, or changed package authority remains out of scope.

## Evidence and root cause

StageFlow already serializes the two approved fields as UTF-8 JSON and explicitly sends
`Content-Type: application/json`, so the missing-content-type hypothesis is rejected. The adapter
instead sends `PUT /sessions/{id}?apiKey=...`. Current upstream source routes patch-style source
updates through `PUT /sessions/sources/{id}` and accepts `x-api-key`. Because StageFlow reached the
general Session update handler, its otherwise valid patch body lacked the full Session `id` or
`sourceId` expected there and was rejected with HTTP 400 `Invalid Id`. StageFlow discarded that
bounded error envelope and exposed only the status code.

## In scope

- Correct the write URL to `/sessions/sources/{external_session_id}`.
- Send the credential only as `x-api-key` and keep UTF-8 JSON with an explicit JSON content type.
- Consume only a small bounded non-success body and map recognized Devcon error envelopes to
  sanitized reason codes.
- Add fake-request and local HTTP-server contract tests for URL, method, headers, content length,
  exact fields, Unicode, bounded failures, and no retry/read-back after rejection.
- Complete focused/full backend validation, privacy review, and live read-only verification.

## Out of scope

- A second live Devcon PUT, automatic retry, additional publish fields, controller lifecycle
  changes, schemas, migrations, dependencies, package authority changes, or compensation.

## Acceptance criteria

- [x] PUT targets exactly `/sessions/sources/{external_session_id}` with no credential query.
- [x] `x-api-key` and explicit JSON content type are present; the body is one UTF-8 JSON object
  containing exactly `transcript_text` and `duration`.
- [x] Actual urllib request handling supplies a valid content length and preserves Unicode.
- [x] A bounded `{status, message}` error maps to a sanitized reason without copying arbitrary
  upstream diagnostics.
- [x] 400, 401, 404, and 500 failures remain distinguishable and no automatic retry occurs.
- [x] A rejected PUT performs no read-back or durability verification.
- [x] No test contains live credentials, transcript evidence, or the live Session identity.
- [x] The approved live package remains unchanged and no additional live Devcon PUT occurs.

## Rollback

Revert the adapter request/header/error mapping, its focused tests, and this plan. Preserve the
approved Demo Session, the failed publication attempt, and all other durable state.

## Completion record

- Implemented revision: working-tree revision on `codex/devcon-publication-contract`; corrected the
  Devcon source-update route and credential header, retained the exact two-field UTF-8 JSON body,
  and added bounded allowlisted failure-reason mapping. No dependency, schema, migration,
  lifecycle, retry, or runtime-configuration change was made.
- Validation: focused Devcon/controller tests: 19 passed; full backend suite: 1772 passed and 5
  skipped; Ruff: passed; Pyright: 0 errors and 0 warnings; local HTTP-server qualification
  verified urllib content length, JSON content type, exact payload, and Unicode encoding.
- Live result: read-only controller status still reports Session
  `3356fcf7-7907-42c4-bac1-3301927616cd` complete at package revision 1 and approved. No live
  Devcon request was made during diagnosis or qualification, so the original failed PUT remains
  the sole publication attempt.
- Warnings and remaining work: the original rejected response body was discarded by the old
  adapter, so `Invalid Id` is established from the captured request shape and the inspected
  upstream handler rather than preserved live response content. The existing Starlette/httpx
  TestClient deprecation warning remains. A second live publication attempt requires human review.
