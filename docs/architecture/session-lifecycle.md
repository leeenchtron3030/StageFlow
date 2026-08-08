# Session lifecycle

This document separates verified current behavior from the Session architecture accepted
by [ADR-0023](../adr/ADR-0023-session-authority-and-completion.md). Accepted architecture
is not a claim that the durable aggregate or workflow is implemented.

## Current implementation

The Durable Kernel implementation candidate now includes an authoritative realized
`Session` contract, human create/start and boundary commands, normalized PostgreSQL
current state, typed boundary/completion history, and a read-only status projection.
These remain distinct from the pre-existing independent Session-related values:

- `ScheduledActivity` reports the planned world through a schedule adapter.
- `SessionWindow` represents a proposed or verified timeline range.
- `SessionWindowProduct` is a verified operational product associated with scheduled
  context.
- Session boundary Evidence and the Session transition policy can propose `inactive`,
  `active`, `ending`, or `ended` Operational State values.
- Transition evaluation, acceptance, and the concrete in-memory Operational State
  repository are caller-driven and process-local.
- Completed Media Asset intentionally carries no inferred Session identity.

These values must not be combined into an invented current Session state machine.
Operational State remains an assertion/projection about a subject; it is not the Session
aggregate.

## Accepted Session meaning

A Session is the complete logical media package for one actual on-stage substantive
presentation or discussion, including Q&A when it is part of the presentation. The same
boundary principle applies to a single presenter, multiple presenters, a panel, or a
conversational format. Multiple recording files may contribute to one Session.

A Session is not a directory, a file, a recording process, a scheduled time interval,
an imported program record, or a reasoning/product projection.

Substantive activity defines the normal observed boundary. An introduction, schedule
time, stage entrance, microphone activity, or presentation-computer activity can support
an `imminent` projection, but cannot establish that the presentation has started. The
normal end follows the substantive presentation/discussion and its included Q&A.

## Identity, Business Event, and Stage

- StageFlow assigns one immutable Session ID. External IDs are versioned references.
- A realized Session belongs to one Business Event.
- Once activity begins, it belongs to exactly one Stage and cannot move to or span
  another Stage.
- Planned Stage and observed Stage disagreement becomes an attributable,
  operator-visible conflict. It does not silently remap the Session, discard media, or
  stop unrelated work.
- Repeated delivery and restart cannot create an unrelated Session or duplicate an
  accepted decision.

Exact creation/realization command authority remains a Yellow decision for the Kernel.

## Program Expectation versus realized Session

A **Program Expectation** is StageFlow's durable representation of planned information
received from a schedule/program source or entered by an operator. It can carry planned
Event/Stage, start/end, title, speakers, status, and versioned external references. It
describes what is expected, not what occurred.

A Program Expectation can contextualize a Session Candidate or realized Session. It does
not automatically create a Session, grant Session identity, set the actual Stage, or set
an authoritative boundary. Corrections to planned information create new expectation
revisions and do not silently rewrite observed Session history.

The existing `ScheduledActivity` remains an adapter contract. A future persistence
boundary may normalize one or more such external records into a Program Expectation.

## Lifecycle dimensions

One status must not collapse program expectation, observed activity, media assembly, and
human review. The accepted lifecycle is represented by related dimensions:

| Dimension | Accepted concepts | Authority |
| --- | --- | --- |
| Planned reality | expected/anticipated | External or declared Program Expectation |
| Activity projection | imminent, presentation active, presentation ended | Observed, derived, or inferred evidence; authoritative boundaries can be declared |
| Media package | assembling, ready for review, correction required | Deterministic package/association state |
| Human review | in review, complete | Attributable human decision for a package revision |

`Imminent` need not be stored as an authoritative Session state; it can be a reconstructable
projection. A Session can have presentation activity ended while media remains assembling.
`Ready for review` is not `complete`.

Editorial selection, publication packaging, delivery, and archive are separate future
lifecycles and do not change the meaning of Session completion.

## Boundary authority

Machine reasoning can propose start and end boundaries with its evidence, rule/model
identity, and evaluation time. An authorized human can declare or correct the
authoritative start or end:

- while presentation activity is ongoing;
- during media assembly or review; or
- after an earlier completion decision when correction is required.

Machine proposals and successive human decisions remain append-oriented and queryable.
A new decision supersedes the current projection but does not destructively replace its
history. Proposal time, observed source time, evaluation time, human decision time, and
database commit time remain distinct.

## Media association

Completed Media Assets receive a categorical association outcome supported by explicit
evidence:

- **Associated:** one authoritative Session association is established.
- **Unresolved:** no safe association is established yet; the asset remains registered
  and may continue through otherwise valid processing.
- **Conflict:** evidence or authority is incompatible; the asset remains registered and
  the conflict requires review.

Stage/source identity is a strong structural constraint. An active realized Session,
temporal continuity, presentation activity, Program Expectation, introduction evidence,
speaker/content evidence, recorder/file facts, and human assignment can contribute, but
directory, filename, schedule, introduction, or AI output alone cannot grant authority.
Human assignment/correction is authoritative and attributable.

The initial automatic association rule remains a Yellow Kernel decision. The first
Kernel must work without AI and preserve unresolved state whenever deterministic context
is insufficient.

## Completion and late media

Session completion applies to a specific Session package revision and requires an
authorized human approval. None of these independently establishes completion:

- apparent presentation end;
- recording stop;
- absence of newly discovered files;
- grace-period expiration; or
- a machine-derived apparently complete package.

When relevant late or previously missing media appears after completion, StageFlow:

1. registers and preserves the valid media;
2. preserves the earlier completion decision and package revision;
3. records the new association or unresolved/conflict outcome; and
4. projects the current package as requiring correction/review until another authorized
   completion decision is made.

This is a reviewable revision, not silent mutation of published or historical truth.

## Persistence and recovery requirements

The durable Session boundary must preserve:

- immutable Business Event, Stage, Program Expectation, Session, asset, and decision
  identities;
- expectation revisions and versioned external references;
- proposed and declared boundaries;
- media association revisions, evidence, and conflicts;
- package revisions and completion decisions;
- actor/system authority, reason, correlation, and aware timestamps; and
- restart/reconciliation status.

PostgreSQL is the accepted store. Append-oriented decision/history records are required
where lineage matters; full event sourcing is not required. Startup reconstructs from
PostgreSQL and reconciles configured sources before event readiness is asserted.

## Decisions still required before implementation

- Session creation/realization authority and command boundary.
- The initial deterministic automatic media-association rule.
- Initial relational aggregate, history, and transaction schema.
- Deployment configuration format, secret-reference resolution, and bootstrap behavior.

Split/merge support, publication-era reopening policy, default grace durations, and
detailed editorial/package/delivery/archive state machines remain outside the first
Kernel.
