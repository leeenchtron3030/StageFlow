# ED-0041 Architecture and Codebase Review

**Directive:** ED-0041

**Review scope:** Backend architecture and tests through ED-0040

**Review date:** 2026-07-16

**Decision:** `pause_for_blocking_remediation`

## 1. Executive Summary

StageFlow remains strongly aligned with its mission as a deterministic, explainable
observer of recorded event media. The implemented layers retain visible operational
meaning: adapters report, interpreters observe, Evidence Builders organize, Session
Boundary Evidence composes, and transition policies evaluate without execution or
persistence. No implemented layer performs show control, media ingest, autonomous
execution, state acceptance, or persistence.

The review recorded 13 findings: one critical, two high, five medium, three low, and two
informational. Most of the architecture should remain unchanged. Two issues must be
remediated before Operational State Acceptance begins:

1. `RecordingTransitionPolicy` does not isolate Evidence by recording context, validate
   the current state domain, or bind supporting roles to the Signal contribution it
   selects. Mixed Evidence can therefore produce a first-rule-wins transition across
   recording blocks or correlations.
2. Concrete Observation Interpreters discard known stage context when choosing a
   recording-block or wall-clock location, and multi-event interpretation assigns the
   entire batch of Event IDs to every Observation. This weakens context isolation and
   exact provenance before Evidence construction.

The generic `TransitionEvaluation` and related result contracts also need explicit
acceptance invariants and first-class evaluation lineage during ED-0042. They currently
permit contradictory shapes and keep policy/rule identity in metadata or concrete
wrappers.

The review therefore selects `pause_for_blocking_remediation`. This is not a request for
a broad refactor. The roadmap limits pre-ED-0042 work to recording-policy safety and
Observation context/provenance preservation.

## 2. Review Scope

Reviewed:

- `backend/app/`, with detailed reads across shared identifiers/time, Production Events,
  both interpreter foundations, all concrete Observation Interpreters, Evidence
  contracts, generic and concrete Evidence Builders, Operational State, generic and
  concrete transition policies, summaries, results, and public exports
- all files under `backend/tests/`
- `backend/pyproject.toml` and dependency/tool configuration
- `REPOSITORY_MANIFEST.md`, `ENGINEERING_DIRECTIVES.md`, Production package READMEs,
  and architecture references relevant to the live-production model
- the four required representative flows and all meaningful production-context metadata
  reads and writes

Not reviewed as implementation scope: frontend behavior, persistence, APIs beyond the
existing health route, workers, queues, provider integrations, or state acceptance.

No production code, contract, policy rule, enum, metadata path, or compatibility branch
was changed by ED-0041.

## 3. Repository Health

Baseline and final post-correction validation:

- Backend tests: 705 passed; one third-party Starlette/httpx deprecation warning
- Ruff: all checks passed
- Pyright strict mode: 0 errors, 0 warnings
- `git diff --check`: passed

Configuration is coherent: Python 3.13, strict Pyright over `app` and `tests`, Ruff E/F/I/
UP/B rules, pytest rooted in `backend/tests`, and dependencies managed by `uv`. The test
and type commands must run from `backend/` so the configured import path and virtual
environment are applied.

## 4. Architecture Alignment

The implemented responsibility chain remains recognizable and restrained:

| Layer | Observed responsibility | Review result |
| --- | --- | --- |
| Production Event | Immutable runtime report with source/payload/references/times | Aligned |
| Observation Interpreter | Domain mapping into objective Observation | Aligned, with context/provenance gaps in ED0041-F002 |
| Observation | Objective phenomenon and location | Aligned; no Session State or policy outcome fields |
| Evidence Builder | Deterministic organization into Concern/Role/Strength/Signal | Aligned |
| Session Boundary Evidence Builder | Cross-domain possible-boundary composition | Aligned; does not verify a boundary |
| Transition Policy | Descriptive proposal only | Session policy aligned; recording policy safety defect in ED0041-F001 |
| Transition Evaluation | Proposed value, outcome, rationale, Evidence IDs | Boundary aligned; acceptance invariants incomplete in ED0041-F003 |

