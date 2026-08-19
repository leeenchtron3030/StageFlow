# Demo rehearsal controller

## Status

Completed

## Execution authority

- Classification: Explicit approval granted for the bounded Devcon publish boundary; Green
  autonomous for the remaining controller work.
- Authority evidence: the explicit 2026-08-19 controller request and revised lifecycle; the
  completed Demo Single-Stage Vertical Slice; the Demo hardware rehearsal; ADR-0004/0005 and
  ADR-0022 through ADR-0025/0027; and the Product Constitution.
- Implementation-ready: Yes.
- Required approval: every real Devcon PUT still requires the controller's explicit human
  confirmation. Automatic/production publish, broader fields, cleanup, schema, authority, or trust
  changes require separate approval.

## Related findings or ADRs

- Finding: manual environment, DSN, UUID, URL, CUDA, and diagnostic plumbing caused an actual
  wrong-database rehearsal launch.
- ADR: external ownership/adapters, PostgreSQL authority, Session/package authority, durable Kernel
  and work, and advisory evidence boundaries listed above.
- Other authority: the user's exact Demo-only publish gates and existing launcher/application logic.

## Problem statement

The real Demo works, but operators must manually import secrets, distinguish Demo and qualification
DSNs, copy UUIDs, construct URLs, configure CUDA PATH, and query PostgreSQL. A guarded controller is
needed to make the approved rehearsal repeatable without changing product semantics.

## Verified current behavior

- `Start-StageFlowDemo.ps1` already owns real CUDA preflight, bootstrap, Devcon GET sync, loopback
  backend/worker, and LAN frontend startup, but requires explicit plumbing and one attached terminal.
- `app.demo.cli` does not reject a wrong database identity before bootstrap/sync writes.
- The Demo DSN resolves to exact database `stageflow_demo`; schema presence cannot distinguish the
  known qualification database.
- Existing Kernel/workspace APIs expose bounded state but workspace transcript text must never be
  copied into normal logs or reports.
- The official Devcon API documents Session GET and API-key PUT. The named test Session GET exposes
  `transcript_text` and `duration`; only those fields are approved here.

## Desired behavior

`scripts/demo/StageFlow-Demo.ps1` provides `prepare`, `start`, `status`, `diagnose`, `stop`,
`rehearsal-report`, and `publish-devcon`. It imports named User-scope values, discovers the bounded
config/CUDA runtime, rejects every database except `stageflow_demo`, wraps existing logic, resolves
current IDs, emits sanitized state, and has no destructive action. Publish requires package
`complete`, remote identity verification, credential presence, digest-bound confirmation, one PUT,
GET read-back, and a second GET durability check; it never follows Session end automatically.

## In scope

- Thin PowerShell lifecycle wrapper and controller-owned process stop.
- Same-process database guard before controller bootstrap and Devcon cache writes.
- Loopback API summaries, unambiguous Session discovery, sanitized reports.
- Demo-only exactly-two-field Devcon publish workflow with explicit confirmation and read-backs.
- Focused tests and runbook/plan documentation.

## Out of scope

- Automatic/generic/production publishing, UI or LAN changes, new public backend endpoints,
  authority/idempotency changes, database provisioning/migration/cleanup, media deletion, and
  authoritative-Transcript claims.

## Constraints

- Devcon remains external authority; Program Expectations remain External; Transcript Evidence is
  evidence; package `complete` is the publication approval gate.
- Existing launcher invocation remains compatible; additions are optional.
- Devcon network work remains explicit; local Event work remains offline-capable after sync.
- Never emit DSNs, credentials, tokens, transcript text, media paths, raw diagnostics, or PUT bodies.
  Backend stays loopback-only and the frontend's trusted-LAN boundary is unchanged.

## Implementation approach

1. Add testable guards, Session selection, API summarization, report sanitization, candidate
   derivation, and Devcon transport behind existing infrastructure boundaries.
2. Run exact database verification and existing preflight/bootstrap/sync in one controller process.
3. Add the thin PowerShell controller around the existing launcher and APIs.
4. Bind confirmation to the exact candidate digest and verify two remote read-backs.
5. Run focused/full validation and deliberate privacy/diff review.

## Files or modules expected to change

| Path | Expected change |
| --- | --- |
| `backend/app/demo/controller.py` | Guards, discovery, summaries/reports, publish workflow |
| `backend/app/infrastructure/devcon` | Narrow authenticated Session GET/PUT adapter |
| `scripts/demo/StageFlow-Demo.ps1` | Guarded operator lifecycle |
| `backend/tests/`, `scripts/demo/README.md` | Regressions and runbook |

