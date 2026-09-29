# StageFlow domain glossary

This implementation-facing glossary applies the terminology accepted by the architecture
baseline disposition. The foundational [StageFlow Glossary](../00_Glossary.md) remains
useful business-language history. Qualified terms below control new architectural and
serialized boundaries where older generic terms are ambiguous. No broad code rename is
authorized by this document.

## UI wording

The source of truth for Producer and Editorial display labels is
[`frontend/src/experience/ui-labels.ts`](../../frontend/src/experience/ui-labels.ts).
Canonical domain, API, and storage terms are unchanged. Internal values remain in
collapsed Details for diagnosis; shared facts appear once and exceptions remain visible.

| Internal term | UI label |
| --- | --- |
| Editorial origin `declared` / `derived` | Marked / Suggested (with matched phrase) |
| Candidate Moment / point mark | Moment / Single point: set start and end |
| Session-relative range | time into Session (mm:ss) |
| Unqualified timing / advisory / derived candidate start | Recorder time (unverified) / Estimate / Estimated start |
| Timing limitations / newer evidence revision | Recorder start and length are unverified / A newer timing estimate exists |
| Kernel status / backend projection | Live · connected |
| Trusted Demo LAN workspace | Session tools |
| Stage aggregate / media membership | Recordings |
| Transcription Evidence | Automatic transcript: may contain errors |
| Registered / Associated / Stabilizing | Found / In this Session / Still recording |
| Unresolved / Conflicting | Needs a decision / Claimed by two Sessions |
| Unplaced media / `no_safely_eligible_session` | Recording needs a decision; nothing was deleted / No Session matches this recording’s time; checked Session titles |
| Lifecycle `declared` | Set by producer |
| Current / stale / frozen proposal order | Up to date / Out of date: inputs changed / Order locked when proposed |
| Render pending, leased, running / succeeded / terminal_failed | Rendering... / Done / Failed |
| Render profile h264-nvenc-1080p-video v3; v1/v2 history | 1080p with audio (v3); 1080p (v1/v2) |
| Render Preset | 1080p Standard / 1080p High / 720p Compact |
| Event Render Setting | Render quality; Default when no setting has been chosen |
| Render Adjustment | Video bitrate / Audio bitrate |
| Explicit render with different current settings | Render again at current quality |
| Slot bindings | Layout: Intro ([asset name]) → Recording |
| Timing ordering / registration fallback | Ordered by recorder time / N recordings ordered by arrival time (no recorder time) |
| Live Triage / Review queue | Editorial review |
| Demo profile disclaimer | Test setup · 1 stage · not event-ready |
| Bounded reads / revision bookkeeping | Showing N of M (or latest N where accurate) / Details |

Certainty labels apply only to their source; rejected and expired timing stay distinct.
Human review, transcript uncertainty, preservation (Nothing was deleted), and the
not-event-ready disclaimer retain their meaning.

## Canonical and qualified terms

### Session Suggestion

- **Definition:** An immutable advisory proposed presentation interval for one Business
  Event and Stage, optionally linked to a specific Program Expectation revision.
- **Components:** Recorder-clock start/end, edge kinds, offsets from planned times,
  silence and cue support per edge, overlap, timing qualifications, categorical strength,
  evidence references and the `boundary-suggestion` policy identity/version.
- **Authority:** A human may confirm with adjusted times, using the existing Kernel
  Session start and end-boundary commands, or reject with a bounded reason. Suggestions
  never realize Sessions, associate media, or complete packages automatically.
- **Status:** Derived from Stage run order and decisions. A newer run supersedes an older
  suggestion; otherwise its decision supplies confirmed/rejected, or it remains open.
  Supersession never removes the retained decision or a realized Session.

### Suggestion Run

- **Definition:** The immutable result of a human invocation of `boundary-suggestion` v1
  for one Event and Stage, with optional Event-scoped start/end phrase-list versions.
