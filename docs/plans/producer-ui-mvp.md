# Producer operational UI MVP

## Status

Completed

## Execution authority

- **Classification:** Green autonomous
- **Authority evidence:** Operator-authorized Autonomous UX Implementation Workstream;
  Product Constitution principles 2, 7, 8, 10, 11, 17, and 18; existing Producer,
  Mission Control, shared-state, visual-system, connected-wireframe, and Event-day scenario
  specifications; accepted Session lifecycle and Durable Event-Mode Kernel architecture;
  Run 002 through Run 004 sanitized validation evidence; root bounded-autonomy policy.
- **Implementation-ready:** Yes
- **Required escalation or approval:** None for the reversible frontend presentation,
  fixture, read-only status adapter, tests, and local-preview work. New authority APIs,
  lifecycle/Attention semantics, role permissions, or consequential dependencies remain
  Yellow and are excluded.

## Related findings or ADRs

- **Finding/disposition:** Run 002 validates distinct Presentation End and Package
  Assembling; Run 003 validates conservative no-Session authority; Run 004 validates
  preserved unresolved turnover media without production failure.
- **ADR:** ADR-0021 time authority, ADR-0023 Session/media authority, ADR-0024 conservative
  association. Proposed ADR-0025/ADR-0026 are not accepted or required for this MVP.
- **Other authority:** Existing `GET /api/v1/kernel/status` is the implemented bounded,
  read-only Producer status boundary. The UX workstream explicitly authorizes the first
  runnable Producer milestone and minimum Editorial shell.

## Problem statement

The repository has a static Next.js foundation and extensive UX specifications, but no
runnable Producer workflow. Operators cannot leave StageFlow open during qualification,
compare realistic Event states, or exercise the existing Kernel projection through a
role-appropriate interface.

## Verified current behavior

- Frontend uses npm, Next.js 16, React 19, TypeScript, Tailwind CSS 4, and a committed
  `package-lock.json`; no frontend test runner or backend communication is configured.
- The shell initially displays only release metadata on `/`.
- The FastAPI backend exposes liveness and a bounded read-only Kernel status projection at
  `/api/v1/kernel/status`, including Event, Stage, Session/package, media counts,
  dependencies, reconciliation, provenance, recent media, proposals, and attention codes.
- No HTTP authority-command surface exists. The UI must not present fixture state as
  durable truth or add frontend-owned authority.
- Node/npm were absent from shell `PATH`; the Codex bundled Node 24 runtime plus npm 11 can
  execute the repository's npm-lockfile workflow.
- The working tree contains substantial unrelated and earlier user work, which remains
  preserved.

## Desired behavior

A locally runnable dark operational UI provides Mission Control, Event, Sessions,
Infrastructure, Stage/Session drill-down, and a minimum Editorial shell. It uses stable
Stage-oriented layouts, a bounded consequence-first Attention surface, realistic labeled
fixtures, and an adapter for actual Kernel status. Fixture and Kernel modes cannot be
confused.

## In scope

- Operational application shell and responsive navigation.
- Producer Mission Control, Event, Sessions, Infrastructure, Stage detail, and Session
  detail routes.
- Development fixtures for requested scenarios A through G plus sanitized Run 002/003/004
  reference states.
- Pure presentation adapter for the existing Kernel status JSON.
- Minimum Editorial shell with clearly labeled development Candidate data.
- Node-native focused unit tests, frontend build/lint/typecheck, and local preview docs.

## Out of scope

- Backend commands, new public/domain contracts, authentication/permissions, database or
  schema changes, continuous polling, production orchestration, transcription/workers,
  real AI outputs, association resolution, Package approval, media playback/editing,
  Marketing, or high-fidelity lock-in.
- Changing Session, Package, Attention, media association, or automation semantics.

## Constraints

- **Architecture and terminology:** Stage is the primary Producer unit; Event is global.
  Health, Impact, and Attention remain separate. Session activity, Package state, and
  media state remain separate. Proposed/external/inferred facts never appear authoritative.
- **Compatibility:** Consume the current read-only HTTP response through a local adapter;
  do not make components depend directly on raw backend JSON.
- **Offline/Event Mode:** Fixture mode is local. Kernel mode calls one explicitly configured
  local status URL and communicates cloud deferral as degraded capability, not Event failure.
- **Security/data handling:** No credentials, source paths, DSNs, raw run artifacts, media,
  or sensitive content. Fixture labels and source-mode treatment are always visible.

## Implementation approach

1. Define a compact provider-neutral presentation model and behavior functions.
2. Add requested fixtures plus sanitized Run evidence scenarios behind a development-only
   query selector.
3. Adapt the existing Kernel status response server-side with no policy duplication and
   explicit unavailable/stale behavior.
4. Build the shared shell and Producer routes with stable operational geometry, bounded
   Attention, dense rows, consequence-first infrastructure, and drill-down.
