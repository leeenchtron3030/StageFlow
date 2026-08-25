# Demo 2 database compatibility upgrade and write-bearing rehearsal

## Status

Completed - core write-bearing flow qualified; PR promotion unqualified

## Execution authority

- Classification: Green autonomous for the bounded, already-accepted migration and
  rehearsal; explicit action approval granted for one irreversible external test PUT.
- Authority evidence: accepted ED-0067 migration 0010 and its completed isolated
  forward/reverse/reapply qualification; ED-0071's factual unqualified result identifying
  only that missing migration as the guarded preflight blocker; accepted ADR-0022 through
  ADR-0025, ADR-0027, and ADR-0028; PR #71's existing live-rehearsal promotion gate; and
  the user's explicit 2026-08-24 instruction to upgrade the preserved Demo environment,
  run Demo 2 against the same test API used by Demo 1, and perform its guarded write.
- Implementation-ready: Yes. The migration, database, external integration, Demo 2
  capability boundary, test identity, and controller safety gates are already selected.
- Required escalation or approval, if any: the external PUT approval is limited to one
  controller-gated write to the already-qualified Demo 1 Devcon test event. Stop for a
  different database, API/event identity, payload surface, schema change, migration,
  authority semantic, production target, or retry/compensation decision.

## Related findings or ADRs

- Finding/disposition: [ED-0071 result](../validation/results/demo2-hardware-rehearsal-001.md)
  stopped before stack startup because exact database `stageflow_demo` lacked migration
  `0010_editorial_candidate_moment`; ED-0071 intentionally prohibited fixing it.
- ADR: ADR-0022 through ADR-0025, ADR-0027, ADR-0028.
- Engineering Directive or other authority: ED-0063, ED-0067, ED-0068, ED-0071,
  ED-0072, the completed Demo 1 hardware baseline, and PR #71.

## Problem statement

The preserved Demo 1 environment still points at the correct durable database and
Devcon test API/event, but current `main` and Demo 2 require the already-accepted
Editorial location-history migration 0010. The guarded controller correctly refuses to
start against the older schema. Demo 2 therefore cannot test its approved autonomous
features or execute the operator-authorized test publication until that compatibility
gap is closed without losing Demo 1 lineage or weakening any write gate.

## Verified current behavior

- PR #71 is draft, open, CI-green, and cleanly reconciled with current `main`; its branch
  includes current main plus Demo 2's unique autonomous additions.
- ED-0071 verified the exact Demo database identity as `stageflow_demo`, the external
  Demo 1 configuration, and migration ledger 0001 through 0009, then stopped before
  CUDA preflight, process startup, Mac UI access, or any Devcon write.
- Migration 0010 is additive: it creates only
  `stageflow.editorial_candidate_moment_location_history`, its constraint/index, and its
  migration-ledger row. Its accepted reversal drops only that table and ledger row.
- Demo 1 qualified Devcon test event `test-devcon-8` through the existing GET/PUT adapter
  and guarded controller. No API key, DSN, transcript, or private path is committed.

## Desired behavior

Create a restorable backup of the exact Demo database, apply and verify only missing
migration 0010, and run one full Demo 2 rehearsal using the same external Demo 1 API,
event, database, model, CUDA mode, media source, and Mac producer workflow. Exercise all
approved Demo 2 additions, then publish exactly the package-approved transcript fields
through the existing single-write controller and verify durable upstream acceptance.

## In scope

- Verify clean branch/PR state and exact non-secret database/API/event identities.
- Create a timestamped PostgreSQL custom-format backup outside the repository before
  schema mutation; record its location only in sanitized local operator evidence.
- Run the focused 0010 migration tests, apply only missing migration 0010, and verify the
  ledger/object without changing pre-existing Event/Stage/Session/media lineage.
- Run controller `prepare`, `diagnose`, `start`, `status`, `rehearsal-report`, and `stop`
  with Demo 2's rehearsal-only 5-second media and 120-second Program cadence.
- Exercise automatic media discovery/registration/association/transcription, real
  CUDA/float16 evidence, truthful worker/deployment projection, exact-revision Mac UI
  Package Approval, ED-0063 visible degradation with loop survival, and durable restart.
- Exercise the approved post-Demo-1 surfaces present on current main: declare or inspect
  a human Editorial Candidate Moment without automatic authority, confirm its bounded
  location/conflict projection, and inspect the bounded Producer Work Queue read model.
- Invoke `publish-devcon` once with captured human authority only after every existing
  remote-identity, completed-Session, package, transcript, and digest gate passes; verify
  the controller's durable upstream result and bounded public-cache convergence.
- Record a new sanitized result and update this completion record and PR #71 without
  merging the PR.

