# StageFlow Cross-Role Session Experience Model

**Status:** Draft v0.1
**Source fidelity:** Exact chat draft.
**Personas:** Producer, Editorial, Marketing
**Purpose:** Define how the same authoritative Session is presented differently to operational roles without overloading one global status or allowing role-specific workflows to rewrite each other's authority.

> **Repository interpretation:** This draft records UX/product direction for
> post-Kernel planning. The Kernel currently owns the single authoritative realized
> Session and package lineage; Editorial, Assembly, Rendering, Marketing, cross-role
> queues, and persona workspaces are not implemented. Participant identity and
> descriptive-metadata authority remain future architecture decisions.

---

## 1. Core Principle

There is one authoritative realized Session.

Different roles operate on different dimensions of that Session.

Therefore:

**Session identity is shared.**

**Workflow state is role-specific.**

Do not create separate Producer Session, Editorial Session, and Marketing Session identities.

---

## 2. Shared Session Identity

All personas refer to the same:

* Session ID,
* Event,
* Stage,
* authoritative start,
* authoritative end,
* participant context,
* Program Expectation linkage where present,
* package revision lineage.

Role-specific objects reference this Session.

---

## 3. Independent Workflow Dimensions

A Session may simultaneously have:

### Production

Package Complete · revision 2

### Intelligence

12 Moment Candidates

### Editorial

4 Editorial Clips approved

### Assembly

Approved · revision 3

### Rendering

2 outputs ready

### Marketing

1 asset scheduled

These states are related.

They are not one lifecycle.

---

## 4. Why One Master Status Is Dangerous

A label such as:

**Complete**

could mean:

* presentation ended,
* package approved,
* Editorial review complete,
* Assembly approved,
* render finished,
* publishing finished.

Therefore StageFlow should never expose an ambiguous global:

**Session = Complete**

without context.

Use:

**Package Complete**

**Editorial Review Complete**

**Assembly Approved**

**Render Complete**

instead.

---

## 5. Producer View

Producer primarily sees:

* Stage/session authority,
* media completeness,
* package revision,
* unresolved/conflicting media,
* Assembly exceptions,
* high-level intelligence activity,
* downstream backlog only where operationally relevant.

Example:

```text
Future of Ethereum

PACKAGE
Complete · revision 2

INTELLIGENCE
8 Moment Candidates

ASSEMBLY
Approved

EDITORIAL
Ready
```

Producer should not ordinarily see detailed Candidate review decisions.

---

## 6. Editorial View

Editorial primarily sees:

* authoritative Session/package basis,
* media playback,
* transcript/intelligence,
* Candidate Moments,
* Producer marks,
* Editorial decisions,
* Editorial Clips,
* package revision impacts.

Example:

```text
Future of Ethereum

SOURCE PACKAGE
Complete · revision 2

CANDIDATES
8

APPROVED
3

UNREVIEWED
2

ASSEMBLY
Available for context
```

Production infrastructure should remain secondary.

---

## 7. Marketing View

Marketing primarily sees approved downstream material.

Example:

```text
Future of Ethereum
Alice Smith · Example Foundation

APPROVED EDITORIAL CLIPS
3

RENDERED ASSETS
2

READY FOR DISTRIBUTION
2
```

Raw Moment Candidates should normally be hidden.

Marketing should not make Producer package decisions or Editorial Candidate judgments.

---

## 8. Session Package as Shared Foundation

The Producer-approved/current Session Package provides the trusted media foundation for downstream work.

Editorial may begin early against an in-progress package, but should always know which package revision its work references.

Marketing should generally consume outputs based on a sufficiently stable/approved package.

---

## 9. Revision Propagation

When the Producer creates a new package revision:

StageFlow should determine downstream impact rather than invalidating everything blindly.

Potential outcomes:

### Unaffected

Candidate/Clip media remains valid.

### Needs Revalidation

Relevant source media changed.

### Outside New Boundary

Candidate now lies outside authoritative Session range.

### Missing Source

Clip references media removed from current package.

Each downstream object should preserve its historical basis.

---

## 10. Editorial Decisions Do Not Change Production Truth

Editorial may:

* approve Candidate,
* reject Candidate,
* adjust clip range,
* add notes,
* tag topics.

Editorial must not silently change:

* Session Stage,
* authoritative Session start/end,
* package membership,
* package completion.

If Editorial discovers a production problem, it should raise a correction request/work item to Producer authority.

---

## 11. Producer Decisions Do Not Rewrite Editorial History

If Producer later corrects a boundary or media assignment:

StageFlow preserves prior Editorial actions and reports impact.

Do not erase:

* rejected Candidates,
* approved Clips,
* Editorial notes,
* review provenance.

---

## 12. Marketing Cannot Change Editorial Authority

Marketing may later:

* select approved assets,
* adapt copy,
* choose channels,
* schedule/publish.

Marketing should not silently convert a rejected Candidate into an approved Editorial Clip.

If Marketing requests another Moment, that should create an Editorial request/workflow.

---

## 13. Moment Candidate Ownership

Candidate Moment belongs to the Editorial intelligence domain.

Origins may include:

* AI/model,
* deterministic signal,
* Producer mark,
* Editorial mark.

Editorial review owns final Candidate disposition.

Producer visibility does not imply Producer ownership.

---

## 14. Editorial Clip

