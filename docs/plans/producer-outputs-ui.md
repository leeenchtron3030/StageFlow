# Producer outputs UI: Assembly, render, and derived Editorial review

## Status

Approved. The owner accepted decision D1, option A, on 2026-09-27.

## Execution authority

- Classification: Green. D1 is a bounded extension of an existing trust boundary, and the
  owner accepted it (option A) on 2026-09-27.
- Authority evidence:
  - The owner asked on 2026-09-27 to plan a Producer UI for the backend capabilities
    delivered in ED-0087 to ED-0092.
  - The Green Producer operational UI MVP (`docs/plans/producer-ui-mvp.md`) and its
    Demo command proxy.
  - The UX specifications (Draft v0.1) are calibration inputs, not authority:
    `docs/ux/session-assembly-approval-automation.md`,
    `docs/ux/editorial-event-queue-live-triage.md`,
    `docs/ux/shared-state-component-language.md`, and
    `docs/ux/visual-design-system-interaction-density.md`.
  - The backend routes already exist and are authenticated: ED-0077, ED-0086, ED-0087,
    ED-0072, ED-0092, and ED-0090.
- Implementation-ready: Yes.
- Required escalation: stop if a phase would:
  - expose the API secret to the browser;
  - allow a browser-chosen backend path outside the allowlist;
  - add automatic approval, render, derivation, or review;
  - add a production dependency;
  - add a backend route or change backend semantics. This plan is frontend-only, apart
    from a strictly additive read that the backend lacks, which must be listed and
    stopped for.

## Problem statement

Everything delivered from ED-0087 to ED-0092 is usable only through the backend API and
scripts:
- Assembly proposal and approval;
- render requests and Rendered Outputs;
- media timing evidence;
- phrase lists, derivation runs, and derived candidates;
- Editorial review (ED-0072), which also has no UI.

The frontend's Editorial page is a fixture placeholder ("No Editorial runtime connected").
A producer cannot use any of it.

## Verified current behavior

- `frontend/app/api/stageflow/demo/[...path]/route.ts` is the only path from browser to
  backend:
  - it forwards only to `/api/v1/demo/*` on a loopback HTTP backend;
  - a fixed set of six command paths plus one workspace read;
  - same-origin checks, a launch-context header match, and a 32 KiB command cap;
  - the API secret is attached on the server, and responses are `no-store`.
- `frontend/src/experience/data-source.ts` reads the Kernel status on the server (React
  Server Components), with the secret held on the server.
- `frontend/app/editorial/page.tsx` renders `EditorialShellView` over fixture data.
- `frontend/src/experience/demo-api.ts`: `DemoMoment` assumes `origin: "declared"` and a
  non-null `operation_id`, which is wrong for ED-0092 derived candidates.
- Backend routes, all authenticated with the shared secret:
  - **Assembly:** templates, revisions (list and propose), approvals, metadata overrides,
    and Packaging Assets (`/api/v1/assembly/...`);
  - **rendering:** `POST /requests`, `GET /operations`, `GET /outputs`;
  - **Editorial:** `POST /moments/{id}/reviews`, `GET /sessions/{id}/moments`,
    `GET /events/{id}/review-queue`, phrase lists (`POST`/`GET`), and
    `POST /sessions/{id}/derivations`;
  - **media timing:** `GET /events/{id}/operations` and `GET /assets/{id}/latest`.

## Decision (accepted: option A, owner, 2026-09-27)

**D1. Extend the browser-to-backend path beyond `/api/v1/demo/*`.**

- **Option A (recommended): one new server-side route per capability**, for example
  `app/api/stageflow/assembly/[...path]`, `.../rendering/...`, and `.../editorial/...`.
  - Each reuses the Demo proxy's exact protections: loopback backend, secret held on the
    server, same-origin, launch-context match, byte caps, and `no-store`.
  - Each route has its own explicit **method + path-pattern allowlist**, listing each
    route above by regular expression. There are no pass-through wildcards.
  - The shared protection code is extracted into one server-only module, so the Demo
    proxy's behaviour is unchanged and proven by its existing tests.
- **Option B: server actions or React Server Component reads only,** with no new route
  handlers. This gives a smaller surface, but mutations would diverge from the
  established Demo command pattern and its tests.
- **Option C: widen the Demo proxy's allowlist.** This mixes Demo-only authority with
  general Producer capabilities, and blurs a boundary that is Demo-scoped today.

The recommendation is A. It keeps one trust model and adds explicit per-route
allowlists, and every command stays a human-attributed command using the server-side
operator identity (`STAGEFLOW_DEMO_OPERATOR_ID`), as the Demo commands already do.

## Phases (one Engineering Directive each)

