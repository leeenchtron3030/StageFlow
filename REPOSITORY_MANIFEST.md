# Repository Manifest

## Purpose

This manifest documents the StageFlow repository structure, repository-level files, and ownership by Engineering Directive.

## Architecture Releases

### AR-1.4 — Complete Reasoning Architecture

This Architecture Release completes the StageFlow reasoning architecture.

It formally establishes:

- Timeline
- Observation
- Evidence
- Hypothesis
- Finding
- Verification Decision

Operational Products are defined as downstream outputs of verified reasoning.

ED-0012 adds the first specialized Operational Product: the Session Window Product.

Subsequent Engineering Directives build on this completed reasoning model and specialized product foundation rather than extending the reasoning layer.

## Architecture Release AR-1.5

Clarifies terminology between reasoning-layer timeline artifacts and execution-layer operational products.

Introduces the concept:

Timeline Window Candidate

Clarifies that:

Session Window Product

is a specialized Operational Product produced after verification.

ED-0013 adds Production Events as the provider-agnostic runtime boundary before Observations.

ED-0014 adds Production Event Interpreters as the translation boundary from Production Events into Observations without extending into reasoning.

ED-0015 adds Production Event Dispatchers as the in-memory routing boundary from Production Events to matching Interpreters.

ED-0016 adds Recording System Adapter contracts as the first adapter-facing boundary that emits generic Production Events.

ED-0017 adds Media Artifact Adapter contracts for reporting artifact availability separately from recording activity and media ingestion.

ED-0018 adds Schedule Source Adapter contracts for planned activities, preserving separation between planned reality and observed reality.

ED-0019 adds Runtime Clock contracts as a time-boundary ingress source that emits generic Production Events without scheduling work.

ED-0020 adds Transcript Source Adapter contracts for transcript availability reporting, preserving the separation between words becoming available and later text meaning.

ED-0021 adds Vision Source Adapter contracts for visual detection reporting, preserving the separation between visual phenomena becoming available and later semantic meaning.

ED-0022 adds Operator Source Adapter contracts for intentional human input, preserving that human-supplied information enters the same reasoning pipeline as every other source.

ED-0023 adds explicit Observation Interpreter contracts for translating one or more Production Events into objective Observations without creating later reasoning artifacts.

ED-0024 adds the first concrete Observation Interpreter by translating recording activity Production Events into objective recording activity Observations.

ED-0025 refines Observation locations so Observations can be explicitly anchored to timeline positions, timeline ranges, recording blocks, wall-clock timestamps, stages, composite context, or unknown location.

ED-0026 adds the Media Artifact Observation Interpreter for objective artifact availability and lifecycle observations.

ED-0027 adds the Runtime Clock Observation Interpreter for objective time-boundary observations.

ED-0028 adds the Schedule Observation Interpreter for objective planned-reality observations without production inference.

ED-0029 adds the Transcript Observation Interpreter for objective transcript availability observations without language understanding.

ED-0030 adds the Vision Observation Interpreter for objective visual-phenomena observations without visual meaning interpretation.

## Architecture Release AR-2.0

AR-2.0 formalizes StageFlow as an observational intelligence system for live event media.

It documents the complete ingress architecture:

Observable Reality -> Production Events -> Dispatcher -> Interpreters -> Observations

It establishes Production Events as the universal ingress language across recording, media artifact, schedule, runtime clock, transcript, vision, and operator sources.

It also marks the transition from foundational architecture to observational intelligence: StageFlow observes recorded reality, incorporates supporting production signals, reasons transparently, and produces explainable operational products.

## Architecture Release AR-2.1

AR-2.1 consolidates the Perception Layer.

It documents the concrete Observation Interpreters completed through ED-0030:

- Recording Activity Observation Interpreter
- Media Artifact Observation Interpreter
- Runtime Clock Observation Interpreter
- Schedule Source Observation Interpreter
- Transcript Source Observation Interpreter
- Vision Source Observation Interpreter

The Perception Layer transforms Production Events into objective Observations. It does not create Evidence, Hypotheses, Findings, Verification Decisions, or Operational Products.

AR-2.1 also captures future refinement targets: first-class Observation traceability, first-class Observation payloads, a shared `RuntimeComponentStatus` contract, and source/context vocabulary for broad Production Event types such as `system_status_changed`.

## Architecture Release AR-3.0 Review Checkpoint

ED-0041 reviews the complete implemented backend reasoning path through ED-0040 before
Operational State Acceptance. The review records evidence-backed findings, metadata and
compatibility classifications, representative flow traces, state-acceptance readiness,
and a prioritized directive roadmap. It does not implement state acceptance or change
runtime policy behavior.

## Directories

