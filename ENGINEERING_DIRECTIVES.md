# Engineering Directives

## Purpose

Engineering Directives are the implementation authority for StageFlow. Each directive must be scoped, reviewed against the architecture, and implemented without expanding beyond its approved boundary.

## Directive Index

| ED | Title | Status | Description |
| --- | --- | --- | --- |
| ED-0001 | Repository Governance & Skeleton | Approved / Implemented | Establishes repository-level governance files and skeleton directories without application code. |
| ED-0002 | Backend Foundation | Approved / Implemented | Establishes the Python FastAPI backend foundation, package boundaries, health endpoint, and baseline quality tooling without domain behavior. |
| ED-0003 | Frontend Foundation | Reserved | Reserved for future frontend foundation work. |
| ED-0004 | Development Tooling | Reserved | Reserved for future development tooling work. |
| ED-0005 | Production Context Foundation | Reserved | Reserved for future Production Context foundation work. |

## Process

- A directive must name its scope, dependencies, owner, acceptance criteria, and out-of-scope items.
- Implementation must preserve existing architecture documents.
- If a directive requires work outside its approved scope, implementation must stop and report the dependency.
