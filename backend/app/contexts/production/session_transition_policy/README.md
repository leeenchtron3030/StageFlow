# Session Transition Policy

ED-0040 adds a narrow, deterministic policy that consumes ED-0039 Session Boundary
Evidence and produces an explainable generic `TransitionEvaluation`. The policy returns
that evaluation inside `SessionTransitionResult`, together with the Evidence profile,
rule and requirement traceability, and input classifications. `evaluate_transition()` is
provided when a caller needs only the generic evaluation contract.

The policy accepts only `possible_session_start` and `possible_session_end` concerns.
Recording, transcript, schedule, media, visual, editorial, and package Evidence must pass
through the Session Boundary Evidence Builder first.

## Session lifecycle

The supported values are `inactive`, `active`, `ending`, and `ended`. A missing current
Session state is evaluated as effective `inactive`; no replacement state record is
created. Existing current state must use `SESSION_STATE`, a Session candidate or Session
product subject, and one of the four supported values.

Supported changes are:

- inactive to active
- active to ending or ended
- ending to ended
- ended to active when the start context is explicitly fresh

Qualifying Evidence for the current value produces `already_current`. Arbitrary changes
such as inactive to ended or ending to active are rejected. The policy proposes only an
`OperationalStateValue`; it never creates or mutates `OperationalState`.

## Categorical rules

Start-to-active requires both:

- one supporting session-specific Signal: speaker introduction, presentation transition,
  or session content
- one independently traceable corroborating media, continuity, schedule, or operator
  indication

Schedule, recording continuity, speech, presentation transition, and other single
Signals never establish active by themselves. Context alone is insufficient.

Active-to-ending accepts either one supporting session/transcript end Signal, or a
recording-end Signal plus independently traceable additional end context. Transition to
ended requires at least two independent end-oriented contributions, including at least
one supporting session-end or transcript-end Signal. Recording end, schedule change,
pause, or media finalization alone cannot establish ended.

When `active` Evidence satisfies both the explicit-ending rule and the stronger terminal
rule, the terminal rule is evaluated first and the policy deterministically proposes
`ended` directly. It does not select a lifecycle value by enum order.

Ended-to-active uses the start rule and additionally requires explicit freshness through
a different prior EvidenceSet basis, recording block, scheduled activity, boundary
context, or later organizational anchor. No Session identity or reset state is invented.

## Roles, independence, and context

Supporting items may satisfy requirements. Contextual items may corroborate only where a
requirement explicitly permits them. Neutral items do not satisfy requirements. Explicit
contradiction in the same compatible boundary context returns
`transition_not_supported` when it blocks otherwise relevant Evidence. Missing Signals
never become contradiction; missing Evidence is insufficient, not contradictory.

Independence uses distinct Observation IDs first. EvidenceItem IDs and EvidenceSet IDs
are the documented fallback hierarchy, although current `EvidenceItem` contracts always
provide an Observation ID. Repeated Signals tied to one Observation do not count as
independent corroboration.

Evidence is grouped by concern, correlation, recording block, stage, known scheduled
activity, and ED-0039 boundary context. Different EvidenceSets are combined only when
they explicitly share a boundary-context ID; otherwise each remains conservative and
separate. The policy adds no time threshold: ED-0039's five-minute window and boundary
anchor remain organizational metadata, not proof. Multiple incompatible qualifying
contexts return `insufficient_evidence` unless the caller supplies a target
`SessionBoundaryEvidenceContext`.

Evidence Strength is preserved in the profile but is not a gate, score, weight, or
confidence calculation.

## Architectural boundary

The policy evaluates only. It does not invoke builders, reinterpret Observations, inspect
transcript text, execute transitions, select final boundary timestamps, create Session
aggregates, mutate state, persist evaluations, rank candidates, calculate confidence,
create downstream reasoning artifacts or Operational Products, call AI, expose APIs, use
queues or workers, or add frontend behavior.
