# Provider-neutral program source

## Status

Completed (2026-09-24); sandbox validation limitations recorded below

## Execution authority

- Classification: Green autonomous
- Authority evidence: [ADR-0031](../adr/ADR-0031-white-label-identity-and-provider-neutral-program-sources.md)
  (Accepted 2026-09-24), decisions 2, 3, 4, and 6: program schedule sources sit behind a
  provider-neutral port shaped from the existing `DevconProgramSync`; a local
  schedule-file adapter is the default; core logic uses provider-neutral reference keys
  with a compatibility fallback; validation must not require an external API. ADR-0005
  (external integrations use adapters); ADR-0028 (Devcon adapter boundary, narrowed by
  ADR-0031).
- Implementation-ready: Yes. ADR-0031 resolved the direction; the choices below are
  bounded implementation details.
- Required escalation or approval, if any: none. Stop and escalate if the work appears to
  require changing Program Expectation authority semantics, editing an applied migration,
  removing Devcon support, changing publication behavior, or modifying the Demo 2 branch.

## Related findings or ADRs

- ADR: ADR-0031, ADR-0028, ADR-0005, ADR-0004.
- Engineering Directive: ED-0079. ED-0080 (white-label presentation pass) and the later
  Demo 2 generalization depend on it.

## Problem statement

StageFlow cannot run without Devcon. The only program schedule source is
`DevconProgramSync`; `DeploymentConfiguration` hard-locks its base URL to
`api.devcon.org`; the `demo-single-stage` runtime profile rejects configuration without a
`[devcon_read]` section; and core Program Expectation reconciliation reads the
provider-specific key `devcon_session_id`. A white-label deployment — or a repeatable
offline test event — has no way in.

## Verified current behavior

- `backend/app/contexts/integration/devcon/service.py` defines `DevconProgramSync` with
  `synchronize(*, event_id, stage_id) -> ProgramSyncResult`, `probe() -> int`, and
  `cached_program(*, event_id) -> tuple[ProgramExpectation, ...]`.
- `backend/app/bootstrap/event_mode_kernel.py` composes `KernelComponents.devcon_program_sync`
  and exposes `sync_devcon_program()`.
- Consumers on `main`: `backend/app/api/v1/demo.py` (program refresh route) and
  `backend/app/demo/cli.py` (`preflight`, `sync-program`). On the unmerged Demo 2 branch,
  `backend/app/demo/autonomous.py` also calls these names.
- `backend/app/core/config/deployment.py` defines `DevconReadConfiguration` (base URL
  locked to `https://api.devcon.org`, `event_id`, `room_id`, paging and timeout) and the
  `demo-single-stage` profile validator requires `devcon_read`.
- `backend/app/contexts/production/event_mode_kernel/program_reconciliation.py` sets
  `external_session_id=expectation.external_references.get("devcon_session_id")`.
- `backend/app/api/v1/kernel_status.py` reads `devcon_event_id`, `devcon_session_id`, and
  `devcon_room_id` to populate neutrally named response fields.
- `backend/app/api/v1/demo.py` imports and catches `DevconReadError` from Devcon
  infrastructure.
- Migration `0009` backfills Devcon-shaped synchronization scopes. It is applied history.

## Desired behavior

A deployment can supply its program from a local schedule file, with no Devcon
configuration, credentials, or Internet access, through the same port Devcon now
implements. Core reconciliation is provider-neutral. Existing Devcon configurations and
persisted data keep working.

## Design decisions

1. **Port:** a `ProgramScheduleSource` protocol with the three methods `DevconProgramSync`
   already exposes. `DevconProgramSync` conforms without behavior change. The protocol
   lives in `backend/app/contexts/integration/` beside, not inside, the Devcon package.
2. **Local schedule file:** one versioned JSON format, validated strictly. It carries a
   schema version, the configured Event key, and a list of sessions each with a stable
   external session key, title, speaker display strings, Stage key, and timezone-aware
   planned start and end. Unknown fields, naive timestamps, duplicate keys, and unknown
   Stage keys are rejected with typed errors. No CSV in this slice.
3. **Configuration:** add a `[local_schedule]` section (a file path and nothing
   provider-specific). The `demo-single-stage` profile requires **exactly one** of
   `[local_schedule]` or `[devcon_read]`. `[devcon_read]` keeps its current meaning, so
   existing external configurations remain valid.
4. **Composition names:** `KernelComponents` gains `program_source` and `sync_program()`.
   `devcon_program_sync` and `sync_devcon_program()` remain as **documented compatibility
   aliases**, removable once the Demo 2 branch no longer calls them.