- **Identity:** A digest of Event/Stage, policy lineage, Program Expectation revisions,
  asset timing revisions, segmentation evidence IDs, complete transcript revisions and
  cue-list versions. Identical inputs return the prior run only while it is the Stage's
  latest run. Returning to earlier inputs creates a fresh latest run and supersedes the
  intervening run's suggestions. Run order is commit-serialized and independent of clock ties.
- **Evidence:** The policy unions recorder coverage, merges freezes separated by at most
  15 seconds and recognizes freezes/gaps of at least 30 seconds as changeovers. Schedule,
  silence and optional phrase cues remain advisory. Implausible recorder clocks are
  excluded, never moved to another day.
- **Bounds:** Five nonnegative integer skip counts; missing timing precedes implausible
  clock, and missing segmentation counts usable assets. Missing planned times and no
  coverage count eligible expectations. Input overflow refuses the run without truncation.
- **Distinction:** Separate from Editorial derivation; reuse of phrase matching creates
  no Editorial candidate and does not require transcripts.

### Editorial phrase list

- **Definition:** An immutable, Event-scoped, operator-supplied list identified by key,
  stable ID and version, with a name, 1–200 phrases, creator and aware creation time.
- **Matching:** Each phrase contains 1–100 trimmed characters. Duplicate phrases after
  NFKC normalization, casefolding and whitespace collapse are rejected. Unicode
  alphanumeric tokens match exactly within one transcript segment.
- **Versioning:** Publishing is a human-only idempotent command. A new version preserves
  earlier versions; it never edits a transcript or activates automatic derivation.

### Editorial derivation run

- **Definition:** The immutable result of a human command matching one phrase-list
  version against a Session's currently associated assets. It pins the latest complete
  Transcript Evidence and the latest active MTE containing exactly one
  `creation_time_plus_duration` derivation for each eligible asset.
- **Identity:** Session, phrase-list ID/version and the sorted asset/transcript/MTE
  identity set. Identical inputs return the original run, including its creator, time,
  candidate IDs and skip counts; changed inputs create a new run.
- **Bounds:** At most 500 candidates. Missing transcript, timing or Session start counts
  once per skipped asset, in that precedence order. Negative Session starts and eligible
  matches beyond the limit count per match as `outside_session` and `limit_reached`.
- **Persistence:** One synchronous transaction owns the run, candidates, provenance,
  initial location evaluations and immutable command receipt. No upstream state changes.

### Derived Editorial candidate

- **Definition:** An advisory `EditorialCandidateMoment` with origin and epistemic kind
  `derived`, source and reason `transcript_phrase_match`, revision 1 and no human-command
  operation ID. It references its derivation run through a required provenance record.
- **Placement:** First-word asset offset plus advisory MTE start minus authoritative
  Session start, in integer microseconds; the last word supplies the end. Starts before
  the Session are skipped. Session-end conflicts use the same evaluation as declared
  candidates and remain visible rather than moving or deleting the candidate.
- **Lineage:** Phrase-list version, normalized phrase, asset, transcript revision,
  segment/word identities, asset offsets, MTE revision and qualification are retained.
  Every occurrence counts; overlapping occurrences of one phrase keep the earliest.
- **Authority:** The unchanged human review actions may create an Editorial Clip.
  Derivation grants no approval, publication, Session, association or package authority.

### Business Event

- **Definition:** A scheduled conference production containing Stages, Sessions, and
  related business context.
- **Distinction:** Not a `ProductionEvent`, which is a technical ingress fact.
- **Current aliases/legacy names:** Older documents use unqualified `Event`.
- **Migration:** The Kernel implements the qualified `BusinessEvent` contract and
  normalized PostgreSQL identity; continue qualifying new schemas/APIs.
- **Example:** “Example Conference” is a Business Event; “media asset registered” is a
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
- **Scope limit:** Demo reconciliation is one configured program source to one Stage.
  ED-0079 supports an offline local schedule file and the optional Devcon adapter.
  A future multi-Stage design must distinguish removal from the Business Event from a
  move to another room before broadening reconciliation.
- **Current aliases/legacy names:** `ScheduledActivity` is the existing schedule-adapter
  input contract; older documents use schedule item, scheduled session, or program item.