No generic Evidence Builder package contains recording, transcript, or Session lifecycle
meaning. `EvidenceBuilderContextKey`, semantic selection, ordering, deduplication, and
input reporting remain domain-neutral. Concrete builders retain explicit mappings and
rules. The visible duplication between recording and transcript builders is acceptable;
their grouping and Signal semantics differ and do not justify another framework.

The material abstraction inconsistency is older versus newer interpreter contracts:
`ProductionEventDispatcher` accepts the ED-0014 `ProductionEventInterpreter`, while all
ED-0024+ concrete interpreters implement the ED-0023 `ObservationInterpreter` pattern.
That prevents the documented dispatcher path from composing with the concrete
Perception Layer without an adapter or consolidation (ED0041-F005).

## 5. Production Workflow Alignment

The code does not require live NDI/SDI, continuous transport, show-control integration,
or production-crew coordination. Adapters accept discrete activity, media artifact,
transcript, schedule, clock, vision, and operator reports. This fits file-based segments,
intermittent arrival, and constrained connectivity. Builders operate on finite in-memory
sequences and tolerate absent schedule, stage, recording block, stream, and artifact
context conservatively in most paths.

Recorded media and transcript Evidence are central. Schedule and operator information
remain context, not conclusion. Missing Evidence is not converted to contradiction.
Policies evaluate but do not execute. No state acceptance or persistence exists.

The principal workflow deviation is not scope expansion but context loss: stage
references supplied by adapter Events do not survive concrete interpretation when a
recording-block or wall-clock location is selected. The old architecture references also
retain broad phrases such as StageFlow owning “live production workflow” and
“operational monitoring”; the approved AR-2.x reasoning documents narrow this meaning,
but canonical wording should be reconciled in a documentation release (ED0041-F011).

## 6. Contract Integrity

Positive contract properties:

- core contracts use frozen, slotted dataclasses
- mutable input sequences are generally normalized to tuples
- top-level metadata mappings are defensively copied and wrapped
- `ProductionEventPayload` uniquely validates JSON compatibility and recursively freezes
  nested mappings/sequences
- `TimelineRange`, `TimelinePosition`, `ObservationLocation`, and recording-block/timeline
  relationships enforce useful structural invariants
- Evidence and state bases use ID-only references
- Session rule/requirement contracts validate supported lifecycle combinations
- public exports are explicit and load under strict Pyright and the full test suite

Weaknesses:

- `TransitionEvaluation` does not validate current-state kind, outcome/proposed-state
  compatibility, or mutually incompatible supporting/blocking shapes. Existing contract
  tests construct `transition_supported` with both supporting and blocking IDs.
- `OperationalState` validates selected family boundaries but not the full
  kind/subject/value matrix.
- `OperationalStateBasis` cannot first-class reference the Transition Evaluation that a
  future acceptance layer would accept.
- builder result classifications are duplicated between direct fields and optional
  `input_report` without consistency validation.
- most metadata-bearing frozen contracts are only shallowly immutable.

These are contract-strength issues, not evidence that current builders emit malformed
objects. Current concrete builders and the Session policy generate internally coherent
outputs in covered paths.

## 7. Metadata Audit

Classification uses ED-0041’s three approved categories.

