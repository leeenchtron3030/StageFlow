# ADR-0023: Session authority, boundaries, association, and completion

## Status

Accepted

## Date

2026-08-08

## Context

StageFlow has timeline windows, Session Candidates, Session Window Products, Session
boundary Evidence, transition policies, and Operational State projections, but no
authoritative Session aggregate. ADR-0002 identifies Session as the primary Production
aggregate, ADR-0013 separates planned and observed reality, and the architecture-baseline
disposition requires a StageFlow-owned immutable Session ID. The remaining product
meaning of a Session, its relationship to program expectations and Stage reality, human
boundary authority, media association, and completion authority must be fixed before a
durable Event-Mode Kernel can be designed or implemented.

## Decision

### Session meaning and identity

A Session is the complete logical media package representing one actual on-stage
substantive presentation or discussion. It may contain one or more presenters, a panel,
a conversational format, and Q&A when that Q&A is part of the presentation. Multiple
recording files may contribute to one Session.

A Session is not a directory, file, recording process, scheduled interval, imported
program record, Session Candidate, Timeline Window Candidate, Session Window Product, or
Operational State assertion. StageFlow assigns the Session one immutable identity;
provider and program identifiers remain versioned external references.

### Planned and observed reality

StageFlow retains planned program information as a **Program Expectation**, separate
from the actual realized Session. A Program Expectation can inform observation and
association confidence, but cannot prove that a Session occurred or define its actual
boundaries. Observed activity determines what occurred.

A Session normally begins when the speaker or speakers begin the substantive
presentation or discussion. Introductions, stage entrance, schedule time, microphone
activity, and presentation-computer activity are contextual evidence that a Session may
be imminent; none establishes the start by itself. A Session normally ends after the
substantive presentation or discussion and any included Q&A have concluded.

### Event and Stage invariants

Every realized Session belongs to one Business Event and, once it has begun, exactly one
Stage. It cannot move between Stages or span multiple Stages. A conflict between a
Program Expectation and observed Stage reality is preserved as an operator-visible
conflict. StageFlow does not silently remap the Session, discard associated media, or
halt unrelated ingest and processing.

### Media association

Completed Media Asset association is evidence-driven. Directory placement, filename,
schedule, introduction evidence, or an AI classification cannot independently grant
Session identity. Relevant evidence can include Stage/source identity, an active
realized Session, temporal continuity, presentation activity, Program Expectations,
introduction evidence, speaker/content evidence, recorder/file facts, and explicit
human assignment.

Stage/source identity is a structural constraint because a Session cannot span Stages.
Association reasoning preserves its evidence and categorical reasons rather than
flattening authority into one opaque probability. At minimum the durable outcome is
`associated`, `unresolved`, or `conflict`. Unresolved or conflicting media remains safely
registered and may continue through otherwise valid processing. Human assignment or
correction is authoritative and attributable.

### Boundary and completion authority

StageFlow may retain machine-proposed start and end boundaries, but an authorized human
can declare or correct the authoritative boundaries while activity is ongoing, during
assembly or review, and after an earlier completion decision. A correction appends a
new decision/revision; it does not erase the proposal or prior human decision.

Presentation end, recording stop, inactivity, file-arrival timeout, and grace expiration
do not make a Session complete. StageFlow must assemble the intended media package and
an authorized human must approve that package revision before the Session is complete.
`Ready for review` may be machine-derived; `complete` is human-declared.

Relevant late or previously missing media creates a correction/review condition for the
current package projection. StageFlow preserves the prior completion decision and its
package revision, registers the valid media, and requires a new review before a revised
package is complete. Late media is not silently ignored.

### Lifecycle dimensions

StageFlow keeps distinct lifecycle meanings rather than one overloaded status:

- a Program Expectation can be expected or anticipated without creating a Session;
- observation can indicate that a possible Session is imminent;
- realized Session activity can be active or ended;
- Session media can be assembling or ready for review;
- an authorized human can place the package in review and approve it complete; and
- late or corrected media can return the current package projection to correction/review.

Editorial selection, publication packaging, delivery, and archival remain separate
downstream lifecycles. Session completion does not imply any of them.

This ADR does not select the Session creation command, automatic association rule,
relational schema, configuration file format, or deployment bootstrap procedure. Those
choices require the bounded Kernel architecture and implementation plan.

## Alternatives

- **Treat a schedule item as the Session:** rejected because planned and observed reality
  can diverge and external identity cannot own StageFlow workflow authority.
- **Use a directory, file, or recording process as the Session:** rejected because one
  Session may contain multiple assets and storage layout is mutable evidence, not
  identity.
- **Let observed or inferred state silently create, move, or complete a Session:**
  rejected because structural conflicts and human authority must remain visible and
  attributable.
- **Replace corrected boundaries or completion decisions in place:** rejected because it
  destroys provenance, auditability, and future model-evaluation evidence.
- **Use one confidence score as association authority:** rejected because structural
  constraints, deterministic evidence, external claims, inference, and human decisions
  have different meanings.

## Consequences

- The durable model needs separate Business Event, Stage, Program Expectation, Session,
  package-revision, boundary-decision, media-association, and conflict meanings.
- Schedule adapters continue to report planned activity; their output does not become a
  Session aggregate.
- Existing Session Candidate, timeline, reasoning, Verification, and Operational State
  contracts can propose or explain decisions but cannot own Session authority.
- The Producer query model must expose evidence provenance, unresolved associations,
  conflicts, human decisions, and the package revision to which completion applies.
- Persistence must preserve immutable identities and append-oriented decision history;
  full event sourcing is not required by this decision.
- Kernel operation remains possible without AI. Later inference may contribute evidence
  but cannot replace structural constraints or human authority.

## Validation

Future implementation must prove that:

- a Session retains one Business Event and one fixed Stage after activity begins;
- a Program Expectation can exist, change, or conflict without silently creating or
  moving a Session;
- multiple assets can associate with one Session and unresolved/conflicting assets remain
  registered;
- filename, directory, schedule, introduction, or inference alone cannot grant
  authoritative association;
- machine proposals and successive human boundary decisions remain queryable;
- completion requires an attributable human decision for a specific package revision;
- late valid media preserves prior completion history and returns the current package to
  correction/review; and
- restart and replay do not create a second Session, duplicate association, or erase
  decision lineage.

## Related documents

- [ADR-0020](ADR-0020-canonical-media-to-event-path.md)
- [ADR-0022](ADR-0022-postgresql-authoritative-operational-store.md)
- ADR-0002, ADR-0012, and ADR-0013 in
  [Architecture Decisions](../../ARCHITECTURE_DECISIONS.md)
- [Session lifecycle](../architecture/session-lifecycle.md)
- [Domain glossary](../architecture/domain-glossary.md)
- [Durable Event-Mode Kernel architecture](../architecture/durable-event-mode-kernel.md)
- [Architecture baseline disposition](../reviews/architecture-baseline-disposition.md),
  D-01 and D-06
