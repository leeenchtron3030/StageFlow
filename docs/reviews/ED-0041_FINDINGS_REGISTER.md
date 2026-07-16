# ED-0041 Findings Register

## Summary

| Severity | Count |
| --- | ---: |
| critical | 1 |
| high | 2 |
| medium | 5 |
| low | 3 |
| informational | 2 |
| **Total** | **13** |

## ED0041-F001

- **Title:** Recording Transition Policy can combine incompatible Evidence and select the first rule
- **Category:** correctness
- **Severity:** critical
- **Status:** open
- **Affected files:** `backend/app/contexts/production/recording_transition_policy/recording_transition_policy.py`; `backend/tests/test_recording_transition_policy_contracts.py`
- **Observed evidence:** `evaluate()` filters only on `EvidenceConcern.RECORDING_COVERAGE`. `_blocking_evidence()` blocks on any contradicting item across all retained sets. `_supported_evidence()` accepts any set containing any supporting item. `_proposed_state()` iterates static rules and selects the first Signal found without checking correlation, recording block, stage, current-state subject, or the Signal reference’s linked item role. The current state kind and subject are not validated.
- **Architectural or operational impact:** Evidence from different recording blocks/correlations can block or support one another, and incompatible start/pause/end Signals can produce a deterministic but semantically arbitrary first-rule result. A state-acceptance layer could record the wrong recording state or accept a recording evaluation against a Session state.
- **Recommended response:** Require a compatible target recording context; validate current state kind/subject/status; bind roles to linked Signal contributions; return an explicit ambiguous/insufficient result for incompatible qualifying contexts; document static priority only where lifecycle policy genuinely requires it.
- **Risk of changing it:** Medium-high. Existing callers may pass mixed Evidence and rely unintentionally on first-rule behavior. Preserve the legacy marker fallback but subject it to the same context and role rules.
- **Suggested directive:** Recording Transition Policy Context Safety
- **Disposition:** `fix_before_ED_0042`

## ED0041-F002

- **Title:** Concrete Observation interpretation loses known stage and exact per-Event provenance
- **Category:** traceability
- **Severity:** high
- **Status:** open
- **Affected files:** concrete `*observation_interpreter.py` modules; `observation_interpreter/observation_interpreter.py`; adapter Event contracts; corresponding interpreter tests
- **Observed evidence:** Recording, media artifact, transcript, and vision adapter Events can contain both stage and recording-block references. Their concrete interpreters choose `ObservationLocation.for_recording_block()` when a block is known and never preserve the stage reference or `ObservationInterpreterContext.stage_id`; schedule and clock interpreters choose wall-clock only. Recording/Transcript Evidence Builders later group on `observation.location.stage_id`. Separately, `_observations_with_traceability()` overwrites every Observation in a multi-Event call with the full batch’s Event ID tuple, and tests explicitly assert that behavior.
- **Architectural or operational impact:** Known context disappears before Evidence construction, weakening cross-stage isolation. Batch-produced Observations cannot identify which specific Event produced each Observation without inspecting order or payload. Both issues reduce explainability and can contaminate later grouping when recording-block/stream context is also absent.
- **Recommended response:** Build a truthful composite location when multiple known anchors exist, or add first-class context fields with clear authority; preserve exact per-Observation source Event IDs and keep batch IDs only at result level; retain metadata compatibility during migration.
- **Risk of changing it:** Medium. Existing tests and consumers expect recording-block-only locations and batch-wide Event ID metadata. Migration must distinguish exact lineage from batch membership.
- **Suggested directive:** Observation Context and Provenance Preservation
- **Disposition:** `fix_before_ED_0042`

## ED0041-F003

