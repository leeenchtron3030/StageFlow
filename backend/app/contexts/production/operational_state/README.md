# Operational State

ED-0033 adds the foundational Operational State taxonomy for StageFlow.

Operational State is perspective-dependent. StageFlow models only state required for its mission:

The fastest, most reliable observer of recorded event media for editorial and session production.

Operational State describes StageFlow-relevant understanding. It does not execute behavior, transition itself, update repositories, create Hypotheses, create Findings, create Verification Decisions, create Operational Products, or implement workflow.

## State Families

Operational State has four explicit families:

- Directly observable state: narrow state established from objective Observations in one domain.
- Evidence-derived state: state later justified by structured Evidence.
- StageFlow readiness: whether StageFlow is prepared to observe or reason for its own responsibilities.
- Environmental context: useful surrounding conditions that are not core StageFlow state.

Directly observable state is distinct from evidence-derived state. Recording active and transcript flowing may be directly observable. Session active and editorial moment candidate active are evidence-derived.

StageFlow readiness is distinct from human production readiness. StageFlow may be ready to observe recorded media or evaluate a session boundary; it does not model whether a speaker, stage manager, lighting operator, camera operator, audience, or production team is ready.

Environmental context remains separate from core StageFlow state. Livestream health, lighting health, camera battery, venue network condition, audio-console status, and RF system health may be contextual if they affect StageFlow responsibilities, but they are not automatically first-class core state.

## Traceability

`OperationalStateBasis` references Observation IDs, EvidenceSet IDs, accepted
Transition Evaluation IDs, policy IDs, and transition rule IDs only. ED-0044 adds the
evaluation, policy, and rule references compatibly; existing construction remains
valid because the new collections default to empty.

It does not embed Observations, EvidenceSets, evaluations, policies, or rules.

The acceptance-grade traceability chain is:

Operational State
↓
Transition Evaluation, policy, rule, Observation, or EvidenceSet ID
↓
Acceptance lineage and Observation or Evidence traceability
↓
Production Event ID

## Acceptance boundary

ED-0044 permits the separate Operational State Acceptance layer to create one immutable
successor record after independently validating one supported evaluation. Recording
state is mapped to directly observable state; Session state is mapped to
Evidence-derived state. The predecessor is not mutated. Intended supersession is
described in a separate immutable contract rather than applied.

The successor state timestamp is the evaluation timestamp. Acceptance time and
organizational boundary anchors remain separate and no boundary is thereby verified.

## Still deferred

The taxonomy itself does not transition state. ED-0044 adds only static Recording and
Session acceptance graphs outside this package. Automatic supersession, repositories,
persistence, execution, state machines, APIs, queues, workers, AI, and frontend
behavior remain deferred.
