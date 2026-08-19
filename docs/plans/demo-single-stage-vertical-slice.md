# Demo single-stage vertical slice

## Status

Implementation complete; live Demo rehearsal pending local model, media, and configuration prerequisites

## Execution authority

- Classification: Green autonomous
- Authority evidence: the 2026-08-18 Demo Vertical Slice milestone request; accepted
  ADR-0022 through ADR-0025 and ADR-0027; the accepted scoped transcription baseline in
  `docs/validation/transcription-engine-evaluation.md`; ED-0053; and the Green slices in
  `docs/architecture/post-kernel-capability-layer.md`.
- Implementation-ready: Yes
- Required escalation or approval, if any: Devcon write publication remains disabled
  unless every upstream durability qualification in the milestone passes. Automatic
  Session or Editorial authority, a broader trust boundary, and any contradiction of
  the accepted worker/transcription architecture require escalation.

## Related findings or ADRs

- Finding/disposition: Demo 1 and first Windows RTX local transcription acceptance;
  broader provider/model selection remains conditional on accented/noisy event evidence.
- ADR: ADR-0019 through ADR-0025 and ADR-0027. Proposed ADR-0026 is not used.
- Engineering Directive or other authority: ED-0053 bounded local filesystem discovery;
  Product Constitution; Durable Event-Mode Kernel and post-Kernel capability architecture.

## Problem statement

StageFlow has a durable Kernel, a bounded media cycle, a PostgreSQL transcription worker
substrate, and read-only operational UI, but no composed path that lets a Producer use a
Mac browser to run one real Stage on a Razer Event Node. Demo 1 must prove the accepted
boundaries end to end with real Devcon program data, vMix-produced media, durable local
GPU transcription, visible transcript evidence, explicit human commands, and restart-safe
state.

## Verified current behavior

- The backend composes the PostgreSQL Kernel and bounded media cycle when
  `STAGEFLOW_KERNEL_CONFIG_PATH` is supplied, but the HTTP surface is read-only and the
  startup migration check stops at migration 0006.
- Migration 0007 and the provider-neutral operation, worker, and transcript-evidence
  contracts/repository are implemented and PostgreSQL-qualified.
- The only real engine adapters are qualification utilities; no production worker process
  or faster-whisper adapter is composed.
- Program Expectations persist, but there is no Devcon adapter or independent program
  projection. The public Devcon API returns enveloped events and paginated sessions;
  session room data is nested and `test-devcon-8` is distinct from `devcon8`.
- The UI reads Kernel status server-side and renders disabled authority controls and
  fixture transcript content. It has no mutation proxy.
- Package Ready changes state without the established durable human-command identity.
- No durable Editorial Candidate Moment store or Mark Moment command exists.
- `frontend/next-env.d.ts` contains a pre-existing unrelated user modification and is
  excluded from this plan.

## Desired behavior

An explicit `demo-single-stage` profile composes one Event and Stage on the Razer. One
PowerShell command preflights and starts the local stack without exposing PostgreSQL.
Devcon program data synchronizes into durable external Program Expectations and remains
available offline. A Producer uses explicit confirmed commands to start/end a Session,
run a bounded media cycle and enqueue transcription, mark the package ready, and declare
a manual Moment. A local faster-whisper CUDA/float16 worker produces durable provider-
neutral transcript evidence whose progress, result, provenance, and limitations are
visible through the Next.js Producer/Editorial UI. Restart reconstructs important state.

## In scope

- Explicit `demo-single-stage` runtime/profile configuration and truthful UI labeling.
- A bounded Razer launcher and preflight with LAN Producer URL and localhost backend.
- Credential-free Devcon read adapter/synchronization for one selected event/Stage.
- Confirmed, idempotent demo command API and same-origin Next.js mutation boundary.
- Explicit bounded media-cycle execution and associated-asset transcription enqueue.
- Production faster-whisper adapter and durable local worker command with no silent CPU
  fallback.
- Bounded work/transcript/program projections and real transcript/timeline UI.
- Durable Package Ready identity and the Green human-declared Mark Moment slice.
- Unit, contract, PostgreSQL, API, frontend, launcher, restart, and rehearsal validation.
- Devcon publication qualification evidence and a disabled-by-default status projection.

## Out of scope

- Automatic Session boundaries, association policy changes, automatic Candidate/Hot
  Moments, clip generation, Marketing, cloud providers, brokers, service proliferation,
  multi-Stage qualification, production authentication/deployment, and Event-readiness
  claims.
