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

#### Phase 2 amendments (owner, 2026-09-27)

- **Command audit log.** The owner wants every action traceable for full diagnosis, with a
  log of successes as well as failures.
  - Every command through a capability route writes two structured `console.info` lines,
    `stageflow_capability_command=` followed by JSON, sharing a server-generated
    `request_id`.
  - **The received line** records:
    - an aware ISO timestamp;
    - the capability, method, and matched route *pattern* (not the raw path);
    - the resource UUIDs;
    - `command_id` and `operation_id` taken from the body, when present;
    - the launch-context fingerprint and whether it was valid;
    - the bounded client address;
    - `accepted`, or a refusal reason: `cross_site`, `launch_context`, `too_large`,
      `not_allowed`, or `secret_unavailable`.
  - **The result line** records:
    - the backend HTTP status;
    - the outcome: `succeeded`, `rejected` (4xx, with the bounded backend error code), or
      `failed` (5xx, timeout, or unavailable);
    - the duration in milliseconds;
    - the resulting identifiers from the response body when present (for example
      `revision_id`, `decision_id`, `operation_id`).
  - **Never logged:** the secret, request or response bodies, or operator free text such
    as reasons. Only `reason_present` and `reason_length` are recorded.
  - Reads are not logged per request.
  - The Demo proxy's existing audit lines stay unchanged.
  - Tests assert both lines for success, rejection, failure, and every refusal branch, and
    that no secret or free text appears.
