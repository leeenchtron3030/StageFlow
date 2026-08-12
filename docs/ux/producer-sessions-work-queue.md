# StageFlow Producer Sessions & Work Queue UX Specification

**Status:** Draft v0.1
**Source fidelity:** Exact chat draft.
**Persona:** Producer
**Primary device:** MacBook Pro
**Context:** Live Event Mode and Event closeout
**Purpose:** Provide a bounded operational workspace for Sessions, decisions, approvals, exceptions, revisions, and deferred Producer work without cluttering Mission Control.

> **Repository interpretation:** This draft records UX/product direction for
> post-Kernel planning. The current frontend remains a static shell and no Work Queue,
> Sessions workspace, Assembly workflow, or automation UI is implemented. Assembly and
> automatic-authority examples remain decision-gated by the post-Kernel architecture.

---

## 1. Primary User Questions

The Sessions & Work Queue surface answers:

**What work is waiting for me?**

and:

**What is the current operational state of all Sessions?**

These are different questions and should remain visually distinct.

Mission Control answers:

**What requires my attention right now?**

The Work Queue answers:

**What human decisions or approvals are waiting when I have capacity?**

The Sessions view answers:

**What is happening, or has happened, across the Event?**

---

## 2. Core UX Principle

StageFlow should not turn every Session into a task.

A Session is an operational entity.

A Work Item exists only when StageFlow requires human action or review.

Therefore:

**100 Sessions does not imply 100 Work Items.**

As automation authority increases, routine Sessions should disappear from the Producer queue rather than merely become faster to approve.

---

## 3. Primary Layout

The surface should have two closely related views:

### Work Queue

Action-oriented.

### All Sessions

State-oriented.

Conceptual layout:

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ STAGEFLOW     DEVCON 202X                         SESSIONS & WORK       │
├──────────────────────────────────────────────────────────────────────────┤
│ [ WORK QUEUE  4 ]     [ ALL SESSIONS  87 ]                              │
│                                                                          │
│ Filters:  Needs Me ▾   All Stages ▾   All Types ▾                       │
├──────────────────────────────────────────────────────────────────────────┤
│ REQUIRES INTERVENTION                                                    │
│                                                                          │
│ Stage C · Protocol Design                                                │
│ Media source interruption                                                │
│ Active Session                                            [ REVIEW ]     │
├──────────────────────────────────────────────────────────────────────────┤
│ NEEDS REVIEW                                                             │
│                                                                          │
│ Future of Ethereum · Stage B                                             │
│ 1 media item unresolved                                                  │
│ Package assembling · ✦ 8 Moment Candidates                [ REVIEW ]    │
│                                                                          │
│ ZK Infrastructure · Main Stage                                           │
│ Assembly approval withheld                                               │
│ Branding asset mismatch                                    [ REVIEW ]    │
│                                                                          │
│ Account Abstraction · Stage B                                            │
│ Package revision 3 requires approval                                     │
│ Previous revision 2 approved                               [ REVIEW ]    │
├──────────────────────────────────────────────────────────────────────────┤
│ READY / AUTOMATED                                                        │
│                                                                          │
│ 14 Sessions completed without Producer action                            │
│                                                     [ VIEW SESSIONS ]    │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Queue Philosophy

The queue is not:

* a chronological activity log,
* a notification inbox,
* a list of every Session,
* a list of every Moment Candidate,
* a system error log.

It is:

**a bounded list of unresolved human responsibilities.**

Every item should answer:

* What requires me?
* Why?
* What is affected?
* How urgent is it?
* What happens if I do nothing right now?
* What action resolves or advances it?

---

## 5. Work Item Types

Initial Producer work-item families may include:

### Session Authority

Examples:

* Session start likely; confirmation required.
* Session end likely; confirmation required.
* Declared Session conflicts with Program Expectation.

### Media Association

Examples:

* Media ownership unresolved.
* Cross-Stage media conflict.
* Human reassignment required.

### Package Review

Examples:

* Session package ready for approval.
* Session package contains unresolved media.
* Package reopened after relevant media discovery.
* Package reopened after media reassignment.

### Assembly Review

Future capability.

Examples:

* Proposed Assembly requires approval.
* Required branding asset unavailable.
* Dynamic graphic metadata incomplete.
* Automatic Assembly approval withheld.

