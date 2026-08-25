# Demo 2 Autonomous Event Node — automated validation and hardware checkpoint

Date: 2026-08-20–21 Pacific
Branch/worktree: `codex/demo2-autonomous-event-node` / isolated clean worktree
Baseline: `504b32567cf856082642697b6974859290c65020`
Disposition: **PARTIAL — not live-qualified; Demo 1 remains the presentation fallback**

## Validated implementation

- Default-off `demo-single-stage` automation configuration parses with 5-second media
  and 120-second Program defaults and appears in the redacted configuration summary.
- The lifespan-owned non-daemon coordinator starts once, bounds stop join to 30 seconds,
  uses one PostgreSQL session advisory owner per deployment, and reconstructs last
  successful media/Program freshness from durable projections.
- Automatic and manual media triggers use one application service and stable
  deployment/Event/Session/asset/manifest/profile Operation identity. Stable and later
  stable files register through the existing bounded media cycle; replay/restart/manual
  use does not duplicate assets or Operations in deterministic coverage.
- Per-asset enqueue failure is isolated; a later asset and later cycle continue.
- Under the explicit 2026-08-20 lifecycle decision, a deterministic unresolved
  association is reevaluated only when the material Session identity/revision input set
  changes. Unchanged inputs create no revision; human and conflict authority is never
  replaced. Restart, no-op, later-safe, human-protection, and conflict-protection tests
  pass.
- Program success, identical replay, changed revision, provider failure, cached snapshot,
  realized Session preservation, manual compatibility, and restart freshness pass.
- Worker status scopes to the current deployment and Event and reports node,
  currentness, health, availability, capacity, and faster-whisper readiness.
- Package approval is separate from Package Ready and publication, requires explicit
  confirmation and exact package revision, is attributable, and performs no Devcon PUT.
- Producer/proxy/launcher projections are bounded and contain no path, DSN, credential,
  launch-context, transcript-content, or provider-payload values.

## Commands and results

- Final Demo 2/API/controller/lifecycle focus: **38 passed**.
- Final full backend suite: **1798 passed, 5 skipped**.
- The previously observed full-suite-only Windows loopback failure in
  `test_devcon_no_body_response_maps_to_bounded_reason_without_retry` did not reproduce
  in the final pre-commit run. It remains recorded as historical environmental or
  order/resource-sensitive behavior; no validation was weakened or skipped.
- Full Ruff: **passed**.
- Full Pyright: **passed, 0 errors/warnings**.
- Frontend tests: **54 passed**.
- TypeScript: **passed**.
- ESLint: **passed**.
- Next production build: **passed**.
- PowerShell AST: **passed**. The final launcher compatibility edit was re-parsed and its
  focused controller-script tests passed **10/10** with focused Ruff passing.
- `git diff --check`: **passed** (Git emitted line-ending conversion warnings only).
- Bounded changed-file privacy/secret audit: **passed**; matches were only secret names,
  field names, redaction assertions, and synthetic `.invalid`/memory-test sentinels.
- Migrations: **not run; no schema, migration, or SQL file changed**.

`npm ci` used the existing lockfile and reported 11 audit findings (2 moderate, 9 high)
plus two install scripts blocked by npm policy (`sharp`, `unrs-resolver`). No dependency,
lockfile, or install-script policy was changed.

## Initial Razer hardware checkpoint

The guarded read-only `diagnose` action passed against the external Demo environment:
exact Demo database identity available; CUDA GPU/faster-whisper 1.2.1
large-v3-turbo float16 silent inference available at model revision
`0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf`; configured media source available; and
Devcon GET available with three bounded Program items.

A fresh non-secret configuration and empty recordings directory were created outside the
repository for Event key `demo2-autonomous-20260820-codex` and deployment
`razer-demo2-20260820-codex`. Guarded `prepare` verified the database and CUDA/Devcon
preflight, then durably created Event `ad062a10-4850-419b-b1a7-d601e223ce03`, Stage
`54d6bd8f-8783-465f-b73d-6199f9f76d70`, and reconciled three Program items.

An older launcher-owned completed Demo 1 process held ports 8000/3000. It was identified
from its recorded launcher state and stopped cleanly; its database, Event, Session,
evidence, reports, and external configuration were not deleted or rewritten. The fresh
Demo 2 stack is stopped. No Session, media, Operation, Transcript Evidence, Moment,
package action, or Devcon PUT occurred in the fresh Event.

The next live step requires the Producer's attributable operator UUID and selection of
one of the three External Program Expectations. The launcher deliberately cannot infer
an actor for a fresh Event with no Session. The two-machine acceptance story and durable
restart reconstruction therefore remain unqualified. The optional SMB/vMix stretch goal
was not attempted.

Demo 2 is not yet recommended as the presentation candidate. Demo 1 remains the safer
choice until the explicit Producer inputs are supplied and the complete two-machine dress
rehearsal passes.