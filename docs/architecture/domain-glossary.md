# StageFlow domain glossary

This implementation-facing glossary applies the terminology accepted by the architecture
baseline disposition. The foundational [StageFlow Glossary](../00_Glossary.md) remains
useful business-language history. Qualified terms below control new architectural and
serialized boundaries where older generic terms are ambiguous. No broad code rename is
authorized by this document.

## Canonical and qualified terms

### Business Event

- **Definition:** A scheduled conference production containing Stages, Sessions, and
  related business context.
- **Distinction:** Not a `ProductionEvent`, which is a technical ingress fact.
- **Current aliases/legacy names:** Older documents use unqualified `Event`.
- **Migration:** The Kernel implements the qualified `BusinessEvent` contract and
  normalized PostgreSQL identity; continue qualifying new schemas/APIs.
- **Example:** “Devcon 2026” is a Business Event; “media asset registered” is a
  Production Event.

### Program Expectation

- **Definition:** StageFlow's durable, revisioned representation of what an external
  program source or authorized operator expects to occur, including planned Business
  Event/Stage, start/end, title, speakers, status, and versioned external references.
- **Distinction:** It describes planned reality. It is not proof that activity occurred,
  not a realized Session, and not authority for actual Session Stage or boundaries.
- **Lifecycle:** **Current** means observed in the latest successful full snapshot for the
  exact configured provider synchronization scope. **Withdrawn** means previously observed
  but absent from that successful snapshot. Withdrawn records remain durable external
  evidence and cannot be selected for new Session realization; linked realized Sessions
  remain unchanged.
- **Scope limit:** Demo reconciliation is currently one Devcon Event/room to one Stage.
  A future multi-Stage design must distinguish removal from the Business Event from a
  move to another room before broadening reconciliation.
- **Current aliases/legacy names:** `ScheduledActivity` is the existing schedule-adapter
  input contract; older documents use schedule item, scheduled session, or program item.
- **Migration:** Preserve `ScheduledActivity` as an adapter contract. The Kernel stores
  Program Expectations as separate revisioned planned-world records without treating
  import or linkage as Session creation.
- **Example:** A program expects a keynote on Main Stage from 10:00 to 10:45; observation
  later determines whether, where, and when a Session actually occurred.

### Production Event

- **Definition:** The provider-neutral ingress statement that a source reports something
  happened.
- **Distinction:** It is neither a Business Event nor a Semantic Observation and assigns
  no meaning beyond its source report.
- **Current aliases/legacy names:** `ProductionEvent` in code; generic “event” in some
  discussions.
- **Migration:** Qualify serialized/public references. Stable ingress identity is
  implemented and reused by the completed-asset registration path.
- **Example:** A recorder source reports that recording activity started.

### Session

- **Definition:** The complete logical media package representing one actual on-stage
  substantive presentation or discussion, including Q&A when part of the presentation,
  with one immutable StageFlow Session ID and versioned external references.
- **Distinction:** Not a Program Expectation, schedule-adapter record, directory, file,
  recording process, Session Candidate, Timeline Window Candidate, Session Window
  Product, or Operational State assertion. Multiple media files may contribute to it.
- **Current aliases/legacy names:** Older specifications describe Session as a scheduled
  presentation. The Kernel `Session` aggregate is authoritative for realized production
  identity while schedule records remain Program Expectations.
- **Migration:** ADR-0023 fixes the meaning and ADR-0024 fixes Kernel authority. The
  normalized schema, human realization/correction, package history, and bounded status
  projection are implemented; later automated realization/split/merge remains deferred.
- **Example:** One reconciled keynote workflow retains the same StageFlow Session ID when
  its schedule time changes.

### Session Candidate

- **Definition:** An observed or reasoned proposal that production facts may correspond
  to a Session or Session boundary.
- **Distinction:** It may propose association or promotion but is not authoritative
  Session identity.
- **Current aliases/legacy names:** `SESSION_CANDIDATE` Operational State subject;
  unqualified “candidate session.”
