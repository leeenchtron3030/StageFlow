# StageFlow Editorial Event Queue & Live Triage UX Specification

**Status:** Draft v0.1
**Source fidelity:** Exact chat draft.
**Persona:** Editorial
**Context:** Multi-stage live conference operation and post-Session review
**Purpose:** Help a small Editorial team monitor, triage, and review Candidate Moments across many simultaneous Sessions without requiring continuous live viewing of every Stage.

> **Repository interpretation:** This draft records UX/product direction for
> post-Kernel planning. The current Editorial bounded context is reserved only; no
> Editorial queue, Temporal Workspace, candidate-review persistence, or Editorial UI
> is implemented. Review-completeness authority and downstream Assembly, rendering,
> and Marketing examples remain future or decision-gated. Presentation clustering does
> not merge durable Candidate identities.

---

## 1. Primary User Question

The Editorial Event Queue answers:

**Where is the most valuable editorial work right now?**

Secondary questions:

* Which Sessions are live?
* Which Sessions have new Moment Candidates?
* Which Moments were manually marked by a Producer?
* Which Sessions are ready for deeper review?
* Which Editorial work is falling behind?
* Which Sessions have already been sufficiently reviewed?
* Which intelligence pipelines are delayed?
* What can wait?

---

## 2. Core Operating Principle

Editorial should not be expected to watch every Stage continuously.

StageFlow exists partly to remove that requirement.

The system should continuously observe Sessions and create structured editorial signals so a small Editorial team can work by:

**priority → context → judgment**

rather than:

**Stage monitor → Stage monitor → Stage monitor**

---

## 3. Two Editorial Modes

The Event Queue supports two operational modes:

### Live Triage

Used while Sessions are still happening.

Primary goal:

**Find important moments quickly enough to support near-live downstream workflows.**

### Review Queue

Used after or between Sessions.

Primary goal:

**Systematically complete Editorial review of accumulated Candidate Moments.**

These modes share one underlying queue and state model.

They differ mainly in ordering, density, and urgency.

---

## 4. Primary Layout

Conceptual layout:

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ STAGEFLOW · EDITORIAL                         DEVCON 202X     LIVE         │
├────────────────────────────────────────────────────────────────────────────┤
│ [ LIVE TRIAGE ]   [ REVIEW QUEUE ]   [ APPROVED ]                        │
│                                                                            │
│ Editorial lag: 2m 18s     Intelligence health: Good                       │
├────────────────────────────────────────────────────────────────────────────┤
│ PRIORITY NOW                                                               │
│                                                                            │
│ ◆ Stage B · Future of Ethereum                                             │
│   Producer-marked moment · 00:18:42                                        │
│   “The breakthrough was realizing…”                                        │
│   Candidate context ready                                     [ REVIEW ]  │
│                                                                            │
│ ✦ Main Stage · Scaling Ethereum                                            │
│   Strong candidate · 00:27:11                                              │
│   Multi-signal suggestion                                     [ REVIEW ]  │
├────────────────────────────────────────────────────────────────────────────┤
│ LIVE SESSIONS                                                              │
│                                                                            │
│ Stage B        Future of Ethereum      8 candidates   4 unreviewed         │
│ Main Stage     Scaling Ethereum        5 candidates   2 unreviewed         │
│ Workshop A     ZK Security             3 candidates   3 unreviewed         │
│ Workshop B     Between Sessions        —              —                    │
├────────────────────────────────────────────────────────────────────────────┤
│ READY FOR DEEP REVIEW                                                      │
│                                                                            │
│ Account Abstraction     11 candidates · 7 unreviewed          [ OPEN ]     │
│ DAO Governance           6 candidates · 2 unreviewed          [ OPEN ]     │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Editorial Queue Is Not the Producer Queue

Producer Work Queue contains:

* authoritative Session decisions,
* media ambiguity,
* package approval,
* Assembly exceptions,
* policy exceptions.

Editorial Queue contains:

* Candidate Moment review,
* Producer marks,
* deferred Editorial judgments,
* approved Editorial Clip follow-up,
* review-completeness work.

The two queues may reference the same Session but represent different responsibilities.

---

## 6. Priority Now

The top of Live Triage should show only the most actionable editorial opportunities.

Likely priority order:

1. Producer-marked Moment Candidate
2. Explicitly high-priority Editorial mark
3. Strong multi-signal candidate
4. New live candidate with high editorial relevance
5. Candidate approaching downstream timing deadline
6. Ordinary unreviewed candidate

The queue should not simply sort by AI score.

---

## 7. Producer Marks

Producer marks should be highly visible because they represent an experienced human noticing something during the live show.

Example:

```text
◆ PRODUCER MARK

Future of Ethereum
Stage B

Session time
18:42

Marked 36 sec ago

Optional note
“Major announcement”

[ REVIEW ]
```

Producer marks should normally appear ahead of ordinary machine-generated candidates.

---

## 8. Live Session Row

Each live Session should show:

* Stage
* Session title
* elapsed time
* Candidate count
* Producer-mark count
* unreviewed count
* intelligence lag
* Editorial review lag
* current review status

