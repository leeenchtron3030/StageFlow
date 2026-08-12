# Producer UX operational refinement and real-data integration

## Status

In progress

## Execution authority

- **Classification:** Green autonomous
- **Authority evidence:** Operator-authorized Autonomous Producer UX Refinement and
  Real-Data Integration workstream; Product Constitution principles 2, 5, 7-11, 15,
  17, 18, and 22-25; accepted Durable Event-Mode Kernel and Media Timing Evidence v1
  architecture; ADR-0023, ADR-0024, and ADR-0027; completed Producer operational UI MVP;
  sanitized Runs 002-004; root bounded-autonomy policy.
- **Implementation-ready:** Yes
- **Required escalation or approval:** None for the bounded read-only projection adapter,
  fixture, presentation, accessibility, preview, documentation, and compatible patch-level
  dependency maintenance described here. Authority commands, profile qualification,
  worker/transcription execution, Editorial authority, and new domain semantics remain
  Yellow or separately governed and are excluded.

## Related findings or ADRs

- **Finding/disposition:** Run 002 proves Presentation Ended plus Package Assembling is
  normal; Run 003 proves preservation without Session authority; Run 004 proves same-Stage
  turnover should read as association review rather than system failure.
- **ADR:** ADR-0023 Session semantics, ADR-0024 Kernel authority and conservative media
  association, ADR-0027 advisory Media Timing Evidence.
- **Engineering Directive or other authority:** ED-0054; Producer, Mission Control,
  Stage Detail, Session Package Review, Editorial, shared-state, visual-density, and
  Event-day UX specifications as calibration inputs within implemented authority.

## Problem statement

The runnable Producer MVP preserves the correct authority boundaries but remains too
sparse for realistic multi-Stage control-room evaluation. Its frontend adapter drops
useful media association/provenance facts already present in the Kernel status response,
fixture/live status is present but not expressed as the four explicit operator states,
Session uncertainty drill-down is shallow, MTE disclosure is summarized too aggressively,
and the Editorial shell does not yet frame the distinct transcript, Candidate, Hot Moment,
approved Clip, and human-review surfaces. Operators also lack one repo-native preview
entry point and a lightweight feedback-capture location.

## Verified current behavior

- Branch `agent/producer-ux-operational-refinement` starts exactly at merged baseline
  `d03966ead74832d7e98997572a90bdbd83004c25` with a clean worktree.
- The frontend consumes `GET /api/v1/kernel/status` server-side and optionally reads
  `GET /api/v1/media-assets/{asset_id}/timing-evidence`; it exposes no command authority.
- The Kernel response already includes bounded recent media registration, association,
  reason, policy, input-reference, timing, and provenance fields, but the frontend model
  currently retains only asset, Stage, and Session IDs for MTE lookup.
- Mission Control uses Stage as the primary unit and existing fixtures correctly keep
  stabilizing media quiet, unresolved turnover at Review, source loss at Intervention,
  and cloud loss consequence-first.
- Editorial is explicitly a development shell and no transcript, model, Candidate,
  review, or Clip runtime exists.
- `npm audit --json` on the committed lock reports 12 findings: one direct runtime
  package (`next` 16.2.10), transitive Next runtime/build packages, and transitive
  development-tooling packages. The registry identifies Next 16.2.11 as the compatible
  patch containing the direct fixes. No audit fix has been run.

## Desired behavior

A dense, Stage-centric operational console answers Event, Stage, media-flow, Session,
package, and consequence questions at a glance; exposes real bounded Kernel media facts
and real MTE history in contextual drill-down; distinguishes live connected, live
unavailable, live unconfigured, and development fixture states; frames Editorial work
without implying nonexistent AI; and remains usable across requested desktop widths,
zoom levels, keyboard navigation, and high/empty Attention conditions.

## In scope

- Dense Mission Control hierarchy for one through seven-plus Stages, long identity text,
  no-Session Stages, quiet and high-Attention states.