| Meaning / field | Classification and disposition | Writer | Reader | Fallback and validation | Migration recommendation |
| --- | --- | --- | --- | --- | --- |
| `recording_activity`, `recording_event_kind` | Authoritative domain meaning in metadata; `potential_contract_gap` | Recording Activity Observation Interpreter; adapter payload supplies event kind | Recording Coverage semantic selector and mapping | Activity key has priority; event-kind key is fallback; normalized value must match static mappings or input is unsupported | Promote together in a typed Observation payload/semantic contract; retain event-kind compatibility during migration |
| `transcript_lifecycle` | Authoritative domain meaning in metadata; `potential_contract_gap` | Transcript Observation Interpreter | Transcript Continuity selector and mapping | No guess from absence; value must match static lifecycle mapping | Promote with other authoritative Observation semantics, not as a standalone abstraction |
| `recording_block_id` | First-class authority with structured compatibility copies; `acceptable_temporarily` | Event reference, Observation, EvidenceSet; copied into item/signal metadata | Builders, summaries, policies | First-class `Observation.recording_block_id` / `EvidenceSet.recording_block_id` wins; metadata is parsed conservatively | Keep first-class authority; remove redundant copies only under a compatibility directive |
| `stage_id` | First-class at Event reference and ObservationLocation/BoundaryContext, but authoritative in Evidence metadata; `potential_contract_gap` | Adapter references; builder item/signal/set metadata | Recording/Transcript grouping, Boundary Builder, Session policy, summaries | Entity IDs are parsed; invalid metadata becomes unknown; concrete interpreters currently drop the known Event stage | Fix stage preservation first; later introduce a typed Evidence context if repeated policy use remains |
| `scheduled_activity_id`, legacy `schedule_activity_id` | Authoritative domain meaning in metadata; `potential_contract_gap` | Schedule Observation and composed Evidence | Boundary Builder and Session policy | Canonical key preferred; legacy alias accepted by Boundary Builder; invalid IDs become unknown | Promote into a reusable Evidence context before persistence/state lineage depends on it |
| `transcript_stream_id`, `stream_id`, `transcript_source_id` | Authoritative grouping meaning with compatibility aliases; `potential_contract_gap` | Currently supplied by callers/tests or copied by Transcript Builder; adapter path does not emit a stream ID | Transcript Builder and Boundary Builder | Canonical then two aliases; blank values become unknown | Add first-class stream identity at transcript ingress; define alias retirement conditions |
| `artifact_id`, `media_artifact_ids` | Observed payload plus later context metadata; `potential_contract_gap` when used for composition | Media Artifact adapter/interpreter and manually composed domain Evidence | Boundary Builder context extraction | Strings retained; no cross-domain identity contract validates them | Defer until a media Evidence Builder or persisted context needs authoritative identity |
| `boundary_context_id` | First-class in `SessionBoundaryEvidenceContext`, compatibility link in Evidence metadata; `acceptable_temporarily` | Session Boundary Builder | Session policy grouping and optional evaluation context | Valid EntityId parsed; absent ID isolates EvidenceSets conservatively | Add a typed Evidence-to-context reference before accepted state lineage is persisted |
| `boundary_anchor_seconds`, `boundary_anchor_at` | Organizational metadata that becomes authoritative only for ended-to-active freshness fallback; `potential_contract_gap` | Session Boundary Builder | Session policy ordering, profiles, and freshness | Numeric/ISO values parsed; invalid values ignored; anchor is explicitly not a final boundary | Keep organizational semantics; make freshness input explicit during state-acceptance/context work |
| `source_production_event_ids` | Authoritative traceability in metadata; known temporary compatibility; `acceptable_temporarily` | Observation Interpreter base | generic Evidence Builder and diagnostics | Tuple of Event ID strings; multi-event batches assign the full tuple to each Observation | Promote exact per-Observation Event IDs to a first-class field; preserve metadata during migration |
| `policy_id`, `applied_rule_id`, satisfied/unmet requirement IDs, effective current value | Authoritative evaluation explanation in metadata or Session wrapper; `potential_contract_gap` | generic/recording/session policies | summaries and future acceptance consumers | Mostly generated from typed IDs; generic contract does not require them | Make acceptance-required policy/evaluation lineage first-class in ED-0042 |
| `recording_transition_marker` | Structured compatibility metadata; `acceptable_temporarily` | legacy callers/tests | Recording Transition Policy | Used only when first-class Signals are absent; Signal always wins | Retain until all stored/provided Evidence is Signal-based; removal requires compatibility metrics and tests |
| descriptive counts/behavior labels | Supplementary metadata; `acceptable` | builders/policies | summaries/diagnostics | Safe defaults commonly used | No promotion recommended |