## Out of scope

- A new API, provider, model, dependency, profile, migration, schema object, payload
  field, automatic publication policy, Session/Moment/package authority, or production
  deployment/readiness claim.
- Automatic or retried Devcon PUTs, a write to any event other than the exact qualified
  Demo 1 test event, or bypass of Package Approval/the controller.
- Destructive cleanup of preserved Demo 1 data or rollback that could remove new
  Editorial location history without first proving it is rehearsal-owned.
- Merging or marking PR #71 ready. It remains draft and unmerged regardless of outcome.

## Constraints

- Architecture and terminology constraints: PostgreSQL remains authority; Program
  Expectations remain External; transcript evidence remains non-authoritative; human
  Candidate Moment and Package Approval commands remain explicit and attributable.
- Compatibility constraints: migration 0010 and existing routes/contracts are used
  unchanged; Demo 1 data and controller semantics remain compatible.
- Offline/event-mode constraints: local production work continues if Devcon refresh is
  unavailable; the external write is optional to local durable completion.
- Security and data-handling constraints: no secret values, DSNs, media paths, transcript
  text, raw provider payloads, or backup contents enter Git or normal reports. Backend
  and PostgreSQL remain loopback-only; only the trusted LAN UI is Mac-reachable.

## Implementation approach

1. Confirm the branch is clean, matches PR #71, and still merge-simulates cleanly.
2. Verify credential presence and exact database/API/event identity without emitting
   secret values; stop on mismatch or ambiguity.
3. Run the focused 0010 tests. Create and verify a timestamped custom-format full backup.
4. Apply `PostgresMigrationRunner.apply_editorial_candidate_moment_v1()` once and verify
   migrations 0001-0010, the new table, and preserved authoritative row counts.
5. Run guarded diagnosis and CUDA inference, then start the launcher-owned stack with
   rehearsal-only Demo 2 timers enabled.
6. Use vMix and the Mac UI to execute the Session/media/transcription/Editorial/Work
   Queue/Package Approval flow. Induce and recover from one bounded source interruption.
7. Stop/restart the stack and verify durable reconstruction and idempotent reconciliation.
8. Preview the exact Devcon candidate/digest, confirm all controller gates, invoke the
   one authorized PUT, and verify its durable upstream result without retry.
9. Stop only launcher-owned processes, generate sanitized evidence, run proportionate
   validation/privacy/diff checks, commit, and push updates to the draft PR.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `ENGINEERING_DIRECTIVES.md` | Record ED-0072 authority and status |
| `docs/plans/README.md` | Index this plan |
| `docs/plans/demo2-database-upgrade-and-write-rehearsal.md` | Plan and completion record |
| `docs/validation/results/demo2-hardware-rehearsal-002.md` | Sanitized factual evidence |
| External `stageflow_demo` PostgreSQL database | Apply accepted migration 0010 only |
| External rehearsal configuration | Ephemeral Demo 2 timer enablement only; never committed |

## Data or migration considerations

Migration 0010 is the only authorized schema change. Before it runs, create a full
custom-format database backup and capture pre-migration ledger plus authoritative table
counts without contents. After it runs, verify that exactly one ledger version and one
empty/additive location-history table were added while all pre-existing counts and
identity-bearing rows remain intact. Preserve the backup until the user accepts the
rehearsal evidence. No data transform, identity rewrite, or lineage reassignment occurs.

## Failure and recovery considerations

- A missing backup tool, failed/non-restorable backup, database/API identity ambiguity,
  unexpected migration state, or changed Devcon event stops execution before mutation.
- The migration runner is ledger-guarded and re-entry is a no-op. If it fails, preserve
  database and logs and validate from the backup; do not improvise SQL.
- Reverse 0010 only if no location-history row was created after upgrade and reversal is
  explicitly chosen. Otherwise preserve the additive schema and use the full backup for
  an approved restore decision; never silently discard authoritative Editorial history.
- A failed external PUT is not retried. Record the bounded result and stop for a new
  explicit decision. Local Session/package state remains authoritative and preserved.
- Process/source failure must be visible, bounded, and recoverable by coordinator retry
  or launcher restart without browser-memory authority.

## Observability requirements

Record sanitized branch/PR/migration/backup verification, GPU/model/compute mode,
automation owner and cadence, worker capability, Event/Stage/Session/package revisions,
bounded media/Operation/transcript provenance, Editorial/Work Queue outcomes, failure
and recovery codes, restart reconstruction, publication candidate digest, controller
write acceptance, durable upstream verification, and public-cache status. Record only
credential presence—not values—and omit transcript/media/provider contents.

## Test strategy