- **Title:** Transition and state contracts lack acceptance-grade invariants and lineage
- **Category:** contract_design
- **Severity:** high
- **Status:** open
- **Affected files:** `transition_policy/transition_evaluation.py`; `transition_policy/transition_reason.py`; `operational_state/operational_state.py`; `operational_state/operational_state_basis.py`; Session transition result/summary; generic transition tests
- **Observed evidence:** `TransitionEvaluation.__post_init__()` only tuple-normalizes IDs and wraps metadata. It does not validate current state kind, outcome/proposed-state compatibility, or supporting versus blocking shape. The generic test suite constructs a `transition_supported` evaluation containing both supporting and blocking IDs. Policy ID is metadata; applied rule and requirement IDs are Session-wrapper fields plus duplicated metadata; recording evaluations expose no selected rule ID. `OperationalStateBasis` has Observation and EvidenceSet IDs but no Transition Evaluation ID or prior state ID.
- **Architectural or operational impact:** A generic acceptance layer cannot safely trust the evaluation shape or preserve the full acceptance lineage using first-class contracts. Metadata conventions could silently become authoritative.
- **Recommended response:** Make evaluation validation, policy/rule lineage, predecessor state identity, accepted evaluation identity, and a distinct acceptance timestamp the first ED-0042 work. Reject unsupported/unknown/internally contradictory evaluations before creating a successor state.
- **Risk of changing it:** Medium-high. Tightened validation may reject manually constructed fixtures or legacy evaluations. Introduce factories/migration paths rather than silently changing serialized meaning.
- **Suggested directive:** Operational State Acceptance, constrained by Transition Evaluation Validation
- **Disposition:** `address_during_ED_0042`

## ED0041-F004

- **Title:** Cross-layer semantic and context authority remains distributed through metadata
- **Category:** metadata
- **Severity:** medium
- **Status:** open
- **Affected files:** Recording/Transcript Observation Interpreters and Evidence Builders; Session Boundary Builder/Context; Session Transition Policy/Summary; Observation and Evidence contracts
- **Observed evidence:** `recording_activity`, `recording_event_kind`, and `transcript_lifecycle` determine semantic selection. Stage and scheduled activity IDs are copied into Evidence metadata and parsed by boundary/policy code. Transcript stream identity uses three metadata aliases and is not emitted by the concrete transcript ingress path. Boundary context IDs and organizational anchors are first-class in the context object but copied to Evidence metadata for policy use. Ended-to-active freshness can depend on anchor metadata. Policy/rule/effective-current details are metadata in the generic evaluation.
- **Architectural or operational impact:** Typos, malformed IDs, alias divergence, or missing writer behavior can change grouping and policy outcomes while remaining invisible to Pyright. State acceptance or persistence would make these conventions harder to migrate.
- **Recommended response:** Promote only reused authoritative semantics: typed Observation semantic payload, reusable Evidence context reference, transcript stream identity, and acceptance lineage. Keep supplementary diagnostics in metadata and retain compatibility aliases until producers are inventoried.
- **Risk of changing it:** High if attempted as one migration. Split by authority boundary and preserve readers during transition.
- **Suggested directive:** Authoritative Observation and Evidence Context Contracts
- **Disposition:** `defer_to_targeted_directive`

## ED0041-F005

- **Title:** Dispatcher and concrete Perception Layer use incompatible interpreter abstractions
- **Category:** architecture
- **Severity:** medium
- **Status:** acknowledged
- **Affected files:** `dispatcher/production_event_dispatcher.py`; `interpreter/`; `observation_interpreter/`; all concrete Observation Interpreter packages; Production README
- **Observed evidence:** `ProductionEventDispatcher.interpreters` is typed as ED-0014 `ProductionEventInterpreter`, while ED-0024+ concrete interpreters wrap ED-0023 `ObservationInterpreter` and are not substitutable under strict typing. Documentation explicitly says both foundations remain.
- **Architectural or operational impact:** The documented Production Event → Dispatcher → concrete Observation Interpreter path is not directly composable. Future runtime code would need an unapproved adapter, duplicate dispatcher, or type bypass.
- **Recommended response:** Define the smallest dispatcher-facing protocol demonstrated by both implementations or adapt the dispatcher to the concrete contract. Preserve old contracts only if a live compatibility consumer exists.
- **Risk of changing it:** Medium. Aesthetic package consolidation would be excessive; runtime consumers are not yet implemented, so choose the boundary before adding them.
- **Suggested directive:** Perception Runtime Composition Boundary
- **Disposition:** `defer_to_targeted_directive`

## ED0041-F006

