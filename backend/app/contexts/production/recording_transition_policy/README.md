# Recording Transition Policy

ED-0034 adds the first concrete Operational State Transition Policy.

ED-0035 updates this policy to consume first-class Evidence Signals for core recording transition meaning.

The Recording Transition Policy evaluates recording-related `EvidenceSet` objects and returns a `TransitionEvaluation` for recording state only.

Supported proposed recording values:

- `active`
- `paused`
- `stopped`

`inactive` may be a current recording state, but the policy does not invent a new transition to inactive.

## Rules

- Recording becomes active when Recording Coverage Evidence carries `recording_continuity_established` or `recording_continuity_restored`.
- Recording becomes paused when Recording Coverage Evidence carries `recording_pause_indicated`.
- Recording becomes stopped when Recording Coverage Evidence carries `recording_end_indicated`.
- If Evidence is incomplete, the policy returns `insufficient_evidence`.
- If current state already matches the proposed state, the policy returns `already_current`.
- If recording Evidence blocks the transition, the policy returns `transition_not_supported`.

The policy ignores transcript, vision, schedule, editorial, media artifact, and other unrelated Evidence.

Legacy metadata markers such as `recording_active`, `recording_paused`, and `recording_stopped` remain readable only as transitional compatibility when an EvidenceSet has no first-class signals. `EvidenceSignal` is authoritative for core transition meaning.

## Deferred

The Recording Transition Policy does not mutate state, execute transitions, persist state, implement repositories, dispatch events, create Hypotheses, create Findings, create Verification Decisions, create Operational Products, call AI, use queues or workers, expose APIs, or add frontend behavior.