| Path | Purpose | Owning Engineering Directive | Notes |
| --- | --- | --- | --- |
| `.` | Repository root for StageFlow governance, specifications, and future implementation. | ED-0001 | Contains root-level project and governance documents. |
| `.github/` | GitHub repository governance and future automation metadata. | ED-0001 | Workflows are reserved for future directives. |
| `.github/workflows/` | Reserved location for GitHub Actions workflows. | ED-0001 | No workflows are created by ED-0001. |
| `architecture/` | Implementation-facing architecture support material. | ED-0001 | Complements, but does not replace, canonical architecture docs. |
| `assets/` | Versioned static assets for documentation, examples, or future product surfaces. | ED-0001 | Runtime media remains excluded by `.gitignore`. |
| `backend/` | Python FastAPI backend workspace. | ED-0002 | Managed with `uv`; contains no StageFlow business logic in ED-0002. |
| `backend/app/` | Backend application package root. | ED-0002 | Contains API, context, shared, core, and bootstrap packages. |
| `backend/app/api/` | HTTP interface layer. | ED-0002 | Exposes only the versioned health endpoint in ED-0002. |
| `backend/app/api/v1/` | Version 1 API routes. | ED-0002 | Contains `GET /api/v1/health`. |
| `backend/app/bootstrap/` | Reserved backend composition package. | ED-0002 | No bootstrap behavior beyond app creation in ED-0002. |
| `backend/app/contexts/` | StageFlow bounded context package root. | ED-0002 | Context package boundaries only; no domain behavior. |
| `backend/app/contexts/editorial/` | Editorial context package boundary. | ED-0002 | Empty package boundary. |
| `backend/app/contexts/events/` | Event Management context package boundary. | ED-0002 | Empty package boundary. |
| `backend/app/contexts/identity/` | Identity & Access context package boundary. | ED-0002 | Empty package boundary. |
| `backend/app/contexts/integration/` | Integration context package boundary. | ED-0002 | Empty package boundary. |
| `backend/app/contexts/packaging/` | Packaging & Delivery context package boundary. | ED-0002 | Empty package boundary. |
| `backend/app/contexts/production/` | Production context package. | ED-0002 / ED-0005 / ED-0012 / ED-0013 / ED-0014 / ED-0015 / ED-0016 / ED-0017 / ED-0018 / ED-0019 / ED-0020 / ED-0021 / ED-0022 / ED-0023 / ED-0024 / ED-0025 / ED-0026 / ED-0027 / ED-0028 / ED-0029 / ED-0030 / ED-0031 / ED-0032 / ED-0033 / ED-0034 / ED-0035 / ED-0036 / ED-0037 / ED-0038 / ED-0039 / ED-0040 | ED-0005 adds production timeline contracts; ED-0012 adds the first specialized operational product; ED-0013 adds runtime input events; ED-0014 adds event interpreter contracts; ED-0015 adds event dispatcher contracts; ED-0016 adds recording adapter contracts; ED-0017 adds media artifact adapter contracts; ED-0018 adds schedule adapter contracts; ED-0019 adds runtime clock contracts; ED-0020 adds transcript adapter contracts; ED-0021 adds vision adapter contracts; ED-0022 adds operator adapter contracts; ED-0023 adds observation interpreter contracts; ED-0024 adds the first concrete recording activity observation interpreter; ED-0025 refines Observation location anchors; ED-0026 adds the media artifact observation interpreter; ED-0027 adds the runtime clock observation interpreter; ED-0028 adds the schedule observation interpreter; ED-0029 adds the transcript observation interpreter; ED-0030 adds the vision observation interpreter; ED-0031 adds the Observation Evidence Builder; ED-0032 refines Evidence semantics; ED-0033 adds the Operational State taxonomy; ED-0034 adds Transition Policy contracts and Recording Transition Policy; ED-0035 adds Evidence Signals; ED-0036 adds Recording Coverage Evidence Builder; ED-0037 adds Transcript Continuity Evidence Builder; ED-0038 adds generic Evidence Builder semantic selection mechanics; ED-0039 adds cross-domain Session Boundary Evidence composition; ED-0040 adds the Session Transition Policy. |
| `backend/app/contexts/production/dispatcher/` | Production event dispatcher contract package. | ED-0015 | Backend-only in-memory routing boundary from Production Events to matching interpreters; no interpretation, reasoning, infrastructure, persistence, APIs, adapters, or frontend behavior. |
| `backend/app/contexts/production/evidence/` | Production evidence contract package. | ED-0007 / ED-0032 | Backend-only evidence primitives with first-class concern, purpose, role, strength, and weight semantics; no reasoning, proposals, scoring policy, Operational State, persistence, APIs, queues, workers, or frontend behavior. |
| `backend/app/contexts/production/evidence_builder/` | Observation evidence builder package. | ED-0031 / ED-0032 / ED-0035 / ED-0038 | Backend-only reasoning boundary and semantic-selection mechanics that organize objective Observations into explainable Evidence using first-class EvidenceConcern, EvidenceRole, and EvidenceSignal semantics; no semantic interpretation, Hypotheses, Findings, Verification Decisions, Operational Products, Operational State, AI, persistence, APIs, queues, workers, provider-specific behavior, or frontend behavior. |
| `backend/app/contexts/production/session_boundary_evidence_builder/` | Session Boundary Evidence Builder package. | ED-0039 | First cross-domain Evidence Builder; composes structured domain Evidence into possible-session-start and possible-session-end Evidence with deterministic context grouping and ID-only lineage, without Session State or transition policy. |
| `backend/app/contexts/production/session_transition_policy/` | Session Transition Policy package. | ED-0040 | Narrow deterministic policy that evaluates Session Boundary Evidence into explainable proposed inactive, active, ending, or ended values without state mutation, scoring, execution, or persistence. |
| `backend/app/contexts/production/finding/` | Production finding contract package. | ED-0009 | Backend-only human-reviewable reasoning artifacts; no verification or workflow behavior. |
| `backend/app/contexts/production/hypothesis/` | Production hypothesis contract package. | ED-0008 | Backend-only hypothesis primitives; no proposals, verification, or action behavior. |
| `backend/app/contexts/production/interpreter/` | Production event interpreter contract package. | ED-0014 | Backend-only translation boundary from Production Events to Observations; no adapters, reasoning, persistence, APIs, queues, workers, or frontend behavior. |
| `backend/app/contexts/production/media_artifact_adapter/` | Production media artifact adapter contract package. | ED-0017 | Backend-only adapter-facing artifact availability contracts that emit generic Production Events; no filesystem watching, ingestion, validation, chunk registration, persistence, APIs, queues, workers, or frontend behavior. |
| `backend/app/contexts/production/media_artifact_observation_interpreter/` | Media artifact observation interpreter package. | ED-0026 | Backend-only Observation Interpreter that translates media artifact Production Events into objective media artifact Observations; no media ingestion, validation, file inspection, chunk registration, reasoning, persistence, APIs, queues, workers, AI, provider-specific behavior, or frontend behavior. |
| `backend/app/contexts/production/observation/` | Production observation contract package. | ED-0006 | Backend-only observation primitives; no reasoning or detection logic. |
| `backend/app/contexts/production/observation_interpreter/` | Production observation interpreter contract package. | ED-0023 | Backend-only AR-2.0 interpreter contracts for translating Production Events into objective Observations; no Evidence, Hypotheses, Findings, Verification Decisions, Operational Products, persistence, APIs, queues, workers, adapters, or frontend behavior. |
| `backend/app/contexts/production/operator_adapter/` | Production operator source adapter contract package. | ED-0022 | Backend-only intentional human input contracts that emit generic Production Events; no UI, authentication, permissions, workflows, review systems, correctness determination, reasoning, persistence, APIs, queues, workers, or frontend behavior. |
| `backend/app/contexts/production/operational_state/` | Operational State taxonomy package. | ED-0033 | Backend-only taxonomy contracts for directly observable state, evidence-derived state, StageFlow readiness, and environmental context; no transition policy, state machines, repositories, persistence, APIs, queues, workers, AI, frontend behavior, Hypotheses, Findings, Verification Decisions, Operational Products, or provider-specific behavior. |
| `backend/app/contexts/production/operational_product/` | Production operational product contract package. | ED-0011 | Backend-only generic execution-layer primitives; no specialized products, persistence, APIs, queues, or workers. |
| `backend/app/contexts/production/production_event/` | Production event contract package. | ED-0013 | Backend-only provider-agnostic runtime input primitives; no adapters, observation generation, persistence, APIs, queues, workers, or frontend behavior. |
| `backend/app/contexts/production/recording_activity_observation_interpreter/` | Recording activity observation interpreter package. | ED-0024 | Backend-only reference Observation Interpreter that translates recording activity Production Events into objective recording activity Observations; no reasoning, cross-domain interpretation, persistence, APIs, queues, workers, AI, provider-specific behavior, or frontend behavior. |
| `backend/app/contexts/production/recording_adapter/` | Production recording system adapter contract package. | ED-0016 | Backend-only adapter-facing recording activity contracts that emit generic Production Events; no provider integrations, media ingestion, persistence, APIs, queues, workers, or frontend behavior. |
| `backend/app/contexts/production/recording_coverage_evidence_builder/` | Recording Coverage Evidence Builder package. | ED-0036 / ED-0038 | Backend-only concrete Evidence Builder that converts objective recording activity Observations into recording coverage Evidence and first-class Evidence Signals using shared semantic-selection mechanics without state mutation, transition execution, Session reasoning, persistence, APIs, queues, workers, AI, or frontend behavior. |
| `backend/app/contexts/production/recording_transition_policy/` | Recording Transition Policy package. | ED-0034 / ED-0035 | Backend-only deterministic policy for evaluating recording-state transitions from recording coverage Evidence Signals; no state mutation, execution, repositories, state machines, persistence, APIs, queues, workers, AI, frontend behavior, Hypotheses, Findings, Verification Decisions, Operational Products, or provider-specific behavior. |
| `backend/app/contexts/production/runtime_clock/` | Production runtime clock contract package. | ED-0019 | Backend-only time-boundary ingress contracts that emit generic Production Events; no scheduling infrastructure, retry execution, reconciliation, persistence, APIs, queues, workers, or frontend behavior. |
| `backend/app/contexts/production/runtime_clock_observation_interpreter/` | Runtime clock observation interpreter package. | ED-0027 | Backend-only Observation Interpreter that translates runtime clock Production Events into objective time-boundary Observations; no schedule reconciliation, session inference, retry execution, timeout execution, reasoning, persistence, APIs, queues, workers, AI, provider-specific behavior, or frontend behavior. |
| `backend/app/contexts/production/schedule_adapter/` | Production schedule source adapter contract package. | ED-0018 | Backend-only planned-activity contracts that emit generic Production Events; no provider integrations, Sessions, Observations, reasoning, persistence, APIs, queues, workers, or frontend behavior. |
| `backend/app/contexts/production/schedule_observation_interpreter/` | Schedule observation interpreter package. | ED-0028 | Backend-only Observation Interpreter that translates schedule source Production Events into objective planned-reality Observations; no production inference, schedule reconciliation, reasoning, persistence, APIs, queues, workers, AI, provider-specific behavior, or frontend behavior. |
| `backend/app/contexts/production/session_window_product/` | Production session window product contract package. | ED-0012 | Backend-only specialized operational product connecting schedule references to verified timeline ranges; no Session aggregate, media storage, packages, persistence, APIs, or frontend behavior. |
| `backend/app/contexts/production/timeline/` | Production timeline contract package. | ED-0005 | Backend-only continuous recording and session window primitives. |
| `backend/app/contexts/production/transcript_adapter/` | Production transcript source adapter contract package. | ED-0020 | Backend-only transcript availability contracts that emit generic Production Events; no transcription execution, audio processing, model calls, text interpretation, persistence, APIs, queues, workers, or frontend behavior. |
| `backend/app/contexts/production/transcript_continuity_evidence_builder/` | Transcript Continuity Evidence Builder package. | ED-0037 / ED-0038 | Backend-only concrete Evidence Builder that converts objective transcript activity Observations into transcript continuity Evidence and first-class Evidence Signals using shared semantic-selection mechanics without transcript meaning analysis, session reasoning, persistence, APIs, queues, workers, AI, or frontend behavior. |
| `backend/app/contexts/production/transcript_observation_interpreter/` | Transcript observation interpreter package. | ED-0029 | Backend-only Observation Interpreter that translates transcript source Production Events into objective transcript Observations; no language understanding, speaker inference, topic inference, sentiment analysis, reasoning, persistence, APIs, queues, workers, AI, provider-specific behavior, or frontend behavior. |
| `backend/app/contexts/production/transition_policy/` | Operational State Transition Policy package. | ED-0034 | Backend-only generic transition-policy contracts and evaluations; no state mutation, execution, repositories, state machines, persistence, APIs, queues, workers, AI, frontend behavior, Hypotheses, Findings, Verification Decisions, or Operational Products. |
| `backend/app/contexts/production/verification/` | Production verification protocol package. | ED-0010 | Backend-only append-only judgment records; no workflow or operational product behavior. |
| `backend/app/contexts/production/vision_adapter/` | Production vision source adapter contract package. | ED-0021 | Backend-only visual detection contracts that emit generic Production Events; no OCR, computer vision execution, model calls, semantic interpretation, persistence, APIs, queues, workers, or frontend behavior. |
| `backend/app/contexts/production/vision_observation_interpreter/` | Vision observation interpreter package. | ED-0030 | Backend-only Observation Interpreter that translates vision source Production Events into objective vision Observations; no OCR, detected-text interpretation, logo identification, face or person identification, scene-meaning classification, session inference, clip inference, production-state inference, reasoning, persistence, APIs, queues, workers, AI, provider-specific behavior, or frontend behavior. |
| `backend/app/contexts/publishing/` | Publishing & Analytics context package boundary. | ED-0002 | Empty package boundary. |
| `backend/app/contexts/rendering/` | Media Rendering context package boundary. | ED-0002 | Empty package boundary. |
| `backend/app/contexts/simulation/` | Simulation context package boundary. | ED-0002 | Empty package boundary. |
| `backend/app/core/` | Backend process concerns below domain layers. | ED-0002 | Contains config, health, lifecycle, and logging packages. |
| `backend/app/core/config/` | Backend configuration loading. | ED-0002 | Minimal service metadata only. |
| `backend/app/core/health/` | Minimal health response support. | ED-0002 | No dependency checks. |
| `backend/app/core/lifecycle/` | FastAPI lifecycle hook. | ED-0002 | No external resource initialization. |
| `backend/app/core/logging/` | Minimal logging setup. | ED-0002 | Standard logging only. |
| `backend/app/shared/` | Domain-neutral shared primitives package root. | ED-0002 / ED-0004 | ED-0004 populates generic shared contracts. |
| `backend/app/shared/domain_events/` | Base domain event contract package. | ED-0004 | Contains only generic event primitives. |
| `backend/app/shared/errors/` | Structured shared error package. | ED-0004 | Contains generic error categories only. |
| `backend/app/shared/ids/` | Shared identifier package. | ED-0004 | Contains generic entity and correlation IDs only. |
| `backend/app/shared/result/` | Shared result package. | ED-0004 | Contains explicit success/failure result contract. |
| `backend/app/shared/time/` | Shared time package. | ED-0004 | Contains clocks, timestamp alias, and time range. |
| `backend/tests/` | Backend test suite. | ED-0002 through ED-0040 / reviewed by ED-0041 | Contains 705 health, shared, Production Event, interpreter, Observation, Evidence, builder, Operational State, and transition policy tests. |
| `docs/` | Canonical and supporting architecture documentation. | Existing architecture work | Preserved by ED-0001. |
| `docs/reviews/` | Structured architecture and codebase review reports. | ED-0041 | Contains the ED-0041 review, findings register, and directive roadmap. |
| `examples/` | Future examples that demonstrate approved implementation patterns. | ED-0001 | No application examples are created by ED-0001. |
| `frontend/` | Next.js frontend workspace. | ED-0003 | Contains no backend communication or business logic in ED-0003. |
| `frontend/app/` | Next.js App Router root. | ED-0003 | Contains only the root layout, root page, and global styles. |
| `frontend/src/` | Frontend source package root. | ED-0003 | Organized around frontend foundations and future workflows. |
| `frontend/src/components/` | Shared frontend component package. | ED-0003 | No components generated in ED-0003. |
| `frontend/src/core/` | Frontend application-wide foundations. | ED-0003 | Reserved for future providers and configuration. |
| `frontend/src/layouts/` | Reusable layout package. | ED-0003 | Reserved for future workflow layouts. |
| `frontend/src/routes/` | Route metadata and route support package. | ED-0003 | No additional routes in ED-0003. |
| `frontend/src/shared/` | Shared frontend utilities and contract package. | ED-0003 / ED-0004 | ED-0004 populates generic shared contracts. |
| `frontend/src/shared/domain-events/` | Frontend base domain event contract package. | ED-0004 | Contains only generic event types. |
| `frontend/src/shared/errors/` | Frontend structured error package. | ED-0004 | Contains generic error categories only. |
| `frontend/src/shared/ids/` | Frontend shared identifier package. | ED-0004 | Contains generic entity and correlation IDs only. |
| `frontend/src/shared/result/` | Frontend shared result package. | ED-0004 | Contains explicit success/failure result type. |
| `frontend/src/shared/time/` | Frontend shared time package. | ED-0004 | Contains clock and time range contracts. |
| `frontend/src/styles/` | Frontend styling foundation package. | ED-0003 | Contains initial design token module. |
| `frontend/src/themes/` | Theme architecture package. | ED-0003 | Reserved for future white-label theme work. |
| `frontend/src/workflows/` | Workflow-oriented frontend package root. | ED-0003 | Package boundaries only; no workflow implementation. |
| `frontend/src/workflows/content_lead/` | Content Lead workflow package boundary. | ED-0003 | Empty boundary with README only. |
| `frontend/src/workflows/package_delivery/` | Package Delivery workflow package boundary. | ED-0003 | Empty boundary with README only. |
| `frontend/src/workflows/reviewer/` | Reviewer workflow package boundary. | ED-0003 | Empty boundary with README only. |
| `frontend/src/workflows/simulation/` | Simulation workflow package boundary. | ED-0003 | Empty boundary with README only. |
| `frontend/src/workflows/technical_director/` | Technical Director workflow package boundary. | ED-0003 | Empty boundary with README only. |
| `frontend/tests/` | Frontend test package. | ED-0003 | No test runner added in ED-0003. |
| `mock_data/` | Future safe synthetic fixtures and mock data. | ED-0001 | Real production or event data does not belong here. |
| `reference/` | Future non-authoritative reference material. | ED-0001 | Canonical specifications remain in root files and `docs/`. |
| `scripts/` | Future repository maintenance and developer utility scripts. | ED-0001 | No scripts are created by ED-0001. |
| `tests/` | Future automated tests. | ED-0001 | No tests or test runner configuration are created by ED-0001. |