- **Scanning rule** (owner's standing rule, `docs/ux/operator-feedback.md`, 2026-09-27).
  Actions sit next to the state they change, as one primary action per state:
  - Propose when there is no current valid revision.
  - Approve or reject when a revision is unreviewed.
  - Request render when a revision is approved and not stale.

  The confirmations lead with a one-line consequence, and name exceptions such as
  `registration_time` members or unqualified timing. Results appear inline as one line,
  with the backend identifier available in details.

#### Phase 2 owner review checkpoint (2026-09-27)

- Classification: Green; implementation-ready. Authority: ED-0094, the six approved
  checkpoint items in `docs/ux/operator-feedback.md`, and the owner's execution
  clarification. Loopback equivalence is explicitly approved for the three named
  aliases, with the same scheme and port; other origin protections stay unchanged.
- Acceptance: compact render tables; operations grouped in stable state precedence
  (in-flight, succeeded, failed/other), without chronology claims; outputs newest first
  by `produced_at` within the bounded read. Resolve known Assembly revision numbers.
  Current-revision summary uses in-flight, succeeded with newest matching output, then
  failed precedence; another render remains an explicit secondary confirmed action.
- Collapse uniform member values into the summary. Resolve slot names and roles using
  bounded server-side Packaging Asset/revision reads under the existing shared deadline;
  unmatched identities remain unavailable with IDs in details. Confirmation consequence
  supplies the accessible dialog label without a repeated heading.
- Scope: frontend production code, focused tests, this plan and the checkpoint record.
  No backend, dependency, schema, configuration, audit-log, or automatic-action changes.
- Validation: presentation and real UI-handler tests for items 1–5; additive proxy tests
  for all loopback pairings, port/scheme differences, non-loopback and cross-site refusal,
  and absent/literal-null origins. Preserve existing security/Demo assertions.
  Run frontend test, typecheck, lint, build, and `git diff --check`; report sandbox worker
  failures, and use the existing per-file no-isolation test workaround if necessary.
  Deliberately review the final diff and record validation before closing the checkpoint.

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

### Phase 1: ED-0093 (2026-09-27)

- **Implemented revision:** branch `codex/ed-0093-producer-outputs-foundation`. Codex
  implemented it and the owner committed it.
  - The shared server-only capability proxy module.
  - Four routes: assembly, rendering, editorial, and media timing. They cover 23 anchored
    method and path pairs, matching the backend exactly.
  - Typed zod clients and the `DemoMoment` fix.
  - A read-only Outputs panel on Session Detail.
- **Checks:**
  - `directive-reviewer`: APPROVE.
  - A security review of the new routes found no findings at confidence 8 or higher. The
    note below the threshold is DNS rebinding, a design gap across the whole app. A
    Host-header allowlist is a follow-up.
  - Demo proxy behaviour and tests are unchanged.
- **Owner review checkpoint (live against the demo database):** the owner directed a
  standing rule. The UI must be simplified and easy to scan under dense workload. See
  `docs/ux/operator-feedback.md`, 2026-09-27. Two presentation passes implemented it:
  - Outputs placed directly after the Session summary.
  - One summary line in place of the repeated warnings, with only exceptions flagged.
  - A compact member table (position, start, duration), with IDs moved into details.
  - Timing folded into the member rows. Only media outside the Assembly is listed
    separately.
  - Evidence and transcription sections collapsed by default, with truthful counts.
  - Operations summarized by state.
  - A five-second overall read budget for Session Detail.
- **Tests:** frontend typecheck, lint, **118/118 tests**, and build pass on the host.
  - Existing assertions changed only where they pinned the wording or structure of the
    redesigned sections.
  - Proxy, route, security, and command tests are unchanged.
  - No backend change.
- **Remaining work:**
  - The Editorial moments grid (31 uniform tiles) is redesigned in ED-0095.
  - A Host-header allowlist (DNS rebinding).
  - A proxy audit log for capability commands, to be decided before ED-0094 adds command UI.

### Phase 2 owner review checkpoint: ED-0094 (2026-09-27)

- Applied the six owner-approved checkpoint changes to the existing ED-0094 action
  implementation (`b4e548b`); changes remain uncommitted on the directive branch.
- Render tables preserve stable state grouping and sort outputs by production instant
  within the bounded read. Known revision IDs resolve to numbers; other IDs and hashes
  are disclosed per row. Current-revision render state replaces the primary render
  action; another render retains confirmation, idempotency, and manual initiation.
  The API's `terminal_failed` state supplies the “Render failed” summary.
- Uniform member start/duration values move to the summary; empty flags columns vanish.
  Packaging names/roles resolve only by frozen revision identity: at most one 100-asset
  page and one 100-revision page per asset, eight concurrent packaging revision reads,
  sharing the existing five-second deadline. Missing/failed/truncated matches remain
  explicitly unavailable; content references are not retained in the presentation model.
- Confirmation consequence now supplies the dialog's accessible label. The loopback
  exception uses the native Request URL because Next.js normalizes other 127.x.x.x
  hosts to localhost; exact-origin, absent-origin and cross-site behavior is preserved.
  All route allowlists, audit behavior and secret handling are unchanged.
- Existing test files touched:
  - `session-outputs.test.ts`: new render ordering/summary, uniform duration, packaging
    identity/failure/budget tests; existing loader mock handles the additional packaging
    read and asserts it separately while preserving its original six-read assertions.
  - `output-actions-ui.test.ts`: new re-render confirmation and primary-action tests;
    harness imports the render-summary helper.
  - `capability-proxy.test.ts`: additions only, six route/method matrices cover every
    loopback pairing, scheme/port mismatch, non-loopback origins, cross-site, null,
    malformed origins, and unapproved 127.x.x.x request hosts.
- Existing assertions changed (only these four):
  - uniform member row markup now omits shared start/duration and empty flags;
  - member-row counting matches numeric position headers, excluding new render rows;
  - uniform member column expectations retain Position/Details and omit Start/Duration/Flags;
  - confirmation `aria-labelledby` expects `output-consequence`.
  Existing Demo, audit and other security assertions are unchanged.
- Validation:
  - `npm.cmd run typecheck`: pass after correcting the new fixture/helper state to the
    existing `terminal_failed` API value. Initial typecheck caught that in-scope error.
  - `npm.cmd run lint`: pass.
  - `npm.cmd run test`: sandbox `spawn EPERM`; 0 passed, 15 file-worker failures,
    before test bodies could run.
  - Each of the 15 files from `package.json` was run separately with
    `node --import ./src/experience/server-test-runtime.ts --test --test-isolation=none <file>`:
    **183 passed, 0 failed, 0 skipped**. Final run followed the independent-review fix.
  - `npm.cmd run build`: compilation passed; TypeScript worker blocked by `spawn EPERM`.
  - `git diff --check`: pass. Git reports normal LF-to-CRLF working-copy notices.
  - Initial `npm run typecheck` was blocked by PowerShell's script execution policy;
    subsequent checks used `npm.cmd`. TMP/TEMP used the workspace `.codex-tmp`.
- Deliberate diff/self-review completed. Independent Codex review found and then verified
  closure of the Next.js hostname-normalization edge; no remaining actionable findings.
  No new plan files, backend changes, dependencies, schemas, migrations or runtime
  configuration changes. Frontend production code changed. No dev server was started.
  No new product/architecture decisions remain; full host test/build completion is
  still required. The operator checkpoint is marked `validated (ED-0094)`.
