# Durable transcription worker substrate

## Status

Implementation complete; isolated PostgreSQL qualification pending

## Execution authority

- **Classification:** Green autonomous.
- **Authority evidence:** Operator-authorized durable transcription worker objective;
  accepted ADR-0022, ADR-0025, and ADR-0027; Product Constitution principles 3, 5,
  8-12, 16-17, and 22-25; the accepted post-Kernel capability architecture; and the root
  bounded-autonomy policy.
- **Implementation-ready:** Yes. ADR-0025 resolves the durable Operation/Attempt/Worker
  topology, PostgreSQL ownership, lease/fencing, retry, Event Mode, and first-consumer
  boundaries. The operator has explicitly authorized this bounded implementation.
- **Required escalation:** Stop for a real transcription provider/model or consequential
  dependency, broker/orchestrator, automatic enqueue authority, MTE-driven Session/media
  authority, recorder-profile qualification, automatic AI/editorial authority, or
  deployment/production credentials.

## Related findings or ADRs

- **Accepted ADR:** ADR-0022 PostgreSQL authoritative operational store; ADR-0025
  PostgreSQL durable operations and workers; ADR-0027 durable advisory Media Timing
  Evidence.
- **Architecture:** Post-Kernel capability layer, transcription evidence readiness,
  persistence boundary, Durable Event-Mode Kernel, and domain glossary.
- **Historical plan:** Recorder calibration and transcription readiness prepared the
  accepted decision package and provider-neutral evidence model.
- **Engineering authority:** The operator-authorized objective implements only the
  first-transcription-worker slice unlocked by accepted ADR-0025.

## Problem statement

StageFlow has no restart-safe execution substrate for long-running transcription. The
existing Software Agent Runtime and media collection coordinator are process-local and
cannot provide multi-process claims, attempt history, database-time leases, fencing,
bounded retry, or atomic transcript-result application. Transcription evidence exists
only as accepted architecture and current transcript source adapters do not execute
providers.

## Verified current behavior

- PostgreSQL is the authoritative operational store and migrations 0001-0006 are explicit,
  additive, and independently reversible.
- Completed Media Asset registry identity and Media Timing Evidence v1 are durable.
- No Operation, Attempt, Worker, Worker Capability, Worker Presence, transcript evidence
  repository, worker loop, provider execution port, or automatic enqueue exists.
- Existing current health/capacity contracts are process-local runtime concepts, not a
  durable worker registry or lease authority.
- The vMix recorder profile remains unqualified. Editorial transcript, Candidate Moment,
  Hot Moment, and Clip content remains simulated.
- The pre-existing generated frontend/next-env.d.ts worktree edit is unrelated and must
  remain byte-for-byte unchanged and excluded.

## Desired behavior

One or more local worker processes can explicitly enqueue and execute a provider-neutral
transcription Operation through PostgreSQL authority. Eligible work is claimed
transactionally against durable capability declarations and expiring presence
observations. Each claim creates one retained Attempt and increments a fencing
generation. Lease renewal, result application, failure, retry, expiry, and reconciliation
validate the current generation using database time.

A normalized transcript evidence revision and the Operation/Attempt success transition
commit atomically. Exact replay is idempotent; conflicting replay fails; a stale worker
cannot apply or overwrite a newer accepted result. A deterministic fake execution adapter
proves the lifecycle without selecting a real provider/model.

## In scope

- Add migration 0007 for Durable Operation, retained Operation Attempt, durable Worker,
  versioned Worker Capability, replaceable expiring Worker Presence, normalized Transcript
  Evidence revision/segment/word/alignment records, and schema migration history.
- Add immutable work-execution and transcription-evidence contracts with timezone-aware
  timestamps and recursively immutable bounded metadata where present.
- Add an explicit transcription enqueue application with exact/conflicting replay.
- Add PostgreSQL registration, capability, presence, claim, start, renew, failure,
  fenced result application, expired-attempt reconciliation, reconstruction, and bounded
  status projection behavior.
- Use PostgreSQL database time, row locking with skip-locked claims, configured
  concurrency ceilings, and monotonic fencing generations.