Example:

```text
Stage B
Future of Ethereum

LIVE · 27:18

Candidates       8
Producer marks   2
Unreviewed       4
Moment detection +34s

[ OPEN SESSION ]
```

---

## 9. Editorial Review Lag

Editorial lag means:

**How far behind the available candidate stream the human Editorial workflow is.**

This is different from:

* transcription lag,
* Moment-detection lag,
* media ingest lag.

Example:

```text
INTELLIGENCE

Transcript
+24 sec

Moment detection
+39 sec

EDITORIAL

Oldest priority candidate awaiting review
2m 18s
```

This helps distinguish compute delay from human workload.

---

## 10. No Forced Live Edge

If an editor opens a Candidate at Session time 18:42 while the Session is already at 27:10, StageFlow must not pull them forward automatically.

Display:

**You are 8m 28s behind live**

with:

[ RETURN TO LIVE ]

Editorial owns its review position.

---

## 11. Candidate Arrival During Review

New candidates should enter the queue without interrupting current playback.

Example notification:

**3 new candidates**

not:

automatic navigation to the newest candidate.

A Producer mark may receive stronger visual prominence, but should still not destroy current editing context.

---

## 12. Queue Stability

Candidate ordering should remain stable while a user is actively interacting.

Avoid rows constantly jumping as scores change or new data arrives.

Recommended behavior:

* new items enter at controlled boundaries,
* currently selected item remains fixed,
* explicit refresh/reorder indicator when necessary.

---

## 13. Review Queue Mode

Post-Session Review Queue should emphasize completeness rather than live urgency.

Example:

```text
REVIEW QUEUE

Future of Ethereum
8 candidates
6 reviewed
2 unreviewed
2 approved
[ CONTINUE REVIEW ]

Scaling Ethereum
11 candidates
11 reviewed
4 approved
Review complete
[ VIEW ]

DAO Governance
7 candidates
4 reviewed
3 unreviewed
[ CONTINUE ]
```

---

## 14. Session Editorial Progress

Useful states:

* Not started
* Live triage active
* Review in progress
* Deferred
* Review complete

These are Editorial workflow states.

They must not replace Producer Session/package lifecycle.

---

## 15. Candidate State

Candidate states may include:

* Unreviewed
* Reviewing
* Approved
* Rejected
* Deferred

Optional future states:

* Needs follow-up
* Sensitive / do not use
* Duplicate/related

Do not invent additional durable states unless product behavior requires them.

---

## 16. Review Completeness

StageFlow should eventually allow Editorial to declare:

**Review complete**

only when applicable Editorial policy is satisfied.

For example:

* all required candidates reviewed,
* no mandatory deferred items remain,
* no unresolved editorial conflict exists.

The exact authority model is future architecture.

The UX should reserve the concept without assuming implementation.

---

## 17. Strong Candidate Presentation

Avoid raw probability as the primary representation.

Prefer:

```text
STRONG CANDIDATE

Signals:
• Producer mark nearby
• Strong semantic significance
• Speaker emphasis
• Self-contained statement
```

Model confidence may appear deeper.

---

## 18. Candidate Preview

Queue rows may include a very short transcript excerpt:

```text
“The breakthrough was realizing that the validator
doesn't need to…”

18:42 · 38 sec
```

Do not show large transcript blocks in the queue.

Context belongs in the Temporal Workspace.

---

## 19. Fast Triage Actions

For obvious cases, Editorial should be able to perform:

* Approve
* Reject
* Defer

without opening the full Temporal Workspace.

However, any fast action should offer enough context to avoid blind review.

Example expandable preview:

[ PLAY 10 SEC CONTEXT ]

[ APPROVE ] [ REJECT ] [ DEFER ]

---

## 20. Deep Review Routing

Selecting:

**REVIEW**

opens the Session Temporal Workspace focused at that Candidate.

The Event Queue should preserve:

* filter,
* position,
* current queue mode,
* scroll position.

Returning from Session review should not reset the operator’s place.

---

## 21. Editorial Clip State

Approved Candidate Moments may show downstream clip state:

```text
✓ APPROVED

Editorial Clip
Created

Render
Not requested
```

The Event Queue should not become a render-management surface.

---

## 22. Multiple Candidate Signals

If several detections refer to essentially the same moment:

```text
3 signals around 18:42

◆ Producer mark
✦ Semantic model
✦ Speaker emphasis
```

Queue them as one review cluster when possible at the presentation layer.

Durable candidate merge remains deferred unless architecture later authorizes it.

---

## 23. Cross-Session Candidate Ranking

Ranking across Sessions should consider editorial operations, not just model score.

Potential inputs:

* Producer mark
* Session priority
* event track priority
* candidate strength
* downstream deadline
* age
* already reviewed nearby content
* diversity/redundancy

Do not let model relevance alone monopolize the queue.

---

## 24. Session Priority

Editorial may need to prioritize certain Sessions:

* keynote,
* sponsor Session,
* major announcement,
* high-profile speaker,
* specific track.