### Phase 1: ED-0093, the access foundation and read-only Session outputs

1. The D1 routes, a shared server-only protection module, and typed client modules
   (`frontend/src/experience/assembly-api.ts`, `rendering-api.ts`, and
   `editorial-api.ts`) with zod response schemas.
2. Fix the `DemoMoment` type (origin union, nullable `operation_id`, optional provenance).
3. An **"Outputs" panel** on `/sessions/[sessionId]` (Session Detail), read-only, with:
   - **Assembly:** the current revision's number, validation (with issue codes),
     approval state, and staleness. Each member shows its order position, ordering
     source (`media_timing`, `timing_evidence`, or `registration_time`), and timing
     qualification badge, so "unqualified recorder timing" is visible before anyone
     approves. The slot bindings are also shown.
   - **Render:** operations (state and attempts) and Rendered Outputs (profile version,
     duration, frame count, SHA-256 prefix, produced time). There are no paths and no
     playback.
   - **Media timing:** a per-asset summary of the candidate start, qualification, and
     evidence revision.
4. Tests:
   - proxy protection tests for each new route: method/path allowlist, cross-site
     refusal, launch-context mismatch, size caps, and no secret in the response;
   - schema parsing tests;
   - presentation tests for ordering-source and qualification labels;
   - the Demo proxy tests stay unchanged.

### Phase 2: ED-0094, Assembly and render actions

1. **Propose revision:** choose a template, confirm, and include the expected revision.
2. **Approve or reject revision:** a required reason, and a confirmation that states what
   is being approved. When any member is ordered by `registration_time` or unqualified
   `timing_evidence`, that is stated explicitly. Includes the expected revision and
   decision count.
3. **Request render:** only for an approved, non-stale revision; confirmation; default
   profile v2.
4. Every command:
   - uses a client-generated UUID v4 command ID, so retries are idempotent;
   - shows bounded error codes;
   - never retries optimistically on a conflict, and refreshes instead.
5. Tests: command construction, confirmation gating, conflict handling, and each route's
   allowlist.

### Phase 3: ED-0095, connecting the Editorial review surface

1. Connect `/editorial` to the real runtime when the data mode is `kernel`. The fixture
   mode stays for development.
2. **Review queue:** the Event-scoped queue from ED-0072, with pagination. Each candidate
   shows its origin (`declared` or `derived`) and provenance: the phrase, the timing
   qualification, and the transcript and evidence revisions. Transcript text is shown
   only as the matched phrase. Nothing is hidden or auto-actioned.
3. **Review actions:** approve and create clip, reject, revise range, and defer. Each
   carries a reason where the backend requires one.
4. **Phrase lists and derivation:** publish a new phrase-list version (textarea, with
   client-side normalization preview), run a derivation for a Session, and show the run
   result: the candidate count and the skip counts by reason.
5. Tests: queue paging, review command construction, derivation result presentation, and
   provenance labels.

## Out of scope

- Media playback and a timeline scrubber, which need a separate media-serving decision.
- Packaging Asset upload.
- Metadata-override editing (later).
- Mission Control changes.
- Automation or approval policies (ADR-0026 stays inactive).
- Any new backend route or semantic.

## Constraints

- **Dependencies:** only the existing ones (Next.js, React, React Query, zod,
  react-hook-form, and Tailwind). No new ones.
- **Browser boundary:**
  - The secret never reaches the browser.
  - The browser only ever calls same-origin `/api/stageflow/*` routes, each with an
    explicit allowlist.
- **Language:** white-label and consequence-first state language, following
  `shared-state-component-language.md`. Colour is never the only carrier of meaning.
- **Offline:** the app uses no external fonts or CDNs.
- **Checks:** every phase passes `npm run build`, `npm run lint`, `npm run typecheck`, and
  `npm run test`, plus the backend suite unchanged.
- **Owner step per phase:** launch the app against the demo database and confirm the new
  surfaces by screenshots. Phase 2 and Phase 3 steps act on the validation Event, not on
  real deliverables.

## Acceptance criteria (for the whole plan)

- [ ] A producer can see, propose, approve or reject, and render a Session's Assembly from
  the UI. Timing qualification and ordering source are visible before approval.
- [ ] A producer can publish a phrase list, run a derivation, and review declared and
  derived candidates in the real Editorial queue.
- [ ] Every browser-to-backend call goes through allowlisted, secret-holding server
  routes with the Demo proxy's protections. The Demo proxy is unchanged.
- [ ] All frontend and backend checks pass, and each phase has an owner screenshot
  validation record.

## Rollback

Each phase is frontend-only and reverts independently. No data migrations are involved.

## Completion record

_(Filled in per phase.)_
