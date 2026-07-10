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