- Frontend adaptation of existing Kernel recent-media, association reason, provenance,
  Session-reference, reconciliation, source, and MTE fields. Association input
  references are labeled as Sessions considered by policy; they are not presented as
  proof of eligibility.
- Explicit data-mode state and connection-failure/unconfigured presentation.
- Stage and Session media-uncertainty drill-down with bounded affected-asset evidence and
  operator-readable explanations.
- Full MTE v1 disclosure for Observed versus Derived, provider/tool, profile, revision,
  qualification, precision, limitations, derivation identity, candidate interval, and
  advisory-only use.
- Consequence-first Infrastructure refinement and structurally useful, clearly simulated
  Editorial workspace framing.
- Accessibility/responsive refinements, focused behavior tests, a development preview
  script, operator-feedback guidance, and dependency-security triage.
- Compatible patch-level Next.js maintenance within the existing major/minor line if
  install, build, tests, and audit evidence remain clean.

## Out of scope

- New authority APIs or enabled Event/Session/package commands.
- Authentication, authorization, role permissions, or multi-operator command behavior.
- MTE recorder-profile qualification or using MTE to change association/Session authority.
- Worker, transcription, AI, Editorial Candidate/Clip persistence, playback, rendering,
  publication, or provider selection.
- Schema, migration, durable domain, Session, Package, Attention, or Editorial semantics.
- Major framework changes, forced audit fixes, or production deployment.

## Constraints

- **Architecture and terminology:** Stage remains the Producer unit; health, consequence,
  and Attention remain separate; Presentation, Package, association, and Editorial state
  do not collapse; MTE is advisory and Derived intervals are never authoritative time.
- **Compatibility:** Existing API response fields remain accepted as-is; frontend changes
  are additive presentation adaptation. Bounded recent-media results must be labeled as
  bounded and must not be presented as complete Session membership.
- **Offline/event mode:** Local Kernel operation and fixture review require no cloud
  service. Internet loss communicates deferred capability, not production failure.
- **Security/data handling:** Do not expose source paths, credentials, DSNs, provider
  dumps, customer media, or real transcript content. Fixtures remain synthetic and
  unmistakably non-authoritative.

## Implementation approach

1. Extend the presentation model with explicit source state, bounded media-asset evidence,
   MTE observations/derivation identity, and simulated Editorial workflow surfaces.
2. Adapt the existing Kernel response without adding browser-owned policy, including
   operator-readable association explanations and bounded Session references, without
   upgrading policy inputs into eligibility claims.
3. Recompose Mission Control and Stage/Session/Infrastructure/Editorial views around dense
   identity-state-consequence-evidence hierarchy.
4. Add scale/high-Attention fixtures and behavior tests for every epistemic and connection
   distinction.
5. Add a dev-only preview script, operator-feedback file, launch/security documentation,
   and the compatible Next patch if verified.
6. Run frontend validation, affected backend projection tests if applicable, docs checks,
   and browser qualification at the requested sizes/zoom/scenarios; correct Green defects.
7. Complete the plan record, self-review/security-audit the diff, and publish one coherent
   milestone PR following repository convention.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `frontend/src/experience/` | Explicit modes, richer Kernel/media/MTE model, fixtures, behavior tests |
| `frontend/src/components/` | Dense operational and diagnostic presentation |
| `frontend/app/globals.css` | Responsive density, focus, status, and accessibility styling |
| `frontend/package*.json` | Compatible Next patch and lockfile only if verified |
| `scripts/preview/` | Dev-only local preview convenience entry point |
| `frontend/README.md`, `scripts/README.md` | Launch, fixture/live, shutdown, failure, and security guidance |
| `docs/ux/` | Lightweight operator-feedback capture process |
| `docs/plans/README.md` | Plan index and milestone completion state |

## Data or migration considerations