- **Migration:** Promotion/reconciliation authority remains open; do not serialize a
  promotion rule yet.
- **Example:** Recording and boundary Evidence suggest a panel began near 10:05.

### Timeline Window Candidate

- **Definition:** A proposed media range before verification in the timeline reasoning
  layer.
- **Distinction:** It answers where/when, not whether a Session exists or an operational
  product is approved.
- **Current aliases/legacy names:** Current code exposes `SessionWindow`, which can carry
  proposed and verified statuses; ADR-0010 names `TimelineWindowCandidate`.
- **Migration:** Use the canonical term in new documentation/serialization; plan a
  compatibility alias before renaming public Python contracts.
- **Example:** Recording Block range 00:14:20–00:55:00 proposed for review.

### Session Window Product

- **Definition:** A verified operational product representing an approved production
  media window associated with scheduled context.
- **Distinction:** It follows verification and remains distinct from both a Timeline
  Window Candidate and the authoritative Session aggregate.
- **Current aliases/legacy names:** `SessionWindowProduct` in code.
- **Migration:** None currently required.
- **Example:** A verified window selected from a reviewed Session-boundary Finding.

### Media Asset Candidate

- **Definition:** One known media resource with deterministic identity and provenance
  that may later be eligible to become a Completed Media Asset.
- **Distinction:** Discovery does not establish stability, readiness, completion,
  registration, Session membership, or editorial value.
- **Current aliases/legacy names:** `MediaAssetCandidate` in ED-0049/52/53 code; older
  documents often say Media Chunk too early.
- **Migration:** New media registries must preserve this distinction; no rename required.
- **Example:** A shallow scan finds `segment-0042.mov` while it may still be growing.

### Completed Media Asset

- **Definition:** An immutable logical media asset with finalized completion,
  safe-to-read readiness, resource manifest, and authoritative provenance.
- **Distinction:** It is stronger than a candidate and is not an Editorial Clip or a
  Session Package.
- **Current aliases/legacy names:** `CompletedMediaAsset` in ED-0048 contracts.
- **Migration:** Future assembly and registry must satisfy the existing contract rather
  than reclassifying candidates.
- **Example:** A finalized recording segment registered after sufficient resource
  observations support `safe_to_read`.

### Media Timing Evidence

- **Definition:** An immutable, durable, asset-linked revision containing sanitized
  Observed recorder/media timing facts, Derived candidate intervals, inspection
  provenance, recorder-profile qualification state, and explicit limitations.
- **Distinction:** It is not a mutable Completed Media Asset field, authoritative content
  time, Semantic Evidence specialization, Session boundary, or association decision.
- **Current aliases/legacy names:** `MediaTimingEvidence` under ADR-0027; the earlier
  candidate architecture is accepted and renamed to the canonical architecture document.
- **Migration:** Additive `0006_media_timing_evidence`; pre-existing assets require no
  evidence/backfill and remain valid.
- **Example:** Unqualified vMix `creation_time` and measured duration support a Derived
  candidate interval shown as advisory evidence during media-uncertainty drill-down.

### Editorial Candidate Moment

- **Definition:** A proposed editorial highlight awaiting human review.
- **Distinction:** Not a Media Asset Candidate, Timeline Window Candidate, or approved
  Editorial Clip.
- **Current aliases/legacy names:** Foundational documents use `Candidate Moment`; ED-0067
  implements only the human-declared, unreviewed Phase 1 aggregate.
- **Migration:** Canonical contracts and APIs use the qualified term. The Demo 1 import
  surface remains a compatibility alias, and simple UI copy may remain "Candidate Moment"
  when context is unambiguous.
- **Example:** A transcript-supported moment recommended to a reviewer.

### Editorial Clip

- **Definition:** A human-approved editorial selection intended for downstream rendering
  or publication workflows.
- **Distinction:** It is not an ingest file, source segment, candidate, or rendered Export.
- **Current aliases/legacy names:** Foundational documents use `Clip`; no implementation
  exists.
