# Engineering Directives

## Purpose

Engineering Directives are the implementation authority for StageFlow. Each directive must be scoped, reviewed against the architecture, and implemented without expanding beyond its approved boundary.

## Directive Index

| ED | Title | Status | Description |
| --- | --- | --- | --- |
| ED-0001 | Repository Governance & Skeleton | Approved / Implemented | Establishes repository-level governance files and skeleton directories without application code. |
| ED-0002 | Backend Foundation | Approved / Implemented | Establishes the Python FastAPI backend foundation, package boundaries, health endpoint, and baseline quality tooling without domain behavior. |
| ED-0003 | Frontend Foundation | Approved / Implemented | Establishes the Next.js frontend foundation, workflow-oriented package boundaries, design tokens, theme foundation, and minimal application shell without backend communication or business logic. |
| ED-0004 | Shared Contracts Foundation | Approved / Implemented | Establishes generic backend and frontend shared contracts for identifiers, correlation, results, errors, time, clocks, time ranges, and base domain events without business behavior. |
| ED-0005 | Production Timeline Foundation | Approved / Implemented | Establishes backend-only Production Context timeline contracts for recording blocks, timeline positions and ranges, schedule references, and session windows without ingestion, persistence, APIs, or media file logic. |
| ED-0006 | Production Observation Foundation | Approved / Implemented | Establishes backend-only Production Context observation contracts for generic timestamped observations on recording timelines without reasoning, detection, persistence, APIs, or provider-specific behavior. |
| ED-0007 | Production Evidence Foundation | Approved / Implemented | Establishes backend-only Production Context evidence contracts for grouping observation references as support without reasoning, proposals, scoring policy, persistence, APIs, or provider-specific behavior. |
| ED-0008 | Production Hypothesis Foundation | Approved / Implemented | Establishes backend-only Production Context hypothesis contracts for possible interpretations of evidence without proposals, verification, session-window generation, persistence, APIs, or provider-specific behavior. |
| ED-0009 | Production Finding Foundation | Approved / Implemented | Establishes backend-only Production Context finding contracts as the first human-reviewable reasoning artifacts without verification workflows, operational products, persistence, APIs, or frontend behavior. |
| ED-0010 | Verification Protocol Foundation | Approved / Implemented | Establishes backend-only Production Context append-only verification decision contracts for judgments about findings without workflows, operational products, persistence, APIs, or frontend behavior. |
| ED-0011 | Operational Product Foundation | Approved / Implemented | Establishes backend-only Production Context operational product contracts as the generic execution-layer boundary without specialized product implementations, persistence, APIs, queues, workers, or frontend behavior. |
| ED-0012 | Session Window Product Foundation | Approved / Implemented | Establishes backend-only Production Context session window product contracts as the first specialized operational product without Session aggregates, persistence, APIs, media storage, package generation, integrations, or frontend behavior. |
| ED-0013 | Production Event Foundation | Approved / Implemented | Establishes backend-only Production Context production event contracts as the provider-agnostic runtime boundary before Observations without adapters, ingestion, persistence, APIs, queues, workers, or frontend behavior. |
| ED-0014 | Production Event Interpreter Foundation | Approved / Implemented | Establishes backend-only Production Context interpreter contracts for translating Production Events into Observations without adapters, reasoning, persistence, APIs, queues, workers, or frontend behavior. |
| ED-0015 | Production Event Dispatcher Foundation | Approved / Implemented | Establishes backend-only Production Context dispatcher contracts for routing Production Events to matching interpreters without interpretation, reasoning, infrastructure, persistence, APIs, adapters, or frontend behavior. |
| ED-0016 | Recording System Adapter Contract | Approved / Implemented | Establishes backend-only Production Context recording system adapter contracts that emit generic Production Events without provider-specific integrations, media ingestion, persistence, APIs, queues, workers, or frontend behavior. |
| ED-0017 | Media Artifact Adapter Contract | Approved / Implemented | Establishes backend-only Production Context media artifact adapter contracts that emit generic Production Events without filesystem watching, ingestion, validation, chunk registration, provider-specific integrations, APIs, persistence, queues, workers, or frontend behavior. |
| ED-0018 | Schedule Source Adapter Contract | Approved / Implemented | Establishes backend-only Production Context schedule source adapter contracts for planned activities that emit generic Production Events without provider-specific integrations, Sessions, Observations, reasoning, APIs, persistence, queues, workers, or frontend behavior. |
| ED-0019 | Runtime Clock Contract | Approved / Implemented | Establishes backend-only Production Context runtime clock contracts that emit generic Production Events for crossed time boundaries without scheduling infrastructure, retries, reconciliation, APIs, persistence, queues, workers, or frontend behavior. |
| ED-0020 | Transcript Source Adapter Contract | Approved / Implemented | Establishes backend-only Production Context transcript source adapter contracts that emit generic Production Events without transcription execution, audio processing, model calls, Observations, reasoning, APIs, persistence, queues, workers, or frontend behavior. |

## Process

- A directive must name its scope, dependencies, owner, acceptance criteria, and out-of-scope items.
- Implementation must preserve existing architecture documents.
- If a directive requires work outside its approved scope, implementation must stop and report the dependency.
