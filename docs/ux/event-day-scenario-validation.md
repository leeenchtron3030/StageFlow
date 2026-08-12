# StageFlow Event-Day UX Scenario Validation Specification

**Status:** Draft v0.1
**Source fidelity:** Exact provided draft.
**Purpose:** Validate the Producer and Editorial UX architecture against realistic concurrent Event-day conditions before higher-fidelity visual design and frontend implementation.

> **Repository interpretation:** This Draft v0.1 is a future UX scenario-validation
> contract, not evidence that the described UI, read models, workers, Editorial
> workflow, Assembly, or automation behavior is implemented or operationally qualified.

---

## 1. Validation Principle

StageFlow UX should be tested against:

**overlap, ambiguity, delay, interruption, recovery, and human attention scarcity**

rather than only ideal sequential workflows.

The question for every scenario is:

> Can each operator understand what is happening, what is theirs to decide, what continues safely, and what requires action without reconstructing internal system state?

---

## 2. Scenario Evaluation Criteria

For each scenario evaluate:

1. **Orientation** — Does the user know Event / Stage / Session context?
2. **Truth** — Does the UI accurately distinguish known, proposed, inferred, external, and declared information?
3. **Consequence** — Is operational impact clear?
4. **Authority** — Is it obvious who may decide?
5. **Preservation** — Is preserved media/history visible where ambiguity exists?
6. **Priority** — Does important work surface without overwhelming the user?
7. **Continuity** — Can the operator continue their current task where appropriate?
8. **Recovery** — Does the interface recover without requiring mental reconstruction?
9. **Cross-role impact** — Are Producer and Editorial consequences separated correctly?
10. **Noise** — Does healthy or non-actionable processing remain quiet?

---

## 3. Scenario A — Normal Multi-Stage Operation

### Situation

Six Stages are active.

All recording sources healthy.

Three Sessions active.

Two between Sessions.

One package assembling.

Moment generation running 30–45 seconds behind live.

No unresolved media.

### Producer

Mission Control should show:

* stable Stage ordering,
* active Sessions,
* media recency,
* compact Moment counts,
* compact intelligence lag,
* no unnecessary Attention items.

Desired global state:

**No intervention required**

### Editorial

Live Triage should show:

* active Sessions,
* Candidate counts,
* any Producer marks,
* normal intelligence lag,
* priority Candidate queue.

### Validation

Healthy operation should look calm.

If the normal six-Stage display feels visually busy or alarming, the design has failed before exceptions occur.

---

## 4. Scenario B — Simultaneous Stage Turnover

### Situation

Stage B:

Previous Session presentation ended.

Its package is still assembling.

Next Session begins.

A new media item arrives without trustworthy interval metadata.

Both Sessions remain plausible owners.

### Producer — Mission Control

Stage B remains in its fixed row.

State:

**REVIEW**

not:

**ERROR**

Moment/intelligence state remains secondary.

### Stage Detail

Show simultaneously:

**PREVIOUS**

Account Abstraction
Package assembling

**CURRENT**

Future of Ethereum
Presentation active

**NEXT**

Next Program Expectation

Association notice:

**1 media item cannot be safely assigned.**

**Media is preserved.**

### Producer Work Queue

One review item:

**Media association requires review**

### Editorial

Existing Candidate review continues.

No Editorial Candidate is deleted or shifted because media ownership is unresolved.

If current Candidate source is affected:

show:

**Source package still assembling**

not invalidation unless actually known.

### Validation

The UX must not implicitly prefer the new active Session merely because it is current.

---

## 5. Scenario C — Producer Marks a Moment During Editorial Review

### Situation

Editorial is reviewing a Candidate from Main Stage.

Producer on Stage B hears an important statement and presses:

**MARK MOMENT**

### Producer

Immediate confirmation:

**Moment marked · 18:42**

Producer continues Stage operation.

No modal workflow.

### Editorial

Current media playback remains untouched.

A visible notice appears:

**◆ New Producer Mark — Stage B**

Actions:

**Review Next**

**Keep Current Review**

The Stage B Candidate rises in queue priority.

### Validation

Human signal receives high priority without stealing editorial context.

---

## 6. Scenario D — Several Producer Marks Arrive Quickly

