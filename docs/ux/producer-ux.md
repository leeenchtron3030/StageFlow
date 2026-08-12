# StageFlow Producer UX Specification
**Status:** Draft v0.1
**Source fidelity:** Recovered accepted UX direction; not a verbatim reproduction.

> **Repository interpretation:** This is a recovered accepted-design summary from the
> handoff bundle, not a verbatim historical chat draft. It records product direction
> without claiming the described frontend or supporting capabilities are implemented.

## Purpose

The Producer UX is the high-level human control surface for StageFlow during live Event operation. The Producer is responsible for operational awareness, Session authority, media completeness, package verification, exception handling, and Event closeout—not detailed content review.

## Deployment assumption

- The primary Producer control surface is expected to run on a **MacBook Pro**.
- Heavy AI/media processing should normally run on separate Event Nodes / workers.
- The UI must not assume the control surface and processing worker are the same machine.
- Worker overload, restart, or disappearance must not remove Producer control as long as the authoritative StageFlow control plane remains reachable.

## Core principles

- Exception-oriented and calm when healthy.
- Stage is the primary operational unit.
- Health, impact, and attention are distinct.
- Production meaning comes before technical telemetry.
- Epistemic authority must remain visible where consequential:
  - Observed
  - Derived
  - Inferred
  - Declared
  - External
- Human consequential decisions are explicit.
- Progressive disclosure:
  1. operational meaning,
  2. workflow detail,
  3. evidence/provenance,
  4. technical telemetry.
- Stable layout and scan density are preferred over animated dashboards.
- Healthy state should be visually quiet.
- The visual character should feel like **broadcast multiview + modern operational console**, not enterprise SaaS.

## Primary Producer navigation

- Mission Control
- Event
- Sessions
- Infrastructure

Internal concepts such as Observations, Candidates, ingress records, or generic jobs should not become top-level Producer navigation.

## Event lifecycle

Conceptually:

**Setup → Armed → Active → Closing → Post-event**

## Primary authoritative Producer interactions

1. Arm Event
2. Start Session
3. End Presentation
4. Approve Session Package

The system may observe, infer, and propose around these actions. In the initial trusted workflow, consequential authority remains human.

## Attention model

Producer-facing attention should remain simple:

- Information
- Review
- Intervention

Acknowledged is not the same as resolved.

## Event closeout

The Producer should eventually have a **Venue Exit / Safe to Leave** determination based on production-relevant durable state such as:

- no active Sessions,
- no media still stabilizing where shutdown risks loss,
- authoritative state durable,
- fresh reconciliation complete,
- no unresolved critical media.

Downstream Editorial, Moment review, rendering, or Marketing backlog may remain after Event capture is safe to close.

---
