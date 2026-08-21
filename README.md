# StageFlow

An observational intelligence system for live event media.

**Start here:** [StageFlow Master Project Brief](docs/PROJECT_BRIEF.md)

⸻

Overview

StageFlow is an observational intelligence system for live event media.

It observes recorded reality, incorporates supporting production signals, reasons transparently, and produces explainable operational products for conference media teams.

Rather than treating content creation as post-production, StageFlow moves observation, reasoning, review, rendering, and package assembly closer to live production while preserving human editorial authority.

Architecture summary:

Observable Reality -> Production Events -> Observations -> Reasoning -> Operational Products

Perception Layer summary:

Production Events -> Observation Interpreters -> Objective Observations

⸻

Mission

Reduce the time between a speaker presenting an idea and that idea becoming professionally reviewed, approved, packaged, and delivered.

⸻

Philosophy

StageFlow is built around several core ideas:

* Live First. Package Second.
* Sessions, Not Files.
* AI Assists. Humans Publish.
* Continuous Editorial Pipeline.
* Human Editorial Authority.
* Reliability Over Complexity.
* Offline-First Event Operations.

These principles are formally defined in PRODUCT_CONSTITUTION.md.

⸻

Primary Goals

* Near real-time content production
* Human-centered editorial workflows
* Conference-scale reliability
* Rapid speaker package delivery
* White-label deployment across multiple events
* Long-term maintainability

⸻

What StageFlow Is Not

StageFlow is not intended to replace traditional nonlinear editing software.

It is not designed to autonomously publish content without human approval.

It is not a cloud-only platform.

Instead, it is an operational system that assists production teams in creating and managing conference media at unprecedented speed.

⸻

Repository Structure

```text
PRODUCT_CONSTITUTION.md
README.md
CHANGELOG.md
ROADMAP.md
backend/        Python/FastAPI application, migrations, qualification tools, and tests
frontend/       Next.js producer and Demo user interfaces
docs/           Architecture, ADRs, reviews, plans, and validation evidence
scripts/        Preview, Demo, and validation launchers
```

⸻

Specifications

The documentation in this repository forms the canonical definition of StageFlow.

Implementation follows the specifications.

The specifications do not evolve to justify implementation decisions.

Start with the current [architecture documentation index](docs/architecture/README.md),
which distinguishes implemented behavior, accepted architecture, future direction, and
open decisions while preserving the historical specifications below.

The historical specification roadmap includes the following document categories. Not all
categories are present or implemented at the current repository baseline; use the
architecture index and Engineering Directive index to determine current authority and
scope.

* Product Manifesto
* System Architecture
* Engineering Blueprint
* Functional Specification
* Database Schema
* API Specification
* Worker Architecture
* UI Wireframes
* Deployment Guide
* Simulation Mode
* Testing Strategy
* Product Roadmap

⸻

Repository Philosophy

This repository is specification-driven.

Every implementation should trace back to an approved specification.

Every significant architectural decision should be documented.

Every specification should reference the Product Constitution.

⸻

Development Workflow

All new functionality follows the same lifecycle:

Vision
↓
Specification
↓
Architecture Review
↓
Approval
↓
Implementation
↓
Validation
↓
Deployment

⸻

Design Principles

StageFlow prioritizes:

* operational reliability
* maintainability
* clarity
* scalability
* simplicity under pressure

The platform is designed for real production environments where failure recovery and operational speed are more valuable than feature quantity.

⸻

Engineering Principles

The codebase should remain:

* modular
* readable
* testable
* event-driven
* specification-driven

Whenever possible:

* business logic should remain independent of user interface
* services should own their own responsibilities
* asynchronous processing should be preferred for long-running work

⸻

Documentation Standards

Every specification document should include:

* Purpose
* Scope
* Dependencies
* Design Principles
* Design Decisions
* Revision History

Specifications should describe why a system behaves a certain way in addition to how it behaves.

⸻

Architecture Decision Records

Major architectural decisions are documented separately as Architecture Decision Records (ADRs).

ADRs explain why important decisions were made and preserve architectural reasoning for future contributors.

⸻

Contributing

Before implementing new functionality:

1. Review the Product Constitution.
2. Review the relevant specification.
3. Confirm the proposed change does not conflict with higher-level specifications.
4. Document any architectural decisions.
5. Implement.
6. Test.
7. Update specifications if behavior intentionally changes.

⸻

Long-Term Vision

StageFlow is intended to become the observational intelligence backbone of conference media production.

The long-term objective is not simply to create clips more quickly, but to redefine how live events approach content creation by moving editorial work into the live production process itself.

⸻

Current Status

Current repository phase: Architecture Release AR-2.1

The repository now includes a FastAPI application with a durable PostgreSQL Event-Mode
Kernel, deterministic Production-domain contracts and policies, bounded local media
discovery, durable advisory Media Timing Evidence, a durable transcription-worker
substrate, and a Demo single-stage application flow. The Next.js frontend includes
producer-facing and Demo workflows backed by fixture or Kernel data.

This is an operational foundation, not an event-readiness claim. Demo hardware rehearsal,
real deployment qualification, and broader workflow composition remain active work; a
passing local or CI contract suite does not establish production-event readiness.

⸻

License

StageFlow is licensed under the [MIT License](LICENSE).

⸻

Acknowledgements

StageFlow is being developed through an iterative architecture-first process emphasizing production experience, editorial workflows, and long-term software maintainability.