### Situation

Three Producers or operators mark Moments across two Stages within 90 seconds.

Editorial has one operator.

### Editorial Queue

Do not generate three interrupting modals/toasts.

Instead:

**3 new Producer marks**

Priority queue shows each Session/time.

Oldest high-priority wait becomes visible.

### Editorial Capacity

Example:

**Priority Moments waiting: 4**

**Oldest: 2m 11s**

### Producer

Mission Control does not display Editorial panic.

At most:

**Editorial priority queue growing**

if policy says this has meaningful downstream impact.

### Validation

StageFlow should aggregate attention rather than amplify it.

---

## 7. Scenario E — AI Worker Stops During Active Sessions

### Situation

Razer/reference worker disappears.

Recording and PostgreSQL remain healthy.

Transcription and Moment generation stop progressing.

### Producer — Mission Control

Infrastructure:

**AI Workers 0 / 1**

Consequence:

**Moment detection deferred**

**Transcription deferred**

Explicitly state:

**Session control and media capture continue normally.**

Stage rows remain healthy unless production itself is affected.

### Editorial

Existing transcripts/Candidates remain usable.

Header:

**INTELLIGENCE DEFERRED**

New intelligence paused.

Recorded media remains available.

### Work Queue

No Producer Work Item merely because the worker stopped unless policy requires a human decision.

### Validation

Worker health must not visually masquerade as production failure.

---

## 8. Scenario F — Worker Returns With Backlog

### Situation

Worker returns after eight minutes.

It begins catching up.

### Producer

Show consequence:

**Moment detection +8m 04s behind**

then decreasing.

Avoid a flood of recovered/success messages.

### Editorial

Clearly distinguish:

**Intelligence backlog**

from:

**Editorial review backlog**

Example:

Moment detection:
+6m 21s

Editorial:
Caught up with available Candidates

### Validation

Recovery should be visible without creating unnecessary human work.

---

## 9. Scenario G — PostgreSQL Becomes Unavailable

### Situation

Authoritative PostgreSQL connection fails during live Event operation.

Recording filesystem continues independently.

### Producer

Global intervention state:

**AUTHORITATIVE CONTROL UNAVAILABLE**

Affected:

* Session authority,
* authoritative package changes,
* Producer commands.

Unaffected where truthful:

* primary recording,
* media already written externally.

Authority-changing controls disabled.

Mission Control remains visible with stale/current-state labeling.

### Editorial

Existing locally/readably available context may remain visible if architecture allows.

Any action requiring authoritative persistence is disabled.

### Validation

The UI must communicate serious authority loss without suggesting primary recordings stopped unless that is actually known.

---

## 10. Scenario H — PostgreSQL Returns

### Situation

Database connection returns.

Fresh reconciliation has not yet completed.

### Producer

State:

**RECOVERING**

Not:

**READY**

Message:

**Connection restored. Fresh reconciliation required before authoritative actions resume.**

### After reconciliation succeeds

Return quietly to normal state.

A brief confirmation may appear:

**Authoritative state restored**

but no large success workflow.

### Validation

Availability and readiness remain distinct.

---

## 11. Scenario I — MacBook Loses Network, Backend Continues

### Situation

Producer MacBook disconnects from StageFlow network for 45 seconds.

The backend continues operating.

Another operator may make changes.

### Producer Client

Display:

**CONNECTION LOST**

Last authoritative update:
14:31:42

Actions disabled.

Do not erase existing Event context.

### Reconnect

Refresh:

* active Sessions,
* Work Queue,
* package revisions,
* Attention,
* current Stage state.

If another operator acted:

**State updated while you were disconnected.**

### Validation

Client failure must not appear equivalent to backend failure.

---

## 12. Scenario J — Two Producers Act on Same Work Item

### Situation

Producer A and Producer B both open the same unresolved media association.

Producer A resolves it first.

### Producer B

Before action proceeds:

**WORK ITEM RESOLVED**

Resolved by another operator.

Current Session state refreshed.

Controls disappear or update.

### Validation

No stale action path should silently overwrite newer authority.

---

## 13. Scenario K — Session Ends While Editorial Is Behind Live

### Situation

