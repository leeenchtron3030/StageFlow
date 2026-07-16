# Observation Evidence Builder

ED-0031 adds the generic Observation Evidence Builder.

ED-0032 refines the builder so concern and role are first-class Evidence semantics rather than metadata-only conventions.

ED-0035 lets builder rules declare first-class Evidence Signals.

ED-0036 adds the first concrete Evidence Builder: Recording Coverage Evidence Builder.

ED-0037 adds the second concrete Evidence Builder: Transcript Continuity Evidence Builder.

ED-0038 extracts generic semantic-selection mechanics proven by the two concrete builders.

ED-0039 adds the first cross-domain Evidence Builder: Session Boundary Evidence Builder.

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

Conclusive multi-domain concerns such as session started remain excluded. ED-0039 may
compose existing domain Evidence only into the non-conclusive concerns
`possible_session_start` and `possible_session_end`.

## Concrete Builders

The Recording Coverage Evidence Builder converts objective recording activity Observations into recording-coverage Evidence and first-class recording Evidence Signals.

It is intentionally separate from the generic Observation Evidence Builder. It proves concrete signal production while staying below Operational State: it does not call transition policies, mutate state, infer sessions, persist Evidence, or create downstream reasoning artifacts.

The Transcript Continuity Evidence Builder converts objective transcript activity Observations into transcript continuity Evidence and first-class transcript Evidence Signals. It handles accumulating transcript streams, distinguishes availability from continuity, and requires explicit interruption or ending Observations before producing interruption or ending Signals.

Both concrete builders suggest a reusable semantic-selector shape may be useful later, but ED-0037 keeps the logic domain-specific until another directive formalizes that abstraction.

The Session Boundary Evidence Builder consumes the outputs of domain builders rather
than Observations. It maps source Concern plus Signal to boundary Concern and Role,
preserves ID-only lineage and source strength, and groups compatible contributions by
recording block, stage, known scheduled activity, correlation, and a bounded temporal
neighborhood. It does not invoke domain builders or transition policy. Its temporal
window and earliest-start/latest-end anchors organize Evidence only and do not prove or
select a boundary.

## Semantic Selection Mechanics

ED-0038 adds shared mechanics for concrete Evidence Builders:

- structured semantic selection from explicitly configured Observation metadata keys
- deterministic normalization of structured values
- deterministic Observation ordering
- duplicate Observation ID handling
- generic recognized, ignored, unsupported, and duplicate reporting
- context-key comparison for domain-provided grouping keys

The generic foundation owns mechanics only. It does not decide Evidence Concern, Evidence Purpose, Evidence Role, Evidence Strength, Signal mappings, grouping meaning, or rationale language.

Semantic selectors do not inspect free-form transcript text, infer missing semantics, infer transcript interruption from silence, or map values to Signals. Concrete builders continue to own operational meaning.

ED-0038 is not a runtime-configurable rules engine. There are no external rule files, expression languages, plugins, repositories, APIs, queues, workers, or frontend behavior.

## Traceability

The current Evidence contract stores Observation references through `EvidenceItem.observation_id` and `EvidenceObservationReference`.

When an Observation carries source Production Event IDs in metadata, that traceability is carried forward as observed traceability metadata.

This package does not redesign Observation-to-Production-Event traceability.