## Data or migration considerations

No schema or migration. Existing Demo state is preserved. `prepare` uses only existing idempotent
bootstrap/Program sync after the exact database guard. External PID/report artifacts are
non-authoritative and contain no secrets or transcript text. No cleanup command is added.

## Failure and recovery considerations

- Missing values report presence/name only; wrong/test/qualification identities fail before writes.
- No Session is safe; multiple plausible Sessions fail rather than guess.
- Start refuses occupied/live state. Stop targets only the recorded launcher process tree and never
  an unverified process.
- Publish recomputes the confirmed digest, never retries PUT automatically, and does not claim
  durability unless both GET read-backs match.

## Observability requirements

Summaries cover Event/Stage/Session, package, media, work/worker, terminal failures, successful
evidence/provenance, Moments, Devcon cache/identity, and launcher liveness without sensitive content.

## Test strategy

- Wrong database; presence-only secrets; Session/no-Session/ambiguity; terminal failure/evidence;
  confirmation/digest/identity/read-back; and no-leak unit tests.
- PowerShell contracts for User DSN, CUDA inheritance, action set, owned stop, confirmation, and no
  global environment mutation.
- Focused/full pytest, Ruff, Pyright, PowerShell AST parsing, and `git diff --check`.

## Acceptance criteria

- [x] Requested actions avoid UUID/URL copy-paste and wrap existing logic.
- [x] Exact Demo DB is checked before writes; test/qualification DBs fail closed.
- [x] Config/CUDA/User secret discovery is bounded and never emits values.
- [x] Status/report handle zero, one, and ambiguous Sessions safely.
- [x] Required operational state is summarized without content/secret leakage.
- [x] Publish is manual, package-approved, identity-checked, digest-bound, read back, and durability
  verified.
- [x] No dependency, schema, migration, cleanup, authority bypass, or trust expansion is introduced.
- [x] Focused/full validation passes and existing Demo state remains preserved.

## Rollback or reversal

Stop only controller-owned processes and revert code. Do not alter Demo data/media or remote Devcon
state as rollback. A real PUT is not part of implementation validation.

## Open questions

- None. Real Devcon PUT execution remains a separate explicit operator decision.

## Completion record

- Implemented revision: 2026-08-19 working-tree implementation on
  `codex/demo-rehearsal-controller`.
- Files and migrations actually changed: the controller/Devcon adapter, PowerShell wrapper,
  focused tests, operator runbook, plan index, and bounded hardware-plan clarification. No
  migration or schema changed. The pre-existing `frontend/next-env.d.ts` modification remains
  preserved and excluded from this milestone's scope.
- Commands and tests actually run:
  - focused controller/adapter/launcher pytest, Ruff, Pyright, and PowerShell AST parsing;
  - full backend pytest, Ruff, and Pyright; frontend production build, ESLint, and
    TypeScript;
  - real `diagnose`, `prepare`, `start`, `status`, `rehearsal-report`, and `stop`;
  - owned-port shutdown, report privacy, secret-pattern, whitespace, and diff audits.
- Results and warnings: 27 focused tests passed; 1,762 full tests passed and 5 skipped; Ruff,
  Pyright, AST parsing, frontend production build, ESLint, and TypeScript passed. Real CUDA
  inference preflight and the complete guarded lifecycle passed. The sole pytest warning is the
  existing Starlette TestClient/httpx deprecation. No real Devcon PUT ran.
- Execution authority used: the explicit bounded Devcon publish decision and Green-autonomous
  Demo ergonomics directive.
- Approved deviations: none.
- Rollback status: the controller-owned stack was stopped and ports 8000/3000 were verified
  closed. Existing Demo database/media state was preserved; no cleanup ran.
- Remaining work: a real `publish-devcon` remains a separate run-time operator action requiring
  package approval and explicit human confirmation. Commit/publication was not requested.

## 2026-08-19 post-completion verification correction

The original controller milestone intentionally recorded its then-implemented two-immediate-GET
model. Live publication evidence later proved that model incorrect for Devcon: the guarded PUT
returned 204 and upstream Git persistence succeeded, while cached public GET remained stale. The
historical completion record above is preserved rather than rewritten.

The bounded correction is tracked in
[Demo Devcon Post-Publish Verification Correction](demo-devcon-post-publish-verification.md).
Git-backed exact-file state now owns durability verification; public GET is bounded convergence
evidence only. A stale GET after matching durable state is not publication failure and never causes
another PUT.