Metadata is not universally problematic. Most behavior labels, counts, notes, and
diagnostic flags are supplementary. Promotion should target only cross-layer identity,
semantic selection, and acceptance lineage.

## 8. Traceability

### Recording flow

`RecordingSessionEvent` creates a `ProductionEvent` with a new Event ID, correlation ID,
recording-block/stage references, source time, receipt time, and structured event-kind
payload. `RecordingActivityObservationInterpreter` creates an Observation ID, carries
the correlation and recording block, and records source Event IDs in metadata.
`RecordingCoverageEvidenceBuilder` creates EvidenceItem IDs and EvidenceSet IDs, keeps
Observation IDs first-class, links Signals to EvidenceItem and Observation IDs, and
records applied builder rule IDs. `RecordingTransitionPolicy` returns a
`TransitionEvaluation` with supporting/blocking EvidenceSet IDs and examined Signal
values.

Weaknesses: stage is dropped during interpretation; exact per-Observation Event lineage
is ambiguous for batch interpretation; the recording evaluation has policy ID only in
metadata and does not expose the selected rule ID; policy context selection is unsafe.

### Transcript flow

`TranscriptSegmentEvent` creates a Production Event with segment identity, artifact
type/status, optional text/language/confidence, correlation, and recording-block/stage
references. `TranscriptObservationInterpreter` creates an objective transcript
Observation and preserves exact text as observed data. The Transcript Continuity Builder
keeps Observation IDs, creates EvidenceItem/EvidenceSet IDs, Signal references, builder
rule IDs, input classifications, and deterministic grouping.

Weaknesses: stage is dropped, source Event lineage is batch-wide, and the concrete
adapter-to-interpreter path never supplies the transcript-stream identity on which the
builder’s strongest isolation key depends.

### Session start flow

Domain Evidence Signals are mapped by static Concern-and-Signal rules. The Session
Boundary Builder preserves source EvidenceSet, EvidenceItem, and Observation IDs;
creates stable boundary Evidence and context IDs; and groups by boundary orientation,
correlation, recording block, stage, known scheduled activity, and bounded temporal
neighborhood. The Session policy links each Signal to its EvidenceItem/Observation
source, checks categorical and independent-source requirements, preserves applied rule
and requirement IDs, and emits a stable evaluation ID when an evaluation timestamp is
supplied. Introduction plus independent speech, presentation plus transcript
continuity, or session content plus recording continuity can propose `active`.

Weaknesses: stage/schedule/context links are copied through metadata, and evaluation
lineage is split between the generic evaluation and Session-specific wrapper.

### Session end flow

The same lineage is preserved for possible-session-end Evidence. Explicit session or
transcript end may propose `ending`; two independent end indications including a
session/transcript-specific end may propose `ended`. Direct `active` to `ended` priority
is static and documented. Recording end alone cannot establish `ended`. Boundary anchors
remain organizational and `final_boundary_timestamp` remains `None`.

No trace is reduced to free-form rationale alone. The material gaps are exact Event
provenance, dropped stage context, and acceptance-oriented policy/evaluation lineage.

## 9. Context Isolation

Recording and Transcript Evidence Builders use the generic deterministic context key and
isolate known recording blocks/stages; Transcript additionally uses stream identity when
available. The Session Boundary Builder isolates boundary concern, correlation,
recording block, stage, known scheduled activity, and a maximum composition window. A
fully unknown boundary source receives an EvidenceSet discriminator rather than being
merged opportunistically. The Session policy additionally requires an explicit shared
boundary context before combining different boundary EvidenceSets.

Session context behavior is conservative and well tested. Composition time never
substitutes for identity, and organizational anchors do not become verified boundaries.

Risks:

- Recording Transition Policy has no context grouping or target context at all
  (ED0041-F001).
- Known stage context is dropped upstream by concrete interpreters (ED0041-F002).
- Transcript stream identity is optional metadata and absent from the concrete ingress
  path (ED0041-F004).
- Media artifact IDs are preserved by the Boundary Context but intentionally are not a
  grouping discriminator; this is reasonable for cross-artifact composition and no
  incorrect merge was verified from current mappings.