- Implement bounded retry and terminal failure with typed reason codes.
- Implement local Event Mode eligibility and cloud-required deferral/resume semantics.
- Add a provider-neutral TranscriptionExecutionPort and bounded local worker cycle.
- Preserve asset-relative transcript timing and optionally derive advisory wall-clock
  alignment from Media Timing Evidence without replacing the original coordinates.
- Add deterministic fake-adapter end-to-end qualification and real PostgreSQL integration
  tests when STAGEFLOW_TEST_POSTGRES_DSN is available.
- Update architecture, ADR/plan indexes, persistence documentation, and completion
  evidence to report partial implementation accurately.

## Out of scope

- A real transcription provider, model, SDK, FFmpeg/CUDA dependency, cloud service, or
  production worker deployment.
- Automatic enqueue from media completion or any broad transcription authority.
- Candidate generation, automatic AI/editorial authority, rendering, publication, or
  generalized operation kinds.
- Session start/end/membership, package state, media association, recorder authority,
  recorder-profile qualification, or MTE authority expansion.
- Redis, RabbitMQ, Kafka, Celery, Temporal, a broker, microservice split, or outbox.
- Broad Producer or Editorial UI changes. Simulated Candidate/Hot Moment/Clip content
  remains simulated.
- Durable history for live heartbeat, capacity, pressure, utilization, or provider
  health. Only the latest expiring presence observation is replaceable; active work and
  utilization derive from leases/Attempts.

## Constraints

- **Architecture:** PostgreSQL is the only coordination authority. The control plane and
  worker are roles in one modular monolith/codebase.
- **Identity/replay:** Operation, Attempt, Worker, capability, evidence, asset, manifest,
  configuration profile, idempotency, and fencing identity are first-class.
- **Time:** Database time owns lease order/expiry. All exposed timestamps are aware.
- **Execution:** At-least-once provider execution is explicit; exactly-once execution is
  not claimed. Result application is idempotent and fenced.
- **Event Mode:** Local/offline capability may run within ceilings. Cloud-required work
  defaults to deferred under local-only policy and resumes only through explicit policy.
- **Authority:** Transcript and aligned timing remain evidence. Worker state cannot change
  Session, media, package, Editorial, recorder, or OS authority.
- **Privacy:** Diagnostics, projections, and tests omit media paths, transcript content,
  provider payloads, credentials, and raw hardware telemetry.
- **Compatibility:** Existing migrations, Kernel behavior, MTE behavior, transcript source
  adapters, APIs, frontend, and dependencies remain compatible.

## Implementation approach

1. Define work-execution lifecycle, retry policy, operation input, worker/capability/
   presence, claim, Attempt, failure, projection, and typed error contracts.
2. Define normalized transcript evidence revision, asset-relative segments, optional word
   timing and known-semantics confidence, provider/model/tool provenance, partial status,
   limitations, reprocessing lineage, and advisory MTE alignment contracts.
3. Add migration 0007 with additive tables, constraints, indexes, foreign keys, migration
   marker, and an explicit reverse script that drops only 0007-owned tables.
4. Implement one PostgreSQL repository that owns claim/fencing and the atomic transaction
   joining transcript evidence application to Operation/Attempt completion.
5. Implement explicit enqueue replay, worker registration, append-only capabilities,
   replaceable expiring presence, deterministic capability matching, database-time claim/
   renew/start, typed retry/terminal failure, and expired-attempt reconciliation.
6. Implement a provider-neutral execution port and bounded worker cycle. Keep deterministic
   fake adapters in tests.
7. Implement a pure advisory MTE alignment function that preserves asset-relative values,
   records the MTE basis/qualification, and labels wall-clock intervals Derived.
8. Add unit/contract tests plus isolated real-PostgreSQL migration, concurrency, restart,
   fencing, idempotency, Event Mode, and reconstruction tests.
9. Run the complete backend suite, Ruff, Pyright, migration forward/reversal/fresh
   reconstruction, docs/privacy/UTF-8/link checks, and deliberate diff review.
10. Record the completion revision and publish the isolated Green milestone without the
    unrelated frontend edit.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| backend/app/contexts/work_execution/ | Durable operation, worker, capability, presence, claim, retry, projection, repository, and worker-cycle contracts |