- Generic Devcon field editing or automatic publication.
- Devcon writes unless all named upstream marker/restore/API/Git durability checks pass.
- A watcher or continuous filesystem polling service; Demo processing invokes the
  existing bounded cycle explicitly.

## Constraints

- Architecture and terminology constraints: Devcon scheduled Session remains External
  Program Expectation, never actual Session authority. Discovery, readiness, registration,
  association, Operation, and Transcript Evidence remain distinct. Manual Mark Moment
  creates an unapproved declared Editorial Candidate Moment.
- Compatibility constraints: additive internal/API/UI changes; schema changes use the
  next explicit forward/reverse migration and preserve prior histories.
- Offline/event-mode constraints: internet is optional after Devcon synchronization;
  model files must be preflighted locally; recording remains local-first on vMix.
- Security and data-handling constraints: no secret output or persistence; PostgreSQL and
  backend remain loopback-only; only Next.js is LAN-bound for the trusted Demo network;
  paths and raw provider payloads are excluded from bounded projections.

## Implementation approach

1. Add the explicit profile, validated configuration, example, and one-command launcher.
2. Add a narrow Devcon read port/adapter and idempotent Program Expectation sync/query.
3. Add a bounded demo application/API layer for confirmed authority commands, media
   cycle execution, and transcription enqueue using stable client operation IDs.
4. Extend human-command idempotency for Package Ready and add the separate durable
   human-declared Editorial Candidate Moment slice with forward/reverse migration.
5. Promote the qualified faster-whisper knowledge into a production adapter and worker
   process that declares exact CUDA/model/runtime capabilities and fails visibly.
6. Extend bounded status projections and the Next.js same-origin surface for real
   program, operation, evidence, transcript timeline, and manual mark data.
7. Validate live-compatible local/UNC discovery, PostgreSQL migration/reversal/restart,
   API idempotency, worker fencing/result replay, frontend build/static checks, launcher
   preflight, and the rehearsal path. Keep fixtures as the labeled emergency path.
8. Publish independently reviewable commits/PR milestones. Evaluate Devcon write only
   after the upstream durability gate; record disabled state rather than blocking reads.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `backend/app/core/config` and demo config | Runtime profile and validated Demo settings |
| `backend/app/integrations/devcon` | Narrow public read adapter and normalization |
| `backend/app/api/v1` and bootstrap | Demo command/query composition |
| Kernel/work execution repositories | Durable Package Ready and bounded projections |
| New Editorial Candidate Moment boundary | Declared Mark Moment contract/repository |
| `backend/app/infrastructure/postgres/sql/0008_*` | Explicit forward/reverse Demo command/Moment state |
| Transcription provider/worker modules | Real faster-whisper CUDA adapter and process |
| `frontend/src` | Same-origin commands and real program/transcript/timeline UI |
| `scripts/demo` | Razer launcher, preflight, rehearsal support |
| Tests and current architecture/operations docs | Behavioral evidence and runbook |

## Data or migration considerations

Migration 0008 will add only the typed Package Ready command/history support and declared
Editorial Candidate Moment state needed by this slice. Forward/reverse scripts and
migration tests are required. Reversal drops only 0008-owned objects/constraints and
must abort on unexpected ownership or dependent state. Existing Session/media/worker
identity and histories are unchanged.

## Failure and recovery considerations

- Every command accepts a stable operation ID; exact replay returns its prior result and
  conflicting replay fails.
- Devcon sync is explicit and idempotent. Cached expectations remain queryable when the
  network is unavailable; failed refresh does not delete the cache.
- Media processing is one bounded pass. A stabilizing asset remains visible and a later
  explicit pass advances it; no hidden watcher is introduced.
- Transcription remains at-least-once with migration-0007 leases/fencing/reconciliation.
  Provider failure records a bounded reason and never silently changes device/model.
- UI commands refresh authoritative state and display conflicts/staleness; backend or
  database loss disables authority rather than inventing local success.

## Observability requirements

Operators can determine profile/deployment identity, configuration and source readiness,
Devcon cache/refresh state, Session/package revisions, media stage counts, Operation and
worker state, exact provider/model/device/compute type, transcript revision/status,
limitations, Candidate Moment lineage, command operation ID, and bounded failure reason.
Secrets, source paths, provider payloads, and raw diagnostics are not returned.

## Test strategy

- Unit/contract tests for profile validation, Devcon mapping/pagination/offline cache,
  command confirmation/idempotency/conflicts, provider normalization, and no CPU fallback.
- PostgreSQL migration forward/reverse and repository/API tests against the isolated test
  database, including restart reconstruction and stale fencing.
