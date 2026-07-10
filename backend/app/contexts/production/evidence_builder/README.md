# Observation Evidence Builder

ED-0031 adds the generic Observation Evidence Builder.

The builder is the first Reasoning component after the Perception Layer.

Production Events become objective Observations through Observation Interpreters. The Observation Evidence Builder then organizes those objective Observations into explainable `EvidenceSet` objects using the existing ED-0007 Evidence contracts.

Observations describe facts.

Evidence organizes related facts.

Meaning comes later.

## Scope

The builder may:

- consume Observations
- group related Observations around one operational concern
- construct Evidence
- preserve Observation and Production Event traceability
- identify supporting, contradicting, and contextual Observation references

The builder must not:

- generate Hypotheses
- generate Findings
- create Verification Decisions
- create Operational Products
- update Operational State
- assign semantic confidence
- conclude that a session, clip, package, speaker identity, production state, or other meaning is true

## Operational Concerns

Each `EvidenceSet` built by this package is organized around exactly one operational concern.

Initial default concerns are deliberately single-domain:

- recording activity
- media artifact availability
- time boundary
- scheduled activity
- transcript activity
- vision activity

Multi-domain concerns such as session started are intentionally excluded. Those belong to later reasoning directives.

## Traceability

The current Evidence contract stores Observation references through `EvidenceItem.observation_id`.

ED-0031 also preserves supporting, contradicting, and contextual Observation IDs in Evidence metadata. When an Observation carries source Production Event IDs in metadata, that traceability is carried forward as observed traceability metadata.

This package does not redesign Observation traceability.
