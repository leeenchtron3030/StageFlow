# Recording Transition Policy

ED-0034 adds the first concrete Operational State Transition Policy.

The Recording Transition Policy evaluates recording-related `EvidenceSet` objects and returns a `TransitionEvaluation` for recording state only.

Supported proposed recording values:

- `active`
- `paused`
- `stopped`

`inactive` may be a current recording state, but the policy does not invent a new transition to inactive.

## Rules

- Recording becomes active only if Recording Coverage Evidence supports active recording.
- Recording becomes paused only if Recording Pause Evidence supports paused recording.
- Recording becomes stopped only if Recording Stop Evidence supports stopped recording.
- If Evidence is incomplete, the policy returns `insufficient_evidence`.
- If current state already matches the proposed state, the policy returns `already_current`.
- If recording Evidence blocks the transition, the policy returns `transition_not_supported`.

The policy ignores transcript, vision, schedule, editorial, media artifact, and other unrelated Evidence.

## Deferred

The Recording Transition Policy does not mutate state, execute transitions, persist state, implement repositories, dispatch events, create Hypotheses, create Findings, create Verification Decisions, create Operational Products, call AI, use queues or workers, expose APIs, or add frontend behavior.
