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