## Repository-Level Files

| Path | Purpose | Owning Engineering Directive | Notes |
| --- | --- | --- | --- |
| `.editorconfig` | Shared editor formatting defaults. | ED-0001 | Covers common Python, TypeScript, Markdown, YAML, and JSON conventions. |
| `.env.example` | Example environment file. | Existing repository work | Preserved by ED-0001. |
| `.gitattributes` | Git text and binary file handling rules. | Existing repository work | Preserved by ED-0001. |
| `.gitignore` | Ignored local, generated, runtime, and dependency files. | Existing repository work / ED-0003 | ED-0003 adds TypeScript build cache ignore coverage. |
| `ARCHITECTURE_DECISIONS.md` | Architecture Decision Record index. | ED-0001 | Initialized with ADR-0001 through ADR-0005. |
| `CHANGELOG.md` | Future release and change history. | Existing repository work | Preserved by ED-0001. |
| `CONTRIBUTING.md` | Initial contributor guide and engineering process expectations. | ED-0001 | Establishes specification-first contribution rules. |
| `ENGINEERING_DIRECTIVES.md` | Engineering Directive index. | ED-0001 / ED-0041 | Registers implemented and reviewed directives through ED-0041. |
| `IMPLEMENTATION_PLAN.md` | High-level staged implementation plan. | ED-0001 | Governance only; no implementation detail. |
| `LICENSE` | Repository license. | ED-0001 | MIT License. |
| `PRODUCT_CONSTITUTION.md` | Canonical product constitution. | Existing architecture work | Preserved by ED-0001. |
| `README.md` | Repository introduction. | Existing repository work | Preserved by ED-0001. |
| `REPOSITORY_MANIFEST.md` | Repository structure and ownership manifest. | ED-0001 / ED-0041 | Created by ED-0001 and updated for the AR-3.0 review checkpoint. |
| `ROADMAP.md` | Future roadmap document. | Existing repository work | Preserved by ED-0001. |

## Backend Files