- **Migration:** Use the qualified term at cross-context boundaries when implemented.
- **Example:** A reviewer approves a 45-second range from an Editorial Candidate Moment.

### Hot Moment

- **Definition:** An urgency designation indicating that an Editorial Candidate Moment
  or approved editorial output may require prompt reviewer attention.
- **Distinction:** It is not a separate aggregate, editorial tier, approval action, or
  grant of automatic authority.
- **Current aliases/legacy names:** Foundational documents use `Hot Moment` and sometimes
  describe a hot flag on Candidate Moment.
- **Migration:** Keep urgency first-class where behavior-driving, but do not introduce a
  `HotMoment` authority object in the first post-Kernel slice.
- **Example:** A time-sensitive announcement candidate is prioritized in Editorial review
  while remaining unapproved.

### Session Assembly

- **Definition:** A versioned downstream presentation plan that combines one fixed
  Session package revision with template, approved packaging-asset, placement, and
  resolved metadata references.
- **Distinction:** It describes how a package should be presented; it does not change
  Session boundaries, media membership, package revision, or package completeness.
- **Current aliases/legacy names:** Foundational documents describe package/export
  branding settings but do not define this separate aggregate. The existing Runtime
  asset assembly plan is a Completed Media Asset manifest mapping and is not Session
  Assembly.
- **Migration:** No implementation exists. Assembly revision must remain independent of
  Session package revision when introduced.
- **Example:** Replacing a sponsor outro creates Assembly revision 4 while Session
  package revision 2 remains unchanged.

### Operational State

- **Definition:** A versioned accepted assertion or projection of a subject's operational
  condition, with transition and acceptance lineage.
- **Distinction:** It is not the subject aggregate, workflow record, Job, or Session.
- **Current aliases/legacy names:** `OperationalState` in ED-0039–0047 contracts.
- **Migration:** Future persistence must retain projection semantics and distinct
  evaluation, acceptance, commit, and organizational-anchor times.
- **Example:** A Session Candidate subject is accepted as `active` at a revision.

### Media Resource Observation

- **Definition:** An objective measurement or status fact about a candidate's physical
  resource used by readiness evaluation.
- **Distinction:** It is not the reasoning-layer `Observation` created from a Production
  Event and does not itself declare readiness.
- **Current aliases/legacy names:** ED-0049 observation facts and ED-0052 observation
  bundles; often shortened to “resource observation.”
- **Migration:** Keep the qualified name in APIs and persistence.
- **Example:** Two samples record unchanged byte size over an explicit interval.

### Semantic Observation

- **Definition:** An objective phenomenon produced by an Observation Interpreter from a
  Production Event and used as the first reasoning-layer artifact.
- **Distinction:** It does not infer Evidence, Session meaning, readiness, or editorial
  value and is not a Media Resource Observation.
- **Current aliases/legacy names:** The code class is `Observation`; AR-2.1 also says
  “Objective Observation.”
- **Migration:** Use `Semantic Observation` when qualification is needed; no broad class
  rename is authorized.
- **Example:** A recording activity interpreter observes that the source reports an
  active recording state.

### Recording Block

- **Definition:** A provider-neutral continuous recording timeline context against which
  positions and ranges can be expressed.
- **Distinction:** Not a physical media file, Session, or Editorial Clip.
- **Current aliases/legacy names:** `RecordingBlock` in timeline contracts.
- **Migration:** None currently required.
- **Example:** Multiple source files may contribute facts associated with one Recording
  Block timeline.

### Stage

- **Definition:** A StageFlow-owned production location/context within one Business Event
  to which sources, Program Expectations, and realized Sessions may be associated.
- **Distinction:** It is not a Runtime host, Node deployment profile, or source adapter.
- **Current aliases/legacy names:** Stage IDs/context remain widespread; the Kernel adds
  the authoritative Event-owned `Stage` aggregate and source-binding records.
- **Migration:** ADR-0023 requires one fixed Stage per realized Session and ADR-0024
  resolves explicit idempotent bootstrap. That persistence/authority is implemented.