5. Add a minimum Editorial shell using explicitly synthetic development content.
6. Add Node-native tests for operational presentation behavior and authority gating.
7. Document npm/bundled-Node prerequisites, fixture mode, Kernel mode, and limitations.
8. Build, lint, typecheck, test, run locally, inspect key scenarios, and capture screenshots.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `frontend/app/` | Shell and operational routes |
| `frontend/src/experience/` | View model, fixtures, Kernel adapter, behavior tests |
| `frontend/src/components/` | Shared Producer/Editorial operational components |
| `frontend/package.json` | Node-native test script only |
| `frontend/README.md` | Local launch and data-mode workflow |
| `docs/plans/README.md` | Plan index |

## Data or migration considerations

None. No database, durable state, public serialization, media, Run artifact, schema, or
migration changes. Query-selected fixtures are frontend development artifacts only.

## Failure and recovery considerations

- Kernel fetch failure produces an explicit unavailable/stale presentation and never
  silently falls back to authoritative-looking fixture data.
- Fixture mode is visually labeled in the shell and scenario controls.
- Kernel status remains server-read-only; authoritative controls remain unavailable.
- Major layout regions remain stable as Attention changes.
- Removal of the isolated frontend routes/components/model restores the prior shell.

## Observability requirements

Operators can identify Event, data source/mode, last status update, readiness/recovery,
Stage source/media/Session state, Attention level, safe continuation, and requested human
action. Developers can identify the active fixture or Kernel endpoint configuration
without exposing secrets or paths.

## Test strategy

- Node-native unit tests for quiet-state Attention, unresolved Review, stabilizing quiet,
  split Presentation/Package visibility, completed-session prominence, infrastructure
  consequence, fixture labeling, and authority-action gating.
- npm install integrity, focused tests, lint, TypeScript, production build.
- Local server HTTP and visual inspection across quiet, turnover, source unavailable,
  cloud unavailable, Run 003, and Run 004 scenarios.
- Documentation UTF-8/link checks and `git diff --check`.

## Acceptance criteria

- [x] Mission Control answers the six Producer glance questions with fixed Stage ordering.
- [x] Healthy/transient states remain quiet; unresolved turnover is Review; source loss is
  consequence-first Intervention; cloud loss preserves local-operational clarity.
- [x] Presentation, media, and Package meanings remain independently visible.
- [x] Fixtures cover scenarios A through G and sanitized Run 002/003/004 evidence.
- [x] Fixture and Kernel modes cannot be confused.
- [x] Existing Kernel status can render through a presentation adapter without backend
  policy duplication.
- [x] Event, Sessions, Infrastructure, Stage/Session detail, and minimum Editorial routes
  are meaningfully testable.
- [x] No unsupported authority action appears enabled.
- [x] Focused tests, lint, typecheck, build, documentation checks, and local preview pass.

## Rollback or reversal

Remove the isolated frontend experience/components/routes, revert the root shell/styles and
test script/docs/index entry, and run the frontend checks. No durable data or configuration
needs reversal.

## Open questions

- Operational-review questions about Editorial staffing, Producer-mark priority,
  near-live target, Producer intelligence density, and Event closeout remain inputs for
  later fidelity tuning; they do not block this testable MVP.
- Adding HTTP authority commands remains a separate Yellow/public-contract decision.

## Completion record

- **Implemented revision:** Uncommitted work based on `74f23b4`; unrelated pre-existing
  worktree changes were preserved.
- **Files and migrations actually changed:** Frontend operational routes, shell/views,
  presentation model, fixtures, Kernel adapter, behavior tests, styles/tokens, package
  scripts, and launch/testing documentation; Producer plan/index, UX index, project brief,
  scripts guide, and existing HTTP API documentation. No schema or migration changed.
- **Commands and tests actually run:** Locked `npm ci`; `npm test`; `npm run lint`;
  `npm run typecheck`; `npm run build`; local fixture and Kernel-mode servers; direct
  Kernel HTTP request; desktop-browser scenario/responsive/disabled-action qualification;
  affected-document UTF-8/relative-link validation; `git diff --check`.
- **Results and warnings:** All 11 behavior tests passed; lint, strict TypeScript, and the
  Next.js production build passed; all seven operational routes rendered; documentation
  validation and whitespace check passed. Browser qualification passed at desktop and
  narrow responsive widths across quiet, turnover, source-unavailable, completed,
  Editorial, and real unconfigured-Kernel states. `npm ci` restored 587 locked packages
  and reported 12 audit findings (3 moderate, 9 high) plus two install-script approval
  notices; no automatic audit fix or dependency upgrade was performed.
- **Execution authority used:** Green autonomous UX workstream.
- **Approved deviations:** None.
- **Rollback status:** Reversible frontend-only change.
- **Remaining work:** Operator calibration questions in Open questions; command APIs,
  authentication, continuous refresh, real Editorial runtime, and Marketing remain
  separately governed future work.
