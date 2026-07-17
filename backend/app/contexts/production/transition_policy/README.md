# Operational State Transition Policy

ED-0034 adds generic Operational State Transition Policy contracts.

Policy evaluates.

Evaluation explains.

State records.

Execution is deferred.

## Scope

An `OperationalStateTransitionPolicy` receives an optional current `OperationalState` and applicable `EvidenceSet` objects. It evaluates deterministic policy rules and returns a `TransitionEvaluation`.

The generic policy contract does not mutate state, persist state, execute transitions, dispatch events, call AI, access infrastructure, create Hypotheses, create Findings, create Verification Decisions, or create Operational Products.

`TransitionEvaluation` is not a command. It records the evaluated state kind, optional current state, optional proposed state value, outcome, supporting Evidence IDs, blocking Evidence IDs, rationale, timestamp, and metadata.

## Outcomes

- `transition_supported`
- `transition_not_supported`
- `insufficient_evidence`
- `already_current`
- `unknown`

Transition policy is the first layer that may justify a change in StageFlow's operational understanding. State mutation and execution remain out of scope.

## Recording Context Safety

ED-0042 makes the concrete Recording Transition Policy evaluate only one compatible
recording Evidence context at a time. It validates recording-state kind, subject, value,
and context compatibility before a lifecycle proposal. Multiple incompatible qualifying
recording contexts, unresolved conflicting Signals, and unknown-context conflicts return
conservative outcomes rather than selecting a first matching rule. This is a
recording-policy-local safety correction; the generic `TransitionEvaluation` contract is
unchanged and state acceptance remains deferred.

## Session Transition Policy

ED-0040 adds a concrete Session Transition Policy above ED-0039 boundary Evidence. It
accepts only `possible_session_start` and `possible_session_end` Evidence and proposes
the narrow Session values inactive, active, ending, or ended.

The policy uses categorical Signal categories, explicit Evidence roles, independent
Observation traceability, and compatible boundary context. It does not use scores,
confidence, Signal weights, ED-0039's composition window, or organizational anchors as
transition proof. It returns one generic `TransitionEvaluation` inside a descriptive
Session-specific result containing its Evidence profile and requirement diagnostics.

Session evaluation does not mutate Operational State, execute a transition, create a
Session aggregate, choose a final boundary timestamp, persist anything, or create
downstream reasoning or Operational Products.

## Operational State Acceptance

ED-0044 adds a separate acceptance layer after policy evaluation. A
`transition_supported` outcome is necessary but not sufficient for state creation.
Acceptance independently validates the evaluation identity, approved policy kind and
policy ID, applied rule ID, current state, proposed lifecycle, subject, known context,
supporting Evidence, Observation lineage, exact source Production Event lineage, and
caller-supplied acceptance history.

The concrete Recording and Session policies expose stable policy/rule identity and
post-ED-0043 lineage for this handoff. The generic `TransitionEvaluation` contract is
not destructively redesigned; policy-specific result profiles populate a separate
ID-only acceptance-lineage contract.

Policy still does not create or mutate state. Acceptance never invokes a policy or
re-evaluates whether Evidence was persuasive. It may create one immutable successor
record, but it neither persists the successor nor executes a transition.
