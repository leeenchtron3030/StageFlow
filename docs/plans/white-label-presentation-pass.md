# White-label presentation pass

## Status

Completed — Green implementation; sandbox validation limits recorded below

## Execution authority

- Classification: Green autonomous
- Authority evidence: [ADR-0031](../adr/ADR-0031-white-label-identity-and-provider-neutral-program-sources.md)
  (Accepted 2026-09-24), decisions 1 and 5: no event, organizer, provider, or venue
  identity in operator-facing strings or default examples and fixtures; external
  publication frozen and removed from operator-facing workflow and documentation.
- Implementation-ready: Yes; ED-0079 has landed. This plan relies on ED-0079's
  provider identifier on program-source results and its `[local_schedule]` configuration
  section. Use their names **as implemented** by ED-0079, not as guessed here.
- Required escalation or approval, if any: none. Stop and escalate if the work appears to
  require a public API or storage compatibility break, removing backend Devcon adapter
  code, changing Session or package authority, or rewriting historical documents.

## Related findings or ADRs

- ADR: ADR-0031, ADR-0028.
- Engineering Directive: ED-0080. Depends on ED-0079.

## Problem statement

Operators see Devcon throughout StageFlow even though it is no longer a target: "Program
refreshed · Devcon · just now", "Devcon session · …", "Provider: Devcon", "It never
publishes to Devcon", status entries named "Devcon program read" and "Devcon publication",
and launcher output announcing "StageFlow Demo 1 is ready". The example deployment
configuration hardcodes `test-devcon-8`, `razer-demo`, and "StageFlow Demo 1", and
frontend fixtures are built on Devcon identities. Publication is also still an advertised
operator action.

## Verified current behavior

- `frontend/src/components/demo-program-refresh-control.tsx` and
  `demo-start-session-control.tsx` hardcode "Devcon" in user-visible copy.
- `frontend/src/experience/kernel-adapter.ts` emits status items with ids `devcon-read`
  and `devcon-write` and labels "Devcon program read" and "Devcon publication".
- `scripts/demo/Start-StageFlowDemo.ps1` prints "StageFlow Demo 1 is ready at …", and
  `scripts/demo/StageFlow-Demo.ps1` matches that string when detecting readiness.
- `scripts/demo/StageFlow-Demo.ps1` exposes a `publish-devcon` action, documented in
  `scripts/demo/README.md`.
- `examples/demo-single-stage.toml.example` hardcodes `deployment_id = "razer-demo"`,
  `event_id = "test-devcon-8"`, and `name = "StageFlow Demo 1"`.
- Frontend tests such as `program-reconciliation.test.ts` use `test-devcon-8` and
  `devcon:`-prefixed keys as fixture data.

## Desired behavior

Every operator-facing surface is event- and provider-neutral. Program data is labelled by
the provider identifier carried in the data itself. Publication no longer appears as an
operator action. Default examples and fixtures use placeholder identities.

## In scope