| backend/app/contexts/transcription_evidence/ | Provider-neutral execution/evidence/MTE-alignment contracts and application seam |
| backend/app/infrastructure/postgres/transcription_work_repository.py | PostgreSQL claim/lease/fence/retry/reconcile and atomic evidence application |
| backend/app/infrastructure/postgres/sql/0007_transcription_worker_* | Additive forward and bounded reverse migration |
| backend/app/infrastructure/postgres/migrations.py | Explicit apply/reverse methods and Kernel ordering |
| backend/tests/test_transcription_* | Contract, service, migration, concurrency, restart, fencing, retry, and evidence qualification |
| docs/architecture/, docs/adr/, docs/plans/ | Accurate implementation status, persistence boundary, and completion evidence |

## Data or migration considerations

Migration 0007 is additive and references the existing Completed Media Asset registry.
Transcript Evidence owns normalized result tables; Operation rows retain only stable
terminal result identity/revision. Attempt history is retained. Worker Capability rows are
versioned/effective-dated. Worker Presence contains only one replaceable expiring
observation per Worker and is never historical live truth.

The reverse script drops only 0007-owned tables in dependency order and removes only the
0007 migration marker. Reversal is exercised against isolated test data. In a deployed
environment, code must stop new work and history must be exported/preserved before an
operator explicitly authorizes any data-bearing reversal; rollback does not silently
delete accepted evidence or attempt history.

## Failure and recovery considerations

- PostgreSQL outage blocks claims, renewal, state transitions, and authoritative result
  commits; there is no memory fallback.
- Worker/process loss leaves a time-bounded lease. Reconciliation finalizes the expired
  Attempt as lease-lost and either detects an already-applied idempotent result, schedules
  bounded retry, or terminally fails.
- Provider calls may execute more than once. Stable work/result keys and atomic fenced
  application prevent duplicate authoritative evidence.
- Renewal or application with a stale/expired fence fails without mutation.
- Retryable failures use bounded attempt count and backoff; invalid/unsupported input and
  exhausted retries terminally fail.
- Cloud-required work is deferred under local-only Event Mode and is not counted as a
  provider failure.
- Missing capability blocks claim and is projected without inventing a live Worker state.
- Cancellation identity/state remains in the schema; a public cancellation workflow is
  deferred unless required by qualification.

## Observability requirements

Bounded projections expose counts by Operation state, oldest eligible age, active lease
count, retry/terminal/deferred/blocked counts, capability availability, and typed reason
codes. Routine pending/running/retry behavior produces no Producer Attention. Attention
is limited to consequences such as required work blocked by missing capability or
terminal failure. Transcript content, paths, provider payloads, credentials, and raw
utilization are excluded.

Current Worker health/capacity/pressure is an expiring presence observation. Current work
and utilization derive from valid leases and configured concurrency, never from a durable
utilization declaration.

## Test strategy

- Contract tests for validation, immutability, time awareness, provider neutrality, and
  forbidden authority effects.
- Migration text tests plus isolated forward/reversal/reapply and fresh reconstruction.
- Exact/conflicting enqueue replay and stable work-key tests.
- Two-Worker concurrent claim uniqueness and deterministic priority/age ordering.
- Lease establishment/renewal/expiry, database-time ownership, fencing generation, and
  stale-result rejection.
- Retryable, terminal, deferred, blocked, missing-capability, and retry-limit behavior.
- Worker crash/restart, expired/orphaned Attempt recovery, provider-return/application
  crash seam, and PostgreSQL repository reconstruction.
- Exact duplicate and conflicting transcript result application.
- Normalized transcript, optional words/speaker/confidence semantics, reprocessing
  lineage, and MTE alignment preservation.
- Deterministic fake-adapter end-to-end execution and bounded status/Attention projection.
- Complete backend pytest, Ruff, Pyright, docs link/UTF-8/privacy checks, and git diff
  checks. Frontend checks are required only if production frontend changes; none are
  planned.

## Acceptance criteria

- [ ] Migration 0007 applies, reverses, reapplies, and preserves all pre-0007 Kernel/MTE
      tables during reversal.
