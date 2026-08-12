# Run 004 qualification-tooling hardening

## Status

Completed

## Execution authority

- **Classification:** Green autonomous.
- **Authority evidence:** The user-authorized Run 003 postmortem disposition and bounded
  Run 004 hardening objective; accepted ADR-0023 and ADR-0024 Session authority and
  conservative-association semantics; the existing real-event playback validation plan;
  and the repository's bounded autonomous execution policy.
- **Implementation-ready:** Yes. The changes are limited to reversible qualification
  tooling, focused tests, and sanitized validation documentation.
- **Required escalation or approval:** None. Stop if implementation would change Kernel
  Session authority, generic Sessionless ingest, production persistence, schemas,
  migrations, workers, queues, services, or public contracts.

## Related findings or ADRs

- **Finding/disposition:** Run 003 is **INVALID — intended same-Stage turnover
  qualification not executed**, with secondary **PASS — media-without-Session-authority
  preservation/conservatism diagnostic**.
- **ADRs:** ADR-0023 and ADR-0024.
- **Other authority:** Real-Event Playback Validation and UX Calibration plan and safe
  local validation-controller procedure.

## Problem statement

Run 003 exposed qualification-layer gaps: turnover media cycles could begin without the
expected human-realized Session; a host timeout stopped waiting without terminating the
Full Access child; later controller actions overlapped that child; and the late child
saved a stale whole-document run record that erased newer external command evidence.
The 60-cycle batch also predictably exceeded the interactive host timeout.

## Verified current behavior

- `DriveCycles` is finite and start-to-start cadenced but has no turnover-specific
  Session-authority precondition.
- Controller actions are documented as sequential but no exclusive lock enforces that
  rule.
- The runner loads the full JSON record, retains changes in memory, and saves the whole
  JSON/Markdown pair only after the command returns or fails.
- Run 003 completed 60 trailing cycles after the host stopped waiting; its late save
  overwrote four newer Reconcile/Checkpoint command entries.
- The Kernel correctly registered 35 assets as unresolved with
  `no_safely_eligible_session`; generic Sessionless ingest is valid and must remain so.

## Desired behavior

Turnover experiments explicitly prove human Session authority before live ingest,
overlapping mutations are refused while either the controller or child runner survives,
external JSON evidence is atomic and protected from stale overwrite, completed cycles
are checkpointed incrementally, and oversized interactive batches are refused with a
qualification-only estimate and smaller suggested bound.

## In scope

- Opt-in same-Stage turnover authority guards and human checkpoint messages.
- Host-local per-run controller/runner locking with safe active-action diagnostics.
- Atomic JSON/Markdown replacement, optimistic stale-write detection, and per-cycle
  evidence saves.
- Advisory empirical runtime estimation and interactive-budget refusal.
- Focused tests and Run 003/Run 004 documentation.

## Out of scope

- Kernel, Session, association, package, persistence, worker, scheduler, queue, service,
  schema, migration, deployment, frontend, or generic Sessionless-ingest changes.
- Repairing or mutating Run 003 external evidence.
- Beginning Run 004.

## Constraints

- **Architecture and terminology:** Program Expectations remain planned reality; only an
  authorized human operation realizes a Session.
- **Compatibility:** Existing unguarded controller commands and direct runner syntax
  remain available; the runtime estimate may require an explicit larger declared host
  budget for long `DriveCycles` batches.
- **Offline/event mode:** All safeguards are host-local and require no network or service.
- **Security:** Lock/runtime diagnostics and external evidence never contain DSNs or
  credentials.

## Implementation approach

1. Add an opt-in turnover phase guard around controller Session/Drive actions and print
   explicit human-authority checkpoints.
2. Add a cooperative two-level byte-range lock: the controller owns one byte and the
   runner owns another, so either surviving process blocks a new mutation. Lock metadata
   is redacted, best-effort diagnostic evidence; OS lock ownership is authoritative.
3. Make run-record writes same-directory atomic replacements and reject a save when the
   on-disk fingerprint changed since load. Persist the running command and each completed
   cycle incrementally.
4. Estimate `DriveCycles` duration from observed Candidate count, cadence, the Run 002/003
   empirical model, a conservative qualification overhead factor, and a declared
   interactive budget. Refuse oversized batches without silently changing cycle count.