### Automation Exception

Future capability.

Examples:

* Automatic package approval withheld.
* Evidence does not satisfy trusted policy.
* Configuration or evidence falls outside automated-authority scope.

### Infrastructure-Related Human Decision

Only when there is an actual human decision rather than ordinary infrastructure telemetry.

Example:

* Worker intentionally paused; resume decision required.

---

## 6. Moment Candidates and the Producer Queue

Ordinary Editorial Candidate Moments do **not** create Producer Work Items.

Example:

**8 Moment Candidates generated**

is Session intelligence, not Producer responsibility.

Moment activity should appear as contextual information:

```text
Future of Ethereum · Stage B

Package ready for review

✦ 8 Moment Candidates
  2 Producer marked

[ REVIEW PACKAGE ]
```

The candidate count helps the Producer understand downstream intelligence activity.

It does not create eight tasks.

---

## 7. Producer-Marked Moments

Stage Detail should support:

**MARK MOMENT**

A Producer mark creates a durable human-declared Editorial Candidate Moment or equivalent canonical candidate record.

In the Sessions view:

```text
Future of Ethereum

✦ 8 Moment Candidates
  2 Producer marked
```

Producer-marked candidates should receive strong Editorial visibility later.

They remain candidates.

They are not Editorial approvals.

---

## 8. Hot Moment Language

Canonical architecture uses:

**Editorial Candidate Moment**

The Producer UI may use the shorter:

**Moment Candidate**

for routine presentation.

The term:

**Hot Moment**

should communicate urgency/editorial significance rather than a separate authoritative aggregate.

Examples:

**Moment Candidates — 8**

and later:

**2 marked Hot / priority**

if Editorial workflow introduces urgency classification.

The UI must not imply that every automatically detected candidate is editorially approved.

---

## 9. Queue Priority

Queue order should reflect operational consequence rather than raw creation time.

Recommended order:

1. Immediate active-production intervention
2. Session authority decisions affecting current Stage operation
3. Media-completeness ambiguity
4. Package/revision review
5. Assembly/policy exception
6. Administrative metadata correction

Within the same priority class, age may influence ordering.

---

## 10. Queue Sections

Recommended visible groups:

### Requires Intervention

Current Event operation or media completeness may be at material risk.

### Needs Review

Human judgment required but immediate production operation can continue.

### Waiting

StageFlow is waiting on processing or another dependency, but no human action is currently possible.

### Automated / Resolved

Optional collapsed summary showing work StageFlow completed without human action.

The Producer should not need to clear these manually.

---

## 11. Waiting Is Not Work

Example:

```text
Future of Ethereum

Package assembling

1 media asset stabilizing

No action required.
```

This belongs in the Session state.

It should generally not enter the Producer Work Queue.

Similarly:

```text
Transcription processing
+42 sec behind live
```

does not become a task unless policy says the lag now requires human intervention.

---

## 12. Work Item Anatomy

Every work item should contain:

### Identity

Affected Session / Stage / Assembly / dependency.

### Required decision

What does StageFlow need?

### Reason

Why is human authority required?

### Operational consequence

What happens if unresolved?

### Current status

What StageFlow has already done.

### Primary action

One clear next step.

Example:

```text
MEDIA ASSOCIATION REVIEW

Future of Ethereum · Stage B

1 media item cannot be safely assigned.

Possible ownership:
• Future of Ethereum
• Account Abstraction

Media is preserved.
Package approval is blocked.

[ REVIEW ASSOCIATION ]
```

---

## 13. Work Item Detail

Selecting a queue item should route into the appropriate contextual workflow instead of a generic task-detail page.

Examples:

Session start item:

→ Stage Detail

Media association:

→ Association Review

Package approval:

→ Session Package Review

Assembly exception:

→ future Assembly Review

Infrastructure:

→ Infrastructure Detail

The queue is navigation into authoritative workflows.

It should not duplicate them.

---

## 14. All Sessions View

The All Sessions tab provides Event-wide Session visibility.

Conceptual layout:

```text
ALL SESSIONS

Search Sessions…                         Stage: All ▾

STATE                 SESSION                    STAGE       INTELLIGENCE

Presentation Active   Autonomous Agents          Stage B     ✦ 7
Presentation Active   Protocol Design            Stage C     ✦ 3
Assembling            Future of Ethereum         Stage B     ✦ 8
Review Required       ZK Infrastructure          Main        ✦ 5
Complete              DAO Governance             Workshop A  ✦ 11
Complete              Scaling Rollups            Main        ✦ 6
```

Selecting a Session opens the appropriate Session operational/detail view.

---

## 15. Session Row Information

A Session row should prioritize:

* Session title,
* Stage,
* participant summary,
* operational lifecycle,
* package state,
* attention state,
* Moment Candidate count,
* Assembly state when available.

Optional secondary information:

* Program Expectation,
* start/end time,
* duration,
* package revision,
* approval time.

Do not overload the default row.

---

## 16. Participant Summary

Examples:

```text
Future of Ethereum
Alice Smith · Example Foundation
```

For panels:

```text
Scaling Rollups Panel
Alice Smith + 3 participants
```

Expanded metadata may show:

* participant name,
* role,
* organization/affiliation.

Organization remains optional.

---

## 17. Session State Presentation

The view should use operational language rather than raw domain state names.

Possible visible states:

**Expected**

**Awaiting Start**

**Presentation Active**

**Presentation Ended**

**Package Assembling**

**Ready for Review**

**Review Required**

**Complete**

A Session may also carry downstream secondary states such as:

**Assembly Proposed**

**Assembly Approved**

**Editorial Active**

These should not replace the primary Session/package lifecycle.

---

## 18. Multi-Dimensional Session State

A Session should not be forced into one overloaded status.

Example:

```text
Future of Ethereum

SESSION PACKAGE
Complete · revision 2

INTELLIGENCE
8 Moment Candidates

EDITORIAL
3 approved clips

ASSEMBLY
Approved · revision 4

RENDER
Pending
```

These are independent workflow dimensions.

Different personas should see different subsets.

---

## 19. Producer Summary State

The Producer-facing Session row can compress those dimensions:

```text
Future of Ethereum

Complete
Assembly approved
✦ 8 Moment Candidates
Editorial ready
```

The Producer generally does not need detailed Editorial workflow state unless it affects Event operations.

---

## 20. Filters

Useful Producer filters:

### Responsibility

* Needs Me
* No Action Required
* Automated
* All

### Stage

Configured Stage list.

### Session state

* Active
* Assembling
* Review
* Complete

### Work type

* Session
* Media
* Package
* Assembly
* Policy

### Time

* Current
* Last hour
* Today
* Event

Do not expose technical filters such as repository state or ingress type.

---

## 21. Search

Search should eventually match:

* Session title,
* participant,
* organization,
* Stage,
* external Program Expectation metadata.

Search results should still show current operational state.

Example:

Search:

**Alice**

Results:

Future of Ethereum
Alice Smith · Example Foundation
Stage B
Complete

Scaling Panel
Alice Smith + 3
Main Stage
Ready for Review

---

## 22. Boundedness

The Producer Work Queue must be bounded.

The architecture plan proposes cursor pagination.

UX should support:

* bounded initial page,
* cursor-based continuation,
* explicit count where reliable,
* indication when additional results exist.

Do not imply that a truncated list is complete.

Example:

**23 items require review**

Showing 1–20

[ LOAD MORE ]

For Mission Control, stricter attention-oriented bounds should remain appropriate.

---

## 23. Queue Count

Navigation may display:

**Sessions**

or:

**Work · 4**

The count should mean:

**unresolved human work items**

not:

all alerts
all Sessions
all notifications.

This makes the number meaningful.

---

## 24. Automated Sessions

When StageFlow runs in exception-only approval modes, the queue should make successful automation visible without creating clutter.

Example:

```text
AUTOMATED TODAY

14 Session packages
14 Assembly approvals
0 automatic decisions later corrected

[ VIEW AUTOMATION ACTIVITY ]
```

This is evidence of system operation, not a task list.

---

## 25. Auto-Approval Withheld

Example:

```text
REVIEW REQUIRED

Future of Ethereum

Automatic package approval withheld.

Policy
Main Stage Completion v2

Passed
✓ boundaries valid
✓ media continuity acceptable
✓ package revision current

Needs review
⚠ 1 media item unresolved

[ REVIEW PACKAGE ]
```

