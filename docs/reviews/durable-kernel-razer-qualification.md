# Durable Kernel Razer reference-node qualification

**Qualification date:** 2026-08-09  
**Reference host:** `WENCESLAS` (Windows build `10.0.26200.8973`, display version
`25H2`)  
**Scope:** fresh qualification of the first Durable Event-Mode Kernel candidate  
**Outcome:** Executed reference-node evidence supports fresh independent phase-completion
review; it does not establish production or event readiness  
**Execution classification:** Green validation/correction under the approved Durable
Event-Mode Kernel plan and ADR-0019 through ADR-0024

## Evidence grading

| Qualification item | Classification | Executed evidence | Result / limitation |
| --- | --- | --- | --- |
| Candidate implementation review | Implemented and test-executed | Reviewed the bounded automatic media path, Producer projections, advisory proposals, configuration, PostgreSQL repository, and migrations. | Preserved discovery/readiness/asset/ingress/association separation, bounded calls, source isolation, path privacy, and human boundary authority. |
| Focused behavior/static validation | Test-executed | Focused Kernel suites passed after correction; Ruff and Pyright passed. Added failure-isolation and interrupted asset/ingress/association replay coverage. | One upstream Starlette/httpx deprecation warning remains. |
| Real PostgreSQL migrations | Real PostgreSQL verified | Applied `0001` through `0003`; inspected constraints/types; reversed `0003` then `0002`; confirmed `0001` remained; reapplied; ran all four gated real-database tests. | Additive/reversible within the documented isolated-database boundary. |
| Complete Kernel scenario | Real Windows/Razer and PostgreSQL verified | Two Stages, two Program Expectations, human Session start/end, four representative media registrations, clear association, unresolved and conflict cases, proposal, trailing media, completion, and Producer queries. | Synthetic disposable media only; no recorder or livestream was controlled. |
| Application process-kill and restart | Real Windows/Razer and PostgreSQL verified | Force-stopped the first app launcher and observed its Uvicorn server exit; PostgreSQL remained live; restarted from the same TOML/database/sources. | Durable Event, Stage, Session, media, ingress, association, proposal, completion, and reconciliation state reconstructed. |
| PostgreSQL stop and recovery | Real Windows/Razer and PostgreSQL verified | Stopped the disposable server, received HTTP 503, and observed an authoritative write fail with `KernelStorageUnavailableError`; restarted and ran explicit reconstruction/reconciliation. | No generic retry system was added. Deployment DSNs should set an operator-selected bounded connection timeout. |
| Source disappearance and recovery | Real Windows/Razer and PostgreSQL verified | Moved only the disposable Studio binding aside, reconciled, restored it, and reconciled again. | Studio alone reported source loss; Main and all durable/media state remained valid; recovery returned ready. |
| PostgreSQL backup and clean restore | Real Windows/Razer and PostgreSQL verified | `pg_dump --format=custom`, clean `createdb`, `pg_restore`, count/identity comparison, fresh reconciliation, and fresh FastAPI process. | Qualification evidence only; not a production backup policy. |
| Bounded endurance | Partially qualified | 197.626-second accepted run, 26 new segments over two Stages, 13 observe/register batches, resource/database samples each batch. | Useful short reference-node evidence, not conference-duration or event-length endurance. |
| Recording/livestream coexistence proxy | Partially qualified | Separate 180.089-second rotating-write/hash process ran concurrently. | Proxy only; no vMix, recorder, livestream, GPU encode, or production file was exercised. |
| Power/sleep posture | Test-executed | Re-ran `powercfg` and Fast Startup registry reads; no policy changed. | Current sleep settings remain unsafe for unattended Event Mode. |
| Full validation matrix | Test-executed | Backend real-PostgreSQL suite, Ruff, Pyright, clean frontend npm install/build/lint/typecheck, and whitespace validation. | Five existing platform/capability skips are reported below and are not passes. |

## Initial integrity and corrections