## 10. Determinism

Deterministic mechanics are explicit in generic Evidence ordering and deduplication,
both concrete Evidence Builders, Session Boundary composition, and Session policy. Sort
keys use timestamps, timeline offsets, IDs, and input index fallbacks. Static Session
rule priority documents direct terminal selection. Stable UUID5 IDs are used for Session
boundary rules/contexts/items/sets and Session evaluations.

Random IDs for new domain entities and recording policy evaluations are not themselves a
determinism defect; evaluation content is stable and identity creation is distinct from
rule selection. The recording policy’s first-rule-wins behavior is deterministic but not
safe when incompatible Signals coexist. Determinism does not make an ambiguous choice
correct.

Timezone awareness is not validated. Mixed naive/aware comparisons can raise raw
`TypeError`, and naive `.timestamp()` conversion can vary by host timezone. That is the
remaining cross-environment determinism risk (ED0041-F007).

## 11. Test Architecture

The 705-test suite provides substantial contract and behavioral regression protection:

- creation and validation of major contracts and enums
- positive and negative adapter/interpreter mappings
- Evidence semantic selection, ordering, deduplication, input classification, and
  compatibility fallbacks
- recording/transcript grouping, traceability, context, Signals, summaries, and
  determinism
- Session boundary composition, context isolation, ambiguity, source lineage, and
  architectural exclusions
- 69 focused Session transition cases covering lifecycle, categorical independence,
  contradiction, context compatibility, traceability, and deterministic behavior
- strict typing and immutable top-level collection tests

Important gaps are concentrated around the verified findings: no recording-policy
cross-block/correlation test, no current-state-kind validation test, no adapter-to-
interpreter test that expects block plus stage preservation, no exact per-Observation
batch provenance test, no invalid TransitionEvaluation combination tests, no nested
metadata immutability test, and no naive timestamp invariant tests.

Many architectural exclusion tests inspect only field/method names or source strings.
They are useful tripwires but cannot prove behavior is absent. They should remain as
supplementary checks, with targeted behavioral tests added when the findings are fixed.

## 12. Type Safety

Pyright strict mode is clean. Public functions and methods are annotated, sequences are
normalized, and unsafe casts are concentrated around deliberately untyped metadata.

Semantic weakness remains behind `Mapping[str, Any]`: authoritative lifecycle values,
context IDs, source IDs, and anchors are parsed at runtime. A technically valid metadata
mapping can contain nested mutable objects or incompatible types. This is not a reason to
replace all metadata with elaborate generic types. It supports focused payload/context/
lineage contracts for values reused across layers.

`OperationalStateSubject.subject_identifier` is a string to allow internal and external
identities. That flexibility is acceptable, but acceptance must validate the expected
subject type and identifier shape for the evaluated state kind.

## 13. Immutability

Frozen dataclasses, tuple normalization, and top-level `MappingProxyType` wrappers are
consistent. `ProductionEventPayload` is genuinely recursively immutable for JSON data.

Most other metadata wrappers are shallow. A caller can retain a list or dictionary
nested inside input metadata and mutate the observable contents of an otherwise frozen
Observation, EvidenceSet, result, or evaluation after construction. This is especially
important because some metadata is authoritative. ED0041-F006 recommends a shared,
small recursive freeze/validation utility or contract-specific defensive copying under a
targeted directive; ED-0041 does not change those contracts.

## 14. Performance

No single-invocation blocker was verified. Concrete builders are predominantly
`O(n log n)` from deterministic sorting plus linear grouping and construction. Static
mapping/rule scans are over small fixed collections. Session policy evaluation is
approximately `O(n log n + g*r*c)` for input ordering plus group/rule/contribution
assessment, with small rule count.

The realistic risk is repeated full rebuild:

- affected paths: Recording Coverage Builder, Transcript Continuity Builder, Session
  Boundary Builder, and Session policy
