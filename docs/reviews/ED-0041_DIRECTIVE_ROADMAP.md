# ED-0041 Directive Roadmap

**Review decision:** `pause_for_blocking_remediation`

ED-0042 should not begin until the two focused preconditions below are complete. This is
not a request to redesign the reasoning architecture. The existing Session boundary and
Session transition design should remain intact.

## Fix Before ED-0042

### 1. Recording Transition Policy Context Safety

**Findings:** ED0041-F001, relevant tests from ED0041-F010

**Scope:**

- validate recording current-state kind, subject, status, and target recording block
- group/select recording Evidence by compatible recording block, stage, and correlation
- bind Evidence roles to the EvidenceItem linked by each Signal reference
- return insufficient/unknown rather than selecting across incompatible qualifying
  contexts
- preserve Signal-first semantics and the legacy marker fallback
- add focused cross-context, mixed-Signal, contradiction, duplicate, and invalid-current-
  state tests

**Out of scope:** state mutation, acceptance, persistence, scoring, generic rules engines,
or removal of legacy metadata.

### 2. Observation Context and Provenance Preservation

**Findings:** ED0041-F002, relevant tests from ED0041-F010

**Depends on:** current ObservationLocation and Observation Interpreter contracts

**Scope:**

- preserve known stage alongside recording block/wall-clock information truthfully
- preserve exact source Production Event IDs per Observation
- distinguish exact Observation lineage from batch-level Event membership
- retain compatibility metadata while establishing the first-class authority
- cover adapter Event → concrete Observation → Evidence grouping for recording and
  transcript paths

**Out of scope:** interpreter package reorganization, persistence, runtime queues, or
provider integrations.

After both directives, rerun the ED-0041 blocker audit and all quality gates. If the
findings are closed without introducing new blockers, the review decision can advance to
`proceed_with_ED_0042_with_constraints`.

## Address During ED-0042

### Operational State Acceptance with Contract Validation

**Finding:** ED0041-F003

**Depends on:** both pre-ED-0042 directives above

**Required first phase:**

- validate `TransitionEvaluation` outcome/proposed-state/current-state invariants
- accept only explicitly supported outcomes
- require the evaluation kind to match the current and successor state kind
- preserve policy ID, applied rule ID when available, Transition Evaluation ID,
  supporting Evidence IDs, and predecessor state ID
- validate subject type/identifier and preserve the existing subject
- create an immutable successor without mutating the predecessor
- record an acceptance timestamp distinct from Event, Observation, evaluation, and
  boundary-anchor times
- describe supersession without persistence or execution

ED-0042 must not use free-form rationale or unvalidated metadata as the sole authority
for acceptance. It may preserve compatibility metadata in addition to first-class
lineage.

## Targeted Follow-Up Directives

Recommended dependency order after ED-0042 contract validation is designed:

1. **Authoritative Observation and Evidence Context Contracts**
   Findings: ED0041-F004. Promote only repeated semantic/context authority: recording
   activity, transcript lifecycle/stream identity, stage/scheduled activity Evidence
   context, and boundary context reference. Preserve aliases during migration.

2. **Perception Runtime Composition Boundary**
   Finding: ED0041-F005. Define a small dispatcher-facing interpreter protocol or an
   explicit adapter between ED-0014 and ED-0023 contracts. Do not reorganize packages for
   aesthetics.

3. **Immutable Metadata Boundary Hardening**
   Finding: ED0041-F006. Inventory metadata value types and recursively freeze or
   defensively copy metadata crossing reasoning/acceptance boundaries.

4. **Production Timestamp Invariants**
   Finding: ED0041-F007. Establish UTC-aware inputs, domain errors for mixed awareness,
   and explicit timestamp roles.

5. **Result and Summary Consistency Hardening**
   Finding: ED0041-F008. Establish authoritative result fields and validate compatibility
   copies/optional input reports.

6. **AR-3.0 Documentation and Mission Alignment**
   Finding: ED0041-F011. Reconcile older live-production/monitoring and Session-centric
   language with the recorded-media observational mission while preserving historical
   context.

Each directive should include the behavioral tests identified by ED0041-F010. A
standalone test-suite rewrite is not recommended.

## Deferred Improvements

### Reasoning Pipeline Workload Benchmark and Invocation Model

**Finding:** ED0041-F009

Defer until a runtime cadence exists. Benchmark finite batch and repeated rebuild paths
using realistic stages, media segments, and transcript counts. Do not add caching without
replay and invalidation semantics.

### Compatibility retirement planning

Retain the recording transition marker, recording semantic fallback,
transcript-stream aliases, scheduled-activity alias, boundary-context metadata, and
optional `input_report`. Removal conditions require producer/storage inventory and
explicit migration tests.

### Security policy for future persistence/logging

**Finding:** ED0041-F012

Define redaction and retention only when persistence or logging of Observation payloads
is introduced. No present code change is recommended.

## No Action Recommended

- Keep explicit mappings and categorical rules in concrete builders and policies.
- Keep generic Evidence mechanics limited to ordering, deduplication, semantic selection,
  context-key shape, and input reporting.
- Keep missing Evidence distinct from contradiction.
- Keep Evidence Strength descriptive and non-scored.
- Keep Session Boundary anchors organizational and non-final.
- Keep multiple incompatible Session contexts ambiguous.
- Keep policy evaluation separate from acceptance, persistence, and runtime effects.
- Keep transcript text as observed data at the Observation layer; do not infer meaning.
- Do not introduce AI, candidate scoring, generalized state machines, or provider-specific
  semantics.
- Do not consolidate concrete builders merely to reduce line count (ED0041-F013).

## Recommendation For ED-0042

Current recommendation: **do not proceed yet**.

Decision: `pause_for_blocking_remediation`.

Reason: ED0041-F001 can produce a recording evaluation from incompatible context, and
ED0041-F002 loses known isolation/provenance before Evidence is built. State acceptance
would turn those descriptive weaknesses into accepted operational history. Once both are
closed, ED-0042 can proceed with the contract-validation and lineage constraints listed
above.
