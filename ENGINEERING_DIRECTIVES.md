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

## Process

- A directive must name its scope, dependencies, owner, acceptance criteria, and out-of-scope items.
- Implementation must preserve existing architecture documents.
- If a directive requires work outside its approved scope, implementation must stop and report the dependency.