- per invocation: approximately `O(n log n)` plus output reconstruction
- cumulative if invoked after each of `n` arrivals: approximately `O(n² log n)` and
  repeated allocation/metadata parsing
- likely scale: hundreds of 60-second media segments per stage and thousands of
  transcript Observations over a multi-hour event
- why it matters: constrained event environments should not spend increasing CPU on old
  inputs after every small arrival
- measurement: benchmark 1, 4, 8, and 16 stages with 500 media and 10,000 transcript
  Observations, measuring batch rebuild cadence and memory allocation
- recommendation: establish realistic batching/rebuild cadence before considering
  incremental APIs; do not add caching without an invalidation model

This is a low, pre-runtime risk rather than a reason to optimize current code now.

## 15. Compatibility

| Compatibility path | Why it exists | Authoritative path | Fallback | Coverage | Recommendation |
| --- | --- | --- | --- | --- | --- |
| `recording_transition_marker` | Pre-ED-0035 recording Evidence | `EvidenceSignalReference` | Marker only when Signals are absent | Explicit first-class-overrides-marker and marker tests | Retain; remove only after all stored/provided Evidence is Signal-based |
| Recording semantic key fallback | Earlier Observations may expose event kind rather than normalized activity | `recording_activity` | `recording_event_kind` | Selector priority/compatibility tests | Retain through typed payload migration |
| Transcript stream aliases | Multiple earlier producer names | `transcript_stream_id` | `stream_id`, then `transcript_source_id` | Fallback tests exist | Define canonical ingress field before deprecation |
| Scheduled activity alias | Earlier source metadata uses `schedule_activity_id` | `scheduled_activity_id` | Alias read by Boundary Builder | Indirect composition coverage | Retain until producer inventory exists |
| Session boundary context metadata | EvidenceSet has no first-class context reference | `SessionBoundaryEvidenceContext.id` | `boundary_context_id` copied to Evidence metadata | Extensive ED-0039/0040 tests | Retain; replace only with typed reference and migration |
| Optional builder `input_report` | Results constructed before ED-0038 remain valid | Populated `EvidenceBuilderInputReport` | Direct classification fields | Current builders always populate; result construction permits `None` | Retain now; add consistency rules in targeted result-contract work |

No compatibility behavior was removed.

## 16. Documentation

Package READMEs through ED-0040 accurately preserve the principal layer boundaries,
Session lifecycle, missing-Evidence semantics, context rules, non-scoring behavior, and
execution exclusions. Manifest entries and public exports match implemented packages.

Corrected directly under ED-0041:

- the stale backend test-suite README, which stopped at ED-0011
- repository manifest ownership/entries for the ED-0041 review deliverables
- the Engineering Directive index

Deferred documentation drift is recorded in ED0041-F011: older canonical architecture
documents retain broad live-production/monitoring and Session-centric wording. AR-2.x
already adds clarifying notes, so this is not a code blocker and should be reconciled in
one architecture-document directive rather than piecemeal edits.

## 17. Repository Organization

Package boundaries are coherent and imports are acyclic under the current suite. Domain
meaning remains in concrete packages. Generic packages remain small. Public exports are
explicit. Test naming follows package ownership.

The one unclear ownership boundary is the coexistence of ED-0014
`production/interpreter` and ED-0023 `production/observation_interpreter`, with the
dispatcher tied to the former and concrete interpreters built on the latter. The current
README documents coexistence, so no move or rename is justified in ED-0041. A focused
runtime composition directive should choose a single dispatcher-facing protocol and
retain compatibility deliberately.

## 18. Security And Data Handling

No credentials, secrets, private keys, or provider tokens were found in reviewed source,
tests, or documentation. `ProductionEventPayload` validates JSON-compatible values,
rejects non-finite floats, and recursively freezes nested data.

Transcript text excerpts and visual/operator details are deliberately retained as
observed metadata. They are not copied into Evidence rationale, transition rationale, or
public summary contracts by the reviewed flow. This is acceptable now. Future logging or
persistence must treat Observation metadata as potentially sensitive and avoid emitting
full payloads by default.

