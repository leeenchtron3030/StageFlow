# Demo Package Approval

## Status

Completed

## Execution authority

- Classification: Green, explicitly authorized by the 2026-08-19 Demo lifecycle directive.
- Authority evidence: ADR-0023's attributable human completion decision for one exact package
  revision, the existing Durable Kernel `complete_package` transaction, and the accepted Demo
  launch-context authority boundary.
- Implementation-ready: Yes.
- Escalation boundary: lifecycle meanings, package revision policy, Devcon publication,
  authentication/trust architecture, schemas, migrations, or automatic approval remain out of
  scope.

## Problem statement

The Kernel already owns durable, idempotent package completion approval, but the bounded Demo API
and Producer UI expose only the machine/human transition into `ready_for_review`. The Producer
cannot explicitly approve the exact current package revision without leaving the guarded Demo
surface.

## Desired behavior

For a `presentation_ended` Session whose package is `ready_for_review`, the Producer can review a
bounded package summary, confirm an attributable decision for the exact current package revision,
and submit it through the launch-scoped proxy to the existing Kernel completion transaction.
Approval remains separate from Devcon publication and creates no external write.

## In scope

- One Demo API command that calls existing Kernel approval semantics with an expected package
  revision.
- One launch-context-protected Producer proxy path and explicit confirmation control.
- Bounded confirmation details for Session title, media disposition, transcription outcomes,
  Transcript Evidence, and declared Moments.
- Backend, frontend, proxy, controller-gate, replay/conflict, and live read-only qualification.

## Out of scope

- New lifecycle states or authority semantics, rejection UX, automatic approval, Devcon PUT,
  package publication, schemas, migrations, dependencies, and unrelated worker reporting.

## Acceptance criteria

- [x] Approval is available only for `presentation_ended` and `ready_for_review`.
- [x] The exact expected package revision reaches the existing durable completion transaction.
- [x] Operator UUID, current launch context, explicit confirmation, and durable operation identity
  remain mandatory.
- [x] Missing/stale launch context and declined confirmation send no backend approval command.
- [x] Identical operation replay is idempotent; conflicting operation reuse fails safely.
- [x] Approval performs no Devcon PUT and publication remains separately gated on completion.
- [x] No automated test or qualification approves the live rehearsal Session.
- [x] The same live Event remains running at package revision 1, `ready_for_review`, unapproved.

## Rollback

Revert the Demo route, optional expected-revision service seam, proxy path, frontend helper/control,
tests, styles if any, and this plan. Preserve all durable Demo state.

## Completion record

- Implemented revision: bounded working-tree milestone on `codex/demo-package-approval`; no
  schema, migration, dependency, lifecycle, Devcon contract, or automatic-authority change.
- Validation: frontend 46 tests, TypeScript, ESLint, and Next production build passed; focused
  backend 13 tests passed; full backend 1,766 tests passed with 5 existing environment-dependent
  skips; full Ruff and Pyright passed; `git diff --check` passed.
- Live rehearsal result: the same Event was relaunched with its existing configuration and a new
  process-scoped launch context. Read-only controller and workspace projections confirmed Session
  `3356fcf7-7907-42c4-bac1-3301927616cd` remains `presentation_ended`, package
  `ready_for_review`, revision 1, unapproved, with one succeeded transcription Operation, one
  complete Transcript Evidence revision, and one declared Moment. The Producer page returned 200
  and rendered the Approve Package control. Sanitized launcher logs contained zero approval POSTs
  and zero actual Devcon PUT method records.
- Warnings and remaining work: the human Approve Package click remains intentionally pending.
  Windows PowerShell 5 cannot execute the launcher's existing
  `RandomNumberGenerator.Fill` call; the same Event relaunched successfully under the repository's
  PowerShell 7 runtime. The pre-existing `frontend/next-env.d.ts` modification remains preserved
  and outside this milestone.