- **Migration:** Preserve `ScheduledActivity` as an adapter contract. The Kernel stores
  Program Expectations as separate revisioned planned-world records without treating
  import or linkage as Session creation.
- **Example:** A program expects a keynote on Main Stage from 10:00 to 10:45; observation
  later determines whether, where, and when a Session actually occurred.

### Program Schedule Source

- **Definition:** The provider-neutral `ProgramScheduleSource` port synchronizes one
  Stage's complete planned program, probes availability, and reads the durable cache.
- **Implementations:** `local_file` is the offline development/rehearsal default choice;
  `devcon` remains an optional provider. Results carry this provider attribution.
- **Distinction:** File input and external API input remain External Program Expectations;
  neither creates a realized Session nor changes its authoritative boundaries.
- **Compatibility:** Neutral `external_session_id`, `external_event_id`, and
  `external_room_id` references take precedence over persisted `devcon_*` equivalents.
  The fallback is removable only when all writers use neutral keys and retained current
  and historical records no longer depend on the legacy keys. No history is rewritten.
- **Composition aliases:** removed under ED-0081. `program_source` and `sync_program()`
  are the only composition names; the former Devcon aliases no longer exist.

### Program refresh

- **Definition:** The coordinator's timed call of `sync_program()`, whose successful
  outcome is a Program Expectation reconciliation
  (`backend/app/demo/autonomous.py:220`, `backend/app/demo/autonomous.py:315`,
  `backend/app/contexts/integration/program_source.py:8`).
- **Distinction:** Refresh names the scheduled invocation; reconciliation names its
  domain result. The call delegates to the configured Program Schedule Source
  (`backend/app/bootstrap/event_mode_kernel.py:164`).
- **Compatibility:** Existing `program_refresh_*` configuration/status fields retain
  their names (`backend/app/core/config/deployment.py:225`,
  `backend/app/api/v1/kernel_status.py:184`, `backend/app/api/v1/kernel_status.py:194`).

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

### Packaging Asset

- **Definition:** An Assembly-owned stable identity for curated packaging content scoped
  to a Business Event and optionally one of its Stages, with a name and role:
  `opening_bumper`, `title_card`, `sponsor_card`, or `outro`.
- **Distinction:** A Completed Media Asset proves production-media completion/readiness;
  a Packaging Asset records human curation and applicability. Neither implies the other.
- **Revision and approval:** `PackagingAssetRevision` is immutable and numbered per asset.
  It references either external content (opaque key, SHA-256, byte size, declared media
  type) or an existing Completed Media Asset ID, with optional measured duration and
  aware effective interval. `PackagingAssetApprovalDecision` appends an attributable
  approve/reject/revoke decision targeting exactly one revision. Approval state is derived
  per revision and never inherited by another revision.
- **Migration:** ADR-0030 and ED-0076 implement this boundary in `contexts/assembly/`
  and additive migration `0012`. Paths are not accepted as identity. Track applicability
  remains deferred; ED-0077 implements Session Assembly. `contexts/packaging/` stays
  reserved for delivery.
- **Example:** A sponsor card's second content revision starts unreviewed even when its
  first revision was approved.

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

### Media timing inspection

- **Definition:** A durable, retryable `media_timing` operation that inspects a registered
  Completed Media Asset using an operator-installed ffprobe and records advisory MTE.
- **Identity:** Asset and manifest identity plus inspection-profile ID/version form the
  work key. The current profile is `container-creation-time` v1; the derivation rule is
  `creation_time_plus_duration` v1. Provenance includes binary version and SHA-256.
- **Authority:** Container creation time is Observed; the candidate interval is Derived.
  Recorder semantics remain unqualified. Inspection never sets `media_started_at`,
  Session boundaries, membership, association, or package state.
