# Observation Evidence Builder

ED-0031 adds the generic Observation Evidence Builder.

ED-0032 refines the builder so concern and role are first-class Evidence semantics rather than metadata-only conventions.

ED-0035 lets builder rules declare first-class Evidence Signals.

ED-0036 adds the first concrete Evidence Builder: Recording Coverage Evidence Builder.

The builder is the first Reasoning component after the Perception Layer.

Production Events become objective Observations through Observation Interpreters. The Observation Evidence Builder then organizes those objective Observations into explainable `EvidenceSet` objects using the existing ED-0007 Evidence contracts.

Observations describe facts.

Evidence organizes related facts.

Meaning comes later.

## Scope

The builder may:

- consume Observations
- group related Observations around one `EvidenceConcern`
- construct Evidence
- preserve Observation and Production Event traceability
- identify supporting, contradicting, contextual, neutral, and unknown Observation references
- identify the Evidence Signal contributed by a rule

The builder must not:

- generate Hypotheses
- generate Findings
- create Verification Decisions
- create Operational Products
- update Operational State
- assign semantic confidence
- conclude that a session, clip, package, speaker identity, production state, or other meaning is true

## Evidence Semantics

Each `EvidenceSet` built by this package is organized around exactly one `EvidenceConcern`.

Builder rules declare:

- one `EvidenceConcern`
- one `EvidencePurpose`
- one optional `EvidenceSignal`
- supporting Observation types
- contradicting Observation types
- contextual Observation types
- neutral Observation types

The builder writes concern to `EvidenceSet.concern`, role to `EvidenceItem.role`, and declared signals to `EvidenceSet.signals`.

Metadata remains available for secondary details, but core concern, role, and signal semantics are first-class.

Initial default rules remain deliberately conservative and map single-domain Observations into StageFlow-focused concerns such as recording coverage, media availability, schedule alignment, transcript continuity, and visual transition context.

Multi-domain concerns such as session started are intentionally excluded. Those belong to later reasoning directives.

## Concrete Builders

The Recording Coverage Evidence Builder converts objective recording activity Observations into recording-coverage Evidence and first-class recording Evidence Signals.

It is intentionally separate from the generic Observation Evidence Builder. It proves concrete signal production while staying below Operational State: it does not call transition policies, mutate state, infer sessions, persist Evidence, or create downstream reasoning artifacts.

## Traceability

The current Evidence contract stores Observation references through `EvidenceItem.observation_id` and `EvidenceObservationReference`.

When an Observation carries source Production Event IDs in metadata, that traceability is carried forward as observed traceability metadata.

This package does not redesign Observation-to-Production-Event traceability.
