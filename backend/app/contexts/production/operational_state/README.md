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

`OperationalStateBasis` references Observation IDs and EvidenceSet IDs only.

It does not embed Observations or EvidenceSets.

The current traceability chain is:

Operational State
↓
Observation ID or EvidenceSet ID
↓
Observation or Evidence metadata
↓
Production Event ID

## Deferred

ED-0033 does not define transition graphs, transition thresholds, transition policy, state machines, automatic supersession, repositories, persistence, APIs, queues, workers, AI, or frontend behavior.
