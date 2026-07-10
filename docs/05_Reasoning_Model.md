StageFlow Reasoning Model

Document: docs/05_Reasoning_Model.md
Architecture Release: AR-2.1
Status: Approved

⸻

Purpose

This document defines the complete reasoning architecture used by StageFlow.

The reasoning model describes how StageFlow progresses from raw production reality to explainable operational knowledge while preserving every stage of reasoning.

Its purpose is to ensure every operational decision can be understood, audited, and traced back to its supporting evidence.

AR-2.0 establishes StageFlow as an observational intelligence system for live event media.

StageFlow observes recorded reality, incorporates supporting production signals, reasons transparently, and produces explainable operational products.

AR-2.1 consolidates the Perception Layer.

Phenomena are observations. Meaning is reasoning.

## AR-2.0 Core Principles

1. Recorded media is StageFlow's primary source of observable reality.
2. Schedules express intent, not reality.
3. Production Events are the universal ingress language.
4. Meaning does not enter StageFlow directly; meaning emerges through reasoning.
5. Human operator input is valuable, but not privileged truth.
6. StageFlow observes production; it does not control production.
7. Operational Products must remain traceable to their reasoning chain.
8. Every runtime layer should stay small, boring, and explainable.

⸻

Core Ingress Model

Observable Reality
↓
Recording Adapter
Media Artifact Adapter
Schedule Source Adapter
Runtime Clock
Transcript Source Adapter
Vision Source Adapter
Operator Source Adapter
↓
Production Events
↓
Dispatcher
↓
Interpreters
↓
Observations

Adapters emit Production Events only.

Dispatchers route events only.

Interpreters translate Production Events into Observations only.

Observations begin the reasoning chain.

No adapter creates Evidence, Hypotheses, Findings, Verification Decisions, or Operational Products.

⸻

Perception Layer

The Perception Layer transforms Production Events into objective Observations.

Production Events
↓
Perception Layer
↓
Objective Observations
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

Observation Interpreters are the concrete units of the Perception Layer.

The completed first pass includes:

* Recording Activity Observation Interpreter
* Media Artifact Observation Interpreter
* Runtime Clock Observation Interpreter
* Schedule Source Observation Interpreter
* Transcript Source Observation Interpreter
* Vision Source Observation Interpreter

Each interpreter follows the same pattern:

Production Event
↓
Observation Interpreter
↓
Objective Observation

Perception is not reasoning.

Observation Interpreters observe signals, not semantics. They do not infer sessions, clips, package readiness, speaker identity, schedule compliance, visual meaning, transcript meaning, or production readiness.

Each interpreter translates only within its own domain. No interpreter correlates across domains yet.

Evidence is the first layer allowed to organize Observations toward interpretation. Meaning emerges after Observations, not inside them.

⸻

Complete Reasoning Chain

Production Event
↓
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

Production Events say something happened.

Observations say StageFlow noticed something objective.

Evidence organizes observations.

Hypotheses express possible meaning.

Findings are human-reviewable reasoning artifacts.

Verification Decisions preserve judgment history.

Operational Products are downstream outputs of verified reasoning.

Everything above Verification Decision contributes knowledge.

Everything below Verification Decision contributes operational outcomes.

No layer should assume the responsibility of another.

⸻

Observable Reality

Recorded media is StageFlow's primary source of observable reality.

Schedules, transcript availability, vision detections, operator input, runtime clock events, and media artifact reports enrich reasoning, but they do not replace recorded production reality.

Meaning does not enter StageFlow directly. Meaning emerges through reasoning.

⸻

Planned World vs Observed World

The planned world describes what should happen.

The observed world describes what appears to have happened.

StageFlow never mistakes intention for reality.

Schedule data enriches reasoning but does not prove production reality.

Schedules express intent. Recorded production expresses reality. StageFlow reasons about the difference.

⸻

Human Input

Human input enters through Operator Source Adapters.

Operator input becomes Production Events.

Human input is valuable but does not bypass reasoning.

A human marker, note, or flag is still evidence to be interpreted, not automatic truth.

Human input is another source of observable information, not privileged truth.

⸻

Runtime Philosophy

StageFlow is not show control.

StageFlow does not initiate production.

StageFlow does not replace producers.

StageFlow observes, reasons, explains, and prepares operational outputs.

Runtime components should remain simple and in-memory unless future directives explicitly require persistence or infrastructure.