5. Add regressions, update procedure/result documentation, validate, and self-review.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `scripts/validation/Invoke-StageFlowValidation.ps1` | Guards, lock ownership/diagnostics, runtime estimate, messages |
| `backend/tests/qualification/real_event_playback.py` | Runner lock, atomic optimistic saves, incremental cycle evidence |
| `backend/tests/test_validation_controller.py` | Guard, budget, lock, child-survival, redaction regressions |
| `backend/tests/test_real_event_playback_validation_runner.py` | Atomic/stale/incremental persistence regressions |
| `scripts/validation/README.md` | Run 004 safe procedure and single-console rule |
| `docs/plans/real-event-playback-validation.md` | Run 003 disposition and hardening linkage |
| `docs/validation/README.md` and sanitized Run 003 result | Indexed invalid-run evidence |

## Data or migration considerations

None. Run JSON/Markdown remain external qualification evidence. No production database,
schema, migration, identity, or compatibility format changes are required.

## Failure and recovery considerations

OS-owned locks release on process exit. Stale metadata alone never proves ownership and
is replaced only after both controller and runner lock regions are acquirable. A host
timeout does not release a surviving child lock. Atomic replacement preserves valid JSON;
fingerprint mismatch refuses stale overwrite. Incremental saves retain completed cycles.

## Observability requirements

Operators can see the expected Session label, current activity/end authority,
turnover-phase checkpoint, lock-owning action/PID/start time when safely readable,
Candidate count, requested cycles/cadence, estimated runtime, host budget, and suggested
maximum. No secret value is emitted.

## Test strategy

- Focused controller regressions for turnover authority, generic Sessionless ingest,
  predecessor end, runtime refusal, active lock/child refusal, and secret redaction.
- Focused runner regressions for atomic valid JSON, stale-writer refusal, direct lock,
  running-command persistence, and incremental interrupted-cycle evidence.
- PowerShell parser validation; Ruff; Pyright; focused pytest; documentation link/UTF-8
  checks; `git diff --check`.

## Acceptance criteria

- [x] Guarded Session A/B ingest cannot begin without required human authority.
- [x] Generic unguarded Sessionless ingest remains available.
- [x] A surviving controller or runner deterministically blocks another mutation.
- [x] Stale writers cannot erase newer command evidence and writes remain valid JSON.
- [x] Completed cycles are preserved incrementally during interruption.
- [x] Oversized interactive batches are refused with a smaller suggested bound.
- [x] Run 003 is documented as invalid turnover evidence and is not mutated.
- [x] Focused tests and proportional static/documentation checks pass.

## Rollback or reversal

Revert the qualification scripts, tests, and documentation. External Run 003 evidence is
untouched. No data/schema reversal is needed.

## Open questions

- None for this bounded hardening increment. Production durable-operation recovery and
  automatic authority remain separate Yellow decisions.

## Completion record

- **Implemented revision:** Working tree based on `74f23b4`; no commit was requested.
- **Files and migrations actually changed:** The validation controller and runbook; the
  qualification runner and its focused controller/runner tests; this plan and the
  real-event plan/index; and a sanitized Run 003 result/index entry. No production code,
  dependency, schema, migration, database, runtime configuration, frontend, or external
  Run 003 artifact changed.
- **Commands and tests actually run:** Focused controller/runner pytest; focused Ruff;
  focused strict Pyright; Python byte compilation; PowerShell parser validation;
  changed-document relative-link/strict-UTF-8 checks; changed-file whitespace check;
  and `git diff --check`.
- **Results and warnings:** 37 focused tests passed; Ruff passed; Pyright reported zero
  errors and warnings; Python and PowerShell parsing passed; documentation and whitespace
  checks passed. `git diff --check` passed and emitted existing line-ending conversion
  warnings for unrelated working-tree files. The full backend and frontend suites were
  skipped as disproportionate because production and frontend code did not change.
- **Execution authority used:** Green autonomous plus explicit user request.
- **Approved deviations:** None.
- **Rollback status:** Qualification-only changes are independently reversible.
- **Remaining work:** Begin Run 004 only as a fresh, separately authorized experiment
  using the documented guarded procedure. Production durable-operation recovery,
  distributed locking, automatic authority, and any different persistence architecture
  remain out of scope and would require separate decisions.
