# Demo launch-scoped authority context

## Status

Completed

## Execution authority

- Classification: Green, explicitly authorized by the 2026-08-19 Demo safety directive.
- Authority evidence: the completed Demo rehearsal controller and hardware rehearsal plans,
  accepted Demo LAN/proxy boundary, durable human-command semantics, and the explicit instruction
  to protect authority requests from stale launcher contexts.
- Implementation-ready: Yes.
- Escalation boundary: Session, Kernel, idempotency, operator, LAN trust, or durable authority
  semantic changes remain out of scope.

## Problem statement

A Producer-proxy Session-start POST reached a newly launched rehearsal after it had been verified
with zero Sessions. The controller and background worker do not issue that command; the authority
surface is the explicit UI/API/proxy path. A stale browser page must not be able to send authority
commands into a later launcher instance.

## Desired behavior

Each launcher instance creates a cryptographically random, process-only context. Current pages
embed it into authority controls; mutating proxy requests must present it. Missing or stale values
fail before loopback forwarding. GET projections are unchanged. Attribution contains only a
fingerprint, time, path, bounded request identity, client address, and validation result.

## In scope

- Process-scoped launcher context generation and cleanup.
- Server-rendered context propagation to existing Demo authority controls.
- Proxy validation, header stripping, and bounded fingerprint-only attribution.
- Current/stale/missing/GET/controller-safety and existing authority-semantic tests.
- Second fresh, non-destructive hardware rehearsal after validation.

## Out of scope

- New authority commands, authentication architecture, public APIs, backend changes, Session
  compensation, Devcon writes, migrations, dependencies, cleanup, or production deployment.

## Acceptance criteria

- [x] Every launcher start receives a fresh cryptographically random context that is never printed.
- [x] Current pages can send confirmed authority commands; stale/missing contexts fail closed.
- [x] The proxy never forwards the context to the loopback backend.
- [x] GET/read projections remain compatible.
- [x] Attribution is bounded and contains no body, credential, transcript, DSN, or raw capability.
- [x] Controller lifecycle actions contain no Session-start execution path.
- [x] Successful explicit Session start remains declared with reason `human_session_start`.
- [x] Focused/full frontend and backend validation passes.
- [x] A second unique Event is CUDA-qualified, Devcon-synchronized, durably zero-Session, and left
  running without any Devcon PUT.

## Rollback

Stop only the controller-owned stack and revert code. Preserve all Demo database, media, Session,
Operation, evidence, Moment, report, and external runtime state.

## Completion record

- Implemented revision: focused milestone commit on `codex/demo-launch-authority-context`; transport,
  UI, launcher, regression tests, runbook, and this plan only.
- Validation: frontend tests, TypeScript, ESLint, and production build passed; backend focused and
  full suites passed (1,765 passed, 5 skipped), Ruff and Pyright passed; PowerShell AST parse and
  `git diff --check` passed.
- Live rehearsal result: Event `stageflow-demo-rehearsal-20260819-105034-3c01fbb0`
  (`b6e82950-df21-4d9b-859f-1103c10ef433`), Stage
  `22da8abc-5e2c-42b7-b6a1-8417dcd7a371`, deployment
  `razer-demo-20260819-105034-3c01fbb0`; real CUDA inference and Devcon GET passed with four
  synchronized expectations. Missing/stale launch contexts both returned 403 before forwarding.
  Durable read-back found zero Sessions, zero Session-start operations, and one current available
  worker. The empty recordings source and Producer UI remain running; no Session start or Devcon
  PUT was issued.
- Warnings and remaining work: the controller's human-readable worker summary reports
  `not_current` because the Kernel status payload has no deployment ID; a bounded direct read-only
  query confirms the new deployment worker is current and available. This pre-existing reporting
  limitation was not expanded into the scoped transport safety fix.