No schema, data migration, identity, durable state, or stored media change. The Kernel API
is consumed through its existing additive response. Fixture and simulated Editorial data
remain code-local and development-labeled.

## Failure and recovery considerations

- A frontend-to-Kernel failure shows `LIVE - unavailable` and no fabricated PostgreSQL or
  subsystem state.
- An intentionally unconfigured Kernel shows `LIVE - unconfigured`, distinct from an
  unreachable endpoint.
- MTE fetch failure affects only evidence drill-down and changes no authority or Attention.
- The preview script surfaces child-process output, exits when a child fails, and stops
  only processes it created.
- Reverting the isolated frontend/docs/script changes restores the MVP; no data reversal
  is required.

## Observability requirements

Operators can identify data mode/freshness, Event readiness, each Stage's current or
relevant Session, Presentation and Package dimensions, media flow/preservation,
association uncertainty, source consequence, bounded evidence, and the exact reason an
asset was not chosen automatically. Developers can identify advisory dependencies and
preview failure without leaking paths or credentials into UI projections.

## Test strategy

- Node-native behavior tests for quiet/stabilizing/turnover/no-authority/infrastructure,
  explicit data modes, bounded media reasoning, MTE non-authority, scale fixtures, and
  disabled authority controls.
- `npm test`, `npm run lint`, `npm run typecheck`, and `npm run build`.
- Focused backend status/MTE tests only if backend code changes; otherwise no backend
  claim beyond the already consumed contracts.
- UTF-8, relative-link, and whitespace checks plus `git diff --check`.
- Browser qualification at approximately 1512, 1440, 1280, and 768 CSS-pixel widths;
  90%, 100%, 110%, and 125% zoom; quiet, turnover, scale/high-Attention, source/cloud
  degradation, fixture/live-unavailable/live-unconfigured, Stage, Session, Infrastructure,
  and Editorial routes; keyboard focus and disabled-control checks.

## Acceptance criteria

- [ ] Mission Control keeps one through seven-plus Stages simultaneously scannable and
  handles long Stage/Session identities and no active Session without layout loss.
- [ ] Normal stabilization and trailing assembly remain quiet; Runs 003/004 communicate
  preservation and review without production-failure language.
- [ ] `LIVE - connected`, `LIVE - unavailable`, `LIVE - unconfigured`, and
  `DEVELOPMENT FIXTURE` are unmistakable and behavior-tested.
- [ ] Stage/Session drill-down exposes bounded affected media, association reasoning,
  eligible Session context only where the projection proves it, otherwise Sessions
  considered by policy, plus a comprehensible non-selection reason.
- [ ] MTE labels Observed and Derived facts, qualification, provenance, precision,
  limitations, candidate interval, and advisory-only use; unqualified evidence cannot
  visually appear authoritative or enter Producer Attention.
- [ ] Infrastructure separates health, consequence, and Attention; Internet degradation
  explicitly preserves local Event Mode.
- [ ] Editorial frames Session, media/timeline, transcript, Candidate, Hot Moment,
  approved Clip, and human-review states without implying a connected AI subsystem.
- [ ] Disabled authority controls explain their backend/authority prerequisite.
- [ ] Preview, feedback, security-triage, responsive, keyboard, and validation evidence
  are documented; all required checks pass or an exact blocker is recorded.

## Rollback or reversal

Revert this plan's frontend model/components/styles/tests, preview/docs, and compatible
lockfile update. No database, migration, production configuration, or external service
requires reversal.

## Open questions

- No Yellow decision is required for this milestone. Enabling authority commands,
  accepting MTE qualification, or implementing real Editorial/transcription work remains
  explicitly deferred.

## Completion record

- **Implemented revision:** Pending
- **Files and migrations actually changed:** Pending
- **Commands and tests actually run:** Pending
- **Results and warnings:** Pending
- **Execution authority used:** Green autonomous
- **Approved deviations:** None
- **Rollback status:** Reversible; not yet exercised
- **Remaining work:** Pending