| Path | Purpose | Owning Engineering Directive | Notes |
| --- | --- | --- | --- |
| `backend/.python-version` | Declares the backend Python version. | ED-0002 | Uses Python 3.13. |
| `backend/README.md` | Backend workspace guide. | ED-0002 | Documents local setup, health route, and quality commands. |
| `backend/pyproject.toml` | Backend Python project and tooling configuration. | ED-0002 | Defines FastAPI, Pydantic, Ruff, Pyright, and Pytest setup managed by `uv`. |
| `backend/uv.lock` | Locked backend dependency graph. | ED-0002 | Generated by `uv sync --dev`. |
| `backend/app/__init__.py` | Backend application package marker. | ED-0002 | No business logic. |
| `backend/app/main.py` | Minimal FastAPI app factory and app instance. | ED-0002 | Registers only the API v1 router. |
| `backend/app/api/__init__.py` | API package marker. | ED-0002 | No business logic. |
| `backend/app/api/README.md` | API package guide. | ED-0002 | Documents HTTP interface boundary. |
| `backend/app/api/v1/__init__.py` | API v1 package marker. | ED-0002 | No business logic. |
| `backend/app/api/v1/README.md` | API v1 package guide. | ED-0002 | Documents the ED-0002 health-only scope. |
| `backend/app/api/v1/health.py` | Health route. | ED-0002 | Exposes `GET /api/v1/health`. |
| `backend/app/api/v1/router.py` | API v1 router composition. | ED-0002 | Includes only the health router. |
| `backend/app/bootstrap/__init__.py` | Bootstrap package marker. | ED-0002 | Reserved for future composition. |
| `backend/app/bootstrap/README.md` | Bootstrap package guide. | ED-0002 | Documents reserved scope. |
| `backend/app/core/config/settings.py` | Minimal configuration loader. | ED-0002 | Loads service metadata only. |
| `backend/app/core/health/service.py` | Minimal health response model and function. | ED-0002 | No dependency checks. |
| `backend/app/core/lifecycle/lifespan.py` | FastAPI lifespan hook. | ED-0002 | Sets process readiness only. |
| `backend/app/core/logging/configure.py` | Minimal logging configuration. | ED-0002 | Standard logging only. |
| `backend/app/contexts/production/evidence/__init__.py` | Production evidence package exports. | ED-0007 / ED-0032 | Exports evidence contracts, including ED-0032 semantic refinements. |
| `backend/app/contexts/production/evidence/evidence_concern.py` | Evidence concern categories. | ED-0032 | First-class operational questions Evidence can relate to without becoming conclusions. |
| `backend/app/contexts/production/evidence/evidence_item.py` | Evidence item contract. | ED-0007 / ED-0032 | References an Observation ID without embedding Observation objects and carries first-class EvidenceRole semantics. |
| `backend/app/contexts/production/evidence/evidence_observation_reference.py` | Evidence observation reference contract. | ED-0032 | ID-only Observation participation reference with role, optional strength, optional weight, rationale, and metadata. |
| `backend/app/contexts/production/evidence/evidence_purpose.py` | Evidence purpose categories. | ED-0007 / ED-0032 | Describes why Evidence is assembled or retained, distinct from EvidenceConcern. |
| `backend/app/contexts/production/evidence/evidence_role.py` | Evidence role categories. | ED-0032 | First-class relationship between an Observation reference and an Evidence concern. |
| `backend/app/contexts/production/evidence/evidence_set.py` | Evidence set contract. | ED-0007 / ED-0031 / ED-0032 / ED-0035 | Groups one or more evidence items; ED-0031 allows non-recording-block Evidence when source Observations are truthfully anchored elsewhere; ED-0032 adds explicit EvidenceConcern; ED-0035 adds first-class EvidenceSignal references. |
| `backend/app/contexts/production/evidence/evidence_signal.py` | Evidence signal vocabulary. | ED-0035 | First-class operational indication values carried by Evidence without becoming Operational State, Hypotheses, Findings, or verification. |
| `backend/app/contexts/production/evidence/evidence_signal_reference.py` | Evidence signal reference contract. | ED-0035 | ID-only Signal participation reference to EvidenceItem IDs and Observation IDs. |
| `backend/app/contexts/production/evidence/evidence_strength.py` | Evidence strength categories. | ED-0007 | Includes contradictory support as first-class evidence. |
| `backend/app/contexts/production/evidence/evidence_summary.py` | Evidence summary contract. | ED-0007 / ED-0032 / ED-0035 | Summarizes concern, purpose, strength counts, role counts, and signal references without final confidence. |
| `backend/app/contexts/production/evidence_builder/__init__.py` | Observation evidence builder package exports. | ED-0031 / ED-0032 / ED-0035 / ED-0038 | Exports the builder, context, rule, result, summary, status, default rule helpers, and generic semantic-selection mechanics. |
| `backend/app/contexts/production/evidence_builder/README.md` | Observation evidence builder package guide. | ED-0031 / ED-0032 / ED-0035 / ED-0038 | Documents the Observation-to-Evidence boundary, first-class EvidenceConcern/EvidenceRole/EvidenceSignal semantics, semantic-selection mechanics, traceability, and excluded reasoning behavior. |
| `backend/app/contexts/production/evidence_builder/evidence_builder_context.py` | Evidence builder context contract. | ED-0031 | Lightweight context for building Evidence without persistence or operational state. |
| `backend/app/contexts/production/evidence_builder/evidence_builder_context_key.py` | Evidence builder context key contract. | ED-0038 | Stable generic grouping key supplied by concrete builders using ID-only or immutable scalar components. |
| `backend/app/contexts/production/evidence_builder/evidence_builder_deduplication.py` | Evidence builder deduplication utility. | ED-0038 | Deterministic Observation-ID duplicate handling with retained Observations and duplicate selection records. |
| `backend/app/contexts/production/evidence_builder/evidence_builder_input_classification.py` | Evidence builder input classification values. | ED-0038 | Distinguishes recognized, ignored, unsupported, missing semantic value, duplicate, and unknown inputs. |
| `backend/app/contexts/production/evidence_builder/evidence_builder_input_report.py` | Evidence builder input report contract. | ED-0038 | ID-only generic report for recognized, ignored, unsupported, duplicate Observation IDs, selections, and applied rule IDs. |
| `backend/app/contexts/production/evidence_builder/evidence_builder_ordering.py` | Evidence builder ordering utility. | ED-0038 | Deterministic provider-agnostic ordering by observed time, timeline offset, Observation ID, and input index fallback. |
| `backend/app/contexts/production/evidence_builder/evidence_builder_result.py` | Evidence builder result contract. | ED-0031 | Returns source Observation IDs, zero or more Evidence sets, warnings, and metadata. |
| `backend/app/contexts/production/evidence_builder/evidence_builder_rule.py` | Evidence builder rule contract. | ED-0031 / ED-0032 / ED-0035 | Declarative single-concern grouping rule using first-class EvidenceConcern, EvidenceRole, and EvidenceSignal semantics. |
| `backend/app/contexts/production/evidence_builder/evidence_builder_semantic_rule.py` | Evidence builder semantic rule contract. | ED-0038 | Generic rule mechanics for one normalized semantic value and target EvidenceSignal without owning concern or purpose. |
| `backend/app/contexts/production/evidence_builder/evidence_builder_summary.py` | Evidence builder summary contract. | ED-0031 / ED-0032 / ED-0035 | Lightweight diagnostics for rule, EvidenceConcern, and declared EvidenceSignal counts. |
| `backend/app/contexts/production/evidence_builder/observation_evidence_builder.py` | Observation evidence builder contract. | ED-0031 / ED-0032 / ED-0035 | Groups objective Observations into existing EvidenceSet contracts while preserving traceability, carrying EvidenceSignals, and avoiding semantic conclusions. |
| `backend/app/contexts/production/evidence_builder/observation_semantic_selection.py` | Observation semantic selection result contract. | ED-0038 | Explicit result for selected, ignored, missing, unsupported, duplicate, or unknown structured semantic selection. |
| `backend/app/contexts/production/evidence_builder/observation_semantic_selector.py` | Observation semantic selector contract. | ED-0038 | Deterministic structured-key selector for accepted Observation types without Signal mapping or Evidence construction. |
| `backend/app/contexts/production/session_boundary_evidence_builder/__init__.py` | Session Boundary Evidence Builder package exports. | ED-0039 | Exports the builder, status, rules, mappings, context, result, summary, constants, and construction helpers. |
| `backend/app/contexts/production/session_boundary_evidence_builder/README.md` | Session Boundary Evidence Builder package guide. | ED-0039 | Documents Concern-and-Signal mappings, roles, context, temporal grouping, anchors, classification, traceability, and architectural exclusions. |
| `backend/app/contexts/production/session_boundary_evidence_builder/session_boundary_evidence_builder.py` | Cross-domain Session Boundary Evidence Builder implementation. | ED-0039 | Deterministically composes structured EvidenceSets into separate possible-start and possible-end EvidenceSets without policy evaluation, state creation, scoring, or persistence. |
| `backend/app/contexts/production/session_boundary_evidence_builder/session_boundary_evidence_context.py` | Session boundary Evidence context contract. | ED-0039 | Immutable ID-only recording, stage, schedule, stream, artifact, timeline, and organizational anchor context with partial-context support. |
| `backend/app/contexts/production/session_boundary_evidence_builder/session_boundary_evidence_mapping.py` | Session boundary Evidence mapping contract. | ED-0039 | Centralizes declarative source Concern-and-Signal to possible-boundary Concern-and-Role mappings. |
| `backend/app/contexts/production/session_boundary_evidence_builder/session_boundary_evidence_result.py` | Session boundary Evidence result contract. | ED-0039 | Describes produced start/end EvidenceSets, input classifications, applied rules, and generated contexts without choosing a boundary. |
| `backend/app/contexts/production/session_boundary_evidence_builder/session_boundary_evidence_rule.py` | Session boundary Evidence rule contract. | ED-0039 | Immutable declarative rule for accepted source concerns and Signal treatment without scores or policy behavior. |
| `backend/app/contexts/production/session_boundary_evidence_builder/session_boundary_evidence_summary.py` | Session boundary Evidence summary contract. | ED-0039 | Summarizes inputs, outputs, Signals, contexts, timeline span, and source role/strength distributions without ranking or confidence. |
| `backend/app/contexts/production/session_transition_policy/__init__.py` | Session Transition Policy package exports. | ED-0040 | Exports policy, requirement, rule, mapping, category, profile, result, summary, constants, and helpers. |
| `backend/app/contexts/production/session_transition_policy/README.md` | Session Transition Policy package guide. | ED-0040 | Documents lifecycle scope, categorical start/end rules, source independence, compatible context, freshness, outcomes, and architectural exclusions. |
| `backend/app/contexts/production/session_transition_policy/session_transition_policy.py` | Session Transition Policy implementation. | ED-0040 | Deterministically evaluates compatible boundary Evidence into one TransitionEvaluation with traceability and no execution, state mutation, scoring, or persistence. |
| `backend/app/contexts/production/session_transition_policy/session_transition_rule.py` | Session transition rule contract. | ED-0040 | Immutable static transition rule with boundary concern, categorical requirements, allowed roles, contradiction behavior, and rationale. |
| `backend/app/contexts/production/session_transition_policy/session_transition_mapping.py` | Session transition mapping and static rules. | ED-0040 | Centralizes boundary Signal categories, supported transition definitions, categorical requirement composition, and rationale language. |
| `backend/app/contexts/production/session_transition_policy/session_transition_requirement.py` | Session transition requirement contract. | ED-0040 | Immutable categorical minimum, source-independence, Signal, role, freshness, and rationale requirement without weights or expressions. |
| `backend/app/contexts/production/session_transition_policy/session_transition_evidence_profile.py` | Session transition Evidence profile contract. | ED-0040 | Describes contributing Evidence, Signals, categories, roles, strengths, independent sources, context, and anchors without confidence or ranking. |
| `backend/app/contexts/production/session_transition_policy/session_transition_result.py` | Session transition result contract. | ED-0040 | Wraps one generic TransitionEvaluation with applied rule, Evidence profile, requirement diagnostics, and input classifications. |
| `backend/app/contexts/production/session_transition_policy/session_transition_summary.py` | Session transition summary contract. | ED-0040 | Summarizes current/proposed values, outcome, boundary concern, Signals, sources, requirements, context, and organizational anchors without claiming execution. |
| `backend/app/contexts/production/recording_coverage_evidence_builder/__init__.py` | Recording Coverage Evidence Builder package exports. | ED-0036 | Exports concrete recording coverage builder, mappings, rules, result, summary, and helper functions. |
| `backend/app/contexts/production/recording_coverage_evidence_builder/README.md` | Recording Coverage Evidence Builder package guide. | ED-0036 / ED-0038 | Documents recording Observation semantics, shared semantic-selection usage, Signal mappings, grouping, duplicate handling, policy separation, and exclusions. |
| `backend/app/contexts/production/recording_coverage_evidence_builder/recording_coverage_evidence_builder.py` | Recording Coverage Evidence Builder implementation. | ED-0036 / ED-0038 | Deterministically builds recording coverage Evidence and Signals from recording activity Observations using shared selection, ordering, deduplication, reporting, and context-key mechanics without invoking transition policies or mutating state. |
| `backend/app/contexts/production/recording_coverage_evidence_builder/recording_coverage_evidence_mapping.py` | Recording coverage Evidence mapping contract. | ED-0036 | Centralizes mapping from structured recording Observation semantics to first-class EvidenceSignals. |
| `backend/app/contexts/production/recording_coverage_evidence_builder/recording_coverage_evidence_result.py` | Recording coverage Evidence result contract. | ED-0036 / ED-0038 | Descriptive build result with produced Evidence, consumed, ignored, unsupported, duplicate Observation IDs, applied rule IDs, and optional generic input report. |
| `backend/app/contexts/production/recording_coverage_evidence_builder/recording_coverage_evidence_rule.py` | Recording coverage Evidence rule contract. | ED-0036 | Declarative rule for one supported recording Observation semantic and target EvidenceSignal. |
| `backend/app/contexts/production/recording_coverage_evidence_builder/recording_coverage_evidence_summary.py` | Recording coverage Evidence summary contract. | ED-0036 | Summarizes input, recognized, ignored, unsupported, EvidenceSet, EvidenceItem, Signal, recording-block, and stage counts without policy evaluation. |
| `backend/app/contexts/production/transcript_continuity_evidence_builder/__init__.py` | Transcript Continuity Evidence Builder package exports. | ED-0037 | Exports concrete transcript continuity builder, mappings, rules, result, summary, and helper functions. |
| `backend/app/contexts/production/transcript_continuity_evidence_builder/README.md` | Transcript Continuity Evidence Builder package guide. | ED-0037 / ED-0038 | Documents transcript lifecycle semantics, shared semantic-selection usage, accumulating continuity, stream grouping, duplicate handling, explicit interruption requirements, and exclusions. |
| `backend/app/contexts/production/transcript_continuity_evidence_builder/transcript_continuity_evidence_builder.py` | Transcript Continuity Evidence Builder implementation. | ED-0037 / ED-0038 | Deterministically builds transcript continuity Evidence and Signals from transcript activity Observations using shared selection, ordering, deduplication, reporting, and context-key mechanics without policy invocation, timeout inference, transcript meaning analysis, or state mutation. |
| `backend/app/contexts/production/transcript_continuity_evidence_builder/transcript_continuity_evidence_mapping.py` | Transcript continuity Evidence mapping contract. | ED-0037 | Centralizes mapping from structured transcript Observation lifecycle semantics to first-class EvidenceSignals. |
| `backend/app/contexts/production/transcript_continuity_evidence_builder/transcript_continuity_evidence_result.py` | Transcript continuity Evidence result contract. | ED-0037 / ED-0038 | Descriptive build result with produced Evidence, consumed, ignored, unsupported, duplicate Observation IDs, applied rule IDs, and optional generic input report. |
| `backend/app/contexts/production/transcript_continuity_evidence_builder/transcript_continuity_evidence_rule.py` | Transcript continuity Evidence rule contract. | ED-0037 | Declarative rule for one supported transcript Observation lifecycle and target EvidenceSignal. |
| `backend/app/contexts/production/transcript_continuity_evidence_builder/transcript_continuity_evidence_summary.py` | Transcript continuity Evidence summary contract. | ED-0037 | Summarizes input, recognized, ignored, unsupported, duplicate, EvidenceSet, EvidenceItem, Signal, stream, recording-block, stage, and timeline span counts without policy evaluation. |
| `backend/app/contexts/production/operational_state/__init__.py` | Operational State package exports. | ED-0033 | Exports the Operational State taxonomy contracts. |
| `backend/app/contexts/production/operational_state/README.md` | Operational State package guide. | ED-0033 | Documents mission boundary, state families, traceability, environmental context, and deferred transition policy. |
| `backend/app/contexts/production/operational_state/operational_state.py` | Operational State contract. | ED-0033 | Descriptive state record with explicit family, kind, subject, value, status, basis, and optional context; no transition behavior. |
| `backend/app/contexts/production/operational_state/operational_state_basis.py` | Operational State basis contract. | ED-0033 | ID-only Observation and EvidenceSet traceability for why a state exists. |
| `backend/app/contexts/production/operational_state/operational_state_family.py` | Operational State family categories. | ED-0033 | Distinguishes directly observable, evidence-derived, StageFlow readiness, environmental context, and unknown state. |
| `backend/app/contexts/production/operational_state/operational_state_kind.py` | Operational State kind categories. | ED-0033 | StageFlow-focused state categories without provider-specific or general production-monitoring kinds. |
| `backend/app/contexts/production/operational_state/operational_state_status.py` | Operational State record lifecycle status. | ED-0033 | Describes whether a state record is current, superseded, expired, archived, or unknown without automatic supersession. |
| `backend/app/contexts/production/operational_state/operational_state_subject.py` | Operational State subject reference. | ED-0033 | Lightweight subject type, identifier, label, and metadata without embedding domain objects. |
| `backend/app/contexts/production/operational_state/operational_state_summary.py` | Operational State summary contract. | ED-0033 | Lightweight diagnostics for family, kind, value, status, basis counts, and optional context. |
| `backend/app/contexts/production/operational_state/operational_state_value.py` | Operational State value categories. | ED-0033 | Generic descriptive values without workflow actions or universal state machine behavior. |
| `backend/app/contexts/production/recording_transition_policy/__init__.py` | Recording Transition Policy package exports. | ED-0034 / ED-0035 | Exports recording transition policy, rule, signal mapping, summary, and helper contracts. |
| `backend/app/contexts/production/recording_transition_policy/README.md` | Recording Transition Policy package guide. | ED-0034 / ED-0035 | Documents supported recording-state evaluations, EvidenceSignal inputs, transitional metadata compatibility, and execution exclusions. |
| `backend/app/contexts/production/recording_transition_policy/recording_transition_mapping.py` | Recording transition mapping contract. | ED-0034 / ED-0035 | Declarative mapping from recording EvidenceSignals to active, paused, or stopped proposed values. |
| `backend/app/contexts/production/recording_transition_policy/recording_transition_policy.py` | Recording Transition Policy implementation. | ED-0034 / ED-0035 | Deterministically evaluates recording coverage Evidence Signals and returns TransitionEvaluation objects without mutating state. |
| `backend/app/contexts/production/recording_transition_policy/recording_transition_rule.py` | Recording transition rule contract. | ED-0034 / ED-0035 | Declarative rule for one supported recording transition target keyed by EvidenceSignal. |
| `backend/app/contexts/production/recording_transition_policy/recording_transition_summary.py` | Recording transition summary contract. | ED-0034 | Lightweight diagnostics for the concrete recording policy. |
| `backend/app/contexts/production/transition_policy/__init__.py` | Transition Policy package exports. | ED-0034 | Exports generic transition policy, evaluation, result, summary, and reason contracts. |
| `backend/app/contexts/production/transition_policy/README.md` | Transition Policy package guide. | ED-0034 | Documents policy evaluation, explainable evaluations, outcomes, and deferred execution. |
| `backend/app/contexts/production/transition_policy/operational_state_transition_policy.py` | Generic Operational State Transition Policy contract. | ED-0034 | Deterministic policy boundary that evaluates Evidence and returns TransitionEvaluation without executing transitions. |
| `backend/app/contexts/production/transition_policy/transition_evaluation.py` | Transition Evaluation contract. | ED-0034 | Immutable explanation of policy outcome with current state, proposed value, evidence IDs, rationale, timestamp, and metadata. |
| `backend/app/contexts/production/transition_policy/transition_policy_result.py` | Transition policy outcome categories. | ED-0034 | Approved transition evaluation outcomes. |
| `backend/app/contexts/production/transition_policy/transition_policy_summary.py` | Transition policy summary contract. | ED-0034 | Lightweight diagnostics for a transition policy. |
| `backend/app/contexts/production/transition_policy/transition_reason.py` | Transition reason contract. | ED-0034 | Concise descriptive rationale for transition evaluations. |
| `backend/app/contexts/production/dispatcher/__init__.py` | Production event dispatcher package exports. | ED-0015 | Exports dispatcher contracts. |
| `backend/app/contexts/production/dispatcher/README.md` | Production event dispatcher package guide. | ED-0015 | Documents routing responsibility and infrastructure exclusions. |
| `backend/app/contexts/production/dispatcher/dispatch_context.py` | Dispatch context contract. | ED-0015 | Lightweight routing context convertible to interpreter context. |
| `backend/app/contexts/production/dispatcher/dispatch_result.py` | Dispatch result contract. | ED-0015 | Aggregates invoked interpreter IDs and InterpreterResults unchanged. |
| `backend/app/contexts/production/dispatcher/dispatch_rule.py` | Dispatch rule contract. | ED-0015 | Declarative routing intent without execution or discovery. |
| `backend/app/contexts/production/dispatcher/dispatch_summary.py` | Dispatch summary contract. | ED-0015 | Lightweight diagnostics summary without dispatch execution or provider details. |
| `backend/app/contexts/production/dispatcher/production_event_dispatcher.py` | Production event dispatcher contract. | ED-0015 | Small in-memory router from Production Events to matching interpreters. |
| `backend/app/contexts/production/finding/__init__.py` | Production finding package exports. | ED-0009 | Exports finding contracts. |
| `backend/app/contexts/production/finding/finding.py` | Finding contract. | ED-0009 | Human-reviewable reasoning artifact referencing hypothesis IDs only. |
| `backend/app/contexts/production/finding/finding_confidence.py` | Finding confidence contract. | ED-0009 | Numeric confidence from `0.0` to `1.0`. |
| `backend/app/contexts/production/finding/finding_location.py` | Finding location contract. | ED-0009 | Point or range on the production timeline. |
| `backend/app/contexts/production/finding/finding_origin.py` | Finding origin categories. | ED-0009 | Generic reasoning pathways only. |
| `backend/app/contexts/production/finding/finding_summary.py` | Finding summary contract. | ED-0009 | Lightweight review-surface representation without workflow state. |
| `backend/app/contexts/production/finding/finding_support.py` | Finding support contract. | ED-0009 | References supporting, contradicting, and neutral hypothesis IDs. |
| `backend/app/contexts/production/finding/finding_type.py` | Finding type categories. | ED-0009 | Generic finding categories only. |
| `backend/app/contexts/production/hypothesis/__init__.py` | Production hypothesis package exports. | ED-0008 | Exports hypothesis contracts. |
| `backend/app/contexts/production/hypothesis/hypothesis.py` | Hypothesis contract. | ED-0008 | Represents a possible interpretation of evidence. |
| `backend/app/contexts/production/hypothesis/hypothesis_confidence.py` | Hypothesis confidence contract. | ED-0008 | Numeric confidence from `0.0` to `1.0`. |
| `backend/app/contexts/production/hypothesis/hypothesis_status.py` | Hypothesis status categories. | ED-0008 | Tentative lifecycle states only; not verification. |
| `backend/app/contexts/production/hypothesis/hypothesis_support.py` | Hypothesis support contract. | ED-0008 | References supporting, contradicting, and neutral evidence-set IDs. |
| `backend/app/contexts/production/hypothesis/hypothesis_type.py` | Hypothesis type categories. | ED-0008 | Tentative possible-meaning categories only. |
| `backend/app/contexts/production/interpreter/__init__.py` | Production event interpreter package exports. | ED-0014 | Exports interpreter contracts. |
| `backend/app/contexts/production/interpreter/README.md` | Production event interpreter package guide. | ED-0014 | Documents translation boundary scope and exclusions. |
| `backend/app/contexts/production/interpreter/interpreter_context.py` | Interpreter context contract. | ED-0014 | Lightweight interpretation context without adapter or persistence objects. |
| `backend/app/contexts/production/interpreter/interpreter_result.py` | Interpreter result contract. | ED-0014 | Traceable result containing zero or more Observations only. |
| `backend/app/contexts/production/interpreter/interpreter_rule.py` | Interpreter rule contract. | ED-0014 | Declarative event/source to intended Observation type description without executable logic. |
| `backend/app/contexts/production/interpreter/interpreter_status.py` | Interpreter status categories. | ED-0014 | Availability values for interpreters only. |
| `backend/app/contexts/production/interpreter/interpreter_summary.py` | Interpreter summary contract. | ED-0014 | Lightweight diagnostics summary without execution or provider internals. |
| `backend/app/contexts/production/interpreter/production_event_interpreter.py` | Production event interpreter contract. | ED-0014 | Generic matching and no-op interpretation contract from Production Events to InterpreterResults. |
| `backend/app/contexts/production/media_artifact_adapter/__init__.py` | Media artifact adapter package exports. | ED-0017 | Exports media artifact adapter contracts. |
| `backend/app/contexts/production/media_artifact_adapter/README.md` | Media artifact adapter package guide. | ED-0017 | Documents artifact reporting scope, generic Production Event mapping, and exclusions. |
| `backend/app/contexts/production/media_artifact_adapter/media_artifact_adapter.py` | Media artifact adapter contract. | ED-0017 | Generic adapter contract that emits Production Events only. |
| `backend/app/contexts/production/media_artifact_adapter/media_artifact_capability.py` | Media artifact adapter capability categories. | ED-0017 | Describes what artifact activity an adapter can report without implementing behavior. |
| `backend/app/contexts/production/media_artifact_adapter/media_artifact_event.py` | Media artifact event contract. | ED-0017 | Adapter-level artifact availability event with generic Production Event mapping helper. |
| `backend/app/contexts/production/media_artifact_adapter/media_artifact_identity.py` | Media artifact adapter identity contract. | ED-0017 | Provider-agnostic adapter identity and kind values. |
| `backend/app/contexts/production/media_artifact_adapter/media_artifact_status.py` | Media artifact status categories. | ED-0017 | Generic artifact availability values, not ingestion or validation state. |
| `backend/app/contexts/production/media_artifact_adapter/media_artifact_summary.py` | Media artifact adapter summary contract. | ED-0017 | Lightweight diagnostics summary without event creation or media inspection. |
| `backend/app/contexts/production/media_artifact_adapter/media_artifact_type.py` | Media artifact type categories. | ED-0017 | Broad artifact families without codec or provider-specific types. |
| `backend/app/contexts/production/timeline/__init__.py` | Production timeline package exports. | ED-0005 | Exports timeline contracts and statuses. |
| `backend/app/contexts/production/observation/__init__.py` | Production observation package exports. | ED-0006 / ED-0025 | Exports observation contracts and refined location kinds. |
| `backend/app/contexts/production/observation/observation.py` | Observation contract. | ED-0006 / ED-0025 | Timestamped statement about something objectively noticed, with recording block validation only when such an anchor exists. |
| `backend/app/contexts/production/observation/observation_confidence.py` | Observation confidence contract. | ED-0006 | Numeric confidence from `0.0` to `1.0`. |
| `backend/app/contexts/production/observation/observation_location.py` | Observation location contract. | ED-0006 / ED-0025 | Explicit location anchors for timeline positions, timeline ranges, recording blocks, wall-clock timestamps, stages, composite context, or unknown location. |
| `backend/app/contexts/production/observation/observation_source.py` | Observation source categories. | ED-0006 | Generic source categories only. |
| `backend/app/contexts/production/observation/observation_type.py` | Observation type categories. | ED-0006 | Generic observation types only; no conclusions. |
| `backend/app/contexts/production/observation_interpreter/__init__.py` | Observation interpreter package exports. | ED-0023 | Exports Observation Interpreter contracts. |
| `backend/app/contexts/production/observation_interpreter/README.md` | Observation interpreter package guide. | ED-0023 | Documents the Production Event to Observation boundary and relationship to ED-0014. |
| `backend/app/contexts/production/observation_interpreter/observation_interpreter.py` | Observation interpreter contract. | ED-0023 | Generic contract for translating one or more Production Events into objective Observations. |
| `backend/app/contexts/production/observation_interpreter/observation_interpreter_context.py` | Observation interpreter context contract. | ED-0023 | Lightweight context without adapter, persistence, or session aggregate objects. |
| `backend/app/contexts/production/observation_interpreter/observation_interpreter_policy.py` | Observation interpreter policy contract. | ED-0023 | Small policy settings without scoring, reasoning, or workflow behavior. |
| `backend/app/contexts/production/observation_interpreter/observation_interpreter_result.py` | Observation interpreter result contract. | ED-0023 | Traceable result containing source Production Event IDs and Observations only. |
| `backend/app/contexts/production/observation_interpreter/observation_interpreter_rule.py` | Observation interpreter rule contract. | ED-0023 | Declarative interpretation intent without execution or Observation creation. |
| `backend/app/contexts/production/observation_interpreter/observation_interpreter_summary.py` | Observation interpreter summary contract. | ED-0023 | Lightweight diagnostics summary without interpretation or provider details. |
| `backend/app/contexts/production/media_artifact_observation_interpreter/__init__.py` | Media artifact observation interpreter package exports. | ED-0026 | Exports the concrete interpreter, rule, summary, and mapping contracts. |
| `backend/app/contexts/production/media_artifact_observation_interpreter/README.md` | Media artifact observation interpreter package guide. | ED-0026 | Documents artifact availability observation scope, objective mappings, truthful location anchoring, and exclusions. |
| `backend/app/contexts/production/media_artifact_observation_interpreter/media_artifact_interpreter_rule.py` | Media artifact interpreter rule contract. | ED-0026 | Declarative rule for supported media artifact Production Event translations. |
| `backend/app/contexts/production/media_artifact_observation_interpreter/media_artifact_interpreter_summary.py` | Media artifact interpreter summary contract. | ED-0026 | Lightweight diagnostics for the concrete media artifact interpreter. |
| `backend/app/contexts/production/media_artifact_observation_interpreter/media_artifact_observation_interpreter.py` | Media artifact observation interpreter. | ED-0026 | Concrete interpreter translating supported media artifact Production Events into objective media artifact Observations only. |
| `backend/app/contexts/production/media_artifact_observation_interpreter/media_artifact_observation_mapping.py` | Media artifact observation mapping contract. | ED-0026 | Lightweight declarative mapping for media artifact created, finalized, and failed observations. |
| `backend/app/contexts/production/recording_activity_observation_interpreter/__init__.py` | Recording activity observation interpreter package exports. | ED-0024 | Exports the concrete interpreter, rule, summary, and mapping contracts. |
| `backend/app/contexts/production/recording_activity_observation_interpreter/README.md` | Recording activity observation interpreter package guide. | ED-0024 / ED-0025 | Documents the reference concrete interpreter, objective mappings, exclusions, and recording-block or wall-clock location anchoring. |
| `backend/app/contexts/production/recording_activity_observation_interpreter/recording_activity_interpreter_rule.py` | Recording activity interpreter rule contract. | ED-0024 | Declarative rule for supported recording activity Production Event translations. |
| `backend/app/contexts/production/recording_activity_observation_interpreter/recording_activity_interpreter_summary.py` | Recording activity interpreter summary contract. | ED-0024 | Lightweight diagnostics for the concrete recording activity interpreter. |
| `backend/app/contexts/production/recording_activity_observation_interpreter/recording_activity_observation_interpreter.py` | Recording activity observation interpreter. | ED-0024 | Concrete interpreter translating supported recording-system Production Events into objective recording activity Observations only. |
| `backend/app/contexts/production/recording_activity_observation_interpreter/recording_activity_observation_mapping.py` | Recording activity observation mapping contract. | ED-0024 | Lightweight declarative mapping for recording started, paused, resumed, and stopped activity observations. |
| `backend/app/contexts/production/runtime_clock_observation_interpreter/__init__.py` | Runtime clock observation interpreter package exports. | ED-0027 | Exports the concrete interpreter, rule, summary, and mapping contracts. |
| `backend/app/contexts/production/runtime_clock_observation_interpreter/README.md` | Runtime clock observation interpreter package guide. | ED-0027 | Documents time-boundary observation scope, objective mappings, conservative status handling, truthful location anchoring, and exclusions. |
| `backend/app/contexts/production/runtime_clock_observation_interpreter/runtime_clock_interpreter_rule.py` | Runtime clock interpreter rule contract. | ED-0027 | Declarative rule for supported runtime clock Production Event translations. |
| `backend/app/contexts/production/runtime_clock_observation_interpreter/runtime_clock_interpreter_summary.py` | Runtime clock interpreter summary contract. | ED-0027 | Lightweight diagnostics for the concrete runtime clock interpreter. |
| `backend/app/contexts/production/runtime_clock_observation_interpreter/runtime_clock_observation_interpreter.py` | Runtime clock observation interpreter. | ED-0027 | Concrete interpreter translating supported runtime clock Production Events into objective time-boundary Observations only. |
| `backend/app/contexts/production/runtime_clock_observation_interpreter/runtime_clock_observation_mapping.py` | Runtime clock observation mapping contract. | ED-0027 | Lightweight declarative mapping for schedule boundary reached, timer elapsed, and runtime clock status changed observations. |
| `backend/app/contexts/production/schedule_observation_interpreter/__init__.py` | Schedule observation interpreter package exports. | ED-0028 | Exports the concrete interpreter, rule, summary, and mapping contracts. |
| `backend/app/contexts/production/schedule_observation_interpreter/README.md` | Schedule observation interpreter package guide. | ED-0028 | Documents planned-reality observation scope, objective mappings, conservative status handling, truthful location anchoring, and exclusions. |
| `backend/app/contexts/production/schedule_observation_interpreter/schedule_interpreter_rule.py` | Schedule interpreter rule contract. | ED-0028 | Declarative rule for supported schedule source Production Event translations. |
| `backend/app/contexts/production/schedule_observation_interpreter/schedule_interpreter_summary.py` | Schedule interpreter summary contract. | ED-0028 | Lightweight diagnostics for the concrete schedule interpreter. |
| `backend/app/contexts/production/schedule_observation_interpreter/schedule_observation_interpreter.py` | Schedule observation interpreter. | ED-0028 | Concrete interpreter translating supported schedule source Production Events into objective schedule Observations only. |
| `backend/app/contexts/production/schedule_observation_interpreter/schedule_observation_mapping.py` | Schedule observation mapping contract. | ED-0028 | Lightweight declarative mapping for schedule activity updates, cancellations, planned time windows, and schedule source status changes. |
| `backend/app/contexts/production/transcript_observation_interpreter/__init__.py` | Transcript observation interpreter package exports. | ED-0029 | Exports the concrete interpreter, rule, summary, and mapping contracts. |
| `backend/app/contexts/production/transcript_observation_interpreter/README.md` | Transcript observation interpreter package guide. | ED-0029 | Documents language availability observation scope, transcript fidelity, conservative status handling, truthful location anchoring, and exclusions. |
| `backend/app/contexts/production/transcript_observation_interpreter/transcript_interpreter_rule.py` | Transcript interpreter rule contract. | ED-0029 | Declarative rule for supported transcript source Production Event translations. |
| `backend/app/contexts/production/transcript_observation_interpreter/transcript_interpreter_summary.py` | Transcript interpreter summary contract. | ED-0029 | Lightweight diagnostics for the concrete transcript interpreter. |
| `backend/app/contexts/production/transcript_observation_interpreter/transcript_observation_interpreter.py` | Transcript observation interpreter. | ED-0029 | Concrete interpreter translating supported transcript source Production Events into objective transcript Observations only. |
| `backend/app/contexts/production/transcript_observation_interpreter/transcript_observation_mapping.py` | Transcript observation mapping contract. | ED-0029 | Lightweight declarative mapping for transcript segment availability and transcript source status changes. |
| `backend/app/contexts/production/vision_observation_interpreter/__init__.py` | Vision observation interpreter package exports. | ED-0030 | Exports the concrete interpreter, rule, summary, and mapping contracts. |
| `backend/app/contexts/production/vision_observation_interpreter/README.md` | Vision observation interpreter package guide. | ED-0030 | Documents visual phenomena observation scope, visual metadata fidelity, conservative status handling, truthful location anchoring, and exclusions. |
| `backend/app/contexts/production/vision_observation_interpreter/vision_interpreter_rule.py` | Vision interpreter rule contract. | ED-0030 | Declarative rule for supported vision source Production Event translations. |
| `backend/app/contexts/production/vision_observation_interpreter/vision_interpreter_summary.py` | Vision interpreter summary contract. | ED-0030 | Lightweight diagnostics for the concrete vision interpreter. |
| `backend/app/contexts/production/vision_observation_interpreter/vision_observation_interpreter.py` | Vision observation interpreter. | ED-0030 | Concrete interpreter translating supported vision source Production Events into objective vision Observations only. |
| `backend/app/contexts/production/vision_observation_interpreter/vision_observation_mapping.py` | Vision observation mapping contract. | ED-0030 | Lightweight declarative mapping for visual detections and vision source status changes. |
| `backend/app/contexts/production/operator_adapter/__init__.py` | Operator source adapter package exports. | ED-0022 | Exports operator adapter contracts. |
| `backend/app/contexts/production/operator_adapter/README.md` | Operator source adapter package guide. | ED-0022 | Documents intentional human input reporting, Production Event mapping, and exclusions. |
| `backend/app/contexts/production/operator_adapter/operator_adapter_capability.py` | Operator adapter capability categories. | ED-0022 | Describes what operator input an adapter can report without implementing behavior. |
| `backend/app/contexts/production/operator_adapter/operator_adapter_identity.py` | Operator adapter identity contract. | ED-0022 | Generic adapter identity and kind values without provider names or UI assumptions. |
| `backend/app/contexts/production/operator_adapter/operator_adapter_summary.py` | Operator adapter summary contract. | ED-0022 | Lightweight diagnostics summary without workflow, event dispatch, or interpretation. |
| `backend/app/contexts/production/operator_adapter/operator_event.py` | Operator event contract. | ED-0022 | Adapter-level intentional human input event with generic Production Event mapping helper. |
| `backend/app/contexts/production/operator_adapter/operator_event_status.py` | Operator event status categories. | ED-0022 | Operator event lifecycle status values, not correctness states. |
| `backend/app/contexts/production/operator_adapter/operator_event_type.py` | Operator event type categories. | ED-0022 | Generic operator action categories without production conclusions. |
| `backend/app/contexts/production/operator_adapter/operator_source_adapter.py` | Operator source adapter contract. | ED-0022 | Generic operator adapter contract that emits Production Events only. |
| `backend/app/contexts/production/operational_product/__init__.py` | Production operational product package exports. | ED-0011 | Exports operational product contracts. |
| `backend/app/contexts/production/operational_product/operational_product.py` | Operational product contract. | ED-0011 | Generic downstream output of verified reasoning. |
| `backend/app/contexts/production/operational_product/operational_product_origin.py` | Operational product origin categories. | ED-0011 | Provider-agnostic execution-layer origins. |
| `backend/app/contexts/production/operational_product/operational_product_reference.py` | Operational product reference contract. | ED-0011 | Loose ID references to related objects. |
| `backend/app/contexts/production/operational_product/operational_product_status.py` | Operational product status categories. | ED-0011 | Execution lifecycle status for products only. |
| `backend/app/contexts/production/operational_product/operational_product_summary.py` | Operational product summary contract. | ED-0011 | Lightweight queue/dashboard summary without workflow policy. |
| `backend/app/contexts/production/operational_product/operational_product_type.py` | Operational product type categories. | ED-0011 | Broad product family categories only. |
| `backend/app/contexts/production/production_event/__init__.py` | Production event package exports. | ED-0013 | Exports production event contracts. |
| `backend/app/contexts/production/production_event/README.md` | Production event package guide. | ED-0013 | Documents runtime boundary scope and exclusions. |
| `backend/app/contexts/production/production_event/production_event.py` | Production event contract. | ED-0013 | Source-agnostic runtime input with occurred and received timestamps. |
| `backend/app/contexts/production/production_event/production_event_payload.py` | Production event payload contract. | ED-0013 | Immutable JSON-compatible runtime input data without provider-specific schema. |
| `backend/app/contexts/production/production_event/production_event_reference.py` | Production event reference contract. | ED-0013 | Lightweight ID or external string references without embedded target objects. |
| `backend/app/contexts/production/production_event/production_event_source.py` | Production event source categories. | ED-0013 | Provider-agnostic source categories only. |
| `backend/app/contexts/production/production_event/production_event_summary.py` | Production event summary contract. | ED-0013 | Lightweight log and diagnostics summary without reasoning or workflow triggers. |
| `backend/app/contexts/production/production_event/production_event_type.py` | Production event type categories. | ED-0013 / ED-0021 / ED-0022 | Generic happened-event types without conclusion-oriented names; ED-0021 adds `visual_detection_available`; ED-0022 adds `operator_input_received`. |
| `backend/app/contexts/production/recording_adapter/__init__.py` | Recording system adapter package exports. | ED-0016 | Exports recording adapter contracts. |
| `backend/app/contexts/production/recording_adapter/README.md` | Recording system adapter package guide. | ED-0016 | Documents adapter scope, generic Production Event mapping, and exclusions. |
| `backend/app/contexts/production/recording_adapter/recording_adapter_capability.py` | Recording adapter capability categories. | ED-0016 | Describes what a recording adapter can report without implementing behavior. |
| `backend/app/contexts/production/recording_adapter/recording_adapter_identity.py` | Recording adapter identity contract. | ED-0016 | Provider-agnostic adapter identity and kind values. |
| `backend/app/contexts/production/recording_adapter/recording_adapter_summary.py` | Recording adapter summary contract. | ED-0016 | Lightweight diagnostics summary without event creation or media inspection. |
| `backend/app/contexts/production/recording_adapter/recording_session_event.py` | Recording session event contract. | ED-0016 | Adapter-level recording activity event with generic Production Event mapping helper. |
| `backend/app/contexts/production/recording_adapter/recording_system_adapter.py` | Recording system adapter contract. | ED-0016 | Generic adapter contract that emits Production Events only. |
| `backend/app/contexts/production/recording_adapter/recording_system_status.py` | Recording system status categories. | ED-0016 | Generic recording system or adapter status values. |
| `backend/app/contexts/production/runtime_clock/__init__.py` | Runtime clock package exports. | ED-0019 | Exports runtime clock contracts. |
| `backend/app/contexts/production/runtime_clock/README.md` | Runtime clock package guide. | ED-0019 | Documents time-boundary ingress scope and scheduling exclusions. |
| `backend/app/contexts/production/runtime_clock/clock_capability.py` | Clock capability categories. | ED-0019 | Describes what the clock can report without implementing behavior. |
| `backend/app/contexts/production/runtime_clock/clock_event.py` | Clock event contract. | ED-0019 | Clock-level boundary event with generic Production Event mapping helper. |
| `backend/app/contexts/production/runtime_clock/clock_summary.py` | Clock summary contract. | ED-0019 | Lightweight diagnostics summary without time evaluation or event emission. |
| `backend/app/contexts/production/runtime_clock/runtime_clock.py` | Runtime clock contract. | ED-0019 | Generic immutable boundary evaluator and Production Event emitter contract. |
| `backend/app/contexts/production/runtime_clock/time_boundary.py` | Time boundary contract. | ED-0019 | Meaningful temporal boundary without workflow action or production outcome semantics. |
| `backend/app/contexts/production/runtime_clock/time_boundary_status.py` | Time boundary status categories. | ED-0019 | Boundary lifecycle values, not production outcome values. |
| `backend/app/contexts/production/runtime_clock/time_boundary_type.py` | Time boundary type categories. | ED-0019 | Generic temporal boundary categories without workflow actions. |
| `backend/app/contexts/production/schedule_adapter/__init__.py` | Schedule source adapter package exports. | ED-0018 | Exports schedule adapter contracts. |
| `backend/app/contexts/production/schedule_adapter/README.md` | Schedule source adapter package guide. | ED-0018 | Documents planned-world scope, generic Production Event mapping, and exclusions. |
| `backend/app/contexts/production/schedule_adapter/schedule_adapter_capability.py` | Schedule adapter capability categories. | ED-0018 | Describes what schedule changes an adapter can report without implementing behavior. |
| `backend/app/contexts/production/schedule_adapter/schedule_adapter_summary.py` | Schedule adapter summary contract. | ED-0018 | Lightweight diagnostics summary without scheduling, event creation, or observation generation. |
| `backend/app/contexts/production/schedule_adapter/schedule_source_adapter.py` | Schedule source adapter contract. | ED-0018 | Generic planned-activity adapter contract that emits Production Events only. |
| `backend/app/contexts/production/schedule_adapter/scheduled_activity.py` | Scheduled activity contract. | ED-0018 | Planned activity information without media, RecordingBlock, Session, or Observation ownership. |
| `backend/app/contexts/production/schedule_adapter/scheduled_activity_identity.py` | Scheduled activity identity contract. | ED-0018 | Descriptive planned-activity identity without runtime state. |
| `backend/app/contexts/production/schedule_adapter/scheduled_activity_status.py` | Scheduled activity status categories. | ED-0018 | Schedule-source state values, not production execution state. |
| `backend/app/contexts/production/schedule_adapter/scheduled_activity_type.py` | Scheduled activity type categories. | ED-0018 | Generic planned activity types without provider-specific assumptions. |
| `backend/app/contexts/production/session_window_product/__init__.py` | Production session window product package exports. | ED-0012 | Exports specialized session window product contracts. |
| `backend/app/contexts/production/session_window_product/README.md` | Session window product package guide. | ED-0012 | Documents scope, lineage, boundary confidence, and relationship to ED-0005 `SessionWindow`. |
| `backend/app/contexts/production/session_window_product/session_window_product.py` | Session window product contract. | ED-0012 | Verified media window for scheduled session information; references Operational Product by ID only. |
| `backend/app/contexts/production/session_window_product/session_window_product_boundary.py` | Session window product boundary contract. | ED-0012 | Start and end boundary confidence from `0.0` through `1.0`. |
| `backend/app/contexts/production/session_window_product/session_window_product_lineage.py` | Session window product lineage contract. | ED-0012 | ID-only traceability to Findings, Verification Decisions, and originating Operational Product. |
| `backend/app/contexts/production/session_window_product/session_window_product_status.py` | Session window product status categories. | ED-0012 | Specialized product lifecycle values, separate from verification and generic Operational Product status. |
| `backend/app/contexts/production/session_window_product/session_window_product_summary.py` | Session window product summary contract. | ED-0012 | Lightweight dashboard/package-workflow summary without package creation or media rendering. |
| `backend/app/contexts/production/timeline/recording_block.py` | Continuous recording block contract. | ED-0005 | Represents recording periods, not sessions. |
| `backend/app/contexts/production/timeline/schedule_reference.py` | External schedule reference contract. | ED-0005 | Uses generic external schedule language. |
| `backend/app/contexts/production/timeline/session_window.py` | Session window contract. | ED-0005 | Connects schedule reference to verified or proposed media range. |
| `backend/app/contexts/production/timeline/timeline_position.py` | Timeline position contract. | ED-0005 | Offset within a recording block. |
| `backend/app/contexts/production/timeline/timeline_range.py` | Timeline range contract. | ED-0005 | Span within one recording block. |
| `backend/app/contexts/production/transcript_adapter/__init__.py` | Transcript source adapter package exports. | ED-0020 | Exports transcript adapter contracts. |
| `backend/app/contexts/production/transcript_adapter/README.md` | Transcript source adapter package guide. | ED-0020 | Documents transcript availability reporting, Production Event mapping, and exclusions. |
| `backend/app/contexts/production/transcript_adapter/transcript_adapter_capability.py` | Transcript adapter capability categories. | ED-0020 | Describes what transcript information an adapter can report without implementing behavior. |
| `backend/app/contexts/production/transcript_adapter/transcript_adapter_identity.py` | Transcript adapter identity contract. | ED-0020 | Generic adapter identity and kind values without source-specific names. |
| `backend/app/contexts/production/transcript_adapter/transcript_adapter_summary.py` | Transcript adapter summary contract. | ED-0020 | Lightweight diagnostics summary without event dispatch or interpretation. |
| `backend/app/contexts/production/transcript_adapter/transcript_artifact_type.py` | Transcript artifact type categories. | ED-0020 | Generic transcript artifact categories without source-specific assumptions. |
| `backend/app/contexts/production/transcript_adapter/transcript_segment_event.py` | Transcript segment event contract. | ED-0020 | Adapter-level transcript activity event with generic Production Event mapping helper. |
| `backend/app/contexts/production/transcript_adapter/transcript_segment_status.py` | Transcript segment status categories. | ED-0020 | Transcript artifact availability status values, not correctness or approval states. |
| `backend/app/contexts/production/transcript_adapter/transcript_source_adapter.py` | Transcript source adapter contract. | ED-0020 | Generic transcript adapter contract that emits Production Events only. |
| `backend/app/contexts/production/verification/__init__.py` | Production verification package exports. | ED-0010 | Exports verification protocol contracts. |
| `backend/app/contexts/production/verification/verification_action.py` | Verification action categories. | ED-0010 | Judgment action values; not workflow states. |
| `backend/app/contexts/production/verification/verification_actor.py` | Verification actor contract. | ED-0010 | References decision actor IDs without user/auth behavior. |
| `backend/app/contexts/production/verification/verification_adjustment.py` | Verification adjustment contract. | ED-0010 | Describes adjustments without applying them. |
| `backend/app/contexts/production/verification/verification_decision.py` | Verification decision contract. | ED-0010 | Immutable judgment record referencing a finding ID. |
| `backend/app/contexts/production/verification/verification_note.py` | Verification note contract. | ED-0010 | Explanatory note attached to a decision. |
| `backend/app/contexts/production/verification/verification_reason.py` | Verification reason categories. | ED-0010 | Provider-agnostic reason values. |
| `backend/app/contexts/production/verification/verification_summary.py` | Verification summary contract. | ED-0010 | Summarizes decision history without final policy. |
| `backend/app/contexts/production/vision_adapter/__init__.py` | Vision source adapter package exports. | ED-0021 | Exports vision adapter contracts. |
| `backend/app/contexts/production/vision_adapter/README.md` | Vision source adapter package guide. | ED-0021 | Documents visual detection reporting, Production Event mapping, and exclusions. |
| `backend/app/contexts/production/vision_adapter/vision_adapter_capability.py` | Vision adapter capability categories. | ED-0021 | Describes what visual phenomena an adapter can report without implementing behavior. |
| `backend/app/contexts/production/vision_adapter/vision_adapter_identity.py` | Vision adapter identity contract. | ED-0021 | Generic adapter identity and kind values without source-specific names. |
| `backend/app/contexts/production/vision_adapter/vision_adapter_summary.py` | Vision adapter summary contract. | ED-0021 | Lightweight diagnostics summary without event dispatch or interpretation. |
| `backend/app/contexts/production/vision_adapter/vision_source_adapter.py` | Vision source adapter contract. | ED-0021 | Generic vision adapter contract that emits Production Events only. |
| `backend/app/contexts/production/vision_adapter/visual_detection_event.py` | Visual detection event contract. | ED-0021 | Adapter-level visual detection activity event with generic Production Event mapping helper. |
| `backend/app/contexts/production/vision_adapter/visual_detection_status.py` | Visual detection status categories. | ED-0021 | Visual detection availability status values. |
| `backend/app/contexts/production/vision_adapter/visual_detection_type.py` | Visual detection type categories. | ED-0021 | Generic observable visual phenomena categories without semantic meaning. |
| `backend/app/shared/domain_events/domain_event.py` | Base domain event contract. | ED-0004 | Generic event ID, type, timestamp, correlation, actor, and metadata. |
| `backend/app/shared/errors/errors.py` | Structured error contracts. | ED-0004 | Generic error categories only. |
| `backend/app/shared/ids/correlation_id.py` | Correlation ID contract. | ED-0004 | Generic UUID-compatible workflow tracing ID. |
| `backend/app/shared/ids/entity_id.py` | Entity ID contract. | ED-0004 | Generic UUID-compatible entity ID. |
| `backend/app/shared/result/result.py` | Result contract. | ED-0004 | Explicit success/failure result. |
| `backend/app/shared/time/clock.py` | Clock contracts. | ED-0004 | System and fixed clocks with UTC timestamps. |
| `backend/app/shared/time/time_range.py` | Time range contract. | ED-0004 | Immutable start/end/duration range. |
| `backend/tests/README.md` | Backend test suite guide. | ED-0002 / ED-0041 | Documents implemented backend coverage through ED-0040 and the ED-0041 review boundary. |
| `backend/tests/test_health.py` | Health endpoint test. | ED-0002 | Verifies startup through FastAPI TestClient. |
| `backend/tests/test_media_artifact_adapter_contracts.py` | Media artifact adapter contract tests. | ED-0017 | Covers adapter identity, artifact events, types, statuses, capabilities, Production Event mapping, summaries, and excluded behaviors. |
| `backend/tests/test_media_artifact_observation_interpreter_contracts.py` | Media artifact observation interpreter contract tests. | ED-0026 | Covers concrete interpreter creation, supported media artifact event mappings, zero-observation handling, traceability, objective wording, truthful ED-0025 locations, and excluded behaviors. |
| `backend/tests/test_evidence_semantics_contracts.py` | Evidence semantics refinement contract tests. | ED-0032 | Covers EvidenceConcern, EvidenceRole, EvidenceObservationReference, mixed roles, concern/purpose distinction, Observation reuse across concerns, builder semantics, and excluded downstream behavior. |
| `backend/tests/test_evidence_signal_contracts.py` | Evidence signal vocabulary contract tests. | ED-0035 | Covers EvidenceSignal values, ID-only references, EvidenceSet signal shapes, distinction from concern/role/strength/state, metadata independence, and excluded downstream behavior. |
| `backend/tests/test_generic_evidence_builder_semantic_selection_contracts.py` | Generic Evidence Builder semantic selection contract tests. | ED-0038 | Covers semantic selector creation, structured key priority, selection statuses, normalization, semantic rules, context keys, input reports, ordering, deduplication, and architectural boundaries. |
| `backend/tests/test_observation_evidence_builder_contracts.py` | Observation evidence builder contract tests. | ED-0031 / ED-0032 / ED-0035 | Covers builder creation, zero-observation input, single and multiple grouping, independent Evidence sets, first-class supporting/contradicting/contextual references, signal output, traceability preservation, explainability, and excluded later reasoning behavior. |
| `backend/tests/test_observation_interpreter_contracts.py` | Observation interpreter contract tests. | ED-0023 | Covers interpreter creation, support declarations, single and multi-event interpretation, result traceability, policy, summaries, and excluded behaviors. |
| `backend/tests/test_operational_state_taxonomy_contracts.py` | Operational State taxonomy contract tests. | ED-0033 | Covers state creation, enum values, subjects, basis traceability, summaries, initial taxonomy examples, family boundaries, StageFlow readiness limits, environmental context separation, and excluded transition/downstream behavior. |
| `backend/tests/test_operator_source_adapter_contracts.py` | Operator source adapter contract tests. | ED-0022 | Covers adapter identity, operator events, types, statuses, capabilities, Production Event mapping, summaries, and excluded behaviors. |
| `backend/tests/test_recording_coverage_evidence_builder_contracts.py` | Recording Coverage Evidence Builder contract tests. | ED-0036 | Covers builder, rule, mapping, result, summary, signal creation, recording Observation mappings, traceability, context preservation, duplicate handling, unsupported semantics, determinism, policy compatibility, and excluded downstream behavior. |
| `backend/tests/test_session_boundary_evidence_builder_contracts.py` | Session Boundary Evidence Builder contract tests. | ED-0039 | Covers contracts, start/end mappings, context preservation, temporal grouping, anchors, classification, deduplication, traceability, strength preservation, determinism, summaries, and architectural boundaries. |
| `backend/tests/test_session_transition_policy_contracts.py` | Session Transition Policy contract tests. | ED-0040 | Covers contracts, mappings, lifecycle transitions, categorical corroboration, independence, contradiction, freshness, ambiguity, context targeting, traceability, determinism, summaries, and architectural boundaries. |
| `backend/tests/test_recording_transition_policy_contracts.py` | Recording Transition Policy contract tests. | ED-0034 / ED-0035 | Covers concrete recording transition evaluations from EvidenceSignals, unrelated Evidence filtering, legacy metadata compatibility, determinism, explainability, summaries, mappings, and execution exclusions. |
| `backend/tests/test_runtime_clock_observation_interpreter_contracts.py` | Runtime clock observation interpreter contract tests. | ED-0027 | Covers concrete interpreter creation, supported clock event mappings, conservative status handling, zero-observation handling, traceability, objective wording, truthful ED-0025 locations, and excluded behaviors. |
| `backend/tests/test_schedule_observation_interpreter_contracts.py` | Schedule observation interpreter contract tests. | ED-0028 | Covers concrete interpreter creation, supported schedule event mappings, conservative status handling, zero-observation handling, traceability, planned-reality wording, truthful ED-0025 locations, and excluded behaviors. |
| `backend/tests/test_transcript_observation_interpreter_contracts.py` | Transcript observation interpreter contract tests. | ED-0029 | Covers concrete interpreter creation, supported transcript event mappings, conservative status handling, zero-observation handling, traceability, transcript text fidelity, truthful ED-0025 locations, and excluded behaviors. |
| `backend/tests/test_transcript_continuity_evidence_builder_contracts.py` | Transcript Continuity Evidence Builder contract tests. | ED-0037 | Covers builder, rule, mapping, result, summary, signal creation, transcript lifecycle mappings, stream grouping, traceability, context preservation, duplicate handling, unsupported semantics, no gap inference, determinism, and excluded downstream behavior. |
| `backend/tests/test_transition_policy_contracts.py` | Generic Transition Policy contract tests. | ED-0034 | Covers generic policy creation, TransitionEvaluation, TransitionReason, outcomes, summaries, explainability, and execution/infrastructure exclusions. |
| `backend/tests/test_vision_observation_interpreter_contracts.py` | Vision observation interpreter contract tests. | ED-0030 | Covers concrete interpreter creation, supported vision event mappings, conservative status handling, zero-observation handling, traceability, visual metadata fidelity, truthful ED-0025 locations, and excluded behaviors. |
| `backend/tests/test_production_dispatcher_contracts.py` | Production event dispatcher contract tests. | ED-0015 | Covers dispatch routing, contexts, rules, summaries, unchanged interpreter results, and excluded infrastructure behaviors. |
| `backend/tests/test_production_evidence_contracts.py` | Production evidence contract tests. | ED-0007 / ED-0035 | Covers evidence primitives, signal summaries, and boundary rules. |
| `backend/tests/test_production_finding_contracts.py` | Production finding contract tests. | ED-0009 | Covers finding primitives and boundary rules. |
| `backend/tests/test_production_hypothesis_contracts.py` | Production hypothesis contract tests. | ED-0008 | Covers hypothesis primitives and boundary rules. |
| `backend/tests/test_production_interpreter_contracts.py` | Production event interpreter contract tests. | ED-0014 | Covers interpreter matching, results, context, rules, summaries, and excluded behaviors. |
| `backend/tests/test_production_observation_contracts.py` | Production observation contract tests. | ED-0006 | Covers observation primitives and boundary rules. |
| `backend/tests/test_recording_activity_observation_interpreter_contracts.py` | Recording activity observation interpreter contract tests. | ED-0024 | Covers concrete interpreter creation, supported recording event mappings, zero-observation handling, traceability, objective wording, and excluded behaviors. |
| `backend/tests/test_production_operational_product_contracts.py` | Production operational product contract tests. | ED-0011 | Covers generic product primitives and boundary rules. |
| `backend/tests/test_production_event_contracts.py` | Production event contract tests. | ED-0013 | Covers runtime event primitives, payload immutability, references, summaries, and excluded behaviors. |
| `backend/tests/test_production_session_window_product_contracts.py` | Production session window product contract tests. | ED-0012 | Covers specialized product primitives, lineage, boundary confidence, summaries, and excluded behaviors. |
| `backend/tests/test_production_timeline_contracts.py` | Production timeline contract tests. | ED-0005 | Tests are placed under `backend/tests/` per existing convention. |
| `backend/tests/test_production_verification_contracts.py` | Production verification contract tests. | ED-0010 | Covers append-only verification primitives and boundary rules. |
| `backend/tests/test_recording_system_adapter_contracts.py` | Recording system adapter contract tests. | ED-0016 | Covers adapter identity, status, capabilities, session events, Production Event mapping, summaries, and excluded behaviors. |
| `backend/tests/test_runtime_clock_contracts.py` | Runtime clock contract tests. | ED-0019 | Covers clock contracts, time boundaries, boundary evaluation, Production Event mapping, summaries, and excluded behaviors. |
| `backend/tests/test_schedule_source_adapter_contracts.py` | Schedule source adapter contract tests. | ED-0018 | Covers planned activity contracts, schedule adapter capabilities, Production Event mapping, summaries, and excluded behaviors. |
| `backend/tests/test_shared_contracts.py` | Shared contract tests. | ED-0004 | Covers backend contract primitives. |
| `backend/tests/test_transcript_source_adapter_contracts.py` | Transcript source adapter contract tests. | ED-0020 | Covers adapter identity, segment events, artifact types, statuses, capabilities, Production Event mapping, summaries, and excluded behaviors. |
| `backend/tests/test_vision_source_adapter_contracts.py` | Vision source adapter contract tests. | ED-0021 | Covers adapter identity, visual detection events, types, statuses, capabilities, Production Event mapping, summaries, and excluded behaviors. |