Session ends at 39:44.

Editorial is reviewing Candidate at 24:16.

### Editorial

Do not jump to Session end.

Current playback remains 24:16.

Header changes:

**SESSION ENDED**

You are reviewing 15m 28s before Session end.

Candidate queue continues accumulating until intelligence catches up.

### Validation

Session lifecycle changes should not steal editorial review position.

---

## 14. Scenario L — Session Ends but Intelligence Is Still Processing

### Situation

Presentation ended.

Package assembling.

Transcript caught up.

Moment generation remains 3 minutes behind.

### Editorial

Show:

Session:
**Ended**

Package:
**Assembling**

Transcript:
**Caught up**

Moment detection:
**+3m 02s**

The editor may continue reviewing.

Do not show:

**Editorial Ready**

as a single misleading global status.

### Validation

Independent workflow dimensions remain visible.

---

## 15. Scenario M — Package Becomes Ready During Editorial Review

### Situation

Editorial began reviewing live.

Producer later approves Session package revision 1.

### Editorial

Subtle update:

**Source package approved · revision 1**

Existing work remains in place.

No forced refresh unless source mapping materially changed.

### Validation

Routine upstream stabilization should increase confidence without interrupting downstream work.

---

## 16. Scenario N — Package Reopened After Editorial Approval

### Situation

Editorial approved three Candidate Moments.

Producer package revision 1 was complete.

Late relevant media creates package revision 2.

### Producer

Work Queue:

**Package revision 2 requires review**

Prior approval preserved.

### Editorial

Banner:

**SOURCE PACKAGE UPDATED**

3 approved Clips checked:

* 2 unaffected
* 1 needs source revalidation

Do not invalidate all Editorial work.

### Cross-role

Producer and Editorial see different work generated from the same change.

### Validation

Revision impact must be scoped, not catastrophic.

---

## 17. Scenario O — Boundary Correction Excludes Producer-Marked Candidate

### Situation

A Producer corrects Session end earlier.

One Producer-marked Candidate now lies outside current authoritative Session boundary.

### Producer Package Review

Before committing boundary change:

**1 Moment Candidate would fall outside the new Session boundary.**

Actions:

**Review Moment**

**Continue Boundary Change**

Candidate does not veto Producer authority.

### Editorial

After correction:

**Candidate preserved**

**Outside current authoritative Session boundary**

Requires Editorial review.

### Validation

Preserve human signals without allowing them to override Session authority implicitly.

---

## 18. Scenario P — Candidate Flood From Model

### Situation

A poorly calibrated model generates 30 Candidates during one Session.

Most are weak.

### Editorial Queue

Do not show 30 equally prominent tasks.

Presentation should use:

* ranking,
* grouping,
* Candidate strength,
* temporal clusters,
* unreviewed count.

Example:

**30 Candidates**

**5 priority**

**11 related to 3 clusters**

### Producer

Mission Control may still show:

`✦ 30`

but does not generate Producer Attention.

### Validation

AI output volume must not directly become human interruption volume.

---

## 19. Scenario Q — Editorial Finds a Moment AI Missed

### Situation

Deep review transcript reveals an important statement with no Candidate.

### Editorial

Select transcript/time range.

Action:

**CREATE CANDIDATE**

Origin:

**DECLARED · Editorial**

Review may proceed normally.

### Validation

AI suggestions never define the upper boundary of Editorial capability.

---

## 20. Scenario R — Transcript Is Wrong but Media Is Fine

### Situation

Candidate is correctly identified.

Transcript contains a significant transcription error.

### Editorial

Show transcript uncertainty/correction capability where available.

Media remains authoritative review context.

Candidate approval does not require transcript accuracy unless downstream workflow specifically does.

### Validation

Text intelligence must not displace media truth.

---

## 21. Scenario S — Speaker Identity Unknown in Panel

### Situation

Panel has four participants.

Diarization cannot determine current speaker.

### Editorial

Candidate remains reviewable.

Display:

**Speaker unknown**

Panel participant list remains available.

Do not suppress Candidate or invent speaker assignment.

### Validation

Metadata uncertainty reduces automation, not preservation/access.

---

## 22. Scenario T — Assembly Branding Asset Missing