This should eventually come from explicit Event/editorial policy.

Avoid hidden prioritization.

---

## 25. Live Triage Capacity

The interface should show whether Editorial demand is exceeding current human capacity.

Example:

```text
EDITORIAL LOAD

Priority candidates waiting
8

Oldest priority wait
6m 14s

Editors active
2

Status
Falling behind
```

This is operational Editorial information.

It may later be visible in Producer infrastructure/workflow status at a higher level.

---

## 26. Intelligence Backlog

Example:

```text
INTELLIGENCE DELAY

Moment detection is 9m behind live.

12 Sessions affected.

Existing candidates remain available.
```

Do not confuse this with human Editorial backlog.

---

## 27. Worker Failure

If the AI worker disappears:

```text
INTELLIGENCE DEFERRED

New transcript and Moment analysis paused.

Recorded Session media remains available.

Editorial can continue reviewing existing candidates.
```

No loss of existing review state.

---

## 28. Manual Editorial Discovery

An editor watching a Session may mark a new moment even if no Candidate exists.

Action:

**MARK MOMENT**

creates an Editorial-origin candidate.

This should appear in the queue as human Editorial provenance.

---

## 29. Candidate Rejection Speed

For rapid live triage, reject should require minimal friction.

Optional reasons may be captured quickly:

* Duplicate
* Not interesting
* Needs too much context
* Poor technical quality
* Other

But a reason should not be mandatory initially.

Operational speed matters.

---

## 30. Deferral

Deferral should support:

* review after Session end,
* needs more context,
* waiting for transcript,
* waiting for package stabilization.

Example:

```text
DEFER UNTIL

○ Session ends
○ Transcript caught up
○ Manual review later
```

The exact automation mechanics may remain future work.

---

## 31. Editorial Notifications

Notifications should be sparse.

Appropriate triggers:

* Producer mark
* major intelligence backlog
* Session package changed while being reviewed
* downstream deadline approaching
* worker unavailable

Ordinary machine candidates should not each trigger a notification.

---

## 32. Filtering

Useful filters:

### Review state

* Unreviewed
* Approved
* Rejected
* Deferred

### Origin

* Producer marked
* AI suggested
* Editorial marked

### Session

* Live
* Ended
* Complete

### Stage

Configured Stages.

### Priority

* Priority
* Normal

---

## 33. Search

Search may match:

* Session title
* participant
* organization
* transcript text later
* topic/tag
* Editorial note

Search should return Candidate/Session context rather than disconnected text fragments.

---

## 34. Multi-Editor Concurrency

Queue state must tolerate several Editorial users.

If another editor reviews a Candidate:

```text
UPDATED

Editor B approved this Moment.

[ VIEW DECISION ]
```

No stale duplicate approval should silently overwrite current state.

---

## 35. Optional Candidate Claiming

For larger Editorial teams, future workflow may support:

**Reviewing — Editor A**

This should be soft coordination, not a hard lock unless operational experience demands one.

Do not add task-claim infrastructure prematurely.

---

## 36. Review Throughput Metrics

Useful operational metrics later:

* candidates reviewed/hour,
* median review delay,
* Producer-mark response time,
* approved percentage,
* deferred backlog.

These are Editorial operations metrics.

They should not dominate the review interface.

---

## 37. Event-Level Review Summary

Example:

```text
EDITORIAL TODAY

Sessions
87

Candidates
684

Reviewed
502

Approved
143

Rejected
329

Deferred
30

Unreviewed
182
```

This helps lead Editorial understand overall progress.

---

## 38. Event Close Behavior

Event capture can close while Editorial work remains.

Example:

```text
EVENT CAPTURE CLOSED

Editorial work continues.

182 Candidate Moments remain unreviewed.
37 Editorial Clips approved.
```

The UI must not treat this as an Event-close failure.

---

## 39. Post-Event Mode

After Event close:

* live urgency disappears,
* queue prioritizes completion,
* Sessions become review units,
* intelligence may continue processing,
* cloud enrichment may resume according to policy.

The same Editorial workspace should transition naturally.

---

## 40. Near-Live Content Objective

StageFlow should support a future workflow where high-value moments can move rapidly:

**Candidate**

→ **Editorial approval**

→ **Editorial Clip**

→ **Assembly/render**

→ **Marketing**

during the Event.

But live speed must not require sacrificing provenance or human authority.

---

## 41. Editorial Event Queue Success Test

Within approximately five seconds, an Editorial operator should know:

* which Sessions are live,
* whether intelligence is keeping up,
* which Candidate deserves attention next,
* whether a Producer manually marked something important.

Within approximately ten seconds, they should be able to start reviewing the highest-priority Moment.

A small Editorial team should not need to watch every Stage continuously to remain effective.

---

## 42. Explicit Non-Goals

The Editorial Event Queue is not:

* a Producer incident queue,
* a media ingest monitor,
* a worker scheduler,
* a render queue,
* a publishing calendar,
* a generic project-management system.

Its purpose is:

**editorial prioritization across Sessions.**
