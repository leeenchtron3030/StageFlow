# StageFlow Stage Detail UX Specification
**Status:** Draft v0.1
**Source fidelity:** Recovered accepted UX direction; not a verbatim reproduction.

> **Repository interpretation:** This is a recovered accepted-design summary from the
> handoff bundle, not a verbatim historical chat draft. It records product direction
> without claiming the described frontend or supporting capabilities are implemented.

## Purpose

Stage Detail answers:

**What is happening on this Stage?**

It is the operational workspace for one Stage and sits between Mission Control and focused Package Review.

## Stable hierarchy

1. Stage identity / operational state
2. Current Session
3. Immediate authoritative action
4. Previous / current / next context
5. Stage activity/source
6. Attention
7. Evidence
8. Technical details

## No-active-session state

Program Expectation and realized Session remain distinct.

Example:

- Program Expectation: External
- `START FUTURE OF ETHEREUM`
- `START AD HOC SESSION`

## Ad hoc Session entry

Support:

- Session title
- participant name(s)
- optional organization/affiliation
- organization preferably attachable per participant for panels
- simple free-form participant entry when speed matters
- authoritative start

Missing organization does not block Session completeness.

## Active Session

Show declared and proposed boundaries separately.

## End-likely flow

A machine proposal does not end the Session.

Possible actions:

- END PRESENTATION
- NOT YET

Q&A remains part of the Session when Q&A belongs to the substantive Session.

## Turnover context

Stage Detail should simultaneously support:

- previous Session assembling,
- current realized Session,
- next Program Expectation.

This temporal handoff view is a core StageFlow interaction pattern.

## Association Review

When media ownership is ambiguous:

- previous Session
- current Session
- not either
- leave unresolved

Show evidence and preserve media.

## Reassignment consequence

If moving an asset affects a completed package:

- preview which Session revisions reopen,
- preserve prior approvals,
- reopen source and target as required by package membership impact.

## Source/media language

Do not claim recorder failure merely because a source is unavailable. Report only what StageFlow knows.

## Mark Moment

Producer should have a fast `MARK MOMENT` action during an active Session.

The durable human mark should be created immediately at the current Session-relative position; optional note entry must not delay the mark.

---