Arbitrary general metadata is not JSON-validated and can hold provider/path objects, but
no current public API, persistence, or logging path exposes it. No security remediation
is required before ED-0042.

## 19. State Acceptance Readiness

| Readiness issue | Classification | Required response |
| --- | --- | --- |
| Recording policy can combine incompatible recording Evidence and accept a mismatched current-state domain | `blocker` | Fix ED0041-F001 before ED-0042 |
| Concrete interpretation loses known stage and exact per-Observation batch provenance | `blocker` | Fix ED0041-F002 before ED-0042 |
| TransitionEvaluation lacks outcome/current-kind invariants and first-class policy/rule lineage | `important_but_nonblocking` | Make validation and lineage the first phase of ED-0042; do not accept arbitrary evaluations |
| OperationalStateBasis lacks accepted TransitionEvaluation reference | `important_but_nonblocking` | Add immutable evaluation lineage during ED-0042 |
| Accepted-at versus evaluated-at versus boundary-anchor semantics | `important_but_nonblocking` | ED-0042 must introduce a distinct acceptance timestamp and never reuse a boundary anchor |
| Subject kind/identifier matrix is only partially validated | `important_but_nonblocking` | Acceptance must validate supported subject type and preserve current subject |
| Authoritative context remains partly in metadata | `defer` | Preserve a snapshot/reference in acceptance; promote through targeted context work before persistence |
| Shallow nested metadata immutability | `defer` | Do not mutate; address in a targeted contract-hardening directive |

After F001 and F002 are corrected, ED-0042 may proceed if it:

- accepts only `transition_supported` or explicitly approved `already_current` behavior
- validates `evaluated_state_kind`, current-state kind/subject/status, proposed value, and
  supporting/blocking invariants
- creates a successor state without mutating the prior state
- preserves the prior state ID, Transition Evaluation ID, policy/rule identity, and
  Evidence basis
- records a separate acceptance timestamp
- does not persist or execute the transition

## 20. Positive Findings

- StageFlow’s mission remains visible in code and documentation.
- Recorded media and transcript Evidence are central; schedule/operator context is
  explicitly non-conclusive.
- The Session boundary and transition layers are unusually well explained and tested.
- Missing Evidence is consistently distinct from contradiction.
- Strength is preserved rather than inflated or turned into hidden confidence.
- Context ambiguity returns insufficient Evidence instead of choosing a score winner.
- Session direct-terminal rule priority is static, documented, and tested.
- Generic Evidence mechanics are appropriately extracted without hiding concrete rules.
- ID-only lineage is extensive across Observation, EvidenceItem, EvidenceSet, Signals,
  boundary outputs, and transition evaluations.
- No policy mutates state or executes runtime effects.
- No realistic single-pass performance blocker, secret exposure, or provider coupling was
  found.

## 21. Risks

Highest risks are accepting a Recording Transition Evaluation produced from mixed
contexts, accepting an evaluation whose generic contract does not prove internal
consistency, and losing stage/provenance information before Evidence is built. Secondary
risks are authoritative untyped metadata, shallow nested mutability, timezone ambiguity,
and cumulative full rebuild cost once runtime orchestration arrives.

The principal change risk is over-correcting. Remediation should not create a generic
rules engine, score candidates, merge interpreter packages aesthetically, remove
compatibility, or promote every metadata field. It should add only explicit validation,
context preservation, and lineage required by demonstrated flows.

## 22. Recommended Next Steps

1. Complete the focused Recording Transition Policy Context Safety directive.
2. Complete the focused Observation Context and Provenance Preservation directive.
3. Re-run ED-0041 blocker checks and quality gates.
4. Begin ED-0042 with Transition Evaluation validation and immutable acceptance lineage,
   then implement non-persistent/non-executing state acceptance.
5. Schedule metadata/context hardening, interpreter runtime composition, timestamp
   invariants, and metadata immutability as separate follow-ups.
6. Benchmark rebuild cadence only when a realistic runtime invocation model exists.

Final decision: `pause_for_blocking_remediation`.