- **Example:** “Main Stage” contextualizes one recorder source and scheduled activities.

### Durable Operation

- **Definition:** A persisted unit of asynchronous, long-running, retryable, or externally
  dependent work with stable identity, claim/lease, retained Attempts, and terminal
  result identity.
- **Distinction:** Deterministic domain policy calls remain synchronous and are not
  Operations merely because they perform work.
- **Current aliases/legacy names:** Older documents use `Job`. Migration 0007 implements
  only the qualified `transcription` operation kind.
- **Migration:** Accepted ADR-0025 and the bounded first-worker plan establish the
  PostgreSQL Operation/Attempt/lease/fencing substrate. Generalized operation kinds,
  automatic enqueue, and a broker remain unimplemented.
- **Example:** An explicitly enqueued transcription request deferred during local-only
  Event Mode because its configured execution requires cloud access.

### Transcript Evidence Revision

- **Definition:** An immutable asset/manifest-scoped normalized transcript result with
  provider/model/tool provenance, preserved asset-relative timing, limitations, and
  predecessor revision lineage.
- **Distinction:** It is evidence about one Completed Media Asset manifest, not the
  foundational cross-asset Session Transcript, Session/media authority, Editorial
  approval, or verified speaker identity.
- **Current aliases/legacy names:** `Transcript Evidence Revision` is the accepted
  internal term for the migration-0007 aggregate. Public API naming is not selected.
- **Migration:** Migration 0007 persists the parent, segments, optional words, and
  optional Derived MTE alignment. Session Transcript composition/correction remains a
  later decision.
- **Example:** A provider-neutral revision whose offsets remain relative to the immutable
  asset while an optional wall-clock interval is explicitly Derived from unqualified MTE.

### Deployment profile

- **Definition:** First-class Runtime provenance describing Agent, Node, Development,
  external-compatible, or genuinely unknown origin.
- **Distinction:** It is not a trust level, identity tier, readiness decision, or
  candidate-identity seed.
- **Current aliases/legacy names:** `RuntimeProfile` and
  `CompletedMediaAssetRuntimeProfile` values.
- **Migration:** None; preserve Development as first-class and reserve unknown for
  unavailable information.
- **Example:** A Development Runtime discovers the same source facts without changing
  candidate identity.

## Visibly unresolved terminology

| Concept | Current evidence | Unresolved decision |
| --- | --- | --- |
| Source Segment / durable Segment record | Disposition reserves a qualified durable media record; older documents use Media Chunk and Timeline Segment | Canonical record name, rename/alias behavior, and relationship to Completed Media Asset |
| Job / Durable Operation / Task | ADR-0025 and migration 0007 implement the internal `Durable Operation`/Attempt/Worker schema for transcription | Public API aliases and any generalized operation kinds remain unresolved |
| Post-Kernel Session evolution | Human Session realization and reassignment are implemented | Automated realization, merge, and split policy |
| Package and publication milestones | Distinct milestones are accepted | Aggregate names and detailed state machines remain deferred |
| Packaging Asset / Event Asset | Session Assembly needs reusable approved presentation media distinct from package correctness | Aggregate name/owner and whether content composes a Completed Media Asset or a separate manifest |
| Session Transcript composition | Transcript Evidence Revision is the implemented internal asset-scoped evidence aggregate; the foundational Session Transcript is a later cross-asset product concept | Accept correction/stitching policy, public naming, and relationship to asset-scoped evidence revisions |
| Wall-Clock Transcript Alignment | MTE can derive advisory wall-clock intervals from immutable asset-relative transcript offsets | Accept aggregate name/owner and authorized consumers; automatic Session/media authority remains prohibited |
| Automation Policy / Approval Policy | Evidence -> Policy -> Authority and per-decision activation are proposed in ADR-0026 | Acceptance, public term, scope storage, and activation authority |

Do not resolve these terms through incidental code naming. Record the decision first and
then plan compatibility for documentation, contracts, storage, and APIs.