### Situation

Session package is complete.

Assembly Template requires sponsor outro.

Required asset unavailable.

### Producer

Session remains:

**Package Complete**

Assembly:

**Review Required**

Reason:

**Sponsor End Card unavailable**

Work Queue receives Assembly review item when capability exists.

### Editorial

Candidate/Clip workflow continues.

### Validation

Downstream packaging problems do not rewrite capture truth.

---

## 23. Scenario U — Assembly Auto-Approved

### Situation

Trusted Assembly policy passes every check.

### Producer

All Sessions:

**Package Complete**

**Assembly Auto-Approved**

No Work Queue item.

Automation provenance available on inspection.

### Validation

Correct automation removes work rather than creating a success task.

---

## 24. Scenario V — Automatic Package Approval Withheld

### Situation

Exception-only policy enabled.

All checks pass except one unresolved media item.

### Producer

Work Queue item:

**Automatic approval withheld**

Reason:
1 unresolved media item.

Show passed checks and failed condition.

Do not say:

**Automation failed**

### Validation

Correct refusal to automate is represented as successful policy behavior.

---

## 25. Scenario W — 100 Sessions Over Event Day

### Situation

Event includes 100 Sessions across several Stages.

85 complete.

4 active.

5 assembling.

3 review required.

3 expected.

### Mission Control

Only current Stage operation.

### All Sessions

Bounded/filterable dense list.

### Producer Work Queue

Only actual unresolved human responsibility.

Perhaps 4 items.

Not 100.

### Editorial

Candidate queue may contain hundreds of records but is filtered/ranked/paginated.

### Validation

Scale does not transform Session count into task count.

---

## 26. Scenario X — Editorial Team Falls Behind

### Situation

Three live Stages.

One editor.

Priority Candidates accumulating faster than review.

### Editorial

Show:

**EDITORIAL BACKLOG GROWING**

Priority waiting:
8

Oldest:
6m 14s

Intelligence:
Healthy

### Producer

Do not automatically create intervention.

Possible compact awareness later:

**Editorial behind live**

only when useful.

### Validation

Human capacity conditions remain distinct from production/system faults.

---

## 27. Scenario Y — Event Capture Ends With Large Editorial Backlog

### Situation

All Sessions finished.

Production media durable.

Reconciliation complete.

No critical unresolved capture work.

Editorial has 180 Candidates remaining.

Rendering queue also remains.

### Producer Closeout

Show:

**EVENT CAPTURE WORKFLOW SAFE TO CLOSE**

Post-event work remaining:

* 180 Editorial Candidates
* 12 transcription operations
* 9 renders

These do not block capture closeout.

### Editorial

Application transitions naturally to Review Queue / post-event mode.

### Validation

Safe-to-leave and all-work-complete are not conflated.

---

## 28. Scenario Z — Cloud Connectivity Lost in Event Mode

### Situation

Internet goes offline.

Local processing policy remains active.

### Producer

Infrastructure:

**Internet unavailable**

Policy consequence:

**Cloud enrichment deferred**

Local Event operation continues.

Do not show broad red Event error.

### Editorial

If local transcription/Moment detection remains operational:

**LOCAL INTELLIGENCE ACTIVE**

**Cloud enrichment deferred**

### Validation

Expected Event Mode behavior does not look like failure.

---

## 29. Compound Scenario — Realistic Pressure Test

### Situation

At 14:32:

* Main Stage Session active.
* Stage B is in turnover.
* Stage C source unavailable.
* Producer marks an important Main Stage Moment.
* Editorial is six minutes behind reviewing Stage B.
* AI worker is three minutes behind live.
* one previous completed package has reopened.
* internet is offline by Event policy.
* PostgreSQL remains healthy.

### Producer Mission Control should communicate approximately:

**1 intervention**

Stage C source unavailable.

**2 reviews**

Stage B media association.
Reopened package.

Main Stage remains healthy.

Moment processing:

+3m behind.

Cloud enrichment:

Deferred.

Producer mark does not become production Attention.

### Editorial should communicate:

Current review preserved.

New Producer mark available and prioritized.

Intelligence +3m behind.

Cloud enrichment deferred.

Existing Candidate work remains available.

### Validation

