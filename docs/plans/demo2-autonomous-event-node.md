# Demo 2 Autonomous Event Node

## Status and authority

In progress. Green autonomous under the explicit 2026-08-20 Demo 2 directive and
the 2026-08-20 association-lifecycle decision.
The milestone began under the explicit 2026-08-20 Demo 2 directive,
accepted ADR-0023 through ADR-0025 and ADR-0027, and the completed Demo vertical
slice and Program reconciliation plans. Implementation-ready: Yes.

The directive selects only the bounded automatic enqueue and process-owned
reconciliation policies ADR-0025 left unselected. Stop before automatic Session,
Moment, package, or publication authority; association-policy change; schema or
migration; new dependency/service/profile; production deployment; or destructive
data work.

## Problem and verified current behavior

Demo 1 proves the real vertical slice but media processing and Program refresh
remain manual, and worker currentness can report falsely.

- `main` is `504b32567cf856082642697b6974859290c65020`; local annotated tag
  `demo1-qualified-2026-08-20` points to it.
- The original worktree has unrelated preserved changes; this work is isolated on
  clean branch `codex/demo2-autonomous-event-node`.
- Startup runs one bounded media cycle; continued operation requires confirmed
  `Process / Transcribe`, whose enqueue identity is command-specific.
- Program sync is startup/controller and manual-only. PostgreSQL serializes it and
  preserves the prior successful snapshot on failure.
- The launcher owns backend, worker, and frontend; lifespan has no coordinator.
- Worker presence is durable/scoped, but controller currentness can use the wrong
  deployment identity.
- The uncommitted package-approval slice is bounded and will be selectively
  reproduced rather than copied wholesale.

## Association lifecycle decision

Authorized 2026-08-20: an existing deterministic `unresolved` association is reevaluated
when its material Session input set changes. This is a lifecycle extension of the existing
accepted association policy, not a new policy. Material inputs are the durable Session
identity and revision references used by the policy. Unchanged inputs create no revision;
human and conflict associations remain protected. Deterministic restart, no-op, later-safe,
human-protection, and conflict-protection tests are required.

## Desired behavior and scope

With explicit configuration in the existing Demo profile, one launcher-owned
coordinator periodically runs the accepted media cycle, enqueues safely associated
assets, and refreshes Devcon Program. Manual paths stay idempotent. Status shows
quiet automation freshness and truthful worker availability. Human decisions stay
explicit and separate.

In scope: default-off configuration (5-second media, 120-second Program);
lifespan-owned coordinator with PostgreSQL advisory singleton ownership; shared
automatic/manual application services; bounded status; exact-revision human package
approval; deterministic backend/frontend/launcher/restart/concurrency/privacy tests;
Demo 1 fallback and Demo 2 runbook.

Out of scope: watcher, broker, external scheduler, microservice, OS task, new profile,
automatic authority, Devcon PUT, association-policy changes beyond the authorized
deterministic-unresolved lifecycle extension, changed late-media semantics, schema,
migration, dependency, production deployment, and SMB/vMix until two-machine success.

Discovery, readiness, registration, association, Operation, and evidence remain
distinct. Automation defaults off. Demo 1/API/data compatibility is preserved.
Devcon failure cannot interrupt local production. Projections omit paths, DSNs,
credentials, contexts, transcript content, provider payloads, and unbounded details.

## Implementation, recovery, and observability

1. Add optional config and a Demo 2 example without a new profile.
2. Extract stable cross-trigger enqueue into the Demo application service.
3. Add a lifespan coordinator with one advisory lock per deployment, bounded waits,
   serialized cycles, failure isolation, and clean shutdown.
4. Add automation/Program freshness and worker identity/capability projections.
5. Reproduce audited package approval with correct revision replay/storage errors.
6. Add tests and run complete validation/privacy review.
7. Run live qualification only with the external Razer/Mac environment.

No schema/migration is planned. PostgreSQL remains authoritative. Process death
releases the lock; restart reconciles from durable state. Stable Operation identity
and deterministic request facts make automatic/manual/concurrent/restarted enqueue
exact replays. One failed asset does not block later assets; worker failure does not
stop media; Program failure preserves the prior snapshot. Stop is bounded.

Expose enabled/running/owner state, intervals, bounded cycle and last
attempt/success/failure facts, media/association/enqueue results, Program freshness,
work counts, and current worker availability/capability. Healthy cycles remain quiet.

## Validation and acceptance

Test config, stable/unstable/unresolved/later-safe media, automatic/manual/concurrent
replay, per-asset isolation, no Session authority, worker-independent progress,
coordinator ownership/cadence/stop/restart, Program success/failure/no-PUT/Session
isolation, API/controller/frontend freshness/worker/approval/privacy.

Run full pytest/Ruff/Pyright; frontend tests/TypeScript/ESLint/build; PowerShell AST;
`git diff --check`; secret/privacy audit.

- [x] Demo 1 tag/baseline exist without rehearsal-state changes.
- [x] Automation is explicit, bounded, default-off, and uses the existing profile.
- [x] Deterministic coverage proves automatic media progress, later-Session reevaluation,
  protected human/conflict authority, and no duplicate assets or Operations.
- [x] Program refresh is failure-safe, reconstructable, manual-compatible, and no-PUT.
- [x] Deterministic coverage proves one coordinator owner and bounded stop/restart.
- [x] Worker current/available/degraded/absent/stale is truthfully projected.
- [x] Package Ready, exact-revision approval, and publication remain separate.
- [x] Full automated validation/privacy review completed. The previously observed
  full-suite-only Windows loopback issue did not reproduce in the final run.
- [ ] Fresh two-machine rehearsal passes before recommending Demo 2.

Rollback: disable automation or run the tagged Demo 1 commit/config; revert additive
code. No data/schema reversal. Live qualification and SMB/vMix remain external.

## Completion record

- Implemented revision: Uncommitted by directive on `codex/demo2-autonomous-event-node`.
- Files/migrations: Bounded backend/frontend/launcher/tests/docs/config example; no migration.
- Commands/results: Final focused Demo 2/API/controller/lifecycle tests 38 passed;
  full backend 1798 passed/5 skipped. The previously observed full-suite-only
  Windows Devcon loopback failure did not reproduce. Ruff/Pyright pass; frontend 54
  tests/TypeScript/ESLint/build pass; PowerShell AST and diff check pass; privacy
  audit passes.
- Warnings/deviations: npm reports 11 existing audit findings and two blocked install
  scripts. An older launcher-owned Demo 1 stack occupied the fixed ports; it was stopped
  without changing durable evidence. The launcher status path was made tolerant of an
  older payload that omits automation fields.
- Authority: Green under the explicit 2026-08-20 Demo 2 directive and association-
  lifecycle decision. Human, conflict, Session, Moment, package, and publication
  authority remain protected.
- Hardware checkpoint: Read-only Razer diagnosis passed. A fresh external non-secret
  config and empty recordings directory were created; fresh Event
  `ad062a10-4850-419b-b1a7-d601e223ce03`, Stage
  `54d6bd8f-8783-465f-b73d-6199f9f76d70`, and three Program items were prepared.
  No Session, media, Operation, evidence, Moment, package, or Devcon PUT was created.
- Rollback: Demo 1 local tag and durable rehearsal data remain preserved. Automation is
  default-off and can be disabled; code remains uncommitted.
- Remaining work: Producer supplies an attributable operator UUID and selects one of the
  three Program Expectations, then complete the two-machine media/restart story and the
  candidate/PR decision. SMB/vMix was not attempted.