## Frontend Files

| Path | Purpose | Owning Engineering Directive | Notes |
| --- | --- | --- | --- |
| `frontend/README.md` | Frontend workspace guide. | ED-0003 | Documents setup, commands, and frontend boundaries. |
| `frontend/package.json` | Frontend package scripts and dependencies. | ED-0003 | Defines Next.js, TypeScript, Tailwind, shadcn, TanStack Query, React Hook Form, and Zod dependencies. |
| `frontend/package-lock.json` | Locked frontend dependency graph. | ED-0003 | Generated by `npm install`. |
| `frontend/next.config.ts` | Next.js configuration. | ED-0003 | Minimal configuration. |
| `frontend/tsconfig.json` | TypeScript configuration. | ED-0003 | Strict TypeScript with Next.js plugin. |
| `frontend/postcss.config.mjs` | PostCSS configuration. | ED-0003 | Enables Tailwind CSS v4 PostCSS plugin. |
| `frontend/eslint.config.mjs` | ESLint flat configuration. | ED-0003 | Uses Next.js core web vitals and TypeScript configs. |
| `frontend/components.json` | shadcn/ui configuration. | ED-0003 | Initializes shadcn aliases and CSS variable mode without generating UI components. |
| `frontend/next-env.d.ts` | Next.js TypeScript environment declarations. | ED-0003 | Generated by Next.js. |
| `frontend/app/layout.tsx` | Root application layout. | ED-0003 | Minimal metadata and global style import. |
| `frontend/app/page.tsx` | Root page. | ED-0003 | Displays required ED-0003 placeholder information only. |
| `frontend/app/globals.css` | Global Tailwind and CSS variable foundation. | ED-0003 | Tailwind v4 CSS-first setup with semantic roles. |
| `frontend/src/shared/domain-events/domain-event.ts` | Frontend base domain event type. | ED-0004 | Generic event shape only. |
| `frontend/src/shared/errors/errors.ts` | Frontend structured error types and helpers. | ED-0004 | Generic error categories only. |
| `frontend/src/shared/ids/correlation-id.ts` | Frontend correlation ID type and helpers. | ED-0004 | Branded UUID-compatible string. |
| `frontend/src/shared/ids/entity-id.ts` | Frontend entity ID type and helpers. | ED-0004 | Branded UUID-compatible string. |
| `frontend/src/shared/result/result.ts` | Frontend result type and helpers. | ED-0004 | Explicit success/failure union. |
| `frontend/src/shared/time/clock.ts` | Frontend clock and timestamp contracts. | ED-0004 | System and fixed clock helpers. |
| `frontend/src/shared/time/time-range.ts` | Frontend time range type and helper. | ED-0004 | Immutable parseable timestamp range. |
| `frontend/src/styles/design_tokens.ts` | Initial design token module. | ED-0003 | Placeholder tokens for future theming and design system work. |