- Local and UNC-path bounded media-cycle tests preserving all four media meanings.
- Real CUDA rehearsal qualification when the Razer runtime/model/corpus is available.
- `uv run pytest`, `uv run ruff check .`, `uv run pyright`.
- `npm run build`, `npm run lint`, `npm run typecheck`.
- `git diff --check` and deliberate diff/self-review.

## Acceptance criteria

- [ ] The UI truthfully identifies `demo-single-stage` and a human-usable LAN URL works
  while backend/PostgreSQL remain non-LAN.
- [x] One command preflights and starts backend, frontend, worker, config, source, GPU,
  Devcon read, and LAN binding or fails with a bounded actionable reason.
- [ ] Real Devcon data becomes durable Program Expectations, remains External, and is
  visible offline after sync.
- [x] Start Session, End Presentation, Process/Transcribe, Package Ready, and Mark Moment
  are explicit confirmed commands with durable identity, observable result, exact replay,
  and conflict rejection.
- [x] Local or UNC media advances only through discovery, readiness, registration, and
  accepted association policy before transcription enqueue.
- [ ] The Razer worker claims a durable Operation and real faster-whisper
  `large-v3-turbo` CUDA/float16 output becomes durable Transcript Evidence with full
  provider/model/runtime/revision/timing/provenance/limitation facts.
- [x] The Mac-facing UI implements bounded program, Session, media, work, Transcription
  Evidence, timeline, provenance, and manual declared Moment projections. A real Mac/LAN
  rehearsal remains pending the listed local prerequisites.
- [x] Restart reconstructs Session/media/Operation/evidence/Moment state.
- [x] Live, rehearsal, and labeled emergency paths are documented; live and rehearsal
  use the real architecture, while the emergency fixture remains explicitly non-authoritative.
- [x] Devcon read remains independent. Write is enabled only if every durability gate
  passes; otherwise it remains visibly disabled without blocking Demo 1.
- [x] Required backend/frontend/static/whitespace and proportionate real PostgreSQL/CUDA
  validation are green, with unavailable model/media rehearsal validation reported rather
  than simulated.

## Rollback or reversal

Revert milestone commits independently, stop Demo processes, and restore the prior
configuration. Reverse migration 0008 only after verifying all target state is 0008-owned
Demo qualification data and no unexpected dependencies exist. Migration 0007 and earlier
state are not touched. Devcon read creates no remote state; Devcon write remains disabled
unless separately qualified.

## Open questions

- None for the Green read/control/transcription/Moment slice. Devcon write eligibility is
  an evidence gate, not an assumed capability.

## Completion record

- Implemented revision: Demo Single-Stage Vertical Slice milestone commit on `codex/demo-single-stage-vertical-slice`.
- Files and migrations actually changed: Demo profile/configuration and launcher; Devcon read
  synchronization; faster-whisper CUDA worker; confirmed Demo API; durable Package Ready and
  declared Editorial Candidate Moment boundaries; migration 0008; bounded Next.js proxy and
  Program/Transcription Evidence UI; focused backend/frontend/launcher/restart tests and docs.
- Commands and tests actually run: migration 0008 forward/reverse/final-forward qualification
  and restart reconstruction against isolated `stageflow_worker_test`; full backend `pytest`,
  Ruff, and Pyright; frontend Node tests, typecheck, lint, and production build; PowerShell AST
  parse; launcher contract tests; real bounded launcher negative preflight; `git diff --check`.
- Results and warnings: 1,732 backend tests passed, 5 Windows filesystem-capability tests
  skipped, and one third-party Starlette deprecation warning; Ruff and Pyright passed; 18
  frontend tests, typecheck, lint, and Next production build passed; 4 launcher contract tests
  passed; RTX 3080 Ti was detected; launcher stopped safely with
  `configured_media_source_unavailable` because no concrete Demo media/model/config is present.
- Execution authority used: Green autonomous Demo Vertical Slice request plus explicit Yellow
  approvals for migration 0008 and trusted-Demo-LAN Transcription Evidence exposure.
- Approved deviations: no simulated live CUDA transcript or Mac/LAN rehearsal; Devcon write
  publication remains disabled because its independent upstream durability gate is not qualified.
- Rollback status: migration 0008 reversal was qualified with default restrictive dependency
  behavior against the isolated test database, then the forward migration was reapplied. No
  production database or deployment was touched.
- Remaining work: provision an external concrete Demo config, exact local model, and controlled
  media source; then run the real Razer worker/Devcon/offline-cache/Mac-LAN rehearsal and capture
  representative accented/noisy-event evidence before broader provider/model acceptance.