- **Execution:** A separate bounded CPU worker shares the existing operation journal;
  when enabled, Demo reconciliation automatically enqueues up to 100 Event assets lacking
  a timing operation per cycle, including existing assets, idempotently by work key.
  The human backfill command remains available. Both paths gather evidence only; see the
  [ADR-0033 Amendment](../adr/ADR-0033-production-media-timing-inspection.md#amendment).

### Editorial Candidate Moment

- **Definition:** A proposed editorial highlight awaiting human review.
- **Distinction:** Not a Media Asset Candidate, Timeline Window Candidate, or approved
  Editorial Clip.
- **Current aliases/legacy names:** Foundational documents use `Candidate Moment`; ED-0067
  implements the human-declared aggregate and ED-0072 derives its current review state
  from append-only decisions.
- **Migration:** Canonical contracts and APIs use the qualified term. The Demo 1 import
  surface remains a compatibility alias, and simple UI copy may remain "Candidate Moment"
  when context is unambiguous.
- **Example:** A transcript-supported moment recommended to a reviewer.

### Editorial Clip

- **Definition:** A human-approved editorial selection intended for downstream rendering
  or publication workflows.
- **Distinction:** It is not an ingest file, source segment, candidate, or rendered Export.
- **Current aliases/legacy names:** Foundational documents use `Clip`; ED-0072 implements
  the qualified immutable selection contract.
- **Migration:** Migration `0011_editorial_review_foundation` persists stable Clip
  identity, approved Session-timeline range, candidate/revision lineage, review-decision
  lineage, and Clip revision. Rendering and publication remain separate.
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
- **Implementation:** ED-0077 implements immutable Event-scoped `AssemblyTemplate`
  versions, ordered slots, Session-numbered `AssemblyRevision`s, frozen completion
  membership and metadata values with Program Expectation source revisions, typed
  validation, and append-only human `AssemblyApprovalDecision`s. `SessionAssembly` is a
  read projection using the Session ID as its stable identity. Current revision,
  approval, and staleness derive from authoritative inputs/history.
- **Migration:** Additive migration `0013`; reverses before Packaging Assets (`0012`).
  Assembly revision remains independent of Session package revision. No rendering or
  Runtime asset assembly plan change is included.
- **Example:** Replacing a sponsor outro creates Assembly revision 4 while Session
  package revision 2 remains unchanged.

### Media order source

- **Definition:** The frozen per-member basis for Session Assembly presentation order:
  `media_timing` uses known `media_started_at`; otherwise `timing_evidence` uses the
  single `creation_time_plus_duration` Derived start in the latest active MTE revision;
  otherwise `registration_time` uses the registry's infrastructure-observed `registered_at`.
  Zero or several matching derivations fall through. The aware `order_key_at` records the
  selected instant. New proposals sort by that key, then asset ID, across all three sources.
  Only `timing_evidence` carries `order_evidence_id`, `order_evidence_revision`, and
  `order_evidence_qualification`, frozen for disclosure before human approval.
- **Authority:** Human Assembly approval confirms the proposed order. Registration time
  does not assert captured-content timing or change completion membership, Session
  boundaries, package authority, or advisory Media Timing Evidence (ADR-0027).
- **Compatibility:** Additive `0016` preserves old positions. Legacy NULL ordering
  columns hydrate as `media_timing` with the stored media start as key. A legacy invalid
  untimed revision retains a null key and its stored validation; it is never approvable
  or renderable. `MEDIA_TIMING_UNAVAILABLE` remains readable but is not newly emitted.
- **Rendering:** Each `session_media` slot expands the frozen member sequence; rendering
  never re-sorts it. Revision APIs expose source and key without filesystem paths.

### Assembly metadata override

- **Definition:** An immutable human `set` or `clear` entry for `session_title` or
  `participant_names`, local to a Session's Assembly history (ED-0086).
- **Provenance:** Override ID, Session, field, values, Session-wide append sequence,
  actor, aware injected-clock recording time, and reason. Values are display strings;
  they introduce no participant identity or observed-presence authority.
- **Resolution:** The latest entry per field wins by sequence. `set` supplies a frozen
  `operator_override` value with override ID and sequence as source lineage; `clear`
  restores the current linked Program Expectation value, or absence if unavailable.
- **Distinction:** It never edits Program Expectations, Session/package authority, or
  Packaging Assets. An existing Assembly revision establishes the command's scope.
- **Migration:** Additive `0014` stores override history and separate override snapshot
  references; existing Program-sourced snapshots remain unchanged. Staleness is derived
  only when the override governing a field has changed since the revision was proposed;
  Program Expectation refreshes never make a revision stale.
- **Example:** An operator corrects a display title for the next Assembly proposal while
  retaining the schedule's original title and all earlier Assembly revisions.

### Rendering terms

- **Render Profile:** immutable, versioned execution settings. The current profile, v3,
  uses CUDA decode and H.264 NVENC at 1080p, preset p4, VBR 8 Mbit/s, GOP 60, MP4,
  with constant 30000/1001 video and one native AAC-LC 48 kHz stereo 192 kbit/s
  audio stream. Each input contributes its first audio stream or digital silence.
  v1 and v2 remain readable video-only recorded identities, refused for new renders.
- **Render Preset:** one code-defined, versioned Render Profile in the closed catalog,
  with default bitrates and permitted video and audio bitrate adjustments. Standard
  (1080p v3) is the default; High (1080p v1) and Compact (720p v1) are alternatives.
- **Render Adjustment:** immutable optional video or audio bitrate within the preset's
  bounds. A value equal to the preset default normalizes to no adjustment. All other
  profile properties remain fixed.
- **Event Render Setting:** rendering-owned, immutable, append-only version for a
  Business Event, recording the preset, adjustments, human actor, command and aware
  selection time. The highest version is current; absence means unadjusted Standard.
  Changes affect future requests only and never cause automatic re-rendering.
- **Render Request:** human-authorized, idempotent command for an approved, non-stale
  Assembly revision. It freezes the Event's current preset, adjustments and setting
  version in the enqueue transaction. The expected setting version guards the human's
  confirmation against concurrent changes. It enqueues a Durable Operation, not publication.
- **Rendered Output:** immutable rendering-owned identity for completed output bytes and
  their frozen-metadata sidecar. It records opaque content keys and SHA-256 identities,
  size, duration, frame count, source revision, profile, FFmpeg identity, producing
  operation/attempt and aware production time. It carries no filesystem location.

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
| Session Transcript composition | Transcript Evidence Revision is the implemented internal asset-scoped evidence aggregate; the foundational Session Transcript is a later cross-asset product concept | Accept correction/stitching policy, public naming, and relationship to asset-scoped evidence revisions |
| Wall-Clock Transcript Alignment | MTE can derive advisory wall-clock intervals from immutable asset-relative transcript offsets | Accept aggregate name/owner and authorized consumers; automatic Session/media authority remains prohibited |
| Automation Policy / Approval Policy | Evidence -> Policy -> Authority and per-decision activation are proposed in ADR-0026 | Acceptance, public term, scope storage, and activation authority |

Do not resolve these terms through incidental code naming. Record the decision first and
then plan compatibility for documentation, contracts, storage, and APIs.

## Media Segmentation Evidence

Immutable advisory freeze and silence intervals for one Completed Media Asset and one
`media_segmentation` Durable Operation (ADR-0034 Phase 1). Offsets are integer microseconds
from asset start, with kind, profile ID/version and explicit FFmpeg version/SHA-256 lineage.
The recorded `freeze-silence` v1 profile fixes CPU decode, the demuxer allowlist,
`fps=5,scale=320:-2,freezedetect=n=0.003:d=4` and `silencedetect=n=-40dB:d=3`.
An evidence result contains at most 10,000 intervals; exceeding the cap fails the operation.
An empty result is valid. Open intervals close at the completed decode's output duration.
An end reported up to 1 s past that duration (for example silence ending at the last audio
frame) is clamped to it; a later end, or any start past the duration, is invalid.

These observations do not identify a Session or grant association, boundary, editorial,
completion or automation authority. Phase 1 produces no Session Suggestions or policy decisions.