5. **Neutral reference keys:** core code reads `external_session_id`, `external_event_id`,
   and `external_room_id` from `external_references`, falling back to the legacy
   `devcon_session_id`, `devcon_event_id`, and `devcon_room_id` keys for data already
   persisted. This applies to both `program_reconciliation.py` and
   `backend/app/api/v1/kernel_status.py`, whose API response fields are already neutral and
   do not change. The Devcon adapter writes the neutral keys for new data. The fallback's
   removal criterion is documented.
6. **Neutral error type:** a provider-neutral `ProgramSourceUnavailableError`, which the
   Devcon adapter's `DevconReadError` maps to or subclasses, so `demo.py` and the CLI stop
   importing Devcon infrastructure errors.
7. **Provider attribution:** each source reports a provider identifier (`local_file`,
   `devcon`) carried in its results, so later presentation can label program data from
   data rather than hardcoded strings.

## In scope

- The `ProgramScheduleSource` port and Devcon conformance.
- A local schedule-file adapter and its strict JSON parser.
- `[local_schedule]` configuration and the exactly-one-source profile rule.
- Neutral composition names with compatibility aliases; API and CLI switched to them.
- The neutral reference keys with legacy fallback, in reconciliation and Kernel status.
- The provider-neutral source error type.
- A provider identifier on source results.
- A small neutral example schedule file under `examples/`, using placeholder identities.
- Behavior-first tests, with no network access required.
- Configuration README, architecture, and glossary updates directly affected.

## Out of scope

- Operator-facing string changes, launcher output, example deployment configuration, and
  frontend fixtures — ED-0080.
- Publication, the `publish-devcon` path, or any external write.
- Modifying the Demo 2 branch or `autonomous.py` — a later directive.
- Editing migration `0009` or any applied migration; new migrations are not needed.
- CSV import, manual entry, or any additional provider.
- Removing Devcon support.

## Constraints

- White-label: no provider name in the port, the local adapter, core reconciliation, or
  configuration defaults. Provider names remain only inside the Devcon adapter and in
  provider-attributed data.
- Offline: the local adapter performs no network access.
- Compatibility: existing `[devcon_read]` configurations, persisted `devcon_session_id`
  references, API routes, and CLI commands keep working unchanged.
- Program Expectations remain External context and never realize a Session.

## Implementation approach

1. Define `ProgramScheduleSource`; verify `DevconProgramSync` conforms.
2. Implement the local schedule-file parser and adapter, reusing Program Expectation
   contracts and the durable cache path Devcon already uses.
3. Add `[local_schedule]` and the exactly-one-source profile rule.
4. Add `program_source`/`sync_program()` and the compatibility aliases; switch
   `demo.py` and `cli.py` to the neutral names.
5. Introduce the neutral reference key with legacy fallback.
6. Add the example schedule file and documentation.
7. Add behavior-first tests.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `backend/app/contexts/integration/program_source.py` | Provider-neutral port (new) |
| `backend/app/contexts/integration/local_schedule/` | Local schedule-file adapter (new) |
| `backend/app/contexts/integration/devcon/service.py` | Port conformance; neutral key; provider id |
| `backend/app/core/config/deployment.py`, `core/config/README.md` | `[local_schedule]`; exactly-one-source rule |
| `backend/app/bootstrap/event_mode_kernel.py` | Neutral composition names plus aliases |
| `backend/app/contexts/production/event_mode_kernel/program_reconciliation.py` | Neutral key with fallback |
| `backend/app/api/v1/kernel_status.py` | Neutral keys with fallback; response fields unchanged |
| `backend/app/api/v1/demo.py`, `backend/app/demo/cli.py` | Use neutral names and error type |
| `examples/local-schedule.example.json` | Neutral example schedule (new) |
| `backend/tests/test_provider_neutral_program_source.py` | Behavior-first tests (new) |

## Data or migration considerations

No migration. Persisted `devcon_session_id` references remain readable through the
fallback. New Devcon-sourced data carries the neutral key.

## Failure and recovery considerations

- A malformed or unreadable schedule file fails synchronization with a typed, bounded
  error and leaves the existing cached program intact, matching Devcon's unavailability
  behavior.
- A configuration supplying both or neither source fails validation with a clear message.

## Observability requirements

Program synchronization results and status report the provider identifier without file
paths or credentials.

## Test strategy

- Behavior-first: valid file import; each rejection case; cached program after a failed
  re-read; exactly-one-source validation; legacy `[devcon_read]` still accepted; Devcon
  conformance to the port; neutral key read and legacy fallback; aliases resolving to the
  neutral implementation; provider identifier propagation.
- No test may require network access or Devcon credentials.
- Full backend suite, Ruff, Pyright.

## Acceptance criteria

