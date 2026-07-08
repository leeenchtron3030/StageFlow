StageFlow Reasoning Model

Document: docs/05_Reasoning_Model.md
Architecture Release: AR-1.4
Status: Approved

⸻

Purpose

This document defines the complete reasoning architecture used by StageFlow.

The reasoning model describes how StageFlow progresses from raw production reality to explainable operational knowledge while preserving every stage of reasoning.

Its purpose is to ensure every operational decision can be understood, audited, and traced back to its supporting evidence.

⸻

Core Reasoning Model

Reality
↓
Timeline
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

Everything above Verification Decision contributes knowledge.

Everything below Verification Decision contributes operational outcomes.

No layer should assume the responsibility of another.

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