- [ ] Explicit enqueue is idempotent and conflicting replay is rejected.
- [ ] Capability and Event/deployment matching allow only one eligible Worker claim.
- [ ] Claim and Attempt creation are one transaction using database time and a new fence.
- [ ] Renewal, start, failure, and result application require the active lease/fence.
- [ ] A stale or expired Attempt cannot overwrite a newer accepted result.
- [ ] Retry, terminal failure, missing capability, local-only cloud deferral, and resume
      are explicit and bounded.
- [ ] Restart reconciliation recovers expired Attempts without memory authority.
- [ ] Transcript evidence and Operation completion commit atomically and replay safely.
- [x] Provider/model/tool provenance, relative timing, optional word/speaker/confidence,
      limitations, partial status, and reprocessing lineage are preserved.
- [x] MTE alignment preserves relative timing and records Derived advisory wall-clock
      evidence without elevating an unqualified recorder profile.
- [x] Live presence/capacity/health remain expiring observations; current utilization is
      lease-derived.
- [ ] Routine retries remain diagnostic; only configured consequential blockage/failure
      appears as Attention.
- [x] No real provider/model/dependency, automatic enqueue, Session/media/package/
      Editorial authority, recorder qualification, broker, frontend redesign, or
      deployment change is introduced.
- [ ] Full required validation and deliberate self-review pass.

## Rollback or reversal

Revert the worker production code, tests, documentation, and migration-runner update.
Stop worker processes and new enqueue/claim paths before any schema reversal. Exercise the
0007 reverse migration only on isolated validation data autonomously. Any deployed
data-bearing reversal requires explicit operator approval and prior preservation of
Operation, Attempt, Worker Capability, and Transcript Evidence history.

## Open questions

- **Yellow:** Which real local/cloud transcription provider, model, and consequential
  dependency should implement the execution port?
- **Yellow:** Should completed media automatically enqueue transcription, and under what
  Event/Session/media authority?
- **Yellow:** Which vMix recorder profile, if any, qualifies MTE for specified alignment
  uses?
- **Yellow:** Which automatic AI/editorial decisions, if any, are authorized under a
  separately accepted policy?
- Operational thresholds for required-transcription Attention remain versioned
  configuration calibration unless they change product authority.

## Completion record

- **Implemented revision:** Local milestone commit on
  `codex/transcription-worker-substrate`, based on accepted ADR-0025 commit `a6dbfbb`;
  the publication commit/PR records the final SHA.
- **Files and migrations actually changed:** Work Execution and Transcript Evidence
  contracts/application services; PostgreSQL migration 0007 forward/reverse, runner,
  repository adapter, and exports; focused unit/gated PostgreSQL tests; architecture,
  glossary, ADR index, persistence, and this plan.
- **Commands and tests actually run:** Complete backend `pytest -p no:cacheprovider`,
  `ruff check .`, and `pyright`; focused worker/MTE regression runs; strict UTF-8 and
  relative-link validation across eight changed documents; privacy/scope searches;
  `git diff --check`; sanitized environment/target availability checks.
- **Results and warnings:** 1,697 tests passed, 14 environment-gated tests skipped, Ruff
  passed, Pyright passed, changed-document UTF-8/links passed, scope/privacy review
  passed, and the unrelated frontend file retained SHA-256
  `083E23C4C5E7761DB151134EA1EF7896120C86C5888CDC8A861F534F7E86D6FD`.
  One pre-existing Starlette/httpx deprecation warning remains. The new real-PostgreSQL
  lifecycle test is among the skips because `STAGEFLOW_TEST_POSTGRES_DSN` is absent;
  the configured validation DSN failed authentication before any query or mutation.
- **Execution authority used:** Green autonomous under accepted ADR-0025 and the explicit
  operator objective.
- **Approved deviations:** None.
- **Rollback status:** A bounded 0007 reverse script and dependency-ordered runner path
  are implemented and statically reviewed. Isolated database reversal execution remains
  pending a valid empty test DSN.
- **Remaining work:** Run the gated PostgreSQL migration/concurrency/restart/fencing/
  replay/reversal test against a valid empty isolated database, then complete publication
  review. Real provider/model, automatic enqueue, and broader authority remain Yellow.