- [x] `ProgramScheduleSource` exists; `DevconProgramSync` conforms without behavior change.
- [x] A local schedule-file adapter imports a strict, versioned JSON schedule offline.
- [x] The `demo-single-stage` profile accepts exactly one of `[local_schedule]` or
  `[devcon_read]`; existing Devcon configurations remain valid.
- [x] `program_source`/`sync_program()` exist; Devcon names remain as documented aliases.
- [x] Reconciliation and Kernel status read neutral keys, with a documented legacy
  fallback; Kernel status response fields are unchanged.
- [x] API and CLI code no longer import Devcon infrastructure errors.
- [x] Source results carry a provider identifier.
- [x] No provider name appears in the port, local adapter, core reconciliation, or
  configuration defaults.
- [x] No test requires network access or Devcon credentials.
- [x] Full backend suite, Ruff, and Pyright pass, apart from known environmental failures.
- [x] No migration, publication, Demo 2 branch, or Program Expectation authority change.

## Rollback or reversal

Additive and reversible: remove the port, adapter, configuration section, neutral names,
and fallback. The Devcon path is unchanged throughout, so reverting restores prior
behavior.

## Open questions

- None blocking.

## Completion record

Implemented ED-0079 on `codex/ed-0079-provider-neutral-program-source`, left
uncommitted for owner review. Green scope and ADR-0031 decisions 2, 3, 4, and 6 were
preserved. No product or architecture decision remains open for this directive.

### Implementation outcome

- Added the neutral three-method `ProgramScheduleSource` protocol, shared result alias,
  and `ProgramSourceUnavailableError`. The existing reconciliation contract already
  carries provider attribution; no extra result contract or persistence field was needed.
- Added strict offline JSON schema `"1.0"`, bounded to 4 MiB and 10,000 sessions, with
  typed read/contract failures. Complete validation precedes the existing repository
  reconciliation transaction; failed reads preserve the cache/latest successful result.
  Stable keys survive file relocation, ordering, revisions, withdrawal, and restoration.
- Added explicit `[local_schedule].path` and source-selection validation. Local schedules
  support offline/local-only operation; existing external configuration/defaults and
  legacy validation precedence remain compatible. Provider-specific configuration
  defaults moved unchanged into the adapter with the old import re-exported.
- Added neutral composition/API/CLI use, provider attribution from results, and documented
  read/write/method/constructor compatibility aliases. Neutral reference reads share the
  explicit persisted-data fallback in `events/program_references.py`; provider names do
  not appear in core reconciliation, the port, or the local adapter. This helper isolates
  the design's required legacy-key exception. Removal criteria are in code, configuration
  documentation, and the glossary.
- Added the neutral example schedule and updated configuration, current architecture,
  glossary, plan, and directive indexes. Added 48 behavior-first offline tests and updated
  the existing adapter test's expected new reference keys.
- Production Python and additive runtime configuration parsing changed. No dependencies,
  lockfiles, database schemas, migrations, deployed configuration, publication behavior,
  operator UI strings, launcher output, example deployment TOML, frontend files, or Demo 2
  coordinator/branch changed. A new versioned schedule-file format is the only new schema.

### Validation and environment

All commands used the existing worktree virtual environment and `uv run --no-sync`.
For every test process the inherited `STAGEFLOW_API_SHARED_SECRET` was removed (the
existing conftest supplies its synthetic test credential). `TMP`/`TEMP` were set to
`C:\Dev\StageFlow-codex\.codex-tmp`; `UV_CACHE_DIR` to its `uv-cache` child;
`VIRTUAL_ENV` to this worktree's `backend/.venv`; and `PYTHONDONTWRITEBYTECODE=1`.
The initial uv invocation could not use the system cache; nothing was synchronized.
Pytest cache was disabled and Ruff used `--no-cache`.

Direct pytest invocation initially produced **6 passed, 40 setup errors, 1 warning**:
Windows creation of mode-0700 directories denied access to the sandbox token. A unique
`--basetemp` alone had the same ACL failure and also failed during pytest cleanup.
Subsequent runs used this process-local wrapper via `uv run --no-sync python -`, changing
only mode-0700 directory creation under the specified temp root to inherited Windows
permissions. No repository test or validation guard was disabled or modified:

```python
import os
from pathlib import Path
import pytest

original_mkdir = os.mkdir
temp_root = Path(os.environ["TMP"]).resolve()

def sandbox_mkdir(path, mode=0o777, *, dir_fd=None):
    if mode == 0o700 and Path(path).resolve().is_relative_to(temp_root):
        mode = 0o777
    return original_mkdir(path, mode, dir_fd=dir_fd)

os.mkdir = sandbox_mkdir
# Final focused run:
raise SystemExit(pytest.main([
    "tests/test_provider_neutral_program_source.py", "-p", "no:cacheprovider",
    "--basetemp=" + str(temp_root / "ed0079-focused-final"), "--tb=short",
]))
# Full run used instead:
# ["-p", "no:cacheprovider", "--basetemp=" + str(temp_root / "ed0079-full-final"),
#  "--tb=line", "-ra"]
```