An Editorial Clip is the first human Editorial-approved downstream content object.

It should reference:

* Session,
* package revision basis,
* approved range,
* originating Candidate/evidence,
* Editorial decision.

This becomes a clean boundary for later Marketing/render workflows.

---

## 15. Assembly Independence

Session Assembly references an approved/current Session package revision.

Assembly may include:

* opening branding,
* title graphics,
* Session content,
* outro,
* sponsor media.

Changing Assembly branding:

**does not alter Session truth**

and:

**does not alter Editorial Session-relative Moment time**

---

## 16. Session-Relative Time as Shared Temporal Currency

Canonical editorial timing should use:

**Session-relative time**

This allows:

* Candidate Moments,
* Editorial Clips,
* transcript references,
* topic segments

to remain stable across Assembly changes.

Derived Assembly/render time may differ.

---

## 17. Participant Metadata

Shared descriptive Session metadata may include:

* participant name,
* organization/affiliation,
* participant role,
* ordering.

Producer may create/correct basic operational metadata.

Editorial may propose descriptive corrections.

Marketing may consume approved/current metadata.

The eventual authoritative participant-data model remains a future architecture decision.

---

## 18. Role-Specific Work Queues

### Producer Queue

Needs human production authority.

### Editorial Queue

Needs human editorial judgment.

### Marketing Queue

Needs distribution/publishing action.

A single issue may create work in more than one role, but each Work Item must state the authority required.

---

## 19. Example: Normal Session

```text
SESSION
Future of Ethereum

PRODUCTION
Package complete · revision 2

INTELLIGENCE
8 Candidates

EDITORIAL
8 reviewed
3 Clips approved

ASSEMBLY
Approved · revision 1

RENDER
3 Clips rendered

MARKETING
2 scheduled
```

No role needs to interpret one generic Session state.

---

## 20. Example: Package Reopened

```text
SESSION
Future of Ethereum

PRODUCTION
Package revision 3 · Review required

EDITORIAL
3 existing Clips
1 needs source revalidation

ASSEMBLY
Revision 1 based on package revision 2
Needs revalidation

MARKETING
1 already published
Historical publication preserved
```

This demonstrates why downstream provenance matters.

---

## 21. Historical Truth

StageFlow should preserve that actions were valid at the time they occurred.

Example:

* Package revision 2 approved.
* Editorial Clip created from revision 2.
* Asset published.
* Later package revision 3 created.

The system should not rewrite history to imply the publication never occurred.

Current-state warnings can identify that newer truth exists.

---

## 22. Cross-Role Attention

A production correction may generate:

Producer:
**Review package revision 3**

Editorial:
**1 approved Clip needs revalidation**

Marketing:
**Published asset based on superseded package**

These are different role consequences from one underlying change.

---

## 23. Cross-Role Request Instead of Unauthorized Mutation

If Editorial detects missing media:

[ REQUEST PRODUCTION REVIEW ]

If Marketing wants a rejected moment:

[ REQUEST EDITORIAL REVIEW ]

If Producer sees a Moment they value:

[ MARK MOMENT ]

Each request preserves authority boundaries.

---

## 24. Shared Navigation Context

Switching persona/workspace should preserve Session identity.

Example:

Producer Session Package Review

→ **Open in Editorial**

Editorial Temporal Workspace opens:

**same Session**

not a new lookup flow.

---

## 25. Role Visibility

Role-specific UI should hide irrelevant internal workflow detail by default.

Producer does not need:

* every rejected Candidate,
* social caption drafts.

Editorial does not need:

* PostgreSQL diagnostics,
* Stage source filesystem details.

Marketing does not need:

* media-readiness observations,
* Session-association evidence.

Technical details remain available only where useful.

---

## 26. Common Provenance Language

Across personas, StageFlow should consistently use:

* Observed
* Derived
* Inferred
* Declared
* External

plus decision context such as:

* Proposed
* Approved
* Automatic
* Human

This prevents an AI suggestion from visually masquerading as authoritative fact.

---

## 27. Automatic Authority Across Roles

Automation policy may differ by workflow.

Example:

Production package approval:
Exception-only

Editorial Candidate approval:
Manual

Assembly approval:
Automatic

Rendering:
Automatic

Marketing publishing:
Manual

There must not be one global Session automation state.

---

## 28. Persona Handoff

Preferred workflow:

**Producer**
establishes trusted Session package

↓

**Editorial**
creates approved content decisions

↓

**Assembly / Rendering**
creates distributable outputs

↓

**Marketing**
publishes/promotes approved assets

StageFlow should support overlap in time without collapsing authority.

---

## 29. Live Overlap

During a live Session:

Producer:
controls Session authority.

Editorial:
reviews Candidate Moments behind live.

Assembly:
may not yet be ready.

Marketing:
may already receive a rapidly approved/rendered clip.

This is valid.

A Session does not need to finish every upstream lifecycle before downstream work can begin if policy allows it.

---

## 30. Cross-Role Success Principle

Every persona should be able to answer:

**What is mine to decide?**

**What has already been decided by another authority?**

**What StageFlow is only suggesting?**

**What downstream/upstream consequence exists?**

without learning the entire internal system model.

---

## 31. Explicit Non-Goal

The Cross-Role Session model is not a single master workflow.

Its purpose is to prevent separate legitimate workflows from being flattened into one misleading Session status.