The Producer should understand why automation stopped.

---

## 26. Automatic Approval

An automatically approved Session may appear in All Sessions as:

```text
Future of Ethereum

Complete
AUTO-APPROVED

Policy
Main Stage Completion v2

15:02
```

This should be visible but not alarming.

Selecting the Session exposes decision provenance.

---

## 27. Automation Provenance

The Producer should be able to inspect:

* human versus automatic approval,
* policy identity/version,
* decision time,
* reason review was or was not required.

Example:

```text
PACKAGE APPROVAL

Automatic

Policy
Main Stage Completion v2.1

Result
All required evidence satisfied policy.

No human review required.
```

Raw model internals remain secondary.

---

## 28. Automation Metrics

StageFlow may eventually provide trust evidence such as:

```text
AUTOMATION PERFORMANCE

Last 62 reviewed Sessions

Accepted unchanged
61

Human corrections
1

Association corrections
0
```

This belongs under Event/Automation configuration, not the normal Work Queue.

It may support a later human decision to increase automation authority.

StageFlow must never increase its own authority automatically.

---

## 29. Assembly State in the Queue

Session Assembly is a downstream workflow independent of Session Package completeness.

Example:

```text
Future of Ethereum

Session Package
Complete · revision 2

Assembly
Review required · revision 3

Reason
Expected sponsor end card unavailable

[ REVIEW ASSEMBLY ]
```

A branding problem does not reopen the Session Package.

---

## 30. Assembly Auto-Approved

Example:

```text
Future of Ethereum

Package complete
Assembly auto-approved

Template
Main Stage Standard v3

No action required.
```

This belongs in All Sessions.

Not the Work Queue.

---

## 31. Assembly Revisions

A Session may show:

```text
PACKAGE
Revision 2 · Complete

ASSEMBLY
Revision 4 · Approved
```

This distinction must remain visible wherever revision history matters.

The Producer should not infer that Assembly revision 4 means Session Package revision 4.

---

## 32. Branding / Packaging Asset Exceptions

Until the architecture Yellow decision around Packaging Asset identity is settled, UX should refer generically to:

**Packaging Asset**

or product-friendly labels such as:

**Opening Bumper**

**Sponsor End Card**

**Title Graphic**

The UI should not depend on whether the backend eventually reuses Completed Media Asset identity or introduces a separate aggregate.

---

## 33. Intelligence State

Every Session may have a compact intelligence state.

Example:

```text
INTELLIGENCE

Moment Candidates
8

Producer marked
2

Latest
38 sec ago

Generation
Healthy
```

If future transcription/intelligence workers are unavailable:

```text
INTELLIGENCE

Deferred

Worker unavailable

Media capture and Session operation unaffected.
```

Again, no automatic Producer task unless the consequence warrants one.

---

## 34. Intelligence Lag

Where useful:

```text
Moment detection
+41 sec behind live

Transcription
+28 sec behind live
```

This should communicate workflow consequence.

Raw GPU utilization is diagnostic.

---

## 35. Boundary Exclusion Warning

If the Producer adjusts a Session boundary and existing Moment Candidates would fall outside it:

```text
BOUNDARY CHANGE NOTICE

The proposed new Session end excludes:

1 Moment Candidate

14:44:03
Producer marked

[ REVIEW MOMENT ]

[ CONTINUE BOUNDARY CHANGE ]
```

This is contextual information.

A Moment Candidate does not automatically override authoritative Session boundaries.

---

## 36. Session Revision History

All Sessions should provide access to:

```text
HISTORY

Revision 3
Current · Review required

Revision 2
Approved 15:02

Revision 1
Superseded
```

History may include:

* boundary corrections,
* package membership changes,
* completion approvals,
* Assembly revisions separately,
* later automation decisions.

Historical state is read-only.

---

## 37. Event Close Integration

The Work Queue becomes especially important during Event close.

Example:

```text
EVENT CLOSEOUT

Sessions
87 total

Complete
84

Needs review
2

Unresolved
1

Assembly
71 approved
13 pending
3 review required

Moment Candidates
684 generated

Editorial processing
May continue after Event close
```

StageFlow should distinguish:

**safe to stop Event capture operation**

