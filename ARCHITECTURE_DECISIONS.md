# Architecture Decisions

## Purpose

This document records approved Architecture Decision Records for StageFlow. ADRs in this file describe foundational choices that implementation must respect.

## ADR-0001 StageFlow Is Implemented as a Modular Monolith

StageFlow is implemented as a modular monolith. Internal boundaries should follow the approved architecture layers and bounded contexts before any distributed-service boundary is introduced.

## ADR-0002 Sessions Are the Primary Production Aggregate

Sessions are the primary production aggregate. Implementation work must treat session-centered production coordination as a core architectural organizing principle.

## ADR-0003 Media Chunks Are Storage Artifacts, Not Editorial Objects

Media Chunks are storage artifacts. They must not be promoted into editorial domain objects unless a future approved architecture decision changes that boundary.

## ADR-0004 StageFlow Owns Workflow, Not Conference Data

StageFlow owns production workflow. It must not become the source of truth for conference data that belongs to external systems or upstream conference management processes.

## ADR-0005 External Integrations Use Adapters Within the Integration Context

External integrations use adapters within the Integration Context. Integration-specific concerns should remain behind adapter boundaries rather than leaking into core domain workflows.

## Reserved

ADR-0006 through ADR-0008 are intentionally reserved for future architectural decisions.

Architecture Decision Records are never renumbered after publication.

## ADR-0009 — Verification Preserves Reasoning History

Verification does not modify Findings.

Instead, Verification records immutable Verification Decisions.

Multiple Verification Decisions may exist for the same Finding.

Verification history is append-only.

Operational Products are created from verified reasoning rather than replacing reasoning artifacts.

This preserves:

- explainability
- auditability
- reviewer history
- disagreement
- future reinterpretation

The reasoning chain therefore becomes:

Observation
↓
Evidence
↓
Hypothesis
↓
Finding
↓
Verification Decision
↓
Operational Product

## ADR-0010 — Timeline Candidates Are Not Operational Products

Early versions of StageFlow used the term Session Window for timeline-level candidate ranges.

As the reasoning architecture matured, it became clear that this object belongs to the timeline reasoning layer rather than the execution layer.

The timeline layer proposes possible media ranges.

Operational Products represent verified work products.

Therefore:

TimelineWindowCandidate

and

SessionWindowProduct

represent different concepts.

TimelineWindowCandidate exists before verification.

SessionWindowProduct exists after verification.

The distinction preserves a clean separation between reasoning and execution.

## ADR-0011 — Production Events Are The Universal Ingress Language

Every source of observable reality enters StageFlow as a Production Event before it can become an Observation.

Recording systems, media artifact sources, schedule sources, runtime clocks, transcript sources, vision sources, and operator sources all emit Production Events through adapter contracts.

Adapters do not create Observations, Evidence, Hypotheses, Findings, Verification Decisions, or Operational Products.

This keeps ingress small, generic, and explainable.

## ADR-0012 — Recorded Media Anchors Observable Reality

Recorded media is the primary reference for what actually happened.

Schedules, transcripts, vision detections, operator input, clock events, and other production signals enrich and contextualize recorded media, but they do not replace it.

Reasoning may use those signals to explain production reality, but recorded production remains the anchor for observable reality.

## ADR-0013 — Planned Reality And Observed Reality Remain Separate

Schedules describe intent.

Observations describe perceived reality.

StageFlow must never treat planned intent as proof that production activity occurred.

Reasoning reconciles planned intent with observed media and supporting production signals.

## ADR-0014 — Runtime Component Status Should Be Shared

Adapter and runtime component status concepts have repeated across multiple Engineering Directives.

Separate status enums were acceptable while the ingress architecture was still forming, but the repetition now indicates a stable shared concept.

A future directive should introduce a shared runtime component status contract rather than continuing separate status enums indefinitely.

## ADR-0015 — Observation Interpreters Produce Objective Observations

Observation Interpreters translate Production Events into Observations.

They do not create Evidence, Hypotheses, Findings, Verification Decisions, or Operational Products.

They observe signals, not semantics.

Phenomena are observations. Meaning is reasoning.

## ADR-0016 — ObservationLocation Is The Location Authority

Observation location is not limited to media timeline.

An Observation may be anchored to a timeline position, timeline range, recording block, wall-clock timestamp, stage, composite context, or explicit unknown location.

Fake timeline offsets must not be introduced when a more truthful non-timeline anchor exists.

Location describes where or when an Observation is anchored, not what the Observation means.

## ADR-0017 — Observation Traceability Should Become First-Class

Observations currently preserve source Production Event traceability through metadata.

This compromise is acceptable while the Perception Layer contracts settle.

Future architecture should promote source Production Event references to first-class Observation fields so traceability is explicit and consistently validated.

## ADR-0018 — Observation Payloads May Need First-Class Modeling

Transcript text, visual metadata, and operator notes currently live in Observation metadata when carried forward.

This keeps the current Observation contracts small, but repeated payload patterns indicate a stable concept.

Future architecture may introduce an ObservationPayload model for source-specific observed data without allowing interpreters to infer meaning.