## Documentation Files

| Path | Purpose | Owning Engineering Directive | Notes |
| --- | --- | --- | --- |
| `docs/00_Glossary.md` | Shared terminology. | Existing architecture work | Preserved by ED-0001. |
| `docs/00.5_Domain_Model.md` | StageFlow domain model. | Existing architecture work / AR-2.1 | AR-2.1 adds concise Perception Layer, objective Observation, ObservationLocation, traceability, and payload notes. |
| `docs/03.5_Technology_Selections.md` | Technology selections specification. | Existing architecture work | Empty at ED-0002 implementation time; preserved by ED-0002. |
| `docs/03.6_Architecture_Layers.md` | Architecture Layers specification. | Existing architecture work | Preserved by ED-0001. |
| `docs/04.5_Bounded_Contexts.md` | Bounded Contexts specification. | Existing architecture work / AR-2.1 | AR-2.1 notes that Perception Layer contracts remain in Production pending future bounded-context realignment. |
| `docs/04.6_Integration_Architecture.md` | Integration Architecture specification. | Existing architecture work / AR-2.1 | AR-2.1 clarifies adapters emit Production Events and Observation Interpreters produce objective Observations before reasoning. |
| `docs/05_Reasoning_Model.md` | Reasoning Model architecture reference. | AR-1.4 / AR-2.0 / AR-2.1 | AR-2.1 consolidates the Perception Layer between Production Events and Objective Observations. |
| `docs/reviews/ED-0041_ARCHITECTURE_CODEBASE_REVIEW.md` | Comprehensive architecture and codebase review through ED-0040. | ED-0041 | Covers all required review areas, four representative flow traces, repository health, state-acceptance readiness, positive findings, risks, and the explicit review decision. |
| `docs/reviews/ED-0041_FINDINGS_REGISTER.md` | Evidence-backed ED-0041 findings register. | ED-0041 | Records severity, category, evidence, impact, response, change risk, directive, and disposition for every finding. |
| `docs/reviews/ED-0041_DIRECTIVE_ROADMAP.md` | Prioritized post-review directive roadmap. | ED-0041 | Separates pre-ED-0042 blockers, ED-0042 constraints, targeted follow-ups, deferred improvements, and intentionally unchanged patterns. |