- **Frontend copy:** replace hardcoded "Devcon" with the provider identifier from program
  data, rendered through a small display-name mapping (for example `local_file` → "Local
  schedule"). Neutral copy for status items, with ids renamed to neutral values
  (`program-read`, `publication`).
- **Publication freeze in the UI:** the publication status item reports "Frozen —
  awaiting Delivery design" and exposes no action.
- **Launcher output:** readiness messages become "StageFlow is ready at …"; update
  `StageFlow-Demo.ps1`'s readiness detection to match, keeping detection robust.
- **Publication freeze in tooling:** remove `publish-devcon` from the controller's
  documented action set and help. Invoking it refuses with a clear message citing
  ADR-0031 and performs no network call. Backend adapter code stays, dormant.
- **Examples:** make `examples/demo-single-stage.toml.example` use placeholder identities
  and ED-0079's `[local_schedule]` section by default, with Devcon shown only as a
  commented optional alternative.
- **Fixtures:** replace Devcon identities in frontend and backend test fixtures with
  neutral placeholders, except in tests that specifically exercise the Devcon adapter.
- **Current-state documentation:** README, `scripts/demo/README.md`, and current
  architecture documents describe Devcon as one optional adapter and publication as
  frozen.

## Out of scope

- Historical records: completed plans, reviews, validation results, and ADRs are not
  rewritten. They remain accurate history.
- Backend Devcon adapter code, ADR-0028, and migration `0009`.
- Any public API field or storage change. Kernel status field names are already neutral.
- Renaming source files or routes that contain "demo" — "Demo" describes a mode, not an
  event. A broader rename is not required by ADR-0031.
- Designing a Delivery context or any replacement publication path.

## Constraints

- No hardcoded provider or event names in operator-facing strings after this pass; the
  only permitted appearances are the provider display-name mapping and Devcon-adapter
  tests.
- Frontend changes stay presentation-only; the backend remains authority.
- Launcher readiness detection must not regress; the matched string and the emitted
  string change together.

## Implementation approach

1. Add the provider display-name mapping and replace hardcoded Devcon copy.
2. Rename the status item ids and labels; show publication as frozen.
3. Update launcher output and readiness detection together.
4. Freeze `publish-devcon` in the controller and runbook.
5. Neutralize the example configuration using ED-0079's section names.
6. Neutralize fixtures outside Devcon-adapter tests.
7. Update current-state documentation.
8. Add a white-label guard test that fails if hardcoded provider or event names reappear in
   operator-facing frontend components, excluding the display-name mapping.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `frontend/src/components/demo-program-refresh-control.tsx`, `demo-start-session-control.tsx` | Provider-neutral copy |
| `frontend/src/experience/kernel-adapter.ts` | Neutral status ids and labels; publication frozen |
| `frontend/src/experience/*.test.ts` | Neutral fixtures; white-label guard test |
| `scripts/demo/Start-StageFlowDemo.ps1`, `StageFlow-Demo.ps1`, `scripts/demo/README.md` | Neutral readiness; publication frozen |
| `examples/demo-single-stage.toml.example` | Placeholder identities; local schedule default |
| `README.md`, current architecture docs | Devcon as optional adapter; publication frozen |

## Data or migration considerations

None.

## Failure and recovery considerations

A refused `publish-devcon` invocation exits non-zero with a clear message and performs no
network call or state change.

## Observability requirements

Not applicable beyond the neutral status labels.

## Test strategy

- Frontend: `npm run test`, `npm run lint`, `npm run typecheck`, `npm run build`,
  including the new white-label guard test.
- PowerShell AST parsing for changed scripts; a focused test that the frozen action
  refuses without network access.
- Backend suite for any fixture changes; Ruff and Pyright.

## Acceptance criteria

- [x] No hardcoded provider or event name remains in operator-facing frontend strings,
  outside the provider display-name mapping.
- [x] Program data is labelled by its provider identifier.
- [x] Status items use neutral ids and labels; publication shows as frozen with no action.
- [x] Launcher output and readiness detection are neutral and still work.
- [x] `publish-devcon` is removed from the documented action set and refuses with a clear
  ADR-0031 message, making no network call.
- [x] The example configuration uses placeholder identities and the local schedule
  source by default.
- [x] Fixtures outside Devcon-adapter tests use neutral placeholders.
- [x] A white-label guard test prevents regression.
- [x] Historical documents, backend adapter code, API fields, and storage are unchanged.
- [x] Frontend and backend checks pass, apart from known environmental failures.

## Rollback or reversal

Presentation, tooling, examples, and fixtures only; directly revertible.

## Open questions

- None blocking.

## Completion record

Implemented as uncommitted changes on `codex/ed-0080-white-label-presentation-pass`
for owner review. ED-0079 was verified present before implementation. No new decision,
external service, dependency, or authority change was required.

### Delivered scope

- Added `frontend/src/experience/program-provider.ts`: `local_file` displays as
  "Local schedule", `devcon` as "Devcon", unknown identifiers remain unchanged, and
  missing attribution displays as unknown. Both Demo controls and the Stage's next
  expectation use this mapping. Refresh results use their own returned provider.
- Neutralized Program/Publication status ids and labels; publication reports
  "Frozen — awaiting Delivery design" with no action. Frontend changes are presentation
  only; API field names and authority behavior are unchanged.
- Changed both launcher readiness emission and controller detection together. Removed
  publication help, implementation, credential import, and confirmation option from the
  PowerShell controller. The retired action refuses during parameter validation with an
  ADR-0031 message before configuration, process launch, or network work.
- Updated the example configuration to placeholder Event/deployment/node identities and
  `[local_schedule]`, aligned with the existing example JSON. `[devcon_read]` appears only
  as a commented optional alternative. No deployed runtime configuration was modified.
- Neutralized general frontend fixtures and backend refresh API / Kernel configuration
  fixtures. Devcon adapter/synchronizer tests, explicit legacy compatibility tests, and
  provider-exclusion assertions retain their specific coverage.
- Updated root and Demo READMEs, current architecture principles/system context/glossary,
  and the ED-0080 plan/directive index entries. Historical plans, reviews, validation
  results, ADRs, migration `0009`, backend application/adapters, and storage are unchanged.
- Added `backend/tests/test_white_label_presentation.py` and the frontend
  `white-label.test.ts`, registered in `package.json`. Tests exercise refusal with blocked
  network/process commands, both PowerShell AST parses, readiness URL matching, example
  identity alignment, real component rendering, mapping fallbacks, and a recursive guard
  over components/routes plus the Kernel presentation adapter. Updated existing script
  contract and frontend projection tests. No dependency or lockfile changed.

### Validation evidence

All test processes cleared inherited `STAGEFLOW_API_SHARED_SECRET`. Backend pytest used
`TMP` and `TEMP` at `C:\Dev\StageFlow-codex\.codex-tmp`; uv always used `--no-sync`.
The inherited `VIRTUAL_ENV` was cleared so only this worktree's `.venv` was selected.
Default uv cache access failed, so `UV_CACHE_DIR` (and Ruff's cache) was placed under
`.codex-tmp`. The directory is retained for owner cleanup as instructed, with a local
ignore file for generated contents. No git metadata writes, install/sync, external
publication, deployment, or history changes occurred.

| Check actually run | Observed result |
| --- | --- |
| `uv run --no-sync pytest tests/test_white_label_presentation.py` (with relocated pytest cache on retry) | 6 passed, 0 failed/skipped; 1 cache warning. Includes 2 successful AST parses and 2 successful refusal cases. Initial attempt could not initialize uv cache; first executing attempt had 4 passed / 2 failures because host policy prohibited `.ps1` file execution. The test now invokes the parsed script in memory without changing execution policy. |
| `uv run --no-sync pytest -o cache_dir=../.codex-tmp/pytest-cache` | 1,742 passed, 1 failed, 1 skipped, 178 setup errors, 3 warnings. |
| Same full suite with `--tb=line -r fs` for diagnosis | 1,743 passed, 0 failed, 1 skipped, 178 setup errors, 3 warnings. All 178 errors were `PermissionError` on `.codex-tmp/pytest-of-<user>`; those test bodies did not execute. The skip is the POSIX descriptor-bound `scandir` case. |
| `uv run --no-sync pytest -p no:cacheprovider tests/test_white_label_presentation.py tests/test_demo_program_refresh_api.py tests/test_demo_rehearsal_controller_script.py tests/test_devcon_session_publish.py` | 25 passed, 1 failed, 0 skipped, 1 warning. The unchanged `test_devcon_no_body_response_maps_to_bounded_reason_without_retry` intermittently returned `devcon_publish_unavailable` from its local HTTP test server instead of `devcon_publish_rejected:no_body`; it passed in the diagnostic full run. No adapter code or test was modified. |
| `uv run --no-sync pytest -p no:cacheprovider tests/test_white_label_presentation.py tests/test_demo_program_refresh_api.py tests/test_demo_rehearsal_controller_script.py` | Final directive-focused check: 17 passed, 0 failed/skipped, 1 existing Starlette/httpx deprecation warning. |
| Focused changed configuration test with `--tb=short` | 1 setup error / 2 cache warnings; confirmed the same temporary-directory access denial. |
| `uv run --no-sync ruff check .` | All checks passed. |
| `uv run --no-sync pyright` | 0 errors, 0 warnings, 0 informations; tool printed an available-version notice. |
| `npm.cmd run test` | 0 passed, 9 file-launch failures, 0 skipped: sandbox `spawn EPERM` before test execution. |
| Same package test list with `node --test-isolation=none` | Final: 59 passed, 0 failed, 0 skipped. An initial guard path error was corrected; a redundant rendered Devcon fixture was removed to keep fixtures neutral. The mapping still tests the Devcon display name. |
| `npm.cmd run lint` / `npm.cmd run typecheck` | Both passed with exit 0. |
| `npm.cmd run build` | Production compilation succeeded; completion blocked by `spawn EPERM` at the TypeScript worker. Not a successful build. |
| `git diff` / `git diff --check` | Complete scoped diff self-reviewed; whitespace check passed. Git reports LF-to-CRLF normalization notices. |

The four known parametrizations of
`test_turnover_boundaries_emit_exact_live_operation_checkpoints` all stopped at fixture
setup due to temporary-directory denial. Their em-dash assertions were neither passed
nor failed, and were not investigated or changed. Real-PostgreSQL startup cases that
require these fixtures were likewise not run; no database-connectivity failure was
observed in the diagnostic run. The owner must complete full-suite/PostgreSQL validation
and the frontend build outside this sandbox. Starlette/httpx deprecation and pytest
cache write warnings are environmental/pre-existing. The unrelated intermittent adapter
failure is recorded, not repaired as adjacent work.

### Review, reversal, and remaining work

Every changed source/document belongs to ED-0080. Self-review checked the provider-data
flow, refusal before side effects, unchanged backend/API/storage boundaries, preserved
adapter/legacy test coverage, and paired readiness strings. No Yellow/Red condition or
blocking architecture decision appeared. Delivery design remains deliberately deferred.
The implementation is directly reversible. No production-event-readiness claim is made;
owner review/commit and validation outside the sandbox remain outstanding.

### Owner validation addendum (2026-09-24)

The sandbox blocked the frontend test runner and the build worker (`spawn EPERM`) and the
pytest temporary directory, so the owner re-ran every check on the host:

- Frontend: `npm run test` **59 passed, 0 failed**, including the new white-label guard;
  `npm run lint`, `npm run typecheck`, and `npm run build` all passed.
- Backend full suite, with the inherited `STAGEFLOW_API_SHARED_SECRET` and `VIRTUAL_ENV`
  cleared and `uv run --no-sync`: **1,916 passed, 4 failed, 2 skipped**. The 4 failures are
  the known Windows console-encoding cases in
  `test_validation_controller.py::test_turnover_boundaries_emit_exact_live_operation_checkpoints`.
  The intermittently failing Devcon publish test passed. Ruff and Pyright were clean.

Owner review confirmed `frontend/package.json` changes only the test script's file list (no
dependency change); `operational-views.tsx` routes an existing provider label through the
display mapping; and the Kernel test fixtures that moved from `[devcon_read]` to
`[local_schedule]` lose no coverage, because ED-0079's tests still exercise legacy
`[devcon_read]` acceptance. `C:/StageFlowDemo/...` in examples and fixtures follows the
install-root convention the example configuration already used.