- **Title:** Frozen contracts expose shallowly mutable nested metadata
- **Category:** immutability
- **Severity:** medium
- **Status:** open
- **Affected files:** most metadata-bearing frozen dataclasses under `backend/app/contexts/production/` and shared domain events; tests covering immutability
- **Observed evidence:** Most `__post_init__()` methods use `MappingProxyType(dict(self.metadata))`, which freezes only the top-level mapping. Nested caller-owned dictionaries/lists remain mutable. `ProductionEventPayload` already demonstrates recursive JSON validation/freezing, but general metadata does not use it.
- **Architectural or operational impact:** A caller can mutate an Observation, EvidenceSet, result, or Transition Evaluation indirectly after construction. Because some metadata is authoritative, equality, summaries, grouping, or acceptance decisions can change despite frozen dataclasses.
- **Recommended response:** Under a focused directive, define a small recursive freeze/validation rule for metadata that crosses reasoning or acceptance boundaries. Do not force every internal diagnostic object into a new framework.
- **Risk of changing it:** Medium. Callers may store non-JSON objects in metadata. Inventory value types and provide a compatibility error/migration policy.
- **Suggested directive:** Immutable Metadata Boundary Hardening
- **Disposition:** `defer_to_targeted_directive`

## ED0041-F007

- **Title:** Timezone awareness is not a contract invariant
- **Category:** compatibility
- **Severity:** medium
- **Status:** open
- **Affected files:** Production Event, timeline, Observation, Evidence, boundary context, Transition Evaluation, adapters, and shared time contracts
- **Observed evidence:** externally supplied datetimes are compared and sorted without validating timezone awareness. Mixed naive/aware values can raise `TypeError`; Session Boundary grouping calls `.timestamp()` on `anchor_at`, which interprets naive time in the host timezone. Metadata timestamp parsers silently assign UTC to naive parsed values.
- **Architectural or operational impact:** Equal source data can order differently across hosts, fail with non-domain exceptions, or acquire an implicit timezone. Accepted-state time semantics would be fragile.
- **Recommended response:** Establish UTC-aware input invariants and explicit normalization boundaries; test mixed and naive timestamps; keep acceptance time distinct from event, observation, evaluation, and boundary-anchor times.
- **Risk of changing it:** Medium. Existing callers may supply naive values. Fail clearly or migrate at adapter boundaries rather than silently reinterpret persisted times.
- **Suggested directive:** Production Timestamp Invariants
- **Disposition:** `defer_to_targeted_directive`

## ED0041-F008

- **Title:** Result contracts duplicate classification and traceability facts without consistency checks
- **Category:** maintainability
- **Severity:** low
- **Status:** open
- **Affected files:** Recording/Transcript Evidence result contracts and summaries; Session transition result/summary/evaluation metadata
- **Observed evidence:** concrete builder results expose direct consumed/ignored/unsupported/duplicate/applied-rule fields and an optional `EvidenceBuilderInputReport` containing the same classifications. Constructors do not reconcile them. Session result fields duplicate applied/satisfied/unmet IDs stored in evaluation metadata; `SessionTransitionSummary` reads effective current state from metadata while other values come from typed fields.
- **Architectural or operational impact:** Manually constructed or deserialized results can disagree, and summaries may report a hybrid of conflicting sources.
- **Recommended response:** Declare one authoritative representation and validate compatibility copies. Retain optional `input_report` until legacy constructors are inventoried.
- **Risk of changing it:** Low-medium. Strict validation may break older test fixtures or serialized results.
- **Suggested directive:** Result and Summary Consistency Hardening
- **Disposition:** `defer_to_targeted_directive`

## ED0041-F009

- **Title:** Stateless repeated full rebuild may become cumulatively expensive
- **Category:** performance
- **Severity:** low
- **Status:** monitor
- **Affected files:** Recording Coverage Builder, Transcript Continuity Builder, Session Boundary Builder, Session Transition Policy
- **Observed evidence:** each invocation tuple-copies, sorts, deduplicates, reparses context metadata, and reconstructs outputs. A single build is approximately `O(n log n)`, but rebuilding after every arrival yields roughly `O(n² log n)` cumulative work.
- **Architectural or operational impact:** Thousands of transcript Observations across many stages could cause increasing latency and allocations once runtime orchestration invokes builders frequently.
- **Recommended response:** Benchmark realistic batch cadence (500 media/10,000 transcript Observations across 1–16 stages). Prefer bounded batching first. Add incremental processing only with an explicit invalidation and replay model.
- **Risk of changing it:** High if caching is introduced prematurely; stale reasoning would be worse than recomputation.
- **Suggested directive:** Reasoning Pipeline Workload Benchmark and Invocation Model
- **Disposition:** `defer_to_targeted_directive`

## ED0041-F010

