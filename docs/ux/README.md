# StageFlow UX specifications

## Purpose

This directory records role-specific product and interaction specifications that
constrain later application/read-model design. UX specifications do not prove that a UI,
API, domain capability, or persistence boundary is implemented, and they do not approve
an unresolved ADR.

Architecture authority and current-state qualification remain in
[the architecture index](../architecture/README.md). Implementation begins only through
an appropriately classified plan.

## Current implementation

The Green [Producer operational UI MVP](../plans/producer-ui-mvp.md) implements a
locally runnable, read-only Producer review surface plus a minimum non-executing
Editorial shell. Draft specifications remain calibration inputs rather than evidence
that their full workflows, authority actions, playback, transcription, or automation
are implemented.

## Status vocabulary

- **Draft:** product/UX direction under refinement; not implementation authority.
- **Accepted:** approved interaction/product behavior whose supporting domain decisions
  are already resolved or explicitly identified as gated.
- **Implemented:** verified in the current application and linked to implementation/test
  evidence.
- **Superseded:** retained for history and replaced by a named later specification.

## Specifications by role

Only captured repository artifacts appear below. Mission Control, Stage Detail, Session
Package Review, Editorial Temporal Workspace, Session Assembly, and other discussed
surfaces need their own specifications before they are added to this index.

### Producer

- [Producer UX](producer-ux.md) — Draft v0.1, recovered accepted-design summary rather
  than verbatim historical prose.
- [Mission Control](mission-control.md) — Draft v0.1, recovered accepted-design summary.
- [Stage Detail](stage-detail.md) — Draft v0.1, recovered accepted-design summary.
- [Session Package Review](session-package-review.md) — Draft v0.1, recovered
  accepted-design summary.
- [Session Assembly & Approval Automation](session-assembly-approval-automation.md) —
  exact Draft v0.1; Assembly, Packaging Asset, and automation decisions remain gated.
- [Producer Sessions & Work Queue](producer-sessions-work-queue.md) — exact Draft v0.1;
  no Sessions/Work Queue frontend or supporting capability is implemented.

### Editorial

- [Editorial Temporal Workspace](editorial-temporal-workspace.md) — exact Draft v0.1;
  no playback, transcript, or candidate-review workspace is implemented.
- [Editorial Event Queue & Live Triage](editorial-event-queue-live-triage.md) — exact
  Draft v0.1; no Editorial queue, Temporal Workspace, or candidate-review workflow is
  implemented.
- [Editorial Live vs Post-Session Operating Model](editorial-live-post-session-operating-model.md)
  — exact Draft v0.1; records the small-team multi-Stage operating assumption.

### Shared role model

- [Cross-Role Session Experience](cross-role-session-experience.md) — exact Draft v0.1;
  downstream Editorial, Assembly, Rendering, and Marketing workflows are not
  implemented.
- [Shared UX State & Component Language](shared-state-component-language.md) — exact
  Draft v0.1; constrains future visual/state grammar without implementing components.
- [Visual Design System & Interaction Density](visual-design-system-interaction-density.md)
  — exact provided Draft v0.1; shared Producer/Editorial visual hierarchy, density,
  responsive behavior, accessibility, and component-language requirements.
- [Connected Low-Fidelity Wireframes & Interaction Model](connected-low-fidelity-wireframes.md)
  — exact Draft v0.1; interaction architecture rather than implemented frontend.
- [Event-Day UX Scenario Validation](event-day-scenario-validation.md) — exact provided
  Draft v0.1; pressure-test contract for concurrent operation, ambiguity, degradation,
  recovery, revision impact, scale, and Event closeout.

## Interpretation rules

- Distinguish Mission Control attention, unresolved human Work Items, and ordinary
  Session state.
- Treat examples involving Session Assembly, workers, or automatic authority as future
  behavior until their architecture decisions and implementation plans are accepted.
- Use UI-friendly labels without changing canonical domain/serialized terminology.
- Preserve bounded queries, stale-state handling, optimistic revision checks, and
  worker-independent Producer availability in implementation plans.
- Preserve one authoritative Session identity while exposing role-specific workflow
  dimensions and queues; never synthesize one ambiguous master Session status.
- Keep Editorial prioritization stable and explainable. Producer marks and explicit
  policy may raise priority, but model score alone does not own queue order.
- Keep shared state language consequence-first, visually quiet when healthy, explicit
  about provenance/authority, and accessible without color-only meaning.
- Treat the visual-system specification as a shared requirement, not as evidence that
  design tokens, components, responsive layouts, or styles are implemented.