from:

**all downstream Editorial/Assembly work finished**

Those are not the same.

---

## 38. Safe-to-Leave Criteria

The Producer Work Queue should participate in the future Venue Exit check.

Blocking conditions might include:

* active Sessions,
* media still stabilizing where shutdown risks loss,
* unresolved critical media,
* authoritative state not durable,
* reconciliation incomplete.

Non-blocking post-event work might include:

* Moment review,
* transcription backlog,
* Assembly rendering,
* Editorial clip review.

Example:

```text
EVENT CAPTURE WORKFLOW SAFE TO CLOSE

Critical Session/media work is durable.

Post-event work remaining:

42 Moment Candidates awaiting Editorial
8 Assemblies awaiting render
3 transcription operations queued

These may continue after Event capture shutdown.
```

---

## 39. Worker Independence

If the Razer AI worker is offline:

```text
WORKER PROCESSING DEFERRED

Affected:
• transcription
• Moment generation
• future rendering

Unaffected:
• Event/Stage authority
• Session control
• media ingest
• Session package review
```

Producer work should not become blocked unless the requested workflow actually depends on the worker result.

---

## 40. MacBook Client Disconnection

If the Producer MacBook loses connection:

```text
CONNECTION LOST

Queue and Session state may be stale.

Last authoritative update:
14:31:42

Authoritative actions are disabled until refresh completes.
```

After reconnect:

* refresh counts,
* refresh Work Items,
* refresh current Session/package revisions,
* detect actions already performed by another operator.

---

## 41. Multi-Operator Queue Behavior

The queue must assume multiple clients may act.

If another Producer resolves an item:

```text
WORK ITEM RESOLVED

This media association was resolved by another operator.

Current Session state has been refreshed.
```

Do not leave stale actionable controls active.

---

## 42. Queue Item Ownership

Initial Producer UX should not require formal task assignment.

Potential later use:

**Claimed by Producer A**

may help larger operations.

Do not introduce workflow assignment infrastructure until actual event operations justify it.

Acknowledgement, action authority, and task assignment are separate concepts.

---

## 43. Keyboard Workflow

Potential shortcuts:

`W`
Focus Work Queue.

`S`
Switch to All Sessions.

`1–9`
Focus visible item.

`Enter`
Open selected work item.

`Esc`
Return.

`/`
Search.

No authoritative action executes directly from the queue through one keystroke.

---

## 44. Compact Event Mode

During active production, the Producer may want a reduced Sessions panel alongside Mission Control.

Possible drawer:

```text
WORK QUEUE · 3

⚠ Stage C
  Media interruption

◉ Future of Ethereum
  Package ready

◉ Account Abstraction
  1 unresolved media

[ OPEN WORK QUEUE ]
```

This should be optional.

Mission Control remains the primary live surface.

---

## 45. Work Queue Success Test

Within approximately three seconds, the Producer should understand:

* How many things require human action?
* Is any item operationally urgent?
* Which Session/Stage is involved?

Within approximately ten seconds, the Producer should understand:

* Why each item needs a human,
* what StageFlow already knows,
* whether processing continues safely,
* which workflow resolves it.

For a healthy highly automated Event, the ideal queue is:

**No Producer work waiting.**

---

## 46. All Sessions Success Test

Within approximately five seconds, the Producer should be able to determine:

* how many Sessions are active,
* which are assembling,
* which need review,
* which are complete,
* where downstream intelligence/Assembly stands.

Finding a particular Session should require only:

* search,
* Stage filter,
* state filter,

not browsing raw media or technical records.

---

## 47. Explicit Non-Goals

The Producer Sessions & Work Queue surface is not:

* an Editorial Candidate review queue,
* a transcript browser,
* a Marketing asset library,
* a generic task-management application,
* a technical incident log,
* a worker queue,
* a database browser.

Its purpose is:

**Event-wide Session visibility and bounded human Producer responsibility.**

---

## 48. Product Principle

The Work Queue should become smaller as StageFlow becomes more trusted.

Manual mode:

**Human confirms routine work.**

Assisted mode:

**Human approves prepared work.**

Exception-only mode:

**Human sees only doubt and exceptions.**

A mature StageFlow Event should make human attention the exception rather than the processing engine.
