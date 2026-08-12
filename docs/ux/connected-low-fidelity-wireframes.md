# StageFlow Connected Low-Fidelity Wireframes & Interaction Model
**Status:** Draft v0.1
**Source fidelity:** Exact chat draft.

> **Repository interpretation:** This exact Draft v0.1 is an interaction model, not an
> implemented wireframe or frontend. Screens involving Editorial, Assembly, workers,
> automation, or Marketing remain future or decision-gated as documented elsewhere.

## 1. Application Shell

Persistent operational shell with Event header and left rail.

Producer surfaces grouped; Editorial explicit workspace transition.

## 2. Global Header

Only Event-level operational context: StageFlow identity, Event, Event Mode/lifecycle, authoritative current time, connection/recovery condition.

## 3. Global Healthy State

Quiet normal state; no success banner.

## 4. Global Stale State

Keep underlying workspace visible but marked stale. Disable authoritative actions.

## 5. Recovering State

After connection returns, remain read-only until fresh reconciliation restores authority.

## 6. Mission Control — Normal State

Fixed Stage rows with Session, media, intelligence, state. Attention and Infrastructure below/adjacent.

## 7. Mission Control — Stage Review State

Stage remains in place; Attention panel explains review reason, preservation, and action.

## 8. Mission Control — Worker Degraded

Show AI Workers availability and consequence lag; do not mark production Stage critical if unaffected.

## 9. Mission Control → Stage Detail

Contextual zoom into selected Stage, not generic detail module.

## 10. Stage Detail — Active Session

Show Stage, Session, participants, Presentation Active, elapsed, previous/current/next, media, Candidates, Producer marks, lag, MARK MOMENT, attention.

## 11. Mark Moment Interaction

MARK MOMENT immediately creates durable mark at current Session-relative point; optional note later.

## 12. Mark Moment Confirmation

Lightweight transient confirmation; no modal.

## 13. Stage Detail — Session Start Expected

Show External Program Expectation separately from Session authority. Allow start expected Session or ad hoc Session.

## 14. Start Session Confirmation

Explain authoritative fact and effective time.

## 15. Stage Detail — End Likely

Machine proposes; Session remains active until Producer declares. Actions END PRESENTATION / NOT YET.

## 16. Stage Detail — Turnover Ambiguity

Show previous assembling + current active + unknown-interval media; preserve and route to Association Review.

## 17. Producer Work Queue — Default

Requires Intervention, Needs Review, Automated summary.

## 18. Work Queue — Empty State

No Producer work waiting; routine processing continues.

## 19. Work Queue Routing

Route to owning workflow rather than duplicate controls.

## 20. Session Package Review — Core Layout

Header, package state/revision, timeline, unplaced/time unknown lane, boundaries, checks, blocking reason.

## 21. Package Review — Ready State

Show approval checks and Candidate context; Candidates do not block package.

## 22. Package Approval

Confirmation lists authoritative facts being confirmed.

## 23. Package Reopened

Show new revision, reason, previous approval preserved.

## 24. All Sessions — Dense Event View

Scan-dense rows with state, Session, Stage, Candidate context.

## 25. Editorial Workspace Transition

Persona switch changes information architecture; Producer controls recede.

## 26. Editorial Event Queue — Live Triage

Priority Now + Live Sessions + lag.

## 27. Editorial Queue — New Candidate Arrival

Stable `new candidates` indicator; avoid disruptive row insertion.

## 28. Editorial Queue — Producer Mark Arrival

More prominent; actions review next / keep current. No forced navigation.

## 29. Editorial Queue — Caught Up

No priority Candidates waiting.

## 30. Editorial Queue — Human Backlog

Show priority queue and oldest wait while intelligence may be healthy.

## 31. Editorial Queue — Intelligence Backlog

Show Moment/transcript lag while Editorial may be caught up.

## 32. Temporal Workspace — Standard Candidate Review

Video, timeline, transcript, Candidate inspector, actions.

## 33. Temporal Workspace — Playback Focus

Transcript follows playback; click transcript seeks; playback does not change review state.

## 34. Temporal Workspace — Live Edge

Being behind live is neutral; explicit return-to-live control.

## 35. Temporal Workspace — Candidate Context

Explain why suggested with provenance.

## 36. Temporal Workspace — Fast Approve

Approval creates Editorial Clip and offers next Candidate/open Clip.

## 37. Temporal Workspace — Approve With Range Refinement Needed

Potential future distinction between editorial value approval and final trim precision; durable semantics remain architecture-gated.

## 38. Temporal Workspace — Reject

Fast rejection with optional reasons.

## 39. Temporal Workspace — Defer

Allow future review contexts.

## 40. Temporal Workspace — Package Changed

Preserve Editorial work; show revision change and impact summary.

## 41. Temporal Workspace — Boundary Impact

Candidate preserved even if now outside authoritative Session boundary.

## 42. Responsive MacBook Layout — Producer

Stage matrix remains primary; Attention/Infrastructure collapse below/drawers. Change layout rather than only shrink typography.

## 43. Responsive MacBook Layout — Editorial

Media remains visible; transcript and Candidate inspector may share tabbed/lateral lower panel; review actions remain accessible.

## 44. External Display Layout

Use space for simultaneous context.

## 45. Selection State

Selection distinct from warning, priority, health, live.

## 46. Hover State

Hover may reveal secondary action but never essential status.

## 47. Focus State

Strong keyboard focus on operational rows/markers/actions.

## 48. Disabled Authority State

Disabled control explains blocking condition.

## 49. Multi-Operator State Change

Refresh current truth and stop stale authority flow.

## 50. Empty States

Operational, not onboarding.

## 51. Navigation Back Behavior

Preserve queue mode, filters, scroll, grouping.

## 52. Deep-Link Behavior

Stable navigable identity for Session/Candidate/Work Item.

## 53. Persona Switching

Preserve Session context where possible.

## 54. Shared Status Vocabulary

Same meaning everywhere for LIVE, REVIEW REQUIRED, RECOVERING, DEFERRED, AUTO-APPROVED, EXTERNAL, DECLARED, INFERRED.

## 55. Screen Success Criteria

Mission Control: 2–3 sec for Event/Stage/attention.
Stage Detail: 5 sec for current situation/action.
Producer Work Queue: 5 sec for what/why/priority.
Package Review: 10 sec for completeness/blocker/change.
Editorial Event Queue: 5 sec for next review/marks/backlog.
Temporal Workspace: 15 sec for what/why/context/decision.

## 56. Overall Interaction Principle

Operators move through progressively deeper context:

**Event → Stage → Session → Package or Editorial Moment**

rather than jumping among software modules.

---