- **Title:** Test suite misses the reviewed safety boundaries and overuses name-based exclusions
- **Category:** testing
- **Severity:** medium
- **Status:** open
- **Affected files:** recording transition, interpreter, transition-policy, immutability, and timestamp tests; architectural exclusion tests across the suite
- **Observed evidence:** no tests cover mixed recording blocks/correlations, mismatched recording current state, Signal-to-role linkage, block-plus-stage preservation, exact batch Event lineage, invalid TransitionEvaluation combinations, nested metadata mutation, or timezone mixing. Many “does not implement” tests scan field/method names or source strings, which cannot prove behavior.
- **Architectural or operational impact:** The full suite passes while F001–F003 remain possible. Name checks may create confidence without exercising production-shaped flows.
- **Recommended response:** Add behavior-first regression tests with each targeted fix. Keep name/source checks as supplementary architectural tripwires, not primary proof. Add at least one adapter-to-policy representative flow test after context/provenance remediation.
- **Risk of changing it:** Low. Avoid a giant integration fixture that hides domain meaning.
- **Suggested directive:** Included with each remediation directive; no standalone test rewrite
- **Disposition:** `defer_to_targeted_directive`

## ED0041-F011

- **Title:** Test-suite and legacy architecture documentation drift from implemented scope and mission wording
- **Category:** documentation
- **Severity:** low
- **Status:** partially corrected
- **Affected files:** `backend/tests/README.md`; `REPOSITORY_MANIFEST.md`; older architecture documents including `docs/03.6_Architecture_Layers.md` and `docs/00.5_Domain_Model.md`
- **Observed evidence:** the backend test README stopped at ED-0011; the manifest’s top-level backend test row described only health/shared coverage. Older architecture text says StageFlow owns broad live production workflow/operational monitoring and contains strongly Session-centric ownership language, while AR-2.x and ED-0041 narrow StageFlow to recorded-media observation and non-controlling reasoning.
- **Architectural or operational impact:** Contributors can infer broader production-control responsibility or underestimate regression coverage.
- **Recommended response:** ED-0041 updates test/manifest/index documentation. Reconcile canonical mission and legacy Session wording in one architecture documentation release while retaining historically useful domain material.
- **Risk of changing it:** Low, but piecemeal edits could erase intentional historical context.
- **Suggested directive:** AR-3.0 Documentation and Mission Alignment
- **Disposition:** `documentation_only`

## ED0041-F012

- **Title:** Sensitive observed payloads remain contained but need future logging discipline
- **Category:** security
- **Severity:** informational
- **Status:** reviewed
- **Affected files:** transcript/vision/operator adapters and interpreters; Production Event payload; summaries
- **Observed evidence:** transcript excerpts and visual/operator details are retained in Event/Observation payload metadata, as documented. They are not copied into Evidence/transition rationale or current summary contracts. No secrets or credentials were found. `ProductionEventPayload` is validated and recursively immutable.
- **Architectural or operational impact:** No current exposure path exists. Future persistence/logging could leak speaker or provider data if it serializes arbitrary metadata wholesale.
- **Recommended response:** When logging/persistence is introduced, default to IDs and summaries and require explicit payload redaction/retention rules.
- **Risk of changing it:** No current change recommended; removing observed text now would reduce fidelity.
- **Suggested directive:** Future persistence/logging data-handling scope
- **Disposition:** `no_action_recommended`

## ED0041-F013

- **Title:** Explicit concrete duplication and narrow generic mechanics are appropriate
- **Category:** duplication
- **Severity:** informational
- **Status:** reviewed
- **Affected files:** generic Evidence Builder mechanics; Recording Coverage, Transcript Continuity, Session Boundary, Recording Transition, and Session Transition packages
- **Observed evidence:** generic code owns ordering, deduplication, semantic selection, context-key shape, and input reporting. Concrete packages retain their mappings, Signals, grouping meaning, rationale, and policy requirements. Similar builder code differs in operational semantics and only two concrete implementations demonstrate some mechanics.
- **Architectural or operational impact:** Operational meaning remains readable and changes stay localized. Further extraction would risk hiding rules in a framework.
- **Recommended response:** Keep the current generic/concrete boundary. Extract only a domain-neutral need demonstrated by at least two implementations and backed by simpler tests.
- **Risk of changing it:** High abstraction risk with little current benefit.
- **Suggested directive:** None
- **Disposition:** `no_action_recommended`