The initial branch was `main`, 14 commits ahead of `origin/main`, at `8671251`. The
reported Kernel files were modified/untracked, no `.git/index.lock` existed, and no Git
process owned one. `frontend/node_modules` was ignored generated state and lacked npm's
generated lock marker, so only that directory was removed and recreated. Manifests,
lockfiles, dependency versions, and user-authored work were preserved.

Fresh execution found and corrected these Green defects:

- Windows-local source paths now use the same normalized form in Runtime and discovery
  bindings.
- internal collection annotations, the media-cycle composition boundary, and one
  Producer projection branch now satisfy Ruff/Pyright without changing semantics.
- a post-registration diagnostic observation cannot regress a candidate from
  `registered` to `stabilizing`.
- PostgreSQL candidate replay preserves the existing durable registration state instead
  of accepting the rediscovered candidate's initial `discovered` state.
- behavior tests now prove per-candidate failure isolation and recovery after interruption
  between durable asset registration and ingress/association effects.

The last correction was discovered by the first real process-kill attempt. That attempt
preserved identities and downstream records but exposed the false `stabilizing`
projection. It is not counted as a pass. The corrected implementation was rerun against
a fresh database and passed.

## PostgreSQL environment and migrations

- Distribution: official EDB PostgreSQL 17.10 Windows x64 binary archive.
- Archive SHA-256:
  `F9AAFCA58E7026A1EF2CAEEE711ACF761671E57904D430ADC85F468374F5A821`.
- Server: PostgreSQL 17.10, 64-bit, MSVC build.
- Listener: loopback-only `127.0.0.1:55433`.
- Data-location class: disposable user temp directory; no Windows service installed.
- Initialization: `initdb`, locale `C`, UTF-8, trust authentication, role
  `stageflow_test`, disposable databases only.
- Test DSN handling: supplied through `KERNEL_DSN` and
  `STAGEFLOW_TEST_POSTGRES_DSN`; no DSN was written to repository configuration.
- Server timezone: `America/Los_Angeles`.

Real schema inspection confirmed `timestamptz` proposal/boundary times, the Session
foreign key, primary key, advisory epistemic check, non-empty policy/reason checks, and
paired optional model identity/version. Kernel reversal left only `0001_ingress` and
`stageflow.production_event_ingress`; reapply restored all three migration ledger rows.

## Complete scenario and process recovery

The accepted clean scenario produced Event
`8e55e20b-098e-4235-92e0-40d5915ef4f1`, two stable Stage IDs, two Program Expectations,
and completed Session `5206418a-00cd-4937-b6f9-e25d243c0a0b`. Three initial files became
Completed Media Assets, and one trailing file was registered and human-associated after
the presentation ended. Final scenario status reported four registered assets, two
associated, one unresolved, one conflict, one advisory proposal, and package state
`complete`. The proposal did not modify authoritative boundaries.

For the corrected process-kill run, PowerShell force-stopped launcher PID `37596`; its
Uvicorn server PID `32796` exited. PostgreSQL PID `9484` remained listening. The restarted
launcher/server were PID `22100`/`30408`. Before and after restart the Event ID matched,
all four candidates remained `registered`, media/association counts matched, the proposal
remained queryable, and startup reconciliation completed. The restart reprocessed the
same source files idempotently.

## Dependency, storage, and restore recovery

With PostgreSQL stopped, the live app returned HTTP 503 with
`postgresql_unavailable`. A Program Expectation write through a fresh PostgreSQL
repository raised `KernelStorageUnavailableError`; after restart the probe row count was
zero. Source-file counts, byte totals, and SHA-256 hashes were unchanged. A fresh graph
then reconstructed and completed reconciliation with four registered assets.

When only Studio storage was unavailable, status retained the same Event/Stage/media
identities, reported `stage:studio:source_unavailable`, and marked reconciliation failed
without invalidating Main. After restoring the exact directory, reconciliation completed,
ready returned true, and Studio file hashes were unchanged.