The interface must separate:

* production intervention,
* review work,
* human editorial priority,
* processing delay,
* expected policy deferral

without turning all five into equivalent red alerts.

This compound scenario is one of the most important StageFlow UX tests.

---

## 30. Failure Criteria

The UX should be considered unsuccessful if scenarios routinely cause:

* healthy Stage rows to turn critical due only to AI delay,
* Work Queue entries for non-actionable processing,
* Candidate floods to produce equivalent human alerts,
* current Editorial playback to jump when new work arrives,
* Program Expectations to look like realized Sessions,
* proposed boundaries to look authoritative,
* package revisions to erase prior approval history,
* downstream changes to reopen unrelated upstream authority,
* worker failure to imply capture failure,
* client disconnection to imply backend failure,
* database reconnection to imply readiness before reconciliation,
* Event closeout to wait for noncritical Editorial backlog,
* one generic `Session Complete` state to hide independent workflows.

---

## 31. Scenario-Driven Component Requirements

The scenario pass confirms likely need for reusable components such as:

* Global Authority Banner
* Stale State Overlay
* Recovering State Banner
* Consequence Block
* Work Item Row
* Stage Operational Row
* Session Row
* Candidate Row
* Lag Indicator
* Producer Mark Indicator
* Review State
* Revision Summary
* Package Impact Summary
* Provenance Inspector
* Timeline Boundary Marker
* Candidate Marker
* Unplaced Media Lane
* Automation Decision Summary
* Downstream Impact Summary

Exact frontend components remain implementation work.

---

## 32. Scenario-Driven Read Model Requirements

Future projections likely need to support:

* active/recent Stage state,
* unresolved Producer Work,
* Session package status/revision,
* Moment counts and Producer-mark counts,
* intelligence lag by capability,
* Editorial human review lag,
* package revision downstream impact,
* Assembly state,
* worker consequence,
* reconciliation/readiness,
* bounded Event closeout summary.

These remain capability/read-model requirements, not Kernel redesign.

---

## 33. Scenario-Driven Interaction Requirements

Future frontend should preserve:

* stable list ordering while selected,
* current review/playback position,
* filter/scroll context after deep navigation,
* explicit stale-action gating,
* current revision freshness,
* multi-operator concurrency response,
* no forced navigation on incoming Candidate,
* no modal for lightweight Mark Moment,
* explicit confirmation for authority changes.

---

## 34. Operational Review Questions

The scenario pass leaves a small number of questions where actual production practice matters more than abstract design.

These should be reviewed with experienced Event operations before higher-fidelity UI is locked.

#### A. Editorial Staffing

Which is closest to normal reality?

1. One editor covering several Stages.
2. One editor primarily per Stage.
3. Hybrid: some dedicated priority Stages plus pooled Editorial coverage.
4. Editorial mostly works after Sessions rather than live.

#### B. Producer Mark Urgency

When a Producer manually marks a Moment, should Editorial normally treat it as:

1. highest-priority next review,
2. high priority but below current work,
3. merely a strong signal among others?

#### C. Near-Live Turnaround

What practical target matters?

Examples:

* under 2 minutes,
* under 5 minutes,
* under 10 minutes,
* primarily post-Session,
* Event-dependent.

#### D. Mission Control Intelligence Density

How much Editorial/AI state does a Producer actually want visible during a real show?

Potential range:

* Candidate count only,
* Candidate + lag,
* Candidate + lag + Editorial backlog,
* richer downstream status.

#### E. Event Closeout

Which downstream activities should actually prevent the technical team from considering StageFlow safe to shut down or leave venue?

---

## 35. Gate to Higher-Fidelity Design

Do not lock higher-fidelity information density or alert hierarchy until the operational questions above have been reviewed.

The overall navigation, role separation, Session-centered temporal model, provenance model, and authority model do not require reopening.

The review should tune:

* staffing assumptions,
* prioritization,
* timing expectations,
* Mission Control density,
* closeout criteria.

---

## 36. Scenario Validation Principle

The desired StageFlow behavior under pressure is:

**Preserve context.**

**Preserve media.**

**Preserve history.**

**Protect human attention.**

**Escalate only the decision that actually needs a human.**