- Run focused migration forward/reverse/reapply and Editorial repository tests before
  applying 0010 to the preserved database.
- Verify the custom-format backup can be listed by PostgreSQL tooling before migration.
- Run controller preflight including a real silent-audio CUDA inference.
- Exercise real autonomous timers, Mac UI, vMix, failure survival, restart, Editorial
  Candidate Moment, Work Queue, Package Approval, and one guarded Devcon test PUT.
- Run directly affected backend tests, Ruff, Pyright, frontend checks if production code
  changes, PowerShell syntax checks if controller code changes, `git diff --check`, and a
  final secret/privacy scan. Do not claim full suites unless they actually run.

## Acceptance criteria

- [x] A verified restorable backup exists before migration and no secret enters Git.
- [x] Exact database `stageflow_demo` reaches migrations 0001-0010 with preserved Demo 1
  identities/counts and only the accepted 0010 schema addition.
- [x] The stack passes real CUDA preflight and preserves loopback backend/PostgreSQL plus
  trusted-LAN-only frontend boundaries.
- [x] Autonomous media progression and CUDA/float16 transcription run on the 5-second
  timer without manual per-block cycle calls.
- [x] Autonomous 120-second Devcon Program refresh and truthful worker/GPU projection are
  observed without interrupting local work on an induced provider/source failure.
- [x] A human Editorial Candidate Moment and Producer Work Queue projection are exercised
  without granting either automatic authority.
- [x] Mac UI Package Approval targets an audited exact completed package revision.
- [ ] ED-0063 visible degradation/loop survival and durable restart reconstruction pass.
  Durable restart passed; the controlled missing-source test recovered but did not enter
  the unexpected-exception/degraded path.
- [x] The controller sends exactly one authorized PUT to Demo 1 test event
  `test-devcon-8`; the accepted digest/fields and durable upstream result are verified.
- [x] A sanitized result distinguishes Demo qualification from production/event readiness.
- [x] PR #71 remains draft, open, and unmerged.

## Rollback or reversal

Code/document changes are reverted normally. Stop only launcher-owned processes and
disable the ephemeral timers. Migration 0010 may be reversed only before it owns any new
location-history row; otherwise preserve it or obtain explicit approval for a restore
from the verified backup. The Devcon PUT is an explicitly authorized irreversible test
side effect: the controller neither retries nor compensates it, and this plan performs
no automatic reversal.

## Open questions

- None before preflight. The exact rehearsal Session/source-interruption timing is an
  operator detail selected during the run and recorded in the sanitized result.

## Completion record

- Implemented revisions: `b2136c0`, `491eee8`, `88e41e5`, and `9b028aa`, plus
  the final evidence commit recorded by Git history.
- Files and migrations actually changed: the accepted migration 0010 was applied to
  the preserved external `stageflow_demo` database after a verified custom-format
  backup. Compatibility corrections changed the Demo controller, bounded Demo API
  transcript projection, PowerShell launcher, directly affected tests, and controller
  documentation. This plan, ED-0072, its plan index, and the sanitized result were
  updated. No new migration file, dependency, payload field, or automatic write was
  introduced.
- Commands and tests actually run: PostgreSQL backup/listing and migration inspection;
  Demo controller diagnose/preflight/start/status/report/publish/stop; real CUDA
  inference; focused migration, controller, Demo API, authentication, and PowerShell
  checks; full backend `pytest`, Ruff, and Pyright; `git diff --check`; and a final
  secret/privacy review.
- Results and warnings: backup verified (234 entries; SHA-256 recorded outside Git),
  migration 0010 applied with pre-existing row counts preserved, 6/6 autonomous media
  transcripts completed on CUDA/float16, one human Moment persisted, exact package
  revision 1 approved on the Mac, durable restart reconstructed authority, and the one
  authorized Devcon PUT converged durably and publicly. Full backend validation passed:
  1822 passed, 5 skipped; Ruff passed; Pyright reported zero errors/warnings. One known
  existing Starlette/httpx TestClient deprecation warning remained.
- Execution authority used: Green bounded migration/rehearsal plus the user's explicit
  2026-08-24 approval for one guarded Devcon test PUT.
- Approved deviations: none. A compatibility blocker was corrected within accepted
  architecture; the write was not retried.
- Rollback status: not invoked. The additive accepted schema, verified backup, durable
  Demo state, and authorized external test side effect were preserved. Launcher-owned
  processes were stopped; vMix was left open and no longer recording.
- Remaining work: qualify ED-0063's unexpected-exception visible degradation/loop
  survival path in a future bounded rehearsal. PR #71 remains draft, open, unmerged,
  and promotion-unqualified until that gate is proven.