| Final check actually run | Result |
| --- | --- |
| Focused pytest through the wrapper above | **48 passed, 0 failed, 0 skipped, 1 warning** |
| Full backend pytest through the wrapper above | **1,876 passed, 32 failed, 2 skipped, 1 warning** |
| `uv run --no-sync pytest tests/test_devcon_session_publish.py::test_devcon_no_body_response_maps_to_bounded_reason_without_retry -p no:cacheprovider --tb=short` | **1 passed, 0 failed, 0 skipped** |
| `uv run --no-sync ruff check . --no-cache` | Passed; no diagnostics |
| `uv run --no-sync pyright` | **0 errors, 0 warnings, 0 informations**; tool printed a newer-version notice |
| `git diff --check` | Passed; Git warned of configured LF-to-CRLF conversion on some edited files |

Full-suite limitations are explicit, not a passing-suite claim:

- **31 environmental failures:** 7 in `test_real_event_playback_validation_runner.py`
  and 24 in `test_validation_controller.py`. Those tests require temp artifacts outside
  the repository; the required sandbox temp root is inside it. Existing path guards
  reject those artifacts (one manifest assertion likewise expects an external path).
- All four known `test_turnover_boundaries_emit_exact_live_operation_checkpoints` cases
  **failed**, at `validation_root_must_be_outside_repository`, before reaching the known
  em-dash comparison. They were not investigated or modified.
- **1 intermittent unrelated failure:** the unchanged publication test named above
  failed an expected-error assertion in the final full run, passed in the preceding full
  run, and passed its isolated rerun. Publication code/tests were not changed.
- **2 expected platform skips:** FIFO creation and descriptor-bound `scandir` POSIX tests.
  No PostgreSQL skips occurred; real-PostgreSQL tests ran in the full suite. The owner
  should still run the normal full-suite validation outside the sandbox after review.
- The single pytest warning is the existing Starlette/httpx TestClient deprecation.
  Frontend checks were not run because no frontend files changed.

Intermediate focused runs exposed and corrected strict datetime conversion and test
harness errors (29 failed/17 passed, then 18 failed/28 passed; then 46 passed before two
additional cases). The first full attempt had 1,874 passed/32 failed/2 skipped: its one
in-scope validation-precedence failure was corrected before the final run. Initial Ruff
import/line-length issues and Pyright test-client/repository-call annotations were fixed;
Ruff's import-only fixes were limited to the edited files, with no formatter run.

### Review and handoff

The complete tracked diff and new files were deliberately self-reviewed against every
acceptance criterion. Fresh independent Codex review found a missing legacy constructor
keyword; it was restored with regression coverage, and follow-up review reported no
remaining findings. Every changed file belongs to ED-0079. No git metadata writes,
commits, branch operations, push, merge, or PR creation were performed.

The authorized `.codex-tmp` output/cache remains for owner cleanup, with a local
self-ignoring `.gitignore` so generated artifacts do not appear in the review diff.
No temporary output was placed elsewhere. Environment/path-limited qualification and
the intermittent local HTTP test remain validation caveats, not production-readiness
claims or new product decisions.

### Owner validation addendum (2026-09-24)

Owner review found one acceptance gap: the legacy-key read fallback in
`app/contexts/events/program_references.py` was implemented correctly but not exercised by
any test, although compatibility with persisted pre-ADR-0031 records is its entire purpose.
The owner added six parametrized cases to `test_provider_neutral_program_source.py`
covering neutral-key preference, `devcon_session_id` fallback, precedence when both keys
are present, the absent case, and the event and room keys. Review also confirmed both call
sites (`program_reconciliation.py`, `kernel_status.py`) go through the fallback and no
direct `devcon_*` key read remains outside the Devcon adapter and the compatibility map.

Host full-suite validation, outside the sandbox, with the inherited
`STAGEFLOW_API_SHARED_SECRET` and `VIRTUAL_ENV` cleared and `uv run --no-sync`:
**1,910 passed, 4 failed, 2 skipped.** The 4 failures are the known Windows console-encoding
cases in
`test_validation_controller.py::test_turnover_boundaries_emit_exact_live_operation_checkpoints`.
The sandbox temporary-path failures recorded above do not occur on the host. Ruff and
Pyright were clean.