The custom-format backup was 62,551 bytes. Before fresh reconciliation, source and restore
databases matched representative counts exactly: one Event, two Stages, two Program
Expectations, one Session, four assets, four ingress rows, four associations, one proposal,
and one completion decision. The restored Session retained
`presentation_ended`/`complete`, package revision 1, and the same identity. A fresh
FastAPI server (PID `32012`) reported ready with the same operational counts.

## Bounded endurance and coexistence proxy

One preliminary attempt completed a Kernel batch but aborted because the
qualification-only Windows RSS probe used an incorrect native field type. The probe was
corrected and statically validated; no Kernel defect was inferred and that attempt is not
counted as endurance evidence.

The accepted run lasted 197.626 seconds. It created 26 uniquely named synthetic segments
across two Stages in 13 batches. Every batch registered two new assets. Final database
state for the qualification Event contained 32 candidates/assets and three Sessions.
PostgreSQL connections were one in every sample. Database size grew from 9,565,875 to
9,950,899 bytes. StageFlow working set grew from 56,868,864 to 57,724,928 bytes, with
57,724,928 bytes peak. The process consumed 9.750 CPU-seconds, measured as 0.247 percent
of total host CPU capacity over the run. No new attention category accumulated; the
pre-existing deliberate Studio unresolved/conflict attention remained.

The concurrent proxy lasted 180.089 seconds, performed 1,650 rotations, wrote
13,841,203,200 bytes cumulatively, retained 33,554,432 bytes, and consumed 13.141
CPU-seconds. It used only disposable files outside configured media sources. This is a
sequential-write/moderate-CPU proxy, not vMix or recording/livestream certification.

## Power and sleep observations

Commands actually run in the closure pass:

```powershell
powercfg /getactivescheme
powercfg /a
powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE
powercfg /query SCHEME_CURRENT SUB_SLEEP RTCWAKE
reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Power" /v HiberbootEnabled
```

Observed state remains:

- Balanced power plan.
- S0 Low Power Idle with network connected, Hibernate, and Fast Startup available.
- AC sleep after 3,600 seconds (60 minutes).
- DC sleep after 180 seconds (3 minutes).
- AC wake timers enabled; DC wake timers disabled.
- Fast Startup enabled (`HiberbootEnabled = 1`).

The AC timeout can suspend an unattended event node, and the DC timeout is especially
unsafe after power loss. Before Event Mode, an operator must explicitly set/review sleep,
hibernate/Fast Startup, wake-timer, Windows Update restart, and adapter power-saving
policy, then rehearse restart behavior. No machine policy was changed. The node is not
fully Event-qualified.

## Repository validation

- Focused Kernel/PostgreSQL suite after correction: 25 passed, two expected DSN-gated
  skips before PostgreSQL provisioning; the gated rerun then passed all four real tests.
- Full backend suite with the real DSN: 1,610 collected; 1,605 passed and five skipped.
  Skips were three unavailable Windows symlink-privilege cases, one non-portable FIFO
  case, and one supported POSIX descriptor-bound `scandir` path.
- Ruff: passed.
- Pyright: zero errors/warnings.
- Frontend: Node 22.23.2/npm 10.9.8; clean `npm ci`, Next.js production build, ESLint,
  and TypeScript `--noEmit` all passed.
- npm audit: 12 findings (nine high, three moderate, zero critical); no dependency or
  lockfile change and no `npm audit fix`.
- The existing FastAPI `TestClient` emitted one Starlette/httpx deprecation warning.

## Qualification conclusion

The drafted Kernel now has executable behavioral/static validation, real PostgreSQL
migration/scenario/recovery evidence, process-kill recovery, dependency and storage
recovery, backup/restore evidence, and honestly bounded endurance/coexistence evidence.
No Yellow or Red condition was found. After commit and clean-worktree closure, the branch
is suitable for a fresh independent Durable Event-Mode Kernel phase-completion review.

This report does not self-accept the Kernel and does not claim production/event readiness.
Conference-duration endurance, real recorder/vMix/livestream coexistence, event-specific
service/credential installation, power-policy correction, and an independent review
remain outside the evidence established here.