StageFlow should have a rich domain model riding atop an intentionally boring runtime.

⸻

# Timeline

Timeline objects describe where something exists within recorded production media.

Timeline produces candidate ranges without assigning operational meaning.

These candidate ranges may later contribute to Findings and, after verification, become Operational Products.

Timeline answers:

- Where did this occur?
- When did this occur?

Timeline does not determine what the range ultimately represents.

⸻

Observation

Observations record things that were noticed.

Examples include:

* title graphic detected
* applause detected
* speech detected
* schedule boundary reached
* operator marker added

Observations are objective statements.

They are not conclusions.

ObservationLocation is the location authority for Observations.

Supported anchors include timeline position, timeline range, recording block, wall clock, stage, composite context, and explicit unknown location.

Media timeline is one possible anchor, not the only anchor. Fake timeline offsets should never be introduced. Location describes where or when an Observation is anchored, not what the Observation means.

Observations currently preserve source Production Event traceability through metadata. This is acceptable for now, but future architecture should make traceability a first-class Observation contract.

Transcript text, visual metadata, and operator notes currently live in metadata when carried forward. A future directive should consider a first-class ObservationPayload model without allowing Observations to become interpretations.

⸻

Evidence

Evidence organizes observations into meaningful support for possible interpretations.

Evidence may:

* support
* contradict
* contextualize

a future interpretation.

Evidence does not determine truth.

⸻

Hypothesis

A Hypothesis represents a possible interpretation supported by evidence.

Example:

A session may begin near this point.

Hypotheses remain tentative.

They are not actions.

They are not operational products.

⸻

Finding

A Finding is the first human-reviewable reasoning artifact.

A Finding represents something StageFlow believes deserves attention.

Examples include:

* possible session boundary
* editorial moment
* technical incident
* schedule conflict
* metadata event
* alert condition

A Finding is explainable and must remain traceable to the hypotheses, evidence, and observations that support it.

⸻

Verification Decision

Verification records judgment about Findings.

Verification Decisions:

* are append-only
* never modify Findings
* preserve reviewer history
* allow disagreement
* allow refinement over time

Examples of Verification Decisions include:

* accept
* reject
* adjust
* merge
* split
* defer
* escalate
* annotate

Verification records human or approved-system judgment.

It does not create operational products.

⸻

Operational Products

Operational Products are created only after verified reasoning.

Examples include:

* Session Window
* Editorial Moment
* Technical Incident
* Alert
* Metadata Record
* Package Task

Operational Products are the outputs consumed by production workflows.

They are not reasoning artifacts.

⸻

Design Principles

The StageFlow reasoning architecture follows these principles:

* Observations are not conclusions.
* Evidence organizes observations.
* Hypotheses express possible meaning.
* Findings are the first human-reviewable reasoning artifacts.
* Verification preserves reasoning history.
* Operational Products are downstream outcomes of verified reasoning.
* No layer bypasses another.

⸻

Explainability

Every operational product should be explainable through its reasoning chain.

Example:

Operational Product
↑
Verification Decision
↑
Finding
↑
Hypothesis
↑
Evidence
↑
Observation
↑
Timeline

This allows reviewers to understand not only what StageFlow produced, but why it produced it.

⸻

External Systems

External systems contribute information.

They do not produce Findings directly.

For example:

Pretalx Schedule
↓
Production Event
↓
Observation
↓
Evidence
↓
Hypothesis
↓
Finding

Likewise:

Transcript Engine
↓
Production Event
↓
Observation
↓
Evidence
↓
Hypothesis
↓
Finding

This keeps StageFlow’s reasoning independent of any specific technology or vendor.

⸻

Future Operational Products

The reasoning architecture is intentionally generic.

Future operational products may include:

* Session Windows
* Editorial Moments
* Alerts
* Technical Incidents
* Accessibility Cues
* Metadata Records
* Publishing Tasks
* Additional workflow products not yet defined

The reasoning model should remain unchanged as new operational products are introduced.

⸻

Revision History

AR-1.3

Initial reasoning model introduced.

AR-1.4

Reasoning architecture completed with Verification Decision and Operational Product layers.

AR-2.0

Observational Intelligence Architecture established. Production Events are now documented as the universal ingress language before Observations, and the complete ingress and reasoning chains are explicit.

AR-2.1

Perception Layer consolidated. Production Events now flow through Observation Interpreters into Objective Observations before Evidence or reasoning layers organize meaning.
